import { useState, useEffect } from 'react';
import { healthCheck, getDashboard, getSpendByVendor } from '../api/client';
import { useToast } from '../components/Toast';
import './DashboardPage.css';

export default function DashboardPage() {
  const [backendStatus, setBackendStatus] = useState('checking');
  const [summary, setSummary] = useState(null);
  const [vendors, setVendors] = useState([]);
  const [loading, setLoading] = useState(true);
  const toast = useToast();

  useEffect(() => {
    healthCheck()
      .then(() => setBackendStatus('healthy'))
      .catch(() => setBackendStatus('error'));

    Promise.all([getDashboard(), getSpendByVendor()])
      .then(([dashData, vendorData]) => {
        setSummary(dashData);
        setVendors(vendorData);
      })
      .catch((err) => toast(err.message, 'error'))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const metrics = summary
    ? [
        {
          label: 'Total Spend',
          value: `$${summary.total_spend.toLocaleString()}`,
          change: `${summary.total_documents} document(s) processed`,
        },
        {
          label: 'Documents Processed',
          value: `${summary.total_documents}`,
          change: Object.entries(summary.documents_by_status || {})
            .map(([s, c]) => `${c} ${s}`)
            .join(', ') || 'None yet',
        },
        {
          label: 'Compliance Score',
          value: `${summary.compliance_score}%`,
          change: summary.compliance
            ? `${summary.compliance.correction_rate}% correction rate`
            : '',
        },
        {
          label: 'Anomalies Detected',
          value: `${summary.anomaly_count}`,
          change: summary.anomaly_count > 0 ? 'Review flagged documents' : 'No anomalies',
        },
      ]
    : [];

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

      {loading ? (
        <div className="dashboard__loading">Loading analytics...</div>
      ) : (
        <>
          <div className="dashboard__metrics">
            {metrics.map((m) => (
              <div className="dashboard__metric-card" key={m.label}>
                <div className="dashboard__metric-label">{m.label}</div>
                <div className="dashboard__metric-value">{m.value}</div>
                <div className="dashboard__metric-change">{m.change}</div>
              </div>
            ))}
          </div>

          <div className="dashboard__charts">
            <div className="dashboard__chart-card">
              <div className="dashboard__chart-title">Spend by Vendor</div>
              {vendors.length > 0 ? (
                <div className="dashboard__vendor-list">
                  {vendors.map((v) => (
                    <div className="dashboard__vendor-row" key={v.vendor_name}>
                      <span className="dashboard__vendor-name">{v.vendor_name}</span>
                      <div className="dashboard__vendor-bar-wrap">
                        <div
                          className="dashboard__vendor-bar"
                          style={{
                            width: `${Math.min(100, (v.total_spend / Math.max(...vendors.map((x) => x.total_spend))) * 100)}%`,
                          }}
                        />
                      </div>
                      <span className="dashboard__vendor-amount">
                        ${v.total_spend.toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="dashboard__chart-placeholder">
                  No vendor data yet. Upload and process documents to see spend breakdown.
                </div>
              )}
            </div>
            <div className="dashboard__chart-card">
              <div className="dashboard__chart-title">Processing Status</div>
              {summary && Object.keys(summary.documents_by_status || {}).length > 0 ? (
                <div className="dashboard__status-list">
                  {Object.entries(summary.documents_by_status).map(([status, count]) => (
                    <div className="dashboard__status-row" key={status}>
                      <span className={`dashboard__status-badge dashboard__status-badge--${status}`}>
                        {status.replace('_', ' ')}
                      </span>
                      <span className="dashboard__status-count">{count}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="dashboard__chart-placeholder">
                  No documents processed yet.
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
