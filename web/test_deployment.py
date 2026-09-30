"""Cloud host and GitHub Pages integration, using an isolated database."""

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import server


class QuietHandler(server.AppHandler):
    def log_message(self, *args):
        pass


class DeploymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory(prefix="puman-deployment-tests-")
        cls.addClassCleanup(temp.cleanup)
        settings = patch.multiple(
            server,
            DB_PATH=Path(temp.name) / "nested" / "puman.sqlite3",
            PUBLIC_ORIGINS={"https://puman-test.onrender.com"},
            ALLOWED_ORIGINS={"https://livreee.github.io"},
        )
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

    def request(self, path, method="GET", body=None, headers=None):
        defaults = {"Host": "puman-test.onrender.com", "X-User-ID": "cloud-test-user"}
        defaults.update(headers or {})
        if body is not None:
            defaults["Content-Type"] = "application/json"
        request = Request(
            self.base + path, method=method, headers=defaults,
            data=json.dumps(body).encode() if body is not None else None,
        )
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.read(), response.headers

    def test_render_health_and_same_origin_page(self):
        status, body, _ = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["ok"])
        status, _, _ = self.request("/", headers={"Origin": "https://puman-test.onrender.com"})
        self.assertEqual(status, 200)

    def test_pages_preflight_and_saved_state(self):
        origin = {"Origin": "https://livreee.github.io"}
        status, _, headers = self.request("/api/state", "OPTIONS", headers={
            **origin, "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "Content-Type, X-User-ID",
        })
        self.assertEqual(status, 204)
        self.assertEqual(headers["Access-Control-Allow-Origin"], origin["Origin"])
        self.assertIn("PUT", headers["Access-Control-Allow-Methods"])
        self.assertIn("X-User-ID", headers["Access-Control-Allow-Headers"])
        self.assertIsNone(headers.get("Access-Control-Allow-Credentials"))
        status, _, headers = self.request("/api/state", "PUT", {"state": {"day": 3}}, origin)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        status, body, headers = self.request("/api/state", headers=origin)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["state"], {"day": 3})
        self.assertEqual(headers["Access-Control-Allow-Origin"], origin["Origin"])

    def test_disallowed_origin_and_host_have_no_cors_access(self):
        for headers in (
            {"Origin": "https://unrelated.example"},
            {"Origin": "https://livreee.github.io.evil.example"},
            {"Host": "evil.example", "Origin": "https://livreee.github.io"},
            {"Origin": "null"},
        ):
            with self.subTest(headers=headers):
                status, _, response_headers = self.request("/api/health", headers=headers)
                self.assertEqual(status, 403)
                self.assertIsNone(response_headers.get("Access-Control-Allow-Origin"))
        status, _, _ = self.request("/index.html", "HEAD", headers={"Host": "evil.example"})
        self.assertEqual(status, 403)

    def test_preflight_rejects_unexpected_methods_and_headers(self):
        for extra in (
            {"Access-Control-Request-Method": "DELETE"},
            {"Access-Control-Request-Headers": "Authorization"},
        ):
            status, _, _ = self.request("/api/state", "OPTIONS", headers={
                "Origin": "https://livreee.github.io", **extra,
            })
            self.assertEqual(status, 403)

    def test_config_is_public_but_source_and_database_remain_private(self):
        status, body, headers = self.request("/config.js")
        self.assertEqual(status, 200)
        self.assertIn(b"apiBaseUrl", body)
        self.assertEqual(headers["Cache-Control"], "no-store")
        for path in ("/server.py", "/.env.example", "/puman.sqlite3", "/assets/"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 404)
        self.assertEqual(self.request("/config.js", headers={"Origin": "https://livreee.github.io"})[0], 403)

    def test_origin_settings_validate_exact_domains(self):
        self.assertEqual(server.normalize_origin(" https://Puman-Test.onrender.com/ "), "https://puman-test.onrender.com")
        self.assertEqual(server.normalize_origin("https://example.com:443"), "https://example.com")
        for value in ("*", "https://*.example.com", "https://user:pass@example.com", "https://example.com/api", "https://example.com?key=123", "null"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                server.normalize_origin(value)


if __name__ == "__main__":
    unittest.main()
