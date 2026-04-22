import { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  getDocumentFields, getDocumentCorrections,
  approveDocument, rejectDocument,
  getDocumentStatus, getDocumentFileUrl,
} from '../api/client';
import { useToast } from '../components/Toast';
import './ReviewPage.css';

export default function ReviewPage() {
  const { documentId: paramId } = useParams();
  const { user }                = useAuth();
  const toast                   = useToast();

  const [docId, setDocId]               = useState(paramId || '');
  const [fields, setFields]             = useState([]);
  const [corrections, setCorrections]   = useState([]);
  const [docStatus, setDocStatus]       = useState(null);
  const [loading, setLoading]           = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [showReject, setShowReject]     = useState(false);
  const [blobUrl, setBlobUrl]           = useState(null);
  const blobRef                         = useRef(null);

  const canReview = user?.role === 'reviewer' || user?.role === 'admin';

  useEffect(() => {
    if (paramId) { setDocId(paramId); loadAll(paramId); }
    return () => { if (blobRef.current) URL.revokeObjectURL(blobRef.current); };
  }, [paramId]); // eslint-disable-line

  const loadAll = async (id) => {
    setLoading(true);
    try {
      const [f, s] = await Promise.all([getDocumentFields(id), getDocumentStatus(id)]);
      setFields(f);
      setDocStatus(s);
      loadPreview(id);
      if (canReview) {
        try { setCorrections(await getDocumentCorrections(id)); } catch { setCorrections([]); }
      }
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const loadPreview = async (id) => {
    try {
      const url   = getDocumentFileUrl(id);
      const token = localStorage.getItem('idp_token');
      const res   = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
      if (!res.ok) return;
      const blob = await res.blob();
      if (blobRef.current) URL.revokeObjectURL(blobRef.current);
      const created  = URL.createObjectURL(blob);
      blobRef.current = created;
      setBlobUrl(created);
    } catch {}
  };

  const handleLoad = () => {
    if (!docId.trim()) { toast('Please enter a document ID', 'error'); return; }
    loadAll(docId.trim());
  };

  const handleApprove = async () => {
    try {
      await approveDocument(docId.trim());
      toast('Document approved', 'success');
      await loadAll(docId.trim());
    } catch (err) {
      toast(err.message, 'error');
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) { toast('Please provide a rejection reason', 'error'); return; }
    try {
      await rejectDocument(docId.trim(), rejectReason.trim());
      toast('Document rejected', 'success');
      setShowReject(false);
      setRejectReason('');
      await loadAll(docId.trim());
    } catch (err) {
      toast(err.message, 'error');
    }
  };

  const status     = docStatus?.status || '';
  const isTerminal = status === 'approved' || status === 'rejected';
  const isPdf      = docStatus?.filename?.toLowerCase().endsWith('.pdf');

  return (
    <div className="page-wrap">
      <div className="page-header">
        <h1 className="page-title">Human-in-the-Loop Review</h1>
        <p className="page-subtitle">Verify extracted data and approve or reject documents</p>
      </div>

      {/* Manual load input */}
      {!paramId && (
        <div style={{ display: 'flex', gap: 'var(--sp-3)', marginBottom: 'var(--sp-6)', alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <label className="form-label">Document ID</label>
            <input
              className="form-input"
              value={docId}
              onChange={(e) => setDocId(e.target.value)}
              placeholder="Enter document UUID…"
            />
          </div>
          <button className="btn btn--primary" onClick={handleLoad}>Load</button>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div style={{ display: 'flex', gap: 'var(--sp-3)', padding: 'var(--sp-8)', justifyContent: 'center', color: 'var(--text-4)' }}>
          <div className="spinner" /> Loading review data…
        </div>
      )}

      {/* Status banner */}
      {docStatus && (
        <div className={`review__status-banner review__status-banner--${status}`}>
          <svg width="16" height="16" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M10 6v5M10 14v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <span>
            <strong>{docStatus.filename || docStatus.document_id}</strong>
            {' · '}Status: <strong>{status.replace(/_/g,' ')}</strong>
            {docStatus.uploaded_at && ` · Uploaded ${new Date(docStatus.uploaded_at).toLocaleString()}`}
          </span>
        </div>
      )}

      {/* Split panel: preview + fields */}
      {fields.length > 0 && (
        <div className="review__split">
          {/* Document preview */}
          <div className="review__panel">
            <div className="review__panel-header">
              <span className="review__panel-title">Document Preview</span>
              {blobUrl && (
                <a href={blobUrl} download={docStatus?.filename} className="btn btn--ghost btn--sm">
                  <svg width="12" height="12" viewBox="0 0 20 20" fill="none"><path d="M10 4v8M10 12l-3-3M10 12l3-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/><path d="M3 15h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
                  Download
                </a>
              )}
            </div>
            <div className="review__panel-body">
              <div className="review__preview">
                {blobUrl
                  ? isPdf
                    ? <iframe src={blobUrl} title="Document Preview" />
                    : <img src={blobUrl} alt="Document Preview" />
                  : (
                    <div className="review__preview-placeholder">
                      <svg width="40" height="40" viewBox="0 0 24 24" fill="none">
                        <rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" strokeWidth="1.5"/>
                        <path d="M3 9h18" stroke="currentColor" strokeWidth="1.5"/>
                      </svg>
                      <span>Preview not available</span>
                    </div>
                  )
                }
              </div>
            </div>
          </div>

          {/* Extracted fields */}
          <div className="review__panel">
            <div className="review__panel-header">
              <span className="review__panel-title">Extracted Fields</span>
              <span style={{ fontSize: 11, color: 'var(--text-4)' }}>{fields.length} fields</span>
            </div>
            <div className="review__panel-body">
              <div className="review__fields-list">
                {fields.map((f, idx) => (
                  <div
                    className="review__field-row animate-fade-in"
                    key={f.id}
                    style={{ animationDelay: `${idx * 20}ms` }}
                  >
                    <span className="review__field-name">{f.fieldName}</span>
                    <span className={`review__field-value${f.status === 'corrected' ? ' review__field-value--corrected' : ''}`}>
                      {f.fieldValue || '—'}
                    </span>
                    <span className={`vs-pill vs-pill--${f.status}`} style={{fontSize:10}}>
                      {f.status}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Terminal state */}
      {isTerminal && (
        <div className={`review__final review__final--${status}`}>
          <div className="review__final-icon">
            {status === 'approved'
              ? <svg width="28" height="28" viewBox="0 0 24 24" fill="none"><path d="M5 12l5 5 9-9" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
              : <svg width="28" height="28" viewBox="0 0 24 24" fill="none"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>
            }
          </div>
          <div className="review__final-title">
            Document {status === 'approved' ? 'Approved' : 'Rejected'}
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-4)', marginTop: 4 }}>
            This document has been {status} and no further action is required
          </div>
        </div>
      )}

      {/* Review actions */}
      {canReview && fields.length > 0 && !isTerminal && (
        <div className="review__action-bar">
          <div className="review__action-bar__label">
            <strong style={{ color: 'var(--text-1)' }}>Ready to review?</strong>
            <span> Approve if the extracted data looks correct, or reject with a reason.</span>
          </div>
          <button className="btn btn--success" onClick={handleApprove}>
            <svg width="15" height="15" viewBox="0 0 20 20" fill="none"><path d="M4 10l4.5 4.5 7.5-8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
            Approve
          </button>
          <button className="btn btn--danger" onClick={() => setShowReject(!showReject)}>
            <svg width="15" height="15" viewBox="0 0 20 20" fill="none"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
            Reject
          </button>
          {showReject && (
            <div className="review__reject-row">
              <input
                className="form-input"
                placeholder="Reason for rejection…"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                autoFocus
              />
              <button className="btn btn--danger" onClick={handleReject}>Confirm Reject</button>
              <button className="btn btn--ghost" onClick={() => { setShowReject(false); setRejectReason(''); }}>Cancel</button>
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {!loading && fields.length === 0 && docId && (
        <div className="empty-state">
          <svg className="empty-state__icon" viewBox="0 0 24 24" fill="none"><path d="M10 4C6 4 2.7 7.6 2 10c.7 2.4 4 6 8 6s7.3-3.6 8-6c-.7-2.4-4-6-8-6z" stroke="currentColor" strokeWidth="1.5"/><circle cx="10" cy="10" r="2.5" stroke="currentColor" strokeWidth="1.5"/></svg>
          <div className="empty-state__title">No review data available</div>
          <div className="empty-state__desc">Process and validate the document before reviewing</div>
        </div>
      )}

      {/* Corrections history */}
      {corrections.length > 0 && (
        <div className="review__history" style={{ marginTop: 'var(--sp-6)' }}>
          <div className="review__history-header">Correction History</div>
          {corrections.map((c, i) => (
            <div className="review__history-item" key={i}>
              <span className="review__history-field">
                {c.field_name}: "{c.original_value}" → "{c.corrected_value}"
              </span>
              <span className="review__history-time">
                {c.corrected_at ? new Date(c.corrected_at).toLocaleString() : ''}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
