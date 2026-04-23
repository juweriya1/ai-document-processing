import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import toast from 'react-hot-toast';
import './Auth.css';

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '' });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  const validate = () => {
    const e = {};
    if (!form.name.trim()) e.name = 'Full name is required';
    if (!form.email) e.email = 'Email is required';
    else if (!/\S+@\S+\.\S+/.test(form.email)) e.email = 'Invalid email address';
    if (!form.password) e.password = 'Password is required';
    else if (form.password.length < 8) e.password = 'Password must be at least 8 characters';
    if (form.password !== form.confirm) e.confirm = 'Passwords do not match';
    return e;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }
    setErrors({});
    setLoading(true);
    try {
      await register(form.name.trim(), form.email, form.password);
      toast.success('Account created!', { className: 'custom-toast' });
      navigate('/dashboard');
    } catch (err) {
      const msg = err.response?.data?.message || 'Registration failed. Please try again.';
      toast.error(msg, { className: 'custom-toast' });
    } finally {
      setLoading(false);
    }
  };

  const field = (name, label, type = 'text', placeholder = '') => (
    <div className="auth-field">
      <label className="form-label" htmlFor={name}>{label}</label>
      <input
        id={name}
        type={type}
        className={`form-input ${errors[name] ? 'error' : ''}`}
        placeholder={placeholder}
        value={form[name]}
        onChange={(e) => setForm((f) => ({ ...f, [name]: e.target.value }))}
      />
      {errors[name] && <span className="form-error">{errors[name]}</span>}
    </div>
  );

  return (
    <div className="auth-page">
      <div className="auth-bg">
        <div className="auth-bg-orb auth-bg-orb--1" />
        <div className="auth-bg-orb auth-bg-orb--2" />
        <div className="auth-bg-grid" />
      </div>

      <div className="auth-container">
        <div className="auth-brand">
          <div className="auth-brand-logo">
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
              <rect width="32" height="32" rx="9" fill="var(--accent-primary)" />
              <path d="M9 11h14M9 16h10M9 21h7" stroke="#080c18" strokeWidth="2.5" strokeLinecap="round" />
              <circle cx="22" cy="21" r="3.5" fill="#080c18" />
            </svg>
          </div>
          <span className="auth-brand-name">Docura</span>
        </div>

        <div className="auth-card">
          <div className="auth-card-header">
            <h2>Create your account</h2>
            <p>Start processing documents with AI today</p>
          </div>

          <form onSubmit={handleSubmit} className="auth-form" noValidate>
            {field('name', 'Full name', 'text', 'Jane Smith')}
            {field('email', 'Email address', 'email', 'jane@company.com')}
            {field('password', 'Password', 'password', 'Min. 8 characters')}
            {field('confirm', 'Confirm password', 'password', 'Repeat password')}

            <button
              type="submit"
              className="btn btn-primary w-full auth-submit"
              disabled={loading}
            >
              {loading ? (
                <><span className="btn-spinner" />Creating account…</>
              ) : (
                'Create account'
              )}
            </button>
          </form>

          <div className="auth-footer">
            <p>Already have an account? <Link to="/login">Sign in</Link></p>
          </div>
        </div>
      </div>
    </div>
  );
}
