import { useState, useEffect } from 'react';
import { healthCheck } from '../api/client';
import { useToast } from '../components/Toast';
import './DashboardPage.css';

const STATIC_METRICS = [
  { label: 'Total Spend', value: '$142,580', change: '+12.3% this month' },
  { label: 'Documents Processed', value: '1,247', change: '+89 this week' },
  { label: 'Compliance Score', value: '94.2%', change: '+2.1% improvement' },
  { label: 'Anomalies Detected', value: '23', change: '3 pending review' },
];

export default function DashboardPage() {
  const [backendStatus, setBackendStatus] = useState('checking');
  const toast = useToast();

  useEffect(() => {
    healthCheck()
      .then(() => setBackendStatus('healthy'))
      .catch(() => setBackendStatus('error'));
  }, []);

  const handleComingSoon = () => {
    toast('Coming soon — analytics backend not yet connected', 'info');
  };

  return (
    <div>
      <div className="dashboard__header">
        <h1 className="dashboard__title">Dashboard</h1>
        <div className="dashboard__status">
          <span
            className={`dashboard__status-dot dashboard__status-dot--${
              backendStatus === 'healthy' ? 'healthy' : 'error'
            }`}
          />
          {backendStatus === 'checking'
            ? 'Checking backend...'
            : backendStatus === 'healthy'
            ? 'Backend: Healthy'
            : 'Backend: Unreachable'}
        </div>
      </div>

      <div className="dashboard__metrics">
        {STATIC_METRICS.map((m) => (
          <div className="dashboard__metric-card" key={m.label}>
            <div className="dashboard__metric-label">{m.label}</div>
            <div className="dashboard__metric-value">{m.value}</div>
            <div className="dashboard__metric-change">{m.change}</div>
          </div>
        ))}
      </div>

      <div className="dashboard__charts">
        <div className="dashboard__chart-card">
          <div className="dashboard__chart-title">Monthly Spend Trend</div>
          <div className="dashboard__chart-placeholder">
            Chart will appear when analytics backend is connected
          </div>
        </div>
        <div className="dashboard__chart-card">
          <div className="dashboard__chart-title">Document Processing Volume</div>
          <div className="dashboard__chart-placeholder">
            Chart will appear when analytics backend is connected
          </div>
        </div>
      </div>

      <div className="dashboard__actions">
        <button className="dashboard__action-btn" onClick={handleComingSoon}>
          Filter by Date Range
        </button>
        <button className="dashboard__action-btn" onClick={handleComingSoon}>
          Filter by Supplier
        </button>
        <button className="dashboard__action-btn" onClick={handleComingSoon}>
          Export Report
        </button>
      </div>
    </div>
  );
}
