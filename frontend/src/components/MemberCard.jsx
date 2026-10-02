import Avatar from './Avatar.jsx';

export default function MemberCard({ member, onClick, onRemove, canRemove }) {
  return (
    <div className="card member-card" onClick={onClick}>
      <div className="member-card-head">
        <Avatar user={member} size={48} />
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <div style={{ fontWeight: 700, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{member.username}</div>
            <span className={`badge-role ${member.role}`}>{member.role === 'leader' ? 'Leader' : 'Member'}</span>
          </div>
          <div style={{ fontSize: 13, color: 'var(--color-text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {member.role_title || member.email}
          </div>
        </div>
      </div>
      {member.bio && <p className="member-bio">{member.bio}</p>}
      {member.skills && member.skills.length > 0 && (
        <div className="member-skills">
          {member.skills.slice(0, 4).map((s) => <span key={s} className="chip">{s}</span>)}
          {member.skills.length > 4 && <span className="chip" style={{ background: '#eee', color: 'var(--color-text-secondary)' }}>+{member.skills.length - 4}</span>}
        </div>
      )}
      {canRemove && member.role !== 'leader' && (
        <button className="btn btn-ghost member-remove" onClick={(e) => { e.stopPropagation(); onRemove?.(); }} title="Remove member">
          Remove
        </button>
      )}
    </div>
  );
}
