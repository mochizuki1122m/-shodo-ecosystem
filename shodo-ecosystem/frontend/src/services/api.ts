import axios from 'axios';

const API_BASE_URL = (process.env.REACT_APP_API_URL || 'http://localhost');

// Axiosインスタンスの作成
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

function getCookie(name: string): string | null {
  const match = document.cookie.split(';').map(c => c.trim()).find(c => c.startsWith(name + '='));
  return match ? decodeURIComponent(match.split('=')[1]) : null;
}

// リクエストインターセプター（認証トークン/CSRFトークンの追加）
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    const csrfCookieName = (process.env.REACT_APP_CSRF_COOKIE_NAME || 'csrf_token');
    const csrfHeaderName = (process.env.REACT_APP_CSRF_HEADER_NAME || 'X-CSRF-Token');
    const csrfToken = getCookie(csrfCookieName);
    if (csrfToken) {
      (config.headers as any)[csrfHeaderName] = csrfToken;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// レスポンスインターセプター（エラーハンドリング）
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // 認証エラーの場合はログイン画面へリダイレクト
      localStorage.removeItem('access_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// CSRF API
export const fetchCsrf = async () => {
  const response = await apiClient.get('/api/v1/auth/csrf');
  return response.data.data || response.data;
};

// NLP API
export const analyzeText = async (text: string) => {
  const response = await apiClient.post('/api/v1/nlp/analyze', { text });
  // BaseResponseのdataフィールドを取得
  return response.data.data || response.data;
};

export const refineAnalysis = async (current_result: any, refinement: string) => {
  const response = await apiClient.post('/api/v1/nlp/refine', { current_result, refinement });
  // BaseResponseのdataフィールドを取得
  return response.data.data || response.data;
};

// Preview API
export const generatePreview = async (changes: any[], context: any, service_id: string) => {
  if (!service_id) {
    throw new Error('service_id is required for preview generation');
  }
  const response = await apiClient.post('/api/v1/preview/generate', { changes, context, service_id });
  // BaseResponseのdataフィールドを取得
  return response.data.data || response.data;
};

export const refinePreview = async (previewId: string, refinement: string) => {
  const response = await apiClient.post(`/api/v1/preview/${previewId}/refine`, { refinement });
  // BaseResponseのdataフィールドを取得
  return response.data.data || response.data;
};

export const applyPreview = async (previewId: string, confirmed: boolean = true) => {
  const response = await apiClient.post(`/api/v1/preview/apply/${previewId}`, { confirmed });
  // BaseResponseのdataフィールドを取得
  return response.data.data || response.data;
};

// Dashboard API
export const getDetectedServices = async () => {
  const response = await apiClient.get('/api/v1/dashboard/services');
  return response.data.data || response.data;
};

export const getServiceStatus = async (serviceId: string) => {
  const response = await apiClient.get(`/api/v1/dashboard/services/${serviceId}/status`);
  return response.data.data || response.data;
};

// Auth API
export const login = async (email: string, password: string) => {
  const response = await apiClient.post('/api/v1/auth/login', { email, password });
  return response.data.data || response.data;
};

export const logout = async () => {
  const response = await apiClient.post('/api/v1/auth/logout');
  return response.data.data || response.data;
};

export const getCurrentUser = async () => {
  const response = await apiClient.get('/api/v1/auth/me');
  return response.data.data || response.data;
};

// MCP API
export const getAvailableTools = async () => {
  const response = await apiClient.get('/api/v1/mcp/tools');
  return response.data.data || response.data;
};

export const invokeTool = async (toolId: string, params: any) => {
  const response = await apiClient.post(`/api/v1/mcp/tools/${toolId}/invoke`, params);
  return response.data.data || response.data;
};

export default apiClient;