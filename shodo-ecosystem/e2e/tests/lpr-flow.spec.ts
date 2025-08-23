import { test, expect } from '@playwright/test';

/**
 * LPR主要フロー E2E テスト
 * 可視ログイン → トークン発行 → 検証 → 失効
 */

test.describe('LPR main flow', () => {
  test('visible login -> issue -> verify -> revoke', async ({ page, request, context }) => {
    // 1) 認証: Cookieベース
    await page.goto('/login');
    await page.fill('[data-testid="email-input"]', 'user@example.com');
    await page.fill('[data-testid="password-input"]', 'password');
    await page.click('[data-testid="login-button"]');
    await page.waitForURL('/dashboard');

    // CSRF トークン取得
    const cookies = await context.cookies();
    const csrf = cookies.find(c => c.name === 'csrf_token');

    // 2) 可視ログイン開始
    const visibleLoginResp = await request.post('/api/v1/lpr/visible-login', {
      data: {
        service_name: 'shopify',
        login_url: 'https://example.com/login',
        auto_fill: { username: 'demo', password: 'demo' },
        timeout: 60
      },
      headers: csrf ? { 'X-CSRF-Token': csrf.value } : {}
    });
    expect(visibleLoginResp.ok()).toBeTruthy();
    const visibleLogin = await visibleLoginResp.json();
    expect(visibleLogin.success).toBeTruthy();
    expect(visibleLogin.session_id).toBeTruthy();

    // 3) LPR発行
    const issueResp = await request.post('/api/v1/lpr/issue', {
      data: {
        session_id: visibleLogin.session_id,
        scopes: [
          { method: 'GET', url_pattern: '/api/v1/shopify/orders' },
          { method: 'POST', url_pattern: '/api/v1/shopify/export' }
        ],
        origins: ['http://localhost:3000'],
        ttl_seconds: 3600,
        device_fingerprint: { browser: 'playwright', os: 'linux' },
        purpose: 'e2e_test',
        consent: true
      },
      headers: csrf ? { 'X-CSRF-Token': csrf.value } : {}
    });
    expect(issueResp.ok()).toBeTruthy();
    const issue = await issueResp.json();
    expect(issue.success || issue.token).toBeTruthy();
    const token = issue.token || (issue.data && issue.data.token);
    const jti = issue.jti || (issue.data && issue.data.jti);
    expect(token).toBeTruthy();

    // 4) LPR検証
    const verifyResp = await request.post('/api/v1/lpr/verify', {
      data: {
        token,
        request_method: 'GET',
        request_url: '/api/v1/shopify/orders',
        request_origin: 'http://localhost:3000',
        device_fingerprint: { browser: 'playwright' }
      },
      headers: csrf ? { 'X-CSRF-Token': csrf.value } : {}
    });
    expect(verifyResp.ok()).toBeTruthy();
    const verify = await verifyResp.json();
    expect(verify.data.valid).toBe(true);

    // 5) LPR失効
    const revokeResp = await request.post('/api/v1/lpr/revoke', {
      data: { jti: jti || verify.data.jti, reason: 'e2e_complete' },
      headers: csrf ? { 'X-CSRF-Token': csrf.value } : {}
    });
    expect(revokeResp.ok()).toBeTruthy();
  });
});