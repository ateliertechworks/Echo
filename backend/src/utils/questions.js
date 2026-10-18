// Question flow for the Echo report chatbot. The backend (not the model) owns
// which field is asked next, so the order here is the order of the conversation.

export const MEMBER_FIELDS = ['project', 'work_done', 'outcome', 'blockers', 'pending_next'];

export const LEADER_FIELDS = ['project', 'discussion', 'event', 'work_done', 'outcome', 'blockers', 'pending_next'];

export const ALL_FIELDS = [...new Set([...LEADER_FIELDS, ...MEMBER_FIELDS])];

export const QUESTIONS = {
  project: 'What project are you reporting on today?',
  discussion: 'What did the team discuss or decide today?',
  event: 'Was there any event, meeting, or activity today?',
  work_done: 'What work did you complete today?',
  outcome: 'What was the outcome of that work?',
  blockers: 'Did anything block or slow you down?',
  pending_next: 'What work is still pending or planned next?',
};

export const FIELD_LABELS = {
  project: 'Project',
  discussion: 'Team discussion',
  event: 'Event / meeting',
  work_done: 'Work done',
  outcome: 'Outcome',
  blockers: 'Blockers',
  pending_next: 'Pending / next',
};

export const fieldsForRole = (role) => (role === 'leader' ? LEADER_FIELDS : MEMBER_FIELDS);

export const questionFor = (field) => QUESTIONS[field] || 'Could you tell me a bit more?';
