import React, { useState, useEffect } from 'react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts';
import { analyticsAPI, processingAPI } from '../services/api';
import PageHeader from '../components/shared/PageHeader';
import './DashboardPage.css';

/* ─── Mock fallback data ─── */
const MOCK = {
  stats: {
    total_documents: 1284,
    processed_today: 47,
    pending_review: 12,
    accuracy_rate: 97.3,
    avg_processing_time: 2.8,
    queue_depth: 8,
  },
  throughput: [
    { day: 'Mon', docs: 38, errors: 2 },
    { day: 'Tue', docs: 52, errors: 1 },
    { day: 'Wed', docs: 45, errors: 3 },
    { day: 'Thu', docs: 63, errors: 0 },
    { day: 'Fri', docs: 58, errors: 2 },
    { day: 'Sat', docs: 29, errors: 1 },
    { day: 'Sun', docs: 47, errors: 0 },
  ],
  document_types: [
    { name: 'Invoices', value: 42, color: '#00d4b4' },
    { name: 'Contracts', value: 23, color: '#3b82f6' },
    { name: 'Reports', value: 19, color: '#8b5cf6' },
    { name: 'Forms', value: 16, color: '#f59e0b' },
  ],
  recent_jobs: [
    { id: 'JOB-0892', doc: 'Q4_Invoice_Batch.pdf', status: 'completed', confidence: 98, time: '2m ago' },
    { id: 'JOB-0891', doc: 'ServiceAgreement_v3.pdf', status: 'review', confidence: 82, time: '11m ago' },
    { id: 'JOB-0890', doc: 'EmployeeRecords_Oct.pdf', status: 'processing', confidence: null, time: '18m ago' },
    { id: 'JOB-0889', doc: 'PurchaseOrders_Batch.pdf', status: 'completed', confidence: 96, time: '34m ago' },
    { id: 'JOB-0888', doc: 'TaxForms_2024.pdf', status: 'error', confidence: null, time: '1h ago' },
  ],
};

const STATUS_LABELS = {
  completed: { label: 'Completed', cls: 'badge-success' },
  review: { label: 'Needs Review', cls: 'badge-warn' },
  processing: { label: 'Processing', cls: 'badge-info' },
  error: { label: 'Error', cls: 'badge-danger' },
};

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <span className="chart-tooltip-label">{label}</span>
      {payload.map((p) => (
        <div key={p.name} className="chart-tooltip-row">
          <span style={{ color: p.color }}>{p.name}</span>
          <span>{p.value}</span>
        </div>
      ))}
    </div>
  );
};

export default function DashboardPage() {
  const [data, setData] = useState(MOCK);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
  analyticsAPI.dashboard()
    .then((res) => {
      const incoming = res.data || {};
      setData({
        stats: incoming.stats || MOCK.stats,
        throughput: incoming.throughput || MOCK.throughput,
        document_types: incoming.document_types || MOCK.document_types,
        recent_jobs: incoming.recent_jobs || MOCK.recent_jobs,
      });
    })
    .catch(() => {
      setData(MOCK);
    })
    .finally(() => setLoading(false));
}, []);

const stats = data?.stats || MOCK.stats;
const throughput = data?.throughput || MOCK.throughput;
const document_types = data?.document_types || MOCK.document_types;
const recent_jobs = data?.recent_jobs || MOCK.recent_jobs;

  const KPI_CARDS = [
    {
      label: 'Total Documents',
      value: loading ? null : stats.total_documents?.toLocaleString(),
      delta: '+12%',
      deltaDir: 'up',
      icon: <DocIcon />,
      accent: 'primary',
    },
    {
      label: 'Processed Today',
      value: loading ? null : stats.processed_today,
      delta: '+8 vs yesterday',
      deltaDir: 'up',
      icon: <CheckIcon />,
      accent: 'success',
    },
    {
      label: 'Pending Review',
      value: loading ? null : stats.pending_review,
      delta: '3 critical',
      deltaDir: 'warn',
      icon: <ClockIcon />,
      accent: 'warn',
    },
    {
      label: 'Accuracy Rate',
      value: loading ? null : `${stats.accuracy_rate}%`,
      delta: '+0.4% this week',
      deltaDir: 'up',
      icon: <AccuracyIcon />,
      accent: 'blue',
    },
  ];

  return (
    <div className="page-enter">
      <PageHeader
        title="Dashboard"
        subtitle="Real-time overview of your document processing operations"
        badge={{ text: 'Live', type: 'primary' }}
        actions={
          <div className="flex items-center gap-3">
            <span className="dash-last-updated">Updated just now</span>
            <button className="btn btn-secondary btn-sm">Export Report</button>
          </div>
        }
      />

      <div className="dashboard-content">
        {/* KPI Row */}
        <div className="kpi-grid stagger-1">
          {KPI_CARDS.map((card, i) => (
            <div
              key={card.label}
              className={`kpi-card kpi-card--${card.accent} page-enter`}
              style={{ animationDelay: `${i * 0.07}s` }}
            >
              <div className="kpi-card-header">
                <span className="kpi-label">{card.label}</span>
                <div className={`kpi-icon kpi-icon--${card.accent}`}>{card.icon}</div>
              </div>
              <div className="kpi-value">
                {loading ? (
                  <div className="skeleton" style={{ width: 80, height: 32 }} />
                ) : (
                  card.value
                )}
              </div>
              <div className={`kpi-delta kpi-delta--${card.deltaDir}`}>
                <span>{card.delta}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Charts Row */}
        <div className="dashboard-charts stagger-2">
          {/* Throughput area chart */}
          <div className="card chart-card page-enter" style={{ animationDelay: '0.2s' }}>
            <div className="chart-card-header">
              <div>
                <h3>Processing Throughput</h3>
                <p className="chart-subtitle">Documents processed per day (last 7 days)</p>
              </div>
              <div className="chart-legend">
                <span className="legend-dot" style={{ background: 'var(--accent-primary)' }} />
                <span>Docs</span>
                <span className="legend-dot" style={{ background: 'var(--accent-danger)' }} />
                <span>Errors</span>
              </div>
            </div>
            <ResponsiveContainer width="100%" height={200}>
              <AreaChart data={throughput} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                <defs>
                  <linearGradient id="gradDocs" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00d4b4" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#00d4b4" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gradErr" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="day" tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="docs" name="Docs" stroke="#00d4b4" fill="url(#gradDocs)" strokeWidth={2} dot={false} />
                <Area type="monotone" dataKey="errors" name="Errors" stroke="#ef4444" fill="url(#gradErr)" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Document types pie */}
          <div className="card chart-card chart-card--sm page-enter" style={{ animationDelay: '0.27s' }}>
            <div className="chart-card-header">
              <div>
                <h3>Document Types</h3>
                <p className="chart-subtitle">Distribution by category</p>
              </div>
            </div>
            <div className="pie-layout">
              <ResponsiveContainer width={150} height={150}>
                <PieChart>
                  <Pie
                    data={document_types}
                    cx="50%"
                    cy="50%"
                    innerRadius={46}
                    outerRadius={70}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {document_types.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="pie-legend">
                {document_types.map((d) => (
                  <div key={d.name} className="pie-legend-item">
                    <span className="legend-dot" style={{ background: d.color }} />
                    <span className="pie-legend-name">{d.name}</span>
                    <span className="pie-legend-pct">{d.value}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Bottom row */}
        <div className="dashboard-bottom stagger-3">
          {/* Recent jobs */}
          <div className="card page-enter" style={{ animationDelay: '0.32s' }}>
            <div className="section-header">
              <h3>Recent Jobs</h3>
              <a href="/processing" className="view-all-link">View all →</a>
            </div>
            <div className="jobs-list">
              {recent_jobs.map((job) => (
                <div key={job.id} className="job-row">
                  <div className="job-row-left">
                    <span className="job-id mono">{job.id}</span>
                    <span className="job-doc">{job.doc}</span>
                  </div>
                  <div className="job-row-right">
                    {job.confidence !== null && (
                      <div className="job-confidence">
                        <div className="confidence-track" style={{ width: 60 }}>
                          <div
                            className={`confidence-fill ${job.confidence >= 90 ? 'high' : job.confidence >= 75 ? 'medium' : 'low'}`}
                            style={{ width: `${job.confidence}%` }}
                          />
                        </div>
                        <span className="job-confidence-val">{job.confidence}%</span>
                      </div>
                    )}
                    <span className={`badge ${STATUS_LABELS[job.status]?.cls}`}>
                      {STATUS_LABELS[job.status]?.label}
                    </span>
                    <span className="job-time">{job.time}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* System health */}
          <div className="card system-health page-enter" style={{ animationDelay: '0.38s' }}>
            <div className="section-header">
              <h3>System Health</h3>
            </div>
            <div className="health-items">
              {[
                { name: 'OCR Engine', status: 'active', latency: '120ms' },
                { name: 'NLP Extractor', status: 'active', latency: '380ms' },
                { name: 'Validation Service', status: 'active', latency: '45ms' },
                { name: 'Storage Layer', status: 'active', latency: '12ms' },
                { name: 'Job Queue', status: 'warn', latency: `${stats.queue_depth || 8} jobs` },
              ].map((item) => (
                <div key={item.name} className="health-item">
                  <span className={`pulse-dot ${item.status}`} />
                  <span className="health-name">{item.name}</span>
                  <span className="health-latency mono">{item.latency}</span>
                </div>
              ))}
            </div>

            <div className="divider" />

            <div className="pipeline-stats">
              <div className="stat-chip">
                <span className="label">Avg. Time</span>
                <span className="value">{stats.avg_processing_time || 2.8}s</span>
              </div>
              <div className="stat-chip">
                <span className="label">Queue Depth</span>
                <span className="value">{stats.queue_depth || 8}</span>
              </div>
              <div className="stat-chip">
                <span className="label">Accuracy</span>
                <span className="value" style={{ color: 'var(--accent-primary)' }}>
                  {stats.accuracy_rate || 97.3}%
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Inline icons ─── */
function DocIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <rect x="3" y="1.5" width="12" height="15" rx="2" />
      <path d="M6 6h6M6 9h6M6 12h4" />
    </svg>
  );
}
function CheckIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <circle cx="9" cy="9" r="7.5" />
      <path d="M5.5 9l2.5 2.5 5-5" />
    </svg>
  );
}
function ClockIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <circle cx="9" cy="9" r="7.5" />
      <path d="M9 5v4l2.5 2.5" />
    </svg>
  );
}
function AccuracyIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M2.5 12.5l4-5 3 2.5 4-6.5" />
      <circle cx="15" cy="3" r="1.5" fill="currentColor" stroke="none" />
    </svg>
  );
}
