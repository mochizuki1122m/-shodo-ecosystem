import axios, { AxiosInstance, AxiosRequestConfig, AxiosError } from 'axios';

// APIレスポンス型
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
  error_code?: string;
  timestamp: string;
  request_id?: string;
}

// ページネーションレスポンス型
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
  has_next: boolean;
  has_prev: boolean;
}

// エラーレスポンス型
export interface ErrorResponse {
  detail: string;
  status_code: number;
  error_code?: string;
}

class ApiClient {
  private client: AxiosInstance;
  private refreshingToken: Promise<string> | null = null;

  constructor() {
    const baseURL = process.env.REACT_APP_API_URL || 'http://localhost/api';
    
    this.client = axios.create({
      baseURL: `${baseURL}/v1`,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // リクエストインターセプター
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('access_token');
        if (token) {
          (config.headers as any).Authorization = `Bearer ${token}`;
        }
        // リクエストIDの追加
        (config.headers as any)['X-Request-ID'] = this.generateRequestId();
        return config;
      },
      (error) => Promise.reject(error)
    );

    // レスポンスインターセプター
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError<ErrorResponse>) => {
        const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

        // 401エラーでトークンリフレッシュ（可能なら）
        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;
          try {
            const newToken = await this.refreshToken();
            if (newToken && originalRequest.headers) {
              (originalRequest.headers as any).Authorization = `Bearer ${newToken}`;
              return this.client(originalRequest);
            }
          } catch (refreshError) {
            // リフレッシュ失敗時はログアウト扱い
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            window.location.href = '/login';
            return Promise.reject(refreshError);
          }
        }

        // エラーメッセージの整形
        const errorMessage = this.extractErrorMessage(error);
        return Promise.reject({
          message: errorMessage,
          status: error.response?.status,
          code: error.response?.data?.error_code,
          original: error,
        });
      }
    );
  }

  private generateRequestId(): string {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  private extractErrorMessage(error: AxiosError<ErrorResponse>): string {
    if (error.response?.data?.detail) return error.response.data.detail;
    if (error.message) return error.message;
    return 'An unexpected error occurred';
  }

  private async refreshToken(): Promise<string> {
    if (this.refreshingToken) {
      return this.refreshingToken;
    }

    this.refreshingToken = new Promise(async (resolve, reject) => {
      try {
        const refreshToken = localStorage.getItem('refresh_token');
        if (!refreshToken) {
          throw new Error('No refresh token available');
        }
        const response = await this.client.post('/auth/refresh', {
          refresh_token: refreshToken,
        });
        const newToken: string | undefined = (response.data?.data?.access_token) || response.data?.access_token;
        const newRefresh: string | undefined = (response.data?.data?.refresh_token) || response.data?.refresh_token;
        if (!newToken) throw new Error('No access token in refresh response');
        localStorage.setItem('access_token', newToken);
        if (newRefresh) {
          localStorage.setItem('refresh_token', newRefresh);
        }
        resolve(newToken);
      } catch (err) {
        reject(err);
      } finally {
        this.refreshingToken = null;
      }
    });

    return this.refreshingToken;
  }

  // === 汎用メソッド ===

  async get<T = any>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    const response = await this.client.get<ApiResponse<T>>(url, config);
    return response.data;
  }

  async post<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    const response = await this.client.post<ApiResponse<T>>(url, data, config);
    return response.data;
  }

  async put<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    const response = await this.client.put<ApiResponse<T>>(url, data, config);
    return response.data;
  }

  async patch<T = any>(url: string, data?: any, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    const response = await this.client.patch<ApiResponse<T>>(url, data, config);
    return response.data;
  }

  async delete<T = any>(url: string, config?: AxiosRequestConfig): Promise<ApiResponse<T>> {
    const response = await this.client.delete<ApiResponse<T>>(url, config);
    return response.data;
  }

  // === ファイルアップロード ===

  async uploadFile(url: string, file: File, onProgress?: (progress: number) => void): Promise<ApiResponse> {
    const formData = new FormData();
    formData.append('file', file);

    return this.post(url, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(progress);
        }
      },
    });
  }

  // === ストリーミング ===

  async *stream<T = any>(url: string, config?: AxiosRequestConfig): AsyncGenerator<T> {
    const response = await this.client.get(url, { ...config, responseType: 'stream' });
    const reader = (response.data as any).getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            yield data;
          } catch {
            // ignore invalid json
          }
        }
      }
    }
  }

  // === バッチリクエスト ===

  async batch<T = any>(requests: Array<{ method: string; url: string; data?: any; }>): Promise<ApiResponse<T[]>> {
    const promises = requests.map((req) => {
      switch (req.method.toLowerCase()) {
        case 'get':
          return this.get(req.url);
        case 'post':
          return this.post(req.url, req.data);
        case 'put':
          return this.put(req.url, req.data);
        case 'patch':
          return this.patch(req.url, req.data);
        case 'delete':
          return this.delete(req.url);
        default:
          throw new Error(`Unsupported method: ${req.method}`);
      }
    });
    const results = await Promise.allSettled(promises);
    const data = results.map((r) => (r.status === 'fulfilled' ? r.value.data : null)).filter(Boolean);
    return { success: true, data: data as T[], timestamp: new Date().toISOString() };
  }

  // === キャンセル可能なリクエスト ===

  createCancelToken() {
    return axios.CancelToken.source();
  }

  isCancel(error: any): boolean {
    return axios.isCancel(error);
  }
}

// シングルトンインスタンス
const apiClient = new ApiClient();
export default apiClient;