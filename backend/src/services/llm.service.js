// Local, rule-based report chatbot. No external LLM APIs.
// Conversation state is rebuilt from `chat_messages` using system events:
//   { type: 'ask',     field }               – bot asked question for field
//   { type: 'answer',  field, value }        – user's normalized answer stored
//   { type: 'skip',    field }               – user skipped this field
//   { type: 'clarify', field }               – bot asked clarification (once)
//   { type: 'ready' }                        – bot signalled READY_TO_SUMMARIZE

const LEADER_FIELDS = [
  'project_name',
  'leader_work',
  'team_discussion',
  'team_progress',
  'outcome',
  'blockers',
  'pending_work',
  'next_plan',
];

const MEMBER_FIELDS = [
  'project_name',
  'work_done',
  'outcome',
  'blockers',
  'pending_work',
  'next_plan',
];

const QUESTIONS = {
  project_name: 'What project or area are you reporting on today?',
  leader_work: 'What work did you personally do today?',
  work_done: 'What work did you do today?',
  team_discussion: 'What did the team discuss or decide today?',
  team_progress: 'What progress did the team make today?',
  outcome: 'What was the outcome of that work?',
  blockers: 'Did anything block or slow you down?',
  pending_work: 'What work is still pending?',
  next_plan: 'What do you plan to work on next?',
};

const CLARIFY = {
  project_name: "I didn't catch that. Could you tell me the project or area name?",
  leader_work: "I didn't catch that. Could you describe the work you personally did?",
  work_done: "I didn't catch that. Could you describe the work you did today?",
  team_discussion: "I didn't catch that. Could you share what the team discussed or decided?",
  team_progress: "I didn't catch that. Could you share what progress the team made?",
  outcome: "I didn't catch that. Could you share the outcome of the work?",
  blockers: "I didn't catch that. Can you explain the blocker a little more clearly?",
  pending_work: "I didn't catch that. Could you mention what work is still pending?",
  next_plan: "I didn't catch that. Could you share what you plan to work on next?",
};

const READY_MESSAGE = "Thanks — I have everything I need. Here's your draft report.";

const requiredFor = (role) => (role === 'leader' ? LEADER_FIELDS : MEMBER_FIELDS);

const emptyDraft = () => ({
  project_name: '',
  leader_work: '',
  work_done: '',
  team_discussion: '',
  team_progress: '',
  outcome: '',
  blockers: '',
  pending_work: '',
  next_plan: '',
});

// --- text helpers -------------------------------------------------------

const TYPO_MAP = [
  [/\bteh\b/gi, 'the'],
  [/\btd\b/gi, 'today'],
  [/\btmrw\b/gi, 'tomorrow'],
  [/\btmr\b/gi, 'tomorrow'],
  [/\babt\b/gi, 'about'],
  [/\bab\b/gi, 'about'],
  [/\bwrk\b/gi, 'work'],
  [/\bthx\b/gi, 'thanks'],
  [/\bpls\b/gi, 'please'],
  [/\bu\b/gi, 'you'],
  [/\br\b/gi, 'are'],
  [/\bim\b/gi, "I'm"],
  [/\bi m\b/gi, "I'm"],
  [/\bdunno\b/gi, "don't know"],
  [/\bidk\b/gi, "I don't know"],
  [/\bno idea\b/gi, "no idea"],
];

const FILLER_LEAD = /^(so|well|umm|um|uh|like|ok|okay|yeah|yes)[,.\s]+/i;

const NOTHING_TOKENS = new Set([
  'nothing', 'none', 'nope', 'no', 'na', 'nil', 'nada',
  'no blockers', 'no blocker', 'no issues', 'no problems',
  'no pending', 'no pending work', 'not planned', 'not decided',
  'not sure', 'nothing yet', 'nothing much', 'nothing planned',
]);

const clean = (v) => String(v ?? '').replace(/\s+/g, ' ').trim();

function applyTypoFixes(text) {
  let out = text;
  for (const [re, sub] of TYPO_MAP) out = out.replace(re, sub);
  return out.replace(/\s+/g, ' ').trim();
}

function stripFillerLead(text) {
  let out = text;
  let prev;
  do {
    prev = out;
    out = out.replace(FILLER_LEAD, '');
  } while (out !== prev);
  return out.trim();
}

function stripWorkPrefix(text) {
  return text
    .replace(/^\s*(?:i(?:'m| am)?\s+(?:currently\s+)?working\s+on\s+)/i, '')
    .replace(/^\s*(?:we(?:'re| are)\s+working\s+on\s+)/i, '')
    .replace(/^\s*(?:i\s+worked\s+on\s+)/i, '')
    .replace(/^\s*(?:working\s+on\s+)/i, '')
    .replace(/^\s*(?:the\s+project\s+is\s+)/i, '')
    .replace(/^\s*(?:project\s*(?:is|name)?\s*[:\-]?\s*)/i, '')
    .trim();
}

const SMALL_WORDS = new Set(['and', 'or', 'of', 'the', 'in', 'on', 'at', 'to', 'for', 'a', 'an', 'but', 'with', 'by', 'is', 'as']);

function titleCase(text) {
  return text
    .split(/\s+/)
    .map((word, i) => {
      if (!word) return word;
      // preserve all-caps acronyms of length <= 4
      if (/^[A-Z]{2,4}$/.test(word)) return word;
      const lower = word.toLowerCase();
      if (i > 0 && SMALL_WORDS.has(lower)) return lower;
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join(' ');
}

function capFirst(text) {
  const t = clean(text);
  if (!t) return t;
  return t.charAt(0).toUpperCase() + t.slice(1);
}

function ensurePeriod(text) {
  const t = clean(text);
  if (!t) return t;
  return /[.!?]$/.test(t) ? t : `${t}.`;
}

function isNothingAnswer(text) {
  const t = clean(text).toLowerCase().replace(/[.!?]+$/, '');
  if (!t) return false;
  if (NOTHING_TOKENS.has(t)) return true;
  return /^(nothing|none|no|not)\b/.test(t) && t.length <= 20;
}

// "unclear" = message contains no alphanumeric characters, e.g. just "?" or "..."
function isUnclear(text) {
  const t = clean(text);
  if (!t) return true;
  return !/[a-z0-9]/i.test(t);
}

// --- normalizers per field ---------------------------------------------

function normProjectName(raw) {
  let t = stripFillerLead(applyTypoFixes(clean(raw)));
  t = stripWorkPrefix(t);
  t = t.replace(/[.!?]+$/, '').trim();
  if (!t) return '';
  return titleCase(t);
}

function normLeaderWork(raw) {
  const t = capFirst(stripFillerLead(applyTypoFixes(clean(raw))));
  if (!t) return '';
  // Rephrase "I ..." into a personal-work sentence.
  if (/^i\b/i.test(t)) return ensurePeriod(t);
  return ensurePeriod(`I ${t.charAt(0).toLowerCase() + t.slice(1)}`);
}

function normWorkDone(raw) {
  const t = capFirst(stripFillerLead(applyTypoFixes(clean(raw))));
  if (!t) return '';
  if (/^i\b/i.test(t) || /^we\b/i.test(t)) return ensurePeriod(t);
  return ensurePeriod(`I ${t.charAt(0).toLowerCase() + t.slice(1)}`);
}

function normTeamDiscussion(raw) {
  let t = stripFillerLead(applyTypoFixes(clean(raw)));
  if (!t) return '';
  const lower = t.toLowerCase();
  if (isNothingAnswer(lower)) return 'No specific discussion was reported.';
  // Drop leading "about "/"regarding "/"on " since we prefix "The team discussed ".
  t = t.replace(/^(about|regarding|on|around)\s+/i, '');
  if (/^we\s+(decided|discussed|talked|agreed|planned)/i.test(t)) {
    return ensurePeriod(capFirst(t.replace(/^we\s+/i, 'The team ')));
  }
  if (/^(decided|discussed|talked|agreed|planned)/i.test(t)) {
    return ensurePeriod(`The team ${t.charAt(0).toLowerCase() + t.slice(1)}`);
  }
  if (/^the team\b/i.test(t)) return ensurePeriod(capFirst(t));
  // Short topic like "notion" → "The team discussed Notion."
  if (t.split(/\s+/).length <= 3) return ensurePeriod(`The team discussed ${titleCase(t)}`);
  return ensurePeriod(`The team discussed ${t}`);
}

function normTeamProgress(raw) {
  const t = stripFillerLead(applyTypoFixes(clean(raw)));
  if (!t) return '';
  if (isNothingAnswer(t)) return 'No specific team progress was reported.';
  if (/^we\b/i.test(t)) return ensurePeriod(capFirst(t.replace(/^we\b/i, 'The team')));
  if (/^the team\b/i.test(t)) return ensurePeriod(capFirst(t));
  return ensurePeriod(`The team ${t.charAt(0).toLowerCase() + t.slice(1)}`);
}

function normOutcome(raw) {
  const t = stripFillerLead(applyTypoFixes(clean(raw)));
  if (!t) return '';
  const lower = t.toLowerCase().replace(/[.!?]+$/, '');
  if (isNothingAnswer(lower)) return 'No specific outcome was reported.';
  // "completed", "we completed the work", "i finished it" → passive form
  const doneVerb = /^(?:(?:we|i|the team|team)\s+)?(?:successfully\s+)?(completed|finished|shipped|delivered|fixed|resolved|done|complete)(?:\s+(?:the|our|it|that)?\s*(?:work|task|project|it)?)?$/i;
  if (doneVerb.test(lower)) return 'The work was completed.';
  return ensurePeriod(capFirst(t));
}

function normBlockers(raw) {
  const t = stripFillerLead(applyTypoFixes(clean(raw)));
  if (!t) return '';
  if (isNothingAnswer(t)) return 'No blockers were reported.';
  if (/\b(blocker|blocked|issue|problem|slowed|delay)/i.test(t)) return ensurePeriod(capFirst(t));
  // Short comma/and-separated topic list e.g. "time and network" → sentence
  if (/^[a-z0-9\s,]+(?:\sand\s[a-z0-9\s]+)?$/i.test(t) && t.split(/\s+/).length <= 6) {
    return ensurePeriod(`${titleCase(t)} issues slowed down the work`);
  }
  return ensurePeriod(capFirst(t));
}

function normPending(raw) {
  const t = stripFillerLead(applyTypoFixes(clean(raw)));
  if (!t) return '';
  if (isNothingAnswer(t)) return 'No pending work was reported.';
  if (/^still\b/i.test(t)) return ensurePeriod(capFirst(t));
  if (/^(we|i)\s+/i.test(t)) return ensurePeriod(capFirst(t));
  return ensurePeriod(`Pending: ${t}`);
}

function normNextPlan(raw) {
  const t = stripFillerLead(applyTypoFixes(clean(raw)));
  if (!t) return '';
  if (isNothingAnswer(t) || /^not planned$|^not decided$|^undecided$/i.test(t)) {
    return 'No next plan was decided yet.';
  }
  if (/^(continue|continuing)\b/i.test(t)) return ensurePeriod(`Plan to ${t.charAt(0).toLowerCase() + t.slice(1)}`);
  if (/^(we|i)\s+/i.test(t)) return ensurePeriod(capFirst(t));
  return ensurePeriod(`Plan to ${t.charAt(0).toLowerCase() + t.slice(1)}`);
}

const NORMALIZERS = {
  project_name: normProjectName,
  leader_work: normLeaderWork,
  work_done: normWorkDone,
  team_discussion: normTeamDiscussion,
  team_progress: normTeamProgress,
  outcome: normOutcome,
  blockers: normBlockers,
  pending_work: normPending,
  next_plan: normNextPlan,
};

function normalizeField(field, raw) {
  const fn = NORMALIZERS[field];
  return fn ? fn(raw) : capFirst(clean(raw));
}

// --- state rebuild from history ----------------------------------------

function parseSystem(msg) {
  try { return JSON.parse(msg); } catch { return null; }
}

function buildState(role, history) {
  const required = requiredFor(role);
  const draft = emptyDraft();
  const answered = new Set();
  const skipped = new Set();
  const clarified = new Set();
  let currentField = null; // the field the user is being asked about
  let ready = false;

  for (const row of history) {
    if (row.message_type !== 'system') continue;
    const ev = parseSystem(row.message);
    if (!ev || !ev.type) continue;
    if (ev.type === 'ask' && ev.field) currentField = ev.field;
    else if (ev.type === 'clarify' && ev.field) {
      clarified.add(ev.field);
      currentField = ev.field;
    } else if (ev.type === 'answer' && ev.field) {
      draft[ev.field] = ev.value || '';
      answered.add(ev.field);
      if (currentField === ev.field) currentField = null;
    } else if (ev.type === 'skip' && ev.field) {
      skipped.add(ev.field);
      draft[ev.field] = '';
      if (currentField === ev.field) currentField = null;
    } else if (ev.type === 'ready') {
      ready = true;
    }
  }

  return { required, draft, answered, skipped, clarified, currentField, ready };
}

function nextMissing(state) {
  return state.required.find(
    (f) => !state.answered.has(f) && !state.skipped.has(f)
  ) || null;
}

// --- turn machine ------------------------------------------------------

function askEvent(field) { return { type: 'ask', field }; }
function answerEvent(field, value) { return { type: 'answer', field, value }; }
function skipEvent(field) { return { type: 'skip', field }; }
function clarifyEvent(field) { return { type: 'clarify', field }; }
function readyEvent() { return { type: 'ready' }; }

/**
 * Compute the next chatbot turn.
 * @param {object} args
 * @param {'leader'|'member'} args.role
 * @param {Array} args.history        rows from chat_messages ordered ASC
 * @param {'start'|'reply'|'skip'} args.action
 * @param {string} [args.content]     user's raw text when action === 'reply'
 * @returns {{ assistantMessage: string|null, readyToSummarize: boolean, events: object[] }}
 */
export function nextChatTurn({ role, history, action, content }) {
  const state = buildState(role, history);

  // Once ready, don't accept more answers – gently steer to Save/Edit/Cancel.
  if (state.ready) {
    return {
      assistantMessage: 'Your draft is ready. Please choose Save Report, Edit, or Cancel to continue.',
      readyToSummarize: true,
      events: [],
    };
  }

  // START: if nothing asked yet, ask the first missing field.
  if (action === 'start') {
    const missing = nextMissing(state);
    if (!missing) {
      return {
        assistantMessage: READY_MESSAGE,
        readyToSummarize: true,
        events: [readyEvent()],
      };
    }
    // If we already asked something and are just being restarted, don't re-ask.
    if (state.currentField) {
      return {
        assistantMessage: QUESTIONS[state.currentField],
        readyToSummarize: false,
        events: [],
      };
    }
    return {
      assistantMessage: QUESTIONS[missing],
      readyToSummarize: false,
      events: [askEvent(missing)],
    };
  }

  // We should always have a currentField at this point. If not (edge case),
  // treat the next missing field as current.
  const field = state.currentField || nextMissing(state);
  if (!field) {
    return {
      assistantMessage: READY_MESSAGE,
      readyToSummarize: true,
      events: [readyEvent()],
    };
  }

  const events = [];

  if (action === 'skip') {
    events.push(skipEvent(field));
  } else if (action === 'reply') {
    const raw = clean(content);
    if (isUnclear(raw) && !state.clarified.has(field)) {
      events.push(clarifyEvent(field));
      return {
        assistantMessage: CLARIFY[field] || QUESTIONS[field],
        readyToSummarize: false,
        events,
      };
    }
    // Accept (either clear, or second attempt after clarification).
    const value = normalizeField(field, raw) || capFirst(raw);
    events.push(answerEvent(field, value));
  } else {
    // Unknown action → do nothing.
    return {
      assistantMessage: QUESTIONS[field],
      readyToSummarize: false,
      events: [],
    };
  }

  // Determine next field.
  const nextState = {
    ...state,
    answered: new Set([...state.answered, ...events.filter((e) => e.type === 'answer').map((e) => e.field)]),
    skipped: new Set([...state.skipped, ...events.filter((e) => e.type === 'skip').map((e) => e.field)]),
  };
  const next = nextMissing(nextState);

  if (!next) {
    events.push(readyEvent());
    return { assistantMessage: READY_MESSAGE, readyToSummarize: true, events };
  }
  events.push(askEvent(next));
  return { assistantMessage: QUESTIONS[next], readyToSummarize: false, events };
}

// --- summary ------------------------------------------------------------

function joinSentences(parts) {
  return parts.filter(Boolean).map(clean).map(ensurePeriod).join(' ');
}

function narrativeFor(role, draft) {
  const parts = [];
  if (draft.project_name) parts.push(`Today, work focused on ${draft.project_name}`);
  if (role === 'leader') {
    if (draft.leader_work) parts.push(draft.leader_work);
    if (draft.team_discussion) parts.push(draft.team_discussion);
    if (draft.team_progress) parts.push(draft.team_progress);
  } else if (draft.work_done) parts.push(draft.work_done);
  if (draft.outcome) parts.push(draft.outcome);
  if (draft.blockers) parts.push(draft.blockers);
  if (draft.pending_work) parts.push(draft.pending_work);
  if (draft.next_plan) parts.push(draft.next_plan);
  return joinSentences(parts);
}

/**
 * Build the structured summary from history.
 */
export function buildSummary({ role, history }) {
  const state = buildState(role, history);
  const draft = { ...state.draft };
  if (role !== 'leader') {
    draft.leader_work = '';
    draft.team_discussion = '';
    draft.team_progress = '';
  } else {
    draft.work_done = '';
  }
  return {
    project_name: draft.project_name,
    leader_work: draft.leader_work,
    work_done: draft.work_done,
    team_discussion: draft.team_discussion,
    team_progress: draft.team_progress,
    outcome: draft.outcome,
    blockers: draft.blockers,
    pending_work: draft.pending_work,
    next_plan: draft.next_plan,
    skipped_fields: [...state.skipped],
    narrative: narrativeFor(role, draft),
  };
}

// --- local edit (no external API) --------------------------------------

const EDIT_MATCHERS = [
  { field: 'blockers',        re: /\b(block(er|ed)?|issue|bug|problem|obstacle)\b/i },
  { field: 'pending_work',    re: /\b(pending|left|remaining|todo|to[-\s]?do)\b/i },
  { field: 'next_plan',       re: /\b(next|tomorrow|plan|upcoming)\b/i },
  { field: 'outcome',         re: /\b(outcome|result|completed|shipped|fixed|delivered)\b/i },
  { field: 'team_discussion', re: /\b(discussion|discussed|decide|decision|talked)\b/i },
  { field: 'team_progress',   re: /\b(team\s+progress|team\s+made|team\s+finished|team\s+worked)\b/i },
  { field: 'leader_work',     re: /\b(my\s+work|personally|leader\s+work|i\s+worked|i\s+did)\b/i },
  { field: 'work_done',       re: /\b(work\s+done|work|built|implemented|developed)\b/i },
  { field: 'project_name',    re: /\b(project|area)\b/i },
];

function guessEditField(instruction) {
  for (const { field, re } of EDIT_MATCHERS) if (re.test(instruction)) return field;
  return null;
}

function stripEditVerb(instruction) {
  return instruction
    .replace(/^(please\s+)?(change|update|set|make|replace|edit|correct|fix)\s+/i, '')
    .replace(/^(the\s+)?(project|blockers?|outcome|pending|next\s*plan|discussion|team\s+progress|work\s+done|leader\s+work|my\s+work)\s+(to|as|with)\s+/i, '')
    .replace(/^(add|append)\s+/i, '')
    .trim();
}

export function editSummary({ role, current, instruction }) {
  const draft = { ...current };
  const field = guessEditField(instruction);
  if (field) {
    const raw = stripEditVerb(instruction);
    if (/\b(clear|remove|delete|none|blank)\b/i.test(raw)) draft[field] = '';
    else draft[field] = normalizeField(field, raw);
  } else {
    // No field detected: append the instruction (capitalized) to the narrative area
    // by treating it as an addition to work_done / leader_work.
    const target = role === 'leader' ? 'leader_work' : 'work_done';
    const raw = stripEditVerb(instruction);
    draft[target] = normalizeField(target, [draft[target], raw].filter(Boolean).join(' and '));
  }
  if (role !== 'leader') {
    draft.leader_work = '';
    draft.team_discussion = '';
    draft.team_progress = '';
  } else {
    draft.work_done = '';
  }
  draft.narrative = narrativeFor(role, draft);
  return draft;
}

// --- capabilities -------------------------------------------------------

export const llmAvailable = () => true;
export const llmProvider = () => 'local';
