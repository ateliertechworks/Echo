"""Question flow for the Echo report chatbot. The app (not the model) owns which
field is asked next, so the order here is the order of the conversation."""

MEMBER_FIELDS = ["project", "work_done", "outcome", "blockers", "pending_next"]

LEADER_FIELDS = ["project", "discussion", "event", "work_done", "outcome", "blockers", "pending_next"]

ALL_FIELDS = list(dict.fromkeys(LEADER_FIELDS + MEMBER_FIELDS))

QUESTIONS = {
    "project": "What project are you reporting on today?",
    "discussion": "What did the team discuss or decide today?",
    "event": "Was there any event, meeting, or activity today?",
    "work_done": "What work did you complete today?",
    "outcome": "What was the outcome of that work?",
    "blockers": "Did anything block or slow you down?",
    "pending_next": "What work is still pending or planned next?",
}

FIELD_LABELS = {
    "project": "Project",
    "discussion": "Team discussion",
    "event": "Event / meeting",
    "work_done": "Work done",
    "outcome": "Outcome",
    "blockers": "Blockers",
    "pending_next": "Pending / next",
}

FIELD_ICONS = {
    "project": "📁",
    "discussion": "💬",
    "event": "📅",
    "work_done": "🛠️",
    "outcome": "🎯",
    "blockers": "🚧",
    "pending_next": "⏭️",
}


def fields_for_role(role: str) -> list[str]:
    return LEADER_FIELDS if role == "leader" else MEMBER_FIELDS


def question_for(field: str) -> str:
    return QUESTIONS.get(field, "Could you tell me a bit more?")
