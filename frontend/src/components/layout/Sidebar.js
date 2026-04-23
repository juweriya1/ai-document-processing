import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import './Sidebar.css';

const NAV_ITEMS = [
  {
    group: 'WORKSPACE',
    items: [
      { path: '/dashboard', label: 'Dashboard', icon: DashIcon },
      { path: '/upload', label: 'Upload', icon: UploadIcon },
      { path: '/processing', label: 'Processing', icon: ProcessIcon },
    ],
  },
  {
    group: 'OPERATIONS',
    items: [
      { path: '/validation', label: 'Validation', icon: ValidIcon },
      { path: '/review', label: 'Review', icon: ReviewIcon },
      { path: '/insights', label: 'Insights', icon: InsightIcon },
    ],
  },
  {
    group: 'SYSTEM',
    items: [
      { path: '/settings', label: 'Settings', icon: SettingsIcon },
    ],
  },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <aside className="sidebar">
      {/* Logo */}
      <div className="sidebar-logo">
        <div className="logo-mark">
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <rect width="22" height="22" rx="6" fill="var(--accent-primary)" />
            <path d="M6 7h10M6 11h7M6 15h5" stroke="#080c18" strokeWidth="2" strokeLinecap="round" />
            <circle cx="16" cy="15" r="2.5" fill="#080c18" />
          </svg>
        </div>
        <div className="logo-text">
          <span className="logo-name">Docura</span>
          <span className="logo-tag">AI Platform</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((group) => (
          <div key={group.group} className="nav-group">
            <span className="nav-group-label section-title">{group.group}</span>
            {group.items.map(({ path, label, icon: Icon }) => (
              <NavLink
                key={path}
                to={path}
                className={({ isActive }) =>
                  `nav-item ${isActive ? 'nav-item--active' : ''}`
                }
              >
                <span className="nav-item-icon">
                  <Icon size={16} />
                </span>
                <span className="nav-item-label">{label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* System status */}
      <div className="sidebar-status">
        <div className="status-row">
          <span className="pulse-dot active" />
          <span className="status-text">All systems operational</span>
        </div>
        <div className="status-row">
          <span className="pulse-dot success" />
          <span className="status-text">API connected</span>
        </div>
      </div>

      {/* User profile */}
      <div className="sidebar-user">
        <div className="user-avatar">
          {user?.name?.[0]?.toUpperCase() || 'U'}
        </div>
        <div className="user-info">
          <span className="user-name">{user?.name || 'User'}</span>
          <span className="user-email">{user?.email || ''}</span>
        </div>
        <button
          className="logout-btn"
          onClick={handleLogout}
          title="Sign out"
          aria-label="Sign out"
        >
          <LogoutIcon size={15} />
        </button>
      </div>
    </aside>
  );
}

/* ─────── Icon Components ─────── */
function DashIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <rect x="1.5" y="1.5" width="5" height="5" rx="1" />
      <rect x="9.5" y="1.5" width="5" height="5" rx="1" />
      <rect x="1.5" y="9.5" width="5" height="5" rx="1" />
      <rect x="9.5" y="9.5" width="5" height="5" rx="1" />
    </svg>
  );
}

function UploadIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M8 10V3M5 6l3-3 3 3" />
      <path d="M2 11v1.5A1.5 1.5 0 003.5 14h9a1.5 1.5 0 001.5-1.5V11" />
    </svg>
  );
}

function ProcessIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <circle cx="8" cy="8" r="6" />
      <path d="M8 5v3l2 2" />
    </svg>
  );
}

function ValidIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M3 8l3 3 7-7" />
      <rect x="1.5" y="1.5" width="13" height="13" rx="2" />
    </svg>
  );
}

function ReviewIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M2 4h12M2 8h8M2 12h5" />
      <circle cx="13" cy="12" r="2.5" />
      <path d="M11.5 10.5L10 9" />
    </svg>
  );
}

function InsightIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M2 12l3.5-4 3 2.5 3-5.5L14 7" />
    </svg>
  );
}

function SettingsIcon({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <circle cx="8" cy="8" r="2.5" />
      <path d="M8 1.5v1M8 13.5v1M1.5 8h1M13.5 8h1M3.05 3.05l.7.7M12.25 12.25l.7.7M3.05 12.95l.7-.7M12.25 3.75l.7-.7" />
    </svg>
  );
}

function LogoutIcon({ size = 15 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 15 15" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M10 7.5H3M6 5l-3 2.5L6 10" />
      <path d="M7 3h4.5A1.5 1.5 0 0113 4.5v6A1.5 1.5 0 0111.5 12H7" />
    </svg>
  );
}
