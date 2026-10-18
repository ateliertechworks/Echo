// Validates and sanitizes the JSON returned by the model before the backend
// applies anything to the draft. Unknown fields and empty values are dropped.

import { ALL_FIELDS } from './questions.js';

const MIN_CONFIDENCE = 0.55;
const MAX_VALUE_LENGTH = 2000;
const DEFAULT_FOLLOW_UP = "I didn't catch that clearly. Can you explain it again?";

const isPlainObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);

/**
 * @param {unknown} output                raw parsed model output
 * @param {string[]} [allowedFields]      fields allowed for this user's role
 * @returns {{ valid: boolean, reason: string|null, updates: object,
 *            needs_follow_up: boolean, follow_up_question: string, confidence: number }}
 */
export function validateModelOutput(output, allowedFields = ALL_FIELDS) {
  const fail = (reason) => ({
    valid: false,
    reason,
    updates: {},
    needs_follow_up: true,
    follow_up_question: DEFAULT_FOLLOW_UP,
    confidence: 0,
  });

  if (!isPlainObject(output)) return fail('missing output');
  if (output.updates !== undefined && !isPlainObject(output.updates)) return fail('updates is not an object');

  const allowed = new Set(allowedFields);
  const updates = {};
  for (const [field, value] of Object.entries(output.updates || {})) {
    if (!allowed.has(field)) continue;
    if (typeof value !== 'string') continue;
    const text = value.replace(/\s+/g, ' ').trim();
    if (!text) continue;
    updates[field] = text.slice(0, MAX_VALUE_LENGTH);
  }

  const needsFollowUp = output.needs_follow_up === true;
  const followUp = typeof output.follow_up_question === 'string' ? output.follow_up_question.trim() : '';

  let confidence = typeof output.confidence === 'number' && Number.isFinite(output.confidence)
    ? output.confidence
    : Number.parseFloat(output.confidence);
  if (!Number.isFinite(confidence)) return fail('confidence is not a number');
  confidence = Math.min(1, Math.max(0, confidence));
  if (Object.keys(updates).length && confidence === 0) confidence = 0.75;

  if (!needsFollowUp && confidence < MIN_CONFIDENCE) {
    return { ...fail('confidence below threshold'), updates: {} };
  }

  return {
    valid: true,
    reason: null,
    updates,
    needs_follow_up: needsFollowUp,
    follow_up_question: needsFollowUp ? (followUp || DEFAULT_FOLLOW_UP) : '',
    confidence,
  };
}
