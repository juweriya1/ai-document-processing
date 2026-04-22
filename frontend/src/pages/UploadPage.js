import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { uploadDocument } from '../api/client';
import { useToast } from '../components/Toast';
import './UploadPage.css';

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fileExt(name) {
  return name?.split('.').pop()?.toUpperCase() || 'FILE';
}

const SUPPORTED = ['.pdf', '.png', '.jpg', '.jpeg', '.doc', '.docx'];

export default function UploadPage() {
  const [file, setFile]             = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading]   = useState(false);
  const [progress, setProgress]     = useState(0);
  const [result, setResult]         = useState(null);
  const inputRef                    = useRef(null);
  const toast                       = useToast();
  const navigate                    = useNavigate();

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(e.type === 'dragenter' || e.type === 'dragover');
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) { setFile(dropped); setResult(null); }
  };

  const handleFileSelect = (e) => {
    const selected = e.target.files?.[0];
    if (selected) { setFile(selected); setResult(null); }
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setProgress(0);

    // Simulate progress
    const tick = setInterval(() => {
      setProgress(p => Math.min(p + Math.random() * 18, 88));
    }, 200);

    try {
      const data = await uploadDocument(file);
      clearInterval(tick);
      setProgress(100);
      setTimeout(() => {
        setResult(data);
        setFile(null);
        setProgress(0);
        toast('Document uploaded successfully', 'success');
      }, 300);
    } catch (err) {
      clearInterval(tick);
      setProgress(0);
      toast(err.message, 'error');
    } finally {
      setUploading(false);
    }
  };

  const clearFile = () => {
    setFile(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <div className="page-wrap">
      <div className="page-header">
        <h1 className="page-title">Upload Document</h1>
        <p className="page-subtitle">
          Upload invoices, contracts or any document for AI-powered extraction
        </p>
      </div>

      {/* Drop zone */}
      {!result && (
        <div
          className={`upload__dropzone${dragActive ? ' upload__dropzone--active' : ''}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => !file && inputRef.current?.click()}
        >
          <svg className="upload__drop-icon" viewBox="0 0 64 64" fill="none">
            <rect x="8" y="12" width="48" height="40" rx="6" stroke="currentColor" strokeWidth="2"/>
            <path d="M32 42V26M32 26L24 33M32 26L40 33" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <div className="upload__drop-title">
            {dragActive ? 'Drop to upload' : 'Drag & drop your document'}
          </div>
          <div className="upload__drop-desc">
            Or click to browse. Max 50MB.
          </div>
          <div className="upload__drop-types">
            {SUPPORTED.map(t => (
              <span className="upload__type-tag" key={t}>{t}</span>
            ))}
          </div>
          <input
            ref={inputRef}
            type="file"
            accept={SUPPORTED.join(',')}
            onChange={handleFileSelect}
            style={{ display: 'none' }}
          />
        </div>
      )}

      {/* Selected file */}
      {file && !uploading && !result && (
        <div className="upload__file-card">
          <div className="upload__file-icon-wrap">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8L14 2z" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M14 2v6h6M9 13h6M9 17h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </div>
          <div className="upload__file-info">
            <div className="upload__file-name">{file.name}</div>
            <div className="upload__file-size">{formatSize(file.size)} · {fileExt(file.name)}</div>
          </div>
          <div className="upload__file-actions">
            <button className="btn btn--ghost btn--sm" onClick={clearFile}>Remove</button>
            <button className="btn btn--primary" onClick={handleUpload}>
              <svg width="15" height="15" viewBox="0 0 20 20" fill="none"><path d="M10 13V4M10 4L7 7M10 4L13 7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/><path d="M3 13v2a2 2 0 002 2h10a2 2 0 002-2v-2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              Upload
            </button>
          </div>
        </div>
      )}

      {/* Upload progress */}
      {uploading && (
        <div className="upload__progress">
          <div className="upload__progress-label">
            <span>Uploading {file?.name}…</span>
            <span>{Math.round(progress)}%</span>
          </div>
          <div className="upload__progress-track">
            <div className="upload__progress-fill" style={{ width: `${progress}%` }} />
          </div>
        </div>
      )}

      {/* Success result */}
      {result && (
        <div className="upload__result">
          <div className="upload__result-header">
            <div className="upload__result-icon">
              <svg width="18" height="18" viewBox="0 0 20 20" fill="none">
                <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5"/>
                <path d="M6.5 10l2.5 2.5 4.5-4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div>
              <div className="upload__result-title">Upload successful</div>
              <div className="upload__result-subtitle">Document is ready for processing</div>
            </div>
            <div style={{ marginLeft: 'auto' }}>
              <span className="badge badge--success">Ready</span>
            </div>
          </div>

          <div className="upload__result-grid">
            <span className="upload__result-label">Document ID</span>
            <span className="upload__result-value">{result.id}</span>
            <span className="upload__result-label">Filename</span>
            <span className="upload__result-value">{result.originalFilename}</span>
            <span className="upload__result-label">Type</span>
            <span className="upload__result-value">{result.fileType}</span>
            <span className="upload__result-label">Size</span>
            <span className="upload__result-value">{formatSize(result.fileSize)}</span>
            <span className="upload__result-label">Status</span>
            <span className="upload__result-value">{result.status}</span>
          </div>

          <div className="upload__result-actions">
            <button className="btn btn--primary" onClick={() => navigate(`/processing/${result.id}`)}>
              <svg width="15" height="15" viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="7.5" stroke="currentColor" strokeWidth="1.5"/><path d="M10 6v4l3 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
              Process Document
            </button>
            <button className="btn btn--secondary" onClick={() => setResult(null)}>
              Upload Another
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
