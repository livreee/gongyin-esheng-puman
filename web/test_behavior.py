"""Regression checks using an isolated SQLite database, never puman.sqlite3."""

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import server
from behavior_model import analyze_events


def event(day, kind="daily_task_completed", **payload):
    return {"event_type": kind, "payload": {"day": day, **payload}}


class ModelTests(unittest.TestCase):
    def test_empty_sequence_is_insufficient(self):
        summary = analyze_events([], 21)["summary"]
        self.assertEqual(summary["data_status"], "insufficient")
        self.assertEqual(summary["active_days"], 0)
        self.assertEqual(summary["streak"], 0)

    def test_break_resets_streak_and_return_measures_gap(self):
        rows = analyze_events([event(1), event(2), event(5)], 5)["daily_features"]
        self.assertEqual([row["streak"] for row in rows], [1, 2, 0, 0, 1])
        self.assertEqual([row["gap_days"] for row in rows], [0, 0, 1, 2, 2])

    def test_stability_break_and_recovery(self):
        events = [event(day, kind, correct=True) for day in (1, 2, 3, 7)
                  for kind in ("daily_task_completed", "daily_quiz_answered")]
        timeline = analyze_events(events, 7)["timeline"]
        self.assertEqual(timeline[2]["state"], "stable")
        self.assertEqual(timeline[5]["state"], "fluctuation")
        self.assertEqual(timeline[6]["state"], "recovery")
        for row in timeline:
            self.assertAlmostEqual(sum(row["probabilities"].values()), 1.0, places=5)

    def test_features_ignore_system_events_and_invalid_days(self):
        events = [event(1, "ai_coach_generated"), event(1.5), event(True),
                  event(22), event(1, "daily_quiz_answered", correct=False),
                  event(1, "daily_quiz_answered", correct=True)]
        features = analyze_events(events, 1)["daily_features"][0]
        self.assertEqual(features["event_count"], 2)
        self.assertEqual(features["quiz_accuracy"], 0.5)
        self.assertEqual(features["task_completed_flag"], 0)

    def test_future_events_do_not_change_historical_inference(self):
        early = [event(1), event(2)]
        self.assertEqual(analyze_events(early, 2), analyze_events(early + [event(7)], 2))

    def test_missing_quiz_is_distinct_from_wrong_quiz(self):
        missing = analyze_events([event(1)], 1)
        wrong = analyze_events([event(1), event(1, "daily_quiz_answered", correct=False)], 1)
        self.assertEqual(missing["daily_features"][0]["quiz_attempts"], 0)
        self.assertEqual(wrong["daily_features"][0]["quiz_attempts"], 1)
        self.assertNotEqual(missing["summary"]["probabilities"], wrong["summary"]["probabilities"])


class QuietHandler(server.AppHandler):
    def log_message(self, *args):
        pass


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="puman-behavior-tests-")
        cls.original_path = server.DB_PATH
        server.DB_PATH = Path(cls.temp.name) / "test.sqlite3"
        server.init_db()
        cls.http = server.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.base = "http://127.0.0.1:" + str(cls.http.server_port)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join(timeout=5)
        server.DB_PATH = cls.original_path
        cls.temp.cleanup()

    def setUp(self):
        self.user = "api-test-" + self._testMethodName.replace("_", "-")

    def id(self):
        return self.user

    def request(self, method, path, body=None, user=None):
        data = json.dumps(body).encode() if body is not None else None
        request = Request(self.base + path, data=data, method=method, headers={
            "Content-Type": "application/json", "X-User-ID": user or self.id(),
        })
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def post_event(self, item):
        status, body = self.request("POST", "/api/events", item)
        self.assertEqual(status, 201, body)

    def test_timeline_and_persisted_features(self):
        for day in (1, 2, 3):
            self.post_event(event(day))
            self.post_event(event(day, "daily_quiz_answered", correct=True))
        status, body = self.request("GET", "/api/behavior/state")
        self.assertEqual(status, 200)
        self.assertEqual(body["summary"]["streak"], 3)
        status, body = self.request("GET", "/api/behavior/timeline?day=3")
        self.assertEqual([row["completed_days"] for row in body["timeline"]], [1, 2, 3])
        connection = server.connect_db()
        try:
            features = json.loads(connection.execute(
                "SELECT features_json FROM daily_behavior_features WHERE user_id = ? AND day = 2",
                (self.id(),),
            ).fetchone()[0])
            self.assertEqual(features["quiz_accuracy"], 1.0)
            self.assertEqual(features["streak"], 2)
            self.assertIn("features", features)
            rows = connection.execute("SELECT day, summary_json FROM behavior_states WHERE user_id = ?", (self.id(),))
            for day, value in rows:
                self.assertEqual(json.loads(value)["day"], day)
        finally:
            connection.close()

    def test_late_event_refreshes_later_cached_days(self):
        self.post_event(event(3))
        self.request("GET", "/api/behavior/state?day=5")
        self.post_event(event(1))
        connection = server.connect_db()
        try:
            value = connection.execute(
                "SELECT summary_json FROM behavior_states WHERE user_id = ? AND day = 5", (self.id(),)
            ).fetchone()[0]
            self.assertEqual(json.loads(value)["completed_days"], 2)
        finally:
            connection.close()

    def test_invalid_input_returns_400_without_recording(self):
        for value in (0, 22, True, 1.5, "bad", None):
            status, _ = self.request("POST", "/api/events", event(value))
            self.assertEqual(status, 400)
        for value in ("0", "22", "1.5", "bad"):
            status, _ = self.request("GET", "/api/behavior/state?day=" + value)
            self.assertEqual(status, 400)
        status, _ = self.request("POST", "/api/events", event(1, "daily_quiz_answered", correct="false"))
        self.assertEqual(status, 400)
        _, body = self.request("GET", "/api/metrics")
        self.assertEqual(body["events"], {})

    def test_user_isolation_and_recompute(self):
        self.post_event(event(1))
        _, body = self.request("GET", "/api/behavior/state", user="isolated-empty-user")
        self.assertEqual(body["summary"]["active_days"], 0)
        status, body = self.request("POST", "/api/behavior/recompute", {"day": 2})
        self.assertEqual(status, 200)
        self.assertEqual(body["summary"]["streak"], 0)
        self.assertEqual(body["summary"]["completed_days"], 1)


if __name__ == "__main__":
    unittest.main()
