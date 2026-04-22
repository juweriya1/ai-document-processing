import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { processDocument, getDocumentStatus } from '../api/client';
import { useToast } from '../components/Toast';
import './ProcessingPage.css';

const STEPS = [
  {
    key: 'preprocessing',
    name: 'Preprocessing',
    desc: 'Image cleanup, deskewing, noise removal and quality enhancement',
    icon: (
      <svg width="16" height="16" viewBox="0 0 20 20" fill="none">
        <rect x="2" y="2" width="16" height="16" rx="3" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M6 10h8M10 6v8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    key: 'extracting',
    name: 'OCR & Field Extraction',
    desc: 'Text extraction via OCR engine + entity recognition using VLM',
    icon: (
      <svg width="16" height="16" viewBox="0 0 20 20" fill="none">
        <path d="M5 3h7l4 4v10a1 1 0 01-1 1H5a1 1 0 01-1-1V4a1 1 0 011-1z" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M7 9h6M7 12h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    key: 'validating',
    name: 'Schema Validation',
    desc: 'Structured field validation against document schema rules',
    icon: (
      <svg width="16" height="16" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M6.5 10l2.5 2.5 4.5-4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    key: 'review_pending',
    name: 'Ready for Review',
    desc: 'Processing complete — awaiting human-in-the-loop review',
    icon: (
      <svg width="16" height="16" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="8" r="4" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M3 18c0-3.3 3.1-6 7-6s7 2.7 7 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
];

const ORDER = ['preprocessing', 'extracting', 'validating', 'review_pending'];

function stepStatus(key, current) {
  const ci = ORDER.indexOf(current);
  const ki = ORDER.indexOf(key);
  if (ci < 0) return 'pending';
  if (ki < ci) return 'done';
  if (ki === ci) return 'active';
  return 'pending';
}

const CheckIcon = () => (
  <svg width="16" height="16" viewBox="0 0 20 20" fill="none">
    <path d="M4 10l4.5 4.5 7.5-8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

const SpinnerSmall = () => (
  <div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} />
);

export default function ProcessingPage() {
  const { documentId: paramId } = useParams();
  const navigate                = useNavigate();
  const toast                   = useToast();

  const [docId, setDocId]         = useState(paramId || '');
  const [processing, setProcessing] = useState(false);
  const [docStatus, setDocStatus] = useState(null);
  const [error, setError]         = useState(null);

  useEffect(() => {
    if (paramId) {
      setDocId(paramId);
      // Auto-load status on arrival
      getDocumentStatus(paramId)
        .then(d => setDocStatus(d))
        .catch(() => {});
    }
  }, [paramId]);

  const handleProcess = async () => {
    if (!docId.trim()) { toast('Please enter a document ID', 'error'); return; }
    setProcessing(true);
    setError(null);
    try {
      const result = await processDocument(docId.trim());
      setDocStatus({
        document_id:           result.document_id,
        status:                result.status,
        fields_extracted:      result.fields_extracted,
        line_items_extracted:  result.line_items_extracted,
      });
      toast(`Processing complete — ${result.fields_extracted} fields extracted`, 'success');
    } catch (err) {
      setError(err.message);
      toast(err.message, 'error');
    } finally {
      setProcessing(false);
    }
  };

  const handleCheckStatus = async () => {
    if (!docId.trim()) { toast('Please enter a document ID', 'error'); return; }
    try {
      const result = await getDocumentStatus(docId.trim());
      setDocStatus(result);
      setError(null);
    } catch (err) {
      setError(err.message);
      toast(err.message, 'error');
    }
  };

  const current = docStatus?.status || '';
  const isTerminal = ['review_pending','approved','rejected','failed'].includes(current);

  return (
    <div className="page-wrap">
      <div className="page-header">
        <h1 className="page-title">Document Processing</h1>
        <p className="page-subtitle">Run the AI pipeline on your uploaded document</p>
      </div>

      {/* Input row */}
      <div className="processing__search-row">
        <div style={{ flex: 1 }}>
          <label className="form-label">Document ID</label>
          <input
            className="form-input"
            type="text"
            value={docId}
            onChange={(e) => setDocId(e.target.value)}
            placeholder="Enter document UUID…"
          />
        </div>
        <button className="btn btn--primary" onClick={handleProcess} disabled={processing}>
          {processing
            ? <><SpinnerSmall /> Processing…</>
            : <>
                <svg width="15" height="15" viewBox="0 0 20 20" fill="none"><path d="M10 4v8M6 8l4-4 4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/><circle cx="10" cy="14" r="2" stroke="currentColor" strokeWidth="1.5"/></svg>
                Process
              </>
          }
        </button>
        <button className="btn btn--secondary" onClick={handleCheckStatus}>
          Check Status
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="processing__error">
          <svg width="16" height="16" viewBox="0 0 20 20" fill="none" style={{flexShrink:0}}>
            <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M10 6v5M10 14v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          {error}
        </div>
      )}

      {/* Document status card */}
      {docStatus && (
        <div className="processing__status-card">
          <div className="processing__doc-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8L14 2z" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M14 2v6h6" stroke="currentColor" strokeWidth="1.5"/>
            </svg>
          </div>
          <div style={{ flex: 1 }}>
            <div className="processing__doc-name">
              {docStatus.filename || `Document ${docStatus.document_id?.slice(0, 8)}…`}
            </div>
            <div className="processing__doc-meta">
              ID: {docStatus.document_id}
              {docStatus.fields_extracted != null && ` · ${docStatus.fields_extracted} fields`}
              {docStatus.line_items_extracted != null && ` · ${docStatus.line_items_extracted} line items`}
            </div>
          </div>
          <span className={`badge ${
            current === 'approved'      ? 'badge--success' :
            current === 'rejected'      ? 'badge--error'   :
            current === 'review_pending'? 'badge--accent'  :
            current === 'failed'        ? 'badge--error'   :
            'badge--warning'
          }`}>
            {current.replace(/_/g,' ')}
          </span>
        </div>
      )}

      {/* Pipeline steps */}
      <div className="card" style={{ marginBottom: 'var(--sp-6)' }}>
        <div className="card-title">Processing Pipeline</div>
        <div className="pipeline">
          {STEPS.map((step, idx) => {
            const status = docStatus ? stepStatus(step.key, current) : 'pending';
            return (
              <div
                className={`pipeline__step pipeline__step--${status} animate-slide-up`}
                key={step.key}
                style={{ animationDelay: `${idx * 80}ms` }}
              >
                <div className="pipeline__icon">
                  {status === 'done'   ? <CheckIcon /> :
                   status === 'active' && processing ? <SpinnerSmall /> :
                   step.icon}
                </div>
                <div className="pipeline__body">
                  <div className="pipeline__step-header">
                    <span className="pipeline__step-name">{step.name}</span>
                    <span className="pipeline__step-status">
                      {status === 'done'   ? '✓ Complete' :
                       status === 'active' ? (processing ? 'Running…' : 'Current') :
                       'Pending'}
                    </span>
                  </div>
                  <div className="pipeline__step-desc">{step.desc}</div>
                  {status === 'active' && (
                    <div className="pipeline__progress-bar">
                      <div className={`pipeline__progress-fill${processing ? '' : ' pipeline__progress-fill--done'}`}
                        style={!processing ? { width: '100%', animation: 'none', background: 'var(--accent)' } : {}} />
                    </div>
                  )}
                  {status === 'done' && (
                    <div className="pipeline__progress-bar">
                      <div className="pipeline__progress-fill pipeline__progress-fill--done" style={{ width: '100%' }} />
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Nav actions when ready */}
      {isTerminal && (
        <div className="processing__nav">
          <button className="btn btn--primary" onClick={() => navigate(`/validation/${docStatus.document_id}`)}>
            <svg width="14" height="14" viewBox="0 0 20 20" fill="none"><path d="M10 2l2 5.5H18l-4.9 3.6 1.9 5.6L10 13.3l-5 3.4 1.9-5.6L2 7.5h6L10 2z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>
            Validate Fields
          </button>
          <button className="btn btn--secondary" onClick={() => navigate(`/review/${docStatus.document_id}`)}>
            <svg width="14" height="14" viewBox="0 0 20 20" fill="none"><path d="M10 4C6 4 2.7 7.6 2 10c.7 2.4 4 6 8 6s7.3-3.6 8-6c-.7-2.4-4-6-8-6z" stroke="currentColor" strokeWidth="1.5"/><circle cx="10" cy="10" r="2.5" stroke="currentColor" strokeWidth="1.5"/></svg>
            Review Document
          </button>
        </div>
      )}
    </div>
  );
}
