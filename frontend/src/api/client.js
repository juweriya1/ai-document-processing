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

// Validation
export function getDocumentFields(documentId) {
  return request(`/api/documents/${documentId}/fields`);
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