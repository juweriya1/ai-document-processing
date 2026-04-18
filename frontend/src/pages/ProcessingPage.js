import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { processDocument, getDocumentStatus } from '../api/client';
import { useToast } from '../components/Toast';
import './ProcessingPage.css';

const STEPS = [
  { key: 'preprocessing',  name: 'Preprocessing',    desc: 'Image cleanup, deskew, noise removal' },
  { key: 'extracting',     name: 'OCR & Extraction', desc: 'Text + field extraction via NER' },
  { key: 'validating',     name: 'Validation',       desc: 'Schema validation on extracted fields' },
  { key: 'review_pending', name: 'Awaiting Review',  desc: 'Queued for human-in-the-loop review' },
];
const ORDER = STEPS.map(s => s.key);

function stepStatus(key, current) {
  const ci = ORDER.indexOf(current);
  const si = ORDER.indexOf(key);
  if (ci < 0) return 'pending';
  if (si < ci) return 'done';
  if (si === ci) return 'active';
  return 'pending';
}

const DocIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8L14 2z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>
  </svg>
);
const CheckSm = () => (
  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round"><path d="M20 6L9 17l-5-5"/></svg>
);

export default function ProcessingPage() {
  const { documentId: paramId } = useParams();
  const navigate = useNavigate();
  const toast    = useToast();

  const [docId, setDocId]         = useState(paramId || '');
  const [processing, setProcessing] = useState(false);
  const [docStatus, setDocStatus] = useState(null);
  const [error, setError]         = useState(null);

  useEffect(() => { if (paramId) setDocId(paramId); }, [paramId]);

  const handleProcess = async () => {
    if (!docId.trim()) { toast('Please enter a document ID', 'error'); return; }
    setProcessing(true); setError(null);
    try {
      const r = await processDocument(docId.trim());
      setDocStatus({ document_id: r.document_id, status: r.status, fields_extracted: r.fields_extracted, line_items_extracted: r.line_items_extracted });
      toast(`Processing complete — ${r.fields_extracted} fields extracted`, 'success');
    } catch (err) { setError(err.message); toast(err.message, 'error'); }
    finally { setProcessing(false); }
  };

  const handleCheck = async () => {
    if (!docId.trim()) { toast('Please enter a document ID', 'error'); return; }
    try {
      const r = await getDocumentStatus(docId.trim());
      setDocStatus(r); setError(null);
    } catch (err) { setError(err.message); toast(err.message, 'error'); }
  };

  const current = docStatus?.status || '';
  const terminal = ['review_pending','approved','rejected'].includes(current);

  return (
    <div className="page-wrap">
      <div className="page-hd">
        <div>
          <h1 className="page-title">Document Processing</h1>
          <p className="page-subtitle">Run the AI pipeline and monitor extraction progress</p>
        </div>
      </div>

      {/* Input */}
      <div className="field" style={{ marginBottom: 16 }}>
        <label className="field-label">Document ID</label>
        <div className="proc-input-row">
          <input className="field-input" type="text" value={docId}
            onChange={e => setDocId(e.target.value)} placeholder="Enter document UUID…" />
          <button className="btn btn-primary" onClick={handleProcess} disabled={processing}>
            {processing ? <><span className="spinner" /> Processing…</> : 'Run Pipeline'}
          </button>
          <button className="btn btn-ghost" onClick={handleCheck}>Check Status</button>
        </div>
      </div>

      {error && <div className="alert alert--error" style={{ marginBottom:16 }}>{error}</div>}

      {/* Doc info card */}
      {docStatus && (
        <div className="proc-doc-card">
          <div className="proc-doc-card__icon"><DocIcon /></div>
          <div>
            <div className="proc-doc-card__name">{docStatus.filename || `Document — ${docStatus.document_id}`}</div>
            <div className="proc-doc-card__meta">
              Status: <strong>{current}</strong>
              {docStatus.fields_extracted != null && ` · ${docStatus.fields_extracted} fields extracted`}
              {docStatus.line_items_extracted != null && ` · ${docStatus.line_items_extracted} line items`}
              {docStatus.uploaded_at && ` · ${new Date(docStatus.uploaded_at).toLocaleString()}`}
            </div>
          </div>
        </div>
      )}

      {/* Stepper */}
      <div className="card">
        <div className="card-title">Pipeline Progress</div>
        <div className="stepper">
          {STEPS.map((s, i) => {
            const st = docStatus ? stepStatus(s.key, current) : 'pending';
            return (
              <div key={s.key} className={`step step--${st}`}>
                <div className="step__indicator">
                  {st === 'done' ? <CheckSm /> : <span>{i + 1}</span>}
                </div>
                <div className="step__body">
                  <div className="step__name">
                    {s.name}
                    <span className={`badge step__status-pill ${st === 'done' ? 'badge--success' : st === 'active' ? 'badge--accent' : 'badge--default'}`}>
                      {st === 'done' ? 'Complete' : st === 'active' ? 'In Progress' : 'Pending'}
                    </span>
                  </div>
                  <div className="step__desc">{s.desc}</div>
                  {st === 'done' && (
                    <div className="step__progress">
                      <div className="step__progress-fill" style={{ width:'100%' }} />
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Navigation actions */}
      {docStatus && terminal && (
        <div className="proc-nav-actions">
          <button className="btn btn-ghost" onClick={() => navigate(`/validation/${docStatus.document_id}`)}>
            View Validation →
          </button>
          <button className="btn btn-primary" onClick={() => navigate(`/review/${docStatus.document_id}`)}>
            Go to Review →
          </button>
        </div>
      )}
    </div>
  );
}
