import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './LoginPage.css';

const LogoIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
    <path d="M12 2L3 7v10l9 5 9-5V7L12 2z" fill="rgba(255,255,255,0.95)"/>
    <path d="M12 22V12M3 7l9 5 9-5" stroke="rgba(0,0,0,0.25)" strokeWidth="1"/>
  </svg>
);

const FeatureItem = ({ icon, title, desc, delay }) => (
  <div className="login__feature" style={{ animationDelay: `${delay}ms` }}>
    <div className="login__feature-icon">{icon}</div>
    <div className="login__feature-text">
      <strong>{title}</strong>
      <span>{desc}</span>
    </div>
  </div>
);

export default function LoginPage() {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [name, setName]         = useState('');
  const [role, setRole]         = useState('enterprise_user');
  const [error, setError]       = useState('');
  const [loading, setLoading]   = useState(false);
  const { loginAction, registerAction } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (isRegister) {
        await registerAction(email, password, name, role);
      } else {
        await loginAction(email, password);
      }
      navigate('/dashboard');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const toggle = () => { setIsRegister(!isRegister); setError(''); };

  return (
    <div className="login">
      {/* ── Left Branding Panel ── */}
      <div className="login__panel">
        <div className="login__brand">
          <div className="login__brand-logo"><LogoIcon /></div>
          <div className="login__brand-text">IDP Platform</div>
        </div>

        <div className="login__hero">
          <div className="login__hero-tag">
            <span className="login__hero-dot" />
            AI-Powered · Enterprise Ready
          </div>
          <h1 className="login__hero-title">
            Intelligent<br />
            <span>Document</span><br />
            Processing
          </h1>
          <p className="login__hero-desc">
            Extract structured data from unstructured documents with AI-grade
            accuracy. Built for enterprise workflows with human-in-the-loop review.
          </p>

          <div className="login__features">
            <FeatureItem
              delay={200}
              icon={<svg width="16" height="16" viewBox="0 0 20 20" fill="none"><path d="M10 2l2 5.5H18l-4.9 3.6 1.9 5.6L10 13.3l-5 3.4 1.9-5.6L2 7.5h6L10 2z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>}
              title="Vision Language Models"
              desc="State-of-the-art VLM extraction with confidence calibration"
            />
            <FeatureItem
              delay={260}
              icon={<svg width="16" height="16" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5"/><path d="M7 10l2 2 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>}
              title="Human-in-the-Loop Review"
              desc="Role-based validation and approval workflow"
            />
            <FeatureItem
              delay={320}
              icon={<svg width="16" height="16" viewBox="0 0 20 20" fill="none"><path d="M2 14l4-4 3 3 4-5 5 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>}
              title="Advanced Analytics"
              desc="Spend forecasting, anomaly detection & supplier risk scoring"
            />
          </div>
        </div>

        <div className="login__footer-note">
          Final Year Project · AI Document Processing System
        </div>
      </div>

      {/* ── Right Form Panel ── */}
      <div className="login__form-panel">
        <div className="login__form-card">
          <h2 className="login__form-title">
            {isRegister ? 'Create account' : 'Welcome back'}
          </h2>
          <p className="login__form-subtitle">
            {isRegister
              ? 'Register a new account to get started'
              : 'Sign in to your IDP Platform account'}
          </p>

          <form className="login__form" onSubmit={handleSubmit}>
            {isRegister && (
              <div className="login__field">
                <label className="form-label">Full Name</label>
                <div className="login__input-wrap">
                  <span className="login__input-icon">
                    <svg width="15" height="15" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="7" r="4" stroke="currentColor" strokeWidth="1.5"/><path d="M3 18c0-3.3 3.1-6 7-6s7 2.7 7 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                  </span>
                  <input
                    className="login__input"
                    type="text"
                    placeholder="John Doe"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                  />
                </div>
              </div>
            )}

            <div className="login__field">
              <label className="form-label">Email address</label>
              <div className="login__input-wrap">
                <span className="login__input-icon">
                  <svg width="15" height="15" viewBox="0 0 20 20" fill="none"><rect x="2" y="5" width="16" height="12" rx="2" stroke="currentColor" strokeWidth="1.5"/><path d="M2 8l8 5 8-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                </span>
                <input
                  className="login__input"
                  type="email"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="login__field">
              <label className="form-label">Password</label>
              <div className="login__input-wrap">
                <span className="login__input-icon">
                  <svg width="15" height="15" viewBox="0 0 20 20" fill="none"><rect x="4" y="9" width="12" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.5"/><path d="M7 9V6a3 3 0 016 0v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                </span>
                <input
                  className="login__input"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>
            </div>

            {isRegister && (
              <div className="login__field">
                <label className="form-label">Role</label>
                <div className="login__input-wrap">
                  <span className="login__input-icon">
                    <svg width="15" height="15" viewBox="0 0 20 20" fill="none"><path d="M10 11a4 4 0 100-8 4 4 0 000 8zM3 18a7 7 0 0114 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                  </span>
                  <select
                    className="login__select"
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                  >
                    <option value="enterprise_user">Enterprise User</option>
                    <option value="reviewer">Reviewer</option>
                    <option value="admin">Administrator</option>
                  </select>
                </div>
              </div>
            )}

            {error && (
              <div className="login__error">
                <svg width="14" height="14" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5"/><path d="M10 6v5M10 14v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                {error}
              </div>
            )}

            <button className="login__submit" type="submit" disabled={loading}>
              {loading
                ? <><span className="spinner" style={{width:16, height:16, borderWidth:2}} /><span>Please wait...</span></>
                : <span>{isRegister ? 'Create Account' : 'Sign In'}</span>
              }
            </button>
          </form>

          <div className="login__toggle">
            {isRegister ? 'Already have an account?' : "Don't have an account?"}
            <button onClick={toggle}>
              {isRegister ? 'Sign In' : 'Register'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
