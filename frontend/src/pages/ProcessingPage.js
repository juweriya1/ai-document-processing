import React, { useState, useEffect, useRef } from 'react';
import { processingAPI, documentsAPI } from '../services/api';
import PageHeader from '../components/shared/PageHeader';
import toast from 'react-hot-toast';
import './ProcessingPage.css';

const PIPELINE_STAGES = [
  { id: 'ingest', name: 'Ingestion', desc: 'Secure document intake and format detection', icon: '📥' },
  { id: 'preprocess', name: 'Pre-process', desc: 'Image normalization, deskewing, denoising', icon: '🔧' },
  { id: 'ocr', name: 'OCR', desc: 'Character recognition with confidence scoring', icon: '👁️' },
  { id: 'extract', name: 'Extraction', desc: 'NLP field identification and classification', icon: '🧠' },
  { id: 'validate', name: 'Validation', desc: 'Rule-based checks and anomaly detection', icon: '✅' },
  { id: 'output', name: 'Output', desc: 'Structured data export and routing', icon: '📤' },
];

const MOCK_JOBS = [
  {
    id: 'JOB-0892', doc: 'Q4_Invoice_Batch.pdf', status: 'completed',
    stages: { ingest: 'done', preprocess: 'done', ocr: 'done', extract: 'done', validate: 'done', output: 'done' },
    confidence: 98, pages: 12, started: '2 min ago', duration: '14.2s',
    logs: [
      { time: '14:23:01', level: 'info', msg: 'Document ingested (12 pages, 4.2MB)' },
      { time: '14:23:02', level: 'info', msg: 'Pre-processing complete — deskew applied to 3 pages' },
      { time: '14:23:05', level: 'info', msg: 'OCR completed — 99.1% character confidence' },
      { time: '14:23:09', level: 'info', msg: 'Extracted 47 fields across 12 invoices' },
      { time: '14:23:12', level: 'info', msg: 'Validation passed — all rules satisfied' },
      { time: '14:23:14', level: 'success', msg: 'Pipeline complete — ready for review' },
    ],
  },
  {
    id: 'JOB-0891', doc: 'ServiceAgreement_v3.pdf', status: 'review',
    stages: { ingest: 'done', preprocess: 'done', ocr: 'done', extract: 'done', validate: 'warn', output: 'pending' },
    confidence: 82, pages: 8, started: '11 min ago', duration: '9.8s',
    logs: [
      { time: '14:12:10', level: 'info', msg: 'Document ingested (8 pages, 1.9MB)' },
      { time: '14:12:12', level: 'warn', msg: 'Scan quality low on pages 3, 7 — enhancement applied' },
      { time: '14:12:16', level: 'info', msg: 'OCR completed — 87.4% character confidence' },
      { time: '14:12:19', level: 'warn', msg: 'Party name ambiguous — manual review flagged' },
      { time: '14:12:20', level: 'warn', msg: 'Validation warning: 2 low-confidence fields' },
    ],
  },
  {
    id: 'JOB-0890', doc: 'EmployeeRecords_Oct.pdf', status: 'processing',
    stages: { ingest: 'done', preprocess: 'done', ocr: 'active', extract: 'pending', validate: 'pending', output: 'pending' },
    confidence: null, pages: 34, started: '18 min ago', duration: null,
    logs: [
      { time: '14:05:20', level: 'info', msg: 'Document ingested (34 pages, 8.7MB)' },
      { time: '14:05:23', level: 'info', msg: 'Pre-processing complete' },
      { time: '14:05:25', level: 'info', msg: 'OCR in progress — page 12/34…' },
    ],
  },
  {
    id: 'JOB-0888', doc: 'TaxForms_2024.pdf', status: 'error',
    stages: { ingest: 'done', preprocess: 'error', ocr: 'pending', extract: 'pending', validate: 'pending', output: 'pending' },
    confidence: null, pages: 6, started: '1 hr ago', duration: '3.1s',
    logs: [
      { time: '13:24:01', level: 'info', msg: 'Document ingested (6 pages, 2.1MB)' },
      { time: '13:24:04', level: 'error', msg: 'Pre-processing failed: encrypted PDF (password protected)' },
    ],
  },
];

const STATUS_MAP = {
  completed:  { label: 'Completed',  cls: 'badge-success' },
  review:     { label: 'Needs Review', cls: 'badge-warn' },
  processing: { label: 'Processing',  cls: 'badge-info' },
  error:      { label: 'Error',       cls: 'badge-danger' },
};

const STAGE_MAP = {
  done:    { cls: 'stage--done',    icon: '✓' },
  active:  { cls: 'stage--active',  icon: '⟳' },
  pending: { cls: 'stage--pending', icon: '○' },
  warn:    { cls: 'stage--warn',    icon: '!' },
  error:   { cls: 'stage--error',   icon: '✗' },
};

const LOG_LEVEL_CLS = { info: '', warn: 'log--warn', error: 'log--error', success: 'log--success' };

export default function ProcessingPage() {
  const [jobs, setJobs] = useState(MOCK_JOBS);
  const [selected, setSelected] = useState(MOCK_JOBS[0]);
  const [loading, setLoading] = useState(false);
  const logRef = useRef(null);

  useEffect(() => {
    processingAPI.list()
      .then((res) => {
        if (res.data?.jobs?.length) {
          setJobs(res.data.jobs);
          setSelected(res.data.jobs[0]);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [selected]);

  const handleRetry = async (jobId) => {
    try {
      await processingAPI.retry(jobId);
      toast.success('Job queued for retry', { className: 'custom-toast' });
    } catch {
      toast.error('Retry failed', { className: 'custom-toast' });
    }
  };

  const handleCancel = async (jobId) => {
    try {
      await processingAPI.cancel(jobId);
      toast.success('Job cancelled', { className: 'custom-toast' });
    } catch {
      toast.error('Cancel failed', { className: 'custom-toast' });
    }
  };

  return (
    <div className="page-enter">
      <PageHeader
        title="Processing Pipeline"
        subtitle="Monitor AI processing jobs and pipeline stage execution"
        badge={{ text: `${jobs.filter(j => j.status === 'processing').length} Active`, type: 'info' }}
        actions={
          <button className="btn btn-secondary btn-sm">Filter jobs</button>
        }
      />

      <div className="processing-layout">
        {/* Jobs sidebar */}
        <div className="jobs-panel">
          <div className="jobs-panel-header">
            <span className="section-title">All Jobs</span>
            <span className="job-count">{jobs.length}</span>
          </div>
          <div className="jobs-panel-list">
            {jobs.map((job) => (
              <button
                key={job.id}
                className={`job-card ${selected?.id === job.id ? 'job-card--selected' : ''}`}
                onClick={() => setSelected(job)}
              >
                <div className="job-card-top">
                  <span className="job-card-id mono">{job.id}</span>
                  <span className={`badge ${STATUS_MAP[job.status]?.cls}`}>
                    {job.status === 'processing' && <span className="pulse-dot active" style={{ width: 6, height: 6 }} />}
                    {STATUS_MAP[job.status]?.label}
                  </span>
                </div>
                <div className="job-card-doc">{job.doc}</div>
                <div className="job-card-meta">
                  <span>{job.pages} pages</span>
                  <span>·</span>
                  <span>{job.started}</span>
                  {job.duration && <><span>·</span><span>{job.duration}</span></>}
                </div>
                {job.confidence !== null && (
                  <div className="confidence-bar" style={{ marginTop: 6 }}>
                    <div className="confidence-track">
                      <div
                        className={`confidence-fill ${job.confidence >= 90 ? 'high' : job.confidence >= 75 ? 'medium' : 'low'}`}
                        style={{ width: `${job.confidence}%` }}
                      />
                    </div>
                    <span className="mono" style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>
                      {job.confidence}%
                    </span>
                  </div>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Detail panel */}
        {selected && (
          <div className="job-detail">
            {/* Header */}
            <div className="job-detail-header">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="job-detail-title">{selected.doc}</h2>
                  <span className={`badge ${STATUS_MAP[selected.status]?.cls}`}>
                    {STATUS_MAP[selected.status]?.label}
                  </span>
                </div>
                <div className="job-detail-meta mono">
                  {selected.id} · {selected.pages} pages ·{' '}
                  Started {selected.started}
                  {selected.duration && ` · Completed in ${selected.duration}`}
                </div>
              </div>
              <div className="flex gap-2">
                {selected.status === 'error' && (
                  <button className="btn btn-secondary btn-sm" onClick={() => handleRetry(selected.id)}>
                    Retry
                  </button>
                )}
                {selected.status === 'processing' && (
                  <button className="btn btn-danger btn-sm" onClick={() => handleCancel(selected.id)}>
                    Cancel
                  </button>
                )}
                {selected.status === 'review' && (
                  <a href="/review" className="btn btn-primary btn-sm">
                    Open Review →
                  </a>
                )}
              </div>
            </div>

            {/* Pipeline stages */}
            <div className="pipeline-viz">
              <div className="pipeline-stages-row">
                {PIPELINE_STAGES.map((stage, i) => {
                  const stageStatus = selected.stages[stage.id] || 'pending';
                  const sm = STAGE_MAP[stageStatus];
                  return (
                    <React.Fragment key={stage.id}>
                      <div className={`pipeline-stage-node ${sm.cls}`}>
                        <div className="stage-indicator">
                          <span className={`stage-icon ${stageStatus === 'active' ? 'stage-spin' : ''}`}>
                            {sm.icon}
                          </span>
                        </div>
                        <div className="stage-label">
                          <span className="stage-name">{stage.name}</span>
                          <span className="stage-desc">{stage.desc}</span>
                        </div>
                      </div>
                      {i < PIPELINE_STAGES.length - 1 && (
                        <div className={`pipeline-connector ${stageStatus === 'done' ? 'pipeline-connector--done' : ''}`} />
                      )}
                    </React.Fragment>
                  );
                })}
              </div>
            </div>

            {/* Stats bar */}
            {selected.confidence !== null && (
              <div className="job-stats-bar">
                <div className="job-stat">
                  <span className="job-stat-label">Confidence</span>
                  <div className="job-stat-conf">
                    <div className="confidence-track" style={{ flex: 1 }}>
                      <div
                        className={`confidence-fill ${selected.confidence >= 90 ? 'high' : selected.confidence >= 75 ? 'medium' : 'low'}`}
                        style={{ width: `${selected.confidence}%` }}
                      />
                    </div>
                    <span className="mono" style={{ fontSize: '0.85rem' }}>{selected.confidence}%</span>
                  </div>
                </div>
                <div className="job-stat-divider" />
                <div className="job-stat">
                  <span className="job-stat-label">Pages</span>
                  <span className="job-stat-val">{selected.pages}</span>
                </div>
                <div className="job-stat-divider" />
                <div className="job-stat">
                  <span className="job-stat-label">Duration</span>
                  <span className="job-stat-val">{selected.duration || '—'}</span>
                </div>
              </div>
            )}

            {/* Log rail */}
            <div className="log-rail">
              <div className="log-rail-header">
                <span className="section-title">Execution Log</span>
                <span className="log-count mono">{selected.logs?.length} events</span>
              </div>
              <div className="log-entries" ref={logRef}>
                {selected.logs?.map((log, i) => (
                  <div key={i} className={`log-entry ${LOG_LEVEL_CLS[log.level]}`}>
                    <span className="log-time mono">{log.time}</span>
                    <span className={`log-level-tag ${log.level}`}>{log.level}</span>
                    <span className="log-msg">{log.msg}</span>
                  </div>
                ))}
                {selected.status === 'processing' && (
                  <div className="log-entry log-entry--streaming">
                    <span className="log-time mono">—</span>
                    <span className="log-level-tag info">info</span>
                    <span className="log-msg">
                      <span className="log-cursor" />
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
