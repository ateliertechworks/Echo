"""Main Echo chatbot flow. The app owns the question order, validation and draft
updates; the model is only consulted to understand the user's words.
Nothing here saves the report — that stays behind the Save Report action."""

import logging
import re

from echo_app.services import teams
from echo_app.services.memory import get_chat_memory
from echo_app.services.model import ModelUnavailableError, analyze_user_message
from echo_app.services.questions import FIELD_LABELS, fields_for_role, question_for
from echo_app.services.validate import validate_model_output

log = logging.getLogger(__name__)

READY_TO_SUMMARIZE = "[READY_TO_SUMMARIZE]"
MAX_FOLLOW_UPS = 2

SKIP_RE = re.compile(r"^\s*(skip|skip it|skip this|skip this one|pass|next)\s*[.!]*\s*$", re.I)
NEGATIVE_RE = re.compile(
    r"^(no|none|nope|nothing|nil|na|n/a|not really|all good|nothing much|nothing today|none today|no blockers?|"
    r"no issues?|no problems?|nothing pending|no pending( work)?|no events?|no meetings?|no discussions?|"
    r"nothing (to report|planned))\s*[.!]*$",
    re.I,
)
SAME_PROJECT_RE = re.compile(
    r"^(same|same project|same one|same as (yesterday|before|last time)|yesterday'?s? project|previous project|"
    r"that project|the same project)\s*[.!]*$",
    re.I,
)
SAME_WORK_RE = re.compile(
    r"^(same work|same task|that task|previous work|same as (yesterday|before|last time)|"
    r"continued (the )?(same|previous) work)\s*[.!]*$",
    re.I,
)

# Answers too generic to put in a report (e.g. "backend work"). Each word must be generic.
VAGUE_WORDS = {
    "backend", "frontend", "front", "end", "back", "ui", "ux", "work", "worked", "stuff", "things", "thing", "some",
    "few", "coding", "code", "development", "dev", "tasks", "task", "fixes", "fix", "bugs", "bug", "testing", "tests",
    "misc", "various", "general", "usual", "the", "on", "did", "done", "i", "my", "just", "it", "good", "fine", "ok",
    "okay", "progress", "meeting", "meetings", "research", "learning", "design",
}
VAGUE_FIELDS = {"work_done", "outcome", "discussion"}
VAGUE_FOLLOW_UPS = {
    "backend": "What backend work did you complete? Was it API, database, authentication, or Excel export?",
    "frontend": "What frontend work did you complete? Was it a page, a component, styling, or a bug fix?",
    "ui": "What UI work did you complete? Which screen or component was it?",
    "bug": "Which bug did you fix, and where was it (page, API, export…)?",
    "fix": "What did you fix, and where was it (page, API, export…)?",
    "testing": "What did you test, and how did it go?",
    "meeting": "What was the meeting about, and was anything decided?",
    "design": "What did you design — a screen, a flow, or a component?",
    "research": "What did you research, and what did you find?",
}
VAGUE_DEFAULT = {
    "work_done": "Could you be more specific? What exactly did you work on (feature, page, API, bug)?",
    "outcome": "What was the result? For example: completed, deployed, tested, or still in progress?",
    "discussion": "What was discussed or decided? A short sentence is enough.",
}

NEGATIVE_TEXT = {
    "blockers": "No blockers were reported.",
    "pending_next": "No pending work was reported.",
    "discussion": "No specific discussion was reported.",
    "event": "No events or meetings took place today.",
}

SUGGESTIONS = {
    "discussion": [{"label": "No specific discussion", "value": "no discussion"}],
    "event": [
        {"label": "No events today", "value": "no events"},
        {"label": "Daily stand-up", "value": "we had the daily stand-up meeting"},
    ],
    "outcome": [
        {"label": "Completed successfully", "value": "completed successfully"},
        {"label": "Still in progress", "value": "still in progress"},
    ],
    "blockers": [{"label": "No blockers", "value": "no blockers"}],
    "pending_next": [{"label": "Nothing pending", "value": "nothing pending"}],
}


def _clean(value) -> str:
    return " ".join(str(value if value is not None else "").split())


def _cap_first(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


def _sentence(text) -> str:
    c = _cap_first(_clean(text))
    return c if not c or c[-1] in ".!?" else f"{c}."


def _format_value(field, text) -> str:
    if field == "project":
        return re.sub(r"\.+$", "", _cap_first(_clean(text)))
    return _sentence(text)


def _strip_plural(word: str) -> str:
    return word[:-1] if word.endswith("s") else word


def _follow_up(question, confidence) -> dict:
    return {"updates": {}, "needs_follow_up": True, "follow_up_question": question, "confidence": confidence}


def _answer(updates, confidence) -> dict:
    return {"updates": updates, "needs_follow_up": False, "follow_up_question": "", "confidence": confidence}


def _vague_follow_up(field, text):
    if field not in VAGUE_FIELDS:
        return None
    words = [w for w in re.split(r"[\s-]+", re.sub(r"[^a-z\s-]", " ", text.lower())) if w]
    if not words or len(words) > 4 or not all(w in VAGUE_WORDS for w in words):
        return None
    if field == "outcome" and any(w in {"done", "good", "fine", "ok", "okay", "progress"} for w in words):
        return None
    key = next((w for w in words if VAGUE_FOLLOW_UPS.get(_strip_plural(w)) or VAGUE_FOLLOW_UPS.get(w)), None)
    question = (VAGUE_FOLLOW_UPS.get(key) or VAGUE_FOLLOW_UPS.get(_strip_plural(key))) if key else VAGUE_DEFAULT[field]
    return _follow_up(question, 0.4)


def _normalize_draft(raw, fields) -> dict:
    """Makes a safe, role-scoped working copy of the draft."""
    src = raw if isinstance(raw, dict) else {}
    draft = {f: _clean(src[f]) if isinstance(src.get(f), str) else "" for f in fields}
    skipped = src.get("_skipped")
    draft["_skipped"] = [f for f in skipped if f in fields and not draft[f]] if isinstance(skipped, list) else []
    draft["_followUps"] = {}
    follow_ups = src.get("_followUps") if isinstance(src.get("_followUps"), dict) else {}
    for f in fields:
        fu = follow_ups.get(f)
        if isinstance(fu, dict):
            try:
                count = int(fu.get("count") or 0)
            except (TypeError, ValueError):
                count = 0
            draft["_followUps"][f] = {
                "count": count,
                "previous": _clean(fu.get("previous"))[:1000],
                "question": _clean(fu.get("question"))[:300],
            }
    return draft


def _next_missing(draft, fields):
    return next((f for f in fields if not draft[f] and f not in draft["_skipped"]), None)


def _suggestions_for(field, memory):
    if not field:
        return []
    if field == "project" and memory.get("lastProject"):
        return [{"label": f"Same project · {memory['lastProject']}", "value": "same project"}]
    if field == "work_done" and memory.get("lastWorkDone"):
        return [{"label": "Same work as last report", "value": "same work"}]
    return SUGGESTIONS.get(field, [])


def _progress_for(draft, fields, current_field):
    def status(f):
        if draft[f]:
            return "filled"
        if f in draft["_skipped"]:
            return "skipped"
        return "current" if f == current_field else "pending"

    return [{"field": f, "label": FIELD_LABELS[f], "status": status(f)} for f in fields]


def build_preview(role, draft) -> dict:
    """Readable preview plus the structure that Save Report expects."""
    fields = fields_for_role(role)
    is_leader = role == "leader"
    parts = []
    if draft.get("project"):
        parts.append(f"Today, work focused on {draft['project']}.")
    parts += [_sentence(draft[f]) for f in fields if f != "project" and draft.get(f)]
    narrative = " ".join(parts)

    return {
        "role": role,
        "fields": [
            {"field": f, "label": FIELD_LABELS[f], "value": draft.get(f) or "", "skipped": not draft.get(f)}
            for f in fields
        ],
        "text": "\n".join(f"{FIELD_LABELS[f]}: {draft.get(f) or '(skipped)'}" for f in fields),
        "narrative": narrative,
        "structured": {
            "project_name": draft.get("project") or "",
            "work_done": "" if is_leader else draft.get("work_done") or "",
            "leader_work": draft.get("work_done") or "" if is_leader else "",
            "team_discussion": draft.get("discussion") or "" if is_leader else "",
            "team_progress": draft.get("event") or "" if is_leader else "",
            "outcome": draft.get("outcome") or "",
            "blockers": draft.get("blockers") or "",
            "pending_work": draft.get("pending_next") or "",
            "next_plan": "",
            "skipped_fields": [f for f in fields if not draft.get(f)],
            "narrative": narrative,
        },
    }


def _shortcut_for(field, message, memory, follow_up):
    """Deterministic answers that don't need the model (faster and exact)."""
    text = _clean(message)
    if not follow_up:
        vague = _vague_follow_up(field, text)
        if vague:
            return vague
    if NEGATIVE_RE.match(text) and field in NEGATIVE_TEXT:
        return _answer({field: NEGATIVE_TEXT[field]}, 1)
    if field == "project" and SAME_PROJECT_RE.match(text):
        if memory.get("lastProject"):
            return _answer({"project": memory["lastProject"]}, 1)
        return _follow_up("I don't have a previous report to refer to yet. What's the project name?", 0.3)
    if field == "work_done" and SAME_WORK_RE.match(text) and memory.get("lastWorkDone"):
        return _answer({"work_done": f"Continued the previous work: {memory['lastWorkDone']}"}, 0.9)
    if field == "pending_next" and SAME_WORK_RE.match(text) and memory.get("lastPending"):
        return _answer({"pending_next": memory["lastPending"]}, 0.9)
    return None


def _apply_updates(draft, updates, *, current_field, review_mode):
    """Writes validated updates into the draft and returns what was captured."""
    captured = []
    for field, value in updates.items():
        text = _format_value(field, value)
        if not text:
            continue
        existing = draft[field]
        if review_mode or field == current_field or not existing:
            draft[field] = text
        elif text.lower() not in existing.lower():
            # Extra detail for a field answered earlier: keep both rather than lose information.
            draft[field] = f"{_sentence(existing)} {text}"
        else:
            continue
        draft["_skipped"] = [f for f in draft["_skipped"] if f != field]
        draft["_followUps"].pop(field, None)
        captured.append({"field": field, "label": FIELD_LABELS[field], "value": draft[field]})
    return captured


def _respond(*, role, draft, fields, memory, bot_message, current_field=None, done=False,
             needs_follow_up=False, captured=None, model_online=True, **extra):
    return {
        "draft": draft,
        "current_field": None if done else current_field,
        "bot_message": bot_message,
        "done": done,
        "needs_follow_up": needs_follow_up,
        "preview": build_preview(role, draft) if done else None,
        "captured": captured or [],
        "suggestions": [] if done else _suggestions_for(current_field, memory),
        "progress": _progress_for(draft, fields, None if done else current_field),
        "model_online": model_online,
        **extra,
    }


def handle_chat_message(*, user_id, team_id, role, message="", current_field=None, draft=None) -> dict:
    """Handles one chat turn. An empty message just returns the current question (or the preview)."""
    fields = fields_for_role(role)
    draft = _normalize_draft(draft, fields)
    memory = get_chat_memory(user_id, team_id)
    text = _clean(message)

    field = current_field if current_field in fields else _next_missing(draft, fields)
    review_mode = not field
    base = {"role": role, "draft": draft, "fields": fields, "memory": memory}

    # Opening turn (or resume): ask the current question, or show the preview.
    if not text:
        if review_mode:
            return _respond(**base, done=True, bot_message=READY_TO_SUMMARIZE)
        return _respond(**base, current_field=field, bot_message=question_for(field))

    if SKIP_RE.match(text):
        if review_mode:
            return _respond(**base, done=True, bot_message=READY_TO_SUMMARIZE)
        draft[field] = ""
        if field not in draft["_skipped"]:
            draft["_skipped"].append(field)
        draft["_followUps"].pop(field, None)
        nxt = _next_missing(draft, fields)
        if not nxt:
            return _respond(**base, done=True, bot_message=READY_TO_SUMMARIZE, skipped=field)
        return _respond(**base, current_field=nxt, bot_message=question_for(nxt), skipped=field)

    follow_up = None if review_mode else draft["_followUps"].get(field)
    previous = (follow_up or {}).get("previous", "")
    model_online = True
    output = None if review_mode else _shortcut_for(field, text, memory, follow_up)

    if output is None:
        try:
            output = analyze_user_message(
                role=role, allowed_fields=fields, current_field=field, draft=draft, memory=memory,
                message=text, review_mode=review_mode, previous_answer=previous,
                follow_up_question=(follow_up or {}).get("question", ""),
            )
        except ModelUnavailableError as e:
            log.warning("[chat] model unavailable, storing cleaned answer: %s", e)
            model_online = False
            if review_mode:
                output = _follow_up(
                    "The language model is offline, so I can't apply edits by chat right now. "
                    "Click a field in the preview to edit it directly.", 0)
            else:
                output = _answer({field: " — ".join(p for p in (previous, text) if p)}, 0.6)

    result = validate_model_output(output, fields)

    if review_mode:
        captured = _apply_updates(draft, result["updates"], current_field=None, review_mode=True)
        bot_message = READY_TO_SUMMARIZE if captured else (
            result["follow_up_question"] or "I couldn't tell which part to change. Which field should I update?")
        return _respond(**base, done=True, bot_message=bot_message, captured=captured,
                        needs_follow_up=not captured, model_online=model_online)

    captured = _apply_updates(draft, result["updates"], current_field=field, review_mode=False)

    # Vague or missing answer for the current field: ask a follow-up (bounded).
    if not draft[field] or result["needs_follow_up"]:
        count = (follow_up or {}).get("count", 0) + 1
        combined = " — ".join(p for p in (previous, text) if p)
        if count > MAX_FOLLOW_UPS:
            # Don't trap the user in a loop — keep what they said, cleaned up.
            if not draft[field]:
                captured += _apply_updates(draft, {field: combined}, current_field=field, review_mode=False)
            draft["_followUps"].pop(field, None)
        else:
            question = (result["follow_up_question"] if result["needs_follow_up"] and result["follow_up_question"]
                        else f"Could you tell me a bit more? {question_for(field)}")
            draft["_followUps"][field] = {"count": count, "previous": combined[:1000], "question": question}
            return _respond(**base, current_field=field, bot_message=question, needs_follow_up=True,
                            captured=captured, model_online=model_online)

    nxt = _next_missing(draft, fields)
    if not nxt:
        return _respond(**base, done=True, bot_message=READY_TO_SUMMARIZE, captured=captured,
                        model_online=model_online)
    return _respond(**base, current_field=nxt, bot_message=question_for(nxt), captured=captured,
                    model_online=model_online)


def chat_turn(user_id, team_id, message="", current_field=None, draft=None) -> dict:
    """One chat turn for a signed-in user. The role always comes from team membership."""
    role = teams.require_role(team_id, user_id)
    result = handle_chat_message(user_id=user_id, team_id=team_id, role=role, message=str(message or "")[:4000],
                                 current_field=current_field, draft=draft)
    return {**result, "role": role}
