import { Router } from 'express';
import { authRequired } from '../middleware/auth.js';
import {
  getStatus,
  getHistory,
  postMessage,
  postChatMessage,
  postFinalize,
  postEditSummary,
  postSave,
  resetToday,
} from '../controllers/chat.controller.js';

const r = Router();
r.get('/status', getStatus); // public — used by client to detect if LLM is configured
r.use(authRequired);
r.get('/history', getHistory);
r.post('/message', postChatMessage); // model-assisted flow (Ollama)
r.post('/legacy/message', postMessage); // previous rule-based flow, kept for compatibility
r.post('/finalize', postFinalize);
r.post('/edit', postEditSummary);
r.post('/save', postSave);
r.post('/reset', resetToday);
export default r;
