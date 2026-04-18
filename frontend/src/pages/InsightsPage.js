import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { getSpendByVendor, getSpendByMonth, getSuppliers, getPredictions, getAnomalies } from '../api/client';
import { useToast } from '../components/Toast';
import './InsightsPage.css';

export default function InsightsPage() {
  const { user } = useAuth();
  const toast    = useToast();
  const [vendors, setVendors]         = useState([]);
  const [monthly, setMonthly]         = useState([]);
  const [suppliers, setSuppliers]     = useState([]);
  const [predictions, setPredictions] = useState(null);
  const [anomalies, setAnomalies]     = useState([]);
  const [loading, setLoading]         = useState(true);

  const isRA = user?.role === 'reviewer' || user?.role === 'admin';

  useEffect(() => {
    const fetches = [getSpendByVendor(), getSpendByMonth()];
    if (isRA) fetches.push(getSuppliers(), getPredictions(), getAnomalies());
    Promise.all(fetches)
      .then(r => {
        setVendors(r[0]); setMonthly(r[1]);
        if (isRA) { setSuppliers(r[2]); setPredictions(r[3]); setAnomalies(r[4]); }
      })
      .catch(err => toast(err.message, 'error'))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line

  if (loading) return (
    <div className="page-wrap">
      <div className="page-hd"><h1 className="page-title">Analytics & Insights</h1></div>
      <div className="loading-page"><span className="spinner" /><span>Loading analytics data…</span></div>
    </div>
  );

  return (
    <div className="page-wrap">
      <div className="page-hd">
        <div>
          <h1 className="page-title">Analytics & Insights</h1>
          <p className="page-subtitle">Spend analysis, supplier risk, and AI-generated predictions</p>
        </div>
      </div>

      {/* 3-column chart cards */}
      <div className="insights-charts">
        {/* Vendor spend */}
        <div className="card">
          <div className="card-title">Spend by Vendor</div>
          {vendors.length > 0 ? vendors.slice(0,8).map(v => (
            <div className="data-row" key={v.vendor_name}>
              <span className="data-row__label">{v.vendor_name}</span>
              <span className="data-row__val">${v.total_spend.toLocaleString()}</span>
            </div>
          )) : <div className="empty-state">No vendor data yet.</div>}
        </div>

        {/* Monthly trend */}
        <div className="card">
          <div className="card-title">Monthly Spend</div>
          {monthly.length > 0 ? monthly.map(m => (
            <div className="data-row" key={m.month}>
              <span className="data-row__label">{m.month}</span>
              <span className="data-row__val">${m.total_spend.toLocaleString()}</span>
            </div>
          )) : <div className="empty-state">No monthly data yet.</div>}
        </div>

        {/* Anomalies */}
        <div className="card">
          <div className="card-title">Anomaly Detection</div>
          {anomalies.length > 0 ? anomalies.map(a => (
            <div className="data-row data-row--anomaly" key={a.document_id}>
              <span className="data-row__label">{a.filename || a.document_id}</span>
              <span className="data-row__val">{a.anomaly_score} ({a.method})</span>
            </div>
          )) : (
            <div className="empty-state" style={{ padding:'32px 16px' }}>
              <span style={{ fontSize:24 }}>✅</span>
              No anomalies detected.
            </div>
          )}
        </div>
      </div>

      {/* Supplier risk — RA only */}
      {isRA && (
        <>
          <h2 className="section-title">Supplier Risk Assessment</h2>
          {suppliers.length > 0 ? (
            <div className="supplier-grid">
              {suppliers.map(s => (
                <div key={s.supplier_name} className={`supplier-card supplier-card--${s.risk_level}`}>
                  <div className="supplier-card__risk">{s.risk_level} risk</div>
                  <div className="supplier-card__name">{s.supplier_name}</div>
                  <div className="supplier-card__detail">
                    {s.total_documents} document(s) · Confidence: {s.avg_confidence ? `${(s.avg_confidence*100).toFixed(1)}%` : 'N/A'}
                    {s.risk_score != null && ` · Score: ${s.risk_score}`}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              No supplier data. Refresh metrics from the Admin page.
            </div>
          )}
        </>
      )}

      {/* AI insights + forecast — RA only */}
      {isRA && predictions && (
        <>
          <h2 className="section-title">AI-Generated Insights</h2>
          {(predictions.insights || []).length > 0 ? (
            <div className="ai-cards">
              {predictions.insights.map((insight, i) => (
                <div className="ai-card" key={i}>{insight}</div>
              ))}
            </div>
          ) : (
            <div className="empty-state">No AI insights available yet.</div>
          )}

          {predictions.spend_forecast?.forecast?.length > 0 && (
            <div className="forecast-section">
              <h2 className="section-title">Spend Forecast <span style={{ fontSize:12, fontWeight:500, color:'var(--text-3)' }}>({predictions.spend_forecast.method})</span></h2>
              <div className="card">
                {predictions.spend_forecast.forecast.map(f => (
                  <div className="data-row" key={f.month}>
                    <span className="data-row__label">{f.month}</span>
                    <span className="data-row__val">${f.predicted_spend.toLocaleString()} <span style={{ color:'var(--accent)', fontSize:11 }}>predicted</span></span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* Methodology note */}
      <div className="method-card">
        <div className="method-card__title">How These Insights Are Generated</div>
        <div className="method-card__text">
          The platform uses <span className="method-pill">Random Forest</span> for supplier risk classification,&nbsp;
          <span className="method-pill">ARIMA/Prophet</span> for spend forecasting, and&nbsp;
          <span className="method-pill">Isolation Forest</span> for anomaly detection.
          All models are trained on your organisation's historical document processing data and updated continuously as new documents are processed.
        </div>
      </div>
    </div>
  );
}
