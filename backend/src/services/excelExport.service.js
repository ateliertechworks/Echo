import ExcelJS from 'exceljs';
import { pool } from '../db/pool.js';

const HEADER_FILL = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF360568' } };
const HEADER_FONT = { color: { argb: 'FFFFFFFF' }, bold: true };
const ACCENT_FILL = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF9AC6C5' } };

function dayName(dateStr) {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { weekday: 'long' });
}

export async function generateWorkbook({ teamId, userIds, filters }) {
  const wb = new ExcelJS.Workbook();
  wb.creator = 'Team Report App';
  wb.created = new Date();

  // Team info
  const teamRes = await pool.query('SELECT * FROM teams WHERE id = $1', [teamId]);
  const team = teamRes.rows[0];

  // Determine members to include
  let memberQuery = `
    SELECT p.*, tm.role FROM team_members tm
    JOIN profiles p ON p.id = tm.user_id
    WHERE tm.team_id = $1`;
  const memberParams = [teamId];
  if (userIds && userIds.length) {
    memberQuery += ` AND p.id = ANY($2::uuid[])`;
    memberParams.push(userIds);
  }
  memberQuery += ` ORDER BY (tm.role = 'leader') DESC, p.username`;
  const members = (await pool.query(memberQuery, memberParams)).rows;

  for (const member of members) {
    const sheetName = (member.username || 'user').slice(0, 28).replace(/[\\/*?:[\]]/g, '_');
    const ws = wb.addWorksheet(sheetName);
    const isLeaderHeader = member.role === 'leader';
    const totalCols = isLeaderHeader ? 12 : 10;

    // Header block - profile
    ws.mergeCells(1, 1, 1, totalCols);
    const title = ws.getCell('A1');
    title.value = `${member.username}  (${isLeaderHeader ? 'Team Leader' : 'Member'})`;
    title.font = { size: 16, bold: true, color: { argb: 'FFFFFFFF' } };
    title.fill = HEADER_FILL;
    title.alignment = { vertical: 'middle', horizontal: 'left', indent: 1 };
    ws.getRow(1).height = 28;

    const labels = [
      ['Team', team.team_name],
      ['Username', member.username],
      ['Email', member.email],
      ['Role', member.role_title || (isLeaderHeader ? 'Team Leader' : 'Team Member')],
      ['LinkedIn', member.linkedin_url || ''],
      ['GitHub', member.github_url || ''],
      ['Kaggle', member.kaggle_url || ''],
      ['Medium', member.medium_url || ''],
    ];
    labels.forEach((row, i) => {
      const r = ws.getRow(2 + i);
      r.getCell(1).value = row[0];
      r.getCell(1).font = { bold: true };
      r.getCell(1).fill = ACCENT_FILL;
      ws.mergeCells(2 + i, 2, 2 + i, totalCols);
      r.getCell(2).value = row[1];
    });

    // Reports table
    const tableStart = 2 + labels.length + 1;
    const isLeader = member.role === 'leader';
    const headers = isLeader
      ? ['Date', 'Day', 'Project', 'Leader Work', 'Team Discussion', 'Team Progress', 'Outcome', 'Blockers', 'Pending Work', 'Next Plan', 'Chatbot Summary', 'Submitted']
      : ['Date', 'Day', 'Project', 'Work Done', 'Outcome', 'Blockers', 'Pending Work', 'Next Plan', 'Chatbot Summary', 'Submitted'];
    const headerRow = ws.getRow(tableStart);
    headers.forEach((h, i) => {
      const c = headerRow.getCell(i + 1);
      c.value = h;
      c.font = HEADER_FONT;
      c.fill = HEADER_FILL;
      c.alignment = { vertical: 'middle', horizontal: 'center' };
    });
    headerRow.height = 22;

    // Fetch reports (and discussions if leader) with filters
    const clauses = ['r.team_id = $1', 'r.user_id = $2'];
    const params = [teamId, member.id];
    const add = (clause, val) => {
      params.push(val);
      clauses.push(clause.replace('?', `$${params.length}`));
    };
    if (filters.project) add('r.project_name ILIKE ?', `%${filters.project}%`);
    if (filters.date) add('r.report_date = ?', filters.date);
    if (filters.from) add('r.report_date >= ?', filters.from);
    if (filters.to) add('r.report_date <= ?', filters.to);
    if (filters.month) add('EXTRACT(MONTH FROM r.report_date) = ?', Number(filters.month));
    if (filters.year) add('EXTRACT(YEAR FROM r.report_date) = ?', Number(filters.year));

    const reports = (
      await pool.query(
        `SELECT r.* FROM reports r WHERE ${clauses.join(' AND ')} ORDER BY r.report_date ASC, r.submitted_time ASC`,
        params
      )
    ).rows;

    // Optionally: leader discussions grouped by date/project
    let discussionMap = new Map();
    if (isLeader) {
      const dClauses = ['d.team_id = $1', 'd.leader_id = $2'];
      const dParams = [teamId, member.id];
      const dAdd = (clause, val) => {
        dParams.push(val);
        dClauses.push(clause.replace('?', `$${dParams.length}`));
      };
      if (filters.project) dAdd('d.project_name ILIKE ?', `%${filters.project}%`);
      if (filters.date) dAdd('d.report_date = ?', filters.date);
      if (filters.from) dAdd('d.report_date >= ?', filters.from);
      if (filters.to) dAdd('d.report_date <= ?', filters.to);
      if (filters.month) dAdd('EXTRACT(MONTH FROM d.report_date) = ?', Number(filters.month));
      if (filters.year) dAdd('EXTRACT(YEAR FROM d.report_date) = ?', Number(filters.year));
      const ds = (
        await pool.query(
          `SELECT d.* FROM discussions d WHERE ${dClauses.join(' AND ')}`,
          dParams
        )
      ).rows;
      // One discussion per leader/team/day, so the date alone is the key.
      for (const d of ds) {
        const key = new Date(d.report_date).toISOString().slice(0, 10);
        discussionMap.set(key, d.discussion_summary || '');
      }
    }

    reports.forEach((r, idx) => {
      const row = ws.getRow(tableStart + 1 + idx);
      const iso = new Date(r.report_date).toISOString().slice(0, 10);
      let col = 1;
      row.getCell(col++).value = iso;
      row.getCell(col++).value = dayName(r.report_date);
      row.getCell(col++).value = r.project_name || '';
      if (isLeader) {
        row.getCell(col++).value = r.leader_work || r.work_done || '';
        row.getCell(col++).value = discussionMap.get(iso) || '';
        row.getCell(col++).value = r.team_progress || '';
      } else {
        row.getCell(col++).value = r.work_done || '';
      }
      row.getCell(col++).value = r.outcome || '';
      row.getCell(col++).value = r.blockers || '';
      row.getCell(col++).value = r.pending_work || '';
      row.getCell(col++).value = r.next_plan || '';
      row.getCell(col++).value = r.chatbot_summary || '';
      row.getCell(col++).value = new Date(r.submitted_time).toLocaleString();
      row.eachCell((cell) => {
        cell.alignment = { vertical: 'top', wrapText: true };
        cell.border = {
          top: { style: 'thin', color: { argb: 'FFE4E6EE' } },
          left: { style: 'thin', color: { argb: 'FFE4E6EE' } },
          bottom: { style: 'thin', color: { argb: 'FFE4E6EE' } },
          right: { style: 'thin', color: { argb: 'FFE4E6EE' } },
        };
      });
    });

    // Column widths
    const widths = isLeader
      ? [12, 12, 22, 32, 32, 32, 25, 22, 22, 22, 40, 22]
      : [12, 12, 22, 32, 25, 22, 22, 22, 40, 22];
    widths.forEach((w, i) => (ws.getColumn(i + 1).width = w));
  }

  return wb;
}

export async function streamExcel(req, res) {
  const { team_id } = req.query;
  if (!team_id) return res.status(400).json({ error: 'team_id required' });
  // Determine caller role
  const roleRes = await pool.query(
    'SELECT role FROM team_members WHERE team_id = $1 AND user_id = $2',
    [team_id, req.user.id]
  );
  if (!roleRes.rowCount) return res.status(403).json({ error: 'Not a member' });
  const role = roleRes.rows[0].role;

  let userIds = null;
  if (role === 'member') {
    userIds = [req.user.id];
  } else if (req.query.user_ids) {
    userIds = String(req.query.user_ids)
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
  }

  const filters = {
    project: req.query.project,
    date: req.query.date,
    from: req.query.from,
    to: req.query.to,
    month: req.query.month,
    year: req.query.year,
  };

  const wb = await generateWorkbook({ teamId: team_id, userIds, filters });
  const teamName = (await pool.query('SELECT team_name FROM teams WHERE id = $1', [team_id])).rows[0]
    ?.team_name || 'team';
  const filename = `${teamName.replace(/[^a-z0-9]+/gi, '_')}_report_${Date.now()}.xlsx`;
  res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
  res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
  await wb.xlsx.write(res);
  res.end();
}
