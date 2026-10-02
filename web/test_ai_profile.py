"""Answer-driven profiles and provider failures, with no paid API calls."""

import io
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import ai_service
import server


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_server_derives_scores_and_meaning_from_answers(self):
        context = ai_service.profile_context({
            "answers": [0, 0, 0, 0], "line": "travel", "scores": {"travel": 999},
        })
        self.assertEqual(context["line"], "home")
        self.assertEqual(context["scores"], {"home": 3, "baby": 2, "travel": 0, "gap": 1, "solo": 1})
        self.assertEqual(len(context["evidence"]), 4)
        self.assertIn("工资", context["evidence"][1]["question"])
        self.assertIn("只进不出", context["evidence"][1]["answer"])

    def test_same_goal_with_different_habits_changes_profile(self):
        first = ai_service.generate_profile({"answers": [0, 0, 0, 0]})
        second = ai_service.generate_profile({"answers": [0, 3, 0, 0]})
        self.assertEqual(first["context"]["line"], second["context"]["line"])
        self.assertNotEqual(first["profile"]["habit"], second["profile"]["habit"])
        self.assertNotEqual(first["profile"]["title"], second["profile"]["title"])
        self.assertEqual(first["provider"], "rules")
        self.assertEqual(first["fallback_reason"], "not_configured")

    def test_each_answer_is_visible_in_evidence(self):
        for index in range(4):
            original = [0, 0, 0, 0]
            changed = original.copy()
            changed[index] = 3
            a = ai_service.generate_profile({"answers": original})
            b = ai_service.generate_profile({"answers": changed})
            self.assertNotEqual(a["context"]["evidence"][index], b["context"]["evidence"][index])
            self.assertNotEqual(a["profile"], b["profile"])

    def test_incomplete_and_invalid_answers_are_rejected(self):
        for answers in (None, [], [0, 0, 0], [0]*5, [0, True, 0, 0], [0, -1, 0, 0],
                        [0, 4, 0, 0], [0, "1", 0, 0], [0, 1.5, 0, 0], {}):
            with self.subTest(answers=answers), self.assertRaises(ValueError):
                ai_service.generate_profile({"answers": answers})

    def test_status_requires_all_three_values(self):
        os.environ["LLM_API_KEY"] = "test-key"
        self.assertFalse(ai_service.provider_status()["configured"])
        os.environ["LLM_BASE_URL"] = "https://model.example/v1"
        os.environ["LLM_MODEL"] = "test-model"
        self.assertTrue(ai_service.provider_status()["configured"])
        self.assertNotIn("test-key", json.dumps(ai_service.provider_status()))

    def test_model_receives_text_answers_and_valid_json_is_used(self):
        os.environ.update(LLM_API_KEY="test-key", LLM_BASE_URL="https://model.example/v1", LLM_MODEL="test-model")
        generated = {key: "模型生成的" + key for key in ("title", "stage", "focus", "habit", "message")}
        generated["guardrail"] = "untrusted override"
        response = {"choices": [{"message": {"content": json.dumps(generated)}}]}
        with patch("ai_service._open_model_request", return_value=io.BytesIO(json.dumps(response).encode())) as mock:
            result = ai_service.generate_profile({"answers": [2, 1, 2, 1]})
        request = mock.call_args.args[0]
        sent = json.loads(request.data)
        context = json.loads(sent["messages"][1]["content"])
        self.assertIn("旅行", context["evidence"][0]["answer"])
        self.assertEqual(request.full_url, "https://model.example/v1/chat/completions")
        self.assertEqual(result["provider"], "llm")
        self.assertEqual(result["profile"]["message"], generated["message"])
        self.assertNotEqual(result["profile"]["guardrail"], "untrusted override")

    def test_timeout_and_partial_output_fall_back_truthfully(self):
        os.environ.update(LLM_API_KEY="test-key", LLM_BASE_URL="https://model.example/v1", LLM_MODEL="test-model")
        with patch("ai_service._open_model_request", side_effect=TimeoutError):
            result = ai_service.generate_profile({"answers": [0, 0, 0, 0]})
        self.assertEqual(result["provider"], "rules")
        self.assertEqual(result["fallback_reason"], "unavailable")
        for content in ("not json", '{"title":"only one field"}', '{"title":3}'):
            response = {"choices": [{"message": {"content": content}}]}
            with patch("ai_service._open_model_request", return_value=io.BytesIO(json.dumps(response).encode())):
                result = ai_service.generate_profile({"answers": [0, 0, 0, 0]})
            self.assertEqual(result["provider"], "rules")


class QuietHandler(server.AppHandler):
    def log_message(self, *args):
        pass


class ProfileApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="puman-profile-tests-")
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

    def request(self, body):
        request = Request(self.base + "/api/ai/profile", data=json.dumps(body).encode(), headers={
            "Content-Type": "application/json", "X-User-ID": "profile-api-test",
        })
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def test_profile_endpoint_validates_and_audits_authoritative_context(self):
        with patch.dict(os.environ, {}, clear=True):
            status, body = self.request({"answers": [0, 1, 0, 2], "line": "invalid", "scores": {"travel": 999}})
        self.assertEqual(status, 200)
        self.assertEqual(body["context"]["line"], "home")
        with server.db_session() as connection:
            row = connection.execute("SELECT * FROM ai_outputs WHERE id = ?", (body["audit_id"],)).fetchone()
            self.assertEqual(json.loads(row["request_json"]), body["context"])
            self.assertEqual(json.loads(row["response_json"])["profile"], body["profile"])
        status, body = self.request({"answers": [0, 1]})
        self.assertEqual(status, 400)
        self.assertIn("four", body["error"])


if __name__ == "__main__":
    unittest.main()
