import { useNavigate } from 'react-router-dom';

export default function TeamCard({ team }) {
  const nav = useNavigate();
  const isLeader = team.role === 'leader';
  const initials = (team.team_name || '?').split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase()).join('');
  return (
    <div className="card team-card" onClick={() => nav(`/teams/${team.id}`)}>
      <div className="team-card-header">
        <div className="team-avatar" aria-hidden>{initials}</div>
        <span className={`badge-role ${team.role}`}>{isLeader ? 'Leader' : 'Member'}</span>
      </div>
      <h3 className="team-card-title">{team.team_name}</h3>
      {team.description && <p className="team-card-desc">{team.description}</p>}
      <div className="team-card-meta">
        <div>
          <div className="team-card-meta-label">Code</div>
          <div className="team-card-meta-value">{team.team_code}</div>
        </div>
        <div>
          <div className="team-card-meta-label">Members</div>
          <div className="team-card-meta-value">{team.member_count ?? '—'}</div>
        </div>
      </div>
    </div>
  );
}
