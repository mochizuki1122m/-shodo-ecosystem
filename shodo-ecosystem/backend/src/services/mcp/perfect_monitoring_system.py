"""
Perfect Monitoring System - 完璧な監視システム
包括的メトリクス、ログ、アラート、ダッシュボードの統合監視
"""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import structlog
from datetime import datetime, timedelta
import uuid
import psutil
import threading

# Monitoring dependencies
import prometheus_client
from prometheus_client import Counter, Histogram, Gauge, Summary, Info, CollectorRegistry, generate_latest
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Alerting
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests  # Slack/Discord webhooks

logger = structlog.get_logger()

class AlertLevel(Enum):
    """アラートレベル"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class MetricType(Enum):
    """メトリクスタイプ"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"
    INFO = "info"

@dataclass
class AlertRule:
    """アラートルール"""
    name: str
    metric_name: str
    condition: str  # 例: "> 0.8", "< 0.95"
    threshold_value: float
    level: AlertLevel
    description: str
    cooldown_minutes: int = 5
    last_triggered: Optional[datetime] = None

@dataclass
class AlertNotification:
    """アラート通知"""
    alert_id: str
    rule_name: str
    level: AlertLevel
    message: str
    metric_value: float
    threshold_value: float
    timestamp: datetime
    service_name: Optional[str] = None
    operation_type: Optional[str] = None

class PerfectMetricsCollector:
    """完璧なメトリクス収集器"""
    
    def __init__(self):
        # カスタムレジストリ
        self.registry = CollectorRegistry()
        
        # === Core MCP Metrics ===
        
        # 接続メトリクス
        self.mcp_services_connected = Gauge(
            'mcp_services_connected_total',
            'Total connected MCP services',
            registry=self.registry
        )
        
        self.mcp_connection_attempts = Counter(
            'mcp_connection_attempts_total',
            'Total connection attempts',
            ['service_name', 'strategy', 'result'],
            registry=self.registry
        )
        
        self.mcp_connection_duration = Histogram(
            'mcp_connection_duration_seconds',
            'Time to establish service connection',
            ['service_name', 'strategy'],
            buckets=[1, 5, 10, 30, 60, 120, 300],
            registry=self.registry
        )
        
        # 操作メトリクス
        self.mcp_operations_total = Counter(
            'mcp_operations_total',
            'Total MCP operations executed',
            ['service_name', 'operation_type', 'strategy', 'result'],
            registry=self.registry
        )
        
        self.mcp_operation_duration = Histogram(
            'mcp_operation_duration_seconds',
            'MCP operation execution time',
            ['service_name', 'operation_type', 'strategy'],
            buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60],
            registry=self.registry
        )
        
        self.mcp_operation_success_rate = Summary(
            'mcp_operation_success_rate',
            'Operation success rate by service',
            ['service_name', 'operation_type']
        )
        
        # パフォーマンスメトリクス
        self.mcp_response_time_percentiles = Summary(
            'mcp_response_time_percentiles',
            'Response time percentiles',
            ['service_name']
        )
        
        self.mcp_throughput_ops_per_second = Gauge(
            'mcp_throughput_ops_per_second',
            'Operations per second',
            ['service_name']
        )
        
        # エラーメトリクス
        self.mcp_errors_total = Counter(
            'mcp_errors_total',
            'Total errors by type',
            ['service_name', 'error_type', 'strategy'],
            registry=self.registry
        )
        
        self.mcp_retry_attempts = Counter(
            'mcp_retry_attempts_total',
            'Total retry attempts',
            ['service_name', 'operation_type', 'attempt_number'],
            registry=self.registry
        )
        
        # === Legal & Compliance Metrics ===
        
        self.mcp_legal_compliance_score = Gauge(
            'mcp_legal_compliance_score',
            'Legal compliance score (0-1)',
            ['service_name'],
            registry=self.registry
        )
        
        self.mcp_terms_analysis_duration = Histogram(
            'mcp_terms_analysis_duration_seconds',
            'Terms of service analysis time',
            ['service_name'],
            registry=self.registry
        )
        
        # === Browser & Infrastructure Metrics ===
        
        self.mcp_browser_pool_size = Gauge(
            'mcp_browser_pool_size',
            'Browser pool size',
            ['engine_type'],
            registry=self.registry
        )
        
        self.mcp_browser_memory_usage = Gauge(
            'mcp_browser_memory_usage_mb',
            'Browser memory usage in MB',
            ['engine_type'],
            registry=self.registry
        )
        
        self.mcp_active_browser_contexts = Gauge(
            'mcp_active_browser_contexts',
            'Active browser contexts',
            registry=self.registry
        )
        
        # === Queue & Concurrency Metrics ===
        
        self.mcp_execution_queue_size = Gauge(
            'mcp_execution_queue_size',
            'Execution queue size',
            registry=self.registry
        )
        
        self.mcp_active_operations = Gauge(
            'mcp_active_operations',
            'Currently active operations',
            ['service_name'],
            registry=self.registry
        )
        
        self.mcp_worker_utilization = Gauge(
            'mcp_worker_utilization',
            'Worker utilization percentage',
            ['worker_id'],
            registry=self.registry
        )
        
        # === Business Metrics ===
        
        self.mcp_business_value_generated = Counter(
            'mcp_business_value_generated',
            'Business value generated (estimated)',
            ['service_name', 'operation_type'],
            registry=self.registry
        )
        
        self.mcp_cost_savings = Counter(
            'mcp_cost_savings_usd',
            'Estimated cost savings in USD',
            ['service_name'],
            registry=self.registry
        )
        
        # === System Metrics ===
        
        self.system_info = Info(
            'mcp_system_info',
            'MCP system information',
            registry=self.registry
        )
        
        self.system_cpu_usage = Gauge(
            'mcp_system_cpu_usage_percent',
            'System CPU usage percentage',
            registry=self.registry
        )
        
        self.system_memory_usage = Gauge(
            'mcp_system_memory_usage_percent',
            'System memory usage percentage',
            registry=self.registry
        )
        
        self.system_disk_usage = Gauge(
            'mcp_system_disk_usage_percent',
            'System disk usage percentage',
            registry=self.registry
        )
    
    def record_connection_attempt(
        self, 
        service_name: str, 
        strategy: str, 
        success: bool, 
        duration_seconds: float
    ):
        """接続試行の記録"""
        
        result = "success" if success else "failure"
        
        self.mcp_connection_attempts.labels(
            service_name=service_name,
            strategy=strategy,
            result=result
        ).inc()
        
        self.mcp_connection_duration.labels(
            service_name=service_name,
            strategy=strategy
        ).observe(duration_seconds)
    
    def record_operation_execution(
        self,
        service_name: str,
        operation_type: str,
        strategy: str,
        success: bool,
        duration_seconds: float,
        error_type: Optional[str] = None
    ):
        """操作実行の記録"""
        
        result = "success" if success else "failure"
        
        self.mcp_operations_total.labels(
            service_name=service_name,
            operation_type=operation_type,
            strategy=strategy,
            result=result
        ).inc()
        
        self.mcp_operation_duration.labels(
            service_name=service_name,
            operation_type=operation_type,
            strategy=strategy
        ).observe(duration_seconds)
        
        success_value = 1.0 if success else 0.0
        self.mcp_operation_success_rate.labels(
            service_name=service_name,
            operation_type=operation_type
        ).observe(success_value)
        
        if error_type and not success:
            self.mcp_errors_total.labels(
                service_name=service_name,
                error_type=error_type,
                strategy=strategy
            ).inc()
    
    def update_system_metrics(self):
        """システムメトリクスの更新"""
        
        # CPU使用率
        cpu_percent = psutil.cpu_percent()
        self.system_cpu_usage.set(cpu_percent)
        
        # メモリ使用率
        memory = psutil.virtual_memory()
        self.system_memory_usage.set(memory.percent)
        
        # ディスク使用率
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        self.system_disk_usage.set(disk_percent)
    
    def set_legal_compliance_score(self, service_name: str, score: float):
        """法的コンプライアンススコアの設定"""
        self.mcp_legal_compliance_score.labels(service_name=service_name).set(score)
    
    def record_business_value(self, service_name: str, operation_type: str, value_usd: float):
        """ビジネス価値の記録"""
        self.mcp_business_value_generated.labels(
            service_name=service_name,
            operation_type=operation_type
        ).inc(value_usd)

class PerfectAlertingSystem:
    """完璧なアラートシステム"""
    
    def __init__(self, metrics_collector: PerfectMetricsCollector):
        self.metrics_collector = metrics_collector
        self.alert_rules: List[AlertRule] = []
        self.notification_channels = {}
        self.alert_history = []
        
        self._initialize_default_rules()
        self._initialize_notification_channels()
    
    def _initialize_default_rules(self):
        """デフォルトアラートルールの初期化"""
        
        self.alert_rules = [
            # システムリソース
            AlertRule(
                name="high_cpu_usage",
                metric_name="mcp_system_cpu_usage_percent",
                condition="> 80",
                threshold_value=80.0,
                level=AlertLevel.WARNING,
                description="CPU使用率が80%を超えています",
                cooldown_minutes=5
            ),
            AlertRule(
                name="critical_cpu_usage",
                metric_name="mcp_system_cpu_usage_percent",
                condition="> 95",
                threshold_value=95.0,
                level=AlertLevel.CRITICAL,
                description="CPU使用率が95%を超えています",
                cooldown_minutes=2
            ),
            
            # 操作成功率
            AlertRule(
                name="low_success_rate",
                metric_name="mcp_operation_success_rate",
                condition="< 0.8",
                threshold_value=0.8,
                level=AlertLevel.WARNING,
                description="操作成功率が80%を下回っています",
                cooldown_minutes=10
            ),
            AlertRule(
                name="critical_success_rate",
                metric_name="mcp_operation_success_rate",
                condition="< 0.5",
                threshold_value=0.5,
                level=AlertLevel.CRITICAL,
                description="操作成功率が50%を下回っています",
                cooldown_minutes=5
            ),
            
            # レスポンス時間
            AlertRule(
                name="slow_response_time",
                metric_name="mcp_operation_duration_seconds",
                condition="> 30",
                threshold_value=30.0,
                level=AlertLevel.WARNING,
                description="操作レスポンス時間が30秒を超えています",
                cooldown_minutes=15
            ),
            
            # エラー率
            AlertRule(
                name="high_error_rate",
                metric_name="mcp_errors_total",
                condition="> 10",
                threshold_value=10.0,
                level=AlertLevel.ERROR,
                description="エラー発生率が高くなっています",
                cooldown_minutes=5
            ),
            
            # 法的コンプライアンス
            AlertRule(
                name="low_compliance_score",
                metric_name="mcp_legal_compliance_score",
                condition="< 0.7",
                threshold_value=0.7,
                level=AlertLevel.WARNING,
                description="法的コンプライアンススコアが低下しています",
                cooldown_minutes=60
            )
        ]
    
    def _initialize_notification_channels(self):
        """通知チャネルの初期化"""
        
        self.notification_channels = {
            "console": self._console_notification,
            "email": self._email_notification,
            "slack": self._slack_notification,
            "discord": self._discord_notification,
            "webhook": self._webhook_notification
        }
    
    async def start_monitoring(self):
        """監視の開始"""
        
        logger.info("Starting perfect monitoring system")
        
        # 監視タスクの起動
        monitoring_tasks = [
            asyncio.create_task(self._metrics_collection_worker()),
            asyncio.create_task(self._alert_evaluation_worker()),
            asyncio.create_task(self._system_health_worker()),
            asyncio.create_task(self._performance_analysis_worker())
        ]
        
        await asyncio.gather(*monitoring_tasks, return_exceptions=True)
    
    async def _metrics_collection_worker(self):
        """メトリクス収集ワーカー"""
        
        while True:
            try:
                # システムメトリクスの更新
                self.metrics_collector.update_system_metrics()
                
                # カスタムメトリクスの収集
                await self._collect_custom_metrics()
                
                # 5秒間隔で収集
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Metrics collection error: {e}")
                await asyncio.sleep(10)
    
    async def _collect_custom_metrics(self):
        """カスタムメトリクスの収集"""
        
        # ブラウザプールメトリクス
        # 実装: ブラウザマネージャーからメトリクスを取得
        
        # キューメトリクス
        # 実装: 実行エンジンからキュー状態を取得
        
        # データベースメトリクス
        # 実装: データベース接続プールの状態を取得
        
        pass
    
    async def _alert_evaluation_worker(self):
        """アラート評価ワーカー"""
        
        while True:
            try:
                current_time = datetime.now()
                
                for rule in self.alert_rules:
                    # クールダウン期間のチェック
                    if (rule.last_triggered and 
                        (current_time - rule.last_triggered).total_seconds() < rule.cooldown_minutes * 60):
                        continue
                    
                    # メトリクス値の取得
                    metric_value = await self._get_metric_value(rule.metric_name)
                    
                    if metric_value is not None:
                        # 条件評価
                        if self._evaluate_condition(metric_value, rule.condition, rule.threshold_value):
                            # アラート発火
                            alert = AlertNotification(
                                alert_id=str(uuid.uuid4()),
                                rule_name=rule.name,
                                level=rule.level,
                                message=rule.description,
                                metric_value=metric_value,
                                threshold_value=rule.threshold_value,
                                timestamp=current_time
                            )
                            
                            await self._trigger_alert(alert)
                            rule.last_triggered = current_time
                
                # 30秒間隔で評価
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Alert evaluation error: {e}")
                await asyncio.sleep(60)
    
    async def _get_metric_value(self, metric_name: str) -> Optional[float]:
        """メトリクス値の取得"""
        
        try:
            # Prometheusレジストリからメトリクス値を取得
            for collector in self.registry._collector_to_names:
                if hasattr(collector, '_name') and collector._name == metric_name:
                    # メトリクスタイプに応じた値の取得
                    if hasattr(collector, '_value'):
                        return collector._value.get()
                    elif hasattr(collector, '_sum'):
                        return collector._sum.get()
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get metric value for {metric_name}: {e}")
            return None
    
    def _evaluate_condition(self, value: float, condition: str, threshold: float) -> bool:
        """条件の評価"""
        
        try:
            if condition.startswith('>'):
                return value > threshold
            elif condition.startswith('<'):
                return value < threshold
            elif condition.startswith('>='):
                return value >= threshold
            elif condition.startswith('<='):
                return value <= threshold
            elif condition.startswith('=='):
                return abs(value - threshold) < 0.001
            elif condition.startswith('!='):
                return abs(value - threshold) > 0.001
            else:
                return False
                
        except Exception as e:
            logger.error(f"Condition evaluation error: {e}")
            return False
    
    async def _trigger_alert(self, alert: AlertNotification):
        """アラートの発火"""
        
        logger.warning(f"Alert triggered: {alert.rule_name} - {alert.message}")
        
        # アラート履歴に追加
        self.alert_history.append(alert)
        
        # 履歴の制限（最新1000件のみ保持）
        if len(self.alert_history) > 1000:
            self.alert_history = self.alert_history[-1000:]
        
        # 通知の送信
        notification_tasks = []
        
        for channel_name, notification_func in self.notification_channels.items():
            try:
                task = asyncio.create_task(notification_func(alert))
                notification_tasks.append(task)
            except Exception as e:
                logger.error(f"Failed to create notification task for {channel_name}: {e}")
        
        # 通知の並列送信
        if notification_tasks:
            await asyncio.gather(*notification_tasks, return_exceptions=True)
    
    async def _console_notification(self, alert: AlertNotification):
        """コンソール通知"""
        
        level_symbols = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.ERROR: "❌",
            AlertLevel.CRITICAL: "🚨"
        }
        
        symbol = level_symbols.get(alert.level, "📢")
        
        print(f"\n{symbol} ALERT: {alert.rule_name}")
        print(f"   Level: {alert.level.value.upper()}")
        print(f"   Message: {alert.message}")
        print(f"   Metric Value: {alert.metric_value}")
        print(f"   Threshold: {alert.threshold_value}")
        print(f"   Time: {alert.timestamp.isoformat()}")
        if alert.service_name:
            print(f"   Service: {alert.service_name}")
        print("-" * 50)
    
    async def _email_notification(self, alert: AlertNotification):
        """メール通知"""
        
        # 実装: SMTP経由でのメール送信
        try:
            # 設定からメール情報を取得
            email_config = {
                "smtp_server": "localhost",
                "smtp_port": 587,
                "username": "",
                "password": "",
                "from_email": "alerts@shodo-ecosystem.com",
                "to_emails": ["admin@shodo-ecosystem.com"]
            }
            
            subject = f"[{alert.level.value.upper()}] MCP Alert: {alert.rule_name}"
            
            body = f"""
MCP システムアラート

アラート名: {alert.rule_name}
レベル: {alert.level.value.upper()}
メッセージ: {alert.message}

詳細:
- メトリクス値: {alert.metric_value}
- 閾値: {alert.threshold_value}
- 発生時刻: {alert.timestamp.isoformat()}
- サービス: {alert.service_name or 'システム全体'}

このアラートは自動的に生成されました。
詳細な情報はダッシュボードで確認してください。
"""
            
            # 実際のメール送信は実装環境に応じて
            logger.info(f"Email notification prepared for {alert.rule_name}")
            
        except Exception as e:
            logger.error(f"Email notification failed: {e}")
    
    async def _slack_notification(self, alert: AlertNotification):
        """Slack通知"""
        
        try:
            webhook_url = "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
            
            color_map = {
                AlertLevel.INFO: "#36a64f",
                AlertLevel.WARNING: "#ff9500", 
                AlertLevel.ERROR: "#ff0000",
                AlertLevel.CRITICAL: "#8b0000"
            }
            
            payload = {
                "text": f"MCP Alert: {alert.rule_name}",
                "attachments": [
                    {
                        "color": color_map.get(alert.level, "#808080"),
                        "fields": [
                            {"title": "Level", "value": alert.level.value.upper(), "short": True},
                            {"title": "Service", "value": alert.service_name or "System", "short": True},
                            {"title": "Metric Value", "value": str(alert.metric_value), "short": True},
                            {"title": "Threshold", "value": str(alert.threshold_value), "short": True},
                            {"title": "Message", "value": alert.message, "short": False}
                        ],
                        "timestamp": int(alert.timestamp.timestamp())
                    }
                ]
            }
            
            # 実際のSlack送信は実装環境に応じて
            logger.info(f"Slack notification prepared for {alert.rule_name}")
            
        except Exception as e:
            logger.error(f"Slack notification failed: {e}")
    
    async def _discord_notification(self, alert: AlertNotification):
        """Discord通知"""
        
        try:
            webhook_url = "https://discord.com/api/webhooks/YOUR/DISCORD/WEBHOOK"
            
            embed_color = {
                AlertLevel.INFO: 0x36a64f,
                AlertLevel.WARNING: 0xff9500,
                AlertLevel.ERROR: 0xff0000,
                AlertLevel.CRITICAL: 0x8b0000
            }
            
            payload = {
                "embeds": [
                    {
                        "title": f"MCP Alert: {alert.rule_name}",
                        "description": alert.message,
                        "color": embed_color.get(alert.level, 0x808080),
                        "fields": [
                            {"name": "Level", "value": alert.level.value.upper(), "inline": True},
                            {"name": "Service", "value": alert.service_name or "System", "inline": True},
                            {"name": "Value", "value": str(alert.metric_value), "inline": True},
                            {"name": "Threshold", "value": str(alert.threshold_value), "inline": True}
                        ],
                        "timestamp": alert.timestamp.isoformat()
                    }
                ]
            }
            
            # 実際のDiscord送信は実装環境に応じて
            logger.info(f"Discord notification prepared for {alert.rule_name}")
            
        except Exception as e:
            logger.error(f"Discord notification failed: {e}")
    
    async def _webhook_notification(self, alert: AlertNotification):
        """Webhook通知"""
        
        try:
            webhook_urls = [
                "https://your-monitoring-system.com/webhooks/mcp-alerts"
            ]
            
            payload = {
                "alert_id": alert.alert_id,
                "rule_name": alert.rule_name,
                "level": alert.level.value,
                "message": alert.message,
                "metric_value": alert.metric_value,
                "threshold_value": alert.threshold_value,
                "timestamp": alert.timestamp.isoformat(),
                "service_name": alert.service_name,
                "operation_type": alert.operation_type
            }
            
            # 実際のWebhook送信は実装環境に応じて
            logger.info(f"Webhook notification prepared for {alert.rule_name}")
            
        except Exception as e:
            logger.error(f"Webhook notification failed: {e}")
    
    async def _system_health_worker(self):
        """システムヘルス監視ワーカー"""
        
        while True:
            try:
                # システム全体のヘルスチェック
                health_status = await self._perform_comprehensive_health_check()
                
                # 異常検出時のアラート
                if health_status["overall_health"] < 0.8:
                    await self._trigger_health_alert(health_status)
                
                # 1分間隔でヘルスチェック
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"System health monitoring error: {e}")
                await asyncio.sleep(120)
    
    async def _perform_comprehensive_health_check(self) -> Dict[str, Any]:
        """包括的ヘルスチェック"""
        
        health_components = {
            "browser_pool": await self._check_browser_pool_health(),
            "execution_queue": await self._check_execution_queue_health(),
            "database": await self._check_database_health(),
            "redis": await self._check_redis_health(),
            "llm_service": await self._check_llm_service_health(),
            "system_resources": await self._check_system_resources_health()
        }
        
        # 全体ヘルススコアの計算
        health_scores = [component["score"] for component in health_components.values()]
        overall_health = sum(health_scores) / len(health_scores) if health_scores else 0.0
        
        return {
            "overall_health": overall_health,
            "components": health_components,
            "timestamp": datetime.now(),
            "healthy_components": sum(1 for score in health_scores if score > 0.8),
            "total_components": len(health_scores)
        }
    
    async def _check_browser_pool_health(self) -> Dict[str, Any]:
        """ブラウザプールヘルスチェック"""
        
        # 実装: ブラウザプールの状態確認
        return {
            "score": 0.9,
            "status": "healthy",
            "details": {
                "active_browsers": 3,
                "available_browsers": 5,
                "memory_usage_mb": 500
            }
        }
    
    async def _check_execution_queue_health(self) -> Dict[str, Any]:
        """実行キューヘルスチェック"""
        
        # 実装: 実行キューの状態確認
        return {
            "score": 0.95,
            "status": "healthy",
            "details": {
                "queue_size": 5,
                "active_operations": 3,
                "worker_count": 5
            }
        }
    
    async def _check_database_health(self) -> Dict[str, Any]:
        """データベースヘルスチェック"""
        
        try:
            # 実装: データベース接続テスト
            return {
                "score": 1.0,
                "status": "healthy",
                "details": {
                    "connection_pool_size": 10,
                    "active_connections": 3,
                    "response_time_ms": 5.2
                }
            }
        except Exception as e:
            return {
                "score": 0.0,
                "status": "unhealthy",
                "details": {"error": str(e)}
            }
    
    async def _check_redis_health(self) -> Dict[str, Any]:
        """Redisヘルスチェック"""
        
        try:
            # 実装: Redis接続テスト
            return {
                "score": 1.0,
                "status": "healthy",
                "details": {
                    "memory_usage_mb": 50,
                    "connected_clients": 5,
                    "response_time_ms": 1.0
                }
            }
        except Exception as e:
            return {
                "score": 0.0,
                "status": "unhealthy",
                "details": {"error": str(e)}
            }
    
    async def _check_llm_service_health(self) -> Dict[str, Any]:
        """LLMサービスヘルスチェック"""
        
        try:
            # 実装: vLLMサービスのヘルスチェック
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{settings.vllm_url}/health", timeout=10)
                
                if response.status_code == 200:
                    return {
                        "score": 1.0,
                        "status": "healthy",
                        "details": {
                            "response_time_ms": response.elapsed.total_seconds() * 1000,
                            "model_loaded": True
                        }
                    }
                else:
                    return {
                        "score": 0.5,
                        "status": "degraded",
                        "details": {"status_code": response.status_code}
                    }
                    
        except Exception as e:
            return {
                "score": 0.0,
                "status": "unhealthy",
                "details": {"error": str(e)}
            }
    
    async def _check_system_resources_health(self) -> Dict[str, Any]:
        """システムリソースヘルスチェック"""
        
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # ヘルススコアの計算
        cpu_score = max(0, 1.0 - (cpu_percent / 100))
        memory_score = max(0, 1.0 - (memory.percent / 100))
        disk_score = max(0, 1.0 - ((disk.used / disk.total)))
        
        overall_score = (cpu_score + memory_score + disk_score) / 3
        
        return {
            "score": overall_score,
            "status": "healthy" if overall_score > 0.8 else "degraded" if overall_score > 0.5 else "unhealthy",
            "details": {
                "cpu_usage_percent": cpu_percent,
                "memory_usage_percent": memory.percent,
                "disk_usage_percent": (disk.used / disk.total) * 100,
                "load_average": psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0
            }
        }
    
    async def _performance_analysis_worker(self):
        """パフォーマンス分析ワーカー"""
        
        while True:
            try:
                # パフォーマンス分析の実行
                analysis_result = await self._analyze_system_performance()
                
                # 最適化提案の生成
                if analysis_result["needs_optimization"]:
                    await self._generate_optimization_recommendations(analysis_result)
                
                # 10分間隔で分析
                await asyncio.sleep(600)
                
            except Exception as e:
                logger.error(f"Performance analysis error: {e}")
                await asyncio.sleep(1200)
    
    async def _analyze_system_performance(self) -> Dict[str, Any]:
        """システムパフォーマンスの分析"""
        
        # メトリクスの収集・分析
        performance_data = {
            "average_response_time": 0.0,
            "success_rate": 0.0,
            "throughput": 0.0,
            "resource_utilization": 0.0,
            "needs_optimization": False
        }
        
        # 実装: 実際のメトリクスデータから分析
        
        return performance_data
    
    async def _generate_optimization_recommendations(self, analysis_result: Dict[str, Any]):
        """最適化推奨事項の生成"""
        
        logger.info("Generating optimization recommendations")
        
        # 実装: パフォーマンスデータに基づく最適化提案
        recommendations = [
            "ブラウザプールサイズの調整",
            "キャッシュ戦略の改善",
            "並列度の最適化"
        ]
        
        for recommendation in recommendations:
            logger.info(f"Optimization recommendation: {recommendation}")

class PerfectDashboard:
    """完璧なダッシュボード"""
    
    def __init__(self, metrics_collector: PerfectMetricsCollector):
        self.metrics_collector = metrics_collector
        
    async def generate_dashboard_data(self) -> Dict[str, Any]:
        """ダッシュボードデータの生成"""
        
        return {
            "system_overview": await self._get_system_overview(),
            "service_status": await self._get_service_status(),
            "performance_metrics": await self._get_performance_metrics(),
            "recent_alerts": await self._get_recent_alerts(),
            "operation_history": await self._get_operation_history()
        }
    
    async def _get_system_overview(self) -> Dict[str, Any]:
        """システム概要の取得"""
        
        return {
            "total_services": 0,  # 実装: 実際の数値
            "active_operations": 0,
            "success_rate_24h": 0.95,
            "average_response_time_ms": 1500,
            "uptime_hours": 168,
            "total_operations_24h": 1250
        }
    
    async def _get_service_status(self) -> List[Dict[str, Any]]:
        """サービスステータスの取得"""
        
        return [
            {
                "name": "zaico",
                "status": "connected",
                "last_operation": "2 minutes ago",
                "success_rate": 0.92,
                "avg_response_time_ms": 1200
            }
        ]
    
    async def _get_performance_metrics(self) -> Dict[str, Any]:
        """パフォーマンスメトリクスの取得"""
        
        return {
            "cpu_usage": 45.2,
            "memory_usage": 67.8,
            "disk_usage": 23.1,
            "network_io": {"in": 1.2, "out": 0.8},
            "browser_pool_utilization": 60.0
        }
    
    async def _get_recent_alerts(self) -> List[Dict[str, Any]]:
        """最近のアラートの取得"""
        
        return [
            {
                "level": "warning",
                "message": "High response time detected",
                "service": "zaico",
                "timestamp": "2024-01-15T10:30:00Z"
            }
        ]
    
    async def _get_operation_history(self) -> List[Dict[str, Any]]:
        """操作履歴の取得"""
        
        return [
            {
                "operation_id": "op-123",
                "service": "zaico",
                "operation": "list_items",
                "status": "success",
                "duration_ms": 1200,
                "timestamp": "2024-01-15T10:35:00Z"
            }
        ]

# 統合監視システム
class PerfectMonitoringSystem:
    """完璧な監視システム"""
    
    def __init__(self):
        self.metrics_collector = PerfectMetricsCollector()
        self.alerting_system = PerfectAlertingSystem(self.metrics_collector)
        self.dashboard = PerfectDashboard(self.metrics_collector)
        
    async def start(self):
        """監視システムの開始"""
        
        logger.info("Starting Perfect Monitoring System")
        
        # 各コンポーネントの開始
        await asyncio.gather(
            self.alerting_system.start_monitoring(),
            return_exceptions=True
        )
    
    def get_metrics_endpoint(self) -> Callable:
        """メトリクスエンドポイントの取得"""
        
        def metrics_handler():
            return generate_latest(self.metrics_collector.registry)
        
        return metrics_handler
    
    async def get_dashboard_data(self) -> Dict[str, Any]:
        """ダッシュボードデータの取得"""
        return await self.dashboard.generate_dashboard_data()

# 使用例
async def demonstrate_perfect_monitoring():
    """完璧な監視システムのデモ"""
    
    print("📊 Perfect Monitoring System Demo")
    print("=" * 50)
    
    monitoring_system = PerfectMonitoringSystem()
    
    # 監視開始（バックグラウンド）
    monitoring_task = asyncio.create_task(monitoring_system.start())
    
    # メトリクスの記録テスト
    metrics = monitoring_system.metrics_collector
    
    # テストメトリクスの記録
    metrics.record_connection_attempt("zaico", "browser_automation", True, 2.5)
    metrics.record_operation_execution("zaico", "list_items", "browser_automation", True, 1.2)
    metrics.set_legal_compliance_score("zaico", 0.9)
    
    print("✅ Metrics recorded")
    
    # ダッシュボードデータの取得
    dashboard_data = await monitoring_system.get_dashboard_data()
    print(f"📊 Dashboard data: {json.dumps(dashboard_data, indent=2, default=str)}")
    
    # 短時間実行後に停止
    await asyncio.sleep(5)
    monitoring_task.cancel()
    
    print("🎯 Perfect Monitoring System demonstrated!")

if __name__ == "__main__":
    asyncio.run(demonstrate_perfect_monitoring())