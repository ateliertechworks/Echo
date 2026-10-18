import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import { runMigrations } from './db/runMigrations.js';
import authRoutes from './routes/auth.routes.js';
import profileRoutes from './routes/profile.routes.js';
import teamsRoutes from './routes/teams.routes.js';
import reportsRoutes from './routes/reports.routes.js';
import exportRoutes from './routes/export.routes.js';
import chatRoutes from './routes/chat.routes.js';

const app = express();
app.use(cors());
app.use(express.json({ limit: '5mb' }));

app.get('/api/health', (_req, res) => res.json({ ok: true, ts: Date.now() }));
app.use('/api/auth', authRoutes);
app.use('/api/profile', profileRoutes);
app.use('/api/teams', teamsRoutes);
app.use('/api', reportsRoutes);
app.use('/api/export', exportRoutes);
app.use('/api/chat', chatRoutes);
app.use('/chat', chatRoutes);

app.use((err, _req, res, _next) => {
  console.error('[error]', err);
  res.status(err.status || 500).json({ error: err.message || 'Internal error' });
});

const port = process.env.PORT || 4000;

async function main() {
  try {
    await runMigrations();
  } catch (e) {
    console.error('[migrate] failed', e);
    process.exit(1);
  }
  app.listen(port, () => console.log(`[api] listening on :${port}`));
}
main();
