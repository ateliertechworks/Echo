import { pool } from '../db/pool.js';
import { requireMembership } from '../middleware/auth.js';

export async function createReport(req, res) {
  const {
    team_id,
    project_name,
    work_done,
    outcome,
    blockers,
    pending_work,
    chatbot_summary,
    report_date,
  } = req.body || {};
  if (!team_id) return res.status(400).json({ error: 'team_id required' });
  const role = await requireMembership(req, res, team_id);
  if (!role) return;
  const date = report_date || new Date().toISOString().slice(0, 10);
  const { rows } = await pool.query(
    `INSERT INTO reports (user_id, team_id, project_name, work_done, outcome, blockers,
                          pending_work, chatbot_summary, report_date)
     VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
     ON CONFLICT (user_id, team_id, report_date)
     DO UPDATE SET
       project_name    = EXCLUDED.project_name,
       work_done       = EXCLUDED.work_done,
       outcome         = EXCLUDED.outcome,
       blockers        = EXCLUDED.blockers,
       pending_work    = EXCLUDED.pending_work,
       chatbot_summary = EXCLUDED.chatbot_summary,
       submitted_time  = now(),
       updated_at      = now()
     RETURNING *`,
    [
      req.user.id,
      team_id,
      project_name || null,
      work_done || null,
      outcome || null,
      blockers || null,
      pending_work || null,
      chatbot_summary || null,
      date,
    ]
  );
  res.json(rows[0]);
}

export async function createDiscussion(req, res) {
  const { team_id, project_name, discussion_summary, report_date } = req.body || {};
  if (!team_id) return res.status(400).json({ error: 'team_id required' });
  const date = report_date || new Date().toISOString().slice(0, 10);
  const { rows } = await pool.query(
    `INSERT INTO discussions (leader_id, team_id, project_name, discussion_summary, report_date)
     VALUES ($1,$2,$3,$4,$5)
     ON CONFLICT (leader_id, team_id, report_date)
     DO UPDATE SET
       project_name       = EXCLUDED.project_name,
       discussion_summary = EXCLUDED.discussion_summary,
       submitted_time     = now(),
       updated_at         = now()
     RETURNING *`,
    [req.user.id, team_id, project_name || null, discussion_summary || null, date]
  );
  res.json(rows[0]);
}

/**
 * Filters (all optional, combinable):
 * team_id, user_id, project, month (1-12), year, from, to, date
 * Members always scoped to their own rows.
 */
export async function listReports(req, res) {
  const { team_id } = req.query;
  if (!team_id) return res.status(400).json({ error: 'team_id required' });
  const role = await requireMembership(req, res, team_id);
  if (!role) return;

  const filters = ['r.team_id = $1'];
  const params = [team_id];
  const push = (clause, val) => {
    params.push(val);
    filters.push(clause.replace('?', `$${params.length}`));
  };

  if (role === 'member') push('r.user_id = ?', req.user.id);
  else if (req.query.user_id) push('r.user_id = ?', req.query.user_id);

  if (req.query.project) push('r.project_name ILIKE ?', `%${req.query.project}%`);
  if (req.query.date) push('r.report_date = ?', req.query.date);
  if (req.query.from) push('r.report_date >= ?', req.query.from);
  if (req.query.to) push('r.report_date <= ?', req.query.to);
  if (req.query.month) push('EXTRACT(MONTH FROM r.report_date) = ?', Number(req.query.month));
  if (req.query.year) push('EXTRACT(YEAR FROM r.report_date) = ?', Number(req.query.year));

  const sql = `
    SELECT r.*, p.username, p.email
    FROM reports r
    JOIN profiles p ON p.id = r.user_id
    WHERE ${filters.join(' AND ')}
    ORDER BY r.report_date DESC, r.submitted_time DESC`;
  const { rows } = await pool.query(sql, params);
  res.json(rows);
}
