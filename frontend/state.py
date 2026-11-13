"""Small state rules shared by the UI and tests."""
import json
import uuid

TERMINAL = {"succeeded", "failed"}


def polling_interval(duration, status, short_limit=30, seconds=7):
    return seconds if duration is not None and 0 < duration < short_limit and status not in TERMINAL else None


def submission_key(state, payload):
    signature = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if state.get("submission_signature") != signature:
        state["submission_signature"] = signature
        state["submission_key"] = uuid.uuid4().hex
    return state["submission_key"]
