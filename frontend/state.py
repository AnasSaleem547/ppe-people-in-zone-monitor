"""Small state rules shared by the UI and tests."""
import json
import uuid

TERMINAL = {"succeeded", "failed"}


def submission_key(state, payload):
    signature = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if state.get("submission_signature") != signature:
        state["submission_signature"] = signature
        state["submission_key"] = uuid.uuid4().hex
    return state["submission_key"]
