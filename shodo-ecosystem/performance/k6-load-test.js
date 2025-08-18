/**
 * K6 Load Testing Script
 * MUST: Verify system meets SLO requirements under load
 * Target: 100 RPS sustained, 99.95% availability, P95 < 300ms
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';
import { randomItem } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

// Custom metrics
const errorRate = new Rate('errors');
const nlpLatency = new Trend('nlp_latency');
const previewLatency = new Trend('preview_latency');
const lprLatency = new Trend('lpr_latency');

// Test configuration
export const options = {
  scenarios: {
    // Smoke test
    smoke: {
      executor: 'constant-vus',
      vus: 1,
      duration: '1m',
      tags: { test_type: 'smoke' },
    },
    
    // Load test - gradual ramp up to target load
    load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 10 },   // Warm up
        { duration: '5m', target: 50 },   // Ramp up to 50 users
        { duration: '10m', target: 100 }, // Ramp up to 100 users
        { duration: '20m', target: 100 }, // Stay at 100 users
        { duration: '5m', target: 0 },    // Ramp down
      ],
      gracefulRampDown: '30s',
      tags: { test_type: 'load' },
    },
    
    // Stress test - push beyond normal capacity
    stress: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 50 },
        { duration: '5m', target: 100 },
        { duration: '2m', target: 200 },  // Beyond normal capacity
        { duration: '5m', target: 200 },
        { duration: '2m', target: 300 },  // Extreme load
        { duration: '5m', target: 300 },
        { duration: '10m', target: 0 },
      ],
      tags: { test_type: 'stress' },
    },
    
    // Spike test - sudden traffic surge
    spike: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '10s', target: 100 },
        { duration: '1m', target: 100 },
        { duration: '10s', target: 500 }, // Sudden spike
        { duration: '3m', target: 500 },
        { duration: '10s', target: 100 },
        { duration: '3m', target: 100 },
        { duration: '10s', target: 0 },
      ],
      tags: { test_type: 'spike' },
    },
    
    // Soak test - sustained load for extended period
    soak: {
      executor: 'constant-vus',
      vus: 100,
      duration: '2h',
      tags: { test_type: 'soak' },
    },
  },
  
  thresholds: {
    // SLO requirements
    http_req_duration: ['p(95)<300', 'p(99)<600'], // API latency
    http_req_failed: ['rate<0.001'],               // Error rate < 0.1%
    errors: ['rate<0.001'],                        // Custom error rate
    nlp_latency: ['p(95)<1500'],                   // NLP specific
    preview_latency: ['p(95)<500'],                // Preview specific
    lpr_latency: ['p(95)<200'],                    // LPR specific
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || '';

// Test data
const NLP_INPUTS = [
  'Shopifyの今月の売上を確認して',
  'Gmailで未読メールを表示',
  'Stripeの決済状況を見せて',
  '商品の在庫を更新して',
  '顧客リストをエクスポート',
  '先月の注文データをCSV形式でダウンロード',
  '価格を1000円に変更',
  'メールを送信して',
];

const PREVIEW_CHANGES = [
  { type: 'style', target: '.title', property: 'font-size', new_value: '24px' },
  { type: 'content', target: '.price', property: 'text', new_value: '¥2000' },
  { type: 'style', target: '.button', property: 'background-color', new_value: '#ff0000' },
];

// Helper functions
function getAuthHeaders() {
  return {
    'Authorization': `Bearer ${AUTH_TOKEN}`,
    'Content-Type': 'application/json',
    'X-Correlation-ID': `k6-${__VU}-${__ITER}`,
  };
}

function generateDeviceFingerprint() {
  return {
    user_agent: 'K6/LoadTest',
    accept_language: 'ja-JP',
    screen_resolution: '1920x1080',
    timezone: 'Asia/Tokyo',
  };
}

// Test scenarios
export function testHealthCheck() {
  const response = http.get(`${BASE_URL}/health`);
  
  check(response, {
    'health check status is 200': (r) => r.status === 200,
    'health check returns healthy': (r) => {
      const body = JSON.parse(r.body);
      return body.data && body.data.status === 'healthy';
    },
  });
}

export function testNLPAnalysis() {
  const payload = {
    text: randomItem(NLP_INPUTS),
    mode: 'dual_path',
  };
  
  const params = {
    headers: getAuthHeaders(),
    tags: { endpoint: 'nlp_analyze' },
  };
  
  const startTime = Date.now();
  const response = http.post(
    `${BASE_URL}/api/v1/nlp/analyze`,
    JSON.stringify(payload),
    params
  );
  const duration = Date.now() - startTime;
  
  nlpLatency.add(duration);
  
  const success = check(response, {
    'NLP analysis status is 200': (r) => r.status === 200,
    'NLP analysis returns intent': (r) => {
      const body = JSON.parse(r.body);
      return body.data && body.data.intent;
    },
    'NLP confidence > 0.7': (r) => {
      const body = JSON.parse(r.body);
      return body.data && body.data.confidence > 0.7;
    },
    'NLP latency < 1500ms': () => duration < 1500,
  });
  
  errorRate.add(!success);
}

export function testPreviewGeneration() {
  const payload = {
    changes: PREVIEW_CHANGES,
    service_id: 'shopify',
  };
  
  const params = {
    headers: getAuthHeaders(),
    tags: { endpoint: 'preview_generate' },
  };
  
  const startTime = Date.now();
  const response = http.post(
    `${BASE_URL}/api/v1/preview/generate`,
    JSON.stringify(payload),
    params
  );
  const duration = Date.now() - startTime;
  
  previewLatency.add(duration);
  
  const success = check(response, {
    'Preview generation status is 200': (r) => r.status === 200,
    'Preview returns ID': (r) => {
      const body = JSON.parse(r.body);
      return body.data && body.data.id;
    },
    'Preview latency < 500ms': () => duration < 500,
  });
  
  errorRate.add(!success);
  
  // If successful, test refinement
  if (response.status === 200) {
    const body = JSON.parse(response.body);
    const previewId = body.data.id;
    
    sleep(1);
    
    const refinePayload = {
      refinement: '価格を500円に変更',
    };
    
    const refineResponse = http.post(
      `${BASE_URL}/api/v1/preview/${previewId}/refine`,
      JSON.stringify(refinePayload),
      params
    );
    
    check(refineResponse, {
      'Preview refinement status is 200': (r) => r.status === 200,
    });
  }
}

export function testLPRFlow() {
  const fingerprint = generateDeviceFingerprint();
  
  // Issue LPR token
  const issuePayload = {
    service: 'shopify',
    purpose: 'load_test',
    scopes: [
      { method: 'GET', url_pattern: '/api/v1/shopify/*' },
    ],
    device_fingerprint: fingerprint,
    consent: true,
  };
  
  const params = {
    headers: getAuthHeaders(),
    tags: { endpoint: 'lpr_issue' },
  };
  
  const startTime = Date.now();
  const issueResponse = http.post(
    `${BASE_URL}/api/v1/lpr/issue`,
    JSON.stringify(issuePayload),
    params
  );
  const issueDuration = Date.now() - startTime;
  
  lprLatency.add(issueDuration);
  
  const issueSuccess = check(issueResponse, {
    'LPR issue status is 200': (r) => r.status === 200,
    'LPR token received': (r) => {
      const body = JSON.parse(r.body);
      return body.data && body.data.token;
    },
    'LPR issue latency < 200ms': () => issueDuration < 200,
  });
  
  errorRate.add(!issueSuccess);
  
  if (issueResponse.status === 200) {
    const body = JSON.parse(issueResponse.body);
    const token = body.data.token;
    const jti = body.data.jti;
    
    // Verify token
    const verifyPayload = {
      token: token,
      device_fingerprint: fingerprint,
    };
    
    const verifyResponse = http.post(
      `${BASE_URL}/api/v1/lpr/verify`,
      JSON.stringify(verifyPayload),
      params
    );
    
    check(verifyResponse, {
      'LPR verify status is 200': (r) => r.status === 200,
      'LPR token is valid': (r) => {
        const body = JSON.parse(r.body);
        return body.data && body.data.valid === true;
      },
    });
    
    // Revoke token
    sleep(1);
    
    const revokePayload = {
      jti: jti,
      reason: 'test_complete',
    };
    
    const revokeResponse = http.post(
      `${BASE_URL}/api/v1/lpr/revoke`,
      JSON.stringify(revokePayload),
      params
    );
    
    check(revokeResponse, {
      'LPR revoke status is 200': (r) => r.status === 200,
    });
  }
}

export function testConcurrentRequests() {
  // Test system behavior under concurrent load
  const batch = [
    ['GET', `${BASE_URL}/health`],
    ['POST', `${BASE_URL}/api/v1/nlp/analyze`, JSON.stringify({ text: 'test' })],
    ['GET', `${BASE_URL}/metrics`],
  ];
  
  const responses = http.batch(batch.map(([method, url, body]) => ({
    method,
    url,
    body,
    params: { headers: getAuthHeaders() },
  })));
  
  responses.forEach((response, index) => {
    check(response, {
      [`Request ${index} succeeded`]: (r) => r.status < 500,
    });
  });
}

// Main test function
export default function () {
  // Mix of different operations to simulate real usage
  const scenario = Math.random();
  
  if (scenario < 0.1) {
    testHealthCheck();
  } else if (scenario < 0.5) {
    testNLPAnalysis();
  } else if (scenario < 0.7) {
    testPreviewGeneration();
  } else if (scenario < 0.9) {
    testLPRFlow();
  } else {
    testConcurrentRequests();
  }
  
  // Think time between requests
  sleep(Math.random() * 2 + 1);
}

// Teardown function
export function teardown(data) {
  console.log('Load test completed');
  console.log(`Total VUs: ${__ENV.K6_VUS}`);
  console.log(`Duration: ${__ENV.K6_DURATION}`);
}