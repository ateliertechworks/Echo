// Main Echo chatbot flow. The backend owns the question order, validation and
// draft updates; the model is only consulted to understand the user's words.
// Nothing here saves the report — that stays behind the Save Report action.

import { FIELD_LABELS, fieldsForRole, questionFor } from '../utils/questions.js';
import { validateModelOutput } from '../utils/validateModelOutput.js';
import { analyzeUserMessage, ModelUnavailableError } from './model.service.js';
import { getChatMemory } from './memory.service.js';

export const READY_TO_SUMMARIZE = '[READY_TO_SUMMARIZE]';
const MAX_FOLLOW_UPS = 2;

const SKIP_RE = /^\s*(skip|skip it|skip this|skip this one|pass|next)\s*[.!]*\s*$/i;
const NEGATIVE_RE = /^(no|none|nope|nothing|nil|na|n\/a|not really|all good|nothing much|nothing today|none today|no blockers?|no issues?|no problems?|nothing pending|no pending( work)?|no events?|no meetings?|no discussions?|nothing (to report|planned))\s*[.!]*$/i;
const SAME_PROJECT_RE = /^(same|same project|same one|same as (yesterday|before|last time)|yesterday'?s? project|previous project|that project|the same project)\s*[.!]*$/i;
const SAME_WORK_RE = /^(same work|same task|that task|previous work|same as (yesterday|before|last time)|continued (the )?(same|previous) work)\s*[.!]*$/i;

// Answers too generic to put in a report (e.g. "backend work"). Each word must be generic.
const VAGUE_WORDS = new Set(['backend', 'frontend', 'front', 'end', 'back', 'ui', 'ux', 'work', 'worked', 'stuff', 'things', 'thing', 'some', 'few', 'coding', 'code', 'development', 'dev', 'tasks', 'task', 'fixes', 'fix', 'bugs', 'bug', 'testing', 'tests', 'misc', 'various', 'general', 'usual', 'the', 'on', 'did', 'done', 'i', 'my', 'just', 'it', 'good', 'fine', 'ok', 'okay', 'progress', 'meeting', 'meetings', 'research', 'learning', 'design']);
const VAGUE_FIELDS = new Set(['work_done', 'outcome', 'discussion']);
const VAGUE_FOLLOW_UPS = {
  backend: 'What backend work did you complete? Was it API, database, authentication, or Excel export?',
  frontend: 'What frontend work did you complete? Was it a page, a component, styling, or a bug fix?',
  ui: 'What UI work did you complete? Which screen or component was it?',
  bug: 'Which bug did you fix, and where was it (page, API, export…)?',
  fix: 'What did you fix, and where was it (page, API, export…)?',
  testing: 'What did you test, and how did it go?',
  meeting: 'What was the meeting about, and was anything decided?',
  design: 'What did you design — a screen, a flow, or a component?',
  research: 'What did you research, and what did you find?',
};
const VAGUE_DEFAULT = {
  work_done: 'Could you be more specific? What exactly did you work on (feature, page, API, bug)?',
  outcome: 'What was the result? For example: completed, deployed, tested, or still in progress?',
  discussion: 'What was discussed or decided? A short sentence is enough.',
};

function vagueFollowUp(field, text) {
  if (!VAGUE_FIELDS.has(field)) return null;
  const words = text.toLowerCase().replace(/[^a-z\s-]/g, ' ').split(/[\s-]+/).filter(Boolean);
  if (!words.length || words.length > 4 || !words.every((w) => VAGUE_WORDS.has(w))) return null;
  if (field === 'outcome' && words.some((w) => ['done', 'good', 'fine', 'ok', 'okay', 'progress'].includes(w))) return null;
  const key = words.find((w) => VAGUE_FOLLOW_UPS[w.replace(/s$/, '')] || VAGUE_FOLLOW_UPS[w]);
  const question = key ? VAGUE_FOLLOW_UPS[key] || VAGUE_FOLLOW_UPS[key.replace(/s$/, '')] : VAGUE_DEFAULT[field];
  return { updates: {}, needs_follow_up: true, follow_up_question: question, confidence: 0.4 };
}

const NEGATIVE_TEXT = {
  blockers: 'No blockers were reported.',
  pending_next: 'No pending work was reported.',
  discussion: 'No specific discussion was reported.',
  event: 'No events or meetings took place today.',
};

const SUGGESTIONS = {
  discussion: [{ label: 'No specific discussion', value: 'no discussion' }],
  event: [{ label: 'No events today', value: 'no events' }, { label: 'Daily stand-up', value: 'we had the daily stand-up meeting' }],
  outcome: [{ label: 'Completed successfully', value: 'completed successfully' }, { label: 'Still in progress', value: 'still in progress' }],
  blockers: [{ label: 'No blockers', value: 'no blockers' }],
  pending_next: [{ label: 'Nothing pending', value: 'nothing pending' }],
};

const clean = (v) => String(v ?? '').replace(/\s+/g, ' ').trim();
const capFirst = (t) => (t ? t.charAt(0).toUpperCase() + t.slice(1) : t);
const sentence = (t) => {
  const c = capFirst(clean(t));
  return !c || /[.!?]$/.test(c) ? c : `${c}.`;
};
const formatValue = (field, text) => (field === 'project' ? capFirst(clean(text)).replace(/[.]+$/, '') : sentence(text));

/** Makes a safe, role-scoped working copy of the draft sent by the client. */
function normalizeDraft(raw, fields) {
  const src = raw && typeof raw === 'object' ? raw : {};
  const draft = {};
  for (const f of fields) draft[f] = typeof src[f] === 'string' ? clean(src[f]) : '';
  draft._skipped = Array.isArray(src._skipped) ? src._skipped.filter((f) => fields.includes(f) && !draft[f]) : [];
  draft._followUps = {};
  const fu = src._followUps && typeof src._followUps === 'object' ? src._followUps : {};
  for (const f of fields) {
    if (fu[f] && typeof fu[f] === 'object') {
      draft._followUps[f] = {
        count: Number(fu[f].count) || 0,
        previous: clean(fu[f].previous).slice(0, 1000),
        question: clean(fu[f].question).slice(0, 300),
      };
    }
  }
  return draft;
}

const nextMissing = (draft, fields) => fields.find((f) => !draft[f] && !draft._skipped.includes(f)) || null;

function suggestionsFor(field, memory) {
  if (!field) return [];
  if (field === 'project' && memory?.lastProject) {
    return [{ label: `Same project · ${memory.lastProject}`, value: 'same project' }];
  }
  if (field === 'work_done' && memory?.lastWorkDone) {
    return [{ label: 'Same work as last report', value: 'same work' }];
  }
  return SUGGESTIONS[field] || [];
}

function progressFor(draft, fields, currentField) {
  return fields.map((f) => ({
    field: f,
    label: FIELD_LABELS[f],
    status: draft[f] ? 'filled' : draft._skipped.includes(f) ? 'skipped' : f === currentField ? 'current' : 'pending',
  }));
}

/** Readable preview plus the structure the existing Save Report endpoint expects. */
export function buildPreview(role, draft) {
  const fields = fieldsForRole(role);
  const isLeader = role === 'leader';
  const narrativeParts = [];
  if (draft.project) narrativeParts.push(`Today, work focused on ${draft.project}.`);
  for (const f of fields) if (f !== 'project' && draft[f]) narrativeParts.push(sentence(draft[f]));
  const narrative = narrativeParts.join(' ');

  const lines = fields.map((f) => `${FIELD_LABELS[f]}: ${draft[f] || '(skipped)'}`);

  return {
    role,
    fields: fields.map((f) => ({ field: f, label: FIELD_LABELS[f], value: draft[f] || '', skipped: !draft[f] })),
    text: lines.join('\n'),
    narrative,
    structured: {
      project_name: draft.project || '',
      work_done: isLeader ? '' : draft.work_done || '',
      leader_work: isLeader ? draft.work_done || '' : '',
      team_discussion: isLeader ? draft.discussion || '' : '',
      team_progress: isLeader ? draft.event || '' : '',
      outcome: draft.outcome || '',
      blockers: draft.blockers || '',
      pending_work: draft.pending_next || '',
      next_plan: '',
      skipped_fields: fields.filter((f) => !draft[f]),
      narrative,
    },
  };
}

/** Deterministic answers that don't need the model (faster and exact). */
function shortcutFor(field, message, memory, followUp) {
  const text = clean(message);
  if (!followUp) {
    const vague = vagueFollowUp(field, text);
    if (vague) return vague;
  }
  if (NEGATIVE_RE.test(text) && NEGATIVE_TEXT[field]) {
    return { updates: { [field]: NEGATIVE_TEXT[field] }, needs_follow_up: false, follow_up_question: '', confidence: 1 };
  }
  if (field === 'project' && SAME_PROJECT_RE.test(text)) {
    return memory.lastProject
      ? { updates: { project: memory.lastProject }, needs_follow_up: false, follow_up_question: '', confidence: 1 }
      : { updates: {}, needs_follow_up: true, follow_up_question: "I don't have a previous report to refer to yet. What's the project name?", confidence: 0.3 };
  }
  if (field === 'work_done' && SAME_WORK_RE.test(text) && memory.lastWorkDone) {
    return { updates: { work_done: `Continued the previous work: ${memory.lastWorkDone}` }, needs_follow_up: false, follow_up_question: '', confidence: 0.9 };
  }
  if (field === 'pending_next' && SAME_WORK_RE.test(text) && memory.lastPending) {
    return { updates: { pending_next: memory.lastPending }, needs_follow_up: false, follow_up_question: '', confidence: 0.9 };
  }
  return null;
}

/** Writes validated updates into the draft and returns what was captured. */
function applyUpdates(draft, updates, { currentField, reviewMode }) {
  const captured = [];
  for (const [field, value] of Object.entries(updates)) {
    const text = formatValue(field, value);
    if (!text) continue;
    const existing = draft[field];
    if (reviewMode || field === currentField || !existing) {
      draft[field] = text;
    } else if (!existing.toLowerCase().includes(text.toLowerCase())) {
      // Extra detail for a field answered earlier: keep both rather than lose information.
      draft[field] = `${sentence(existing)} ${text}`;
    } else {
      continue;
    }
    draft._skipped = draft._skipped.filter((f) => f !== field);
    delete draft._followUps[field];
    captured.push({ field, label: FIELD_LABELS[field], value: draft[field] });
  }
  return captured;
}

function respond({ role, draft, fields, currentField, botMessage, memory, done = false, needsFollowUp = false, captured = [], modelOnline = true, extra = {} }) {
  return {
    draft,
    currentField: done ? null : currentField,
    botMessage,
    done,
    needsFollowUp,
    preview: done ? buildPreview(role, draft) : null,
    captured,
    suggestions: done ? [] : suggestionsFor(currentField, memory),
    progress: progressFor(draft, fields, done ? null : currentField),
    modelOnline,
    ...extra,
  };
}

/**
 * Handle one chat turn.
 * @param {object} args
 * @param {string} args.userId
 * @param {string} args.teamId
 * @param {'leader'|'member'} args.role   resolved by the backend, never by the model
 * @param {string} [args.message]          empty → just return the current question
 * @param {string} [args.currentField]
 * @param {object} [args.draft]
 */
export async function handleChatMessage({ userId, teamId, role, message, currentField, draft: rawDraft }) {
  const fields = fieldsForRole(role);
  const draft = normalizeDraft(rawDraft, fields);
  const memory = await getChatMemory(userId, teamId);
  const text = clean(message);

  let field = fields.includes(currentField) ? currentField : nextMissing(draft, fields);
  const reviewMode = !field;
  const base = { role, draft, fields, memory };

  // Opening turn (or resume): ask the current question, or show the preview.
  if (!text) {
    if (reviewMode) return respond({ ...base, done: true, botMessage: READY_TO_SUMMARIZE });
    return respond({ ...base, currentField: field, botMessage: questionFor(field) });
  }

  if (SKIP_RE.test(text)) {
    if (reviewMode) return respond({ ...base, done: true, botMessage: READY_TO_SUMMARIZE });
    draft[field] = '';
    if (!draft._skipped.includes(field)) draft._skipped.push(field);
    delete draft._followUps[field];
    const next = nextMissing(draft, fields);
    if (!next) return respond({ ...base, done: true, botMessage: READY_TO_SUMMARIZE, extra: { skipped: field } });
    return respond({ ...base, currentField: next, botMessage: questionFor(next), extra: { skipped: field } });
  }

  const followUp = reviewMode ? null : draft._followUps[field];
  let modelOnline = true;
  let output = reviewMode ? null : shortcutFor(field, text, memory, followUp);

  if (!output) {
    try {
      output = await analyzeUserMessage({
        role,
        allowedFields: fields,
        currentField: field,
        draft,
        memory,
        message: text,
        reviewMode,
        previousAnswer: followUp?.previous || '',
        followUpQuestion: followUp?.question || '',
      });
    } catch (e) {
      if (!(e instanceof ModelUnavailableError)) throw e;
      console.warn('[chat] model unavailable, storing cleaned answer:', e.message);
      modelOnline = false;
      output = reviewMode
        ? { updates: {}, needs_follow_up: true, follow_up_question: 'The language model is offline, so I can’t apply edits by chat right now. Click a field in the preview to edit it directly.', confidence: 0 }
        : { updates: { [field]: [followUp?.previous, text].filter(Boolean).join(' — ') }, needs_follow_up: false, follow_up_question: '', confidence: 0.6 };
    }
  }

  const result = validateModelOutput(output, fields);

  if (reviewMode) {
    const captured = applyUpdates(draft, result.updates, { currentField: null, reviewMode: true });
    const botMessage = captured.length ? READY_TO_SUMMARIZE : result.follow_up_question || "I couldn't tell which part to change. Which field should I update?";
    return respond({ ...base, done: true, botMessage, captured, needsFollowUp: !captured.length, modelOnline });
  }

  const captured = applyUpdates(draft, result.updates, { currentField: field, reviewMode: false });

  // Vague or missing answer for the current field: ask a follow-up (bounded).
  if (!draft[field] || result.needs_follow_up) {
    const count = (followUp?.count || 0) + 1;
    if (count > MAX_FOLLOW_UPS) {
      // Don't trap the user in a loop — keep what they said, cleaned up.
      if (!draft[field]) {
        captured.push(...applyUpdates(draft, { [field]: [followUp?.previous, text].filter(Boolean).join(' — ') }, { currentField: field, reviewMode: false }));
      }
      delete draft._followUps[field];
    } else {
      const question = result.needs_follow_up && result.follow_up_question
        ? result.follow_up_question
        : `Could you tell me a bit more? ${questionFor(field)}`;
      draft._followUps[field] = {
        count,
        previous: [followUp?.previous, text].filter(Boolean).join(' — ').slice(0, 1000),
        question,
      };
      return respond({ ...base, currentField: field, botMessage: question, needsFollowUp: true, captured, modelOnline });
    }
  }

  const next = nextMissing(draft, fields);
  if (!next) return respond({ ...base, done: true, botMessage: READY_TO_SUMMARIZE, captured, modelOnline });
  return respond({ ...base, currentField: next, botMessage: questionFor(next), captured, modelOnline });
}
