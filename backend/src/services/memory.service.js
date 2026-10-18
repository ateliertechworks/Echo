// Previous-report memory for the chatbot, used to resolve phrases like
// "same project" or "previous work". Read-only: never writes to the DB.

import { pool } from '../db/pool.js';

const EMPTY_MEMORY = { lastProject: '', lastWorkDone: '', lastPending: '' };

/**
 * Latest saved report for this user/team before today.
 * Falls back to an empty memory when the DB is unavailable.
 */
export async function getChatMemory(userId, teamId) {
  if (!userId || !teamId) return { ...EMPTY_MEMORY };
  try {
    const { rows } = await pool.query(
      `SELECT project_name, work_done, leader_work, pending_work, next_plan, report_date
       FROM reports
       WHERE user_id = $1 AND team_id = $2 AND report_date < CURRENT_DATE
       ORDER BY report_date DESC, submitted_time DESC
       LIMIT 1`,
      [userId, teamId]
    );
    const r = rows[0];
    if (!r) return { ...EMPTY_MEMORY };
    return {
      lastProject: r.project_name || '',
      lastWorkDone: r.leader_work || r.work_done || '',
      lastPending: [r.pending_work, r.next_plan].filter(Boolean).join(' '),
    };
  } catch (e) {
    console.warn('[chat-memory] falling back to empty memory:', e.message);
    return { ...EMPTY_MEMORY };
  }
}
