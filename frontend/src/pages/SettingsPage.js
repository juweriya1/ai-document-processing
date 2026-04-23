import React, { useState } from 'react';
import PageHeader from '../components/shared/PageHeader';
import './SettingsPage.css';

const SECTIONS = ['Profile', 'API', 'Processing', 'Notifications'];

export default function SettingsPage() {
  const [active, setActive] = useState('Profile');
  const [saved, setSaved] = useState(false);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="page-enter">
      <PageHeader
        title="Settings"
        subtitle="Manage your account, API keys, and platform preferences"
        actions={
          <button className="btn btn-primary btn-sm" onClick={handleSave}>
            {saved ? '✓ Saved' : 'Save changes'}
          </button>
        }
      />

      <div className="settings-layout">
        <nav className="settings-nav">
          {SECTIONS.map((s) => (
            <button
              key={s}
              className={`settings-nav-btn ${active === s ? 'settings-nav-btn--active' : ''}`}
              onClick={() => setActive(s)}
            >
              {s}
            </button>
          ))}
        </nav>

        <div className="settings-content">
          {active === 'Profile' && (
            <div className="settings-section">
              <h3 className="settings-section-title">Profile Information</h3>
              <p className="settings-section-desc">Update your account details and preferences.</p>
              <div className="settings-form">
                {[
                  { label: 'Full Name', placeholder: 'Jane Smith', type: 'text' },
                  { label: 'Email Address', placeholder: 'jane@company.com', type: 'email' },
                  { label: 'Organization', placeholder: 'Acme Corp', type: 'text' },
                ].map((f) => (
                  <div key={f.label} className="settings-field">
                    <label className="form-label">{f.label}</label>
                    <input className="form-input" type={f.type} placeholder={f.placeholder} />
                  </div>
                ))}
              </div>

              <div className="settings-divider" />
              <h3 className="settings-section-title">Change Password</h3>
              <div className="settings-form">
                {[
                  { label: 'Current Password', type: 'password' },
                  { label: 'New Password', type: 'password' },
                  { label: 'Confirm New Password', type: 'password' },
                ].map((f) => (
                  <div key={f.label} className="settings-field">
                    <label className="form-label">{f.label}</label>
                    <input className="form-input" type={f.type} placeholder="••••••••" />
                  </div>
                ))}
              </div>
            </div>
          )}

          {active === 'API' && (
            <div className="settings-section">
              <h3 className="settings-section-title">API Configuration</h3>
              <p className="settings-section-desc">Configure external AI service integrations.</p>
              <div className="settings-form">
                {[
                  { label: 'OpenAI API Key', placeholder: 'sk-••••••••••••••••' },
                  { label: 'Google Vision API Key', placeholder: 'AIza••••••••••••••••' },
                  { label: 'Backend API URL', placeholder: 'http://localhost:5000' },
                ].map((f) => (
                  <div key={f.label} className="settings-field">
                    <label className="form-label">{f.label}</label>
                    <input className="form-input" type="text" placeholder={f.placeholder} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {active === 'Processing' && (
            <div className="settings-section">
              <h3 className="settings-section-title">Processing Defaults</h3>
              <p className="settings-section-desc">Configure default pipeline behavior and thresholds.</p>
              <div className="settings-form">
                <div className="settings-field">
                  <label className="form-label">Confidence Threshold for Auto-approval (%)</label>
                  <input className="form-input" type="number" defaultValue={95} min={50} max={100} />
                </div>
                <div className="settings-field">
                  <label className="form-label">Default OCR Language</label>
                  <select className="form-input">
                    <option>English</option>
                    <option>Arabic</option>
                    <option>French</option>
                    <option>Spanish</option>
                  </select>
                </div>
                <div className="settings-field">
                  <label className="form-label">Max Concurrent Jobs</label>
                  <input className="form-input" type="number" defaultValue={5} min={1} max={20} />
                </div>
              </div>

              <div className="settings-toggles">
                {[
                  { label: 'Auto-process on upload', desc: 'Start pipeline immediately after upload', defaultVal: true },
                  { label: 'Send to review queue if confidence < threshold', desc: 'Automatically flag low-confidence documents', defaultVal: true },
                  { label: 'Enable image pre-processing', desc: 'Deskewing, denoising, and format normalization', defaultVal: true },
                  { label: 'Generate audit trail', desc: 'Log all pipeline events for compliance', defaultVal: false },
                ].map((t) => (
                  <div key={t.label} className="settings-toggle-row">
                    <div>
                      <div className="settings-toggle-label">{t.label}</div>
                      <div className="settings-toggle-desc">{t.desc}</div>
                    </div>
                    <label className="toggle-switch">
                      <input type="checkbox" defaultChecked={t.defaultVal} />
                      <span className="toggle-thumb" />
                    </label>
                  </div>
                ))}
              </div>
            </div>
          )}

          {active === 'Notifications' && (
            <div className="settings-section">
              <h3 className="settings-section-title">Notification Preferences</h3>
              <p className="settings-section-desc">Choose when and how you receive alerts.</p>
              <div className="settings-toggles">
                {[
                  { label: 'Processing completed', desc: 'Notify when a document finishes processing' },
                  { label: 'Review required', desc: 'Alert when documents need human review' },
                  { label: 'Processing errors', desc: 'Alert on pipeline failures' },
                  { label: 'Weekly digest', desc: 'Summary report every Monday morning' },
                ].map((t, i) => (
                  <div key={t.label} className="settings-toggle-row">
                    <div>
                      <div className="settings-toggle-label">{t.label}</div>
                      <div className="settings-toggle-desc">{t.desc}</div>
                    </div>
                    <label className="toggle-switch">
                      <input type="checkbox" defaultChecked={i < 3} />
                      <span className="toggle-thumb" />
                    </label>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
