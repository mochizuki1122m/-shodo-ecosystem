/**
 * E2E Critical Path Tests
 * MUST: All critical user journeys must pass
 */

import { test, expect } from '@playwright/test';
import { generateDeviceFingerprint, generateLPRToken } from './helpers/auth';

test.describe('Critical User Journey', () => {
  test.beforeEach(async ({ page }) => {
    // Set up test environment
    await page.goto(process.env.BASE_URL || 'http://localhost:3000');
  });

  test('Complete authentication flow', async ({ page }) => {
    // Navigate to login
    await page.goto('/login');
    
    // Fill login form
    await page.fill('[data-testid="email-input"]', 'test@example.com');
    await page.fill('[data-testid="password-input"]', 'Test123!@#');
    
    // Submit
    await page.click('[data-testid="login-button"]');
    
    // Wait for redirect
    await page.waitForURL('/dashboard');
    
    // Verify authentication via cookie
    const cookies = await page.context().cookies();
    const accessCookie = cookies.find(c => c.name === 'access_token');
    expect(accessCookie).toBeTruthy();
    expect(accessCookie?.httpOnly).toBeTruthy();
    
    // Verify user info is displayed
    await expect(page.locator('[data-testid="user-menu"]')).toBeVisible();
  });

  test('NLP analysis flow', async ({ page, context }) => {
    // Authenticate first
    await context.addCookies([{
      name: 'access_token',
      value: 'test-token',
      domain: 'localhost',
      path: '/'
    }]);
    
    await page.goto('/nlp');
    
    // Enter Japanese text
    const testInput = 'Shopifyの今月の売上を確認して';
    await page.fill('[data-testid="nlp-input"]', testInput);
    
    // Submit for analysis
    await page.click('[data-testid="analyze-button"]');
    
    // Wait for results
    await page.waitForSelector('[data-testid="analysis-result"]');
    
    // Verify analysis results
    const intent = await page.textContent('[data-testid="intent"]');
    expect(intent).toBe('view_orders');
    
    const confidence = await page.textContent('[data-testid="confidence"]');
    expect(parseFloat(confidence)).toBeGreaterThan(0.7);
    
    const service = await page.textContent('[data-testid="service"]');
    expect(service).toBe('shopify');
  });

  test('Preview generation and refinement', async ({ page, context }) => {
    // Authenticate
    await context.addCookies([{
      name: 'access_token',
      value: 'test-token',
      domain: 'localhost',
      path: '/'
    }]);
    
    await page.goto('/preview');
    
    // Generate initial preview
    await page.click('[data-testid="generate-preview"]');
    
    // Wait for preview
    await page.waitForSelector('[data-testid="preview-frame"]');
    
    // Verify preview content
    const previewContent = await page.frameLocator('[data-testid="preview-frame"]').locator('body').innerHTML();
    expect(previewContent).toContain('サンプルタイトル');
    
    // Refine preview
    await page.fill('[data-testid="refinement-input"]', '価格を500円に変更');
    await page.click('[data-testid="refine-button"]');
    
    // Wait for refinement
    await page.waitForTimeout(1000);
    
    // Verify refinement applied
    const refinedContent = await page.frameLocator('[data-testid="preview-frame"]').locator('.price').textContent();
    expect(refinedContent).toContain('500');
    
    // Test undo
    await page.click('[data-testid="undo-button"]');
    await page.waitForTimeout(500);
    
    // Verify undo worked
    const undoneContent = await page.frameLocator('[data-testid="preview-frame"]').locator('.price').textContent();
    expect(undoneContent).not.toContain('500');
  });

  test('LPR token issuance and verification', async ({ page, request, context }) => {
    // Authenticate
    await context.addCookies([{
      name: 'access_token',
      value: 'test-token',
      domain: 'localhost',
      path: '/'
    }]);
    
    // Generate device fingerprint
    const fingerprint = await generateDeviceFingerprint(page);
    
    // Request LPR token
    const issueResponse = await request.post('/api/v1/lpr/issue', {
      data: {
        service: 'shopify',
        purpose: 'data_export',
        scopes: [
          { method: 'GET', url_pattern: '/api/v1/shopify/orders' },
          { method: 'POST', url_pattern: '/api/v1/shopify/export' }
        ],
        device_fingerprint: fingerprint,
        consent: true
      }
    });
    
    expect(issueResponse.ok()).toBeTruthy();
    const { token, jti } = await issueResponse.json();
    expect(token).toBeTruthy();
    expect(jti).toBeTruthy();
    
    // Verify token
    const verifyResponse = await request.post('/api/v1/lpr/verify', {
      data: {
        token: token,
        device_fingerprint: fingerprint
      }
    });
    
    expect(verifyResponse.ok()).toBeTruthy();
    const verification = await verifyResponse.json();
    expect(verification.data.valid).toBe(true);
    expect(verification.data.jti).toBe(jti);
    
    // Use token for protected operation
    const protectedResponse = await request.get('/api/v1/mcp/shopify/orders', {
      headers: {
        'Authorization': `Bearer LPR-${token}`,
        'X-Device-Fingerprint': fingerprint
      }
    });
    
    expect(protectedResponse.ok()).toBeTruthy();
    
    // Revoke token
    const revokeResponse = await request.post('/api/v1/lpr/revoke', {
      data: {
        jti: jti,
        reason: 'test_complete'
      }
    });
    
    expect(revokeResponse.ok()).toBeTruthy();
    
    // Verify token is revoked
    const verifyRevokedResponse = await request.post('/api/v1/lpr/verify', {
      data: {
        token: token,
        device_fingerprint: fingerprint
      }
    });
    
    const revokedVerification = await verifyRevokedResponse.json();
    expect(revokedVerification.data.valid).toBe(false);
  });

  test('End-to-end data export flow', async ({ page, context }) => {
    // Full user journey: Login -> NLP -> Preview -> LPR -> Export
    
    // 1. Login
    await page.goto('/login');
    await page.fill('[data-testid="email-input"]', 'test@example.com');
    await page.fill('[data-testid="password-input"]', 'Test123!@#');
    await page.click('[data-testid="login-button"]');
    await page.waitForURL('/dashboard');
    
    // 2. Navigate to NLP
    await page.click('[data-testid="nav-nlp"]');
    
    // 3. Request data export via NLP
    await page.fill('[data-testid="nlp-input"]', 'Shopifyの先月の注文データをCSVでエクスポートして');
    await page.click('[data-testid="analyze-button"]');
    await page.waitForSelector('[data-testid="analysis-result"]');
    
    // 4. Confirm action
    await page.click('[data-testid="confirm-action"]');
    
    // 5. LPR consent screen
    await page.waitForSelector('[data-testid="lpr-consent"]');
    await page.check('[data-testid="consent-checkbox"]');
    await page.click('[data-testid="grant-access"]');
    
    // 6. Wait for export to complete
    await page.waitForSelector('[data-testid="export-complete"]', { timeout: 30000 });
    
    // 7. Download file
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.click('[data-testid="download-button"]')
    ]);
    
    // Verify download
    expect(download.suggestedFilename()).toContain('orders');
    expect(download.suggestedFilename()).toContain('.csv');
  });

  test('Health check endpoints', async ({ request }) => {
    // Main health check
    const healthResponse = await request.get('/health');
    expect(healthResponse.ok()).toBeTruthy();
    const health = await healthResponse.json();
    expect(health.data.status).toBe('healthy');
    
    // Component health checks
    const components = health.data.components;
    expect(components.database.status).toBe('healthy');
    expect(components.redis.status).toBe('healthy');
    expect(components.ai_server.status).toBe('healthy');
    
    // Kubernetes probes
    const liveResponse = await request.get('/health/live');
    expect(liveResponse.ok()).toBeTruthy();
    
    const readyResponse = await request.get('/health/ready');
    expect(readyResponse.ok()).toBeTruthy();
    
    // Metrics endpoint
    const metricsResponse = await request.get('/metrics');
    expect(metricsResponse.ok()).toBeTruthy();
    const metrics = await metricsResponse.text();
    expect(metrics).toContain('http_requests_total');
    expect(metrics).toContain('lpr_tokens_issued_total');
  });

  test('Security headers validation', async ({ request }) => {
    const response = await request.get('/');
    
    // Verify security headers
    expect(response.headers()['x-content-type-options']).toBe('nosniff');
    expect(response.headers()['x-frame-options']).toBe('DENY');
    expect(response.headers()['x-xss-protection']).toBe('1; mode=block');
    expect(response.headers()['strict-transport-security']).toContain('max-age=');
    expect(response.headers()['content-security-policy']).toBeTruthy();
    expect(response.headers()['x-correlation-id']).toBeTruthy();
  });

  test('Rate limiting enforcement', async ({ request }) => {
    // Make multiple rapid requests
    const promises = [];
    for (let i = 0; i < 150; i++) {
      promises.push(request.get('/api/v1/nlp/analyze'));
    }
    
    const responses = await Promise.all(promises);
    
    // Some requests should be rate limited
    const rateLimited = responses.filter(r => r.status() === 429);
    expect(rateLimited.length).toBeGreaterThan(0);
    
    // Check rate limit headers
    const limitedResponse = rateLimited[0];
    expect(limitedResponse.headers()['x-ratelimit-limit']).toBeTruthy();
    expect(limitedResponse.headers()['x-ratelimit-remaining']).toBeTruthy();
    expect(limitedResponse.headers()['x-ratelimit-reset']).toBeTruthy();
  });
});

test.describe('Error Handling', () => {
  test('Handles network errors gracefully', async ({ page, context }) => {
    // Simulate offline
    await context.setOffline(true);
    
    await page.goto('/nlp');
    await page.fill('[data-testid="nlp-input"]', 'test');
    await page.click('[data-testid="analyze-button"]');
    
    // Should show error message
    await expect(page.locator('[data-testid="error-message"]')).toBeVisible();
    await expect(page.locator('[data-testid="error-message"]')).toContainText('ネットワークエラー');
    
    // Restore connection
    await context.setOffline(false);
    
    // Retry should work
    await page.click('[data-testid="retry-button"]');
    await page.waitForSelector('[data-testid="analysis-result"]');
  });

  test('Handles API errors with correlation ID', async ({ page, request }) => {
    // Make a bad request
    const response = await request.post('/api/v1/nlp/analyze', {
      data: { invalid: 'data' }
    });
    
    expect(response.status()).toBe(400);
    const error = await response.json();
    
    // Should have correlation ID for tracking
    expect(error.correlation_id).toBeTruthy();
    expect(error.error.code).toBe('VALIDATION_ERROR');
  });
});