import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../store/authStore.js';
import { useToast } from '../hooks/useToast.js';
import './AuthPage.css';

export default function AuthPage() {
  const [mode, setMode] = useState('signin');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const auth = useAuth();
  const nav = useNavigate();
  const toast = useToast();

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      let user;
      if (mode === 'signup') user = await auth.signup(username, email, password);
      else user = await auth.signin(email, password);
      toast(`Welcome, ${user.username || user.email}`, 'success');
      nav(user.profile_completed ? '/teams' : '/profile-setup', { replace: true });
    } catch (err) {
      toast(err.response?.data?.error || err.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-wrap">
      <div className="auth-hero">
        <img src="/team-photo.svg" alt="" className="auth-hero-img" />
        <div className="auth-hero-tagline">
          <div className="auth-hero-brand">Team Report</div>
          <div className="auth-hero-title">AI-powered daily reporting for teams.</div>
        </div>
      </div>

      <div className="auth-form-side">
        <form onSubmit={submit} className="auth-form-card">
          <h2 className="auth-form-title">
            {mode === 'signin' ? 'Sign in' : 'Create your account'}
          </h2>
          <p className="auth-form-sub">
            {mode === 'signin' ? 'Welcome back — pick up where you left off.' : 'Get started in under a minute.'}
          </p>

          {mode === 'signup' && (
            <div className="field">
              <label>Username</label>
              <input className="input" required autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Your name" />
            </div>
          )}
          <div className="field">
            <label>Email</label>
            <input className="input" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" />
          </div>
          <div className="field">
            <label>Password</label>
            <input className="input" type="password" required minLength={6} autoComplete={mode === 'signin' ? 'current-password' : 'new-password'} value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
          </div>

          <button className="btn btn-primary" type="submit" disabled={busy} style={{ width: '100%' }}>
            {busy ? <span className="spinner" /> : mode === 'signin' ? 'Sign in' : 'Create account'}
          </button>

          <p className="auth-toggle">
            {mode === 'signin' ? "Don't have an account?" : 'Already have an account?'}{' '}
            <a href="#" onClick={(e) => { e.preventDefault(); setMode(mode === 'signin' ? 'signup' : 'signin'); }}>
              {mode === 'signin' ? 'Sign up' : 'Sign in'}
            </a>
          </p>
        </form>
      </div>
    </div>
  );
}
