import Modal from './Modal.jsx';
import Avatar from './Avatar.jsx';

const SocialLink = ({ href, label }) => href ? (
  <a href={href} target="_blank" rel="noopener noreferrer" className="btn btn-secondary" style={{ padding: '8px 14px', fontSize: 13 }}>
    {label}
  </a>
) : null;

export default function ProfilePopup({ member, onClose }) {
  return (
    <Modal open={!!member} onClose={onClose} title={null} wide>
      {member && (
        <div>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            <Avatar user={member} size={72} />
            <div style={{ minWidth: 0 }}>
              <h3 style={{ margin: 0 }}>{member.username}</h3>
              <div style={{ color: 'var(--color-text-secondary)' }}>{member.role_title || 'Team member'}</div>
              <div style={{ marginTop: 6 }}>
                <span className={`badge-role ${member.role}`}>{member.role === 'leader' ? 'Team Leader' : 'Member'}</span>
              </div>
            </div>
          </div>
          <div style={{ marginTop: 18, color: 'var(--color-text-secondary)', fontSize: 14 }}>
            <div><strong style={{ color: 'var(--color-text-primary)' }}>Email:</strong> {member.email}</div>
            {member.bio && <p style={{ marginTop: 12, lineHeight: 1.6, color: 'var(--color-text-primary)' }}>{member.bio}</p>}
          </div>
          {member.skills && member.skills.length > 0 && (
            <div style={{ marginTop: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--color-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Skills</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {member.skills.map((s) => <span key={s} className="chip">{s}</span>)}
              </div>
            </div>
          )}
          <div style={{ marginTop: 18, display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            <SocialLink href={member.linkedin_url} label="LinkedIn ↗" />
            <SocialLink href={member.github_url} label="GitHub ↗" />
            <SocialLink href={member.kaggle_url} label="Kaggle ↗" />
            <SocialLink href={member.medium_url} label="Medium ↗" />
          </div>
        </div>
      )}
    </Modal>
  );
}
