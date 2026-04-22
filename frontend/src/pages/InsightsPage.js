import { useState, useEffect } from 'react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import { useAuth } from '../context/AuthContext';
import {
  getSpendByVendor, getSpendByMonth,
  getSuppliers, getPredictions, getAnomalies,
} from '../api/client';
import { useToast } from '../components/Toast';
import './InsightsPage.css';

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
          {typeof p.value === 'number' ? `$${p.value.toLocaleString()}` : p.value}
        </div>
      ))}
    </div>
  );
};

const SkeletonChart = () => (
  <div style={{ padding: 'var(--sp-6)' }}>
    <div className="skeleton" style={{ height: 200, borderRadius: 8 }} />
  </div>
);

export default function InsightsPage() {
  const { user } = useAuth();
  const toast    = useToast();

  const [vendors, setVendors]         = useState([]);
  const [monthly, setMonthly]         = useState([]);
  const [suppliers, setSuppliers]     = useState([]);
  const [predictions, setPredictions] = useState(null);
  const [anomalies, setAnomalies]     = useState([]);
  const [loading, setLoading]         = useState(true);

  const isPriv = user?.role === 'reviewer' || user?.role === 'admin';

  useEffect(() => {
    const fetches = [getSpendByVendor(), getSpendByMonth()];
    if (isPriv) fetches.push(getSuppliers(), getPredictions(), getAnomalies());

    Promise.all(fetches)
      .then((results) => {
        setVendors(results[0]);
        setMonthly(results[1]);
        if (isPriv) {
          setSuppliers(results[2]);
          setPredictions(results[3]);
          setAnomalies(results[4]);
        }
      })
      .catch((err) => toast(err.message, 'error'))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line

  const vendorData = vendors.map(v => ({
    name: v.vendor_name?.length > 12 ? v.vendor_name.slice(0,12)+'…' : v.vendor_name,
    spend: v.total_spend,
    docs: v.document_count,
  }));

  const monthlyData = monthly.map(m => ({
    name: m.month?.slice(0, 7) || m.month,
    spend: m.total_spend,
  }));

  const forecastData = predictions?.spend_forecast?.forecast?.map(f => ({
    name: f.month?.slice(0,7) || f.month,
    spend: f.predicted_spend,
  })) || [];

  const combinedTrend = [...monthlyData, ...forecastData.map(d => ({ ...d, forecast: d.spend, spend: undefined }))];

  return (
    <div className="page-wrap">
      <div className="page-header">
        <h1 className="page-title">Analytics & Insights</h1>
        <p className="page-subtitle">
          Spend analysis, trend forecasting, supplier risk, and anomaly detection
        </p>
      </div>

      <div className="insights__charts-grid">
        {/* Vendor spend bar chart */}
        <div className="insights__chart-card">
          <div className="insights__chart-header">
            <span className="insights__chart-title">Spend by Vendor</span>
            <span className="insights__chart-meta">{vendors.length} vendors</span>
          </div>
          {loading ? <SkeletonChart /> : vendorData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={vendorData} margin={{ top: 4, right: 4, bottom: 20, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(56,189,248,0.06)" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: 'var(--text-4)', fontSize: 10 }} axisLine={false} tickLine={false} angle={-20} textAnchor="end" />
                <YAxis tick={{ fill: 'var(--text-4)', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={v => `$${(v/1000).toFixed(0)}k`} />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(56,189,248,0.05)' }} />
                <Bar dataKey="spend" radius={[4,4,0,0]}>
                  {vendorData.map((_, i) => (
                    <Cell key={i} fill={`rgba(56,189,248,${0.45 + i * 0.06})`} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state"><div className="empty-state__title">No vendor data</div></div>
          )}
        </div>

        {/* Monthly trend area chart */}
        <div className="insights__chart-card">
          <div className="insights__chart-header">
            <span className="insights__chart-title">Monthly Spend Trend</span>
            <span className="insights__chart-meta">{monthly.length} months</span>
          </div>
          {loading ? <SkeletonChart /> : monthlyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={monthlyData} margin={{ top: 4, right: 4, bottom: 4, left: 0 }}>
                <defs>
                  <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="var(--accent)" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="var(--accent)" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(56,189,248,0.06)" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: 'var(--text-4)', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: 'var(--text-4)', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={v => `$${(v/1000).toFixed(0)}k`} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="spend" stroke="var(--accent)" strokeWidth={2} fill="url(#areaGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state"><div className="empty-state__title">No monthly data</div></div>
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
          {loading ? <SkeletonChart /> : anomalies.length > 0 ? (
            anomalies.map((a) => (
              <div className="anomaly-item" key={a.document_id}>
                <span className="anomaly-item__score">{a.anomaly_score?.toFixed(2)}</span>
                <span className="anomaly-item__name">{a.filename || a.document_id}</span>
                <span className="anomaly-item__method">{a.method}</span>
                <span className="badge badge--error">Anomaly</span>
              </div>
            ))
          ) : (
            <div className="empty-state" style={{ padding: 'var(--sp-8)' }}>
              <svg className="empty-state__icon" viewBox="0 0 24 24" fill="none"><path d="M10 12l2 2 4-4M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              <div className="empty-state__title">No anomalies detected</div>
              <div className="empty-state__desc">All documents are within normal parameters</div>
            </div>
          )}
        </div>

        {/* Forecast chart (privileged) */}
        {isPriv && (
          <div className="insights__chart-card">
            <div className="insights__chart-header">
              <span className="insights__chart-title">Spend Forecast</span>
              {predictions?.spend_forecast?.method && (
                <span className="badge badge--purple">{predictions.spend_forecast.method}</span>
              )}
            </div>
            {loading ? <SkeletonChart /> : forecastData.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={forecastData} margin={{ top: 4, right: 4, bottom: 4, left: 0 }}>
                  <defs>
                    <linearGradient id="forecastGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="var(--purple)" stopOpacity={0.2}/>
                      <stop offset="95%" stopColor="var(--purple)" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(167,139,250,0.06)" vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: 'var(--text-4)', fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: 'var(--text-4)', fontSize: 10 }} axisLine={false} tickLine={false} tickFormatter={v => `$${(v/1000).toFixed(0)}k`} />
                  <Tooltip content={<ChartTooltip />} />
                  <Area type="monotone" dataKey="spend" stroke="var(--purple)" strokeWidth={2} fill="url(#forecastGrad)" strokeDasharray="5 3" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="empty-state"><div className="empty-state__title">No forecast data</div></div>
            )}
          </div>
        )}
      </div>

      {/* Supplier risk cards */}
      {isPriv && (
        <>
          <div style={{ marginBottom: 'var(--sp-5)' }}>
            <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 20, fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.3px' }}>
              Supplier Risk Assessment
            </h2>
            <p className="page-subtitle" style={{ marginTop: 4 }}>
              AI-generated risk scores based on document processing history
            </p>
          </div>
          {loading ? (
            <div className="risk-cards-grid">
              {[1,2,3].map(i => <div key={i} className="skeleton" style={{ height: 140, borderRadius: 12 }} />)}
            </div>
          ) : suppliers.length > 0 ? (
            <div className="risk-cards-grid">
              {suppliers.map((s, idx) => (
                <div
                  className={`risk-card risk-card--${s.risk_level} animate-slide-up`}
                  key={s.supplier_name}
                  style={{ animationDelay: `${idx * 60}ms` }}
                >
                  <div className="risk-card__level">⬥ {s.risk_level} risk</div>
                  <div className="risk-card__name">{s.supplier_name}</div>
                  <div className="risk-cards__stats">
                    <div className="risk-card__stat">{s.total_documents} document(s) processed</div>
                    {s.avg_confidence != null && (
                      <div className="risk-card__stat">
                        Avg confidence: {(s.avg_confidence * 100).toFixed(1)}%
                      </div>
                    )}
                  </div>
                  {s.risk_score != null && (
                    <div className="risk-card__score">{s.risk_score}</div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state" style={{ marginBottom: 'var(--sp-8)' }}>
              <div className="empty-state__title">No supplier data</div>
              <div className="empty-state__desc">Refresh suppliers from the Admin page to generate risk scores</div>
            </div>
          )}
        </>
      )}

      {/* AI-generated insights */}
      {isPriv && predictions?.insights?.length > 0 && (
        <>
          <div style={{ marginBottom: 'var(--sp-5)' }}>
            <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 20, fontWeight: 700, color: 'var(--text-1)', letterSpacing: '-0.3px', display:'flex', alignItems:'center', gap:'var(--sp-2)' }}>
              <span className="badge badge--purple">AI</span> Generated Insights
            </h2>
          </div>
          <div className="insights__ai-grid">
            {predictions.insights.map((insight, i) => (
              <div className="insights__ai-card animate-slide-up" key={i} style={{ animationDelay: `${i * 60}ms` }}>
                <div style={{ display:'flex', gap:'var(--sp-2)', marginBottom:'var(--sp-2)', color:'var(--purple)', fontSize:11, fontWeight:700, letterSpacing:0.5 }}>
                  ◆ INSIGHT {i+1}
                </div>
                {insight}
              </div>
            ))}
          </div>
        </>
      )}

      {/* Explainer */}
      <div className="insights__explainer">
        <div className="insights__explainer-title">
          <svg width="14" height="14" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5"/><path d="M10 9v5M10 7v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
          How These Insights Are Generated
        </div>
        <div className="insights__explainer-text">
          The IDP Platform uses Random Forest models for risk classification, ARIMA/Prophet
          for spend forecasting, and Isolation Forest for anomaly detection. All models are
          trained on your organisation's historical document processing data and are
          updated continuously as new documents flow through the pipeline.
        </div>
      </div>
    </div>
  );
}
