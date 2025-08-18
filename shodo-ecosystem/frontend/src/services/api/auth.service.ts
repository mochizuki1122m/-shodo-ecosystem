import apiClient, { ApiResponse } from '../apiClient';

// 型定義
export interface LoginRequest {
  email: string;
  password: string;
  remember_me?: boolean;
}

export interface LoginResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_in: number;
  user: UserInfo;
}

export interface RegisterRequest {
  email: string;
  password: string;
  confirm_password: string;
  username: string;
  full_name?: string;
}

export interface UserInfo {
  user_id: string;
  email: string;
  username: string;
  full_name?: string;
  roles: string[];
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
  last_login?: string;
}

export interface PasswordResetRequest {
  email: string;
}

export interface PasswordResetConfirm {
  token: string;
  new_password: string;
  confirm_password: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
  confirm_password: string;
}

class AuthService {
  /**
   * ログイン
   */
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const response = await apiClient.post<LoginResponse>('/auth/login', credentials);
    
    if (response.success && response.data) {
      // トークンをローカルストレージに保存
      localStorage.setItem('access_token', response.data.access_token);
      if (response.data.refresh_token) {
        localStorage.setItem('refresh_token', response.data.refresh_token);
      }
      
      return response.data;
    }
    
    throw new Error(response.error || 'Login failed');
  }

  /**
   * ログアウト
   */
  async logout(): Promise<void> {
    try {
      await apiClient.post('/auth/logout');
    } finally {
      // ローカルストレージをクリア
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      
      // ホームページにリダイレクト
      window.location.href = '/';
    }
  }

  /**
   * ユーザー登録
   */
  async register(data: RegisterRequest): Promise<UserInfo> {
    const response = await apiClient.post<UserInfo>('/auth/register', data);
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Registration failed');
  }

  /**
   * 現在のユーザー情報取得
   */
  async getCurrentUser(): Promise<UserInfo> {
    const response = await apiClient.get<UserInfo>('/auth/me');
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Failed to get user info');
  }

  /**
   * ユーザー情報更新
   */
  async updateProfile(data: Partial<UserInfo>): Promise<UserInfo> {
    const response = await apiClient.patch<UserInfo>('/auth/me', data);
    
    if (response.success && response.data) {
      return response.data;
    }
    
    throw new Error(response.error || 'Failed to update profile');
  }

  /**
   * パスワードリセットリクエスト
   */
  async requestPasswordReset(data: PasswordResetRequest): Promise<void> {
    const response = await apiClient.post('/auth/password-reset', data);
    
    if (!response.success) {
      throw new Error(response.error || 'Failed to request password reset');
    }
  }

  /**
   * パスワードリセット確認
   */
  async confirmPasswordReset(data: PasswordResetConfirm): Promise<void> {
    const response = await apiClient.post('/auth/password-reset/confirm', data);
    
    if (!response.success) {
      throw new Error(response.error || 'Failed to reset password');
    }
  }

  /**
   * パスワード変更
   */
  async changePassword(data: ChangePasswordRequest): Promise<void> {
    const response = await apiClient.post('/auth/change-password', data);
    
    if (!response.success) {
      throw new Error(response.error || 'Failed to change password');
    }
  }

  /**
   * トークンリフレッシュ
   */
  async refreshToken(refreshToken: string): Promise<LoginResponse> {
    const response = await apiClient.post<LoginResponse>('/auth/refresh', {
      refresh_token: refreshToken
    });
    
    if (response.success && response.data) {
      // 新しいトークンを保存
      localStorage.setItem('access_token', response.data.access_token);
      if (response.data.refresh_token) {
        localStorage.setItem('refresh_token', response.data.refresh_token);
      }
      
      return response.data;
    }
    
    throw new Error(response.error || 'Failed to refresh token');
  }

  /**
   * メール確認
   */
  async verifyEmail(token: string): Promise<void> {
    const response = await apiClient.post('/auth/verify-email', { token });
    
    if (!response.success) {
      throw new Error(response.error || 'Failed to verify email');
    }
  }

  /**
   * メール確認再送信
   */
  async resendVerificationEmail(): Promise<void> {
    const response = await apiClient.post('/auth/resend-verification');
    
    if (!response.success) {
      throw new Error(response.error || 'Failed to resend verification email');
    }
  }

  /**
   * トークンの有効性チェック
   */
  isAuthenticated(): boolean {
    const token = localStorage.getItem('access_token');
    if (!token) return false;
    
    try {
      // JWTのペイロードをデコード（簡易チェック）
      const payload = JSON.parse(atob(token.split('.')[1]));
      const exp = payload.exp * 1000; // Convert to milliseconds
      
      return Date.now() < exp;
    } catch {
      return false;
    }
  }

  /**
   * 現在のトークン取得
   */
  getAccessToken(): string | null {
    return localStorage.getItem('access_token');
  }

  /**
   * リフレッシュトークン取得
   */
  getRefreshToken(): string | null {
    return localStorage.getItem('refresh_token');
  }
}

const authService = new AuthService();
export default authService;