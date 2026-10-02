"""Idempotent demo quiz/travel rewards. All mutations share the caller's transaction."""

from __future__ import annotations

import json
import secrets
import time
import uuid

LINES = ("home", "baby", "travel", "gap", "solo", "custom")
# Same question order as DAILY_QUIZ in index.html; the contract is covered by tests.
QUIZ_ANSWERS = (1, 0, 0, 2, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0)
QUIZ_GOLD = 1
TRAVEL_MIN_GOLD, TRAVEL_MAX_GOLD = 3, 10
TRAVEL_DURATION_MS = 45_000
SOUVENIR_COUNT = 12


def now_ms():
    return int(time.time() * 1000)


def init_schema(connection):
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS reward_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            reward_key TEXT NOT NULL,
            kind TEXT NOT NULL,
            amount INTEGER NOT NULL CHECK(amount > 0),
            created_at INTEGER NOT NULL,
            UNIQUE(user_id, reward_key)
        );
        CREATE TABLE IF NOT EXISTS daily_quiz_answers (
            user_id TEXT NOT NULL, line TEXT NOT NULL, day INTEGER NOT NULL,
            question INTEGER NOT NULL, selected INTEGER NOT NULL,
            correct INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 1,
            PRIMARY KEY(user_id, line, day)
        );
        CREATE TABLE IF NOT EXISTS pet_trips (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, line TEXT NOT NULL,
            milestone INTEGER NOT NULL, started_at INTEGER NOT NULL,
            ready_at INTEGER NOT NULL, claimed_at INTEGER,
            coins INTEGER, souvenir INTEGER,
            UNIQUE(user_id, line, milestone)
        );
        DROP INDEX IF EXISTS one_active_pet_trip;
        CREATE UNIQUE INDEX IF NOT EXISTS one_active_pet_trip_line
            ON pet_trips(user_id, line) WHERE claimed_at IS NULL;
    """)


def journey(payload):
    line, day = payload.get("line"), payload.get("day")
    if line not in LINES or type(day) is not int or not 1 <= day <= 21:
        raise ValueError("line and integer day (1-21) are required")
    return line, day


def saved_state(connection, user_id):
    row = connection.execute("SELECT state_json FROM user_states WHERE user_id=?", (user_id,)).fetchone()
    return json.loads(row[0]) if row else {}


def snapshot(connection, user_id):
    rows = connection.execute("SELECT * FROM daily_quiz_answers WHERE user_id=?", (user_id,)).fetchall()
    quizzes = {f"{row['line']}:{row['day']}": {
        "question": row["question"], "selected": row["selected"],
        "correct": bool(row["correct"]), "coins": QUIZ_GOLD if row["correct"] else 0,
    } for row in rows}
    trips = [dict(row) for row in connection.execute(
        "SELECT id, line, milestone, started_at, ready_at, claimed_at, coins, souvenir "
        "FROM pet_trips WHERE user_id=? ORDER BY started_at, id", (user_id,)
    )]
    ledger = connection.execute(
        "SELECT COALESCE(SUM(amount),0), COUNT(*) FROM reward_ledger WHERE user_id=?", (user_id,)
    ).fetchone()
    return {
        "provider": "server", "gold": ledger[0], "quizzes": quizzes, "trips": trips,
        "active_trips": [trip for trip in trips if trip["claimed_at"] is None],
        # Kept for older clients; new clients select from active_trips by line.
        "active_trip": next((trip for trip in trips if trip["claimed_at"] is None), None),
        "revision": sum(row["attempts"] for row in rows) + len(trips) + ledger[1],
        "server_time": now_ms(),
    }


def answer_quiz(connection, user_id, payload):
    line, day = journey(payload)
    selected = payload.get("selected")
    if type(selected) is not int or not 0 <= selected <= 3:
        raise ValueError("selected must be an integer from 0 to 3")
    question = (day + LINES.index(line)) % len(QUIZ_ANSWERS)
    answer = QUIZ_ANSWERS[question]
    existing = connection.execute(
        "SELECT * FROM daily_quiz_answers WHERE user_id=? AND line=? AND day=?", (user_id, line, day)
    ).fetchone()
    if existing and existing["correct"]:
        return {"correct": True, "correct_index": answer, "question": question,
                "selected": existing["selected"], "awarded": False, "coins": 0}
    correct = selected == answer
    # Repeated network delivery of the same attempt does not inflate analytics.
    repeated = existing is not None and existing["selected"] == selected
    if not repeated:
        connection.execute("""
            INSERT INTO daily_quiz_answers(user_id,line,day,question,selected,correct)
            VALUES(?,?,?,?,?,?) ON CONFLICT(user_id,line,day) DO UPDATE SET
            selected=excluded.selected, correct=excluded.correct, attempts=attempts+1
        """, (user_id, line, day, question, selected, int(correct)))
        event = {"line": line, "day": day, "question": question, "correct": correct}
        connection.execute(
            "INSERT INTO events(user_id,event_type,payload_json,created_at) VALUES(?,?,?,?)",
            (user_id, "daily_quiz_answered", json.dumps(event), time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
        )
    if correct:
        connection.execute(
            "INSERT INTO reward_ledger(user_id,reward_key,kind,amount,created_at) VALUES(?,?,?,?,?)",
            (user_id, f"quiz:{line}:{day}", "daily_quiz", QUIZ_GOLD, now_ms()),
        )
    return {"correct": correct, "correct_index": answer, "question": question,
            "selected": selected, "awarded": correct, "coins": QUIZ_GOLD if correct else 0}


def completed_count(connection, user_id, line):
    state = saved_state(connection, user_id)
    completed = state.get("completed", {})
    days = completed.get(line, []) if isinstance(completed, dict) else []
    days = {day for day in days if type(day) is int and 1 <= day <= 21} if isinstance(days, list) else set()
    # An event may arrive before the debounced state snapshot.
    for row in connection.execute(
        "SELECT payload_json FROM events WHERE user_id=? AND event_type='daily_task_completed'", (user_id,)
    ):
        payload = json.loads(row[0])
        if payload.get("line") == line and type(payload.get("day")) is int and 1 <= payload["day"] <= 21:
            days.add(payload["day"])
    return len(days)


def start_trip(connection, user_id, payload):
    line, milestone = journey({"line": payload.get("line"), "day": payload.get("milestone")})
    if milestone % 3:
        raise ValueError("milestone must be a multiple of 3")
    existing = connection.execute(
        "SELECT * FROM pet_trips WHERE user_id=? AND line=? AND milestone=?", (user_id, line, milestone)
    ).fetchone()
    if existing:
        return {"trip": dict(existing), "started": False}
    if completed_count(connection, user_id, line) < milestone:
        raise ValueError("complete the required journey tasks before starting this trip")
    active = connection.execute(
        "SELECT * FROM pet_trips WHERE user_id=? AND line=? AND claimed_at IS NULL", (user_id, line)
    ).fetchone()
    if active:
        return {"trip": dict(active), "started": False}
    timestamp = now_ms()
    trip_id = uuid.uuid4().hex
    connection.execute(
        "INSERT INTO pet_trips(id,user_id,line,milestone,started_at,ready_at) VALUES(?,?,?,?,?,?)",
        (trip_id, user_id, line, milestone, timestamp, timestamp + TRAVEL_DURATION_MS),
    )
    return {"trip": dict(connection.execute("SELECT * FROM pet_trips WHERE id=?", (trip_id,)).fetchone()), "started": True}


def claim_trip(connection, user_id, payload):
    trip_id = payload.get("trip_id")
    if not isinstance(trip_id, str) or len(trip_id) > 80:
        raise ValueError("trip_id is required")
    trip = connection.execute("SELECT * FROM pet_trips WHERE id=? AND user_id=?", (trip_id, user_id)).fetchone()
    if trip is None:
        raise ValueError("trip not found")
    if trip["claimed_at"] is not None:
        return {"awarded": False, "coins": trip["coins"], "souvenir": trip["souvenir"], "trip_id": trip_id}
    timestamp = now_ms()
    if timestamp < trip["ready_at"]:
        return {"awarded": False, "pending": True, "remaining_ms": trip["ready_at"] - timestamp, "trip_id": trip_id}
    coins = TRAVEL_MIN_GOLD + secrets.randbelow(TRAVEL_MAX_GOLD - TRAVEL_MIN_GOLD + 1)
    previous = saved_state(connection, user_id).get("souvenirs", [])
    collected = {value for value in previous if type(value) is int} if isinstance(previous, list) else set()
    collected.update(row[0] for row in connection.execute(
        "SELECT souvenir FROM pet_trips WHERE user_id=? AND claimed_at IS NOT NULL", (user_id,)
    ))
    pool = [i for i in range(SOUVENIR_COUNT) if i not in collected] or list(range(SOUVENIR_COUNT))
    souvenir = secrets.choice(pool)
    connection.execute("UPDATE pet_trips SET claimed_at=?,coins=?,souvenir=? WHERE id=?", (timestamp, coins, souvenir, trip_id))
    connection.execute(
        "INSERT INTO reward_ledger(user_id,reward_key,kind,amount,created_at) VALUES(?,?,?,?,?)",
        (user_id, "travel:" + trip_id, "pet_travel", coins, timestamp),
    )
    return {"awarded": True, "coins": coins, "souvenir": souvenir, "trip_id": trip_id}
