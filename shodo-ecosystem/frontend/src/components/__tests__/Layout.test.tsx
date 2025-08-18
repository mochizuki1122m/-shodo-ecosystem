import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router-dom';
import { configureStore } from '@reduxjs/toolkit';
import Layout from '../Layout';
import authSlice from '../../store/authSlice';
import uiSlice from '../../store/uiSlice';

// モックストアの作成
const createMockStore = (initialState = {}) => {
  return configureStore({
    reducer: {
      auth: authSlice,
      ui: uiSlice,
    },
    preloadedState: initialState,
  });
};

// テストユーティリティ
const renderWithProviders = (component: React.ReactElement, initialState = {}) => {
  const store = createMockStore(initialState);
  return render(
    <Provider store={store}>
      <BrowserRouter>
        {component}
      </BrowserRouter>
    </Provider>
  );
};

describe('Layout Component', () => {
  const mockUser = {
    user_id: 'test-user',
    username: 'testuser',
    email: 'test@example.com',
    roles: ['user'],
  };

  it('renders without crashing', () => {
    renderWithProviders(<Layout />);
    expect(screen.getByRole('banner')).toBeInTheDocument();
  });

  it('displays user information when logged in', () => {
    renderWithProviders(<Layout />, {
      auth: {
        isAuthenticated: true,
        user: mockUser,
        token: 'test-token',
      },
    });

    expect(screen.getByText(mockUser.username)).toBeInTheDocument();
  });

  it('shows login button when not authenticated', () => {
    renderWithProviders(<Layout />, {
      auth: {
        isAuthenticated: false,
        user: null,
        token: null,
      },
    });

    expect(screen.getByText(/ログイン/i)).toBeInTheDocument();
  });

  it('toggles sidebar on menu button click', () => {
    renderWithProviders(<Layout />);
    
    const menuButton = screen.getByLabelText(/menu/i);
    const sidebar = screen.getByRole('navigation');
    
    // 初期状態を確認
    expect(sidebar).toHaveStyle({ width: '240px' });
    
    // メニューボタンをクリック
    fireEvent.click(menuButton);
    
    // サイドバーが閉じることを確認
    expect(sidebar).toHaveStyle({ width: '0px' });
  });

  it('navigates to different routes', () => {
    renderWithProviders(<Layout />, {
      auth: {
        isAuthenticated: true,
        user: mockUser,
        token: 'test-token',
      },
    });

    const dashboardLink = screen.getByText(/ダッシュボード/i);
    fireEvent.click(dashboardLink);
    
    expect(window.location.pathname).toBe('/dashboard');
  });

  it('displays notification badge when there are notifications', () => {
    renderWithProviders(<Layout />, {
      ui: {
        notifications: [
          { id: '1', message: 'Test notification', type: 'info' },
        ],
      },
    });

    const badge = screen.getByTestId('notification-badge');
    expect(badge).toHaveTextContent('1');
  });

  it('opens user menu on avatar click', () => {
    renderWithProviders(<Layout />, {
      auth: {
        isAuthenticated: true,
        user: mockUser,
        token: 'test-token',
      },
    });

    const avatar = screen.getByTestId('user-avatar');
    fireEvent.click(avatar);
    
    expect(screen.getByText(/プロフィール/i)).toBeInTheDocument();
    expect(screen.getByText(/設定/i)).toBeInTheDocument();
    expect(screen.getByText(/ログアウト/i)).toBeInTheDocument();
  });

  it('handles logout correctly', () => {
    const store = createMockStore({
      auth: {
        isAuthenticated: true,
        user: mockUser,
        token: 'test-token',
      },
    });

    render(
      <Provider store={store}>
        <BrowserRouter>
          <Layout />
        </BrowserRouter>
      </Provider>
    );

    const avatar = screen.getByTestId('user-avatar');
    fireEvent.click(avatar);
    
    const logoutButton = screen.getByText(/ログアウト/i);
    fireEvent.click(logoutButton);
    
    // ストアの状態を確認
    const state = store.getState();
    expect(state.auth.isAuthenticated).toBe(false);
    expect(state.auth.user).toBeNull();
  });

  it('applies dark theme when enabled', () => {
    renderWithProviders(<Layout />, {
      ui: {
        theme: 'dark',
      },
    });

    const root = document.documentElement;
    expect(root).toHaveClass('dark-theme');
  });

  it('shows loading spinner when loading', () => {
    renderWithProviders(<Layout />, {
      ui: {
        isLoading: true,
      },
    });

    expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
  });
});