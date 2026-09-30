"""Interpretable temporal behavior model for the 21-day journey.

This module models engagement and habit formation only. It does not estimate
credit, investment, transaction, or financial risk. The implementation is a
small dependency-free HMM-style forward model that is suitable for the demo's
short per-user sequences and can later be replaced by a trained model.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable


MODEL_VERSION = "hmm-lite-v1"
BEHAVIOR_EVENT_TYPES = frozenset({
    "daily_task_completed", "daily_quiz_answered", "saving_challenge_completed",
    "saving_recorded", "day_opened", "line_selected",
})
STATE_ORDER = ("activation", "trial", "stable", "fluctuation", "recovery")
STATE_NAMES = {
    "activation": "启动期",
    "trial": "尝试期",
    "stable": "稳定期",
    "fluctuation": "波动期",
    "recovery": "回归期",
}

# Transition priors. Rows are the previous state, columns are the next state.
TRANSITIONS = {
    "activation": {"activation": .42, "trial": .45, "stable": .08, "fluctuation": .03, "recovery": .02},
    "trial": {"activation": .06, "trial": .48, "stable": .30, "fluctuation": .13, "recovery": .03},
    "stable": {"activation": .01, "trial": .08, "stable": .72, "fluctuation": .15, "recovery": .04},
    "fluctuation": {"activation": .01, "trial": .16, "stable": .13, "fluctuation": .50, "recovery": .20},
    "recovery": {"activation": .01, "trial": .22, "stable": .36, "fluctuation": .10, "recovery": .31},
}

# Feature order: task completion, quiz accuracy, challenge completion,
# activity intensity, streak strength, inactivity gap.
PROTOTYPES = {
    "activation": (0.05, 0.15, 0.00, 0.18, 0.00, 0.10),
    "trial": (0.38, 0.42, 0.18, 0.40, 0.22, 0.20),
    "stable": (0.86, 0.70, 0.48, 0.75, 0.78, 0.04),
    "fluctuation": (0.18, 0.34, 0.12, 0.30, 0.12, 0.72),
    "recovery": (0.72, 0.52, 0.30, 0.68, 0.34, 0.36),
}


def _day_from_event(event: dict[str, Any]) -> int | None:
    payload = event.get("payload") or {}
    if not isinstance(payload, dict):
        return None
    day = payload.get("day")
    if isinstance(day, bool) or not isinstance(day, (int, str)):
        return None
    try:
        day = int(day)
    except (TypeError, ValueError):
        return None
    return day if 1 <= day <= 21 else None


def _empty_day(day: int) -> dict[str, Any]:
    return {
        "day": day,
        "event_count": 0,
        "active": 0,
        "task_completed": 0,
        "quiz_attempts": 0,
        "quiz_correct": 0,
        "challenge_completed": 0,
        "saving_records": 0,
        "task_completed_flag": 0,
        "quiz_accuracy": 0.0,
        "activity_intensity": 0.0,
        "streak": 0,
        "gap_days": 0,
        "features": {},
    }


def build_daily_features(events: Iterable[dict[str, Any]], upto_day: int) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        if event.get("event_type") not in BEHAVIOR_EVENT_TYPES:
            continue
        day = _day_from_event(event)
        if day is not None and day <= upto_day:
            grouped[day].append(event)

    days = [_empty_day(day) for day in range(1, upto_day + 1)]
    last_active_day: int | None = None

    for item in days:
        day = item["day"]
        day_events = grouped.get(day, [])
        item["event_count"] = len(day_events)
        item["active"] = int(bool(day_events))
        for event in day_events:
            event_type = event.get("event_type", "")
            if event_type == "daily_task_completed":
                item["task_completed"] += 1
            elif event_type == "daily_quiz_answered":
                item["quiz_attempts"] += 1
                if (event.get("payload") or {}).get("correct") is True:
                    item["quiz_correct"] += 1
            elif event_type == "saving_challenge_completed":
                item["challenge_completed"] += 1
            elif event_type == "saving_recorded":
                item["saving_records"] += 1

        item["task_completed_flag"] = int(item["task_completed"] > 0)
        item["quiz_accuracy"] = round(
            item["quiz_correct"] / item["quiz_attempts"], 4
        ) if item["quiz_attempts"] else 0.0
        item["activity_intensity"] = round(min(1.0, item["event_count"] / 5.0), 4)
        if item["task_completed_flag"]:
            item["streak"] = (
                days[day - 2]["streak"] + 1
                if day > 1 and days[day - 2]["task_completed_flag"]
                else 1
            )
        else:
            item["streak"] = 0
        # On an active day this is the preceding break; otherwise include today.
        item["gap_days"] = (
            min(7, day - last_active_day - item["active"])
            if last_active_day is not None else 0
        )
        if item["active"]:
            last_active_day = day
        item["features"] = feature_vector(item)

    return days


def feature_vector(day: dict[str, Any]) -> dict[str, float]:
    return {
        "completion": float(day["task_completed_flag"]),
        "quiz_accuracy": float(day["quiz_accuracy"]),
        "challenge": min(1.0, float(day["challenge_completed"])),
        "activity": float(day["activity_intensity"]),
        "streak": min(1.0, float(day["streak"]) / 5.0),
        "gap": min(1.0, float(day["gap_days"]) / 3.0),
    }


def _emission(state: str, day: dict[str, Any]) -> float:
    features = day["features"]
    names = ("completion", "quiz_accuracy", "challenge", "activity", "streak", "gap")
    prototype = PROTOTYPES[state]
    # Not answering a quiz is missing evidence, not an incorrect answer.
    distance = sum(
        (features[name] - prototype[index]) ** 2
        for index, name in enumerate(names)
        if name != "quiz_accuracy" or day["quiz_attempts"] > 0
    )
    if state == "recovery" and (not day["active"] or day["gap_days"] == 0):
        return 0.0001
    # A floor keeps a state alive during sparse or partially missing sequences.
    return max(0.0001, math.exp(-4.5 * distance))


def infer_sequence(days: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not days:
        return []
    prior = {state: 0.0 for state in STATE_ORDER}
    prior.update({"activation": .65, "trial": .20, "stable": .06, "fluctuation": .06, "recovery": .03})
    previous = prior
    output: list[dict[str, Any]] = []

    for index, day in enumerate(days):
        likelihood = {state: _emission(state, day) for state in STATE_ORDER}
        if index == 0:
            scores = {state: prior[state] * likelihood[state] for state in STATE_ORDER}
        else:
            scores = {
                state: likelihood[state] * sum(
                    previous[before] * TRANSITIONS[before][state] for before in STATE_ORDER
                )
                for state in STATE_ORDER
            }
        total = sum(scores.values()) or 1.0
        normalized = {state: scores[state] / total for state in STATE_ORDER}
        probabilities = {state: round(normalized[state], 6) for state in STATE_ORDER}
        current = max(probabilities, key=probabilities.get)
        day["state"] = current
        day["state_name"] = STATE_NAMES[current]
        day["probabilities"] = probabilities
        day["model_version"] = MODEL_VERSION
        previous = normalized
        output.append(day)
    return output


def analyze_events(events: Iterable[dict[str, Any]], upto_day: int = 21) -> dict[str, Any]:
    upto_day = max(1, min(21, int(upto_day)))
    days = infer_sequence(build_daily_features(events, upto_day))
    current = days[-1]
    completed_days = active_days = 0
    timeline = []
    previous_state = None
    for day in days:
        completed_days += day["task_completed_flag"]
        active_days += day["active"]
        if not active_days:
            trend = "待积累"
        elif day["state"] == "fluctuation":
            trend = "波动"
        elif previous_state == day["state"]:
            trend = "持平"
        elif day["state"] in {"stable", "recovery"}:
            trend = "回升"
        else:
            trend = "建立中"
        summary = {
            "day": day["day"], "state": day["state"],
            "state_name": day["state_name"], "probabilities": day["probabilities"],
            "streak": day["streak"], "completed_days": completed_days,
            "active_days": active_days, "trend": trend,
            "data_status": "observed" if active_days else "insufficient",
            "model_version": MODEL_VERSION,
        }
        timeline.append({**summary, "completed": bool(day["task_completed_flag"]), "active": bool(day["active"])})
        previous_state = day["state"]
    return {
        "model_version": MODEL_VERSION,
        "upto_day": upto_day,
        "current": current,
        "summary": summary,
        "daily_features": [
            {
                "day": day["day"],
                "event_count": day["event_count"],
                "active": bool(day["active"]),
                "task_completed": day["task_completed"],
                "quiz_attempts": day["quiz_attempts"],
                "quiz_correct": day["quiz_correct"],
                "challenge_completed": day["challenge_completed"],
                "saving_records": day["saving_records"],
                "task_completed_flag": day["task_completed_flag"],
                "quiz_accuracy": day["quiz_accuracy"],
                "activity_intensity": day["activity_intensity"],
                "streak": day["streak"],
                "gap_days": day["gap_days"],
                "features": day["features"],
            }
            for day in days
        ],
        "timeline": timeline,
    }
