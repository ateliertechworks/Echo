import { Router } from 'express';
import { signup, signin } from '../controllers/auth.controller.js';

const r = Router();
r.post('/signup', signup);
r.post('/signin', signin);
export default r;
