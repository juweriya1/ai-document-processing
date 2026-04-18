import { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getDocumentFields, getDocumentCorrections, approveDocument, rejectDocument, getDocumentStatus, getDocumentFileUrl } from '../api/client';
import { useToast } from '../components/Toast';
import './ReviewPage.css';

function statusBadgeClass(s) {
  return s === 'valid' ? 'badge--success' : s === 'invalid' ? 'badge--danger' : s === 'corrected' ? 'badge--info' : 'badge--default';
}

const CheckIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M20 6L9 17l-5-5"/></svg>
);
const XIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
);

export default function ReviewPage() {
  const { documentId: paramId } = useParams();
  const { user } = useAuth();
  const toast    = useToast();

  const [docId, setDocId]         = useState(paramId || '');
  const [fields, setFields]       = useState([]);
  const [corrections, setCorr]    = useState([]);
  const [docStatus, setDocStatus] = useState(null);
  const [loading, setLoading]     = useState(false);
  const [rejectReason, setReason] = useState('');
  const [showReject, setShowReject] = useState(false);
  const [blobUrl, setBlobUrl]     = useState(null);
  const blobRef = useRef(null);

  const canAct = user?.role === 'reviewer' || user?.role === 'admin';

  useEffect(() => { if (paramId) { setDocId(paramId); loadAll(paramId); } }, [paramId]); // eslint-disable-line
  useEffect(() => () => { if (blobRef.current) URL.revokeObjectURL(blobRef.current); }, []);

  const loadAll = async (id) => {
    setLoading(true);
    try {
      const [f, s] = await Promise.all([getDocumentFields(id), getDocumentStatus(id)]);
      setFields(f); setDocStatus(s);
      loadPreview(id);
      if (canAct) { try { setCorr(await getDocumentCorrections(id)); } catch { setCorr([]); } }
    } catch (err) { toast(err.message, 'error'); }
    finally { setLoading(false); }
  };

  const loadPreview = async (id) => {
    try {
      const url = getDocumentFileUrl(id);
      const token = localStorage.getItem('idp_token');
      const res = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
      if (!res.ok) return;
      const blob = await res.blob();
      if (blobRef.current) URL.revokeObjectURL(blobRef.current);
      const bu = URL.createObjectURL(blob);
      blobRef.current = bu; setBlobUrl(bu);
    } catch { /* preview unavailable */ }
  };

  const handleApprove = async () => {
    try { await approveDocument(docId.trim()); toast('Document approved ✓', 'success'); await loadAll(docId.trim()); }
    catch (err) { toast(err.message, 'error'); }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) { toast('Please provide a rejection reason', 'error'); return; }
    try {
      await rejectDocument(docId.trim(), rejectReason.trim());
      toast('Document rejected', 'info');
      setShowReject(false); setReason('');
      await loadAll(docId.trim());
    } catch (err) { toast(err.message, 'error'); }
  };

  const isTerminal = docStatus?.status === 'approved' || docStatus?.status === 'rejected';
  const isPdf      = docStatus?.filename?.toLowerCase().endsWith('.pdf');
  const bannerCls  = docStatus?.status ? `review-banner--${docStatus.status}` : 'review-banner--default';

  return (
    <div className="page-wrap">
      <div className="page-hd">
        <div>
          <h1 className="page-title">Human-in-the-Loop Review</h1>
          <p className="page-subtitle">Inspect extracted data and approve or reject the document</p>
        </div>
      </div>

      {/* Doc ID entry */}
      {!paramId && (
        <div className="field" style={{ marginBottom: 20 }}>
          <label className="field-label">Document ID</label>
          <div style={{ display:'flex', gap:10 }}>
            <input className="field-input" type="text" value={docId}
              onChange={e => setDocId(e.target.value)} placeholder="Enter document UUID…" />
            <button className="btn btn-ghost" onClick={() => loadAll(docId.trim())}>Load Review</button>
          </div>
        </div>
      )}

      {loading && <div className="val-loading" style={{ paddingTop: 24 }}><span className="spinner" /> Loading review data…</div>}

      {/* Status banner */}
      {docStatus && !loading && (
        <div className={`review-banner ${bannerCls}`}>
          <strong>{docStatus.filename || docStatus.document_id}</strong>
          <span>—</span>
          <span>Status: <strong>{docStatus.status}</strong></span>
        </div>
      )}

      {/* Final state indicator */}
      {isTerminal && (
        <div className={`review-final review-final--${docStatus.status}`}>
          {docStatus.status === 'approved' ? <CheckIcon /> : <XIcon />}
          This document has been <strong>{docStatus.status}</strong>.
        </div>
      )}

      {/* Action buttons */}
      {canAct && fields.length > 0 && !isTerminal && (
        <div className="review-actions">
          <button className="btn btn-success" onClick={handleApprove}><CheckIcon /> Approve</button>
          {showReject ? (
            <div className="review-reject-form">
              <input className="review-reject-input" placeholder="Reason for rejection…"
                value={rejectReason} onChange={e => setReason(e.target.value)} autoFocus
                onKeyDown={e => e.key === 'Enter' && handleReject()} />
              <button className="btn btn-danger" onClick={handleReject}><XIcon /> Confirm Reject</button>
              <button className="btn btn-ghost" onClick={() => { setShowReject(false); setReason(''); }}>Cancel</button>
            </div>
          ) : (
            <button className="btn btn-danger" onClick={() => setShowReject(true)}><XIcon /> Reject</button>
          )}
        </div>
      )}

      {/* Split pane */}
      {!loading && fields.length > 0 && (
        <div className="review-split">
          {/* Preview */}
          <div className="card" style={{ padding: 0, overflow:'hidden' }}>
            <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)' }}>
              <div className="card-title" style={{ margin: 0 }}>Document Preview</div>
            </div>
            <div className="review-preview">
              {blobUrl ? (
                isPdf ? (
                  <iframe src={blobUrl} title="Document Preview" style={{ width:'100%', height:'540px', border:'none' }} />
                ) : (
                  <img src={blobUrl} alt="Document Preview" style={{ maxWidth:'100%', height:'auto' }} />
                )
              ) : (
                <span>Preview not available</span>
              )}
            </div>
          </div>

          {/* Fields */}
          <div className="card">
            <div className="card-title">Extracted Fields ({fields.length})</div>
            <div className="review-fields">
              <div className="review-field-row" style={{ fontWeight:700, fontSize:'11px', textTransform:'uppercase', letterSpacing:'0.5px', color:'var(--text-3)', border:'none', paddingBottom:4 }}>
                <span>Field</span><span>Value</span><span>Status</span>
              </div>
              {fields.map(f => (
                <div className="review-field-row" key={f.id}>
                  <span className="review-field-row__name">{f.fieldName}</span>
                  <span className={`review-field-row__value${f.status === 'corrected' ? ' review-field-row__value--corrected' : ''}`}>
                    {f.fieldValue || '—'}
                  </span>
                  <span className={`badge ${statusBadgeClass(f.status)}`}>{f.status}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Correction history */}
      {corrections.length > 0 && (
        <>
          <h2 className="section-title">Correction History</h2>
          <div className="history-list">
            {corrections.map((c, i) => (
              <div className="history-item" key={i}>
                <span className="history-item__field">
                  <strong>{c.field_name}:</strong> "{c.original_value}" → "{c.corrected_value}"
                </span>
                <span className="history-item__time">
                  {c.corrected_at ? new Date(c.corrected_at).toLocaleString() : ''}
                </span>
              </div>
            ))}
          </div>
        </>
      )}

      {!loading && fields.length === 0 && docId && paramId && (
        <div className="empty-state" style={{ marginTop: 40 }}>
          <span style={{ fontSize: 32 }}>🔍</span>
          No data available. Process and validate the document first.
        </div>
      )}
    </div>
  );
}
