import { Router } from 'express';
import { authRequired, leaderOnly } from '../middleware/auth.js';
import {
  createTeam,
  joinTeam,
  listMyTeams,
  getTeam,
  listMembers,
  removeMember,
} from '../controllers/teams.controller.js';

const r = Router();
r.use(authRequired);
r.post('/', createTeam);
r.post('/join', joinTeam);
r.get('/', listMyTeams);
r.get('/:id', getTeam);
r.get('/:id/members', listMembers);
r.delete('/:id/members/:userId', leaderOnly, removeMember);
export default r;
