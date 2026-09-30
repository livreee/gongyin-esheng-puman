"""Credential storage and public-file boundaries; uses disposable fake keys."""

import io
import errno
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
import private_config
import server


@unittest.skipUnless(os.name == "nt", "DPAPI requires Windows")
class CredentialTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="puman-private-tests-")
        self.addCleanup(self.temp.cleanup)
        env = patch.dict(os.environ, {"LOCALAPPDATA": self.temp.name}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        self.key = "sk-" + "disposable" * 3

    def test_encrypted_round_trip_outside_project(self):
        path = private_config.save_deepseek_key(self.key)
        self.assertFalse(path.is_relative_to(private_config.PROJECT_ROOT))
        self.assertNotIn(self.key, path.read_text())
        self.assertTrue(private_config.load_private_config())
        self.assertEqual(os.environ["LLM_API_KEY"], self.key)
        self.assertEqual(os.environ["LLM_BASE_URL"], "https://api.deepseek.com")
        self.assertNotIn(self.key, json.dumps(ai_service.provider_status()))

    def test_environment_override_and_key_replacement(self):
        path = private_config.save_deepseek_key(self.key)
        private_config.save_deepseek_key(self.key + "changed")
        os.environ["LLM_API_KEY"] = "deployment-key"
        os.environ["LLM_MODEL"] = "deployment-model"
        private_config.load_private_config()
        self.assertEqual(os.environ["LLM_API_KEY"], "deployment-key")
        self.assertEqual(os.environ["LLM_MODEL"], "deployment-model")
        del os.environ["LLM_API_KEY"]
        private_config.load_private_config()
        self.assertEqual(os.environ["LLM_API_KEY"], self.key + "changed")
        self.assertEqual(len(list(path.parent.iterdir())), 1)

    def test_corrupt_config_fails_without_echoing_key(self):
        path = private_config.save_deepseek_key(self.key)
        path.write_text(json.dumps({"version": 1, "protection": "windows-dpapi-current-user", "api_key_dpapi": "invalid"}))
        with self.assertRaises(RuntimeError) as raised:
            private_config.load_private_config()
        self.assertNotIn(self.key, str(raised.exception))
        self.assertNotIn("LLM_API_KEY", os.environ)

    def test_storage_inside_project_is_rejected(self):
        with patch.object(private_config, "PROJECT_ROOT", Path(self.temp.name)):
            with self.assertRaises(RuntimeError):
                private_config.save_deepseek_key(self.key)

    def test_redirected_profile_can_copy_only_encrypted_data(self):
        with patch("private_config.os.replace", side_effect=OSError(errno.EXDEV, "cross-volume profile")):
            path = private_config.save_deepseek_key(self.key)
        self.assertNotIn(self.key, path.read_text())
        private_config.load_private_config()
        self.assertEqual(os.environ["LLM_API_KEY"], self.key)


class QuietHandler(server.AppHandler):
    def log_message(self, *args):
        pass


class PublicFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="puman-public-tests-")
        root = Path(cls.temp.name)
        (root / "assets").mkdir()
        (root / "index.html").write_text("public page")
        (root / "assets" / "icon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        for name in (".env", "server.py", "puman.sqlite3", "deepseek.json"):
            (root / name).write_text("private fixture")
        cls.root_patch = patch.object(server, "ROOT", root)
        cls.root_patch.start()
        cls.http = server.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.base = "http://127.0.0.1:" + str(cls.http.server_port)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join(timeout=5)
        cls.root_patch.stop()
        cls.temp.cleanup()

    def request(self, path, method="GET", headers=None):
        request = Request(self.base + path, method=method, headers=headers or {})
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.read(), response.headers

    def test_private_files_and_directory_listing_blocked_for_get_and_head(self):
        for path in ("/.env", "/%2eenv", "/server.py", "/puman.sqlite3", "/deepseek.json", "/assets/", "/assets/../server.py"):
            for method in ("GET", "HEAD"):
                with self.subTest(path=path, method=method):
                    status, body, _ = self.request(path, method)
                    self.assertEqual(status, 404)
                    self.assertNotIn(b"private fixture", body)

    def test_public_page_and_assets_still_work(self):
        for path in ("/", "/index.html", "/assets/icon.svg"):
            status, _, headers = self.request(path)
            self.assertEqual(status, 200)
            self.assertIsNone(headers.get("Access-Control-Allow-Origin"))

    def test_cross_site_api_and_unexpected_host_rejected(self):
        status, _, _ = self.request("/api/ai/profile", "POST", {"Origin": "https://unrelated.example"})
        self.assertEqual(status, 403)
        status, _, _ = self.request("/api/ai/status", headers={"Host": "unrelated.example"})
        self.assertEqual(status, 403)
        status, _, _ = self.request("/api/ai/status", headers={"Origin": self.base})
        self.assertEqual(status, 200)


class ProviderProtectionTests(unittest.TestCase):
    def test_credentials_are_not_forwarded_by_redirects(self):
        request = Request("https://api.deepseek.com/chat/completions", headers={"Authorization": "Bearer fake"})
        handler = ai_service.NoCredentialRedirect()
        self.assertIsNone(handler.redirect_request(request, None, 302, "Found", {}, "https://unrelated.example/"))

    def test_deepseek_json_configuration_and_no_key_in_payload(self):
        with patch.dict(os.environ, {"LLM_API_KEY": "fake-test-key", "LLM_BASE_URL": "https://api.deepseek.com", "LLM_MODEL": "deepseek-flash"}, clear=True):
            response = {"choices": [{"message": {"content": '{"ok":true}'}}]}
            with patch("ai_service._open_model_request", return_value=io.BytesIO(json.dumps(response).encode())) as mock:
                ai_service._call_json("Return JSON.", {"answer": "synthetic test"})
        request = mock.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(body["thinking"], {"type": "disabled"})
        self.assertNotIn(b"fake-test-key", request.data)


if __name__ == "__main__":
    unittest.main()
