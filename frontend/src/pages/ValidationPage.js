import React, { useState, useEffect } from 'react';
import { validationAPI } from '../services/api';
import PageHeader from '../components/shared/PageHeader';
import toast from 'react-hot-toast';
import './ValidationPage.css';

const MOCK_ITEMS = [
  {
    id: 'VAL-0012',
    doc: 'Q4_Invoice_Batch.pdf',
    status: 'pending',
    confidence: 96,
    fields: [
      { key: 'vendor_name', label: 'Vendor Name', value: 'Acme Corp Ltd.', confidence: 99, issue: null },
      { key: 'invoice_no', label: 'Invoice Number', value: 'INV-2024-00892', confidence: 99, issue: null },
      { key: 'invoice_date', label: 'Invoice Date', value: '2024-10-15', confidence: 98, issue: null },
      { key: 'due_date', label: 'Due Date', value: '2024-11-14', confidence: 95, issue: null },
      { key: 'total_amount', label: 'Total Amount', value: '$12,450.00', confidence: 97, issue: null },
      { key: 'tax_amount', label: 'Tax (GST)', value: '$1,122.50', confidence: 89, issue: 'Low confidence — verify manually' },
      { key: 'currency', label: 'Currency', value: 'USD', confidence: 99, issue: null },
      { key: 'payment_terms', label: 'Payment Terms', value: 'Net 30', confidence: 92, issue: null },
      { key: 'po_number', label: 'PO Number', value: 'PO-2024-0456', confidence: 78, issue: 'Partial match — possible OCR error on digit 6' },
      { key: 'bank_account', label: 'Bank Account', value: '****3892', confidence: 94, issue: null },
    ],
  },
  {
    id: 'VAL-0011',
    doc: 'ServiceAgreement_v3.pdf',
    status: 'pending',
    confidence: 82,
    fields: [
      { key: 'party_a', label: 'Party A', value: 'TechSolutions Inc.', confidence: 91, issue: null },
      { key: 'party_b', label: 'Party B', value: 'ClientCo Pvt Ltd', confidence: 73, issue: 'Ambiguous entity — two possible matches found' },
      { key: 'effective_date', label: 'Effective Date', value: '2024-09-01', confidence: 95, issue: null },
      { key: 'contract_value', label: 'Contract Value', value: '$240,000/yr', confidence: 88, issue: null },
      { key: 'duration', label: 'Duration', value: '2 years', confidence: 96, issue: null },
      { key: 'governing_law', label: 'Governing Law', value: 'State of Delaware', confidence: 99, issue: null },
    ],
  },
];

function ConfidenceChip({ value }) {
  const cls = value >= 90 ? 'conf--high' : value >= 75 ? 'conf--medium' : 'conf--low';
  return <span className={`conf-chip ${cls}`}>{value}%</span>;
}

export default function ValidationPage() {
  const [items, setItems] = useState(MOCK_ITEMS);
  const [selected, setSelected] = useState(MOCK_ITEMS[0]);
  const [editValues, setEditValues] = useState({});
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    validationAPI.list()
      .then((res) => {
        if (res.data?.items?.length) {
          setItems(res.data.items);
          setSelected(res.data.items[0]);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (selected) {
      const init = {};
      selected.fields.forEach((f) => { init[f.key] = f.value; });
      setEditValues(init);
    }
  }, [selected]);

  const issues = selected?.fields.filter((f) => f.issue) || [];

  const handleApprove = async () => {
    setSaving(true);
    try {
      await validationAPI.approve(selected.id);
      toast.success('Validation approved', { className: 'custom-toast' });
      setItems((prev) =>
        prev.map((it) => it.id === selected.id ? { ...it, status: 'approved' } : it)
      );
    } catch {
      toast.error('Failed to approve', { className: 'custom-toast' });
    } finally {
      setSaving(false);
    }
  };

  const handleReject = async () => {
    const reason = window.prompt('Rejection reason (optional):');
    setSaving(true);
    try {
      await validationAPI.reject(selected.id, reason || '');
      toast.success('Rejected and flagged for re-processing', { className: 'custom-toast' });
      setItems((prev) =>
        prev.map((it) => it.id === selected.id ? { ...it, status: 'rejected' } : it)
      );
    } catch {
      toast.error('Failed to reject', { className: 'custom-toast' });
    } finally {
      setSaving(false);
    }
  };

  const handleSubmit = async () => {
    setSaving(true);
    try {
      await validationAPI.submit(selected.id, editValues);
      toast.success('Fields saved', { className: 'custom-toast' });
    } catch {
      toast.error('Save failed', { className: 'custom-toast' });
    } finally {
      setSaving(false);
    }
  };

  const filteredItems = items.filter((it) =>
    filter === 'all' ? true : it.status === filter
  );

  return (
    <div className="page-enter">
      <PageHeader
        title="Validation"
        subtitle="Review and correct AI-extracted fields before approval"
        badge={{ text: `${items.filter(i => i.status === 'pending').length} Pending`, type: 'warn' }}
      />

      <div className="validation-layout">
        {/* Left panel */}
        <div className="val-list-panel">
          <div className="val-filter-bar">
            {['all', 'pending', 'approved', 'rejected'].map((f) => (
              <button
                key={f}
                className={`val-filter-btn ${filter === f ? 'val-filter-btn--active' : ''}`}
                onClick={() => setFilter(f)}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>
          <div className="val-list">
            {filteredItems.map((item) => (
              <button
                key={item.id}
                className={`val-list-item ${selected?.id === item.id ? 'val-list-item--active' : ''}`}
                onClick={() => setSelected(item)}
              >
                <div className="val-list-top">
                  <span className="mono val-list-id">{item.id}</span>
                  <ConfidenceChip value={item.confidence} />
                </div>
                <div className="val-list-doc">{item.doc}</div>
                <div className="val-list-meta">
                  {item.fields.filter((f) => f.issue).length > 0 && (
                    <span className="val-issue-count">
                      ⚠ {item.fields.filter((f) => f.issue).length} issue{item.fields.filter((f) => f.issue).length > 1 ? 's' : ''}
                    </span>
                  )}
                  <span className={`badge ${
                    item.status === 'approved' ? 'badge-success' :
                    item.status === 'rejected' ? 'badge-danger' :
                    'badge-warn'
                  }`}>{item.status}</span>
                </div>
              </button>
            ))}
            {filteredItems.length === 0 && (
              <div className="empty-state" style={{ padding: 'var(--space-8)' }}>
                <div className="icon-wrap">✓</div>
                <h4>No items</h4>
                <p>Nothing matching this filter</p>
              </div>
            )}
          </div>
        </div>

        {/* Right panel */}
        {selected && (
          <div className="val-detail-panel">
            {/* Header */}
            <div className="val-detail-header">
              <div>
                <div className="flex items-center gap-3">
                  <h3 className="val-detail-title">{selected.doc}</h3>
                  <ConfidenceChip value={selected.confidence} />
                </div>
                <div className="val-detail-meta mono">
                  {selected.id} · {selected.fields.length} fields extracted
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={handleSubmit}
                  disabled={saving}
                >
                  Save changes
                </button>
                <button
                  className="btn btn-danger btn-sm"
                  onClick={handleReject}
                  disabled={saving}
                >
                  Reject
                </button>
                <button
                  className="btn btn-primary btn-sm"
                  onClick={handleApprove}
                  disabled={saving}
                >
                  Approve →
                </button>
              </div>
            </div>

            {/* Issues banner */}
            {issues.length > 0 && (
              <div className="val-issues-banner">
                <span className="val-issues-icon">⚠</span>
                <span className="val-issues-text">
                  <strong>{issues.length} field{issues.length > 1 ? 's require' : ' requires'} attention</strong>
                  {' — '}Low-confidence extractions are highlighted below.
                </span>
              </div>
            )}

            {/* Fields grid */}
            <div className="val-fields-scroll">
              <div className="val-fields-grid">
                {selected.fields.map((field) => (
                  <div
                    key={field.key}
                    className={`val-field-card ${field.issue ? 'val-field-card--issue' : ''}`}
                  >
                    <div className="val-field-header">
                      <label className="val-field-label">{field.label}</label>
                      <ConfidenceChip value={field.confidence} />
                    </div>
                    <input
                      className="form-input val-field-input"
                      value={editValues[field.key] ?? field.value}
                      onChange={(e) =>
                        setEditValues((prev) => ({ ...prev, [field.key]: e.target.value }))
                      }
                    />
                    {field.issue && (
                      <div className="val-field-issue">
                        <span>⚠ {field.issue}</span>
                      </div>
                    )}
                    <div className="val-field-confidence-bar">
                      <div className="confidence-track">
                        <div
                          className={`confidence-fill ${field.confidence >= 90 ? 'high' : field.confidence >= 75 ? 'medium' : 'low'}`}
                          style={{ width: `${field.confidence}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
