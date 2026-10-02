import { useEffect, useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { api, API_BASE } from '../../api/axiosClient.js';
import { useToast } from '../../hooks/useToast.js';
import './PastReportsPage.css';

const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
const CURRENT_YEAR = new Date().getFullYear();
const YEARS = Array.from({ length: 8 }, (_, i) => CURRENT_YEAR - i);

export default function PastReportsPage() {
  const { team } = useOutletContext();
  const [members, setMembers] = useState([]);
  const [period, setPeriod] = useState('month'); // month|year|single|range
  const [month, setMonth] = useState(new Date().getMonth() + 1);
  const [year, setYear] = useState(CURRENT_YEAR);
  const [singleDate, setSingleDate] = useState(new Date().toISOString().slice(0, 10));
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [memberSel, setMemberSel] = useState('all'); // 'all' or user_id
  const [reports, setReports] = useState(null);
  const [busy, setBusy] = useState(false);
  const [busyExport, setBusyExport] = useState(false);
  const toast = useToast();

  useEffect(() => {
    if (!team) return;
    api.get(`/teams/${team.id}/members`).then(({ data }) => {
      setMembers(data);
      // If member (not leader), lock selection to themselves
      if (team.role !== 'leader') {
        const me = data.find((m) => m.role === 'member' || m.role === 'leader'); // fallback
      }
    });
  }, [team?.id]);

  const buildFilters = () => {
    const f = {};
    if (period === 'month') { f.month = month; f.year = year; }
    else if (period === 'year') { f.year = year; }
    else if (period === 'single') { f.date = singleDate; }
    else if (period === 'range') {
      if (fromDate) f.from = fromDate;
      if (toDate) f.to = toDate;
    }
    if (team.role === 'leader' && memberSel !== 'all') f.user_id = memberSel;
    return f;
  };

  const applyFilters = async () => {
    if (!team) return;
    setBusy(true);
    setReports(null);
    try {
      const params = { team_id: team.id, ...buildFilters() };
      const { data } = await api.get('/reports', { params });
      setReports(data);
    } catch (e) {
      toast(e.response?.data?.error || e.message, 'error');
      setReports([]);
    } finally { setBusy(false); }
  };

  useEffect(() => { if (team) applyFilters(); /* eslint-disable-next-line */ }, [team?.id]);

  const doExport = async () => {
    setBusyExport(true);
    try {
      const params = new URLSearchParams();
      params.set('team_id', team.id);
      const f = buildFilters();
      for (const [k, v] of Object.entries(f)) {
        if (v == null || v === '') continue;
        if (k === 'user_id') params.set('user_ids', v);
        else params.set(k, v);
      }
      const token = localStorage.getItem('tr_token');
      const res = await fetch(`${API_BASE}/api/export/excel?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) {
        const text = await res.text().catch(() => '');
        throw new Error(text || 'Export failed');
      }
      const blob = await res.blob();
      const disp = res.headers.get('content-disposition') || '';
      const match = disp.match(/filename="?([^";]+)"?/);
      const filename = match?.[1] || `${team.team_name || 'team'}_report.xlsx`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = filename; a.click();
      URL.revokeObjectURL(url);
      toast('Excel downloaded', 'success');
    } catch (e) { toast(e.message, 'error'); }
    finally { setBusyExport(false); }
  };

  if (!team) return null;
  const isLeader = team.role === 'leader';

  return (
    <div>
      <div className="filter-card card">
        <div className="filter-grid">
          {/* Period */}
          <div className="field">
            <label>Period</label>
            <select className="select" value={period} onChange={(e) => setPeriod(e.target.value)}>
              <option value="month">Month</option>
              <option value="year">Year</option>
              <option value="single">Single Date</option>
              <option value="range">Custom Range</option>
            </select>
          </div>

          {/* Dynamic period control */}
          {period === 'month' && (
            <>
              <div className="field">
                <label>Month</label>
                <select className="select" value={month} onChange={(e) => setMonth(Number(e.target.value))}>
                  {MONTHS.map((m, i) => <option key={i} value={i + 1}>{m}</option>)}
                </select>
              </div>
              <div className="field">
                <label>Year</label>
                <select className="select" value={year} onChange={(e) => setYear(Number(e.target.value))}>
                  {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
                </select>
              </div>
            </>
          )}
          {period === 'year' && (
            <div className="field">
              <label>Year</label>
              <select className="select" value={year} onChange={(e) => setYear(Number(e.target.value))}>
                {YEARS.map((y) => <option key={y} value={y}>{y}</option>)}
              </select>
            </div>
          )}
          {period === 'single' && (
            <div className="field">
              <label>Date</label>
              <input className="input" type="date" value={singleDate} onChange={(e) => setSingleDate(e.target.value)} />
            </div>
          )}
          {period === 'range' && (
            <>
              <div className="field">
                <label>From date</label>
                <input className="input" type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
              </div>
              <div className="field">
                <label>To date</label>
                <input className="input" type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
              </div>
            </>
          )}

          {/* Member */}
          <div className="field">
            <label>Member</label>
            {isLeader ? (
              <select className="select" value={memberSel} onChange={(e) => setMemberSel(e.target.value)}>
                <option value="all">All members</option>
                {members.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.username} — {m.role === 'leader' ? 'Leader' : 'Member'}
                  </option>
                ))}
              </select>
            ) : (
              <div className="input" style={{ display: 'flex', alignItems: 'center', background: '#F7F8FA' }}>
                Only your reports
              </div>
            )}
          </div>
        </div>

        <div className="filter-actions">
          <button className="btn btn-secondary" onClick={applyFilters} disabled={busy}>
            {busy ? <span className="spinner" /> : '🔍 Apply filters'}
          </button>
          <button className="btn btn-primary" onClick={doExport} disabled={busyExport}>
            {busyExport ? <span className="spinner" /> : '📤 Export Excel'}
          </button>
        </div>
      </div>

      {/* Results preview */}
      <div style={{ marginTop: 18 }}>
        <div className="results-header">
          <div>
            <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', fontWeight: 700, letterSpacing: '0.05em', textTransform: 'uppercase' }}>Matches</div>
            <div style={{ fontSize: 20, fontWeight: 700 }}>{reports === null ? '…' : `${reports.length} report${reports.length === 1 ? '' : 's'}`}</div>
          </div>
        </div>

        {reports === null && (
          <div className="reports-list">
            {[0,1,2].map((i) => <div key={i} className="skeleton" style={{ height: 90 }} />)}
          </div>
        )}
        {reports && reports.length === 0 && (
          <div className="empty-state">
            <div style={{ fontSize: 40 }}>🗂️</div>
            <h3>No reports found</h3>
            <p>Try adjusting the filters, or submit today's report to get started.</p>
          </div>
        )}
        {reports && reports.length > 0 && (
          <div className="reports-list">
            {reports.map((r) => <ReportRow key={r.id} r={r} showAuthor={isLeader} />)}
          </div>
        )}
      </div>
    </div>
  );
}

function ReportRow({ r, showAuthor }) {
  const [open, setOpen] = useState(false);
  const date = new Date(r.report_date).toLocaleDateString(undefined, { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' });
  return (
    <div className="card report-row">
      <div className="report-row-head" onClick={() => setOpen(!open)}>
        <div>
          <div className="report-row-date">{date}</div>
          <div className="report-row-project">{r.project_name || 'Untitled project'}</div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {showAuthor && <span className="chip" style={{ background: 'var(--color-accent-light)' }}>{r.username}</span>}
          <span aria-hidden style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }}>⌄</span>
        </div>
      </div>
      {open && (
        <div className="report-row-body">
          {r.leader_work && <Row label="Leader work" value={r.leader_work} />}
          {r.team_progress && <Row label="Team progress" value={r.team_progress} />}
          <Row label="Work done" value={r.leader_work ? null : r.work_done} />
          <Row label="Outcome" value={r.outcome} />
          <Row label="Blockers" value={r.blockers} />
          <Row label="Pending" value={r.pending_work} />
          <Row label="Next plan" value={r.next_plan} />
          {r.chatbot_summary && (
            <details style={{ marginTop: 10 }}>
              <summary style={{ cursor: 'pointer', color: 'var(--color-text-secondary)', fontSize: 13 }}>View narrative summary</summary>
              <pre style={{ whiteSpace: 'pre-wrap', background: '#F7F8FA', padding: 12, borderRadius: 8, marginTop: 8, fontFamily: 'inherit', fontSize: 13 }}>{r.chatbot_summary}</pre>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

function Row({ label, value }) {
  if (!value) return null;
  return (
    <div className="rr-row">
      <div className="rr-label">{label}</div>
      <div className="rr-value">{value}</div>
    </div>
  );
}
