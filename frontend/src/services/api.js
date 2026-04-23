import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';

const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Handle 401 globally — log out and redirect
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

/* ─────────────── AUTH ─────────────── */
export const authAPI = {
  login: (email, password) =>
    api.post('/api/auth/login', { email, password }),

  register: (name, email, password, role = 'enterprise_user') =>
  api.post('/api/auth/register', { name, email, password, role }),

  me: () =>
    api.get('/api/auth/me'),
};

/* ─────────────── DOCUMENTS ─────────────── */
export const documentsAPI = {
  list: (params = {}) =>
    api.get('/api/documents', { params }),

  get: (id) =>
    api.get(`/api/documents/${id}`),

  upload: (formData, onProgress) =>
    api.post('/api/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress) onProgress(Math.round((e.loaded * 100) / e.total));
      },
    }),

  delete: (id) =>
    api.delete(`/api/documents/${id}`),
};

/* ─────────────── PROCESSING ─────────────── */
export const processingAPI = {
  start: (documentId, options = {}) =>
    api.post('/api/processing/start', { document_id: documentId, ...options }),

  status: (jobId) =>
    api.get(`/api/processing/status/${jobId}`),

  list: (params = {}) =>
    api.get('/api/processing/jobs', { params }),

  retry: (jobId) =>
    api.post(`/api/processing/retry/${jobId}`),

  cancel: (jobId) =>
    api.post(`/api/processing/cancel/${jobId}`),
};

/* ─────────────── VALIDATION ─────────────── */
export const validationAPI = {
  list: (params = {}) =>
    api.get('/api/validation', { params }),

  get: (id) =>
    api.get(`/api/validation/${id}`),

  submit: (id, fields) =>
    api.post(`/api/validation/${id}/submit`, { fields }),

  approve: (id) =>
    api.post(`/api/validation/${id}/approve`),

  reject: (id, reason) =>
    api.post(`/api/validation/${id}/reject`, { reason }),
};

/* ─────────────── REVIEW ─────────────── */
export const reviewAPI = {
  list: (params = {}) =>
    api.get('/api/review', { params }),

  get: (id) =>
    api.get(`/api/review/${id}`),

  approve: (id, notes = '') =>
    api.post(`/api/review/${id}/approve`, { notes }),

  reject: (id, reason) =>
    api.post(`/api/review/${id}/reject`, { reason }),

  addComment: (id, comment) =>
    api.post(`/api/review/${id}/comment`, { comment }),
};

/* ─────────────── ANALYTICS ─────────────── */
export const analyticsAPI = {
  dashboard: () =>
    api.get('/api/analytics/dashboard'),

  processing: (params = {}) =>
    api.get('/api/analytics/processing', { params }),

  accuracy: (params = {}) =>
    api.get('/api/analytics/accuracy', { params }),

  throughput: (params = {}) =>
    api.get('/api/analytics/throughput', { params }),
};

export default api;
