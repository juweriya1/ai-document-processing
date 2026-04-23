import React, { useState, useEffect } from 'react';
import {
  BarChart, Bar, AreaChart, Area, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { analyticsAPI } from '../services/api';
import PageHeader from '../components/shared/PageHeader';
import './InsightsPage.css';

const THROUGHPUT_DATA = [
  { month: 'May', docs: 320, errors: 12 },
  { month: 'Jun', docs: 445, errors: 8 },
  { month: 'Jul', docs: 512, errors: 15 },
  { month: 'Aug', docs: 490, errors: 6 },
  { month: 'Sep', docs: 620, errors: 9 },
  { month: 'Oct', docs: 743, errors: 11 },
];

const ACCURACY_DATA = [
  { week: 'W1', ocr: 94.2, extraction: 91.5, validation: 97.1 },
  { week: 'W2', ocr: 95.1, extraction: 92.8, validation: 97.4 },
  { week: 'W3', ocr: 94.7, extraction: 93.1, validation: 96.9 },
  { week: 'W4', ocr: 96.3, extraction: 94.2, validation: 98.1 },
];

const TYPE_BREAKDOWN = [
  { type: 'Invoices', count: 542, accuracy: 97.8, color: '#00d4b4' },
  { type: 'Contracts', count: 296, accuracy: 94.2, color: '#3b82f6' },
  { type: 'Reports', count: 244, accuracy: 96.1, color: '#8b5cf6' },
  { type: 'Forms', count: 206, accuracy: 95.5, color: '#f59e0b' },
];

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <span className="chart-tooltip-label">{label}</span>
      {payload.map((p) => (
        <div key={p.name} className="chart-tooltip-row">
          <span style={{ color: p.color }}>{p.name}</span>
          <span>{typeof p.value === 'number' && p.value % 1 !== 0 ? `${p.value}%` : p.value}</span>
        </div>
      ))}
    </div>
  );
};

export default function InsightsPage() {
  const [data, setData] = useState(null);
  const [period, setPeriod] = useState('6m');

  useEffect(() => {
    analyticsAPI.dashboard().then((res) => setData(res.data)).catch(() => {});
  }, []);

  return (
    <div className="page-enter">
      <PageHeader
        title="Insights"
        subtitle="Analytics and performance metrics for your document processing operations"
        actions={
          <div className="period-selector">
            {['1m', '3m', '6m', '1y'].map((p) => (
              <button
                key={p}
                className={`period-btn ${period === p ? 'period-btn--active' : ''}`}
                onClick={() => setPeriod(p)}
              >
                {p}
              </button>
            ))}
          </div>
        }
      />

      <div className="insights-content">
        {/* Summary KPIs */}
        <div className="insights-kpis stagger-1">
          {[
            { label: 'Total Processed', value: '1,288', delta: '+23% vs last period', dir: 'up' },
            { label: 'Avg. Accuracy', value: '96.4%', delta: '+1.2pp improvement', dir: 'up' },
            { label: 'Avg. Processing Time', value: '3.1s', delta: '-0.4s faster', dir: 'up' },
            { label: 'Human Review Rate', value: '8.7%', delta: '-1.1pp reduction', dir: 'up' },
          ].map((kpi, i) => (
            <div key={kpi.label} className="insights-kpi-card page-enter" style={{ animationDelay: `${i * 0.07}s` }}>
              <div className="ikpi-label">{kpi.label}</div>
              <div className="ikpi-value">{kpi.value}</div>
              <div className="ikpi-delta ikpi-delta--up">{kpi.delta}</div>
            </div>
          ))}
        </div>

        {/* Throughput chart */}
        <div className="card insights-chart-card page-enter stagger-2">
          <div className="chart-card-header">
            <div>
              <h3>Monthly Throughput</h3>
              <p className="chart-subtitle">Documents processed and error rate over time</p>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={THROUGHPUT_DATA} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
              <defs>
                <linearGradient id="barGradDocs" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#00d4b4" />
                  <stop offset="100%" stopColor="#00d4b480" />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
              <XAxis dataKey="month" tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="docs" name="Documents" fill="url(#barGradDocs)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="errors" name="Errors" fill="var(--accent-danger)" radius={[4, 4, 0, 0]} opacity={0.7} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Accuracy trends + type breakdown */}
        <div className="insights-row-2 stagger-3">
          <div className="card page-enter" style={{ animationDelay: '0.2s' }}>
            <div className="chart-card-header">
              <div>
                <h3>Accuracy by Stage</h3>
                <p className="chart-subtitle">Weekly accuracy across the 3 pipeline stages</p>
              </div>
            </div>
            <div className="chart-legend" style={{ marginBottom: 'var(--space-3)' }}>
              <span className="legend-dot" style={{ background: 'var(--accent-primary)' }} />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>OCR</span>
              <span className="legend-dot" style={{ background: 'var(--accent-secondary)' }} />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Extraction</span>
              <span className="legend-dot" style={{ background: 'var(--accent-success)' }} />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Validation</span>
            </div>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={ACCURACY_DATA} margin={{ top: 4, right: 4, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="week" tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis domain={[88, 100]} tick={{ fill: 'var(--text-tertiary)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Line type="monotone" dataKey="ocr" name="OCR" stroke="#00d4b4" strokeWidth={2} dot={{ r: 3, fill: '#00d4b4' }} />
                <Line type="monotone" dataKey="extraction" name="Extraction" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3, fill: '#3b82f6' }} />
                <Line type="monotone" dataKey="validation" name="Validation" stroke="#22c55e" strokeWidth={2} dot={{ r: 3, fill: '#22c55e' }} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          {/* Document types */}
          <div className="card page-enter" style={{ animationDelay: '0.27s' }}>
            <div className="chart-card-header">
              <div>
                <h3>By Document Type</h3>
                <p className="chart-subtitle">Volume and accuracy breakdown</p>
              </div>
            </div>
            <div className="type-breakdown-list">
              {TYPE_BREAKDOWN.map((t) => (
                <div key={t.type} className="type-row">
                  <div className="type-row-left">
                    <span className="legend-dot" style={{ background: t.color }} />
                    <span className="type-name">{t.type}</span>
                  </div>
                  <div className="type-row-right">
                    <div className="type-bar-wrap">
                      <div className="type-bar-track">
                        <div
                          className="type-bar-fill"
                          style={{ width: `${(t.count / 542) * 100}%`, background: t.color }}
                        />
                      </div>
                      <span className="type-count mono">{t.count}</span>
                    </div>
                    <span className="type-accuracy" style={{ color: t.color }}>
                      {t.accuracy}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
