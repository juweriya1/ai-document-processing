import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { uploadDocument } from '../api/client';
import { useToast } from '../components/Toast';
import './UploadPage.css';

const fmt = b => b < 1024 ? `${b} B` : b < 1048576 ? `${(b/1024).toFixed(1)} KB` : `${(b/1048576).toFixed(1)} MB`;

const UploadIcon = () => (
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" />
  </svg>
);
const FileIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8L14 2z"/><path d="M14 2v6h6"/>
  </svg>
);
const CheckIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
    <path d="M20 6L9 17l-5-5"/>
  </svg>
);
const XIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M18 6L6 18M6 6l12 12"/>
  </svg>
);

const FILE_TYPES = ['PDF', 'PNG', 'JPG', 'JPEG', 'DOC', 'DOCX'];

export default function UploadPage() {
  const [file, setFile]         = useState(null);
  const [dragActive, setDrag]   = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult]     = useState(null);
  const inputRef = useRef(null);
  const toast    = useToast();
  const navigate = useNavigate();

  const onDrag = e => { e.preventDefault(); e.stopPropagation(); setDrag(e.type === 'dragenter' || e.type === 'dragover'); };
  const onDrop = e => { e.preventDefault(); e.stopPropagation(); setDrag(false); if (e.dataTransfer.files[0]) { setFile(e.dataTransfer.files[0]); setResult(null); } };
  const onSelect = e => { if (e.target.files[0]) { setFile(e.target.files[0]); setResult(null); } };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    try {
      const data = await uploadDocument(file);
      setResult(data);
      setFile(null);
      toast('Document uploaded successfully', 'success');
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="page-wrap">
      <div className="page-hd">
        <div>
          <h1 className="page-title">Upload Document</h1>
          <p className="page-subtitle">Upload a document to begin the processing pipeline</p>
        </div>
      </div>

      {/* Drop zone */}
      <div
        className={`dropzone${dragActive ? ' dropzone--active' : ''}`}
        onDragEnter={onDrag} onDragLeave={onDrag} onDragOver={onDrag} onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
      >
        <div className="dropzone__icon"><UploadIcon /></div>
        <div className="dropzone__title">
          {dragActive ? 'Drop file here' : 'Drag & drop your document'}
        </div>
        <div className="dropzone__sub">or click to browse files from your computer</div>
        <div className="dropzone__types">
          {FILE_TYPES.map(t => <span key={t} className="dropzone__type-pill">.{t.toLowerCase()}</span>)}
        </div>
        <input ref={inputRef} type="file" accept=".pdf,.png,.jpg,.jpeg,.doc,.docx" onChange={onSelect} style={{ display:'none' }} />
      </div>

      {/* Selected file */}
      {file && (
        <div className="file-card">
          <div className="file-card__icon"><FileIcon /></div>
          <div className="file-card__info">
            <div className="file-card__name">{file.name}</div>
            <div className="file-card__size">{fmt(file.size)}</div>
          </div>
          <div className="file-card__actions">
            <button className="btn btn-ghost btn-sm" onClick={() => setFile(null)}><XIcon /> Remove</button>
            <button className="btn btn-primary" onClick={handleUpload} disabled={uploading}>
              {uploading ? <><span className="spinner" /> Uploading…</> : <><UploadIcon /> Upload</>}
            </button>
          </div>
        </div>
      )}

      {/* Upload result */}
      {result && (
        <div className="upload-result">
          <div className="upload-result__header">
            <div className="upload-result__icon"><CheckIcon /></div>
            <div className="upload-result__title">Upload Successful</div>
          </div>
          <div className="upload-result__grid">
            <span className="upload-result__label">Document ID</span>
            <span className="upload-result__val">{result.id}</span>
            <span className="upload-result__label">Filename</span>
            <span className="upload-result__val">{result.originalFilename}</span>
            <span className="upload-result__label">Type</span>
            <span className="upload-result__val">{result.fileType}</span>
            <span className="upload-result__label">Size</span>
            <span className="upload-result__val">{fmt(result.fileSize)}</span>
            <span className="upload-result__label">Status</span>
            <span className="upload-result__val">
              <span className="badge badge--info">{result.status}</span>
            </span>
          </div>
          <div className="upload-result__actions">
            <button className="btn btn-primary" onClick={() => navigate(`/processing/${result.id}`)}>
              Start Processing →
            </button>
            <button className="btn btn-ghost" onClick={() => setResult(null)}>Upload Another</button>
          </div>
        </div>
      )}
    </div>
  );
}
