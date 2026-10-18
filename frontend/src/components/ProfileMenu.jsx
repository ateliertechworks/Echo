import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../store/authStore.js';
import { api } from '../api/axiosClient.js';
import Avatar from './Avatar.jsx';
import Modal from './Modal.jsx';

const SocialLink = ({ href, label }) => href ? (
  <a href={href} target="_blank" rel="noopener noreferrer" className="btn btn-secondary" style={{ padding: '8px 14px', fontSize: 13 }}>
    {label}
  </a>
) : null;

export default function ProfileMenu() {
  const { user, signout } = useAuth();
  const [open, setOpen] = useState(false);
  const [profile, setProfile] = useState(null);
  const nav = useNavigate();
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    api.get('/profile').then(({ data }) => setProfile(data)).catch(() => {});
    const onDown = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  if (!user) return null;

  const details = profile || user;

  return (
    <div className="profile-menu" ref={ref}>
      <button className="profile-menu-btn" onClick={() => setOpen(!open)} aria-label="Profile">
        <Avatar user={details} size={38} />
      </button>
      {open && (
        <div className="profile-menu-popup">
          <div className="profile-menu-head">
            <Avatar user={details} size={56} />
            <div style={{ minWidth: 0 }}>
              <div className="profile-menu-name">{details.username}</div>
              <div className="profile-menu-email">{details.email}</div>
              {details.role_title && (
                <div className="profile-menu-role">{details.role_title}</div>
              )}
            </div>
          </div>

          <div className="profile-menu-section">
            <div className="profile-menu-label">Contact & socials</div>
            <div className="profile-menu-links">
              <SocialLink href={details.linkedin_url} label="LinkedIn ↗" />
              <SocialLink href={details.github_url} label="GitHub ↗" />
              <SocialLink href={details.kaggle_url} label="Kaggle ↗" />
              <SocialLink href={details.medium_url} label="Medium ↗" />
              {!details.linkedin_url && !details.github_url && !details.kaggle_url && !details.medium_url && (
                <div style={{ color: 'var(--color-text-secondary)', fontSize: 13 }}>None added yet.</div>
              )}
            </div>
          </div>

          {details.skills?.length > 0 && (
            <div className="profile-menu-section">
              <div className="profile-menu-label">Skills</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {details.skills.map((s) => <span key={s} className="chip">{s}</span>)}
              </div>
            </div>
          )}

          <div className="profile-menu-actions">
            <button className="btn btn-primary" style={{ flex: 1 }} onClick={() => { setOpen(false); nav('/profile-setup'); }}>
              Edit profile
            </button>
            <button className="btn btn-secondary" onClick={() => { signout(); nav('/auth'); }}>
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
