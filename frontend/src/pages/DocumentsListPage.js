import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listDocuments } from '../api/client';
import { useToast } from '../components/Toast';
import DocumentViewer from '../components/DocumentViewer';
import './DocumentsListPage.css';

const PAGE_SIZE = 25;

function StatusPill({ status }) {
  const cls = `docs__status docs__status--${status || 'unknown'}`;
  return <span className={cls}>{status || 'unknown'}</span>;
}

function formatBytes(n) {
  if (!n && n !== 0) return '';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTime(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function DocumentsListPage() {
  const navigate = useNavigate();
  const toast = useToast();

  const [docs, setDocs] = useState([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedFilename, setSelectedFilename] = useState(null);

  const load = async (newSkip) => {
    setLoading(true);
    try {
      const data = await listDocuments({ skip: newSkip, limit: PAGE_SIZE });
      setDocs(data.documents || []);
      setTotal(data.total || 0);
      setSkip(newSkip);
    } catch (err) {
      toast(err.message || 'Failed to load documents', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSelect = (doc) => {
    setSelectedId(doc.id);
    setSelectedFilename(doc.originalFilename);
  };

  const handleClosePreview = () => {
    setSelectedId(null);
    setSelectedFilename(null);
  };

  const goReview = () => {
    if (selectedId) navigate(`/review/${selectedId}`);
  };
  const goValidate = () => {
    if (selectedId) navigate(`/validation/${selectedId}`);
  };

  const hasNext = skip + PAGE_SIZE < total;
  const hasPrev = skip > 0;

  return (
    <div>
      <h1 className="docs__title">Documents</h1>
      <p className="docs__subtitle">
        {total === 0 && !loading ? 'No documents yet — upload one to get started.' :
         `${total} document${total === 1 ? '' : 's'} total — click a row to preview.`}
      </p>

      <div className={`docs__layout${selectedId ? ' docs__layout--split' : ''}`}>
        <div className="docs__list-pane">
          <table className="docs__table">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Status</th>
                <th>Tier</th>
                <th>Confidence</th>
                <th>Size</th>
                <th>Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr
                  key={d.id}
                  onClick={() => handleSelect(d)}
                  className={
                    `docs__row${selectedId === d.id ? ' docs__row--selected' : ''}`
                  }
                >
                  <td className="docs__filename" title={d.id}>
                    {d.originalFilename}
                  </td>
                  <td><StatusPill status={d.status} /></td>
                  <td>{d.fallbackTier || '—'}</td>
                  <td>
                    {typeof d.confidenceScore === 'number'
                      ? d.confidenceScore.toFixed(2)
                      : '—'}
                  </td>
                  <td>{formatBytes(d.fileSize)}</td>
                  <td>{formatTime(d.uploadedAt)}</td>
                </tr>
              ))}
              {docs.length === 0 && !loading && (
                <tr>
                  <td colSpan={6} className="docs__empty">No documents found.</td>
                </tr>
              )}
            </tbody>
          </table>

          <div className="docs__pagination">
            <button
              className="docs__btn"
              disabled={!hasPrev || loading}
              onClick={() => load(Math.max(0, skip - PAGE_SIZE))}
            >
              Previous
            </button>
            <span className="docs__page-info">
              {total === 0
                ? '0'
                : `${skip + 1}–${Math.min(skip + PAGE_SIZE, total)} of ${total}`}
            </span>
            <button
              className="docs__btn"
              disabled={!hasNext || loading}
              onClick={() => load(skip + PAGE_SIZE)}
            >
              Next
            </button>
          </div>
        </div>

        {selectedId && (
          <div className="docs__preview-pane">
            <div className="docs__preview-header">
              <span className="docs__preview-filename" title={selectedId}>
                {selectedFilename || 'Selected document'}
              </span>
              <span className="docs__preview-actions">
                <button className="docs__btn docs__btn--accent" onClick={goValidate}>
                  Validate
                </button>
                <button className="docs__btn docs__btn--accent" onClick={goReview}>
                  Review
                </button>
                <button
                  className="docs__btn docs__btn--close"
                  onClick={handleClosePreview}
                  aria-label="Close preview"
                  title="Close preview"
                >
                  ✕
                </button>
              </span>
            </div>
            <DocumentViewer documentId={selectedId} filename={selectedFilename} />
          </div>
        )}
      </div>
    </div>
  );
}
