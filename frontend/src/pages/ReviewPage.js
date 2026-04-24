import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  getDocumentFields,
  getDocumentCorrections,
  approveDocument,
  rejectDocument,
  getDocumentStatus,
  getDocumentFileUrl,
} from '../api/client';
import { useToast } from '../components/Toast';
import './ReviewPage.css';

export default function ReviewPage() {
  const { documentId: paramId } = useParams();
  const navigate = useNavigate(); // eslint-disable-line no-unused-vars
  const { user } = useAuth();
  const toast = useToast();

  const [docId, setDocId] = useState(paramId || '');
  const [fields, setFields] = useState([]);
  const [corrections, setCorrections] = useState([]);
  const [docStatus, setDocStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [documentBlobUrl, setDocumentBlobUrl] = useState(null);
  const blobUrlRef = useRef(null);

  const isReviewerOrAdmin = user?.role === 'reviewer' || user?.role === 'admin';

  useEffect(() => {
    if (paramId) {
      setDocId(paramId);
      loadData(paramId);
    }
  }, [paramId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    return () => {
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
      }
    };
  }, []);

  const loadData = async (id) => {
    setLoading(true);
    try {
      const [fieldsData, statusData] = await Promise.all([
        getDocumentFields(id),
        getDocumentStatus(id),
      ]);
      setFields(fieldsData);
      setDocStatus(statusData);

      loadDocumentPreview(id);

      if (isReviewerOrAdmin) {
        try {
          const corr = await getDocumentCorrections(id);
          setCorrections(corr);
        } catch {
          setCorrections([]);
        }
      }
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const loadDocumentPreview = async (id) => {
    try {
      const fileUrl = getDocumentFileUrl(id);
      const token = localStorage.getItem('idp_token');
      const response = await fetch(fileUrl, {
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      });
      if (!response.ok) return;
      const blob = await response.blob();
      if (blobUrlRef.current) {
        URL.revokeObjectURL(blobUrlRef.current);
      }
      const blobUrl = URL.createObjectURL(blob);
      blobUrlRef.current = blobUrl;
      setDocumentBlobUrl(blobUrl);
    } catch {
      // Preview not available
    }
  };

  const handleLoad = () => {
    if (!docId.trim()) {
      toast('Please enter a document ID', 'error');
      return;
    }
    loadData(docId.trim());
  };

  const handleApprove = async () => {
    try {
      await approveDocument(docId.trim());
      toast('Document approved', 'success');
      await loadData(docId.trim());
    } catch (err) {
      toast(err.message, 'error');
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) {
      toast('Please provide a rejection reason', 'error');
      return;
    }
    try {
      await rejectDocument(docId.trim(), rejectReason.trim());
      toast('Document rejected', 'success');
      setShowRejectInput(false);
      setRejectReason('');
      await loadData(docId.trim());
    } catch (err) {
      toast(err.message, 'error');
    }
  };

  const isTerminal = docStatus?.status === 'approved' || docStatus?.status === 'rejected';

  const isPdf = docStatus?.filename?.toLowerCase().endsWith('.pdf');

  return (
    <div>
      <h1 className="review__title">Human-in-the-Loop Review</h1>

      {!paramId && (
        <div className="review__input-section">
          <label className="review__input-label">Document ID</label>
          <div className="review__input-row">
            <input
              type="text"
              className="review__input"
              value={docId}
              onChange={(e) => setDocId(e.target.value)}
              placeholder="Enter document ID (UUID)"
            />
            <button className="review__load-btn" onClick={handleLoad}>
              Load Review
            </button>
          </div>
        </div>
      )}

      {loading && (
        <div className="review__loading">Loading review data...</div>
      )}

      {docStatus && (
        <div className={`review__status-banner review__status-banner--${docStatus.status}`}>
          Document: {docStatus.filename || docStatus.document_id} &mdash; Status:{' '}
          <strong>{docStatus.status}</strong>
        </div>
      )}

      {fields.length > 0 && (
        <div className="review__split">
          <div className="review__panel">
            <div className="review__panel-title">Document Preview</div>
            <div className="review__preview">
              {documentBlobUrl ? (
                isPdf ? (
                  <iframe
                    src={documentBlobUrl}
                    title="Document Preview"
                    style={{ width: '100%', height: '600px', border: 'none' }}
                  />
                ) : (
                  <img
                    src={documentBlobUrl}
                    alt="Document Preview"
                    style={{ maxWidth: '100%', height: 'auto' }}
                  />
                )
              ) : (
                <span>Document preview not available</span>
              )}
            </div>
          </div>

          <div className="review__panel">
            <div className="review__panel-title">Extracted Fields</div>
            <div className="review__fields">
              <div className="review__field-row" style={{ fontWeight: 600, fontSize: '12px', color: 'var(--color-text-muted)' }}>
                <span>Field</span>
                <span>Value</span>
                <span>Status</span>
              </div>
              {fields.map((f) => (
                <div className="review__field-row" key={f.id}>
                  <span className="review__field-label">{f.fieldName}</span>
                  <span className={f.status === 'corrected' ? 'review__field-corrected' : 'review__field-value'}>
                    {f.fieldValue || '\u2014'}
                  </span>
                  <span className={`validation__status validation__status--${f.status}`}>
                    {f.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {isReviewerOrAdmin && fields.length > 0 && !isTerminal && (
        <div className="review__actions">
          <button className="review__btn review__btn--approve" onClick={handleApprove}>
            Approve
          </button>
          {showRejectInput ? (
            <div className="review__reject-form">
              <input
                type="text"
                className="review__reject-input"
                placeholder="Reason for rejection"
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                autoFocus
              />
              <button className="review__btn review__btn--reject" onClick={handleReject}>
                Confirm Reject
              </button>
              <button
                className="review__btn review__btn--cancel"
                onClick={() => { setShowRejectInput(false); setRejectReason(''); }}
              >
                Cancel
              </button>
            </div>
          ) : (
            <button
              className="review__btn review__btn--reject"
              onClick={() => setShowRejectInput(true)}
            >
              Reject
            </button>
          )}
        </div>
      )}

      {isTerminal && (
        <div className={`review__final-status review__final-status--${docStatus.status}`}>
          This document has been <strong>{docStatus.status}</strong>.
        </div>
      )}

      {corrections.length > 0 && (
        <div className="review__history">
          <div className="review__history-title">Correction History</div>
          {corrections.map((c, i) => (
            <div className="review__history-item" key={i}>
              <span className="review__history-field">
                {c.field_name}: &ldquo;{c.original_value}&rdquo; &rarr; &ldquo;{c.corrected_value}&rdquo;
              </span>
              <span className="review__history-time">
                {c.corrected_at ? new Date(c.corrected_at).toLocaleString() : ''}
              </span>
            </div>
          ))}
        </div>
      )}

      {!loading && fields.length === 0 && docId && paramId && (
        <div className="review__empty">
          No data available. Process and validate the document first.
        </div>
      )}
    </div>
  );
}
