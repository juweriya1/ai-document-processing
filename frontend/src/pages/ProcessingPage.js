import { useToast } from '../components/Toast';
import './ProcessingPage.css';

const STEPS = [
  { name: 'Preprocessing', desc: 'Image cleanup, deskew, noise removal', progress: 100, status: 'done' },
  { name: 'OCR', desc: 'Text extraction via Tesseract + EasyOCR', progress: 42, status: 'active' },
  { name: 'Layout Analysis', desc: 'Detecting tables, headers, paragraphs', progress: 0, status: 'pending' },
  { name: 'Field Extraction', desc: 'NER + regex for invoice fields', progress: 0, status: 'pending' },
];

export default function ProcessingPage() {
  const toast = useToast();

  const handleAction = () => {
    toast('Coming soon — processing pipeline not yet connected', 'info');
  };

  return (
    <div>
      <h1 className="processing__title">Document Processing</h1>
      <div className="placeholder-banner">
        Preview layout — processing pipeline will be connected in a future phase.
      </div>

      <div className="processing__doc-card">
        <div className="processing__doc-name">invoice_2024_march.pdf</div>
        <div className="processing__doc-meta">
          Uploaded 2 minutes ago &middot; 2.4 MB &middot; PDF
        </div>
      </div>

      <div className="processing__steps">
        {STEPS.map((step) => (
          <div className="processing__step" key={step.name} onClick={handleAction}>
            <div className={`processing__step-icon processing__step-icon--${step.status}`}>
              {step.status === 'done' ? '\u2713' : step.status === 'active' ? '\u27A4' : '\u2022'}
            </div>
            <div className="processing__step-content">
              <div className="processing__step-name">{step.name}</div>
              <div className="processing__step-desc">{step.desc}</div>
              {step.status !== 'pending' && (
                <div className="processing__progress-bar">
                  <div
                    className={`processing__progress-fill processing__progress-fill--${step.status}`}
                    style={{ width: `${step.progress}%` }}
                  />
                </div>
              )}
            </div>
            <span className={`processing__step-status processing__step-status--${step.status}`}>
              {step.status === 'done' ? 'Complete' : step.status === 'active' ? `${step.progress}%` : 'Pending'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
