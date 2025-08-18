# インシデント対応 Runbook
## 即座に実行可能な手順書

---

## 🚨 緊急度別クイックリファレンス

### 🔴 CRITICAL - サービス完全停止
```bash
# 5秒で状況把握
kubectl get pods -n shodo | grep -v Running
curl -sf https://api.shodo.example.com/health || echo "API DOWN"

# 30秒で自動復旧試行
./scripts/auto-recovery.sh --mode=emergency
```

### 🟡 HIGH - パフォーマンス劣化
```bash
# メトリクス確認
kubectl top pods -n shodo
curl -s http://localhost:9090/api/v1/query?query=rate(http_request_duration_seconds[5m])

# スケールアウト
kubectl scale deployment/shodo-backend -n shodo --replicas=10
```

### 🔵 MEDIUM - 単一機能障害
```bash
# 影響サービス再起動
kubectl rollout restart deployment/[SERVICE_NAME] -n shodo
kubectl rollout status deployment/[SERVICE_NAME] -n shodo
```

---

## 📋 チェックリスト型対応手順

### ✅ 初動対応チェックリスト（5分以内）

- [ ] **1. アラート確認**
  ```bash
  # Slack/PagerDutyでアラート内容確認
  # Grafanaダッシュボード確認
  open https://grafana.shodo.example.com/d/alerts
  ```

- [ ] **2. 影響範囲特定**
  ```bash
  # サービス状態確認
  for svc in backend frontend ai-server; do
    echo "=== $svc ==="
    kubectl get pods -n shodo -l app=shodo-$svc
    curl -sf https://api.shodo.example.com/health || echo "DOWN"
  done
  ```

- [ ] **3. インシデント宣言**
  ```bash
  # インシデント記録開始
  ./scripts/incident.sh declare \
    --severity=[CRITICAL|HIGH|MEDIUM|LOW] \
    --service=[affected-service] \
    --description="[brief description]"
  ```

- [ ] **4. 関係者通知**
  ```bash
  # 自動通知
  ./scripts/notify.sh \
    --channel=oncall \
    --severity=[severity] \
    --message="[status update]"
  ```

- [ ] **5. 対応記録開始**
  ```bash
  # タイムスタンプ付きログ開始
  script -f incident-$(date +%Y%m%d-%H%M%S).log
  ```

---

## 🔧 サービス別復旧手順

### Backend API

#### 症状: レスポンス遅延
```bash
# 1. 現状確認
kubectl logs -n shodo deployment/shodo-backend --tail=100 | grep ERROR
kubectl top pods -n shodo -l app=shodo-backend

# 2. 即時対応
# Option A: Pod増設
kubectl scale deployment/shodo-backend -n shodo --replicas=8

# Option B: 問題Podの再起動
kubectl delete pod -n shodo [PROBLEMATIC_POD_NAME]

# 3. 根本対応
# メモリリーク疑いの場合
kubectl set resources deployment/shodo-backend -n shodo \
  --limits=memory=6Gi --requests=memory=2Gi

# 4. 確認
watch -n 2 'kubectl top pods -n shodo -l app=shodo-backend'
```

#### 症状: 5xxエラー多発
```bash
# 1. エラーログ確認
kubectl logs -n shodo deployment/shodo-backend --tail=500 | grep -E "ERROR|CRITICAL"

# 2. 最新デプロイが原因の場合
kubectl rollout undo deployment/shodo-backend -n shodo
kubectl rollout status deployment/shodo-backend -n shodo

# 3. データベース接続問題の場合
kubectl exec -n shodo deployment/shodo-backend -- \
  python -c "from src.services.database import check_database_health; import asyncio; print(asyncio.run(check_database_health()))"

# 4. 監視
curl -sf https://api.shodo.example.com/health | jq .
```

### Database (PostgreSQL)

#### 症状: 接続エラー
```bash
# 1. PostgreSQL Pod状態確認
kubectl get pods -n shodo -l app=postgres
kubectl logs -n shodo postgres-primary-0 --tail=100

# 2. 接続テスト
kubectl exec -n shodo postgres-primary-0 -- pg_isready -U shodo

# 3. 接続数確認
kubectl exec -n shodo postgres-primary-0 -- psql -U shodo -d shodo -c "
  SELECT count(*) as connections,
         state,
         wait_event_type
  FROM pg_stat_activity
  GROUP BY state, wait_event_type;"

# 4. 必要に応じて接続リセット
kubectl exec -n shodo postgres-primary-0 -- psql -U shodo -d shodo -c "
  SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
  WHERE state = 'idle'
    AND state_change < now() - interval '10 minutes';"
```

#### 症状: レプリケーション遅延
```bash
# 1. レプリケーション状態確認
kubectl exec -n shodo postgres-primary-0 -- psql -U shodo -c "
  SELECT client_addr,
         state,
         sent_lsn,
         write_lsn,
         flush_lsn,
         replay_lsn,
         write_lag,
         flush_lag,
         replay_lag
  FROM pg_stat_replication;"

# 2. レプリカ側確認
kubectl exec -n shodo postgres-replica-0 -- psql -U shodo -c "
  SELECT now() - pg_last_xact_replay_timestamp() AS replication_lag;"

# 3. 大きな遅延がある場合
# レプリカ再構築
kubectl delete pod postgres-replica-0 -n shodo
```

### Redis

#### 症状: メモリ不足
```bash
# 1. メモリ使用状況確認
kubectl exec -n shodo redis-master-0 -- redis-cli INFO memory

# 2. キー分析
kubectl exec -n shodo redis-master-0 -- redis-cli --bigkeys

# 3. 緊急クリア（注意：キャッシュクリア）
kubectl exec -n shodo redis-master-0 -- redis-cli FLUSHDB

# 4. メモリ上限変更
kubectl exec -n shodo redis-master-0 -- redis-cli CONFIG SET maxmemory 2gb
kubectl exec -n shodo redis-master-0 -- redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

### AI Server

#### 症状: モデルロードエラー
```bash
# 1. GPU状態確認
kubectl exec -n shodo deployment/shodo-ai-server -- nvidia-smi

# 2. モデルファイル確認
kubectl exec -n shodo deployment/shodo-ai-server -- ls -la /models/

# 3. Pod再起動（モデル再ロード）
kubectl delete pod -n shodo -l app=shodo-ai-server

# 4. メモリ不足の場合
kubectl set resources deployment/shodo-ai-server -n shodo \
  --limits=memory=48Gi --requests=memory=32Gi
```

---

## 📊 監視コマンド集

### リアルタイム監視
```bash
# 全体監視
watch -n 2 'kubectl get pods -n shodo | grep -v Running'

# メトリクス監視
watch -n 5 'curl -s localhost:9090/api/v1/query?query=up | jq .data.result[].value[1]'

# ログストリーム
kubectl logs -n shodo -f deployment/shodo-backend --tail=100

# トラフィック監視
kubectl exec -n shodo deployment/shodo-backend -- \
  sh -c 'while true; do netstat -an | grep ESTABLISHED | wc -l; sleep 2; done'
```

### パフォーマンス分析
```bash
# レスポンスタイム測定
for i in {1..10}; do
  time curl -sf https://api.shodo.example.com/health > /dev/null
  sleep 1
done

# 負荷テスト（軽量版）
ab -n 100 -c 10 https://api.shodo.example.com/health

# データベーススロークエリ
kubectl exec -n shodo postgres-primary-0 -- psql -U shodo -d shodo -c "
  SELECT query,
         calls,
         mean_exec_time,
         total_exec_time
  FROM pg_stat_statements
  ORDER BY mean_exec_time DESC
  LIMIT 10;"
```

---

## 🔄 ロールバック手順

### アプリケーションロールバック
```bash
# 1. 現在のリビジョン確認
kubectl rollout history deployment/shodo-backend -n shodo

# 2. 前バージョンへロールバック
kubectl rollout undo deployment/shodo-backend -n shodo

# 3. 特定リビジョンへロールバック
kubectl rollout undo deployment/shodo-backend -n shodo --to-revision=3

# 4. ステータス確認
kubectl rollout status deployment/shodo-backend -n shodo

# 5. 検証
./scripts/smoke-test.sh
```

### データベースロールバック（PITR）
```bash
# 1. 復旧ポイント確認
kubectl exec -n shodo postgres-primary-0 -- \
  pg_waldump -p /var/lib/postgresql/data/pg_wal -t 1

# 2. 特定時点へ復旧
./scripts/pitr-recovery.sh \
  --timestamp="2024-01-20 14:30:00 JST" \
  --confirm=yes

# 3. データ検証
./scripts/verify-data.sh
```

---

## 📞 エスカレーション

### 判断基準
| 条件 | アクション |
|------|-----------|
| 5分で解決不可 | チームリードに連絡 |
| 10分で解決不可 | CTOに連絡 |
| データ損失リスク | 即座に全体通知 |
| セキュリティ侵害疑い | セキュリティチーム即時招集 |

### 連絡テンプレート
```
【インシデント報告】
発生時刻: YYYY-MM-DD HH:MM JST
影響サービス: [Service Name]
影響範囲: [全体/一部機能/特定ユーザー]
現在の状態: [調査中/対応中/復旧済み]
推定復旧時刻: HH:MM
対応者: [Name]
次回更新: HH:MM

詳細:
[問題の詳細説明]

実施済み対応:
- [対応1]
- [対応2]

次の対応:
- [予定1]
- [予定2]
```

---

## 📝 事後対応

### インシデント終了後チェックリスト
- [ ] サービス完全復旧確認
- [ ] 監視アラートクリア
- [ ] インシデント終了宣言
- [ ] タイムライン作成
- [ ] 影響ユーザー数集計
- [ ] Post-mortem日程調整
- [ ] 改善タスク起票

### ログ・証跡保全
```bash
# インシデントログ保存
./scripts/collect-incident-logs.sh \
  --start="2024-01-20 14:00:00" \
  --end="2024-01-20 15:00:00" \
  --output=/backup/incidents/

# 監査ログ抽出
kubectl exec -n shodo deployment/shodo-backend -- \
  python -c "from src.services.audit.audit_logger import get_audit_logger; ..."
```

---

## 🛠️ ユーティリティスクリプト

すべてのスクリプトは `/opt/shodo/scripts/` に配置済み：

- `auto-recovery.sh` - 自動復旧
- `health-check.sh` - ヘルスチェック
- `collect-logs.sh` - ログ収集
- `notify.sh` - 通知送信
- `incident.sh` - インシデント管理
- `rollback.sh` - ロールバック
- `scale.sh` - スケーリング
- `backup.sh` - バックアップ
- `restore.sh` - リストア
- `test-dr.sh` - DR演習

---

**最終更新**: 2024-01-XX  
**次回レビュー**: 2024-02-XX