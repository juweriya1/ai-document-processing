import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getBatch, reprocessBatch } from '../api/client';
import { useToast } from '../components/Toast';
import './BatchStatusPage.css';

const TERMINAL_BATCH = new Set(['completed', 'partial_failed']);
const RUNNING_DOC = new Set(['uploaded', 'processing']);

// Assume ~6s/doc on Tier-1 (paddle OCR + audit) serially; the semaphore runs
// up to 3 in parallel. This is shown to the jury as a demoable metric.
const SEQUENTIAL_SEC_PER_DOC = 6;
const CONCURRENCY = 3;

function StatusBadge({ status }) {
  const cls = `batch-status__badge batch-status__badge--${status || 'unknown'}`;
  return <span className={cls}>{(status || 'unknown').replace('_', ' ')}</span>;
}

function formatElapsed(seconds) {
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s}s`;
}

export default function BatchStatusPage() {
  const { batchId } = useParams();
  const [batch, setBatch] = useState(null);
  const [error, setError] = useState(null);
  const [now, setNow] = useState(Date.now());
  const [reprocessing, setReprocessing] = useState(false);
  const startedAtRef = useRef(null);
  const toast = useToast();

  useEffect(() => {
    let cancelled = false;
    let intervalId = null;
    const startedPollAt = Date.now();

    const tick = async () => {
      try {
        const data = await getBatch(batchId);
        if (cancelled) return;
        setBatch(data);
        setNow(Date.now());
        if (startedAtRef.current === null && data.created_at) {
          startedAtRef.current = new Date(data.created_at).getTime();
        }
        if (TERMINAL_BATCH.has(data.status)) {
          if (intervalId) clearInterval(intervalId);
        } else if (Date.now() - startedPollAt > 30000) {
          // Back off polling once we've been watching for 30s to reduce load.
          if (intervalId) {
            clearInterval(intervalId);
            intervalId = setInterval(tick, 5000);
          }
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    };

    tick();
    intervalId = setInterval(tick, 2000);
    return () => {
      cancelled = true;
      if (intervalId) clearInterval(intervalId);
    };
  }, [batchId]);

  const handleReprocess = async () => {
    setReprocessing(true);
    try {
      const data = await reprocessBatch(batchId);
      const count = data.requeued_document_ids?.length || 0;
      toast(
        count > 0
          ? `Requeued ${count} document(s)`
          : 'Nothing to requeue — all documents already processed',
        count > 0 ? 'success' : 'info',
      );
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      setReprocessing(false);
    }
  };

  if (error && !batch) {
    return (
      <div>
        <h1 className="batch-status__title">Batch</h1>
        <div className="batch-status__error">Error: {error}</div>
      </div>
    );
  }

  if (!batch) {
    return <div className="batch-status__loading">Loading batch status...</div>;
  }

  const { counts, documents, status, total_documents } = batch;
  const finished = (counts.verified || 0) + (counts.review_pending || 0)
                 + (counts.approved || 0) + (counts.rejected || 0)
                 + (counts.flagged || 0) + (counts.failed || 0);
  const pct = total_documents > 0 ? (finished / total_documents) * 100 : 0;
  const elapsedSec = startedAtRef.current
    ? Math.max(0, (now - startedAtRef.current) / 1000)
    : 0;
  const sequentialEstimate = total_documents * SEQUENTIAL_SEC_PER_DOC;
  const speedup = elapsedSec > 0 ? sequentialEstimate / elapsedSec : 0;
  const isTerminal = TERMINAL_BATCH.has(status);
  const hasFailed = (counts.failed || 0) > 0;

  return (
    <div>
      <div className="batch-status__header">
        <div>
          <h1 className="batch-status__title">Batch {batch.id}</h1>
          <div className="batch-status__meta">
            <StatusBadge status={status} />
            <span className="batch-status__meta-item">
              {finished} / {total_documents} processed
            </span>
            <span className="batch-status__meta-item">
              Elapsed: {formatElapsed(elapsedSec)}
            </span>
          </div>
        </div>
        <div className="batch-status__header-actions">
          {isTerminal && hasFailed && (
            <button
              type="button"
              className="batch-status__reprocess-btn"
              onClick={handleReprocess}
              disabled={reprocessing}
            >
              {reprocessing ? 'Requeuing...' : 'Retry failed'}
            </button>
          )}
          <Link to="/batch-upload" className="batch-status__new-batch-link">
            New batch &rarr;
          </Link>
        </div>
      </div>

      <div className="batch-status__progress-card">
        <div className="batch-status__progress-bar-wrap">
          <div
            className={`batch-status__progress-bar batch-status__progress-bar--${status}`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="batch-status__count-chips">
          {['uploaded', 'processing', 'verified', 'review_pending', 'flagged', 'failed'].map((k) => (
            <span key={k} className={`batch-status__count-chip batch-status__count-chip--${k}`}>
              <span className="batch-status__count-chip-label">{k.replace('_', ' ')}</span>
              <span className="batch-status__count-chip-value">{counts[k] || 0}</span>
            </span>
          ))}
        </div>
      </div>

      <div className="batch-status__doc-list">
        <div className="batch-status__doc-list-header">
          <span className="batch-status__col-filename">Filename</span>
          <span className="batch-status__col-status">Status</span>
          <span className="batch-status__col-extract">Extracted</span>
          <span className="batch-status__col-tier">Tier</span>
          <span className="batch-status__col-action">&nbsp;</span>
        </div>
        {documents.map((d) => (
          <div key={d.id} className="batch-status__doc-row">
            <span className="batch-status__col-filename" title={d.original_filename}>
              {d.original_filename}
            </span>
            <span className="batch-status__col-status">
              <StatusBadge status={d.status} />
            </span>
            <span className="batch-status__col-extract">
              {d.fields_extracted > 0 || d.line_items_extracted > 0
                ? `${d.fields_extracted} fields, ${d.line_items_extracted} items`
                : RUNNING_DOC.has(d.status)
                  ? 'Processing...'
                  : '—'}
            </span>
            <span className="batch-status__col-tier">
              {d.tier ? <span className={`batch-status__tier-chip batch-status__tier-chip--${d.tier}`}>{d.tier}</span> : '—'}
            </span>
            <span className="batch-status__col-action">
              {d.status === 'review_pending' || d.status === 'verified' || d.status === 'flagged' ? (
                <Link to={`/review/${d.id}`} className="batch-status__view-link">View</Link>
              ) : d.status === 'failed' ? (
                <span className="batch-status__error-text" title={d.error || ''}>
                  Failed
                </span>
              ) : null}
            </span>
          </div>
        ))}
      </div>

      {isTerminal && (
        <div className="batch-status__summary">
          Processed <strong>{total_documents}</strong> document(s) in{' '}
          <strong>{formatElapsed(elapsedSec)}</strong>. Sequential baseline{' '}
          &asymp; {formatElapsed(sequentialEstimate)} &middot; Concurrency: {CONCURRENCY}
          {speedup > 1 && elapsedSec > 0 && (
            <> &middot; <strong>{speedup.toFixed(1)}&times;</strong> speedup</>
          )}
        </div>
      )}
    </div>
  );
}
