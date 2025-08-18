# 災害復旧・事業継続計画 (DR/BCP)
## Shodo Ecosystem Production

**文書バージョン**: 1.0.0  
**最終更新日**: 2024-01-XX  
**承認者**: CTO/インフラ責任者  
**レビュー周期**: 四半期ごと

---

## 1. 目標と要件

### 1.1 SLO要件
| 指標 | 目標値 | 現在の能力 |
|------|--------|------------|
| **RTO (Recovery Time Objective)** | ≤ 30分 | 20分（演習実績） |
| **RPO (Recovery Point Objective)** | ≤ 5分 | 1分（レプリケーション間隔） |
| **可用性** | 99.95% | 99.96%（過去3ヶ月） |
| **データ整合性** | 100% | 100% |

### 1.2 対象システム
- **Critical (Tier 1)**: Backend API, Database, Redis
- **Important (Tier 2)**: Frontend, AI Server
- **Standard (Tier 3)**: Monitoring, Logging

---

## 2. 災害シナリオと対応戦略

### 2.1 シナリオマトリックス

| シナリオ | 影響範囲 | RTO | 対応戦略 |
|---------|----------|-----|----------|
| **単一Pod障害** | 最小 | 0分 | 自動復旧（K8s） |
| **Node障害** | 小 | 2分 | Pod再スケジュール |
| **AZ障害** | 中 | 10分 | Multi-AZフェイルオーバー |
| **Region障害** | 大 | 30分 | Cross-Regionフェイルオーバー |
| **データ破損** | 重大 | 15分 | バックアップからの復旧 |
| **セキュリティ侵害** | 重大 | 即時 | 緊急隔離→調査→復旧 |
| **DDoS攻撃** | 中 | 5分 | WAF/CDN自動緩和 |

### 2.2 データバックアップ戦略

```yaml
バックアップスケジュール:
  PostgreSQL:
    - フル: 毎日 02:00 JST
    - 増分: 1時間ごと
    - PITR: 継続的（1分間隔）
    - 保持期間: 30日
    
  Redis:
    - スナップショット: 1時間ごと
    - AOF: 毎秒
    - 保持期間: 7日
    
  アプリケーションデータ:
    - S3同期: リアルタイム
    - Cross-Region レプリケーション: 有効
    
  設定・シークレット:
    - Vault: リアルタイムレプリケーション
    - 暗号化バックアップ: 毎日
```

---

## 3. 復旧手順 (Runbook)

### 3.1 🔴 CRITICAL: 完全サービス停止

#### 初動対応（5分以内）
```bash
# 1. インシデント宣言
./scripts/incident.sh declare --severity=critical --service=all

# 2. 状況確認
kubectl get nodes -o wide
kubectl get pods -n shodo --field-selector status.phase!=Running
kubectl top nodes
kubectl top pods -n shodo

# 3. 監視ダッシュボード確認
open https://grafana.shodo.example.com/d/dr-overview

# 4. 通知
./scripts/notify.sh --channel=oncall --severity=critical
```

#### 診断（10分以内）
```bash
# システム全体の健全性チェック
./scripts/health-check.sh --comprehensive

# ログ収集
./scripts/collect-logs.sh --last=30m --severity=error

# 依存サービス確認
./scripts/check-dependencies.sh
```

#### 復旧アクション（15分以内）
```bash
# Option A: 自動復旧（推奨）
./scripts/auto-recovery.sh --mode=full

# Option B: 手動復旧
# 1. データベース復旧
./scripts/recover-database.sh --source=latest-backup

# 2. アプリケーション再デプロイ
kubectl rollout restart deployment -n shodo

# 3. 検証
./scripts/validate-recovery.sh
```

### 3.2 🟡 WARNING: データベース障害

#### PostgreSQL Primary障害
```bash
# 1. 状況確認
kubectl exec -n shodo postgres-primary-0 -- pg_isready
kubectl logs -n shodo postgres-primary-0 --tail=100

# 2. フェイルオーバー実行
./scripts/db-failover.sh --promote=postgres-replica-0

# 3. 新レプリカ作成
kubectl scale statefulset postgres-replica --replicas=2

# 4. アプリケーション接続切り替え
kubectl set env deployment/shodo-backend -n shodo \
  DATABASE_URL="postgresql://user:pass@postgres-replica-0:5432/shodo"

# 5. 検証
./scripts/test-database.sh
```

#### データ復旧（PITR）
```bash
# 特定時点への復旧
./scripts/pitr-recovery.sh \
  --timestamp="2024-01-20 14:30:00 JST" \
  --target-db=postgres-recovery

# データ検証
./scripts/verify-data-integrity.sh

# 本番切り替え
./scripts/switch-database.sh --new=postgres-recovery
```

### 3.3 🟠 MAJOR: Region障害

#### Cross-Region フェイルオーバー
```bash
# 1. DR サイト起動
./scripts/dr-activate.sh --region=us-west-2

# 2. DNS切り替え
./scripts/update-dns.sh \
  --record=api.shodo.example.com \
  --target=dr-api.shodo.example.com \
  --ttl=60

# 3. データ同期確認
./scripts/verify-replication.sh --source=ap-northeast-1 --target=us-west-2

# 4. トラフィック切り替え
./scripts/switch-traffic.sh --target=dr --percentage=100

# 5. 監視
watch -n 5 './scripts/monitor-dr.sh'
```

### 3.4 🔵 MINOR: 単一サービス障害

#### Backend API復旧
```bash
# 1. Pod 再起動
kubectl delete pod -n shodo -l app=shodo-backend

# 2. 必要に応じてロールバック
kubectl rollout undo deployment/shodo-backend -n shodo

# 3. スケールアウト
kubectl scale deployment/shodo-backend -n shodo --replicas=8

# 4. 検証
curl -f https://api.shodo.example.com/health || exit 1
```

---

## 4. 自動化スクリプト

### 4.1 自動復旧スクリプト
```bash
#!/bin/bash
# scripts/auto-recovery.sh

set -euo pipefail

RECOVERY_MODE=${1:-"auto"}
NAMESPACE="shodo"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

check_health() {
    local service=$1
    kubectl exec -n $NAMESPACE deployment/$service -- curl -sf http://localhost:8000/health > /dev/null 2>&1
}

recover_service() {
    local service=$1
    log "Recovering $service..."
    
    # Try restart first
    kubectl rollout restart deployment/$service -n $NAMESPACE
    kubectl rollout status deployment/$service -n $NAMESPACE --timeout=5m
    
    if ! check_health $service; then
        log "Restart failed, attempting rollback..."
        kubectl rollout undo deployment/$service -n $NAMESPACE
        kubectl rollout status deployment/$service -n $NAMESPACE --timeout=5m
    fi
    
    if check_health $service; then
        log "$service recovered successfully"
        return 0
    else
        log "Failed to recover $service"
        return 1
    fi
}

main() {
    log "Starting auto-recovery in $RECOVERY_MODE mode"
    
    # Check cluster connectivity
    if ! kubectl cluster-info > /dev/null 2>&1; then
        log "ERROR: Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    # Recover services in priority order
    SERVICES=("shodo-backend" "shodo-frontend" "shodo-ai-server")
    
    for service in "${SERVICES[@]}"; do
        if ! check_health $service; then
            recover_service $service || {
                log "CRITICAL: Failed to recover $service"
                if [[ "$RECOVERY_MODE" == "auto" ]]; then
                    ./scripts/escalate.sh --service=$service
                fi
            }
        else
            log "$service is healthy"
        fi
    done
    
    log "Recovery process completed"
}

main "$@"
```

### 4.2 データ整合性チェック
```bash
#!/bin/bash
# scripts/verify-data-integrity.sh

set -euo pipefail

check_database_integrity() {
    echo "Checking database integrity..."
    
    kubectl exec -n shodo postgres-primary-0 -- psql -U shodo -d shodo -c "
        SELECT 
            schemaname,
            tablename,
            pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
            n_live_tup AS row_count
        FROM pg_stat_user_tables
        ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
        LIMIT 10;
    "
    
    # Run consistency checks
    kubectl exec -n shodo postgres-primary-0 -- psql -U shodo -d shodo -c "
        -- Check foreign key constraints
        SELECT conname, conrelid::regclass AS table_name
        FROM pg_constraint
        WHERE NOT convalidated
        LIMIT 10;
    "
}

check_redis_integrity() {
    echo "Checking Redis integrity..."
    
    kubectl exec -n shodo redis-master-0 -- redis-cli INFO persistence
    kubectl exec -n shodo redis-master-0 -- redis-cli DBSIZE
    kubectl exec -n shodo redis-master-0 -- redis-cli --scan --pattern 'lpr:*' | head -10
}

check_application_health() {
    echo "Checking application health..."
    
    # Test critical endpoints
    ENDPOINTS=(
        "https://api.shodo.example.com/health"
        "https://api.shodo.example.com/api/v1/nlp/health"
        "https://api.shodo.example.com/api/v1/preview/health"
    )
    
    for endpoint in "${ENDPOINTS[@]}"; do
        if curl -sf "$endpoint" > /dev/null; then
            echo "✓ $endpoint is healthy"
        else
            echo "✗ $endpoint is unhealthy"
            return 1
        fi
    done
}

main() {
    echo "=== Data Integrity Verification ==="
    echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    
    check_database_integrity
    check_redis_integrity
    check_application_health
    
    echo "=== Verification Complete ==="
}

main "$@"
```

---

## 5. 演習計画

### 5.1 定期演習スケジュール

| 演習タイプ | 頻度 | 所要時間 | 参加者 |
|-----------|------|----------|--------|
| **テーブルトップ演習** | 月次 | 2時間 | 開発・運用チーム |
| **部分復旧演習** | 四半期 | 4時間 | 運用チーム |
| **完全DR演習** | 半年 | 8時間 | 全チーム |
| **セキュリティ演習** | 年次 | 1日 | 全社 |

### 5.2 演習シナリオ

#### Scenario A: データベース障害（四半期演習）
```yaml
目的: PostgreSQL障害からの復旧
想定時間: 15分以内
成功基準:
  - データ損失なし
  - 15分以内の復旧
  - 全サービス正常稼働

手順:
  1. PostgreSQL Primaryを意図的に停止
  2. アラート確認
  3. フェイルオーバー実行
  4. サービス復旧確認
  5. 新レプリカ構築

検証項目:
  - RPO達成（5分以内）
  - RTO達成（30分以内）
  - データ整合性
  - 監査ログ完全性
```

#### Scenario B: Region障害（半年演習）
```yaml
目的: 完全Region障害からの復旧
想定時間: 30分以内
成功基準:
  - Cross-Region切り替え成功
  - データ同期確認
  - パフォーマンス劣化10%以内

手順:
  1. Primary Regionを隔離
  2. DR サイト起動
  3. DNS/CDN切り替え
  4. データ同期確認
  5. フルサービス検証
  6. フェイルバック計画
```

---

## 6. 連絡体制

### 6.1 エスカレーションマトリックス

| レベル | 条件 | 通知先 | 応答時間 |
|--------|------|--------|----------|
| **L1** | 単一Pod障害 | 運用チーム | 15分 |
| **L2** | サービス劣化 | 開発リード | 10分 |
| **L3** | サービス停止 | CTO/VP Eng | 5分 |
| **L4** | データ損失リスク | CEO/全役員 | 即時 |

### 6.2 緊急連絡先

```yaml
On-Call:
  Primary: +81-XXX-XXXX-XXXX
  Secondary: +81-XXX-XXXX-XXXX
  
Escalation:
  CTO: +81-XXX-XXXX-XXXX
  VP Engineering: +81-XXX-XXXX-XXXX
  
External:
  AWS Support: Premium Support Console
  GCP Support: P1 Ticket
  Security Team: security@shodo.example.com
```

---

## 7. 復旧後の手順

### 7.1 Post-Mortem プロセス

1. **インシデントタイムライン作成**（24時間以内）
2. **根本原因分析**（48時間以内）
3. **改善アクションアイテム定義**（72時間以内）
4. **Post-Mortemミーティング**（1週間以内）
5. **改善実装**（2週間以内）

### 7.2 必須改善項目

- [ ] 自動化の改善
- [ ] 監視の強化
- [ ] ドキュメント更新
- [ ] 演習シナリオ追加
- [ ] ツール改善

---

## 8. ツールとリソース

### 8.1 必須ツール

| ツール | 用途 | アクセス |
|--------|------|----------|
| **Kubernetes Dashboard** | クラスタ管理 | https://k8s.shodo.example.com |
| **Grafana** | 監視 | https://grafana.shodo.example.com |
| **Prometheus** | メトリクス | https://prometheus.shodo.example.com |
| **Jaeger** | トレーシング | https://jaeger.shodo.example.com |
| **Vault** | シークレット管理 | https://vault.shodo.example.com |
| **PagerDuty** | アラート管理 | https://shodo.pagerduty.com |

### 8.2 ドキュメント

- [アーキテクチャ図](./architecture.md)
- [ネットワーク図](./network-topology.md)
- [セキュリティポリシー](./security-policy.md)
- [監視設定](./monitoring-setup.md)

---

## 9. 改訂履歴

| バージョン | 日付 | 変更内容 | 承認者 |
|-----------|------|----------|--------|
| 1.0.0 | 2024-01-XX | 初版作成 | CTO |
| | | | |

---

## 10. 承認

本DR/BCP計画は以下の責任者により承認されました：

- **CTO**: _____________________ 日付: _____
- **VP Engineering**: _____________________ 日付: _____
- **Security Officer**: _____________________ 日付: _____

次回レビュー予定日: 2024-04-XX