import { Router } from 'express';
import { authRequired } from '../middleware/auth.js';
import { getProfile, updateProfile } from '../controllers/profile.controller.js';

const r = Router();
r.use(authRequired);
r.get('/', getProfile);
r.put('/', updateProfile);
export default r;
