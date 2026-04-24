import { useState, useEffect, useCallback } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, AreaChart, Area, PieChart,
  Pie, Legend,
} from 'recharts';
import { useAuth } from '../context/AuthContext';
import {
  getDashboard,
  getSpendByVendor, getSpendByMonth,
  getTrustOverview, getFlaggedDocuments,
  getVendorRisk, getAnomalies, getPredictions,
  getWidgetPreferences,
} from '../api/client';
import { useToast } from '../components/Toast';
import PowerBIEmbed from '../components/PowerBIEmbed';
import WidgetPickerDrawer from '../components/WidgetPickerDrawer';
import './InsightsPage.css';

// ── Helpers ────────────────────────────────────────────────────────────────

const fmtMoney = (v) =>
  v >= 1_000_000 ? `$${(v / 1_000_000).toFixed(1)}M`
  : v >= 1_000   ? `$${(v / 1_000).toFixed(1)}k`
  : `$${v?.toFixed(2) ?? '–'}`;

const PRIORITY_CLASS = {
  'Auto-Approve Candidate': 'auto',
  'Needs Human Review':     'review',
  'Escalate':               'escalate',
  'Reject / Incomplete':    'reject',
};

const PRIORITY_DOT = {
  'Auto-Approve Candidate': '✓',
  'Needs Human Review':     '⚠',
  'Escalate':               '▲',
  'Reject / Incomplete':    '✕',
};

function trustColor(score) {
  if (score >= 80) return '#22c55e';
  if (score >= 60) return '#38bdf8';
  if (score >= 40) return '#eab308';
  if (score >= 20) return '#f97316';
  return '#ef4444';
}

// ── Sub-components ─────────────────────────────────────────────────────────

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
          {typeof p.value === 'number'
            ? p.name?.includes('spend') || p.name?.includes('Spend')
              ? fmtMoney(p.value) : p.value
            : p.value}
        </div>
      ))}
    </div>
  );
};

const SkeletonCard = ({ h = 120 }) => (
  <div className="skeleton" style={{ height: h, borderRadius: 12 }} />
);

const EmptyState = ({ icon = '📊', title, desc }) => (
  <div className="insights__empty">
    <div className="insights__empty-icon">{icon}</div>
    <div className="insights__empty-title">{title}</div>
    {desc && <div className="insights__empty-desc">{desc}</div>}
  </div>
);

function KpiCard({ icon, iconClass, label, value, sub, colorClass }) {
  return (
    <div className={`kpi-card${colorClass ? ` kpi-card--${colorClass}` : ''}`}>
      <div className={`kpi-card__icon kpi-card__icon--${iconClass}`}>{icon}</div>
      <div className="kpi-card__label">{label}</div>
      <div className="kpi-card__value">{value ?? '–'}</div>
      {sub && <div className="kpi-card__sub">{sub}</div>}
    </div>
  );
}

function TrustBar({ score }) {
  const color = trustColor(score);
  return (
    <div className="trust-bar">
      <div className="trust-bar__track">
        <div
          className="trust-bar__fill"
          style={{ width: `${score}%`, background: color }}
        />
      </div>
      <div className="trust-bar__label" style={{ color }}>{score}</div>
    </div>
  );
}

function PriorityBadge({ priority }) {
  const cls = PRIORITY_CLASS[priority] || 'review';
  const dot = PRIORITY_DOT[priority] || '?';
  return (
    <span className={`priority-badge priority-badge--${cls}`}>
      {dot} {priority}
    </span>
  );
}

function DistBar({ label, count, max, color }) {
  const pct = max > 0 ? (count / max) * 100 : 0;
  return (
    <div className="dist-bar-row">
      <div className="dist-bar-row__label">{label}</div>
      <div className="dist-bar-row__track">
        <div className="dist-bar-row__fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div className="dist-bar-row__count">{count}</div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────

export default function InsightsPage() {
  const { user } = useAuth();
  const toast = useToast();

  const [dashboard, setDashboard]   = useState(null);
  const [trustData, setTrustData]   = useState(null);
  const [flagged, setFlagged]       = useState([]);
  const [vendorRisk, setVendorRisk] = useState([]);
  const [vendors, setVendors]       = useState([]);
  const [monthly, setMonthly]       = useState([]);
  const [anomalies, setAnomalies]   = useState([]);
  const [predictions, setPredictions] = useState(null);
  const [loading, setLoading]       = useState(true);
  const [activeTab, setActiveTab]   = useState('overview');
  const [pickerOpen, setPickerOpen] = useState(false);
  const [prefs, setPrefs]           = useState(null);

  const isPriv = user?.role === 'reviewer' || user?.role === 'admin';
  const canSeeExecutiveBI = isPriv;
  const isWidgetEnabled = (key) => !prefs || (prefs.enabled || []).includes(key);

  const load = useCallback(() => {
    setLoading(true);
    const base = [
      getDashboard(),
      getTrustOverview(),
      getFlaggedDocuments(),
      getSpendByVendor(),
      getSpendByMonth(),
    ];
    const priv = isPriv
      ? [getVendorRisk(), getAnomalies(), getPredictions()]
      : [Promise.resolve([]), Promise.resolve([]), Promise.resolve(null)];

    Promise.all([...base, ...priv])
      .then(([dash, trust, flag, vend, mon, vRisk, anom, pred]) => {
        setDashboard(dash);
        setTrustData(trust);
        setFlagged(flag || []);
        setVendors(vend || []);
        setMonthly(mon || []);
        if (isPriv) {
          setVendorRisk(vRisk || []);
          setAnomalies(anom || []);
          setPredictions(pred);
        }
      })
      .catch((e) => toast(e.message, 'error'))
      .finally(() => setLoading(false));
  }, [isPriv]); // eslint-disable-line

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    getWidgetPreferences().then(setPrefs).catch(() => setPrefs(null));
  }, []);

  // ── Derived chart data ─────────────────────────────────────────────────
  const vendorChartData = vendors.map((v) => ({
    name: v.vendor_name?.length > 14 ? v.vendor_name.slice(0, 14) + '…' : v.vendor_name,
    spend: v.total_spend,
    docs: v.document_count,
  }));

  const monthlyChartData = monthly.map((m) => ({
    name: m.month?.slice(0, 7) || m.month,
    spend: m.total_spend,
  }));

  const forecastData = predictions?.spend_forecast?.forecast?.map((f) => ({
    name: f.month?.slice(0, 7) || f.month,
    spend: f.predicted_spend,
  })) || [];

  const maxDist = trustData?.trust_distribution
    ? Math.max(...trustData.trust_distribution.map((b) => b.count), 1)
    : 1;
  const maxPrio = trustData?.priority_distribution
    ? Math.max(...trustData.priority_distribution.map((b) => b.count), 1)
    : 1;

  const validationData = dashboard?.validation_failure_breakdown || [];

  // ── Render ─────────────────────────────────────────────────────────────
  return (
    <div className="page-wrap">
      {/* ── Header ── */}
      <div className="insights__page-header">
        <div>
          <h1 className="page-title">Procurement Intelligence</h1>
          <p className="page-subtitle">
            Spend, compliance, and pipeline quality across your AP operations —
            with an Executive BI dashboard for leadership reporting.
          </p>
        </div>
        <button className="btn btn--secondary" onClick={() => setPickerOpen(true)}>
          ⚙ Configure Dashboard
        </button>
      </div>

      {/* ── Tab bar ── */}
      <div className="insights__tabs" role="tablist">
        <button
          role="tab"
          className={`insights__tab${activeTab === 'overview' ? ' insights__tab--active' : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          Overview
        </button>
        {canSeeExecutiveBI && (
          <button
            role="tab"
            className={`insights__tab${activeTab === 'executive' ? ' insights__tab--active' : ''}`}
            onClick={() => setActiveTab('executive')}
          >
            Executive BI
          </button>
        )}
      </div>

      {activeTab === 'executive' && canSeeExecutiveBI ? (
        <PowerBIEmbed />
      ) : (<>

      {/* ══ SECTION 1: KPI Cards ══════════════════════════════════════════ */}
      <div className="insights__kpi-grid">
        {loading ? (
          [1,2,3,4,5,6].map((i) => <SkeletonCard key={i} h={130} />)
        ) : (<>
          <KpiCard
            icon="📄" iconClass="blue"
            label="Documents Processed"
            value={dashboard?.total_documents ?? 0}
            sub={`${dashboard?.documents_by_status?.approved ?? 0} approved`}
          />
          <KpiCard
            icon="🛡" iconClass="green"
            label="Avg Trust Score"
            value={trustData?.avg_trust_score != null ? `${trustData.avg_trust_score}/100` : '–'}
            sub="Based on OCR confidence, corrections & validation"
            colorClass={
              trustData?.avg_trust_score >= 75 ? 'trust'
              : trustData?.avg_trust_score >= 50 ? ''
              : 'warn'
            }
          />
          <KpiCard
            icon="⚠️" iconClass="orange"
            label="High-Risk Vendors"
            value={dashboard?.high_risk_vendor_count ?? 0}
            sub="Risk score ≥ 60 — correction + invalid field patterns"
            colorClass={dashboard?.high_risk_vendor_count > 0 ? 'warn' : ''}
          />
          <KpiCard
            icon="🔍" iconClass="yellow"
            label="Requiring Review"
            value={dashboard?.docs_requiring_review ?? 0}
            sub={`${dashboard?.escalation_count ?? 0} escalations, ${dashboard?.reject_count ?? 0} rejections`}
            colorClass={dashboard?.docs_requiring_review > 0 ? 'warn' : ''}
          />
          <KpiCard
            icon="❌" iconClass="red"
            label="Compliance Exceptions"
            value={dashboard?.compliance_exception_count ?? 0}
            sub="Documents with invalid extracted fields"
            colorClass={dashboard?.compliance_exception_count > 0 ? 'danger' : ''}
          />
          <KpiCard
            icon="🚨" iconClass="purple"
            label="Anomalies Detected"
            value={dashboard?.anomaly_count ?? 0}
            sub="Statistical outliers in amount, confidence, corrections"
            colorClass={dashboard?.anomaly_count > 0 ? 'danger' : ''}
          />
        </>)}
      </div>

      {/* ══ SECTION 2: Trust Score Distribution + Priority Breakdown ══════ */}
      <div className="insights__section-header">
        <div className="insights__section-title">
          <span className="badge badge--success">TRUST</span>
          Document Trust Score Analysis
        </div>
        <div className="insights__section-sub">
          Each document is scored 0–100 based on OCR confidence, field validity,
          corrections applied, and line-item reconciliation.
        </div>
      </div>

      <div className="insights__charts-grid" style={{ marginBottom: 'var(--sp-8)' }}>
        {/* Trust distribution */}
        <div className="insights__chart-card">
          <div className="insights__chart-header">
            <span className="insights__chart-title">Trust Score Distribution</span>
            <span className="insights__chart-meta">
              {trustData?.documents?.length ?? 0} documents
            </span>
          </div>
          {loading ? <SkeletonCard h={200} /> : trustData?.trust_distribution?.length > 0 ? (
            <div className="dist-bar-list">
              {trustData.trust_distribution.map((b) => (
                <DistBar key={b.label} label={b.label} count={b.count} max={maxDist} color={b.color} />
              ))}
            </div>
          ) : (
            <EmptyState icon="📊" title="No trust data yet" desc="Process documents to generate trust scores" />
          )}
        </div>

        {/* Review priority breakdown */}
        <div className="insights__chart-card">
          <div className="insights__chart-header">
            <span className="insights__chart-title">Review Priority Breakdown</span>
            <span className="insights__chart-meta">Deterministic classification</span>
          </div>
          {loading ? <SkeletonCard h={200} /> : trustData?.priority_distribution?.length > 0 ? (
            <div className="dist-bar-list" style={{ marginTop: 'var(--sp-2)' }}>
              {trustData.priority_distribution.map((b) => (
                <DistBar key={b.label} label={b.label} count={b.count} max={maxPrio} color={b.color} />
              ))}
            </div>
          ) : (
            <EmptyState icon="🏷" title="No priority data" desc="Documents will be classified as they are processed" />
          )}
        </div>

        {/* Validation failure breakdown */}
        <div className="insights__chart-card">
          <div className="insights__chart-header">
            <span className="insights__chart-title">Validation Failure Breakdown</span>
            <span className="insights__chart-meta">By field type</span>
          </div>
          {loading ? <SkeletonCard h={200} /> : validationData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart
                data={validationData}
                layout="vertical"
                margin={{ top: 0, right: 20, bottom: 0, left: 80 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(56,189,248,0.06)" horizontal={false} />
                <XAxis type="number" tick={{ fill: 'var(--text-4)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="field_name" tick={{ fill: 'var(--text-3)', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(239,68,68,0.05)' }} />
                <Bar dataKey="count" radius={[0, 4, 4, 0]} fill="#ef4444" fillOpacity={0.7} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState icon="✅" title="No validation failures" desc="All extracted fields passed validation" />
          )}
        </div>

        {/* Anomalies */}
        <div className="insights__chart-card">
          <div className="insights__chart-header">
            <span className="insights__chart-title">Anomaly Detection</span>
            <span className={`badge ${anomalies.length > 0 ? 'badge--error' : 'badge--success'}`}>
              {anomalies.length} found
            </span>
          </div>
          {loading ? <SkeletonCard h={200} /> : anomalies.length > 0 ? (
            <div style={{ maxHeight: 220, overflowY: 'auto' }}>
              {anomalies.map((a) => (
                <div className="anomaly-item" key={a.document_id}>
                  <span className="anomaly-item__score">{a.anomaly_score?.toFixed(2)}</span>
                  <span className="anomaly-item__name">{a.filename || a.document_id}</span>
                  <span className="anomaly-item__method">{a.method}</span>
                  <span className="badge badge--error">Anomaly</span>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState icon="🟢" title="No anomalies detected" desc="All documents are within normal statistical parameters" />
          )}
        </div>
      </div>

      {/* ══ SECTION 3: Flagged Documents Table ═══════════════════════════ */}
      <div className="insights__section-header">
        <div className="insights__section-title">
          <span className="badge badge--error">FLAGGED</span>
          Documents Requiring Attention
        </div>
        <div className="insights__section-sub">
          Every flagged document shows why it was classified, which signals triggered the flag,
          and what the recommended action is.
        </div>
      </div>

      {loading ? (
        <SkeletonCard h={180} />
      ) : flagged.length > 0 ? (
        <div className="flagged-table-wrap">
          <table className="flagged-table">
            <thead>
              <tr>
                <th>Document</th>
                <th>Trust Score</th>
                <th>Priority</th>
                <th>Flags / Reasons</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {flagged.map((doc) => (
                <tr key={doc.document_id}>
                  <td>
                    <div className="flagged-doc__name" title={doc.filename}>
                      {doc.filename || doc.document_id}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-5)', marginTop: 2 }}>
                      {doc.document_id}
                    </div>
                  </td>
                  <td style={{ width: 160 }}>
                    <TrustBar score={doc.trust_score} />
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <PriorityBadge priority={doc.review_priority} />
                  </td>
                  <td>
                    <div className="flagged-doc__reasons">
                      {(doc.reasons || []).slice(0, 3).map((r, i) => (
                        <div className="flagged-doc__reason" key={i}>{r}</div>
                      ))}
                      {doc.reasons?.length > 3 && (
                        <div style={{ fontSize: 11, color: 'var(--text-5)', marginTop: 2 }}>
                          +{doc.reasons.length - 3} more signals
                        </div>
                      )}
                    </div>
                  </td>
                  <td>
                    <span className="badge" style={{
                      background: 'rgba(255,255,255,0.05)',
                      color: 'var(--text-3)',
                      fontSize: 11,
                    }}>
                      {doc.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="insights__chart-card" style={{ marginBottom: 'var(--sp-8)' }}>
          <EmptyState icon="✅" title="No flagged documents" desc="All processed documents are Auto-Approve candidates" />
        </div>
      )}

      {/* ══ SECTION 4: Spend Analysis ═════════════════════════════════════ */}
      <div className="insights__section-header">
        <div className="insights__section-title">
          <span className="badge badge--purple">SPEND</span>
          Procurement Spend Analysis
        </div>
        <div className="insights__section-sub">
          Spend trends and vendor distribution derived from approved invoice amounts.
        </div>
      </div>

      <div className="insights__charts-grid">
        {/* Vendor spend */}
        <div className="insights__chart-card">
          <div className="insights__chart-header">
            <span className="insights__chart-title">Spend by Vendor</span>
            <span className="insights__chart-meta">{vendors.length} vendors</span>
          </div>
          {loading ? <SkeletonCard h={220} /> : vendorChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={vendorChartData} margin={{ top: 4, right: 4, bottom: 24, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(56,189,248,0.06)" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: 'var(--text-4)', fontSize: 10 }} axisLine={false} tickLine={false} angle={-20} textAnchor="end" />
                <YAxis tick={{ fill: 'var(--text-4)', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => fmtMoney(v)} />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(56,189,248,0.05)' }} />
                <Bar dataKey="spend" name="Spend" radius={[4,4,0,0]}>
                  {vendorChartData.map((_, i) => (
                    <Cell key={i} fill={`rgba(56,189,248,${0.4 + i * 0.08})`} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState icon="💰" title="No spend data" desc="Approve documents with vendor names and amounts to see spend breakdown" />
          )}
        </div>

        {/* Monthly trend */}
        <div className="insights__chart-card">
          <div className="insights__chart-header">
            <span className="insights__chart-title">Monthly Spend Trend</span>
            {predictions?.spend_forecast?.method && (
              <span className="badge badge--purple">
                {predictions.spend_forecast.method} forecast
              </span>
            )}
          </div>
          {loading ? <SkeletonCard h={220} /> : monthlyChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart
                data={[
                  ...monthlyChartData,
                  ...forecastData.map((d) => ({ name: d.name, forecast: d.spend })),
                ]}
                margin={{ top: 4, right: 4, bottom: 4, left: 0 }}
              >
                <defs>
                  <linearGradient id="histGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="var(--accent)" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="var(--accent)" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="foreGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="var(--purple)" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="var(--purple)" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(56,189,248,0.06)" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: 'var(--text-4)', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'var(--text-4)', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={(v) => fmtMoney(v)} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="spend" name="Historical Spend" stroke="var(--accent)" strokeWidth={2} fill="url(#histGrad)" />
                {forecastData.length > 0 && (
                  <Area type="monotone" dataKey="forecast" name="Forecast" stroke="var(--purple)" strokeWidth={2} fill="url(#foreGrad)" strokeDasharray="5 3" />
                )}
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState icon="📈" title="No monthly data" desc="More approved records are needed to generate spend trends" />
          )}
        </div>
      </div>

      {/* ══ SECTION 5: Vendor Risk Ranking ═══════════════════════════════ */}
      {isPriv && (
        <>
          <div className="insights__section-header">
            <div className="insights__section-title">
              <span className="badge badge--error">RISK</span>
              Vendor Risk Ranking
            </div>
            <div className="insights__section-sub">
              Risk scores derived from real correction patterns, invalid field rates,
              low trust rates, and invoice amount volatility per vendor.
            </div>
          </div>

          {loading ? (
            <div className="risk-cards-grid">
              {[1,2,3].map((i) => <SkeletonCard key={i} h={180} />)}
            </div>
          ) : vendorRisk.length > 0 ? (
            <div className="risk-cards-grid" style={{ marginBottom: 'var(--sp-8)' }}>
              {vendorRisk.map((v, idx) => (
                <div
                  className={`risk-card risk-card--${v.risk_level} animate-slide-up`}
                  key={v.vendor_name}
                  style={{ animationDelay: `${idx * 50}ms` }}
                >
                  <div className="risk-card__badge">⬥ {v.risk_level} risk</div>
                  <div className="risk-card__name" title={v.vendor_name}>{v.vendor_name}</div>
                  <div className="risk-card__score">{v.risk_score}</div>
                  <div className="risk-card__stat">{v.total_documents} document(s) · avg trust {v.avg_trust_score}/100</div>
                  {v.total_corrections > 0 && (
                    <div className="risk-card__stat">{v.total_corrections} total correction(s)</div>
                  )}
                  {v.reasons?.length > 0 && (
                    <div className="risk-card__reasons">
                      {v.reasons.slice(0, 2).map((r, i) => (
                        <div className="risk-card__reason" key={i}>{r}</div>
                      ))}
                    </div>
                  )}
                  {v.recommended_action && (
                    <div className="risk-card__action">{v.recommended_action}</div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="insights__chart-card" style={{ marginBottom: 'var(--sp-8)' }}>
              <EmptyState
                icon="🏢"
                title="No vendor risk data"
                desc="More approved records are needed to generate vendor risk patterns"
              />
            </div>
          )}
        </>
      )}

      {/* ══ SECTION 6: AI-Generated Insights ════════════════════════════ */}
      {isPriv && predictions?.insights?.length > 0 && (
        <>
          <div className="insights__section-header">
            <div className="insights__section-title">
              <span className="badge badge--purple">AI</span>
              Generated Insights
            </div>
          </div>
          <div className="insights__ai-grid">
            {predictions.insights.map((insight, i) => (
              <div
                className="insights__ai-card animate-slide-up"
                key={i}
                style={{ animationDelay: `${i * 60}ms` }}
              >
                <div style={{ display:'flex', gap:'var(--sp-2)', marginBottom:'var(--sp-2)', color:'var(--purple)', fontSize:11, fontWeight:700, letterSpacing:0.5 }}>
                  ◆ INSIGHT {i+1}
                </div>
                {insight}
              </div>
            ))}
          </div>
        </>
      )}

      {/* ══ SECTION 7: Formula Explainer ═════════════════════════════════ */}
      <div className="insights__explainer">
        <div className="insights__explainer-title">
          <svg width="14" height="14" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5"/><path d="M10 9v5M10 7v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
          How These Scores Are Computed
        </div>
        <div className="insights__formula-grid">
          <div className="insights__formula-item">
            <div className="insights__formula-name">🛡 Document Trust Score</div>
            <div className="insights__formula-desc">
              Starts at 100. Penalties: low OCR confidence (−30 max), invalid fields
              (−7 each, −20 max), missing required fields (−8 each, −25 max),
              human corrections (−5 each, −15 max), line-item mismatch (−12).
              Source: extracted_fields, corrections, line_items tables.
            </div>
          </div>
          <div className="insights__formula-item">
            <div className="insights__formula-name">⚠️ Vendor Risk Score</div>
            <div className="insights__formula-desc">
              Aggregated across all vendor documents: correction rate (25 pts),
              invalid field rate (25 pts), low-trust rate (20 pts),
              invoice amount volatility/CV (20 pts), missing required field rate (10 pts).
              All signals derived from real DB records.
            </div>
          </div>
          <div className="insights__formula-item">
            <div className="insights__formula-name">🏷 Review Priority</div>
            <div className="insights__formula-desc">
              Deterministic rules: Auto-Approve (trust ≥ 80, no issues),
              Needs Human Review (trust 50–79 or 1 correction),
              Escalate (trust 25–49 or line-item mismatch or ≥ 3 corrections),
              Reject/Incomplete (trust &lt; 25 or ≥ 2 required fields missing).
            </div>
          </div>
        </div>
      </div>
      </>)}

      <WidgetPickerDrawer
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSaved={(layout) => setPrefs(layout)}
      />
    </div>
  );
}
