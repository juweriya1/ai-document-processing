import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import {
  getDocumentFields,
  validateDocument,
  submitCorrection,
} from '../api/client';
import { useToast } from '../components/Toast';
import './ValidationPage.css';

export default function ValidationPage() {
  const { documentId: paramId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const toast = useToast();

  const [docId, setDocId] = useState(paramId || '');
  const [fields, setFields] = useState([]);
  const [loading, setLoading] = useState(false);
  const [editingField, setEditingField] = useState(null);
  const [editValue, setEditValue] = useState('');
  const [validationResult, setValidationResult] = useState(null);

  const isReviewerOrAdmin = user?.role === 'reviewer' || user?.role === 'admin';

  useEffect(() => {
    if (paramId) {
      setDocId(paramId);
      loadFields(paramId);
    }
  }, [paramId]); // eslint-disable-line react-hooks/exhaustive-deps

  const loadFields = async (id) => {
    setLoading(true);
    try {
      const data = await getDocumentFields(id);
      setFields(data);
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
    loadFields(docId.trim());
  };

  const handleValidate = async () => {
    if (!docId.trim()) return;
    try {
      const data = await validateDocument(docId.trim());
      setValidationResult(data.summary);
      await loadFields(docId.trim());
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
      await loadFields(docId.trim());
    } catch (err) {
      toast(err.message, 'error');
    }
  };

  return (
    <div>
      <h1 className="validation__title">Data Validation</h1>

      {!paramId && (
        <div className="validation__input-section">
          <label className="validation__input-label">Document ID</label>
          <div className="validation__input-row">
            <input
              type="text"
              className="validation__input"
              value={docId}
              onChange={(e) => setDocId(e.target.value)}
              placeholder="Enter document ID (UUID)"
            />
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
                  <th>Field Name</th>
                  <th>Extracted Value</th>
                  <th>Confidence</th>
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
                        field.fieldValue || '\u2014'
                      )}
                    </td>
                    <td>
                      {field.confidence != null
                        ? `${(field.confidence * 100).toFixed(1)}%`
                        : '\u2014'}
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

      {!loading && fields.length === 0 && docId && paramId && (
        <div className="validation__empty">
          No extracted fields found. Process the document first.
        </div>
      )}
    </div>
  );
}
