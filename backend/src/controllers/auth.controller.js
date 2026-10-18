import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { pool } from '../db/pool.js';

function signToken(user) {
  return jwt.sign({ sub: user.id, email: user.email }, process.env.JWT_SECRET, { expiresIn: '7d' });
}

export async function signup(req, res) {
  const { username, email, password } = req.body || {};
  if (!username || !email || !password) {
    return res.status(400).json({ error: 'username, email, password required' });
  }
  if (password.length < 6) return res.status(400).json({ error: 'Password too short' });
  const existing = await pool.query('SELECT id FROM profiles WHERE email = $1', [email]);
  if (existing.rowCount) return res.status(409).json({ error: 'Email already registered' });
  const hash = await bcrypt.hash(password, 10);
  const { rows } = await pool.query(
    `INSERT INTO profiles (username, email, password_hash)
     VALUES ($1, $2, $3)
     RETURNING id, username, email, profile_completed`,
    [username, email, hash]
  );
  const user = rows[0];
  return res.json({ token: signToken(user), user });
}

export async function signin(req, res) {
  const { email, password } = req.body || {};
  if (!email || !password) return res.status(400).json({ error: 'email, password required' });
  const { rows } = await pool.query(
    'SELECT id, username, email, password_hash, profile_completed FROM profiles WHERE email = $1',
    [email]
  );
  if (!rows.length) return res.status(401).json({ error: 'Invalid credentials' });
  const ok = await bcrypt.compare(password, rows[0].password_hash);
  if (!ok) return res.status(401).json({ error: 'Invalid credentials' });
  const { password_hash, ...user } = rows[0];
  return res.json({ token: signToken(user), user });
}
