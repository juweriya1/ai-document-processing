import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useDocuments } from '../context/DocumentContext';
import {
  getDocumentFieldsWithStats,
  validateDocument,
  submitCorrection,
} from '../api/client';
import { useToast } from '../components/Toast';
import './ValidationPage.css';

const REASON_LABELS = {
  validation_failed: 'VALIDATION FAILED',
  missing_confidence: 'NO CONFIDENCE',
  critical_field: 'CRITICAL',
  low_confidence: 'LOW CONFIDENCE',
  auto_approved: 'AUTO-APPROVED',
};

const REASON_CLASSES = {
  validation_failed: 'validation__reason--fail',
  missing_confidence: 'validation__reason--unknown',
  critical_field: 'validation__reason--critical',
  low_confidence: 'validation__reason--low',
  auto_approved: 'validation__reason--auto',
};

export default function ValidationPage() {
  const { documentId: paramId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { recentDocId, recentBatch, setRecentDocId } = useDocuments();
  const toast = useToast();

  // Pre-fill priority: URL param > recent single-doc upload > first doc in
  // most recent batch > empty. The user explicitly asked never to retype IDs.
  const initialDocId = paramId || recentDocId || recentBatch?.documentIds?.[0] || '';

  const [docId, setDocId] = useState(initialDocId);
  const [fields, setFields] = useState([]);
  const [loading, setLoading] = useState(false);
  const [editingField, setEditingField] = useState(null);
  const [editValue, setEditValue] = useState('');
  const [validationResult, setValidationResult] = useState(null);
  const [hitlMode, setHitlMode] = useState(true);
  const [hitlStats, setHitlStats] = useState(null);

  const isReviewerOrAdmin = user?.role === 'reviewer' || user?.role === 'admin';

  // Auto-load whenever the doc ID changes via URL param OR a non-batch
  // pre-fill resolved at mount. The user shouldn't have to press "Load".
  useEffect(() => {
    const id = paramId || initialDocId;
    if (id) {
      setDocId(id);
      loadFields(id, hitlMode);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramId]);

  const loadFields = async (id, useHitl) => {
    setLoading(true);
    try {
      const { fields: data, total, shown, skipped, expectedResidualErrors } =
        await getDocumentFieldsWithStats(id, useHitl);
      setFields(data);
      setHitlStats({ total, shown, skipped, expectedResidualErrors });
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleHitl = () => {
    const next = !hitlMode;
    setHitlMode(next);
    if (docId.trim()) loadFields(docId.trim(), next);
  };

  const handleLoad = () => {
    if (!docId.trim()) {
      toast('Please enter a document ID', 'error');
      return;
    }
    loadFields(docId.trim(), hitlMode);
  };

  const handleValidate = async () => {
    if (!docId.trim()) return;
    try {
      const data = await validateDocument(docId.trim());
      setValidationResult(data.summary);
      await loadFields(docId.trim(), hitlMode);
      toast('Validation complete', 'success');
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

  const handleSubmitCorrection = async (fieldId) => {
    try {
      await submitCorrection(docId.trim(), fieldId, editValue);
      toast('Correction submitted', 'success');
      setEditingField(null);
      setEditValue('');
      await loadFields(docId.trim(), hitlMode);
    } catch (err) {
      toast(err.message, 'error');
    }
  };

  const confidenceBadgeClass = (confidence) => {
    if (confidence == null) return 'validation__conf--unknown';
    if (confidence >= 0.90) return 'validation__conf--high';
    if (confidence >= 0.75) return 'validation__conf--medium';
    return 'validation__conf--low';
  };

  const reasonLabel = (reason) => REASON_LABELS[reason] || reason || '—';
  const reasonClass = (reason) => REASON_CLASSES[reason] || '';

  const pctSaved = hitlStats && hitlStats.total > 0
    ? Math.round((hitlStats.skipped / hitlStats.total) * 100)
    : 0;

  return (
    <div>
      <div className="validation__header-row">
        <h1 className="validation__title">Data Validation</h1>

        {isReviewerOrAdmin && (
          <div className="validation__hitl-toggle">
            <span className="validation__hitl-label">
              {hitlMode ? '🎯 Smart Review (HITL)' : '📋 Show All Fields'}
            </span>
            <button
              className={`validation__toggle-btn ${hitlMode ? 'validation__toggle-btn--active' : ''}`}
              onClick={handleToggleHitl}
            >
              {hitlMode ? 'ON' : 'OFF'}
            </button>
          </div>
        )}
      </div>

      {hitlStats && hitlMode && (
        <div className="validation__hitl-banner">
          <div className="validation__hitl-headline">
            Reviewing <strong>{hitlStats.shown}</strong> of <strong>{hitlStats.total}</strong> fields
            · <strong>{hitlStats.skipped}</strong> auto-approved
            {hitlStats.total > 0 && <> · <strong>{pctSaved}%</strong> effort saved</>}
          </div>
          <div className="validation__hitl-sub">
            Sorted by risk (critical fields &amp; low confidence first).
            Expected residual error across auto-approved fields:{' '}
            <strong>{(hitlStats.expectedResidualErrors ?? 0).toFixed(2)}</strong>
            {' '}(lower is safer).
          </div>
        </div>
      )}

      {!paramId && (
        <div className="validation__input-section">
          <label className="validation__input-label">Document ID</label>
          <div className="validation__input-row">
            {recentBatch?.documentIds?.length > 1 ? (
              // Batch context: dropdown over the batch's doc IDs so the
              // user can switch between docs without retyping.
              <select
                className="validation__input"
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
                className="validation__input"
                value={docId}
                onChange={(e) => setDocId(e.target.value)}
                placeholder="Enter document ID (UUID)"
              />
            )}
            <button className="validation__load-btn" onClick={handleLoad}>
              Load Fields
            </button>
          </div>
        </div>
      )}

      {loading && (
        <div className="validation__loading">Loading fields...</div>
      )}

      {validationResult && (
        <div className="validation__summary">
          <span className="validation__summary-item validation__summary-item--valid">
            Valid: {validationResult.valid}
          </span>
          <span className="validation__summary-item validation__summary-item--invalid">
            Invalid: {validationResult.invalid}
          </span>
          <span className="validation__summary-item validation__summary-item--corrected">
            Corrected: {validationResult.corrected}
          </span>
          <span className="validation__summary-item">
            Pending: {validationResult.pending}
          </span>
        </div>
      )}

      {fields.length > 0 && (
        <>
          <div className="validation__table-wrap">
            <table className="validation__table">
              <thead>
                <tr>
                  <th>Priority</th>
                  <th>Field Name</th>
                  <th>Extracted Value</th>
                  <th>Confidence</th>
                  <th>Risk</th>
                  <th>Status</th>
                  {isReviewerOrAdmin && <th>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {fields.map((field) => (
                  <tr
                    key={field.id}
                    className={field.status === 'invalid' ? 'validation__row--invalid' : ''}
                  >
                    <td>
                      <span
                        className={`validation__reason ${reasonClass(field.reviewReason)}`}
                        title={
                          field.effectiveThreshold != null
                            ? `Threshold: ${(field.effectiveThreshold * 100).toFixed(1)}% · Criticality: ${field.criticality ?? 1}`
                            : undefined
                        }
                      >
                        {reasonLabel(field.reviewReason)}
                      </span>
                    </td>
                    <td>{field.fieldName}</td>
                    <td>
                      {editingField === field.id ? (
                        <input
                          type="text"
                          className="validation__edit-input"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          autoFocus
                        />
                      ) : (
                        field.fieldValue || '—'
                      )}
                    </td>
                    <td>
                      <span className={`validation__conf ${confidenceBadgeClass(field.confidence)}`}>
                        {field.confidence != null
                          ? `${(field.confidence * 100).toFixed(1)}%`
                          : '—'}
                      </span>
                    </td>
                    <td>
                      <span className="validation__risk">
                        {field.riskScore != null ? field.riskScore.toFixed(2) : '∞'}
                      </span>
                    </td>
                    <td>
                      <span className={`validation__status validation__status--${field.status}`}>
                        {field.status}
                      </span>
                    </td>
                    {isReviewerOrAdmin && (
                      <td>
                        {editingField === field.id ? (
                          <>
                            <button
                              className="validation__action-btn"
                              onClick={() => handleSubmitCorrection(field.id)}
                            >
                              Save
                            </button>
                            <button
                              className="validation__action-btn"
                              onClick={handleCancelEdit}
                            >
                              Cancel
                            </button>
                          </>
                        ) : (
                          <button
                            className="validation__action-btn"
                            onClick={() => handleStartEdit(field)}
                          >
                            Edit
                          </button>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="validation__footer">
            {isReviewerOrAdmin && (
              <button
                className="validation__footer-btn validation__footer-btn--proceed"
                onClick={handleValidate}
              >
                Run Validation
              </button>
            )}
            <button
              className="validation__footer-btn validation__footer-btn--proceed"
              onClick={() => navigate(`/review/${docId.trim()}`)}
            >
              Proceed to Review
            </button>
          </div>
        </>
      )}

      {fields.length === 0 && !loading && hitlMode && hitlStats?.skipped > 0 && (
        <div className="validation__empty validation__empty--all-clear">
          🎉 All {hitlStats.total} fields passed the risk budget — nothing to review.
          {hitlStats.expectedResidualErrors > 0 && (
            <> Expected residual error: {hitlStats.expectedResidualErrors.toFixed(2)}.</>
          )}
        </div>
      )}

      {!loading && fields.length === 0 && docId && paramId && !hitlStats?.skipped && (
        <div className="validation__empty">
          No extracted fields found. Process the document first.
        </div>
      )}
    </div>
  );
}
