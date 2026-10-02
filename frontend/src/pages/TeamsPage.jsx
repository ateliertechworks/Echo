import { useEffect, useState } from 'react';
import AppShell from '../components/AppShell.jsx';
import Modal from '../components/Modal.jsx';
import TeamCard from '../components/TeamCard.jsx';
import { api } from '../api/axiosClient.js';
import { useToast } from '../hooks/useToast.js';
import './TeamsPage.css';

const IconTeams = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
);

const NAV = [{ to: '/teams', label: 'Teams', icon: <IconTeams />, end: true }];

export default function TeamsPage() {
  const [teams, setTeams] = useState(null);
  const [modal, setModal] = useState(null); // 'create' | 'join'
  const [teamName, setTeamName] = useState('');
  const [teamDesc, setTeamDesc] = useState('');
  const [joinCode, setJoinCode] = useState('');
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  const load = () => api.get('/teams').then(({ data }) => setTeams(data));
  useEffect(() => { load(); }, []);

  const create = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post('/teams', { team_name: teamName, description: teamDesc });
      toast('Team created', 'success');
      setModal(null); setTeamName(''); setTeamDesc('');
      await load();
    } catch (err) { toast(err.response?.data?.error || err.message, 'error'); }
    finally { setBusy(false); }
  };

  const join = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post('/teams/join', { team_code: joinCode.trim().toUpperCase() });
      toast('Joined team', 'success');
      setModal(null); setJoinCode('');
      await load();
    } catch (err) { toast(err.response?.data?.error || err.message, 'error'); }
    finally { setBusy(false); }
  };

  return (
    <AppShell title="Your Teams" navItems={NAV}>
      <div className="page">
        <div className="teams-header">
          <div>
            <h2>Your Teams</h2>
            <div className="subtitle">Create a new team or join one with a code.</div>
          </div>
          <div className="teams-actions">
            <button className="btn btn-secondary" onClick={() => setModal('join')}>Join team</button>
            <button className="btn btn-primary" onClick={() => setModal('create')}>+ Create team</button>
          </div>
        </div>

        {teams === null && (
          <div className="teams-grid">
            {[0,1,2].map((i) => <div key={i} className="skeleton" style={{ height: 180 }} />)}
          </div>
        )}

        {teams && teams.length === 0 && (
          <div className="empty-state">
            <div style={{ fontSize: 48 }}>🚀</div>
            <h3>No teams yet</h3>
            <p>Kick things off by creating a team or joining an existing one.</p>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'center', marginTop: 14, flexWrap: 'wrap' }}>
              <button className="btn btn-primary" onClick={() => setModal('create')}>+ Create team</button>
              <button className="btn btn-secondary" onClick={() => setModal('join')}>Join team</button>
            </div>
          </div>
        )}

        {teams && teams.length > 0 && (
          <div className="teams-grid">
            {teams.map((t) => <TeamCard key={t.id} team={t} />)}
          </div>
        )}
      </div>

      <Modal
        open={modal === 'create'} onClose={() => setModal(null)} title="Create a new team"
        footer={<>
          <button className="btn btn-ghost" type="button" onClick={() => setModal(null)}>Cancel</button>
          <button form="create-team-form" className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? <span className="spinner" /> : 'Create'}
          </button>
        </>}
      >
        <form id="create-team-form" onSubmit={create}>
          <div className="field">
            <label>Team name</label>
            <input className="input" required value={teamName} onChange={(e) => setTeamName(e.target.value)} placeholder="e.g. Data Insights" />
          </div>
          <div className="field">
            <label>Description (optional)</label>
            <textarea className="textarea" value={teamDesc} onChange={(e) => setTeamDesc(e.target.value)} placeholder="What does this team focus on?" />
          </div>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: 13 }}>
            You'll be added as the Team Leader. A shareable team code will be generated automatically.
          </p>
        </form>
      </Modal>

      <Modal
        open={modal === 'join'} onClose={() => setModal(null)} title="Join a team"
        footer={<>
          <button className="btn btn-ghost" type="button" onClick={() => setModal(null)}>Cancel</button>
          <button form="join-team-form" className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? <span className="spinner" /> : 'Join'}
          </button>
        </>}
      >
        <form id="join-team-form" onSubmit={join}>
          <div className="field">
            <label>Team code</label>
            <input className="input" required value={joinCode}
              onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
              placeholder="e.g. K7P3XM2N" style={{ letterSpacing: '0.2em', textTransform: 'uppercase' }} />
          </div>
          <p style={{ color: 'var(--color-text-secondary)', fontSize: 13 }}>
            Ask your team leader for the code. You'll join as a Member.
          </p>
        </form>
      </Modal>
    </AppShell>
  );
}
