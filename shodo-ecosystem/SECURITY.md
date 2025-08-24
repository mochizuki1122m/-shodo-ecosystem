# Security Policy

## Supported Versions
- main, develop ブランチに対してセキュリティ修正を提供します

## Reporting a Vulnerability
- 連絡先: security@shodo.example.com
- 重大度区分: Critical / High / Medium / Low
- 含めてほしい情報: 再現手順、影響範囲、PoC、回避策
- 機密保持: 公開前に事前連絡をお願いします（90日公開ポリシー）

## SLA
- Critical: 24時間以内に暫定対処、72時間以内に恒久対応
- High: 3営業日以内に恒久対応
- Medium/Low: 次回定期リリースで対応

## Scope
- バックエンドAPI、AIサーバ、フロントエンド、インフラ構成（Docker/K8s/監視）
- サードパーティ依存性は最小化し、継続的に監査します

## CORS/CSP 運用指針
- 本番: `TrustedHostMiddleware`でFQDNを限定し、CORSは`CORS_ORIGINS`で必要最小限のオリジンのみ許可。ワイルドカード禁止。
- 開発: `localhost`系のみ許容。デバッグ用途で一時的なワイルドカードを用いる場合はコミットしない。
- CSP: 既定は厳格（`default-src 'self'`）。外部接続が必要な場合は`connect-src`に限定的に追加。`script-src`の`'unsafe-inline'`禁止。必要に応じてサブリソースのハッシュ/nonceを採用。
- AIサーバ: `ALLOWED_ORIGINS`で本番許容オリジンを列挙。SSE利用時も同一の方針を遵守。