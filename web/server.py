"""Lightweight backend for the ICBC 21-day demo.

Run from the project root with: python web/server.py
The server hosts the static frontend and a small SQLite API on one origin.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ai_service import generate_coach, generate_profile, provider_status
from behavior_model import BEHAVIOR_EVENT_TYPES, analyze_events
from private_config import load_private_config
import rewards
import journey_state


ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("DB_PATH") or ROOT / "puman.sqlite3").expanduser().resolve()
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8000"))
MAX_BODY = 1024 * 1024
USER_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{8,80}$")
DB_LOCK = threading.Lock()


def normalize_origin(value: str) -> str:
    """Accept exact HTTP(S) origins, never wildcards, paths or credentials."""
    parsed = urlparse(value.strip())
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
            or "*" in parsed.netloc):
        raise ValueError("Expected an HTTP(S) origin without a path or credentials")
    port = parsed.port
    host = parsed.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    if port and port != {"http": 80, "https": 443}[parsed.scheme]:
        host += f":{port}"
    return f"{parsed.scheme}://{host}"


# Render provides its own public URL; custom domains can use PUBLIC_ORIGIN.
PUBLIC_ORIGINS = {
    normalize_origin(value) for value in (
        os.environ.get("PUBLIC_ORIGIN", ""), os.environ.get("RENDER_EXTERNAL_URL", ""),
    ) if value.strip()
}
ALLOWED_ORIGINS = {
    normalize_origin(value) for value in os.environ.get("ALLOWED_ORIGINS", "").split(",")
    if value.strip()
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    return connection


@contextmanager
def db_session():
    connection = connect_db()
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()
    finally:
        connection.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DB_LOCK, db_session() as connection:
        rewards.init_schema(connection)
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS user_states (
                user_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_events_user_time
                ON events(user_id, created_at);
            CREATE TABLE IF NOT EXISTS ai_outputs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                feature TEXT NOT NULL,
                request_json TEXT NOT NULL,
                response_json TEXT NOT NULL,
                provider TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS daily_behavior_features (
                user_id TEXT NOT NULL,
                day INTEGER NOT NULL,
                features_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(user_id, day)
            );
            CREATE TABLE IF NOT EXISTS behavior_states (
                user_id TEXT NOT NULL,
                day INTEGER NOT NULL,
                state TEXT NOT NULL,
                state_name TEXT NOT NULL,
                probabilities_json TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                model_version TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(user_id, day)
            );
            """
        )


def valid_user_id(value: str | None) -> str:
    if value and USER_ID_RE.fullmatch(value):
        return value
    raise ValueError("invalid user id")


def behavior_day(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError("day must be an integer between 1 and 21")
    try:
        day = int(value)
    except ValueError:
        raise ValueError("day must be an integer between 1 and 21") from None
    if not 1 <= day <= 21:
        raise ValueError("day must be between 1 and 21")
    return day


def read_json(handler: SimpleHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0 or length > MAX_BODY:
        raise ValueError("request body is empty or too large")
    raw = handler.rfile.read(length)
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("request body must be an object")
    return value


class AppHandler(SimpleHTTPRequestHandler):
    server_version = "PumanBackend/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("X-Backend-Version", "1.0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Vary", "Origin")
        if getattr(self, "cors_origin", None):
            self.send_header("Access-Control-Allow-Origin", self.cors_origin)
        if urlparse(self.path).path.startswith("/api/") or urlparse(self.path).path == "/config.js":
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def same_origin_request(self) -> bool:
        self.cors_origin = None
        port = self.server.server_port
        allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        local_origins = {f"http://{host}" for host in allowed_hosts}
        allowed_hosts.update(urlparse(origin).netloc for origin in PUBLIC_ORIGINS)
        origin = self.headers.get("Origin")
        is_api = urlparse(self.path).path.startswith("/api/")
        allowed_origins = local_origins | PUBLIC_ORIGINS | (ALLOWED_ORIGINS if is_api else set())
        if self.headers.get("Host", "").lower() not in allowed_hosts or (origin and origin not in allowed_origins):
            self.send_json(HTTPStatus.FORBIDDEN, {"error": "request host or origin is not allowed"})
            return False
        if is_api and origin in ALLOWED_ORIGINS:
            self.cors_origin = origin
        return True

    def send_head(self):
        # Both GET and HEAD must use the same public-file allowlist.
        path = Path(self.translate_path(self.path)).resolve()
        root = ROOT.resolve()
        assets = (root / "assets").resolve()
        allowed_asset = (
            assets.is_relative_to(root) and path.is_relative_to(assets)
            and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".mp3", ".wav", ".ogg", ".css", ".js"}
            and not any(part.startswith(".") for part in path.relative_to(assets).parts)
        )
        if path == root:
            self.path = "/index.html"
        elif path not in {root / "index.html", root / "config.js"} and not allowed_asset:
            self.send_error(HTTPStatus.NOT_FOUND)
            return None
        return super().send_head()

    def do_OPTIONS(self) -> None:
        if not self.same_origin_request():
            return
        if not urlparse(self.path).path.startswith("/api/"):
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return
        method = self.headers.get("Access-Control-Request-Method", "GET").upper()
        headers = {value.strip().lower() for value in self.headers.get("Access-Control-Request-Headers", "").split(",") if value.strip()}
        if method not in {"GET", "POST", "PUT"} or not headers.issubset({"content-type", "x-user-id"}):
            self.send_json(HTTPStatus.FORBIDDEN, {"error": "preflight method or headers are not allowed"})
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-User-ID")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_HEAD(self) -> None:
        if self.same_origin_request():
            super().do_HEAD()

    def do_GET(self) -> None:
        if not self.same_origin_request():
            return
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            try:
                self.handle_api_get(parsed)
            except ValueError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            except Exception as error:  # Keep demo API errors JSON-shaped.
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})
            return
        super().do_GET()

    def do_PUT(self) -> None:
        if not self.same_origin_request():
            return
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            try:
                self.handle_state_put()
            except ValueError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            except Exception as error:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        if not self.same_origin_request():
            return
        parsed = urlparse(self.path)
        if parsed.path in {"/api/daily-quiz/answer", "/api/travel/start", "/api/travel/claim"}:
            try:
                self.handle_reward_post(parsed.path)
            except ValueError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            except Exception:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "reward service unavailable"})
            return
        if parsed.path == "/api/events":
            try:
                self.handle_event_post()
            except ValueError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            except Exception as error:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})
            return
        if parsed.path == "/api/ai/profile":
            try:
                self.handle_ai_post("profile")
            except ValueError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            except Exception as error:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})
            return
        if parsed.path == "/api/ai/coach":
            try:
                self.handle_ai_post("coach")
            except ValueError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            except Exception as error:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})
            return
        if parsed.path == "/api/behavior/recompute":
            try:
                self.handle_behavior_recompute_post()
            except ValueError as error:
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            except Exception as error:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(error)})
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def user_id(self) -> str:
        parsed = parse_qs(urlparse(self.path).query)
        candidate = self.headers.get("X-User-ID") or (parsed.get("user_id") or [None])[0]
        return valid_user_id(candidate)

    def handle_api_get(self, parsed) -> None:
        if parsed.path == "/api/health":
            self.send_json(HTTPStatus.OK, {"ok": True, "service": "puman-backend", "version": "1.0"})
            return
        if parsed.path == "/api/state":
            user_id = self.user_id()
            with DB_LOCK, db_session() as connection:
                connection.execute("BEGIN")
                row = connection.execute(
                    "SELECT state_json, version, updated_at FROM user_states WHERE user_id = ?",
                    (user_id,),
                ).fetchone()
                reward_state = rewards.snapshot(connection, user_id)
            if row is None:
                self.send_json(HTTPStatus.OK, {"state": None, "version": 0, "rewards": reward_state})
            else:
                self.send_json(
                    HTTPStatus.OK,
                    {
                        "state": json.loads(row["state_json"]),
                        "version": row["version"],
                        "updated_at": row["updated_at"],
                        "rewards": reward_state,
                    },
                )
            return
        if parsed.path == "/api/metrics":
            user_id = self.user_id()
            with db_session() as connection:
                counts = connection.execute(
                    "SELECT event_type, COUNT(*) AS total FROM events WHERE user_id = ? GROUP BY event_type",
                    (user_id,),
                ).fetchall()
            self.send_json(HTTPStatus.OK, {"events": {row["event_type"]: row["total"] for row in counts}})
            return
        if parsed.path == "/api/rewards":
            user_id = self.user_id()
            with DB_LOCK, db_session() as connection:
                connection.execute("BEGIN")
                reward_state = rewards.snapshot(connection, user_id)
            self.send_json(HTTPStatus.OK, {"ok": True, "rewards": reward_state})
            return
        if parsed.path == "/api/behavior/state":
            self.handle_behavior_get(parsed, timeline=False)
            return
        if parsed.path == "/api/behavior/timeline":
            self.handle_behavior_get(parsed, timeline=True)
            return
        if parsed.path == "/api/ai/status":
            self.send_json(HTTPStatus.OK, provider_status())
            return
        self.send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def handle_state_put(self) -> None:
        user_id = self.user_id()
        body = read_json(self)
        state = body.get("state")
        if not isinstance(state, dict):
            raise ValueError("state must be an object")
        # Reward balances/claims have their own ledger; stale saves cannot overwrite them.
        state.pop("rewards", None)
        journey_state.validate_state(state)
        state_json = json.dumps(state, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        timestamp = now_iso()
        with DB_LOCK, db_session() as connection:
            existing = connection.execute(
                "SELECT version FROM user_states WHERE user_id = ?", (user_id,)
            ).fetchone()
            version = (existing["version"] + 1) if existing else 1
            connection.execute(
                """
                INSERT INTO user_states(user_id, state_json, version, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    state_json = excluded.state_json,
                    version = excluded.version,
                    updated_at = excluded.updated_at
                """,
                (user_id, state_json, version, timestamp),
            )
            reward_state = rewards.snapshot(connection, user_id)
        self.send_json(HTTPStatus.OK, {"ok": True, "version": version, "updated_at": timestamp, "rewards": reward_state})

    def handle_reward_post(self, path: str) -> None:
        user_id, payload = self.user_id(), read_json(self)
        operation = {
            "/api/daily-quiz/answer": rewards.answer_quiz,
            "/api/travel/start": rewards.start_trip,
            "/api/travel/claim": rewards.claim_trip,
        }[path]
        with DB_LOCK, db_session() as connection:
            connection.execute("BEGIN IMMEDIATE")
            result = operation(connection, user_id, payload)
            if path == "/api/daily-quiz/answer":
                self.recompute_behavior(connection, user_id)
            reward_state = rewards.snapshot(connection, user_id)
        self.send_json(HTTPStatus.OK, {"ok": True, **result, "rewards": reward_state})

    def handle_event_post(self) -> None:
        user_id = self.user_id()
        body = read_json(self)
        event_type = body.get("event_type")
        payload = body.get("payload", {})
        if not isinstance(event_type, str) or not re.fullmatch(r"[a-z0-9_.-]{2,64}", event_type):
            raise ValueError("invalid event_type")
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        if event_type in BEHAVIOR_EVENT_TYPES:
            payload["day"] = behavior_day(payload.get("day"))
            if "line" in payload:
                journey_state.valid_line(payload["line"])
        if event_type == "daily_quiz_answered" and not isinstance(payload.get("correct"), bool):
            raise ValueError("correct must be a boolean")
        with DB_LOCK, db_session() as connection:
            cursor = connection.execute(
                "INSERT INTO events(user_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?)",
                (user_id, event_type, json.dumps(payload, ensure_ascii=False), now_iso()),
            )
            if event_type in BEHAVIOR_EVENT_TYPES:
                self.recompute_behavior(connection, user_id)
        self.send_json(HTTPStatus.CREATED, {"ok": True, "event_id": cursor.lastrowid})

    def handle_behavior_get(self, parsed, timeline: bool) -> None:
        user_id = self.user_id()
        params = parse_qs(parsed.query)
        requested_day = (params.get("day") or [None])[0]
        line = (params.get("line") or [None])[0]
        if line is not None:
            journey_state.valid_line(line)
        if requested_day is not None:
            requested_day = behavior_day(requested_day)
        with DB_LOCK, db_session() as connection:
            analysis = self.recompute_behavior(connection, user_id, requested_day, line=line)
        if timeline:
            self.send_json(HTTPStatus.OK, {
                "ok": True,
                "line": line,
                "model_version": analysis["model_version"],
                "timeline": analysis["timeline"],
            })
        else:
            self.send_json(HTTPStatus.OK, {
                "ok": True,
                "line": line,
                "model_version": analysis["model_version"],
                "summary": analysis["summary"],
            })

    def handle_behavior_recompute_post(self) -> None:
        user_id = self.user_id()
        payload = read_json(self)
        upto_day = payload.get("day")
        line = payload.get("line")
        if line is not None:
            journey_state.valid_line(line)
        if upto_day is not None:
            upto_day = behavior_day(upto_day)
        with DB_LOCK, db_session() as connection:
            analysis = self.recompute_behavior(connection, user_id, upto_day, line=line)
        self.send_json(HTTPStatus.OK, {
            "ok": True,
            "line": line,
            "model_version": analysis["model_version"],
            "summary": analysis["summary"],
            "timeline": analysis["timeline"],
        })

    def recompute_behavior(self, connection: sqlite3.Connection, user_id: str, upto_day: Any = None, line: str | None = None) -> dict[str, Any]:
        rows = connection.execute(
            "SELECT event_type, payload_json, created_at FROM events WHERE user_id = ? ORDER BY created_at ASC, id ASC",
            (user_id,),
        ).fetchall()
        events = []
        max_event_day = 1
        for row in rows:
            try:
                payload = json.loads(row["payload_json"])
            except json.JSONDecodeError:
                payload = {}
            if not isinstance(payload, dict) or row["event_type"] not in BEHAVIOR_EVENT_TYPES:
                continue
            if line is not None and payload.get("line") != line:
                continue
            events.append({"event_type": row["event_type"], "payload": payload, "created_at": row["created_at"]})
            try:
                max_event_day = max(max_event_day, behavior_day(payload.get("day")))
            except ValueError:
                pass
        row = connection.execute("SELECT state_json FROM user_states WHERE user_id = ?", (user_id,)).fetchone()
        if line is not None:
            saved = json.loads(row["state_json"]) if row else {}
            try:
                state_day = behavior_day(saved.get("lineDays", {}).get(line, 1))
            except (ValueError, AttributeError):
                state_day = 1
            # Per-line views never read or overwrite the legacy all-line cache.
            target_day = behavior_day(upto_day) if upto_day is not None else max(max_event_day, state_day)
            return analyze_events(events, target_day)
        try:
            state_day = behavior_day(json.loads(row["state_json"]).get("day")) if row else 1
        except (ValueError, AttributeError):
            state_day = 1
        cached_day = connection.execute(
            "SELECT MAX(day) FROM behavior_states WHERE user_id = ?", (user_id,)
        ).fetchone()[0] or 1
        target_day = behavior_day(upto_day) if upto_day is not None else max(max_event_day, state_day, cached_day)
        # A late event changes all later posteriors, including cached future days.
        full_day = max(target_day, max_event_day, cached_day)
        analysis = analyze_events(events, full_day)
        timestamp = now_iso()
        feature_by_day = {
            item["day"]: item for item in analysis["daily_features"]
        }
        for day in analysis["timeline"]:
            connection.execute(
                """
                INSERT INTO daily_behavior_features(user_id, day, features_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, day) DO UPDATE SET
                    features_json = excluded.features_json,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    day["day"],
                    json.dumps(feature_by_day[day["day"]], ensure_ascii=False),
                    timestamp,
                ),
            )
            connection.execute(
                """
                INSERT INTO behavior_states(
                    user_id, day, state, state_name, probabilities_json,
                    summary_json, model_version, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, day) DO UPDATE SET
                    state = excluded.state,
                    state_name = excluded.state_name,
                    probabilities_json = excluded.probabilities_json,
                    summary_json = excluded.summary_json,
                    model_version = excluded.model_version,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    day["day"],
                    day["state"],
                    day["state_name"],
                    json.dumps(day["probabilities"], ensure_ascii=False),
                    json.dumps(day, ensure_ascii=False),
                    analysis["model_version"],
                    timestamp,
                ),
            )
        return analysis if target_day == full_day else analyze_events(events, target_day)

    def handle_ai_post(self, feature: str) -> None:
        user_id = self.user_id()
        payload = read_json(self)
        if feature == "profile":
            result = generate_profile(payload)
            # Persist authoritative answers and scoring, never client-supplied scores.
            payload = result["context"]
        else:
            day = int(payload.get("day", 0))
            if day < 1 or day > 21:
                raise ValueError("day must be between 1 and 21")
            result = generate_coach(payload)
        response = {"ok": True, "feature": feature, **result}
        with DB_LOCK, db_session() as connection:
            cursor = connection.execute(
                """
                INSERT INTO ai_outputs(user_id, feature, request_json, response_json, provider, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    feature,
                    json.dumps(payload, ensure_ascii=False),
                    json.dumps(response, ensure_ascii=False),
                    result["provider"],
                    now_iso(),
                ),
            )
        response["audit_id"] = cursor.lastrowid
        self.send_json(HTTPStatus.OK, response)

    def send_json(self, status: HTTPStatus, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args) -> None:
        # Keep the demo terminal readable while retaining request visibility.
        print("[%s] %s" % (self.log_date_time_string(), format % args))


def main() -> None:
    load_private_config()
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"Puman backend running at http://{HOST}:{PORT}/index.html")
    print(f"SQLite database: {DB_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping backend")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
