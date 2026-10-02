"""Exercise reward endpoints with an isolated database and controlled travel clock."""

import json
import re
import tempfile
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import rewards
import server


class QuietHandler(server.AppHandler):
    def log_message(self, *args):
        pass


class RewardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory(prefix="puman-reward-tests-")
        cls.addClassCleanup(temp.cleanup)
        settings = patch.object(server, "DB_PATH", Path(temp.name) / "test.sqlite3")
        settings.start()
        cls.addClassCleanup(settings.stop)
        server.init_db()
        cls.http = server.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.base = f"http://127.0.0.1:{cls.http.server_port}"
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join(timeout=5)

    def setUp(self):
        self.user = "reward-test-" + uuid.uuid4().hex

    def request(self, path, body=None, method=None, user=None):
        request = Request(self.base + path, method=method or ("GET" if body is None else "POST"),
                          data=json.dumps(body).encode() if body is not None else None,
                          headers={"Content-Type": "application/json", "X-User-ID": user or self.user})
        try:
            response = urlopen(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def ok(self, path, body=None, **kwargs):
        status, result = self.request(path, body, **kwargs)
        self.assertEqual(status, 200, result)
        return result

    def save(self, completed=None, **state):
        return self.ok("/api/state", {"state": {"completed": completed or {"home": [1, 2, 3]}, **state}}, method="PUT")

    def start(self, milestone=3, line="home"):
        return self.ok("/api/travel/start", {"line": line, "milestone": milestone})

    def ledger_count(self):
        with server.db_session() as connection:
            return connection.execute("SELECT COUNT(*) FROM reward_ledger WHERE user_id=?", (self.user,)).fetchone()[0]

    def test_question_contract_matches_frontend(self):
        source = (server.ROOT / "index.html").read_text(encoding="utf-8")
        quiz = source.split("const DAILY_QUIZ = [", 1)[1].split("\n];", 1)[0]
        self.assertEqual(tuple(map(int, re.findall(r"\bans:(\d+)", quiz))), rewards.QUIZ_ANSWERS)

    def test_wrong_retry_correct_and_duplicate_rewards(self):
        payload = {"line": "home", "day": 1, "selected": 3, "correct": True, "coins": 999}
        wrong = self.ok("/api/daily-quiz/answer", payload)
        self.assertFalse(wrong["correct"])
        self.assertEqual(wrong["rewards"]["gold"], 0)
        self.ok("/api/daily-quiz/answer", payload)
        correct = self.ok("/api/daily-quiz/answer", {**payload, "selected": 0})
        self.assertTrue(correct["awarded"])
        self.assertEqual(correct["rewards"]["gold"], 1)
        duplicate = self.ok("/api/daily-quiz/answer", payload)
        self.assertTrue(duplicate["correct"])
        self.assertFalse(duplicate["awarded"])
        self.assertEqual(duplicate["rewards"]["gold"], 1)
        self.assertEqual(self.ledger_count(), 1)
        with server.db_session() as connection:
            data = connection.execute("SELECT features_json FROM daily_behavior_features WHERE user_id=? AND day=1", (self.user,)).fetchone()[0]
            features = json.loads(data)
            self.assertEqual(features["quiz_attempts"], 2)
            self.assertEqual(features["quiz_accuracy"], 0.5)

    def test_concurrent_correct_answers_only_credit_once(self):
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(lambda _: self.ok("/api/daily-quiz/answer", {"line": "home", "day": 1, "selected": 0}), range(5)))
        self.assertEqual(sum(result["awarded"] for result in results), 1)
        self.assertTrue(all(result["rewards"]["gold"] == 1 for result in results))
        self.assertEqual(self.ledger_count(), 1)

    def test_question_mapping_separate_days_lines_and_users(self):
        expected = 0
        for index, line in enumerate(rewards.LINES):
            for day in (1, 15, 21):
                question = (day + index) % len(rewards.QUIZ_ANSWERS)
                result = self.ok("/api/daily-quiz/answer", {"line": line, "day": day, "selected": rewards.QUIZ_ANSWERS[question]})
                expected += 1
                self.assertEqual(result["question"], question)
                self.assertEqual(result["rewards"]["gold"], expected)
        self.assertEqual(self.ok("/api/rewards", user="another-test-user")["rewards"]["gold"], 0)

    def test_invalid_answers_do_not_create_rewards(self):
        valid = {"line": "home", "day": 1, "selected": 0}
        for key, values in (("line", [None, "unknown", []]), ("day", [True, 0, 22, 1.5, "1"]), ("selected", [False, -1, 4, 0.5, "0", None])):
            for value in values:
                with self.subTest(key=key, value=value):
                    self.assertEqual(self.request("/api/daily-quiz/answer", {**valid, key: value})[0], 400)
        self.assertEqual(self.ledger_count(), 0)

    def test_stale_or_forged_state_cannot_overwrite_rewards(self):
        self.save()
        trip = self.start()["trip"]
        self.ok("/api/daily-quiz/answer", {"line": "home", "day": 1, "selected": 0})
        self.save(rewards={"gold": 999999, "active_trip": None, "quizzes": {}}, gold=4)
        server.init_db()  # Reopening/migrating the existing database preserves claims.
        result = self.ok("/api/state")
        self.assertNotIn("rewards", result["state"])
        self.assertEqual(result["rewards"]["gold"], 1)
        self.assertEqual(result["rewards"]["active_trip"]["id"], trip["id"])
        self.assertTrue(result["rewards"]["quizzes"]["home:1"]["correct"])

    def test_trip_requires_distinct_completed_tasks(self):
        self.save(completed={"home": [1, 1, 2, True, "3", 0, 22]})
        self.assertEqual(self.request("/api/travel/start", {"line": "home", "milestone": 3})[0], 400)
        status, _ = self.request("/api/events", {"event_type": "daily_task_completed", "payload": {"line": "home", "day": 3}})
        self.assertEqual(status, 201)
        self.assertTrue(self.start()["started"])
        for milestone in (0, 2, 4, 24, True, "3"):
            self.assertEqual(self.request("/api/travel/start", {"line": "home", "milestone": milestone})[0], 400)

    def test_single_active_trip_per_line_and_parallel_goals(self):
        self.save(completed={"home": list(range(1, 7)), "baby": [1, 2, 3]})
        first = self.start()
        self.assertTrue(first["started"])
        for line, milestone in (("home", 3), ("home", 6)):
            result = self.start(milestone, line)
            self.assertFalse(result["started"])
            self.assertEqual(result["trip"]["id"], first["trip"]["id"])
        parallel = self.start(3, "baby")
        self.assertTrue(parallel["started"])
        self.assertNotEqual(parallel["trip"]["id"], first["trip"]["id"])
        self.assertEqual({trip["line"] for trip in parallel["rewards"]["active_trips"]}, {"home", "baby"})
        self.assertEqual(first["trip"]["ready_at"] - first["trip"]["started_at"], 45000)

    def test_early_and_foreign_claims_do_not_award(self):
        self.save()
        with patch.object(rewards, "now_ms", return_value=1_000_000):
            trip = self.start()["trip"]
            result = self.ok("/api/travel/claim", {"trip_id": trip["id"], "coins": 999, "ready_at": 0})
        self.assertTrue(result["pending"])
        self.assertEqual(result["remaining_ms"], 45000)
        self.assertEqual(result["rewards"]["gold"], 0)
        with patch.object(rewards, "now_ms", return_value=trip["ready_at"]):
            self.assertEqual(self.request("/api/travel/claim", {"trip_id": trip["id"]}, user="foreign-test-user")[0], 400)
        self.assertEqual(self.ledger_count(), 0)

    def test_concurrent_return_and_lost_response_retry_only_credit_once(self):
        self.save()
        trip = self.start()["trip"]
        with patch.object(rewards, "now_ms", return_value=trip["ready_at"]):
            with ThreadPoolExecutor(max_workers=5) as pool:
                results = list(pool.map(lambda _: self.ok("/api/travel/claim", {"trip_id": trip["id"]}), range(5)))
            retry = self.ok("/api/travel/claim", {"trip_id": trip["id"]})
        self.assertEqual(sum(result["awarded"] for result in results), 1)
        self.assertEqual(len({(result["coins"], result["souvenir"]) for result in results}), 1)
        self.assertGreaterEqual(retry["coins"], 3)
        self.assertLessEqual(retry["coins"], 10)
        self.assertFalse(retry["awarded"])
        self.assertIsNone(retry["rewards"]["active_trip"])
        self.assertEqual(retry["rewards"]["gold"], retry["coins"])
        self.assertEqual(self.ledger_count(), 1)
        self.assertFalse(self.start()["started"])

    def test_reward_bounds_and_new_souvenirs_across_trips(self):
        self.save(completed={"home": list(range(1, 7))})
        souvenirs = []
        for milestone, random_value, expected in ((3, 0, 3), (6, 7, 10)):
            trip = self.start(milestone)["trip"]
            with patch.object(rewards, "now_ms", return_value=trip["ready_at"]), patch.object(rewards.secrets, "randbelow", return_value=random_value):
                result = self.ok("/api/travel/claim", {"trip_id": trip["id"]})
            self.assertEqual(result["coins"], expected)
            souvenirs.append(result["souvenir"])
        self.assertEqual(len(set(souvenirs)), 2)
        self.assertEqual(self.ok("/api/rewards")["rewards"]["gold"], 13)

    def test_failed_transaction_can_retry_without_losing_or_duplicating_credit(self):
        payload = {"line": "home", "day": 1, "selected": 0}
        with patch.object(server.AppHandler, "recompute_behavior", side_effect=RuntimeError("test rollback")):
            self.assertEqual(self.request("/api/daily-quiz/answer", payload)[0], 500)
        self.assertEqual(self.ledger_count(), 0)
        self.assertEqual(self.ok("/api/rewards")["rewards"]["quizzes"], {})
        self.assertTrue(self.ok("/api/daily-quiz/answer", payload)["awarded"])
        self.assertEqual(self.ledger_count(), 1)


if __name__ == "__main__":
    unittest.main()
