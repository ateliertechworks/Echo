import { Router } from 'express';
import { authRequired, leaderOnly } from '../middleware/auth.js';
import { createReport, createDiscussion, listReports } from '../controllers/reports.controller.js';

const r = Router();
r.use(authRequired);
r.post('/reports', createReport);
r.get('/reports', listReports);
r.post('/discussions', leaderOnly, createDiscussion);
export default r;
