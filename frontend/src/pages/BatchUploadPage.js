import { useState, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { uploadBatch } from '../api/client';
import { useDocuments } from '../context/DocumentContext';
import { useToast } from '../components/Toast';
import './BatchUploadPage.css';

const MAX_FILES = 20;
const ALLOWED_EXT = ['.pdf', '.png', '.jpg', '.jpeg', '.doc', '.docx'];

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function hasAllowedExtension(filename) {
  const lower = (filename || '').toLowerCase();
  return ALLOWED_EXT.some((ext) => lower.endsWith(ext));
}

export default function BatchUploadPage() {
  const [files, setFiles] = useState([]);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const inputRef = useRef(null);
  const toast = useToast();
  const navigate = useNavigate();
  const { setRecentBatch } = useDocuments();

  const totalSize = files.reduce((sum, f) => sum + f.size, 0);
  const tooManyFiles = files.length > MAX_FILES;

  const addFiles = (newOnes) => {
    const combined = [...files];
    for (const f of newOnes) {
      if (!hasAllowedExtension(f.name)) {
        toast(`Skipped "${f.name}" — only PDF, JPG, PNG, DOC, DOCX are allowed`, 'error');
        continue;
      }
      // Dedupe by (name, size) — cheap and good enough for accidental double-drops.
      if (!combined.some((c) => c.name === f.name && c.size === f.size)) {
        combined.push(f);
      }
    }
    setFiles(combined);
  };

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length) {
      addFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files.length) {
      addFiles(Array.from(e.target.files));
    }
    // Allow re-selecting the same file later.
    if (inputRef.current) inputRef.current.value = '';
  };

  const removeFile = (idx) => {
    setFiles(files.filter((_, i) => i !== idx));
  };

  const handleUpload = async () => {
    if (!files.length) return;
    if (tooManyFiles) {
      toast(`Please remove files — max ${MAX_FILES} per batch.`, 'error');
      return;
    }
    setUploading(true);
    try {
      const data = await uploadBatch(files);
      // Cache batch ID + per-doc IDs so the Validation/Review pages can
      // present a doc selector instead of a free-text doc-ID input.
      setRecentBatch(
        data.batch_id,
        (data.documents || []).map((d) => d.id || d.documentId).filter(Boolean),
      );
      toast(`Batch of ${data.total_documents} document(s) submitted`, 'success');
      navigate(`/batches/${data.batch_id}`);
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <h1 className="batch-upload__title">Batch Upload</h1>
      <p className="batch-upload__subtitle">
        Drop up to {MAX_FILES} documents at once. Processing starts automatically;
        you&rsquo;ll watch per-file progress on the next screen.{' '}
        <Link to="/upload" className="batch-upload__inline-link">
          Only have one file? Use single upload &rarr;
        </Link>
      </p>

      <div
        className={`batch-upload__dropzone${dragActive ? ' batch-upload__dropzone--active' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <div className="batch-upload__dropzone-icon">+</div>
        <div className="batch-upload__dropzone-text">
          Drag and drop your documents here, or
        </div>
        <button
          className="batch-upload__browse-btn"
          type="button"
          onClick={(e) => { e.stopPropagation(); inputRef.current?.click(); }}
        >
          Browse Files
        </button>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />
      </div>

      {files.length > 0 && (
        <div className="batch-upload__queue">
          <div className="batch-upload__queue-header">
            <span>
              <strong>{files.length}</strong> file(s) queued &middot;{' '}
              <span className="batch-upload__queue-total">
                {formatSize(totalSize)} total
              </span>
            </span>
            <button
              type="button"
              className="batch-upload__clear"
              onClick={() => setFiles([])}
              disabled={uploading}
            >
              Clear all
            </button>
          </div>

          {tooManyFiles && (
            <div className="batch-upload__error">
              Too many files. Max {MAX_FILES} per batch — remove {files.length - MAX_FILES} to continue.
            </div>
          )}

          <ul className="batch-upload__file-list">
            {files.map((f, i) => (
              <li key={`${f.name}-${i}`} className="batch-upload__file-row">
                <span className="batch-upload__file-name">{f.name}</span>
                <span className="batch-upload__file-size">{formatSize(f.size)}</span>
                <button
                  type="button"
                  className="batch-upload__remove-btn"
                  onClick={() => removeFile(i)}
                  disabled={uploading}
                  aria-label={`Remove ${f.name}`}
                >
                  &times;
                </button>
              </li>
            ))}
          </ul>

          <div className="batch-upload__actions">
            <button
              className="batch-upload__submit-btn"
              onClick={handleUpload}
              disabled={uploading || tooManyFiles || !files.length}
            >
              {uploading
                ? `Uploading ${files.length} file(s)...`
                : `Upload & Process ${files.length} file(s)`}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
