import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { api } from '../../api/axiosClient.js';
import Avatar from '../../components/Avatar.jsx';
import ProfilePopup from '../../components/ProfilePopup.jsx';
import Modal from '../../components/Modal.jsx';
import { useToast } from '../../hooks/useToast.js';
import './TeamDetailsPage.css';

const IconEye = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
);
const IconTrash = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-2 14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"/></svg>
);
const IconCopy = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
);

export default function TeamDetailsPage() {
  const { team } = useOutletContext();
  const [members, setMembers] = useState(null);
  const [selected, setSelected] = useState(null);
  const [confirmRemove, setConfirmRemove] = useState(null);
  const toast = useToast();

  const load = () => api.get(`/teams/${team.id}/members`).then(({ data }) => setMembers(data));
  useEffect(() => { if (team?.id) load(); /* eslint-disable-next-line */ }, [team?.id]);

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(team.team_code);
      toast('Team code copied — share it with new members', 'success');
    } catch { toast('Copy failed', 'error'); }
  };

  const remove = async (userId) => {
    try {
      await api.delete(`/teams/${team.id}/members/${userId}`);
      toast('Member removed', 'success');
      setConfirmRemove(null);
      await load();
    } catch (e) { toast(e.response?.data?.error || e.message, 'error'); }
  };

  const leader = members?.find((m) => m.role === 'leader');
  const isLeader = team?.role === 'leader';

  return (
    <div>
      {/* Team info card */}
      <div className="details-summary card">
        <div className="ds-block">
          <div className="ds-label">Team name</div>
          <div className="ds-value">{team?.team_name || '—'}</div>
        </div>
        <div className="ds-block">
          <div className="ds-label">Team code</div>
          <div className="ds-value ds-code">
            <span>{team?.team_code}</span>
            <button className="btn btn-ghost ds-copy" onClick={copyCode} title="Copy code"><IconCopy /></button>
          </div>
        </div>
        <div className="ds-block">
          <div className="ds-label">Leader</div>
          <div className="ds-value">{leader?.username || '—'}</div>
        </div>
        <div className="ds-block">
          <div className="ds-label">Members</div>
          <div className="ds-value">{members?.length ?? '—'}</div>
        </div>
        <div className="ds-invite">
          <button className="btn btn-primary" onClick={copyCode}>
            <IconCopy /> Invite — copy team code
          </button>
        </div>
      </div>

      {/* Members header */}
      <div className="members-header">
        <h3 style={{ margin: 0 }}>Team roster</h3>
        <div style={{ color: 'var(--color-text-secondary)', fontSize: 13 }}>
          {members?.length ?? '—'} {members?.length === 1 ? 'person' : 'people'}
          {isLeader && ' · click a row to view full profile'}
        </div>
      </div>

      {/* Vertical member list */}
      {members === null && (
        <div className="member-list">
          {[0,1,2].map((i) => <div key={i} className="skeleton" style={{ height: 68 }} />)}
        </div>
      )}
      {members && (
        <div className="member-list">
          {members.map((m) => (
            <div key={m.id} className="member-row card" onClick={() => setSelected(m)}>
              <Avatar user={m} size={44} />
              <div className="member-row-main">
                <div className="member-row-name">
                  {m.username}
                  <span className={`badge-role ${m.role}`} style={{ marginLeft: 10 }}>
                    {m.role === 'leader' ? 'Leader' : 'Member'}
                  </span>
                </div>
                <div className="member-row-sub">
                  {m.role_title ? <span>{m.role_title} · </span> : null}
                  <span>{m.email}</span>
                </div>
              </div>
              <div className="member-row-actions">
                <button className="btn btn-ghost member-action-btn" onClick={(e) => { e.stopPropagation(); setSelected(m); }} title="View profile">
                  <IconEye /> <span className="member-action-label">View profile</span>
                </button>
                {isLeader && m.role !== 'leader' && (
                  <button className="btn btn-ghost member-action-btn danger" onClick={(e) => { e.stopPropagation(); setConfirmRemove(m); }} title="Remove member">
                    <IconTrash /> <span className="member-action-label">Remove</span>
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <ProfilePopup member={selected} onClose={() => setSelected(null)} />

      <Modal
        open={!!confirmRemove}
        onClose={() => setConfirmRemove(null)}
        title="Remove member?"
        footer={<>
          <button className="btn btn-ghost" onClick={() => setConfirmRemove(null)}>Cancel</button>
          <button className="btn btn-danger" onClick={() => remove(confirmRemove.id)}>Remove</button>
        </>}
      >
        <p style={{ margin: 0, color: 'var(--color-text-secondary)', lineHeight: 1.6 }}>
          Are you sure you want to remove <strong>{confirmRemove?.username}</strong> from the team?
          Their existing reports will remain in the archive, but they will lose access to this workspace.
        </p>
      </Modal>
    </div>
  );
}
