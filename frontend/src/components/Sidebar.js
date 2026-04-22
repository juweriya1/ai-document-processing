import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Sidebar.css';

/* ─ SVG Icon Components ─ */
const IconDashboard = () => (
  <svg className="sidebar__nav-icon" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect x="2" y="2" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
    <rect x="11" y="2" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
    <rect x="2" y="11" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
    <rect x="11" y="11" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
  </svg>
);

const IconUpload = () => (
  <svg className="sidebar__nav-icon" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M10 13V4M10 4L7 7M10 4L13 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M3 13v2a2 2 0 002 2h10a2 2 0 002-2v-2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);

const IconProcessing = () => (
  <svg className="sidebar__nav-icon" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="10" cy="10" r="7.5" stroke="currentColor" strokeWidth="1.5"/>
    <path d="M10 6v4l3 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

const IconValidation = () => (
  <svg className="sidebar__nav-icon" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M10 2l1.8 5.5H18l-4.9 3.6 1.9 5.6L10 13.3l-5 3.4 1.9-5.6L2 7.5h6.2L10 2z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
  </svg>
);

const IconReview = () => (
  <svg className="sidebar__nav-icon" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M10 4C6 4 2.7 7.6 2 10c.7 2.4 4 6 8 6s7.3-3.6 8-6c-.7-2.4-4-6-8-6z" stroke="currentColor" strokeWidth="1.5"/>
    <circle cx="10" cy="10" r="2.5" stroke="currentColor" strokeWidth="1.5"/>
  </svg>
);

const IconInsights = () => (
  <svg className="sidebar__nav-icon" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M2 14l4-4 3 3 4-5 5 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M2 17h16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);

const IconAdmin = () => (
  <svg className="sidebar__nav-icon" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M10 12a3 3 0 100-6 3 3 0 000 6z" stroke="currentColor" strokeWidth="1.5"/>
    <path d="M17.3 10a7.4 7.4 0 00-.1-1.2l1.8-1.4-1.7-3-2.2.9a7.3 7.3 0 00-2.1-1.2l-.3-2.4h-3.4l-.3 2.4a7.3 7.3 0 00-2.1 1.2L4.7 4.4l-1.7 3 1.8 1.4a7.4 7.4 0 000 2.4L3 12.6l1.7 3 2.2-.9a7.3 7.3 0 002.1 1.2l.3 2.4h3.4l.3-2.4a7.3 7.3 0 002.1-1.2l2.2.9 1.7-3-1.7-1.6z" stroke="currentColor" strokeWidth="1.5"/>
  </svg>
);

const IconLogout = () => (
  <svg width="14" height="14" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M13 7l3 3-3 3M16 10H7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M10 3H5a2 2 0 00-2 2v10a2 2 0 002 2h5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
  </svg>
);

const LogoIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M12 2L3 7v10l9 5 9-5V7L12 2z" fill="rgba(255,255,255,0.9)" />
    <path d="M12 22V12M3 7l9 5 9-5" stroke="rgba(0,0,0,0.3)" strokeWidth="1" />
  </svg>
);

const roleLabel = (role) => {
  if (role === 'enterprise_user') return 'Enterprise User';
  if (role === 'reviewer') return 'Reviewer';
  if (role === 'admin') return 'Administrator';
  return role || 'User';
};

const getInitials = (name) => {
  if (!name) return '?';
  return name.split(' ').map(p => p[0]).join('').toUpperCase().slice(0, 2);
};

const NAV_ITEMS = [
  { to: '/dashboard',  label: 'Dashboard',   Icon: IconDashboard  },
  { to: '/upload',     label: 'Upload',       Icon: IconUpload     },
  { to: '/processing', label: 'Processing',   Icon: IconProcessing },
  { to: '/validation', label: 'Validation',   Icon: IconValidation },
  { to: '/review',     label: 'Review',       Icon: IconReview     },
  { to: '/insights',   label: 'Insights',     Icon: IconInsights   },
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
      {/* Brand */}
      <div className="sidebar__brand">
        <div className="sidebar__brand-logo">
          <LogoIcon />
        </div>
        <div>
          <div className="sidebar__brand-name">IDP</div>
          <div className="sidebar__brand-tag">Platform</div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="sidebar__nav">
        <div className="sidebar__section-label">Main</div>
        {NAV_ITEMS.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `sidebar__nav-item${isActive ? ' active' : ''}`
            }
          >
            <Icon />
            <span>{label}</span>
          </NavLink>
        ))}

        {user?.role === 'admin' && (
          <>
            <div className="sidebar__section-label" style={{ marginTop: 8 }}>Admin</div>
            <NavLink
              to="/admin"
              className={({ isActive }) =>
                `sidebar__nav-item${isActive ? ' active' : ''}`
              }
            >
              <IconAdmin />
              <span>Administration</span>
            </NavLink>
          </>
        )}
      </nav>

      {/* Footer */}
      <div className="sidebar__footer">
        {user && (
          <div className="sidebar__user">
            <div className="sidebar__avatar">{getInitials(user.name)}</div>
            <div className="sidebar__user-info">
              <div className="sidebar__user-name">{user.name || user.email}</div>
              <div className="sidebar__user-role">{roleLabel(user.role)}</div>
            </div>
          </div>
        )}
        <button className="sidebar__logout" onClick={handleLogout}>
          <IconLogout />
          <span>Sign out</span>
        </button>
      </div>
    </aside>
  );
}
