import { Router } from 'express';
import { authRequired } from '../middleware/auth.js';
import { streamExcel } from '../services/excelExport.service.js';

const r = Router();
r.use(authRequired);
r.get('/excel', streamExcel);
export default r;
