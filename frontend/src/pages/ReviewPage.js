import { useToast } from '../components/Toast';
import './ReviewPage.css';

const MOCK_FIELDS = [
  { label: 'Invoice #', ocr: 'INV-2024-03I2', corrected: 'INV-2024-0312' },
  { label: 'Date', ocr: '2024-O3-15', corrected: '2024-03-15' },
  { label: 'Vendor', ocr: 'Acme Corp', corrected: 'Acme Corp.' },
  { label: 'Amount', ocr: '$14,58O.OO', corrected: '$14,580.00' },
  { label: 'PO Number', ocr: '', corrected: 'PO-2024-0089' },
];

const HISTORY = [
  { field: 'Invoice #', change: 'I \u2192 1 (OCR correction)', time: '2 min ago' },
  { field: 'Date', change: 'O \u2192 0 (OCR correction)', time: '2 min ago' },
  { field: 'PO Number', change: 'Added manually', time: '1 min ago' },
];

export default function ReviewPage() {
  const toast = useToast();

  const handleAction = () => {
    toast('Coming soon — HITL review not yet connected', 'info');
  };

  return (
    <div>
      <h1 className="review__title">Human-in-the-Loop Review</h1>
      <div className="placeholder-banner">
        Preview layout — HITL review will be connected in a future phase.
      </div>

      <div className="review__split">
        <div className="review__panel">
          <div className="review__panel-title">Document Preview</div>
          <div className="review__preview">
            Invoice preview will render here when OCR pipeline is connected
          </div>
        </div>

        <div className="review__panel">
          <div className="review__panel-title">Extracted Fields</div>
          <div className="review__fields">
            <div className="review__field-row" style={{ fontWeight: 600, fontSize: '12px', color: 'var(--color-text-muted)' }}>
              <span>Field</span>
              <span>OCR Output</span>
              <span>Corrected</span>
            </div>
            {MOCK_FIELDS.map((f) => (
              <div className="review__field-row" key={f.label}>
                <span className="review__field-label">{f.label}</span>
                <span className="review__field-ocr">{f.ocr || '\u2014'}</span>
                <span className="review__field-corrected">{f.corrected}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="review__actions">
        <button className="review__btn review__btn--approve" onClick={handleAction}>
          Approve
        </button>
        <button className="review__btn review__btn--reject" onClick={handleAction}>
          Reject
        </button>
      </div>

      <div className="review__history">
        <div className="review__history-title">Correction History</div>
        {HISTORY.map((h, i) => (
          <div className="review__history-item" key={i}>
            <span className="review__history-field">{h.field}: {h.change}</span>
            <span className="review__history-time">{h.time}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
