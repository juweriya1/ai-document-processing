import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useDocuments } from '../context/DocumentContext';
import {
  getDocumentFields,
  getDocumentCorrections,
  approveDocument,
  rejectDocument,
  getDocumentStatus,
  submitCorrection,
} from '../api/client';
import { useToast } from '../components/Toast';
import DocumentViewer from '../components/DocumentViewer';
import './ReviewPage.css';

// Pull the most recent verifier verdict out of the traceability_log so it
// can be surfaced in the trace pane. The auditor_node writes a "verifier"
// detail block on every audit pass; we want the latest one (the
// post-Tier-2 verdict, when there was a Tier 2).
function pickLatestVerifierVerdict(traceabilityLog) {
  if (!Array.isArray(traceabilityLog)) return null;
  for (let i = traceabilityLog.length - 1; i >= 0; i -= 1) {
    const entry = traceabilityLog[i];
    if (entry?.stage === 'audit' && entry?.detail?.verifier) {
      return entry.detail.verifier;
    }
  }
  return null;
}

export default function ReviewPage() {
  const { documentId: paramId } = useParams();
  const navigate = useNavigate(); // eslint-disable-line no-unused-vars
  const { user } = useAuth();
  const { recentDocId, recentBatch, setRecentDocId } = useDocuments();
  const toast = useToast();

  // Pre-fill priority: URL param > recent single-doc upload > first doc
  // in last batch. Avoids the user re-typing the doc ID they just uploaded.
  const initialDocId = paramId || recentDocId || recentBatch?.documentIds?.[0] || '';

  const [docId, setDocId] = useState(initialDocId);
  const [fields, setFields] = useState([]);
  const [corrections, setCorrections] = useState([]);
  const [docStatus, setDocStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [editingField, setEditingField] = useState(null);
  const [editValue, setEditValue] = useState('');

  const isReviewerOrAdmin = user?.role === 'reviewer' || user?.role === 'admin';

  // Auto-load on URL param OR when a non-empty doc ID is pre-filled at mount.
  useEffect(() => {
    const id = paramId || initialDocId;
    if (id) {
      setDocId(id);
      loadData(id);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramId]);

  const loadData = async (id) => {
    setLoading(true);
    try {
      const [fieldsData, statusData] = await Promise.all([
        getDocumentFields(id),
        getDocumentStatus(id),
      ]);
      setFields(fieldsData);
      setDocStatus(statusData);

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

  const handleStartEdit = (field) => {
    setEditingField(field.id);
    setEditValue(field.fieldValue || '');
  };

  const handleCancelEdit = () => {
    setEditingField(null);
    setEditValue('');
  };

  const handleSaveEdit = async (fieldId) => {
    try {
      await submitCorrection(docId.trim(), fieldId, editValue);
      toast('Correction saved', 'success');
      setEditingField(null);
      setEditValue('');
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

  // Verifier verdict from the latest auditor pass — if a Tier 2 ran, this
  // reflects the post-reconciliation plausibility, not the pre-Tier-2 one.
  const verifierVerdict = pickLatestVerifierVerdict(docStatus?.traceability_log);

  return (
    <div>
      <h1 className="review__title">Human-in-the-Loop Review</h1>

      {!paramId && (
        <div className="review__input-section">
          <label className="review__input-label">Document ID</label>
          <div className="review__input-row">
            {recentBatch?.documentIds?.length > 1 ? (
              <select
                className="review__input"
                value={docId}
                onChange={(e) => {
                  setDocId(e.target.value);
                  setRecentDocId(e.target.value);
                }}
              >
                <option value="">Select a document from your last batch…</option>
                {recentBatch.documentIds.map((id, i) => (
                  <option key={id} value={id}>
                    Doc {i + 1} — {id.slice(0, 12)}…
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                className="review__input"
                value={docId}
                onChange={(e) => setDocId(e.target.value)}
                placeholder="Enter document ID (UUID)"
              />
            )}
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
          <div className="review__panel review__panel--preview">
            <div className="review__panel-title">Document Preview</div>
            <div className="review__preview">
              <DocumentViewer documentId={docId.trim()} filename={docStatus?.filename} />
            </div>
            {verifierVerdict && !verifierVerdict.skipped && (
              <div
                className={
                  verifierVerdict.ok
                    ? 'review__verifier review__verifier--ok'
                    : 'review__verifier review__verifier--flag'
                }
              >
                <div className="review__verifier-row">
                  <strong>Plausibility verifier:</strong>{' '}
                  {verifierVerdict.ok ? 'PASSED' : 'FLAGGED'}
                  {' '}— score{' '}
                  <strong>{(verifierVerdict.score ?? 0).toFixed(3)}</strong>
                  {' '}/ threshold {(verifierVerdict.threshold ?? 0).toFixed(3)}
                </div>
                {Array.isArray(verifierVerdict.top_features) &&
                  verifierVerdict.top_features.length > 0 && (
                    <div className="review__verifier-row">
                      <span className="review__verifier-sub">
                        Top deviating features:
                      </span>{' '}
                      {verifierVerdict.top_features
                        .map((f) => `${f.name} (${(f.contribution ?? 0).toFixed(3)})`)
                        .join(' · ')}
                    </div>
                  )}
              </div>
            )}
            {verifierVerdict && verifierVerdict.skipped && (
              <div className="review__verifier review__verifier--skipped">
                Plausibility verifier: skipped ({verifierVerdict.reason || 'no model loaded'})
              </div>
            )}
          </div>

          <div className="review__panel review__panel--fields">
            <div className="review__panel-title">Extracted Fields</div>
            <div className="review__fields">
              <div className="review__field-row review__field-row--header">
                <span>Field</span>
                <span>Value</span>
                <span>Status</span>
                {!isTerminal && <span>Actions</span>}
              </div>
              {fields.map((f) => {
                const editing = editingField === f.id;
                return (
                  <div className="review__field-row" key={f.id}>
                    <span className="review__field-label">{f.fieldName}</span>
                    {editing ? (
                      <input
                        type="text"
                        className="review__edit-input"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleSaveEdit(f.id);
                          if (e.key === 'Escape') handleCancelEdit();
                        }}
                        autoFocus
                      />
                    ) : (
                      <span
                        className={
                          f.status === 'corrected'
                            ? 'review__field-corrected'
                            : 'review__field-value'
                        }
                      >
                        {f.fieldValue || '\u2014'}
                      </span>
                    )}
                    <span className={`validation__status validation__status--${f.status}`}>
                      {f.status}
                    </span>
                    {!isTerminal && (
                      <span className="review__field-actions">
                        {editing ? (
                          <>
                            <button
                              className="review__field-btn review__field-btn--save"
                              onClick={() => handleSaveEdit(f.id)}
                            >
                              Save
                            </button>
                            <button
                              className="review__field-btn"
                              onClick={handleCancelEdit}
                            >
                              Cancel
                            </button>
                          </>
                        ) : (
                          <button
                            className="review__field-btn"
                            onClick={() => handleStartEdit(f)}
                          >
                            Edit
                          </button>
                        )}
                      </span>
                    )}
                  </div>
                );
              })}
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
