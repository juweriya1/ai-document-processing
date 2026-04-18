import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Sidebar.css';

/* ── SVG Icon set ─────────────────────────────────────── */
const Icon = ({ d, ...p }) => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...p}>
    <path d={d} />
  </svg>
);

const Icons = {
  dashboard: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
      <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
    </svg>
  ),
  upload: () => <Icon d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" />,
  processing: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3"/><path d="M19.07 4.93a10 10 0 010 14.14M4.93 4.93a10 10 0 000 14.14"/>
    </svg>
  ),
  validation: () => <Icon d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />,
  review: () => <Icon d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8zM12 9a3 3 0 100 6 3 3 0 000-6z" />,
  insights: () => (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
    </svg>
  ),
  admin: () => <Icon d="M12 2a5 5 0 015 5v2a5 5 0 01-10 0V7a5 5 0 015-5zM4 20c0-4 3.6-7 8-7s8 3 8 7" />,
  logout: () => <Icon d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />,
};

const NAV_ITEMS = [
  { to: '/dashboard',  label: 'Dashboard',  icon: Icons.dashboard },
  { to: '/upload',     label: 'Upload',     icon: Icons.upload },
  { to: '/processing', label: 'Processing', icon: Icons.processing },
  { to: '/validation', label: 'Validation', icon: Icons.validation },
  { to: '/review',     label: 'Review',     icon: Icons.review },
  { to: '/insights',   label: 'Insights',   icon: Icons.insights },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const initial = (user?.name || 'U')[0].toUpperCase();
  const roleFmt = (user?.role || '').replace(/_/g, ' ');

  return (
    <nav className="sidebar">
      {/* Brand */}
      <div className="sidebar__brand">
        <div className="sidebar__logo">IDP</div>
        <div className="sidebar__brand-text">
          <span className="sidebar__brand-name">IntelliDoc</span>
          <span className="sidebar__brand-sub">Processing Platform</span>
        </div>
      </div>

      {/* Nav */}
      <div className="sidebar__section">
        <div className="sidebar__section-label">Navigation</div>
        {NAV_ITEMS.map(({ to, label, icon: IconComp }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `sidebar__item${isActive ? ' sidebar__item--active' : ''}`
            }
          >
            <span className="sidebar__item-icon"><IconComp /></span>
            <span className="sidebar__item-label">{label}</span>
          </NavLink>
        ))}

        {user?.role === 'admin' && (
          <NavLink
            to="/admin"
            className={({ isActive }) =>
              `sidebar__item${isActive ? ' sidebar__item--active' : ''}`
            }
          >
            <span className="sidebar__item-icon"><Icons.admin /></span>
            <span className="sidebar__item-label">Admin</span>
          </NavLink>
        )}
      </div>

      <div className="sidebar__spacer" />

      {/* Footer */}
      <div className="sidebar__footer">
        <div className="sidebar__user">
          <div className="sidebar__avatar">{initial}</div>
          <div className="sidebar__user-info">
            <div className="sidebar__user-name">{user?.name || 'User'}</div>
            <div className="sidebar__user-role">{roleFmt}</div>
          </div>
        </div>
        <button className="sidebar__logout" onClick={handleLogout}>
          <Icons.logout />
          Sign out
        </button>
      </div>
    </nav>
  );
}
