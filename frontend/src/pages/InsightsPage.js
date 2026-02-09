import { useToast } from '../components/Toast';
import './InsightsPage.css';

const RISK_CARDS = [
  { level: 'high', name: 'Delta Supplies Ltd.', detail: 'Invoice anomalies detected in 3 of last 5 submissions. Duplicate amounts flagged.' },
  { level: 'medium', name: 'GlobalTech Services', detail: 'Delivery delays averaging 4.2 days. Payment terms approaching threshold.' },
  { level: 'low', name: 'Reliable Parts Inc.', detail: 'Consistent compliance. All invoices validated within SLA.' },
];

const AI_INSIGHTS = [
  { title: 'Spending Anomaly Detected', text: 'Q1 procurement spending is 18% above forecast. Primary driver: raw materials category increased 34% month-over-month.' },
  { title: 'Duplicate Invoice Risk', text: '3 potential duplicate invoices detected from Delta Supplies. Amounts match within 0.5% tolerance across different invoice numbers.' },
  { title: 'Compliance Improvement', text: 'Automated validation has reduced manual review time by 42% this quarter. Recommend expanding to accounts payable workflow.' },
];

export default function InsightsPage() {
  const toast = useToast();

  const handleAction = () => {
    toast('Coming soon — analytics engine not yet connected', 'info');
  };

  return (
    <div>
      <h1 className="insights__title">Analytics & Insights</h1>
      <div className="placeholder-banner">
        Preview layout — analytics engine will be connected in a future phase.
      </div>

      <div className="insights__charts">
        <div className="insights__chart-card" onClick={handleAction}>
          <div className="insights__chart-title">Spend by Category</div>
          <div className="insights__chart-placeholder">
            Plotly chart will appear when analytics backend is connected
          </div>
        </div>
        <div className="insights__chart-card" onClick={handleAction}>
          <div className="insights__chart-title">Processing Trend (30 days)</div>
          <div className="insights__chart-placeholder">
            Plotly chart will appear when analytics backend is connected
          </div>
        </div>
        <div className="insights__chart-card" onClick={handleAction}>
          <div className="insights__chart-title">Anomaly Detection Timeline</div>
          <div className="insights__chart-placeholder">
            Plotly chart will appear when analytics backend is connected
          </div>
        </div>
      </div>

      <h2 className="insights__section-title">Supplier Risk Assessment</h2>
      <div className="insights__risk-cards">
        {RISK_CARDS.map((card) => (
          <div className={`insights__risk-card insights__risk-card--${card.level}`} key={card.name} onClick={handleAction}>
            <div className="insights__risk-level">{card.level} risk</div>
            <div className="insights__risk-name">{card.name}</div>
            <div className="insights__risk-detail">{card.detail}</div>
          </div>
        ))}
      </div>

      <h2 className="insights__section-title">AI-Generated Insights</h2>
      <div className="insights__ai-cards">
        {AI_INSIGHTS.map((insight) => (
          <div className="insights__ai-card" key={insight.title} onClick={handleAction}>
            <div className="insights__ai-title">{insight.title}</div>
            <div className="insights__ai-text">{insight.text}</div>
          </div>
        ))}
      </div>

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
