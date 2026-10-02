import jwt from 'jsonwebtoken';
import { pool } from '../db/pool.js';

export function authRequired(req, res, next) {
  const header = req.headers.authorization || '';
  const token = header.startsWith('Bearer ') ? header.slice(7) : null;
  if (!token) return res.status(401).json({ error: 'Missing token' });
  try {
    const payload = jwt.verify(token, process.env.JWT_SECRET);
    req.user = { id: payload.sub, email: payload.email };
    next();
  } catch {
    return res.status(401).json({ error: 'Invalid token' });
  }
}

export function leaderOnly(req, res, next) {
  const teamId = req.params.id || req.params.teamId || req.body.team_id || req.query.team_id;
  if (!teamId) return res.status(400).json({ error: 'team_id required' });
  pool
    .query('SELECT role FROM team_members WHERE team_id = $1 AND user_id = $2', [teamId, req.user.id])
    .then(({ rows }) => {
      if (!rows.length) return res.status(403).json({ error: 'Not a member of this team' });
      if (rows[0].role !== 'leader') return res.status(403).json({ error: 'Leader only' });
      req.teamRole = 'leader';
      next();
    })
    .catch((err) => next(err));
}

export async function requireMembership(req, res, teamId) {
  const { rows } = await pool.query(
    'SELECT role FROM team_members WHERE team_id = $1 AND user_id = $2',
    [teamId, req.user.id]
  );
  if (!rows.length) {
    res.status(403).json({ error: 'Not a member of this team' });
    return null;
  }
  return rows[0].role;
}
