"""
メトリクス収集モジュール
"""

from typing import Dict, Any
from functools import wraps
import time
from datetime import datetime

# メトリクス格納用辞書
metrics_data = {
    "http_requests_total": {},
    "http_request_duration_seconds": [],
    "active_users": 0,
    "api_calls_total": {},
    "nlp_processing_time": [],
    "cache_hits": 0,
    "cache_misses": 0,
}

def track_request(method: str, endpoint: str):
    """リクエストトラッキングデコレータ"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            key = f"{method}_{endpoint}"
            
            # リクエストカウント
            if key not in metrics_data["http_requests_total"]:
                metrics_data["http_requests_total"][key] = 0
            metrics_data["http_requests_total"][key] += 1
            
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                # 処理時間記録
                duration = time.time() - start_time
                metrics_data["http_request_duration_seconds"].append({
                    "method": method,
                    "endpoint": endpoint,
                    "duration": duration,
                    "timestamp": datetime.utcnow()
                })
                
                # 古いデータを削除（メモリ節約）
                if len(metrics_data["http_request_duration_seconds"]) > 1000:
                    metrics_data["http_request_duration_seconds"] = metrics_data["http_request_duration_seconds"][-1000:]
        
        return wrapper
    return decorator

def increment_cache_hits():
    """キャッシュヒット数増加"""
    metrics_data["cache_hits"] += 1

def increment_cache_misses():
    """キャッシュミス数増加"""
    metrics_data["cache_misses"] += 1

def set_active_users(count: int):
    """アクティブユーザー数設定"""
    metrics_data["active_users"] = count

def track_nlp_processing(processing_time: float, analysis_type: str):
    """NLP処理時間記録"""
    metrics_data["nlp_processing_time"].append({
        "time": processing_time,
        "type": analysis_type,
        "timestamp": datetime.utcnow()
    })
    
    # 古いデータを削除
    if len(metrics_data["nlp_processing_time"]) > 1000:
        metrics_data["nlp_processing_time"] = metrics_data["nlp_processing_time"][-1000:]

def get_metrics() -> str:
    """Prometheus形式でメトリクス取得"""
    lines = []
    
    # HTTPリクエスト数
    lines.append("# TYPE http_requests_total counter")
    for key, value in metrics_data["http_requests_total"].items():
        lines.append(f'http_requests_total{{endpoint="{key}"}} {value}')
    
    # アクティブユーザー数
    lines.append("# TYPE active_users gauge")
    lines.append(f'active_users {metrics_data["active_users"]}')
    
    # キャッシュヒット率
    lines.append("# TYPE cache_hits_total counter")
    lines.append(f'cache_hits_total {metrics_data["cache_hits"]}')
    
    lines.append("# TYPE cache_misses_total counter")
    lines.append(f'cache_misses_total {metrics_data["cache_misses"]}')
    
    # 平均処理時間
    if metrics_data["http_request_duration_seconds"]:
        avg_duration = sum(d["duration"] for d in metrics_data["http_request_duration_seconds"]) / len(metrics_data["http_request_duration_seconds"])
        lines.append("# TYPE http_request_duration_seconds_avg gauge")
        lines.append(f'http_request_duration_seconds_avg {avg_duration:.3f}')
    
    return "\n".join(lines)

def get_metrics_json() -> Dict[str, Any]:
    """JSON形式でメトリクス取得"""
    return {
        "http_requests": metrics_data["http_requests_total"],
        "active_users": metrics_data["active_users"],
        "cache": {
            "hits": metrics_data["cache_hits"],
            "misses": metrics_data["cache_misses"],
            "hit_rate": metrics_data["cache_hits"] / max(1, metrics_data["cache_hits"] + metrics_data["cache_misses"])
        },
        "average_response_time": sum(d["duration"] for d in metrics_data["http_request_duration_seconds"][-100:]) / max(1, len(metrics_data["http_request_duration_seconds"][-100:])) if metrics_data["http_request_duration_seconds"] else 0
    }