import { pool } from '../db/pool.js';
import { requireMembership } from '../middleware/auth.js';

function generateCode(len = 8) {
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  let out = '';
  for (let i = 0; i < len; i++) out += alphabet[Math.floor(Math.random() * alphabet.length)];
  return out;
}

export async function createTeam(req, res) {
  const { team_name, description } = req.body || {};
  if (!team_name) return res.status(400).json({ error: 'team_name required' });
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    let code;
    for (let i = 0; i < 5; i++) {
      code = generateCode();
      const dup = await client.query('SELECT 1 FROM teams WHERE team_code = $1', [code]);
      if (!dup.rowCount) break;
    }
    const t = await client.query(
      `INSERT INTO teams (team_name, team_code, description, created_by)
       VALUES ($1, $2, $3, $4) RETURNING *`,
      [team_name, code, description || null, req.user.id]
    );
    await client.query(
      `INSERT INTO team_members (team_id, user_id, role) VALUES ($1, $2, 'leader')`,
      [t.rows[0].id, req.user.id]
    );
    await client.query('COMMIT');
    res.json({ ...t.rows[0], role: 'leader' });
  } catch (e) {
    await client.query('ROLLBACK');
    throw e;
  } finally {
    client.release();
  }
}

export async function joinTeam(req, res) {
  const { team_code } = req.body || {};
  if (!team_code) return res.status(400).json({ error: 'team_code required' });
  const team = await pool.query('SELECT * FROM teams WHERE team_code = $1', [team_code.toUpperCase()]);
  if (!team.rowCount) return res.status(404).json({ error: 'Team code not found' });
  const already = await pool.query(
    'SELECT role FROM team_members WHERE team_id = $1 AND user_id = $2',
    [team.rows[0].id, req.user.id]
  );
  if (already.rowCount) return res.json({ ...team.rows[0], role: already.rows[0].role });
  await pool.query(
    `INSERT INTO team_members (team_id, user_id, role) VALUES ($1, $2, 'member')`,
    [team.rows[0].id, req.user.id]
  );
  res.json({ ...team.rows[0], role: 'member' });
}

export async function listMyTeams(req, res) {
  const { rows } = await pool.query(
    `SELECT t.*, tm.role,
            (SELECT COUNT(*) FROM team_members WHERE team_id = t.id)::int AS member_count
     FROM teams t
     JOIN team_members tm ON tm.team_id = t.id
     WHERE tm.user_id = $1
     ORDER BY t.created_at DESC`,
    [req.user.id]
  );
  res.json(rows);
}

export async function getTeam(req, res) {
  const role = await requireMembership(req, res, req.params.id);
  if (!role) return;
  const team = await pool.query('SELECT * FROM teams WHERE id = $1', [req.params.id]);
  if (!team.rowCount) return res.status(404).json({ error: 'Not found' });
  res.json({ ...team.rows[0], role });
}

export async function listMembers(req, res) {
  const role = await requireMembership(req, res, req.params.id);
  if (!role) return;
  const { rows } = await pool.query(
    `SELECT p.id, p.username, p.email, p.linkedin_url, p.github_url, p.kaggle_url, p.medium_url,
            p.profile_photo, p.role_title, p.bio, p.skills, tm.role, tm.joined_at
     FROM team_members tm
     JOIN profiles p ON p.id = tm.user_id
     WHERE tm.team_id = $1
     ORDER BY (tm.role = 'leader') DESC, tm.joined_at ASC`,
    [req.params.id]
  );
  res.json(rows);
}

export async function removeMember(req, res) {
  const teamId = req.params.id;
  const userId = req.params.userId;
  // caller has already passed leaderOnly middleware
  const target = await pool.query(
    'SELECT role FROM team_members WHERE team_id = $1 AND user_id = $2',
    [teamId, userId]
  );
  if (!target.rowCount) return res.status(404).json({ error: 'Member not found' });
  if (target.rows[0].role === 'leader') return res.status(400).json({ error: 'Cannot remove leader' });
  await pool.query('DELETE FROM team_members WHERE team_id = $1 AND user_id = $2', [teamId, userId]);
  res.json({ ok: true });
}
