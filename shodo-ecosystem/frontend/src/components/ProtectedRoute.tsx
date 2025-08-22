import React from 'react';
import { Navigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { RootState } from '../store';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated } = useSelector((state: RootState) => state.auth);
  const token = localStorage.getItem('access_token');

  // 明示的フラグでバイパス（開発時のみに使用）
  const disableAuthGuard = (process.env.REACT_APP_DISABLE_AUTH_GUARD || 'false') === 'true';
  if (disableAuthGuard) {
    return <>{children}</>;
  }

  if (!isAuthenticated && !token) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

export default ProtectedRoute;