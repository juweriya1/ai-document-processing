import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import {
  getSpendByVendor,
  getSpendByMonth,
  getSuppliers,
  getPredictions,
  getAnomalies,
} from '../api/client';
import { useToast } from '../components/Toast';
import './InsightsPage.css';

export default function InsightsPage() {
  const { user } = useAuth();
  const toast = useToast();
  const [vendors, setVendors] = useState([]);
  const [monthly, setMonthly] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [predictions, setPredictions] = useState(null);
  const [anomalies, setAnomalies] = useState([]);
  const [loading, setLoading] = useState(true);

  const isReviewerOrAdmin = user?.role === 'reviewer' || user?.role === 'admin';

  useEffect(() => {
    const fetches = [getSpendByVendor(), getSpendByMonth()];
    if (isReviewerOrAdmin) {
      fetches.push(getSuppliers(), getPredictions(), getAnomalies());
    }

    Promise.all(fetches)
      .then((results) => {
        setVendors(results[0]);
        setMonthly(results[1]);
        if (isReviewerOrAdmin) {
          setSuppliers(results[2]);
          setPredictions(results[3]);
          setAnomalies(results[4]);
        }
      })
      .catch((err) => toast(err.message, 'error'))
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div>
        <h1 className="insights__title">Analytics & Insights</h1>
        <div className="insights__loading">Loading analytics data...</div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="insights__title">Analytics & Insights</h1>

      <div className="insights__charts">
        <div className="insights__chart-card">
          <div className="insights__chart-title">Spend by Vendor</div>
          {vendors.length > 0 ? (
            <div className="insights__data-list">
              {vendors.map((v) => (
                <div className="insights__data-row" key={v.vendor_name}>
                  <span className="insights__data-label">{v.vendor_name}</span>
                  <span className="insights__data-value">
                    ${v.total_spend.toLocaleString()} ({v.document_count} docs)
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="insights__chart-placeholder">No vendor data available yet.</div>
          )}
        </div>
        <div className="insights__chart-card">
          <div className="insights__chart-title">Monthly Spend Trend</div>
          {monthly.length > 0 ? (
            <div className="insights__data-list">
              {monthly.map((m) => (
                <div className="insights__data-row" key={m.month}>
                  <span className="insights__data-label">{m.month}</span>
                  <span className="insights__data-value">
                    ${m.total_spend.toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="insights__chart-placeholder">No monthly data available yet.</div>
          )}
        </div>
        <div className="insights__chart-card">
          <div className="insights__chart-title">Anomalies</div>
          {anomalies.length > 0 ? (
            <div className="insights__data-list">
              {anomalies.map((a) => (
                <div className="insights__data-row insights__data-row--anomaly" key={a.document_id}>
                  <span className="insights__data-label">{a.filename}</span>
                  <span className="insights__data-value">
                    Score: {a.anomaly_score} ({a.method})
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="insights__chart-placeholder">No anomalies detected.</div>
          )}
        </div>
      </div>

      {isReviewerOrAdmin && (
        <>
          <h2 className="insights__section-title">Supplier Risk Assessment</h2>
          {suppliers.length > 0 ? (
            <div className="insights__risk-cards">
              {suppliers.map((s) => (
                <div
                  className={`insights__risk-card insights__risk-card--${s.risk_level}`}
                  key={s.supplier_name}
                >
                  <div className="insights__risk-level">{s.risk_level} risk</div>
                  <div className="insights__risk-name">{s.supplier_name}</div>
                  <div className="insights__risk-detail">
                    {s.total_documents} document(s) &middot; Confidence:{' '}
                    {s.avg_confidence
                      ? `${(s.avg_confidence * 100).toFixed(1)}%`
                      : 'N/A'}
                    {s.risk_score !== null && ` · Risk Score: ${s.risk_score}`}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="insights__empty">
              No supplier data. Refresh suppliers from the Admin page.
            </div>
          )}
        </>
      )}

      {isReviewerOrAdmin && predictions && (
        <>
          <h2 className="insights__section-title">AI-Generated Insights</h2>
          <div className="insights__ai-cards">
            {(predictions.insights || []).map((insight, i) => (
              <div className="insights__ai-card" key={i}>
                <div className="insights__ai-text">{insight}</div>
              </div>
            ))}
          </div>

          {predictions.spend_forecast?.forecast?.length > 0 && (
            <div className="insights__forecast">
              <h3 className="insights__forecast-title">
                Spend Forecast ({predictions.spend_forecast.method})
              </h3>
              <div className="insights__data-list">
                {predictions.spend_forecast.forecast.map((f) => (
                  <div className="insights__data-row" key={f.month}>
                    <span className="insights__data-label">{f.month}</span>
                    <span className="insights__data-value">
                      ${f.predicted_spend.toLocaleString()} (predicted)
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      <div className="insights__explanation">
        <div className="insights__explanation-title">How These Insights Are Generated</div>
        <div className="insights__explanation-text">
          The IDP Platform uses a combination of Random Forest models for risk classification,
          ARIMA/Prophet for trend forecasting, and Isolation Forest for anomaly detection.
          All models are trained on your organization's historical document processing data
          and are continuously updated as new documents are processed.
        </div>
      </div>
    </div>
  );
}
