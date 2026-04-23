import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { useNavigate } from 'react-router-dom';
import { documentsAPI } from '../services/api';
import PageHeader from '../components/shared/PageHeader';
import toast from 'react-hot-toast';
import './UploadPage.css';

const MAX_SIZE = 50 * 1024 * 1024; // 50MB
const ACCEPTED = {
  'application/pdf': ['.pdf'],
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'image/tiff': ['.tiff', '.tif'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
};

const FILE_ICONS = {
  'application/pdf': '📄',
  'image/png': '🖼️',
  'image/jpeg': '🖼️',
  'image/tiff': '🖼️',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '📝',
};

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const DOC_TYPE_HINTS = [
  { icon: '🧾', label: 'Invoices', desc: 'PDF, JPEG, TIFF supported' },
  { icon: '📋', label: 'Contracts', desc: 'PDF, DOCX supported' },
  { icon: '📊', label: 'Reports', desc: 'PDF, DOCX supported' },
  { icon: '📝', label: 'Forms', desc: 'PDF, PNG, TIFF supported' },
];

export default function UploadPage() {
  const navigate = useNavigate();
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [docType, setDocType] = useState('auto');

  const onDrop = useCallback((accepted, rejected) => {
    if (rejected.length) {
      rejected.forEach((r) => {
        const err = r.errors[0];
        if (err.code === 'file-too-large') toast.error(`${r.file.name} exceeds 50MB limit`, { className: 'custom-toast' });
        else toast.error(err.message, { className: 'custom-toast' });
      });
    }
    setFiles((prev) => [
      ...prev,
      ...accepted.map((f) => ({
        file: f,
        id: `${Date.now()}-${Math.random()}`,
        progress: 0,
        status: 'queued', // queued | uploading | done | error
        preview: f.type.startsWith('image/') ? URL.createObjectURL(f) : null,
      })),
    ]);
  }, []);

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: ACCEPTED,
    maxSize: MAX_SIZE,
    multiple: true,
  });

  const removeFile = (id) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  };

  const uploadAll = async () => {
    if (!files.length) return;
    setUploading(true);

    const results = await Promise.allSettled(
      files.filter((f) => f.status === 'queued').map(async (item) => {
        setFiles((prev) =>
          prev.map((f) => f.id === item.id ? { ...f, status: 'uploading' } : f)
        );
        const formData = new FormData();
        formData.append('file', item.file);
        formData.append('doc_type', docType);

        try {
          await documentsAPI.upload(formData, (pct) => {
            setFiles((prev) =>
              prev.map((f) => f.id === item.id ? { ...f, progress: pct } : f)
            );
          });
          setFiles((prev) =>
            prev.map((f) => f.id === item.id ? { ...f, status: 'done', progress: 100 } : f)
          );
        } catch (err) {
          setFiles((prev) =>
            prev.map((f) => f.id === item.id ? { ...f, status: 'error' } : f)
          );
          throw err;
        }
      })
    );

    const succeeded = results.filter((r) => r.status === 'fulfilled').length;
    const failed = results.filter((r) => r.status === 'rejected').length;

    if (succeeded) toast.success(`${succeeded} document${succeeded > 1 ? 's' : ''} uploaded successfully`, { className: 'custom-toast' });
    if (failed) toast.error(`${failed} upload${failed > 1 ? 's' : ''} failed`, { className: 'custom-toast' });

    setUploading(false);
    if (succeeded && !failed) {
      setTimeout(() => navigate('/processing'), 1200);
    }
  };

  const queuedCount = files.filter((f) => f.status === 'queued').length;

  return (
    <div className="page-enter">
      <PageHeader
        title="Document Upload"
        subtitle="Ingest documents into the AI processing pipeline"
        actions={
          files.length > 0 && (
            <div className="flex gap-3 items-center">
              <span className="upload-file-count">{files.length} file{files.length > 1 ? 's' : ''} staged</span>
              <button
                className="btn btn-secondary btn-sm"
                onClick={() => setFiles([])}
                disabled={uploading}
              >
                Clear all
              </button>
              <button
                className="btn btn-primary"
                onClick={uploadAll}
                disabled={uploading || queuedCount === 0}
              >
                {uploading ? (
                  <><span className="btn-spinner" style={{ borderTopColor: '#080c18' }} />Processing…</>
                ) : (
                  <>Upload {queuedCount} file{queuedCount !== 1 ? 's' : ''}</>
                )}
              </button>
            </div>
          )
        }
      />

      <div className="upload-content">
        <div className="upload-main">
          {/* Drop zone */}
          <div
            {...getRootProps()}
            className={`dropzone ${isDragActive ? 'dropzone--active' : ''} ${isDragReject ? 'dropzone--reject' : ''}`}
          >
            <input {...getInputProps()} />
            <div className="dropzone-inner">
              <div className="dropzone-icon-wrap">
                <svg width="36" height="36" viewBox="0 0 36 36" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                  <path d="M18 22V10M12 16l6-6 6 6" />
                  <path d="M6 26v2a2 2 0 002 2h20a2 2 0 002-2v-2" />
                </svg>
              </div>
              {isDragActive && !isDragReject ? (
                <div className="dropzone-text">
                  <h3>Release to add files</h3>
                  <p>Drop your documents here</p>
                </div>
              ) : isDragReject ? (
                <div className="dropzone-text dropzone-text--error">
                  <h3>Unsupported file type</h3>
                  <p>Please use PDF, PNG, JPEG, TIFF, or DOCX</p>
                </div>
              ) : (
                <div className="dropzone-text">
                  <h3>Drag & drop documents</h3>
                  <p>or <span className="dropzone-browse">click to browse</span></p>
                  <div className="dropzone-hints">
                    <span className="tag">PDF</span>
                    <span className="tag">PNG</span>
                    <span className="tag">JPEG</span>
                    <span className="tag">TIFF</span>
                    <span className="tag">DOCX</span>
                    <span className="tag">Max 50MB</span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Document type selector */}
          <div className="card doc-type-card">
            <div className="doc-type-header">
              <h4>Document Type</h4>
              <p>Selecting the correct type improves extraction accuracy</p>
            </div>
            <div className="doc-type-grid">
              <label className={`doc-type-option ${docType === 'auto' ? 'doc-type-option--active' : ''}`}>
                <input type="radio" name="docType" value="auto" checked={docType === 'auto'} onChange={() => setDocType('auto')} />
                <span className="doc-type-icon">🤖</span>
                <span className="doc-type-label">Auto-detect</span>
              </label>
              {DOC_TYPE_HINTS.map((t) => (
                <label
                  key={t.label}
                  className={`doc-type-option ${docType === t.label.toLowerCase() ? 'doc-type-option--active' : ''}`}
                >
                  <input
                    type="radio"
                    name="docType"
                    value={t.label.toLowerCase()}
                    checked={docType === t.label.toLowerCase()}
                    onChange={() => setDocType(t.label.toLowerCase())}
                  />
                  <span className="doc-type-icon">{t.icon}</span>
                  <span className="doc-type-label">{t.label}</span>
                  <span className="doc-type-desc">{t.desc}</span>
                </label>
              ))}
            </div>
          </div>

          {/* File staging area */}
          {files.length > 0 && (
            <div className="staged-files">
              <h4 className="staged-title">Staged Files</h4>
              <div className="staged-list">
                {files.map((item) => (
                  <div key={item.id} className={`staged-item staged-item--${item.status}`}>
                    <div className="staged-thumb">
                      {item.preview ? (
                        <img src={item.preview} alt="" />
                      ) : (
                        <span>{FILE_ICONS[item.file.type] || '📄'}</span>
                      )}
                    </div>
                    <div className="staged-info">
                      <span className="staged-name">{item.file.name}</span>
                      <span className="staged-meta">
                        {formatSize(item.file.size)}
                        {item.file.type && <> · <span className="mono">{item.file.type.split('/')[1].toUpperCase()}</span></>}
                      </span>
                      {item.status === 'uploading' && (
                        <div className="progress-bar staged-progress">
                          <div className="progress-fill" style={{ width: `${item.progress}%` }} />
                        </div>
                      )}
                    </div>
                    <div className="staged-status">
                      {item.status === 'queued' && <span className="badge badge-default">Queued</span>}
                      {item.status === 'uploading' && (
                        <span className="badge badge-info">{item.progress}%</span>
                      )}
                      {item.status === 'done' && <span className="badge badge-success">✓ Done</span>}
                      {item.status === 'error' && <span className="badge badge-danger">Failed</span>}
                    </div>
                    {item.status !== 'uploading' && item.status !== 'done' && (
                      <button
                        className="staged-remove"
                        onClick={() => removeFile(item.id)}
                        aria-label="Remove file"
                      >
                        ×
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Empty state */}
          {files.length === 0 && (
            <div className="card upload-guidelines">
              <h4>Processing Pipeline</h4>
              <div className="pipeline-steps">
                {[
                  { step: '01', name: 'Upload', desc: 'Secure document ingestion' },
                  { step: '02', name: 'Pre-process', desc: 'Deskewing, denoising, format normalization' },
                  { step: '03', name: 'OCR', desc: 'Character recognition across 50+ languages' },
                  { step: '04', name: 'Extract', desc: 'NLP-based field extraction & classification' },
                  { step: '05', name: 'Validate', desc: 'Rule-based validation & confidence scoring' },
                  { step: '06', name: 'Review', desc: 'Human-in-the-loop quality assurance' },
                ].map((s, i) => (
                  <div key={s.step} className="pipeline-step">
                    <div className="pipeline-step-num mono">{s.step}</div>
                    {i < 5 && <div className="pipeline-step-line" />}
                    <div className="pipeline-step-body">
                      <span className="pipeline-step-name">{s.name}</span>
                      <span className="pipeline-step-desc">{s.desc}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
