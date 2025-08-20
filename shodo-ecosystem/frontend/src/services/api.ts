import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost';

// Axiosインスタンスの作成
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// リクエストインターセプター（認証トークンの追加）
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('authToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// レスポンスインターセプター（エラーハンドリング）
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // 認証エラーの場合はログイン画面へリダイレクト
      localStorage.removeItem('authToken');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// NLP API
export const analyzeText = async (text: string) => {
  const response = await apiClient.post('/api/v1/nlp/analyze', { text });
  return response.data;
};

export const refineAnalysis = async (analysisId: string, refinement: string) => {
  const response = await apiClient.post(`/api/v1/nlp/refine/${analysisId}`, { refinement });
  return response.data;
};

// Preview API
export const generatePreview = async (changes: any[], context: any) => {
  const response = await apiClient.post('/api/v1/preview/generate', { changes, context });
  return response.data;
};

export const refinePreview = async (previewId: string, refinement: string) => {
  const response = await apiClient.post(`/api/v1/preview/refine/${previewId}`, { refinement });
  return response.data;
};

export const applyPreview = async (previewId: string) => {
  const response = await apiClient.post(`/api/v1/preview/apply/${previewId}`);
  return response.data;
};

// Dashboard API
export const getDetectedServices = async () => {
  const response = await apiClient.get('/api/v1/dashboard/services');
  return response.data;
};

export const getServiceStatus = async (serviceId: string) => {
  const response = await apiClient.get(`/api/v1/dashboard/services/${serviceId}/status`);
  return response.data;
};

// Auth API
export const login = async (email: string, password: string) => {
  const response = await apiClient.post('/api/v1/auth/login', { email, password });
  return response.data;
};

export const logout = async () => {
  const response = await apiClient.post('/api/v1/auth/logout');
  return response.data;
};

export const getCurrentUser = async () => {
  const response = await apiClient.get('/api/v1/auth/me');
  return response.data;
};

// MCP API
export const getAvailableTools = async () => {
  const response = await apiClient.get('/api/v1/mcp/tools');
  return response.data;
};

export const invokeTool = async (toolId: string, params: any) => {
  const response = await apiClient.post(`/api/v1/mcp/tools/${toolId}/invoke`, params);
  return response.data;
};

export default apiClient;