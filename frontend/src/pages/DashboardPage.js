import { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, PieChart, Pie, Legend,
} from 'recharts';
import { useNavigate } from 'react-router-dom';
import { healthCheck, getDashboard, getSpendByVendor } from '../api/client';
import { useToast } from '../components/Toast';
import { useAuth } from '../context/AuthContext';
import './DashboardPage.css';

/* ─ Tooltip ─ */
const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'var(--bg-3)', border: '1px solid var(--border)',
      borderRadius: 8, padding: '8px 12px', fontSize: 12,
    }}>
      {label && <div style={{ color: 'var(--text-3)', marginBottom: 4 }}>{label}</div>}
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color || 'var(--accent)', fontWeight: 600 }}>
          {p.name ? `${p.name}: ` : ''}{typeof p.value === 'number' && p.name !== 'count'
            ? `$${p.value.toLocaleString()}`
            : p.value}
        </div>
      ))}
    </div>
  );
};

/* ─ KPI Card ─ */
function KpiCard({ label, value, meta, variant, icon, delay, loading }) {
  return (
    <div
      className={`kpi-card kpi-card--${variant} animate-slide-up`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="kpi-card__header">
        <span className="kpi-card__label">{label}</span>
        <div className="kpi-card__icon">{icon}</div>
      </div>
      {loading ? (
        <>
          <div className="skeleton kpi-card__skeleton-value" />
          <div className="skeleton kpi-card__skeleton-meta" />
        </>
      ) : (
        <>
          <div className="kpi-card__value">{value}</div>
          <div className="kpi-card__meta">{meta}</div>
        </>
      )}
    </div>
  );
}

const STATUS_COLORS = {
  uploaded:       '#38bdf8',
  processing:     '#fbbf24',
  preprocessing:  '#fbbf24',
  extracting:     '#fbbf24',
  validating:     '#a78bfa',
  review_pending: '#60a5fa',
  approved:       '#34d399',
  rejected:       '#f87171',
  failed:         '#f87171',
};

export default function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const toast    = useToast();

  const [backendStatus, setBackendStatus] = useState('checking');
  const [summary, setSummary]             = useState(null);
  const [vendors, setVendors]             = useState([]);
  const [loading, setLoading]             = useState(true);

  useEffect(() => {
    healthCheck()
      .then(() => setBackendStatus('healthy'))
      .catch(() => setBackendStatus('error'));

    Promise.all([getDashboard(), getSpendByVendor()])
      .then(([d, v]) => { setSummary(d); setVendors(v); })
      .catch((err) => toast(err.message, 'error'))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line

  /* Vendor chart data */
  const vendorData = vendors.slice(0, 8).map(v => ({
    name: v.vendor_name?.length > 14 ? v.vendor_name.slice(0, 14) + '…' : v.vendor_name,
    spend: v.total_spend,
  }));

  /* Status pie data */
  const statusData = summary
    ? Object.entries(summary.documents_by_status || {}).map(([name, value]) => ({ name, value }))
    : [];

  const kpis = [
    {
      label: 'Total Spend',
      value: summary ? `$${summary.total_spend.toLocaleString()}` : '—',
      meta: `Across ${summary?.total_documents ?? 0} document(s)`,
      variant: 'success',
      icon: <svg width="18" height="18" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5"/><path d="M10 6v1.5m0 5V14m-2.5-5.5c0-1 1-1.5 2.5-1.5s2.5.7 2.5 1.5-1 1.5-2.5 1.5-2.5.5-2.5 1.5S8.5 13 10 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>,
    },
    {
      label: 'Docs Processed',
      value: summary?.total_documents ?? '—',
      meta: Object.entries(summary?.documents_by_status || {}).map(([s, c]) => `${c} ${s.replace('_',' ')}`).join(' · ') || 'No documents yet',
      variant: 'accent',
      icon: <svg width="18" height="18" viewBox="0 0 20 20" fill="none"><path d="M5 3h7l4 4v10a1 1 0 01-1 1H5a1 1 0 01-1-1V4a1 1 0 011-1z" stroke="currentColor" strokeWidth="1.5"/><path d="M12 3v4h4M7 9h6M7 12h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>,
    },
    {
      label: 'Compliance Score',
      value: summary ? `${summary.compliance_score}%` : '—',
      meta: summary?.compliance ? `${summary.compliance.correction_rate}% correction rate` : 'No data yet',
      variant: 'purple',
      icon: <svg width="18" height="18" viewBox="0 0 20 20" fill="none"><path d="M10 2l2 3h4l-3 3 1 4-4-2-4 2 1-4-3-3h4l2-3z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>,
    },
    {
      label: 'Anomalies',
      value: summary?.anomaly_count ?? '—',
      meta: summary?.anomaly_count > 0 ? 'Review flagged documents' : 'All clear',
      variant: summary?.anomaly_count > 0 ? 'warning' : 'success',
      icon: <svg width="18" height="18" viewBox="0 0 20 20" fill="none"><path d="M10 3L18 17H2L10 3z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/><path d="M10 8v4M10 14v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>,
    },
  ];

  return (
    <div className="page-wrap">
      {/* Top bar */}
      <div className="dashboard__topbar">
        <div>
          <h1 className="page-title">
            Good {new Date().getHours() < 12 ? 'morning' : new Date().getHours() < 18 ? 'afternoon' : 'evening'}, {user?.name?.split(' ')[0] || 'there'} 👋
          </h1>
          <p className="page-subtitle">Here's what's happening with your documents today</p>
        </div>
        <div className="dashboard__status-pill">
          <div className={`dashboard__status-indicator dashboard__status-indicator--${backendStatus}`} />
          {backendStatus === 'checking' ? 'Connecting…' : backendStatus === 'healthy' ? 'System healthy' : 'Backend unreachable'}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="dashboard__kpis">
        {kpis.map((k, i) => (
          <KpiCard key={k.label} {...k} delay={i * 60} loading={loading} />
        ))}
      </div>

      {/* Charts */}
      {!loading && (
        <div className="dashboard__charts animate-slide-up" style={{ animationDelay: '240ms' }}>
          {/* Vendor Spend Bar Chart */}
          <div className="dash-chart-card">
            <div className="dash-chart-card__header">
              <span className="dash-chart-card__title">Spend by Vendor</span>
              <span className="dash-chart-card__badge">{vendors.length} vendors</span>
            </div>
            {vendorData.length > 0 ? (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={vendorData} margin={{ top: 4, right: 4, bottom: 4, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(56,189,248,0.06)" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: 'var(--text-4)', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: 'var(--text-4)', fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `$${(v/1000).toFixed(0)}k`} />
                  <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(56,189,248,0.05)' }} />
                  <Bar dataKey="spend" radius={[4, 4, 0, 0]} name="Spend" fill="var(--accent)">
                    {vendorData.map((_, i) => (
                      <Cell key={i} fill={`rgba(56,189,248,${0.5 + (i * 0.06)})`} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="empty-state">
                <svg className="empty-state__icon" viewBox="0 0 24 24" fill="none"><path d="M3 17l4-8 4 4 3-6 4 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
                <div className="empty-state__title">No vendor data yet</div>
                <div className="empty-state__desc">Upload and process documents to see spend breakdown</div>
              </div>
            )}
          </div>

          {/* Processing Status */}
          <div className="dash-chart-card">
            <div className="dash-chart-card__header">
              <span className="dash-chart-card__title">Processing Status</span>
              <span className="dash-chart-card__badge">{summary?.total_documents ?? 0} total</span>
            </div>
            {statusData.length > 0 ? (
              <>
                <ResponsiveContainer width="100%" height={180}>
                  <PieChart>
                    <Pie
                      data={statusData}
                      cx="50%" cy="50%"
                      innerRadius={55} outerRadius={80}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {statusData.map((entry, i) => (
                        <Cell key={i} fill={STATUS_COLORS[entry.name] || '#475569'} />
                      ))}
                    </Pie>
                    <Tooltip content={<ChartTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="dash-status-list">
                  {statusData.map(({ name, value }) => (
                    <div className="dash-status-item" key={name}>
                      <div className="dash-status-dot" style={{ background: STATUS_COLORS[name] || '#475569' }} />
                      <span className="dash-status-item__label">{name.replace(/_/g, ' ')}</span>
                      <span className="dash-status-item__count">{value}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="empty-state">
                <svg className="empty-state__icon" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.5"/><path d="M12 8v4M12 16v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                <div className="empty-state__title">No documents processed</div>
                <div className="empty-state__desc">
                  <button className="btn btn--primary btn--sm" style={{ marginTop: 12 }} onClick={() => navigate('/upload')}>
                    Upload a document
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Quick actions */}
      {!loading && (
        <div className="card animate-slide-up" style={{ animationDelay: '300ms' }}>
          <div className="card-title">Quick Actions</div>
          <div style={{ display: 'flex', gap: 'var(--sp-3)', flexWrap: 'wrap' }}>
            <button className="btn btn--primary" onClick={() => navigate('/upload')}>
              <svg width="15" height="15" viewBox="0 0 20 20" fill="none"><path d="M10 13V4M10 4L7 7M10 4L13 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/><path d="M3 13v2a2 2 0 002 2h10a2 2 0 002-2v-2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              Upload Document
            </button>
            <button className="btn btn--secondary" onClick={() => navigate('/review')}>
              <svg width="15" height="15" viewBox="0 0 20 20" fill="none"><path d="M10 4C6 4 2.7 7.6 2 10c.7 2.4 4 6 8 6s7.3-3.6 8-6c-.7-2.4-4-6-8-6z" stroke="currentColor" strokeWidth="1.5"/><circle cx="10" cy="10" r="2.5" stroke="currentColor" strokeWidth="1.5"/></svg>
              Review Queue
            </button>
            <button className="btn btn--secondary" onClick={() => navigate('/insights')}>
              <svg width="15" height="15" viewBox="0 0 20 20" fill="none"><path d="M2 14l4-4 3 3 4-5 5 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
              Analytics
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
