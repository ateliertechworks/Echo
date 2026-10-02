import { pool } from '../db/pool.js';
import { requireMembership } from '../middleware/auth.js';
import { nextChatTurn, buildSummary, editSummary, llmAvailable, llmProvider } from '../services/llm.service.js';
import { handleChatMessage } from '../services/chatFlow.service.js';
import { modelStatus } from '../services/model.service.js';

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

async function getRole(teamId, userId) {
  const { rows } = await pool.query(
    'SELECT role FROM team_members WHERE team_id = $1 AND user_id = $2',
    [teamId, userId]
  );
  return rows[0]?.role || null;
}

async function loadHistory({ teamId, userId, reportDate }) {
  const { rows } = await pool.query(
    `SELECT id, role, message, message_type, report_date, created_at
     FROM chat_messages
     WHERE team_id = $1 AND user_id = $2 AND report_date = $3
     ORDER BY created_at ASC, id ASC`,
    [teamId, userId, reportDate]
  );
  return rows;
}

async function saveMessage(client, { teamId, userId, role, message, messageType, reportDate }) {
  await client.query(
    `INSERT INTO chat_messages (team_id, user_id, role, message, message_type, report_date)
     VALUES ($1,$2,$3,$4,$5,$6)`,
    [teamId, userId, role, message, messageType, reportDate]
  );
}

export async function getStatus(_req, res) {
  const model = await modelStatus();
  return res.json({ llm_available: llmAvailable(), provider: llmProvider(), model });
}

// Model-assisted chat turn. Identity comes from the auth token and the role from
// team membership — body userId/role are never trusted. Nothing is saved here.
export async function postChatMessage(req, res, next) {
  try {
    const body = req.body || {};
    const teamId = body.teamId || body.team_id;
    if (!teamId) return res.status(400).json({ error: 'teamId required' });
    const role = await getRole(teamId, req.user.id);
    if (!role) return res.status(403).json({ error: 'Not a team member' });
    if (body.message != null && typeof body.message !== 'string') {
      return res.status(400).json({ error: 'message must be a string' });
    }
    const result = await handleChatMessage({
      userId: req.user.id,
      teamId,
      role,
      message: String(body.message || '').slice(0, 4000),
      currentField: body.currentField,
      draft: body.draft,
    });
    return res.json({ ...result, role });
  } catch (e) { next(e); }
}

export async function getHistory(req, res) {
  const { team_id } = req.query;
  const report_date = req.query.report_date || todayIso();
  if (!team_id) return res.status(400).json({ error: 'team_id required' });
  const role = await requireMembership(req, res, team_id);
  if (!role) return;
  const history = await loadHistory({ teamId: team_id, userId: req.user.id, reportDate: report_date });
  return res.json({ history, report_date });
}

export async function postMessage(req, res, next) {
  const client = await pool.connect();
  try {
    const { team_id, action } = req.body || {};
    const report_date = req.body?.report_date || todayIso();
    if (!team_id) return res.status(400).json({ error: 'team_id required' });
    const role = await getRole(team_id, req.user.id);
    if (!role) return res.status(403).json({ error: 'Not a team member' });

    await client.query('BEGIN');

    // Persist inbound event first so history reflects the user's action.
    if (action === 'reply') {
      const content = String(req.body?.content || '').trim();
      if (!content) {
        await client.query('ROLLBACK');
        return res.status(400).json({ error: 'content required' });
      }
      await saveMessage(client, {
        teamId: team_id, userId: req.user.id, role,
        message: content, messageType: 'user', reportDate: report_date,
      });
    } else if (action === 'skip') {
      await saveMessage(client, {
        teamId: team_id, userId: req.user.id, role,
        message: '(skipped)', messageType: 'skipped', reportDate: report_date,
      });
    } else if (action !== 'start') {
      await client.query('ROLLBACK');
      return res.status(400).json({ error: "action must be 'start', 'reply', or 'skip'" });
    }

    // Reload history (with the just-inserted row) and compute next turn.
    const { rows: history } = await client.query(
      `SELECT id, role, message, message_type, report_date, created_at
       FROM chat_messages
       WHERE team_id = $1 AND user_id = $2 AND report_date = $3
       ORDER BY created_at ASC, id ASC`,
      [team_id, req.user.id, report_date]
    );

    const content = action === 'reply' ? String(req.body?.content || '').trim() : '';
    const { assistantMessage, readyToSummarize, events } = nextChatTurn({
      role, history, action, content,
    });

    // Persist every system event, then the assistant message.
    for (const ev of events || []) {
      await saveMessage(client, {
        teamId: team_id, userId: req.user.id, role,
        message: JSON.stringify(ev), messageType: 'system', reportDate: report_date,
      });
    }
    if (assistantMessage) {
      await saveMessage(client, {
        teamId: team_id, userId: req.user.id, role,
        message: assistantMessage, messageType: 'assistant', reportDate: report_date,
      });
    }

    await client.query('COMMIT');
    return res.json({ assistantMessage, readyToSummarize, role });
  } catch (e) {
    try { await client.query('ROLLBACK'); } catch (_) { /* ignore */ }
    next(e);
  } finally {
    client.release();
  }
}

export async function postFinalize(req, res, next) {
  try {
    const { team_id } = req.body || {};
    const report_date = req.body?.report_date || todayIso();
    if (!team_id) return res.status(400).json({ error: 'team_id required' });
    const role = await getRole(team_id, req.user.id);
    if (!role) return res.status(403).json({ error: 'Not a team member' });
    const history = await loadHistory({ teamId: team_id, userId: req.user.id, reportDate: report_date });
    if (!history.length) return res.status(400).json({ error: 'No conversation to summarize yet' });

    const structured = buildSummary({ role, history });
    return res.json({ structured, role });
  } catch (e) { next(e); }
}

export async function postEditSummary(req, res, next) {
  try {
    const { team_id, current, instruction } = req.body || {};
    if (!team_id || !current || !instruction) return res.status(400).json({ error: 'team_id, current, instruction required' });
    const role = await getRole(team_id, req.user.id);
    if (!role) return res.status(403).json({ error: 'Not a team member' });
    const updated = editSummary({ role, current, instruction });
    return res.json({ structured: updated });
  } catch (e) { next(e); }
}

export async function postSave(req, res, next) {
  try {
    const { team_id, structured } = req.body || {};
    const report_date = req.body?.report_date || todayIso();
    if (!team_id || !structured) return res.status(400).json({ error: 'team_id and structured required' });
    const role = await getRole(team_id, req.user.id);
    if (!role) return res.status(403).json({ error: 'Not a team member' });

    const workDoneCol = role === 'leader' ? (structured.leader_work || null) : (structured.work_done || null);

    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      const rep = await client.query(
        `INSERT INTO reports (user_id, team_id, project_name, work_done, leader_work, team_progress,
                              outcome, blockers, pending_work, next_plan, chatbot_summary, report_date)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
         ON CONFLICT (user_id, team_id, report_date)
         DO UPDATE SET
           project_name    = EXCLUDED.project_name,
           work_done       = EXCLUDED.work_done,
           leader_work     = EXCLUDED.leader_work,
           team_progress   = EXCLUDED.team_progress,
           outcome         = EXCLUDED.outcome,
           blockers        = EXCLUDED.blockers,
           pending_work    = EXCLUDED.pending_work,
           next_plan       = EXCLUDED.next_plan,
           chatbot_summary = EXCLUDED.chatbot_summary,
           submitted_time  = now(),
           updated_at      = now()
         RETURNING *, (xmax = 0) AS inserted`,
        [
          req.user.id,
          team_id,
          structured.project_name || null,
          workDoneCol,
          role === 'leader' ? (structured.leader_work || null) : null,
          role === 'leader' ? (structured.team_progress || null) : null,
          structured.outcome || null,
          structured.blockers || null,
          structured.pending_work || null,
          structured.next_plan || null,
          structured.narrative || null,
          report_date,
        ]
      );
      // The day's discussion mirrors the latest saved report: replaced when present,
      // removed when the re-saved report no longer has one.
      if (role === 'leader' && structured.team_discussion) {
        await client.query(
          `INSERT INTO discussions (leader_id, team_id, project_name, discussion_summary, report_date)
           VALUES ($1,$2,$3,$4,$5)
           ON CONFLICT (leader_id, team_id, report_date)
           DO UPDATE SET
             project_name       = EXCLUDED.project_name,
             discussion_summary = EXCLUDED.discussion_summary,
             submitted_time     = now(),
             updated_at         = now()`,
          [req.user.id, team_id, structured.project_name || null, structured.team_discussion, report_date]
        );
      } else if (role === 'leader') {
        await client.query(
          `DELETE FROM discussions WHERE leader_id = $1 AND team_id = $2 AND report_date = $3`,
          [req.user.id, team_id, report_date]
        );
      }
      // Persist final structured summary for auditability.
      await client.query(
        `INSERT INTO chat_messages (team_id, user_id, role, message, message_type, report_date)
         VALUES ($1,$2,$3,$4,'summary',$5)`,
        [team_id, req.user.id, role, JSON.stringify(structured), report_date]
      );
      await client.query('COMMIT');
      const { inserted, ...report } = rep.rows[0];
      return res.json({ report, saved: true, updated: !inserted });
    } catch (e) {
      await client.query('ROLLBACK');
      throw e;
    } finally {
      client.release();
    }
  } catch (e) { next(e); }
}

export async function resetToday(req, res, next) {
  try {
    const { team_id } = req.body || {};
    const report_date = req.body?.report_date || todayIso();
    if (!team_id) return res.status(400).json({ error: 'team_id required' });
    const role = await getRole(team_id, req.user.id);
    if (!role) return res.status(403).json({ error: 'Not a team member' });
    // Clears only the draft conversation; the saved row in `reports` is untouched.
    await pool.query(
      `DELETE FROM chat_messages WHERE team_id = $1 AND user_id = $2 AND report_date = $3`,
      [team_id, req.user.id, report_date]
    );
    return res.json({ ok: true });
  } catch (e) { next(e); }
}
