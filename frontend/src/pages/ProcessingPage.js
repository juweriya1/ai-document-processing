import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { processDocument, getDocumentStatus } from '../api/client';
import { useDocuments } from '../context/DocumentContext';
import { useToast } from '../components/Toast';
import './ProcessingPage.css';

const PIPELINE_STEPS = [
  { key: 'preprocessing', name: 'Preprocessing', desc: 'Image cleanup, deskew, noise removal' },
  { key: 'extracting', name: 'OCR & Extraction', desc: 'Text extraction + field extraction via NER' },
  { key: 'validating', name: 'Validation', desc: 'Schema validation on extracted fields' },
  { key: 'review_pending', name: 'Ready for Review', desc: 'Awaiting human review and approval' },
];

function getStepStatus(stepKey, currentStatus) {
  const order = ['preprocessing', 'extracting', 'validating', 'review_pending'];
  const currentIdx = order.indexOf(currentStatus);
  const stepIdx = order.indexOf(stepKey);
  if (currentIdx < 0) return 'pending';
  if (stepIdx < currentIdx) return 'done';
  if (stepIdx === currentIdx) return 'active';
  return 'pending';
}

export default function ProcessingPage() {
  const { documentId: paramId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { lastProcessing, recentDocId, setProcessingResult, clearProcessingResult } = useDocuments();

  // Initial doc-ID resolution priority:
  //   URL param > most-recent processing result > most-recent uploaded ID > empty
  // This is the "no copy-paste" UX the user asked for.
  const initialDocId = paramId || lastProcessing?.documentId || recentDocId || '';

  const [docId, setDocId] = useState(initialDocId);
  const [processing, setProcessing] = useState(false);
  // Restore last processing result so navigating away and back doesn't blank the page.
  // Only restore when it matches the current docId (otherwise it's stale).
  const [docStatus, setDocStatus] = useState(() => {
    if (lastProcessing && (paramId === lastProcessing.documentId || (!paramId && initialDocId === lastProcessing.documentId))) {
      return lastProcessing.result;
    }
    return null;
  });
  const [error, setError] = useState(null);

  useEffect(() => {
    if (paramId) {
      setDocId(paramId);
      // If the URL param matches the cached result, surface it; otherwise
      // fetch fresh status so we don't show stale data for a different doc.
      if (lastProcessing && lastProcessing.documentId === paramId) {
        setDocStatus(lastProcessing.result);
      } else {
        getDocumentStatus(paramId)
          .then((result) => {
            setDocStatus(result);
            setProcessingResult(paramId, result);
          })
          .catch(() => { /* user can press the button manually */ });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramId]);

  const handleProcess = async () => {
    if (!docId.trim()) {
      toast('Please enter a document ID', 'error');
      return;
    }
    setProcessing(true);
    setError(null);
    try {
      const result = await processDocument(docId.trim());
      const next = {
        document_id: result.document_id,
        status: result.status,
        fields_extracted: result.fields_extracted,
        line_items_extracted: result.line_items_extracted,
      };
      setDocStatus(next);
      setProcessingResult(docId.trim(), next);
      toast(`Processing complete: ${result.fields_extracted} fields extracted`, 'success');
    } catch (err) {
      setError(err.message);
      toast(err.message, 'error');
    } finally {
      setProcessing(false);
    }
  };

  const handleCheckStatus = async () => {
    if (!docId.trim()) {
      toast('Please enter a document ID', 'error');
      return;
    }
    try {
      const result = await getDocumentStatus(docId.trim());
      setDocStatus(result);
      setProcessingResult(docId.trim(), result);
      setError(null);
    } catch (err) {
      setError(err.message);
      toast(err.message, 'error');
    }
  };

  const handleReset = () => {
    clearProcessingResult();
    setDocStatus(null);
    setDocId('');
    setError(null);
  };

  const currentStatus = docStatus?.status || '';

  return (
    <div>
      <h1 className="processing__title">Document Processing</h1>

      <div className="processing__input-section">
        <label className="processing__input-label">Document ID</label>
        <div className="processing__input-row">
          <input
            type="text"
            className="processing__input"
            value={docId}
            onChange={(e) => setDocId(e.target.value)}
            placeholder="Enter document ID (UUID)"
          />
          <button
            className="processing__action-btn"
            onClick={handleProcess}
            disabled={processing}
          >
            {processing ? 'Processing...' : 'Process'}
          </button>
          <button
            className="processing__action-btn processing__action-btn--secondary"
            onClick={handleCheckStatus}
          >
            Check Status
          </button>
          {(docStatus || docId) && (
            <button
              className="processing__action-btn processing__action-btn--secondary"
              onClick={handleReset}
              title="Clear cached result and start fresh"
            >
              Reset
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="processing__error">{error}</div>
      )}

      {docStatus && (
        <div className="processing__doc-card">
          <div className="processing__doc-name">
            {docStatus.filename || `Document ${docStatus.document_id}`}
          </div>
          <div className="processing__doc-meta">
            Status: {docStatus.status}
            {docStatus.fields_extracted != null && ` · ${docStatus.fields_extracted} fields extracted`}
            {docStatus.line_items_extracted != null && ` · ${docStatus.line_items_extracted} line items`}
            {docStatus.uploaded_at && ` · Uploaded ${new Date(docStatus.uploaded_at).toLocaleString()}`}
          </div>
        </div>
      )}

      <div className="processing__steps">
        {PIPELINE_STEPS.map((step) => {
          const status = docStatus ? getStepStatus(step.key, currentStatus) : 'pending';
          return (
            <div className="processing__step" key={step.key}>
              <div className={`processing__step-icon processing__step-icon--${status}`}>
                {status === 'done' ? '\u2713' : status === 'active' ? '\u27A4' : '\u2022'}
              </div>
              <div className="processing__step-content">
                <div className="processing__step-name">{step.name}</div>
                <div className="processing__step-desc">{step.desc}</div>
                {status === 'done' && (
                  <div className="processing__progress-bar">
                    <div className="processing__progress-fill processing__progress-fill--done" style={{ width: '100%' }} />
                  </div>
                )}
              </div>
              <span className={`processing__step-status processing__step-status--${status}`}>
                {status === 'done' ? 'Complete' : status === 'active' ? 'Current' : 'Pending'}
              </span>
            </div>
          );
        })}
      </div>

      {docStatus && (docStatus.status === 'review_pending' || docStatus.status === 'approved' || docStatus.status === 'rejected') && (
        <div className="processing__nav-actions">
          <button
            className="processing__nav-btn"
            onClick={() => navigate(`/validation/${docStatus.document_id}`)}
          >
            View Validation
          </button>
          <button
            className="processing__nav-btn"
            onClick={() => navigate(`/review/${docStatus.document_id}`)}
          >
            Go to Review
          </button>
        </div>
      )}
    </div>
  );
}
