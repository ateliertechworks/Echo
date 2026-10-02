// Language understanding for the Echo chatbot via a local Ollama model.
// The model only interprets the user's answer and returns clean text as JSON;
// it never saves, never touches the DB and never decides the question flow.

import { FIELD_LABELS, QUESTIONS } from '../utils/questions.js';

const OLLAMA_URL = () => process.env.OLLAMA_URL || 'http://localhost:11434/api/generate';
const OLLAMA_MODEL = () => process.env.OLLAMA_MODEL || 'qwen3:1.7b';
const TIMEOUT_MS = Number(process.env.OLLAMA_TIMEOUT_MS) || 60000;

export const PARSE_FAILURE = Object.freeze({
  updates: {},
  needs_follow_up: true,
  follow_up_question: "I didn't catch that clearly. Can you explain it again?",
  confidence: 0,
});

const FIELD_GUIDE = {
  project: 'the project or product name (short title, e.g. "Team Management App")',
  discussion: 'what the team discussed or decided',
  event: 'any event, meeting, demo or activity that happened',
  work_done: 'concrete work the user completed today',
  outcome: 'the result of that work (what now works, what was delivered)',
  blockers: 'anything that blocked or slowed the user down',
  pending_next: 'work still pending or planned next',
};

const EXAMPLES = `EXAMPLES (follow this style exactly):

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
{"updates":{"work_done":"Fixed the Excel export bug and wrote the reports API.","outcome":"The changes were tested successfully.","blockers":"No blockers were reported."},"needs_follow_up":false,"follow_up_question":"","confidence":0.9}`;

function buildPrompt({ role, allowedFields, currentField, draft, memory, message, reviewMode, previousAnswer, followUpQuestion }) {
  const filled = Object.fromEntries(allowedFields.filter((f) => draft[f]).map((f) => [f, draft[f]]));
  const fieldList = allowedFields.map((f) => `- ${f}: ${FIELD_GUIDE[f]}`).join('\n');
  const task = reviewMode
    ? `The report draft is complete and the user is reviewing it. Their message is a correction or addition. Update ONLY the fields they want to change, rewriting each changed field as complete clean text (merge with the existing value when they are adding something). If it is unclear which field to change, set needs_follow_up=true and ask which part to change.`
    : `The bot just asked about "${currentField}" (${FIELD_LABELS[currentField]}): "${QUESTIONS[currentField]}". Map the user's answer to that field. If the same answer also clearly contains information for other allowed fields, fill those too.`;

  const followUpContext = previousAnswer
    ? `\nThe user's earlier answer for this field was ${JSON.stringify(previousAnswer)} and you asked: ${JSON.stringify(followUpQuestion || '')}. Combine the earlier answer with the new message into one complete value. Only ask another follow-up if it is still impossible to write a useful report line.`
    : '';

  return `/no_think
You are Echo, a friendly daily team report assistant. You turn a ${role}'s messy chat answers into clean report fields.

Respond with ONLY one valid JSON object. No markdown, no code fences, no explanation.
Shape: {"updates":{"<field>":"clean text"},"needs_follow_up":false,"follow_up_question":"","confidence":0.9}

ALLOWED FIELDS (never use any other key):
${fieldList}

RULES:
1. Fix spelling, grammar and capitalization. Write clean, professional, complete sentences (project is just a short title, no period).
2. Keep the user's meaning. Never invent facts, names, numbers or dates that the user did not say.
3. Context words like "same project", "same work", "that task", "previous work", "yesterday project" refer to MEMORY. Use memory values only when the matching memory value is non-empty; otherwise ask a follow-up.
4. If the answer is too vague to be useful in a report (e.g. "backend work", "stuff", "coding", "some fixes"), set needs_follow_up=true, leave updates empty and ask one short specific follow-up question with examples.
5. Clear negative answers ("no", "none", "nothing", "no blockers") are valid answers: write them as a full sentence such as "No blockers were reported.".
6. One answer may fill several fields; put each piece in the right field.
7. confidence is a number 0-1. If the answer is clear and unambiguous, confidence must be above 0.8.

${EXAMPLES}

NOW THE REAL INPUT:
${task}${followUpContext}
memory: ${JSON.stringify(memory || {})}
draft so far: ${JSON.stringify(filled)}
current_field=${reviewMode ? 'review' : currentField}, user: ${JSON.stringify(message)}
JSON:`;
}

/** Extracts the first balanced JSON object from text that may contain extra output. */
export function extractFirstJson(text) {
  if (typeof text !== 'string') return null;
  const cleaned = text.replace(/<think>[\s\S]*?<\/think>/gi, '');
  try { return JSON.parse(cleaned.trim()); } catch { /* fall through to scanning */ }

  for (let start = cleaned.indexOf('{'); start !== -1; start = cleaned.indexOf('{', start + 1)) {
    let depth = 0;
    let inString = false;
    let escaped = false;
    for (let i = start; i < cleaned.length; i++) {
      const ch = cleaned[i];
      if (inString) {
        if (escaped) escaped = false;
        else if (ch === '\\') escaped = true;
        else if (ch === '"') inString = false;
        continue;
      }
      if (ch === '"') inString = true;
      else if (ch === '{') depth++;
      else if (ch === '}' && --depth === 0) {
        try { return JSON.parse(cleaned.slice(start, i + 1)); } catch { break; }
      }
    }
  }
  return null;
}

async function callOllama(prompt) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const res = await fetch(OLLAMA_URL(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal,
      body: JSON.stringify({
        model: OLLAMA_MODEL(),
        prompt,
        stream: false,
        think: false,
        format: 'json',
        keep_alive: '30m',
        options: { temperature: 0.1, num_predict: 400 },
      }),
    });
    if (!res.ok) throw new Error(`Ollama HTTP ${res.status}: ${(await res.text()).slice(0, 200)}`);
    const data = await res.json();
    return data.response || '';
  } finally {
    clearTimeout(timer);
  }
}

export class ModelUnavailableError extends Error {}

/**
 * Asks the model to interpret one user message.
 * Returns the raw parsed object (validated later by the caller), or PARSE_FAILURE
 * when the response is not JSON. Throws ModelUnavailableError when Ollama is unreachable.
 */
export async function analyzeUserMessage({
  role, allowedFields, currentField, draft, memory, message, reviewMode = false, previousAnswer = '', followUpQuestion = '',
}) {
  const prompt = buildPrompt({ role, allowedFields, currentField, draft, memory, message, reviewMode, previousAnswer, followUpQuestion });
  let raw;
  try {
    raw = await callOllama(prompt);
  } catch (e) {
    throw new ModelUnavailableError(e.name === 'AbortError' ? 'Model timed out' : e.message);
  }
  const parsed = extractFirstJson(raw);
  if (!parsed) {
    console.warn('[model] could not parse JSON from response:', raw.slice(0, 300));
    return { ...PARSE_FAILURE };
  }
  return parsed;
}

/** Lightweight health check used by GET /chat/status. */
export async function modelStatus() {
  const base = OLLAMA_URL().replace(/\/api\/generate\/?$/, '');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 2500);
  try {
    const res = await fetch(`${base}/api/tags`, { signal: controller.signal });
    if (!res.ok) return { online: false, model: OLLAMA_MODEL() };
    const data = await res.json();
    const installed = (data.models || []).some((m) => m.name === OLLAMA_MODEL() || m.model === OLLAMA_MODEL());
    return { online: installed, model: OLLAMA_MODEL(), installed };
  } catch {
    return { online: false, model: OLLAMA_MODEL() };
  } finally {
    clearTimeout(timer);
  }
}
