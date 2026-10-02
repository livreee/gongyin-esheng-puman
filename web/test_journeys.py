"""Independent goal saves, diaries, behavior views and parallel trip migration."""

import copy
import json
import tempfile
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import ai_service
import rewards
import server


class QuietHandler(server.AppHandler):
    def log_message(self, *args):
        pass


class JourneyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory(prefix="puman-journey-tests-")
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
        self.user = "journeys-" + uuid.uuid4().hex

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

    def state(self):
        return {
            "multiLineVersion": 1, "line": "custom", "day": 2,
            "lineDays": {"home": 8, "solo": 4, "custom": 2},
            "completed": {"home": [1, 2, 3], "solo": [1], "custom": [1]},
            "challenges": {"home": [1, 2], "solo": [1], "custom": []},
            "lineRecords": {
                "solo": [{"line": "solo", "day": 1, "amount": 30, "from": "每日剧情任务"}],
                "custom": [{"line": "custom", "day": 1, "amount": 12.34, "from": "自定义存钱日记", "note": "省下饮料钱"}],
            },
            "customLine": {"name": "报名考试", "goal": 500, "dailyTarget": 20, "intro": "给成长留一笔预算", "entries": {
                "1": {"target": 20, "amount": 12.34, "note": "省下饮料钱", "createdAt": "2026-10-02T10:00:00Z", "completed": True},
                "2": {"target": 25, "amount": 0, "note": "今天先写计划", "completed": False},
            }},
        }

    def test_multiline_and_diary_round_trip_survives_reopen(self):
        state = self.state()
        self.ok("/api/state", {"state": state}, method="PUT")
        server.init_db()
        result = self.ok("/api/state")["state"]
        self.assertEqual(result, state)
        self.assertNotEqual(result["lineDays"]["solo"], result["lineDays"]["custom"])
        self.assertNotEqual(result["lineRecords"]["solo"][0]["amount"], result["lineRecords"]["custom"][0]["amount"])
        self.assertIsNone(self.ok("/api/state", user="other-journey-user")["state"])

    def test_diary_plan_update_preserves_other_goals_and_rewards(self):
        state = self.state()
        self.ok("/api/state", {"state": state}, method="PUT")
        reward = self.ok("/api/daily-quiz/answer", {"line": "custom", "day": 1, "selected": 0})
        before = copy.deepcopy(state["lineRecords"]["solo"])
        state["customLine"]["entries"]["1"]["note"] = "修改回顾，不是重复存钱"
        state["customLine"]["entries"]["2"]["target"] = 15.5
        saved = self.ok("/api/state", {"state": state}, method="PUT")
        self.assertEqual(saved["rewards"]["gold"], reward["rewards"]["gold"])
        self.assertEqual(self.ok("/api/state")["state"]["lineRecords"]["solo"], before)

    def test_invalid_custom_amounts_fail_without_overwriting(self):
        original = self.state()
        self.ok("/api/state", {"state": original}, method="PUT")
        for value in (-1, 0, True, "20", 1.001, 1000001, float("nan"), float("inf")):
            with self.subTest(value=value):
                state = self.state()
                state["customLine"]["goal"] = value
                self.assertEqual(self.request("/api/state", {"state": state}, method="PUT")[0], 400)
        self.assertEqual(self.ok("/api/state")["state"], original)

    def test_invalid_diary_days_text_and_crossline_records(self):
        variants = []
        state = self.state()
        state["customLine"]["entries"]["22"] = state["customLine"]["entries"]["1"]
        variants.append(state)
        state = self.state()
        state["customLine"]["entries"]["1"]["note"] = "长" * 241
        variants.append(state)
        state = self.state()
        state["lineRecords"]["solo"][0]["line"] = "home"
        variants.append(state)
        state = self.state()
        state["lineDays"]["__proto__"] = 1
        variants.append(state)
        state = self.state()
        state["lineDays"]["home"] = True
        variants.append(state)
        state = self.state()
        state["completed"]["custom"] = [1, 1]
        variants.append(state)
        for state in variants:
            self.assertEqual(self.request("/api/state", {"state": state}, method="PUT")[0], 400)

    def test_legacy_state_stays_intact(self):
        original = {"day": 7, "line": "solo", "records": [{"day": 1, "amount": 50}], "completed": {"solo": [1, 2]}}
        self.ok("/api/state", {"state": original}, method="PUT")
        self.assertEqual(self.ok("/api/state")["state"], original)

    def test_behavior_query_is_partitioned_by_line(self):
        for line, days in (("home", [1, 2, 3]), ("solo", [2]), ("custom", [1, 3])):
            for day in days:
                status, _ = self.request("/api/events", {"event_type": "daily_task_completed", "payload": {"line": line, "day": day}})
                self.assertEqual(status, 201)
        for line, expected in (("home", 3), ("solo", 1), ("custom", 2), ("baby", 0)):
            result = self.ok(f"/api/behavior/state?line={line}&day=3")
            self.assertEqual(result["line"], line)
            self.assertEqual(result["summary"]["completed_days"], expected)
        self.assertEqual(self.ok("/api/behavior/state?line=home&day=3")["summary"]["streak"], 3)
        self.assertEqual(self.ok("/api/behavior/state?line=custom&day=3")["summary"]["streak"], 1)
        self.assertEqual(self.request("/api/behavior/state?line=unknown&day=3")[0], 400)
        self.assertEqual(self.ok("/api/behavior/recompute", {"line": "solo", "day": 3})["summary"]["completed_days"], 1)

    def test_parallel_rewards_and_claiming_one_line_leaves_other_active(self):
        state = self.state()
        state["completed"] = {line: [1, 2, 3] for line in ("home", "solo", "custom")}
        self.ok("/api/state", {"state": state}, method="PUT")
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda line: self.ok("/api/travel/start", {"line": line, "milestone": 3}), ("home", "solo", "custom")))
        trips = self.ok("/api/rewards")["rewards"]["active_trips"]
        self.assertEqual(len(trips), 3)
        self.assertEqual(len({trip["id"] for trip in trips}), 3)
        for line in ("home", "solo", "custom"):
            selected = rewards.QUIZ_ANSWERS[(1 + rewards.LINES.index(line)) % len(rewards.QUIZ_ANSWERS)]
            self.assertTrue(self.ok("/api/daily-quiz/answer", {"line": line, "day": 1, "selected": selected})["awarded"])
        with patch.object(rewards, "now_ms", return_value=max(trip["ready_at"] for trip in trips)):
            claimed = self.ok("/api/travel/claim", {"trip_id": trips[0]["id"]})
        self.assertEqual(len(claimed["rewards"]["active_trips"]), 2)
        self.assertEqual(claimed["rewards"]["gold"], 3 + claimed["coins"])

    def test_old_global_trip_index_migrates_without_losing_active_trip(self):
        # Isolated secondary file so other test users' parallel trips are irrelevant.
        with tempfile.TemporaryDirectory(prefix="puman-index-migration-") as folder:
            with patch.object(server, "DB_PATH", Path(folder) / "old.sqlite3"):
                server.init_db()
                with server.db_session() as connection:
                    connection.execute("DROP INDEX one_active_pet_trip_line")
                    connection.execute("CREATE UNIQUE INDEX one_active_pet_trip ON pet_trips(user_id) WHERE claimed_at IS NULL")
                    connection.execute("INSERT INTO pet_trips(id,user_id,line,milestone,started_at,ready_at) VALUES('kept','migration-user','solo',3,1,45001)")
                server.init_db()
                with server.db_session() as connection:
                    connection.execute("INSERT INTO pet_trips(id,user_id,line,milestone,started_at,ready_at) VALUES('parallel','migration-user','custom',3,1,45001)")
                    self.assertEqual(len(rewards.snapshot(connection, "migration-user")["active_trips"]), 2)

    def test_learning_profile_and_custom_coach_use_current_goal(self):
        context = ai_service.profile_context({"answers": [0, 2, 0, 1]})
        self.assertEqual(context["line"], "solo")
        self.assertEqual(context["line_name"], "攒一笔学习基金")
        self.assertIn("技能", context["evidence"][2]["answer"])
        with patch.object(ai_service, "_call_json", return_value=(None, "rules", "test")):
            coach = ai_service.generate_coach({"line": "custom", "day": 2, "goal": {"name": "考试报名费"}})
        self.assertIn("考试报名费", coach["coach"]["message"])


if __name__ == "__main__":
    unittest.main()
