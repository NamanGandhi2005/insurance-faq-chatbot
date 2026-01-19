import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const authAPI = {
  register: (data) => api.post('/auth/register', data),
  login: (username, password) => {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);
    return api.post('/auth/login', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  }
};

export const chatAPI = {
  ask: (data) => api.post('/chat/ask', data),
  getSuggestions: () => api.get('/chat/suggestions')
};

export const productsAPI = {
  list: () => api.get('/products/'),
  get: (id) => api.get(`/products/${id}`),
  create: (data) => api.post('/products/', data),
  update: (id, data) => api.put(`/products/${id}`, data),
  delete: (id) => api.delete(`/products/${id}`)
};

export const adminAPI = {
  uploadPDF: (productId, file) => {
    const formData = new FormData();
    formData.append('product_id', productId);
    formData.append('file', file);
    return api.post('/admin/upload-pdf', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  },
  listPDFs: (productId) => api.get(`/admin/pdfs/${productId}`),
  getPDFStatus: (productId, pdfId) => api.get(`/admin/products/${productId}/pdfs/${pdfId}/status`),
  deletePDF: (pdfId) => api.delete(`/admin/pdfs/${pdfId}`),
  reprocessPDFs: (productId) => api.post(`/admin/products/${productId}/reprocess-pdfs`),
  reloadStartup: () => api.post('/admin/startup/reload'),

  addFAQ: (productId, data) => api.post(`/admin/products/${productId}/pre-faq`, data),
  getFAQs: (productId) => api.get(`/admin/products/${productId}/pre-faq`),
  updateFAQ: (productId, faqId, data) => api.put(`/admin/products/${productId}/pre-faq/${faqId}`, data),
  deleteFAQ: (productId, faqId) => api.delete(`/admin/products/${productId}/pre-faq/${faqId}`),

  getAuditLogs: (limit = 100) => api.get(`/admin/audit?limit=${limit}`),

  listUsers: () => api.get('/admin/users'),
  updateUserRole: (userId, role) => api.put(`/admin/users/${userId}/role`, { role }),

  getCacheStats: () => api.get('/admin/cache/stats'),
  clearSemanticCache: () => api.delete('/admin/cache/semantic'),
  clearRedisCache: () => api.delete('/admin/cache/redis'),
  clearKnowledgeBase: () => api.delete('/admin/knowledge-base/clear')
};

export default api;
