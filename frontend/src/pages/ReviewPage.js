import React, { useState, useEffect } from 'react';
import { reviewAPI } from '../services/api';
import PageHeader from '../components/shared/PageHeader';
import toast from 'react-hot-toast';
import './ReviewPage.css';

const MOCK_REVIEWS = [
  {
    id: 'REV-0042',
    doc: 'ServiceAgreement_v3.pdf',
    assignee: 'Auto-assigned',
    status: 'pending',
    priority: 'high',
    confidence: 82,
    issues: 2,
    pages: 8,
    submitted: '11 min ago',
    extracted: {
      'Party A': 'TechSolutions Inc.',
      'Party B': 'ClientCo Pvt Ltd (?)',
      'Effective Date': '2024-09-01',
      'Contract Value': '$240,000/yr',
      'Duration': '2 years',
      'Governing Law': 'State of Delaware',
    },
    comments: [
      { author: 'AI System', time: '11:22', text: 'Party B name ambiguous — two entity matches found in database.' },
      { author: 'AI System', time: '11:22', text: 'Low-confidence field: Party B (73%). Manual verification recommended.' },
    ],
  },
  {
    id: 'REV-0041',
    doc: 'PurchaseOrder_Oct_Batch.pdf',
    assignee: 'Jane Smith',
    status: 'in_review',
    priority: 'medium',
    confidence: 88,
    issues: 1,
    pages: 5,
    submitted: '28 min ago',
    extracted: {
      'Vendor': 'Global Supplies Ltd.',
      'PO Number': 'PO-2024-0456',
      'Order Date': '2024-10-12',
      'Total': '$8,320.00',
      'Delivery By': '2024-11-01',
    },
    comments: [
      { author: 'AI System', time: '10:45', text: 'PO number digit 6 may be OCR error — original reads as 0 or 6.' },
    ],
  },
  {
    id: 'REV-0040',
    doc: 'EmployeeOnboarding_Form.pdf',
    assignee: 'John Doe',
    status: 'approved',
    priority: 'low',
    confidence: 95,
    issues: 0,
    pages: 3,
    submitted: '2 hr ago',
    extracted: {
      'Employee Name': 'Sarah Mitchell',
      'Start Date': '2024-11-01',
      'Department': 'Engineering',
      'Manager': 'Alex Turner',
      'Salary Grade': 'L5',
    },
    comments: [
      { author: 'John Doe', time: '09:14', text: 'All fields verified. Approving.' },
    ],
  },
];

const PRIORITY_MAP = {
  high:   { cls: 'badge-danger', label: 'High' },
  medium: { cls: 'badge-warn', label: 'Medium' },
  low:    { cls: 'badge-default', label: 'Low' },
};

const STATUS_MAP = {
  pending:   { cls: 'badge-info', label: 'Pending Review' },
  in_review: { cls: 'badge-warn', label: 'In Review' },
  approved:  { cls: 'badge-success', label: 'Approved' },
  rejected:  { cls: 'badge-danger', label: 'Rejected' },
};

export default function ReviewPage() {
  const [items, setItems] = useState(MOCK_REVIEWS);
  const [selected, setSelected] = useState(MOCK_REVIEWS[0]);
  const [comment, setComment] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    reviewAPI.list()
      .then((res) => {
        if (res.data?.items?.length) {
          setItems(res.data.items);
          setSelected(res.data.items[0]);
        }
      })
      .catch(() => {});
  }, []);

  const handleApprove = async () => {
    setSaving(true);
    try {
      await reviewAPI.approve(selected.id, comment);
      toast.success('Document approved', { className: 'custom-toast' });
      setItems((prev) =>
        prev.map((it) => it.id === selected.id ? { ...it, status: 'approved' } : it)
      );
      setSelected((s) => ({ ...s, status: 'approved' }));
    } catch {
      toast.error('Approval failed', { className: 'custom-toast' });
    } finally {
      setSaving(false);
    }
  };

  const handleReject = async () => {
    if (!comment.trim()) {
      toast.error('Please provide a rejection reason in the notes field', { className: 'custom-toast' });
      return;
    }
    setSaving(true);
    try {
      await reviewAPI.reject(selected.id, comment);
      toast.success('Document rejected', { className: 'custom-toast' });
      setItems((prev) =>
        prev.map((it) => it.id === selected.id ? { ...it, status: 'rejected' } : it)
      );
      setSelected((s) => ({ ...s, status: 'rejected' }));
    } catch {
      toast.error('Rejection failed', { className: 'custom-toast' });
    } finally {
      setSaving(false);
    }
  };

  const handleAddComment = async () => {
    if (!comment.trim()) return;
    try {
      await reviewAPI.addComment(selected.id, comment);
      const newComment = { author: 'You', time: new Date().toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' }), text: comment };
      setSelected((s) => ({ ...s, comments: [...s.comments, newComment] }));
      setComment('');
      toast.success('Comment added', { className: 'custom-toast' });
    } catch {
      toast.error('Failed to add comment', { className: 'custom-toast' });
    }
  };

  return (
    <div className="page-enter">
      <PageHeader
        title="Human Review"
        subtitle="Final quality assurance workspace — approve or reject processed documents"
        badge={{ text: `${items.filter(i => i.status === 'pending' || i.status === 'in_review').length} Awaiting`, type: 'warn' }}
      />

      <div className="review-layout">
        {/* Queue */}
        <div className="review-queue">
          <div className="review-queue-header">
            <span className="section-title">Review Queue</span>
          </div>
          <div className="review-queue-list">
            {items.map((item) => (
              <button
                key={item.id}
                className={`review-queue-item ${selected?.id === item.id ? 'review-queue-item--active' : ''}`}
                onClick={() => setSelected(item)}
              >
                <div className="rq-top">
                  <span className="mono rq-id">{item.id}</span>
                  <span className={`badge ${PRIORITY_MAP[item.priority]?.cls}`}>
                    {PRIORITY_MAP[item.priority]?.label}
                  </span>
                </div>
                <div className="rq-doc">{item.doc}</div>
                <div className="rq-meta">
                  <span className={`badge ${STATUS_MAP[item.status]?.cls}`} style={{ fontSize: '0.7rem' }}>
                    {STATUS_MAP[item.status]?.label}
                  </span>
                  {item.issues > 0 && (
                    <span className="rq-issues">⚠ {item.issues}</span>
                  )}
                </div>
                <div className="rq-assignee">
                  {item.assignee} · {item.submitted}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Workspace */}
        {selected && (
          <div className="review-workspace">
            {/* Top bar */}
            <div className="review-workspace-header">
              <div>
                <div className="flex items-center gap-3">
                  <h3 className="rw-title">{selected.doc}</h3>
                  <span className={`badge ${STATUS_MAP[selected.status]?.cls}`}>
                    {STATUS_MAP[selected.status]?.label}
                  </span>
                  <span className={`badge ${PRIORITY_MAP[selected.priority]?.cls}`}>
                    {PRIORITY_MAP[selected.priority]?.label} priority
                  </span>
                </div>
                <div className="rw-meta mono">
                  {selected.id} · {selected.pages} pages ·
                  Confidence: <span style={{ color: selected.confidence >= 90 ? 'var(--accent-success)' : selected.confidence >= 75 ? 'var(--accent-warn)' : 'var(--accent-danger)' }}>
                    {selected.confidence}%
                  </span>
                  {selected.issues > 0 && ` · ${selected.issues} issue${selected.issues > 1 ? 's' : ''}`}
                  {' · Submitted '}{selected.submitted}
                </div>
              </div>
              {selected.status !== 'approved' && selected.status !== 'rejected' && (
                <div className="flex gap-2">
                  <button className="btn btn-danger btn-sm" onClick={handleReject} disabled={saving}>
                    Reject
                  </button>
                  <button className="btn btn-primary btn-sm" onClick={handleApprove} disabled={saving}>
                    ✓ Approve
                  </button>
                </div>
              )}
            </div>

            <div className="review-workspace-body">
              {/* Extracted data */}
              <div className="rw-data-panel">
                <div className="rw-section-title section-title">Extracted Data</div>
                <div className="rw-fields">
                  {Object.entries(selected.extracted).map(([key, val]) => (
                    <div key={key} className="rw-field">
                      <span className="rw-field-key">{key}</span>
                      <span className={`rw-field-val ${val.includes('(?)') ? 'rw-field-val--issue' : ''}`}>
                        {val}
                        {val.includes('(?)') && <span className="rw-flag">⚠ Review needed</span>}
                      </span>
                    </div>
                  ))}
                </div>

                {/* Audit trail */}
                <div className="rw-audit">
                  <div className="rw-section-title section-title" style={{ marginBottom: 'var(--space-3)' }}>Audit Trail</div>
                  <div className="rw-comments">
                    {selected.comments.map((c, i) => (
                      <div key={i} className={`rw-comment ${c.author === 'AI System' ? 'rw-comment--ai' : ''}`}>
                        <div className="rw-comment-header">
                          <span className="rw-comment-author">{c.author}</span>
                          <span className="rw-comment-time">{c.time}</span>
                        </div>
                        <p className="rw-comment-text">{c.text}</p>
                      </div>
                    ))}
                  </div>

                  {/* Add comment */}
                  {selected.status !== 'approved' && selected.status !== 'rejected' && (
                    <div className="rw-add-comment">
                      <textarea
                        className="form-input rw-textarea"
                        placeholder="Add a note or rejection reason…"
                        value={comment}
                        onChange={(e) => setComment(e.target.value)}
                        rows={3}
                      />
                      <div className="flex justify-end gap-2" style={{ marginTop: 'var(--space-2)' }}>
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={handleAddComment}
                          disabled={!comment.trim()}
                        >
                          Add comment
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Document preview placeholder */}
              <div className="rw-doc-preview">
                <div className="rw-preview-placeholder">
                  <div className="rw-preview-icon">📄</div>
                  <p>Document preview</p>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
                    {selected.pages} page{selected.pages > 1 ? 's' : ''}
                  </p>
                  <button className="btn btn-secondary btn-sm" style={{ marginTop: 'var(--space-3)' }}>
                    Open in viewer
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
