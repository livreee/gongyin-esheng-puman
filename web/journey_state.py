"""Validate the lightweight multi-goal JSON save format (not a banking ledger)."""

import math

LINES = ("home", "baby", "travel", "gap", "solo", "custom")
MAX_MONEY = 1_000_000


def valid_line(value):
    if not isinstance(value, str) or value not in LINES:
        raise ValueError("unknown journey line")
    return value


def day(value):
    if type(value) is not int or not 1 <= value <= 21:
        raise ValueError("journey day must be an integer from 1 to 21")
    return value


def money(value, allow_zero=True):
    if (type(value) not in (int, float) or not math.isfinite(value)
            or not (0 if allow_zero else 0.01) <= value <= MAX_MONEY
            or abs(value * 100 - round(value * 100)) > 0.000001):
        raise ValueError("amount must be finite, within limits, and have at most two decimal places")
    return value


def text(value, limit, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError("invalid or overlong journey text")
    return value


def line_map(value):
    if not isinstance(value, dict):
        raise ValueError("per-line state must be an object")
    for line in value:
        valid_line(line)
    return value


def validate_custom(custom):
    if not isinstance(custom, dict):
        raise ValueError("customLine must be an object")
    text(custom.get("name"), 30, True)
    money(custom.get("goal"), False)
    money(custom.get("dailyTarget"), False)
    text(custom.get("intro", ""), 80)
    entries = custom.get("entries", {})
    if not isinstance(entries, dict) or len(entries) > 21:
        raise ValueError("custom diary must contain at most 21 journey days")
    for key, entry in entries.items():
        if key not in {str(value) for value in range(1, 22)} or not isinstance(entry, dict):
            raise ValueError("invalid diary day")
        money(entry.get("target"))
        money(entry.get("amount"))
        text(entry.get("note", ""), 240)
        text(entry.get("createdAt", ""), 40)
        if type(entry.get("completed", False)) is not bool:
            raise ValueError("diary completed must be a boolean")


def validate_state(state):
    # Legacy clients may still save a minimal {day:3}; do not reinterpret their data.
    for line, value in line_map(state.get("lineDays", {})).items():
        day(value)
    for field in ("challenges", "completed"):
        if field == "completed" and state.get("multiLineVersion") != 1:
            continue
        for values in line_map(state.get(field, {})).values():
            if not isinstance(values, list) or len(values) > 21 or any(type(value) is not int for value in values):
                raise ValueError("journey days must be an integer list")
            if len(values) != len(set(values)):
                raise ValueError("duplicate journey day")
            for value in values:
                day(value)
    for line, records in line_map(state.get("lineRecords", {})).items():
        if not isinstance(records, list) or len(records) > 1000:
            raise ValueError("invalid journey records")
        for record in records:
            if not isinstance(record, dict) or record.get("line", line) != line:
                raise ValueError("record belongs to another journey")
            day(record.get("day"))
            money(record.get("amount"))
            text(record.get("from", ""), 80)
            text(record.get("note", ""), 240)
    if "customLine" in state:
        validate_custom(state["customLine"])
    if state.get("multiLineVersion") == 1:
        valid_line(state.get("line"))
        day(state.get("day"))
