import { useEffect, useMemo, useState } from 'react';
import { Outlet, useParams, useNavigate } from 'react-router-dom';
import AppShell from '../../components/AppShell.jsx';
import { api } from '../../api/axiosClient.js';
import { useToast } from '../../hooks/useToast.js';
import './TeamWorkspaceLayout.css';

const IconChat = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
);
const IconArchive = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="21 8 21 21 3 21 3 8"/><rect x="1" y="3" width="22" height="5"/><line x1="10" y1="12" x2="14" y2="12"/></svg>
);
const IconUsers = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
);

export default function TeamWorkspaceLayout() {
  const { teamId } = useParams();
  const [team, setTeam] = useState(null);
  const [error, setError] = useState(null);
  const toast = useToast();
  const nav = useNavigate();

  useEffect(() => {
    api.get(`/teams/${teamId}`).then(({ data }) => setTeam(data)).catch((e) => setError(e));
  }, [teamId]);

  const navItems = useMemo(() => ([
    { to: `/teams/${teamId}`, label: "Today's Report", icon: <IconChat />, end: true },
    { to: `/teams/${teamId}/past`, label: 'Past Reports', icon: <IconArchive /> },
    { to: `/teams/${teamId}/details`, label: 'Team Details', icon: <IconUsers /> },
  ]), [teamId]);

  const footerAction = { label: 'Back to Team Space', onClick: () => nav('/teams') };

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(team.team_code);
      toast('Team code copied', 'success');
    } catch { toast('Copy failed', 'error'); }
  };

  if (error) {
    return (
      <AppShell title="Team" navItems={navItems} footerAction={footerAction}>
        <div className="page">
          <div className="empty-state">
            Team not accessible.
            <div style={{ marginTop: 10 }}><button className="btn btn-secondary" onClick={() => nav('/teams')}>Back</button></div>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell title={team?.team_name || 'Team'} navItems={navItems} footerAction={footerAction}>
      <div className="page workspace">
        <div className="ws-hero card">
          <div className="ws-hero-main">
            <div className="subtitle" style={{ marginBottom: 0 }}>Team</div>
            <h2 style={{ margin: '2px 0 4px 0' }}>
              {team?.team_name || <span className="skeleton" style={{ display: 'inline-block', width: 200, height: 22 }} />}
            </h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              {team && <span className={`badge-role ${team.role}`}>{team.role === 'leader' ? 'Team Leader' : 'Member'}</span>}
              {team && (
                <button className="chip" onClick={copyCode} title="Copy code" style={{ cursor: 'pointer', fontFamily: 'ui-monospace, monospace' }}>
                  Code: {team.team_code} <span aria-hidden>📋</span>
                </button>
              )}
            </div>
          </div>
        </div>
        <div style={{ marginTop: 20 }}>
          <Outlet context={{ team }} />
        </div>
      </div>
    </AppShell>
  );
}
