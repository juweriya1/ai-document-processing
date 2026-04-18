import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './LoginPage.css';

const CheckIcon = () => (
  <svg width="10" height="10" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M2 6l3 3 5-5" />
  </svg>
);

const FEATURES = [
  'OCR & intelligent field extraction',
  'Human-in-the-loop review workflow',
  'Anomaly detection & spend analytics',
  'Role-based access control',
];

export default function LoginPage() {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail]     = useState('');
  const [password, setPassword] = useState('');
  const [name, setName]       = useState('');
  const [role, setRole]       = useState('enterprise_user');
  const [error, setError]     = useState('');
  const [loading, setLoading] = useState(false);
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

  const switchMode = () => { setIsRegister(v => !v); setError(''); };

  return (
    <div className="login-page">
      {/* ── Left hero ── */}
      <div className="login-page__hero">
        <div className="login-page__hero-content">
          <div className="login-page__logo-mark">
            <div className="login-page__logo-box">IDP</div>
            <span className="login-page__logo-text">IntelliDoc</span>
          </div>

          <h1 className="login-page__hero-title">
            Intelligent<br />
            <span>Document Processing</span><br />
            Platform
          </h1>
          <p className="login-page__hero-desc">
            AI-powered extraction, validation, and human-in-the-loop review 
            for enterprise document workflows.
          </p>
          <div className="login-page__features">
            {FEATURES.map(f => (
              <div className="login-page__feature" key={f}>
                <div className="login-page__feature-dot"><CheckIcon /></div>
                {f}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Right form ── */}
      <div className="login-page__form-panel">
        <div className="login-page__form-box">
          <div className="login-page__form-header">
            <h2 className="login-page__form-title">
              {isRegister ? 'Create account' : 'Welcome back'}
            </h2>
            <p className="login-page__form-sub">
              {isRegister
                ? 'Fill in the details below to get started.'
                : 'Sign in to your IntelliDoc account.'}
            </p>
          </div>

          <form className="login-page__form" onSubmit={handleSubmit}>
            {isRegister && (
              <div className="field">
                <label className="field-label">Full Name</label>
                <input className="field-input" type="text" value={name}
                  onChange={e => setName(e.target.value)} placeholder="Jane Smith" required />
              </div>
            )}
            <div className="field">
              <label className="field-label">Email</label>
              <input className="field-input" type="email" value={email}
                onChange={e => setEmail(e.target.value)} placeholder="you@company.com" required />
            </div>
            <div className="field">
              <label className="field-label">Password</label>
              <input className="field-input" type="password" value={password}
                onChange={e => setPassword(e.target.value)} placeholder="••••••••" required />
            </div>
            {isRegister && (
              <div className="field">
                <label className="field-label">Role</label>
                <select className="field-input" value={role} onChange={e => setRole(e.target.value)}>
                  <option value="enterprise_user">Enterprise User</option>
                  <option value="reviewer">Reviewer</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
            )}

            {error && <div className="alert alert--error">{error}</div>}

            <button className="btn btn-primary login-page__submit" type="submit" disabled={loading}>
              {loading ? <><span className="spinner" /> Please wait…</> : isRegister ? 'Create Account' : 'Sign In'}
            </button>
          </form>

          <p className="login-page__toggle">
            {isRegister ? 'Already have an account?' : "Don't have an account?"}
            <button className="login-page__toggle-btn" onClick={switchMode}>
              {isRegister ? 'Sign In' : 'Register'}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
