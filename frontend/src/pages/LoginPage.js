import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './LoginPage.css';

export default function LoginPage() {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [role, setRole] = useState('enterprise_user');
  const [error, setError] = useState('');
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
      // navigate('/dashboard');
      setTimeout(() => {
        navigate('/dashboard');
      }, 0);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login">
      <div className="login__card">
        <h1 className="login__title">IDP Platform</h1>
        <p className="login__subtitle">
          {isRegister ? 'Create your account' : 'Sign in to continue'}
        </p>
        <form className="login__form" onSubmit={handleSubmit}>
          {isRegister && (
            <div className="login__field">
              <label className="login__label">Full Name</label>
              <input
                className="login__input"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
          )}
          <div className="login__field">
            <label className="login__label">Email</label>
            <input
              className="login__input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="login__field">
            <label className="login__label">Password</label>
            <input
              className="login__input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {isRegister && (
            <div className="login__field">
              <label className="login__label">Role</label>
              <select
                className="login__select"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                <option value="enterprise_user">Enterprise User</option>
                <option value="reviewer">Reviewer</option>
                <option value="admin">Admin</option>
              </select>
            </div>
          )}
          {error && <div className="login__error">{error}</div>}
          <button className="login__submit" type="submit" disabled={loading}>
            {loading ? 'Please wait...' : isRegister ? 'Create Account' : 'Sign In'}
          </button>
        </form>
        <div className="login__toggle">
          {isRegister ? 'Already have an account?' : "Don't have an account?"}
          <button onClick={() => { setIsRegister(!isRegister); setError(''); }}>
            {isRegister ? 'Sign In' : 'Register'}
          </button>
        </div>
      </div>
    </div>
  );
}
