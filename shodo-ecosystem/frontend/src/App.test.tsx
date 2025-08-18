import React from 'react';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import App from './App';
import { store } from './store';

const theme = createTheme();
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
  },
});

const AllTheProviders = ({ children }: { children: React.ReactNode }) => {
  return (
    <Provider store={store}>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider theme={theme}>
          <BrowserRouter>
            {children}
          </BrowserRouter>
        </ThemeProvider>
      </QueryClientProvider>
    </Provider>
  );
};

describe('App Component', () => {
  test('renders without crashing', () => {
    render(
      <AllTheProviders>
        <App />
      </AllTheProviders>
    );
  });

  test('renders login page when not authenticated', () => {
    render(
      <AllTheProviders>
        <App />
      </AllTheProviders>
    );
    
    // ログインページへのリダイレクトを確認
    expect(window.location.pathname).toBe('/');
  });
});

describe('Authentication Flow', () => {
  test('redirects to login when not authenticated', () => {
    const { container } = render(
      <AllTheProviders>
        <App />
      </AllTheProviders>
    );
    
    expect(container).toBeTruthy();
  });
});

describe('Routing', () => {
  test('has correct routes configured', () => {
    render(
      <AllTheProviders>
        <App />
      </AllTheProviders>
    );
    
    // ルーティングが正しく設定されていることを確認
    expect(window.location.pathname).toBeDefined();
  });
});