import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/axiosClient.js';
import { useAuth } from '../store/authStore.js';
import { useToast } from '../hooks/useToast.js';
import './ProfileSetupPage.css';

export default function ProfileSetupPage() {
  const { user, updateUser } = useAuth();
  const nav = useNavigate();
  const toast = useToast();
  const [form, setForm] = useState({
    username: user?.username || '',
    email: user?.email || '',
    linkedin_url: '',
    github_url: '',
    kaggle_url: '',
    medium_url: '',
    profile_photo: '',
    role_title: '',
    bio: '',
    skills: [],
  });
  const [skillDraft, setSkillDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api.get('/profile').then(({ data }) => {
      setForm((f) => ({ ...f, ...data, skills: data.skills || [] }));
      setLoaded(true);
    }).catch(() => setLoaded(true));
  }, []);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const addSkill = () => {
    const v = skillDraft.trim();
    if (!v) return;
    if (form.skills.includes(v)) { setSkillDraft(''); return; }
    setForm({ ...form, skills: [...form.skills, v] });
    setSkillDraft('');
  };

  const removeSkill = (s) => setForm({ ...form, skills: form.skills.filter((x) => x !== s) });

  const onPhotoUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) { toast('Photo must be under 2MB', 'error'); return; }
    const reader = new FileReader();
    reader.onload = () => setForm((f) => ({ ...f, profile_photo: reader.result }));
    reader.readAsDataURL(file);
  };

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.put('/profile', form);
      updateUser({ ...data, profile_completed: true });
      toast('Profile saved', 'success');
      nav('/teams', { replace: true });
    } catch (err) {
      toast(err.response?.data?.error || err.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="profile-setup-wrap">
      <img src="/team-photo.svg" alt="" className="profile-bg" />
      <div className="profile-overlay" />
      <form onSubmit={submit} className="profile-card">
        <h2 style={{ margin: 0 }}>Set up your profile</h2>
        <p style={{ color: 'var(--color-text-secondary)', marginTop: 6 }}>
          Help teammates get to know you. You can update this anytime.
        </p>

        <div className="profile-photo-row">
          <div className="profile-photo-preview">
            {form.profile_photo
              ? <img src={form.profile_photo} alt="" />
              : <span>{(form.username || '?').slice(0,1).toUpperCase()}</span>}
          </div>
          <div>
            <label className="btn btn-secondary" style={{ cursor: 'pointer' }}>
              Upload photo
              <input type="file" accept="image/*" onChange={onPhotoUpload} style={{ display: 'none' }} />
            </label>
            <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginTop: 6 }}>PNG or JPG, max 2MB</div>
          </div>
        </div>

        <div className="profile-grid">
          <div className="field">
            <label>Username</label>
            <input className="input" value={form.username} onChange={set('username')} required />
          </div>
          <div className="field">
            <label>Email</label>
            <input className="input" type="email" value={form.email} onChange={set('email')} required />
          </div>
          <div className="field">
            <label>Role / Title</label>
            <input className="input" placeholder="e.g. Data Engineer" value={form.role_title || ''} onChange={set('role_title')} />
          </div>
          <div className="field">
            <label>LinkedIn URL</label>
            <input className="input" placeholder="https://linkedin.com/in/..." value={form.linkedin_url || ''} onChange={set('linkedin_url')} />
          </div>
          <div className="field">
            <label>GitHub URL</label>
            <input className="input" placeholder="https://github.com/..." value={form.github_url || ''} onChange={set('github_url')} />
          </div>
          <div className="field">
            <label>Kaggle URL</label>
            <input className="input" placeholder="https://kaggle.com/..." value={form.kaggle_url || ''} onChange={set('kaggle_url')} />
          </div>
          <div className="field">
            <label>Medium URL</label>
            <input className="input" placeholder="https://medium.com/@..." value={form.medium_url || ''} onChange={set('medium_url')} />
          </div>
        </div>

        <div className="field">
          <label>Short bio (optional)</label>
          <textarea className="textarea" value={form.bio || ''} onChange={set('bio')} placeholder="A sentence or two about your focus areas." />
        </div>

        <div className="field">
          <label>Skills</label>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {form.skills.map((s) => (
              <span key={s} className="chip" style={{ padding: '6px 10px' }}>
                {s}
                <button type="button" onClick={() => removeSkill(s)} style={{ color: 'var(--color-primary)', fontWeight: 700 }}>×</button>
              </span>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <input className="input" placeholder="Add a skill and press Enter"
              value={skillDraft}
              onChange={(e) => setSkillDraft(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addSkill(); } }} />
            <button type="button" className="btn btn-secondary" onClick={addSkill}>Add</button>
          </div>
        </div>

        <button className="btn btn-primary" type="submit" disabled={busy || !loaded} style={{ width: '100%', marginTop: 8 }}>
          {busy ? <span className="spinner" /> : 'Save and continue'}
        </button>
      </form>
    </div>
  );
}
