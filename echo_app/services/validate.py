"""Validates and sanitizes the JSON returned by the model before anything is
applied to the draft. Unknown fields and empty values are dropped."""

import math
import re

from echo_app.services.questions import ALL_FIELDS

MIN_CONFIDENCE = 0.55
MAX_VALUE_LENGTH = 2000
DEFAULT_FOLLOW_UP = "I didn't catch that clearly. Can you explain it again?"

_FLOAT_PREFIX = re.compile(r"\s*[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


def _to_confidence(value) -> float:
    """Number as-is; strings parsed by leading number (like JS parseFloat); otherwise NaN."""
    if isinstance(value, bool):
        return math.nan
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = _FLOAT_PREFIX.match(value)
        if m:
            return float(m.group(0))
    return math.nan


def validate_model_output(output, allowed_fields=ALL_FIELDS) -> dict:
    def fail(reason):
        return {
            "valid": False,
            "reason": reason,
            "updates": {},
            "needs_follow_up": True,
            "follow_up_question": DEFAULT_FOLLOW_UP,
            "confidence": 0,
        }

    if not isinstance(output, dict):
        return fail("missing output")
    raw_updates = output.get("updates")
    if raw_updates is not None and not isinstance(raw_updates, dict):
        return fail("updates is not an object")

    allowed = set(allowed_fields)
    updates = {}
    for field, value in (raw_updates or {}).items():
        if field not in allowed or not isinstance(value, str):
            continue
        text = " ".join(value.split())
        if text:
            updates[field] = text[:MAX_VALUE_LENGTH]

    needs_follow_up = output.get("needs_follow_up") is True
    follow_up = output.get("follow_up_question")
    follow_up = follow_up.strip() if isinstance(follow_up, str) else ""

    confidence = _to_confidence(output.get("confidence"))
    if not math.isfinite(confidence):
        return fail("confidence is not a number")
    confidence = min(1.0, max(0.0, confidence))
    if updates and confidence == 0:
        confidence = 0.75

    if not needs_follow_up and confidence < MIN_CONFIDENCE:
        return fail("confidence below threshold")

    return {
        "valid": True,
        "reason": None,
        "updates": updates,
        "needs_follow_up": needs_follow_up,
        "follow_up_question": (follow_up or DEFAULT_FOLLOW_UP) if needs_follow_up else "",
        "confidence": confidence,
    }
