import { pool } from '../db/pool.js';

const PROFILE_FIELDS = `id, username, email, linkedin_url, github_url, kaggle_url, medium_url,
  profile_photo, role_title, bio, skills, profile_completed, created_at`;

export async function getProfile(req, res) {
  const { rows } = await pool.query(`SELECT ${PROFILE_FIELDS} FROM profiles WHERE id = $1`, [req.user.id]);
  if (!rows.length) return res.status(404).json({ error: 'Not found' });
  return res.json(rows[0]);
}

export async function updateProfile(req, res) {
  const {
    username,
    email,
    linkedin_url,
    github_url,
    kaggle_url,
    medium_url,
    profile_photo,
    role_title,
    bio,
    skills,
  } = req.body || {};
  const { rows } = await pool.query(
    `UPDATE profiles SET
       username = COALESCE($2, username),
       email = COALESCE($3, email),
       linkedin_url = $4,
       github_url = $5,
       kaggle_url = $6,
       medium_url = $7,
       profile_photo = $8,
       role_title = $9,
       bio = $10,
       skills = $11,
       profile_completed = TRUE
     WHERE id = $1
     RETURNING ${PROFILE_FIELDS}`,
    [
      req.user.id,
      username,
      email,
      linkedin_url || null,
      github_url || null,
      kaggle_url || null,
      medium_url || null,
      profile_photo || null,
      role_title || null,
      bio || null,
      Array.isArray(skills) ? skills : null,
    ]
  );
  return res.json(rows[0]);
}
