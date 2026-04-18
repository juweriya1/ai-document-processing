import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getDocumentFields, validateDocument, submitCorrection } from '../api/client';
import { useToast } from '../components/Toast';
import './ValidationPage.css';

function statusBadgeClass(s) {
  return s === 'valid' ? 'badge--success' : s === 'invalid' ? 'badge--danger' : s === 'corrected' ? 'badge--info' : 'badge--default';
}
function confClass(c) { return c >= 0.85 ? 'high' : c >= 0.6 ? 'mid' : 'low'; }

export default function ValidationPage() {
  const { documentId: paramId } = useParams();
  const navigate = useNavigate();
  const { user }  = useAuth();
  const toast     = useToast();

  const [docId, setDocId]     = useState(paramId || '');
  const [fields, setFields]   = useState([]);
  const [loading, setLoading] = useState(false);
  const [editingId, setEditId] = useState(null);
  const [editVal, setEditVal] = useState('');
  const [valResult, setValResult] = useState(null);

  const canEdit = user?.role === 'reviewer' || user?.role === 'admin';

  useEffect(() => { if (paramId) { setDocId(paramId); loadFields(paramId); } }, [paramId]); // eslint-disable-line

  const loadFields = async (id) => {
    setLoading(true);
    try { const d = await getDocumentFields(id); setFields(d); }
    catch (err) { toast(err.message, 'error'); }
    finally { setLoading(false); }
  };

  const handleLoad = () => { if (!docId.trim()) { toast('Enter a document ID', 'error'); return; } loadFields(docId.trim()); };

  const handleValidate = async () => {
    if (!docId.trim()) return;
    try {
      const d = await validateDocument(docId.trim());
      setValResult(d.summary);
      await loadFields(docId.trim());
      toast('Validation complete', 'success');
    } catch (err) { toast(err.message, 'error'); }
  };

  const handleSaveEdit = async (fieldId) => {
    try {
      await submitCorrection(docId.trim(), fieldId, editVal);
      toast('Correction saved', 'success');
      setEditId(null); setEditVal('');
      await loadFields(docId.trim());
    } catch (err) { toast(err.message, 'error'); }
  };

  const counts = fields.reduce((acc, f) => { acc[f.status] = (acc[f.status] || 0) + 1; return acc; }, {});
  const summaryItems = [
    { key: 'valid',     label: 'Valid',     color: 'var(--success)' },
    { key: 'invalid',   label: 'Invalid',   color: 'var(--danger)' },
    { key: 'corrected', label: 'Corrected', color: 'var(--info)' },
    { key: 'pending',   label: 'Pending',   color: 'var(--warning)' },
  ];

  return (
    <div className="page-wrap">
      <div className="page-hd">
        <div>
          <h1 className="page-title">Data Validation</h1>
          <p className="page-subtitle">Review extracted fields and submit corrections</p>
        </div>
        {canEdit && fields.length > 0 && (
          <button className="btn btn-primary" onClick={handleValidate}>Run Validation</button>
        )}
      </div>

      {/* Doc ID input (only if not from URL param) */}
      {!paramId && (
        <div className="field" style={{ marginBottom: 20 }}>
          <label className="field-label">Document ID</label>
          <div style={{ display:'flex', gap:10 }}>
            <input className="field-input" type="text" value={docId}
              onChange={e => setDocId(e.target.value)} placeholder="Enter document UUID…" />
            <button className="btn btn-ghost" onClick={handleLoad}>Load Fields</button>
          </div>
        </div>
      )}

      {/* Validation result summary */}
      {(valResult || fields.length > 0) && (
        <div className="val-summary">
          {summaryItems.map(({ key, label, color }) => (
            <div className="val-summary__item" key={key}>
              <div className="val-summary__dot" style={{ background: color }} />
              <span className="val-summary__label">{label}</span>
              <span className="val-summary__count">{counts[key] || 0}</span>
            </div>
          ))}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="val-loading"><span className="spinner" /> Loading extracted fields…</div>
      )}

      {/* Fields table */}
      {!loading && fields.length > 0 && (
        <>
          <div className="table-wrap">
            <table className="table">
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
                {fields.map(f => (
                  <tr key={f.id} style={f.status === 'invalid' ? { background:'rgba(248,113,113,0.04)' } : {}}>
                    <td style={{ fontWeight:600, color:'var(--text-1)' }}>{f.fieldName}</td>
                    <td>
                      {editingId === f.id ? (
                        <input className="val-edit-input" value={editVal}
                          onChange={e => setEditVal(e.target.value)} autoFocus
                          onKeyDown={e => e.key === 'Enter' && handleSaveEdit(f.id)} />
                      ) : (
                        <span className={f.status === 'corrected' ? '' : ''} style={f.status === 'corrected' ? { color:'var(--info)' } : {}}>
                          {f.fieldValue || '—'}
                        </span>
                      )}
                    </td>
                    <td>
                      {f.confidence != null ? (
                        <div className="conf-bar">
                          <div className="conf-bar__track">
                            <div className={`conf-bar__fill conf-bar__fill--${confClass(f.confidence)}`}
                              style={{ width: `${(f.confidence*100).toFixed(0)}%` }} />
                          </div>
                          <span className="conf-bar__label">{(f.confidence*100).toFixed(1)}%</span>
                        </div>
                      ) : '—'}
                    </td>
                    <td><span className={`badge ${statusBadgeClass(f.status)}`}>{f.status}</span></td>
                    {canEdit && (
                      <td>
                        <div className="val-actions">
                          {editingId === f.id ? (
                            <>
                              <button className="btn btn-success btn-sm" onClick={() => handleSaveEdit(f.id)}>Save</button>
                              <button className="btn btn-ghost btn-sm" onClick={() => { setEditId(null); setEditVal(''); }}>Cancel</button>
                            </>
                          ) : (
                            <button className="btn btn-ghost btn-sm" onClick={() => { setEditId(f.id); setEditVal(f.fieldValue || ''); }}>Edit</button>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="val-footer">
            <button className="btn btn-primary" onClick={() => navigate(`/review/${docId.trim()}`)}>
              Proceed to Review →
            </button>
          </div>
        </>
      )}

      {!loading && fields.length === 0 && docId && paramId && (
        <div className="empty-state" style={{ marginTop: 40 }}>
          <span style={{ fontSize: 32 }}>📋</span>
          No extracted fields found. Process the document first.
          <button className="btn btn-ghost btn-sm" onClick={() => navigate(`/processing/${docId}`)}>Go to Processing</button>
        </div>
      )}
    </div>
  );
}
