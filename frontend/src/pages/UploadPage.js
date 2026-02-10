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

export default function UploadPage() {
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const inputRef = useRef(null);
  const toast = useToast();
  const navigate = useNavigate();

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
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
      setResult(null);
    }
  };

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setResult(null);
    }
  };

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
    <div>
      <h1 className="upload__title">Upload Document</h1>

      <div
        className={`upload__dropzone${dragActive ? ' upload__dropzone--active' : ''}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <div className="upload__dropzone-icon">+</div>
        <div className="upload__dropzone-text">
          Drag and drop your document here, or
        </div>
        <button
          className="upload__browse-btn"
          type="button"
          onClick={(e) => { e.stopPropagation(); inputRef.current?.click(); }}
        >
          Browse Files
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />
      </div>

      {file && (
        <div className="upload__file-info">
          <div>
            <span className="upload__file-name">{file.name}</span>
            <span className="upload__file-size">{formatSize(file.size)}</span>
          </div>
          <button
            className="upload__submit-btn"
            onClick={handleUpload}
            disabled={uploading}
          >
            {uploading ? 'Uploading...' : 'Upload'}
          </button>
        </div>
      )}

      {result && (
        <div className="upload__result">
          <div className="upload__result-title">Upload Successful</div>
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
            <button
              className="upload__process-btn"
              onClick={() => navigate(`/processing/${result.id}`)}
            >
              Process Document
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
