import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getDocumentFields, validateDocument, submitCorrection } from '../api/client';
import { useToast } from '../components/Toast';
import './ValidationPage.css';

function ConfidenceBar({ value }) {
  if (value == null) return <span style={{ color: 'var(--text-5)', fontSize: 12 }}>—</span>;
  const pct  = Math.round(value * 100);
  const color = pct >= 80 ? 'var(--success)' : pct >= 50 ? 'var(--warning)' : 'var(--error)';
  return (
    <div className="confidence-bar">
      <div className="confidence-bar__track">
        <div className="confidence-bar__fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="confidence-bar__label">{pct}%</span>
    </div>
  );
}

const SkeletonRow = () => (
  <tr>
    {[140, 180, 80, 70, 60].map((w, i) => (
      <td key={i}><div className="skeleton" style={{ height: 14, width: w, borderRadius: 4 }} /></td>
    ))}
  </tr>
);

export default function ValidationPage() {
  const { documentId: paramId } = useParams();
  const navigate                = useNavigate();
  const { user }                = useAuth();
  const toast                   = useToast();

  const [docId, setDocId]               = useState(paramId || '');
  const [fields, setFields]             = useState([]);
  const [loading, setLoading]           = useState(false);
  const [editingField, setEditingField] = useState(null);
  const [editValue, setEditValue]       = useState('');
  const [validationResult, setValResult]= useState(null);

  const canEdit = user?.role === 'reviewer' || user?.role === 'admin';

  useEffect(() => {
    if (paramId) { setDocId(paramId); loadFields(paramId); }
  }, [paramId]); // eslint-disable-line

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
    if (!docId.trim()) { toast('Please enter a document ID', 'error'); return; }
    loadFields(docId.trim());
  };

  const handleValidate = async () => {
    if (!docId.trim()) return;
    try {
      const data = await validateDocument(docId.trim());
      setValResult(data.summary);
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

  const handleCancelEdit = () => { setEditingField(null); setEditValue(''); };

  const handleSave = async (fieldId) => {
    try {
      await submitCorrection(docId.trim(), fieldId, editValue);
      toast('Correction saved', 'success');
      setEditingField(null);
      setEditValue('');
      await loadFields(docId.trim());
    } catch (err) {
      toast(err.message, 'error');
    }
  };

  // Summary counts from fields
  const counts = fields.reduce((acc, f) => {
    acc[f.status] = (acc[f.status] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="page-wrap">
      <div className="page-header">
        <h1 className="page-title">Data Validation</h1>
        <p className="page-subtitle">Review extracted fields and submit corrections</p>
      </div>

      {/* Doc ID input */}
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
          <button className="btn btn--primary" onClick={handleLoad}>Load Fields</button>
        </div>
      )}

      {/* Summary chips */}
      {fields.length > 0 && !loading && (
        <div className="validation__summary-strip">
          {counts.valid != null && (
            <div className="validation__summary-chip validation__summary-chip--valid">
              <svg width="13" height="13" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5"/><path d="M6.5 10l2.5 2.5 4.5-4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              {counts.valid} Valid
            </div>
          )}
          {counts.invalid != null && (
            <div className="validation__summary-chip validation__summary-chip--invalid">
              <svg width="13" height="13" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5"/><path d="M7 13l6-6M13 13L7 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              {counts.invalid} Invalid
            </div>
          )}
          {counts.corrected != null && (
            <div className="validation__summary-chip validation__summary-chip--corrected">
              <svg width="13" height="13" viewBox="0 0 20 20" fill="none"><path d="M4 14l4-4 2 2 6-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
              {counts.corrected} Corrected
            </div>
          )}
          {counts.pending != null && (
            <div className="validation__summary-chip validation__summary-chip--pending">
              {counts.pending} Pending
            </div>
          )}
          {validationResult && (
            <div className="validation__summary-chip validation__summary-chip--pending" style={{ marginLeft: 'auto' }}>
              Last run: {validationResult.valid} valid / {validationResult.invalid} invalid
            </div>
          )}
        </div>
      )}

      {/* Table */}
      <div className="validation__table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Field Name</th>
              <th>Extracted Value</th>
              <th>Confidence</th>
              <th>Status</th>
              {canEdit && <th>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 6 }).map((_, i) => <SkeletonRow key={i} />)
              : fields.length === 0
              ? (
                <tr>
                  <td colSpan={canEdit ? 5 : 4}>
                    <div className="empty-state" style={{ padding: 'var(--sp-10)' }}>
                      <svg className="empty-state__icon" viewBox="0 0 24 24" fill="none"><path d="M9 12h6M9 16h6M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8L14 2z" stroke="currentColor" strokeWidth="1.5"/><path d="M14 2v6h6" stroke="currentColor" strokeWidth="1.5"/></svg>
                      <div className="empty-state__title">No fields extracted</div>
                      <div className="empty-state__desc">Process the document first to see extracted fields here</div>
                    </div>
                  </td>
                </tr>
              )
              : fields.map((field, idx) => (
                <tr
                  key={field.id}
                  className="animate-fade-in"
                  style={{ animationDelay: `${idx * 20}ms` }}
                >
                  <td>
                    <span style={{ fontWeight: 500, color: 'var(--text-1)' }}>
                      {field.fieldName}
                    </span>
                  </td>
                  <td>
                    {editingField === field.id ? (
                      <input
                        className="validation__edit-input"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        autoFocus
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleSave(field.id);
                          if (e.key === 'Escape') handleCancelEdit();
                        }}
                      />
                    ) : (
                      <span
                        style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: 12,
                          color: field.status === 'corrected' ? 'var(--warning)' : 'var(--text-2)',
                        }}
                      >
                        {field.fieldValue || '—'}
                      </span>
                    )}
                  </td>
                  <td><ConfidenceBar value={field.confidence} /></td>
                  <td>
                    <span className={`vs-pill vs-pill--${field.status}`}>
                      {field.status}
                    </span>
                  </td>
                  {canEdit && (
                    <td>
                      {editingField === field.id ? (
                        <div style={{ display: 'flex', gap: 6 }}>
                          <button className="btn btn--success btn--sm" onClick={() => handleSave(field.id)}>Save</button>
                          <button className="btn btn--ghost btn--sm" onClick={handleCancelEdit}>Cancel</button>
                        </div>
                      ) : (
                        <button
                          className="btn btn--ghost btn--sm"
                          onClick={() => handleStartEdit(field)}
                        >
                          <svg width="12" height="12" viewBox="0 0 20 20" fill="none"><path d="M14 2l4 4-10 10H4v-4L14 2z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/></svg>
                          Edit
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))
            }
          </tbody>
        </table>
      </div>

      {/* Footer */}
      {fields.length > 0 && (
        <div className="validation__footer">
          {canEdit && (
            <button className="btn btn--secondary" onClick={handleValidate}>
              <svg width="14" height="14" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5"/><path d="M7 10l2 2 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              Run Validation
            </button>
          )}
          <button className="btn btn--primary" onClick={() => navigate(`/review/${docId.trim()}`)}>
            Proceed to Review
            <svg width="14" height="14" viewBox="0 0 20 20" fill="none"><path d="M8 4l6 6-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
          </button>
        </div>
      )}
    </div>
  );
}
