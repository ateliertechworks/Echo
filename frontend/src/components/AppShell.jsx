import { useEffect, useState } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import ProfileMenu from './ProfileMenu.jsx';

const IconMenu = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
);
const IconBack = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
);

export default function AppShell({ title, navItems = [], footerAction, children }) {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const nav = useNavigate();
  useEffect(() => setOpen(false), [location.pathname]);

  return (
    <div className="app-shell">
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="brand" onClick={() => nav('/teams')} style={{ cursor: 'pointer' }}>
          <div className="brand-logo">📊</div>
          <div>Team Report</div>
        </div>
        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end}>
              {item.icon && <span className="sidebar-nav-icon">{item.icon}</span>}
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="spacer" />
        {footerAction && (
          <button className="sidebar-footer-btn" onClick={footerAction.onClick}>
            <IconBack /> {footerAction.label}
          </button>
        )}
      </aside>
      <div className={`sidebar-backdrop ${open ? 'open' : ''}`} onClick={() => setOpen(false)} />
      <div className="main">
        <div className="topbar">
          <button className="menu-toggle" onClick={() => setOpen(!open)} aria-label="Menu"><IconMenu /></button>
          <h1>{title}</h1>
          <div className="spacer" />
          <ProfileMenu />
        </div>
        {children}
      </div>
    </div>
  );
}
