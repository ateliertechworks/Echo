"""Language understanding for the Echo chatbot via a local Ollama model.
The model only interprets the user's answer and returns clean text as JSON;
it never saves, never touches the DB and never decides the question flow."""

import json
import logging
import re
import socket
import urllib.error
import urllib.request

from echo_app import config
from echo_app.services.questions import FIELD_LABELS, QUESTIONS

log = logging.getLogger(__name__)

PARSE_FAILURE = {
    "updates": {},
    "needs_follow_up": True,
    "follow_up_question": "I didn't catch that clearly. Can you explain it again?",
    "confidence": 0,
}

FIELD_GUIDE = {
    "project": 'the project or product name (short title, e.g. "Team Management App")',
    "discussion": "what the team discussed or decided",
    "event": "any event, meeting, demo or activity that happened",
    "work_done": "concrete work the user completed today",
    "outcome": "the result of that work (what now works, what was delivered)",
    "blockers": "anything that blocked or slowed the user down",
    "pending_next": "work still pending or planned next",
}

EXAMPLES = """EXAMPLES (follow this style exactly):

current_field=project, memory.lastProject="Team Management App", user: "same project"
{"updates":{"project":"Team Management App"},"needs_follow_up":false,"follow_up_question":"","confidence":0.95}

current_field=project, memory.lastProject="", user: "same project"
{"updates":{},"needs_follow_up":true,"follow_up_question":"I don't have a previous report to refer to. What is the project name?","confidence":0.3}

current_field=work_done, user: "completed login page but signup pending"
{"updates":{"work_done":"Completed the login page.","pending_next":"Signup page is pending."},"needs_follow_up":false,"follow_up_question":"","confidence":0.92}

current_field=blockers, user: "no blockers"
{"updates":{"blockers":"No blockers were reported."},"needs_follow_up":false,"follow_up_question":"","confidence":0.97}

current_field=work_done, user: "backend work"
{"updates":{},"needs_follow_up":true,"follow_up_question":"What backend work did you complete? Was it API, database, authentication, or Excel export?","confidence":0.4}

current_field=outcome, user: "it wroks now, users can loggin"
{"updates":{"outcome":"It works now; users can log in."},"needs_follow_up":false,"follow_up_question":"","confidence":0.9}

current_field=discussion (leader), user: "we decided to move db to postgres, also had client demo in evening"
{"updates":{"discussion":"The team decided to move the database to PostgreSQL.","event":"A client demo took place in the evening."},"needs_follow_up":false,"follow_up_question":"","confidence":0.9}

current_field=work_done, user: "fixed teh excel export bug and wrote api for reports, tested it, no issues"
{"updates":{"work_done":"Fixed the Excel export bug and wrote the reports API.","outcome":"The changes were tested successfully.","blockers":"No blockers were reported."},"needs_follow_up":false,"follow_up_question":"","confidence":0.9}"""


class ModelUnavailableError(Exception):
    pass


def _js(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def build_prompt(*, role, allowed_fields, current_field, draft, memory, message,
                 review_mode, previous_answer, follow_up_question) -> str:
    filled = {f: draft[f] for f in allowed_fields if draft.get(f)}
    field_list = "\n".join(f"- {f}: {FIELD_GUIDE[f]}" for f in allowed_fields)
    if review_mode:
        task = ("The report draft is complete and the user is reviewing it. Their message is a correction or addition. "
                "Update ONLY the fields they want to change, rewriting each changed field as complete clean text "
                "(merge with the existing value when they are adding something). If it is unclear which field to change, "
                "set needs_follow_up=true and ask which part to change.")
    else:
        task = (f'The bot just asked about "{current_field}" ({FIELD_LABELS[current_field]}): "{QUESTIONS[current_field]}". '
                "Map the user's answer to that field. If the same answer also clearly contains information for other "
                "allowed fields, fill those too.")

    follow_up_context = ""
    if previous_answer:
        follow_up_context = (
            f"\nThe user's earlier answer for this field was {_js(previous_answer)} and you asked: "
            f"{_js(follow_up_question or '')}. Combine the earlier answer with the new message into one complete value. "
            "Only ask another follow-up if it is still impossible to write a useful report line."
        )

    return f"""/no_think
You are Echo, a friendly daily team report assistant. You turn a {role}'s messy chat answers into clean report fields.

Respond with ONLY one valid JSON object. No markdown, no code fences, no explanation.
Shape: {{"updates":{{"<field>":"clean text"}},"needs_follow_up":false,"follow_up_question":"","confidence":0.9}}

ALLOWED FIELDS (never use any other key):
{field_list}

RULES:
1. Fix spelling, grammar and capitalization. Write clean, professional, complete sentences (project is just a short title, no period).
2. Keep the user's meaning. Never invent facts, names, numbers or dates that the user did not say.
3. Context words like "same project", "same work", "that task", "previous work", "yesterday project" refer to MEMORY. Use memory values only when the matching memory value is non-empty; otherwise ask a follow-up.
4. If the answer is too vague to be useful in a report (e.g. "backend work", "stuff", "coding", "some fixes"), set needs_follow_up=true, leave updates empty and ask one short specific follow-up question with examples.
5. Clear negative answers ("no", "none", "nothing", "no blockers") are valid answers: write them as a full sentence such as "No blockers were reported.".
6. One answer may fill several fields; put each piece in the right field.
7. confidence is a number 0-1. If the answer is clear and unambiguous, confidence must be above 0.8.

{EXAMPLES}

NOW THE REAL INPUT:
{task}{follow_up_context}
memory: {_js(memory or {})}
draft so far: {_js(filled)}
current_field={'review' if review_mode else current_field}, user: {_js(message)}
JSON:"""


def extract_first_json(text):
    """Returns the first balanced JSON object in text that may contain extra output."""
    if not isinstance(text, str):
        return None
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I)
    try:
        return json.loads(cleaned.strip())
    except ValueError:
        pass

    start = cleaned.find("{")
    while start != -1:
        depth, in_string, escaped = 0, False, False
        for i in range(start, len(cleaned)):
            ch = cleaned[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(cleaned[start:i + 1])
                    except ValueError:
                        break
        start = cleaned.find("{", start + 1)
    return None


def _post_json(url, payload, timeout):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def _call_ollama(prompt: str) -> str:
    try:
        data = _post_json(
            config.OLLAMA_URL,
            {
                "model": config.OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "think": False,
                "format": "json",
                "keep_alive": "30m",
                "options": {"temperature": 0.1, "num_predict": 400},
            },
            config.OLLAMA_TIMEOUT_S,
        )
    except (socket.timeout, TimeoutError):
        raise ModelUnavailableError("Model timed out") from None
    except urllib.error.HTTPError as e:
        raise ModelUnavailableError(f"Ollama HTTP {e.code}: {e.read()[:200]!r}") from None
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise ModelUnavailableError(str(e)) from None
    return data.get("response") or ""


def analyze_user_message(*, role, allowed_fields, current_field, draft, memory, message,
                         review_mode=False, previous_answer="", follow_up_question="") -> dict:
    """Asks the model to interpret one user message.

    Returns the raw parsed object (validated later by the caller), or PARSE_FAILURE when the
    response is not JSON. Raises ModelUnavailableError when Ollama is unreachable.
    """
    prompt = build_prompt(
        role=role, allowed_fields=allowed_fields, current_field=current_field, draft=draft, memory=memory,
        message=message, review_mode=review_mode, previous_answer=previous_answer,
        follow_up_question=follow_up_question,
    )
    raw = _call_ollama(prompt)
    parsed = extract_first_json(raw)
    if parsed is None:
        log.warning("[model] could not parse JSON from response: %s", raw[:300])
        return dict(PARSE_FAILURE)
    return parsed


def model_status() -> dict:
    """Lightweight health check: is Ollama up and is the configured model installed?"""
    base = re.sub(r"/api/generate/?$", "", config.OLLAMA_URL)
    try:
        with urllib.request.urlopen(f"{base}/api/tags", timeout=2.5) as res:
            data = json.loads(res.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return {"online": False, "model": config.OLLAMA_MODEL}
    installed = any(
        m.get("name") == config.OLLAMA_MODEL or m.get("model") == config.OLLAMA_MODEL
        for m in data.get("models", [])
    )
    return {"online": installed, "model": config.OLLAMA_MODEL, "installed": installed}
