#!/bin/bash

# 監視システム起動スクリプト
# Prometheus, Grafana, Loki, AlertManagerを起動

set -e

echo "🔍 Starting Shodo Ecosystem Monitoring Stack..."

# 設定ファイルの存在確認
if [ ! -f "monitoring/prometheus/prometheus.yml" ]; then
    echo "❌ Prometheus configuration not found!"
    echo "Please ensure monitoring configuration files are present."
    exit 1
fi

# 監視用ネットワークの作成
echo "📡 Creating monitoring network..."
docker network create monitoring-network 2>/dev/null || echo "Network already exists"

# 監視システム起動
echo "🚀 Starting monitoring services..."
docker-compose -f docker-compose.monitoring.yml up -d

# 起動待機
echo "⏳ Waiting for services to start..."
sleep 30

# ヘルスチェック
echo "🏥 Checking service health..."

services=(
    "prometheus:9090"
    "grafana:3001"
    "loki:3100"
    "alertmanager:9093"
)

all_healthy=true

for service in "${services[@]}"; do
    name=$(echo $service | cut -d: -f1)
    port=$(echo $service | cut -d: -f2)
    
    if curl -f -s http://localhost:$port/health >/dev/null 2>&1 || \
       curl -f -s http://localhost:$port >/dev/null 2>&1; then
        echo "✅ $name is healthy"
    else
        echo "❌ $name is not responding"
        all_healthy=false
    fi
done

if [ "$all_healthy" = true ]; then
    echo ""
    echo "🎉 Monitoring stack started successfully!"
    echo ""
    echo "📊 Access URLs:"
    echo "  Grafana:      http://localhost:3001 (admin/admin123)"
    echo "  Prometheus:   http://localhost:9090"
    echo "  AlertManager: http://localhost:9093"
    echo "  Loki:         http://localhost:3100"
    echo ""
    echo "📈 Default dashboards are pre-configured in Grafana"
    echo "🚨 Alerts will be sent according to alertmanager configuration"
else
    echo ""
    echo "⚠️  Some services are not healthy. Check logs:"
    echo "docker-compose -f docker-compose.monitoring.yml logs"
fi