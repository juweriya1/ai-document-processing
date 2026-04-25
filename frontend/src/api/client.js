const API_URL = process.env.REACT_APP_API_URL || '';

function getToken() {
  return localStorage.getItem('idp_token');
}

async function request(endpoint, options = {}) {
  const token = getToken();
  const headers = { ...options.headers };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    localStorage.removeItem('idp_token');
    localStorage.removeItem('idp_user');
    window.location.href = '/login';
    throw new Error('Session expired');
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));
    throw new Error(error.detail || 'Request failed');
  }

  return response.json();
}

// Auth
export function healthCheck() {
  return request('/health');
}

export function login(email, password) {
  return request('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export function register(email, password, name, role) {
  return request('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, name, role }),
  });
}

// Documents
export function uploadDocument(file) {
  const formData = new FormData();
  formData.append('file', file);
  return request('/api/documents/upload', {
    method: 'POST',
    body: formData,
  });
}

export function processDocument(documentId) {
  return request(`/api/documents/${documentId}/process`, {
    method: 'POST',
  });
}

export function getDocumentStatus(documentId) {
  return request(`/api/documents/${documentId}/status`);
}

// Batches
export function uploadBatch(files) {
  const formData = new FormData();
  files.forEach((f) => formData.append('files', f));
  return request('/api/batches/upload', {
    method: 'POST',
    body: formData,
  });
}

export function getBatch(batchId) {
  return request(`/api/batches/${batchId}`);
}

export function reprocessBatch(batchId) {
  return request(`/api/batches/${batchId}/process`, {
    method: 'POST',
  });
}

export function listBatches(limit = 5) {
  return request(`/api/batches?limit=${limit}`);
}

// Documents (list / metadata)
export function listDocuments({ skip = 0, limit = 50, batchId } = {}) {
  const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
  if (batchId) params.set('batchId', batchId);
  return request(`/api/documents?${params.toString()}`);
}

export function getDocumentMetadata(documentId) {
  return request(`/api/documents/${documentId}`);
}

// Validation
export function getDocumentFields(documentId, hitl = false) {
  return request(`/api/documents/${documentId}/fields?hitl=${hitl}`);
}

export function getDocumentFieldsWithStats(documentId, hitl = false) {
  // Returns { fields, total, shown, skipped } using the X-HITL-* headers
  const token = localStorage.getItem('idp_token');
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  return fetch(`${API_URL}/api/documents/${documentId}/fields?hitl=${hitl}`, { headers })
    .then(async (res) => {
      if (!res.ok) throw new Error('Failed to load fields');
      const fields = await res.json();
      return {
        fields,
        total: parseInt(res.headers.get('X-HITL-Total-Fields') ?? fields.length, 10),
        shown: parseInt(res.headers.get('X-HITL-Shown-Fields') ?? fields.length, 10),
        skipped: parseInt(res.headers.get('X-HITL-Skipped-Fields') ?? 0, 10),
        expectedResidualErrors: parseFloat(
          res.headers.get('X-HITL-Expected-Residual-Errors') ?? '0'
        ),
      };
    });
}

export function validateDocument(documentId) {
  return request(`/api/documents/${documentId}/validate`, {
    method: 'POST',
  });
}

export function submitCorrection(documentId, fieldId, correctedValue) {
  return request(`/api/documents/${documentId}/corrections`, {
    method: 'POST',
    body: JSON.stringify({ fieldId, correctedValue }),
  });
}

export function getDocumentCorrections(documentId) {
  return request(`/api/documents/${documentId}/corrections`);
}

export function approveDocument(documentId) {
  return request(`/api/documents/${documentId}/approve`, {
    method: 'POST',
  });
}

export function rejectDocument(documentId, reason) {
  return request(`/api/documents/${documentId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  });
}

// Analytics
export function getDashboard() {
  return request('/api/analytics/dashboard');
}

export function getSpendByVendor() {
  return request('/api/analytics/spend/by-vendor');
}

export function getSpendByMonth(months = 12) {
  return request(`/api/analytics/spend/by-month?months=${months}`);
}

export function getSuppliers() {
  return request('/api/analytics/suppliers');
}

export function refreshSuppliers() {
  return request('/api/analytics/suppliers/refresh', {
    method: 'POST',
  });
}

export function getPredictions() {
  return request('/api/analytics/predictions');
}

export function getAnomalies() {
  return request('/api/analytics/anomalies');
}

// Admin
export function listUsers() {
  return request('/api/admin/users');
}

export function createUser(email, password, name, role) {
  return request('/api/admin/users', {
    method: 'POST',
    body: JSON.stringify({ email, password, name, role }),
  });
}

export function updateUser(userId, name, role) {
  return request(`/api/admin/users/${userId}`, {
    method: 'PUT',
    body: JSON.stringify({ name, role }),
  });
}

export function deactivateUser(userId) {
  return request(`/api/admin/users/${userId}/deactivate`, {
    method: 'POST',
  });
}

export function activateUser(userId) {
  return request(`/api/admin/users/${userId}/activate`, {
    method: 'POST',
  });
}

// HITL Calibration
export function runCalibration() {
  return request('/api/admin/calibrate', { method: 'POST' });
}

export function getCalibrationStatus() {
  return request('/api/admin/calibrate');
}

// Document file preview
export function getDocumentFileUrl(documentId) {
  const token = getToken();
  const base = API_URL || '';
  return `${base}/api/documents/${documentId}/file?token=${encodeURIComponent(token || '')}`;
}

export function getTrustOverview() {
  return request('/api/analytics/trust/overview');
}

export function getTrustForDocument(documentId) {
  return request(`/api/analytics/trust/document/${documentId}`);
}

export function getFlaggedDocuments() {
  return request('/api/analytics/trust/flagged');
}

export function getVendorRisk() {
  return request('/api/analytics/vendor-risk');
}

// BI + widget preferences + extra analytics
export function getBIConfig() {
  return request('/api/bi/config');
}

export function getWidgetCatalog() {
  return request('/api/analytics/widgets/catalog');
}

export function getWidgetPreferences() {
  return request('/api/analytics/widgets/preferences');
}

export function saveWidgetPreferences(payload) {
  return request('/api/analytics/widgets/preferences', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export function getSLAMetrics() {
  return request('/api/analytics/sla');
}

export function getThroughput() {
  return request('/api/analytics/throughput');
}

export function getCorrectionPatterns() {
  return request('/api/analytics/correction-patterns');
}

export function getOCRDrift() {
  return request('/api/analytics/ocr-drift');
}