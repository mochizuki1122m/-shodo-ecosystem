import React from 'react';
import { Navigate } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { RootState } from '../store';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

function hasCookie(name: string): boolean {
  return document.cookie.split(';').some(c => c.trim().startsWith(name + '='));
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated } = useSelector((state: RootState) => state.auth);
  const hasAccessCookie = hasCookie('access_token');

  // 明示的フラグでバイパス（開発時のみに使用）
  const disableAuthGuard = (process.env.REACT_APP_DISABLE_AUTH_GUARD || 'false') === 'true';
  if (disableAuthGuard) {
    return <>{children}</>;
  }

  if (!isAuthenticated && !hasAccessCookie) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
};

export default ProtectedRoute;