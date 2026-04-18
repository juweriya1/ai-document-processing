import { useState, useEffect } from 'react';
import { healthCheck, getDashboard, getSpendByVendor } from '../api/client';
import { useToast } from '../components/Toast';
import './DashboardPage.css';

/* ── Icon helpers ─────────────────────────────────────── */
const SI = ({ path, bg }) => (
  <div className="metric-card__icon" style={{ background: bg }}>
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d={path} />
    </svg>
  </div>
);

const ICON_MAP = {
  'Total Spend':           { path: 'M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6', bg: 'rgba(16,185,129,.15)', color: 'var(--success)' },
  'Documents Processed':  { path: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z', bg: 'rgba(91,139,245,.15)', color: 'var(--accent)' },
  'Compliance Score':     { path: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z', bg: 'rgba(56,189,248,.15)', color: 'var(--info)' },
  'Anomalies Detected':   { path: 'M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z', bg: 'rgba(251,191,36,.15)', color: 'var(--warning)' },
};

function statusBadgeClass(s) {
  if (s === 'approved') return 'badge--success';
  if (s === 'rejected') return 'badge--danger';
  if (s === 'review_pending') return 'badge--warning';
  return 'badge--default';
}

function BackendStatus({ status }) {
  const label = status === 'checking' ? 'Checking…' : status === 'healthy' ? 'Backend: Healthy' : 'Backend: Unreachable';
  return (
    <div className={`backend-status backend-status--${status}`}>
      <div className={`backend-status__dot backend-status__dot--${status}`} />
      {label}
    </div>
  );
}

function MetricCard({ label, value, sub }) {
  const meta = ICON_MAP[label] || {};
  return (
    <div className="metric-card">
      <div className="metric-card__label">
        {meta.path && <SI path={meta.path} bg={meta.bg} />}
        {label}
      </div>
      <div className="metric-card__value">{value}</div>
      {sub && <div className="metric-card__sub">{sub}</div>}
    </div>
  );
}

export default function DashboardPage() {
  const [backendStatus, setBackendStatus] = useState('checking');
  const [summary, setSummary]   = useState(null);
  const [vendors, setVendors]   = useState([]);
  const [loading, setLoading]   = useState(true);
  const toast = useToast();

  useEffect(() => {
    healthCheck().then(() => setBackendStatus('healthy')).catch(() => setBackendStatus('error'));
    Promise.all([getDashboard(), getSpendByVendor()])
      .then(([d, v]) => { setSummary(d); setVendors(v); })
      .catch(err => toast(err.message, 'error'))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line

  const metrics = summary ? [
    { label: 'Total Spend',           value: `$${(summary.total_spend || 0).toLocaleString()}`,   sub: `${summary.total_documents} document(s) processed` },
    { label: 'Documents Processed',   value: `${summary.total_documents}`,                        sub: Object.entries(summary.documents_by_status || {}).map(([s,c]) => `${c} ${s}`).join(' · ') || 'None yet' },
    { label: 'Compliance Score',      value: `${summary.compliance_score}%`,                      sub: summary.compliance ? `${summary.compliance.correction_rate}% correction rate` : 'No data' },
    { label: 'Anomalies Detected',    value: `${summary.anomaly_count}`,                          sub: summary.anomaly_count > 0 ? 'Review flagged items' : 'No anomalies found' },
  ] : [];

  const maxSpend = vendors.length ? Math.max(...vendors.map(v => v.total_spend)) : 1;

  return (
    <div className="page-wrap">
      <div className="page-hd">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Overview of your document processing pipeline</p>
        </div>
        <BackendStatus status={backendStatus} />
      </div>

      {loading ? (
        <div className="metrics-skeleton">
          {[1,2,3,4].map(i => (
            <div key={i} className="metric-card--skeleton">
              <div className="sk" style={{ height:12, width:'60%', marginBottom:14 }} />
              <div className="sk" style={{ height:28, width:'80%', marginBottom:8 }} />
              <div className="sk" style={{ height:10, width:'50%' }} />
            </div>
          ))}
        </div>
      ) : (
        <>
          <div className="metrics-grid">
            {metrics.map(m => <MetricCard key={m.label} {...m} />)}
          </div>

          <div className="charts-grid">
            {/* Vendor spend */}
            <div className="card">
              <div className="card-title">Spend by Vendor</div>
              {vendors.length > 0 ? (
                <div className="vendor-chart">
                  {vendors.slice(0, 8).map(v => (
                    <div className="vendor-row" key={v.vendor_name}>
                      <span className="vendor-name">{v.vendor_name}</span>
                      <div className="vendor-track">
                        <div className="vendor-fill" style={{ width: `${(v.total_spend / maxSpend) * 100}%` }} />
                      </div>
                      <span className="vendor-amount">${v.total_spend.toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state">
                  <span style={{ fontSize: 28 }}>📊</span>
                  Upload and process documents to see vendor spend breakdown.
                </div>
              )}
            </div>

            {/* Processing status */}
            <div className="card">
              <div className="card-title">Processing Status</div>
              {summary && Object.keys(summary.documents_by_status || {}).length > 0 ? (
                <div className="status-list">
                  {Object.entries(summary.documents_by_status).map(([s, c]) => (
                    <div className="status-row" key={s}>
                      <span className={`badge ${statusBadgeClass(s)}`}>{s.replace(/_/g, ' ')}</span>
                      <span className="status-count">{c}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state">No documents processed yet.</div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
