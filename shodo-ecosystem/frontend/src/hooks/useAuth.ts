import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useDispatch } from 'react-redux';
import authService, {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  UserInfo,
  ChangePasswordRequest,
  PasswordResetRequest,
  PasswordResetConfirm
} from '../services/api/auth.service';

// クエリキー
const QUERY_KEYS = {
  currentUser: ['auth', 'currentUser'],
  isAuthenticated: ['auth', 'isAuthenticated'],
};

/**
 * 現在のユーザー情報を取得するフック
 */
export function useCurrentUser() {
  return useQuery<UserInfo, Error>({
    queryKey: QUERY_KEYS.currentUser,
    queryFn: () => authService.getCurrentUser(),
    enabled: authService.isAuthenticated(),
    staleTime: 5 * 60 * 1000, // 5分
    retry: 1,
  });
}

/**
 * ログインフック
 */
export function useLogin() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const dispatch = useDispatch();

  return useMutation<LoginResponse, Error, LoginRequest>({
    mutationFn: (credentials) => authService.login(credentials),
    onSuccess: (data) => {
      // ユーザー情報をキャッシュに設定
      queryClient.setQueryData(QUERY_KEYS.currentUser, data.user);
      
      // Reduxストアを更新
      dispatch({
        type: 'auth/loginSuccess',
        payload: {
          user: data.user,
          token: data.access_token,
          refreshToken: data.refresh_token,
        },
      });
      
      // ダッシュボードにリダイレクト
      navigate('/dashboard');
    },
    onError: (error) => {
      console.error('Login failed:', error);
    },
  });
}

/**
 * ログアウトフック
 */
export function useLogout() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const dispatch = useDispatch();

  return useMutation<void, Error>({
    mutationFn: () => authService.logout(),
    onSuccess: () => {
      // キャッシュをクリア
      queryClient.clear();
      
      // Reduxストアをクリア
      dispatch({ type: 'auth/logout' });
      
      // ログインページにリダイレクト
      navigate('/login');
    },
  });
}

/**
 * ユーザー登録フック
 */
export function useRegister() {
  const navigate = useNavigate();

  return useMutation<UserInfo, Error, RegisterRequest>({
    mutationFn: (data) => authService.register(data),
    onSuccess: () => {
      // 登録成功後、ログインページにリダイレクト
      navigate('/login', {
        state: { message: 'Registration successful. Please login.' }
      });
    },
  });
}

/**
 * プロフィール更新フック
 */
export function useUpdateProfile() {
  const queryClient = useQueryClient();

  return useMutation<UserInfo, Error, Partial<UserInfo>>({
    mutationFn: (data) => authService.updateProfile(data),
    onSuccess: (data) => {
      // キャッシュを更新
      queryClient.setQueryData(QUERY_KEYS.currentUser, data);
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.currentUser });
    },
  });
}

/**
 * パスワード変更フック
 */
export function useChangePassword() {
  return useMutation<void, Error, ChangePasswordRequest>({
    mutationFn: (data) => authService.changePassword(data),
    onSuccess: () => {
      // 成功メッセージを表示
      console.log('Password changed successfully');
    },
  });
}

/**
 * パスワードリセットリクエストフック
 */
export function useRequestPasswordReset() {
  return useMutation<void, Error, PasswordResetRequest>({
    mutationFn: (data) => authService.requestPasswordReset(data),
    onSuccess: () => {
      // 成功メッセージを表示
      console.log('Password reset email sent');
    },
  });
}

/**
 * パスワードリセット確認フック
 */
export function useConfirmPasswordReset() {
  const navigate = useNavigate();

  return useMutation<void, Error, PasswordResetConfirm>({
    mutationFn: (data) => authService.confirmPasswordReset(data),
    onSuccess: () => {
      // ログインページにリダイレクト
      navigate('/login', {
        state: { message: 'Password reset successful. Please login with your new password.' }
      });
    },
  });
}

/**
 * メール確認フック
 */
export function useVerifyEmail() {
  return useMutation<void, Error, string>({
    mutationFn: (token) => authService.verifyEmail(token),
    onSuccess: () => {
      console.log('Email verified successfully');
    },
  });
}

/**
 * メール確認再送信フック
 */
export function useResendVerificationEmail() {
  return useMutation<void, Error>({
    mutationFn: () => authService.resendVerificationEmail(),
    onSuccess: () => {
      console.log('Verification email resent');
    },
  });
}

/**
 * 認証状態チェックフック
 */
export function useIsAuthenticated() {
  return useQuery<boolean>({
    queryKey: QUERY_KEYS.isAuthenticated,
    queryFn: () => Promise.resolve(authService.isAuthenticated()),
    staleTime: 60 * 1000, // 1分
  });
}

/**
 * トークンリフレッシュフック
 */
export function useRefreshToken() {
  const queryClient = useQueryClient();
  const dispatch = useDispatch();

  return useMutation<LoginResponse, Error, string>({
    mutationFn: (refreshToken) => authService.refreshToken(refreshToken),
    onSuccess: (data) => {
      // ユーザー情報を更新
      queryClient.setQueryData(QUERY_KEYS.currentUser, data.user);
      
      // Reduxストアを更新
      dispatch({
        type: 'auth/tokenRefreshed',
        payload: {
          token: data.access_token,
          refreshToken: data.refresh_token,
        },
      });
    },
  });
}