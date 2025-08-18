"""
構造化ログシステム
JSON形式での構造化ログ、相関ID、パフォーマンス計測
"""

import logging
import json
import sys
import time
import traceback
from datetime import datetime
from typing import Any, Dict, Optional, Union
from contextvars import ContextVar
from functools import wraps
import uuid

from pythonjsonlogger import jsonlogger

# コンテキスト変数（リクエスト間で独立）
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
session_id_var: ContextVar[Optional[str]] = ContextVar('session_id', default=None)

class StructuredLogger:
    """構造化ログクラス"""
    
    def __init__(self, name: str, level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # 既存のハンドラーをクリア
        self.logger.handlers = []
        
        # JSONフォーマッターの設定
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s'
        )
        
        # コンソールハンドラー
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # ファイルハンドラー（本番環境用）
        # file_handler = logging.FileHandler('/var/log/shodo/app.log')
        # file_handler.setFormatter(formatter)
        # self.logger.addHandler(file_handler)
    
    def _add_context(self, extra: Dict[str, Any]) -> Dict[str, Any]:
        """コンテキスト情報の追加"""
        context = {
            'request_id': request_id_var.get(),
            'user_id': user_id_var.get(),
            'session_id': session_id_var.get(),
            'timestamp': datetime.utcnow().isoformat(),
        }
        
        # extraの内容をマージ
        if extra:
            context.update(extra)
        
        return {'extra': context}
    
    def debug(self, message: str, **kwargs):
        """デバッグログ"""
        self.logger.debug(message, **self._add_context(kwargs))
    
    def info(self, message: str, **kwargs):
        """情報ログ"""
        self.logger.info(message, **self._add_context(kwargs))
    
    def warning(self, message: str, **kwargs):
        """警告ログ"""
        self.logger.warning(message, **self._add_context(kwargs))
    
    def error(self, message: str, error: Optional[Exception] = None, **kwargs):
        """エラーログ"""
        if error:
            kwargs['error_type'] = type(error).__name__
            kwargs['error_message'] = str(error)
            kwargs['stacktrace'] = traceback.format_exc()
        
        self.logger.error(message, **self._add_context(kwargs))
    
    def critical(self, message: str, error: Optional[Exception] = None, **kwargs):
        """クリティカルログ"""
        if error:
            kwargs['error_type'] = type(error).__name__
            kwargs['error_message'] = str(error)
            kwargs['stacktrace'] = traceback.format_exc()
        
        self.logger.critical(message, **self._add_context(kwargs))
    
    def audit(self, action: str, resource: str, **kwargs):
        """監査ログ"""
        audit_data = {
            'audit': True,
            'action': action,
            'resource': resource,
            'timestamp': datetime.utcnow().isoformat(),
        }
        audit_data.update(kwargs)
        
        self.logger.info(f"AUDIT: {action} on {resource}", **self._add_context(audit_data))
    
    def performance(self, operation: str, duration_ms: float, **kwargs):
        """パフォーマンスログ"""
        perf_data = {
            'performance': True,
            'operation': operation,
            'duration_ms': duration_ms,
        }
        perf_data.update(kwargs)
        
        level = logging.INFO
        if duration_ms > 1000:  # 1秒以上は警告
            level = logging.WARNING
        elif duration_ms > 5000:  # 5秒以上はエラー
            level = logging.ERROR
        
        self.logger.log(
            level,
            f"Performance: {operation} took {duration_ms:.2f}ms",
            **self._add_context(perf_data)
        )

class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """カスタムJSONフォーマッター"""
    
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        
        # タイムスタンプの追加
        log_record['timestamp'] = datetime.utcnow().isoformat()
        
        # レベル名の追加
        log_record['level'] = record.levelname
        
        # モジュール情報の追加
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno
        
        # プロセス/スレッド情報
        log_record['process_id'] = record.process
        log_record['thread_id'] = record.thread
        
        # extraフィールドの展開
        if hasattr(record, 'extra'):
            for key, value in record.extra.items():
                log_record[key] = value

class LogContext:
    """ログコンテキストマネージャー"""
    
    def __init__(self, **kwargs):
        self.context = kwargs
        self.tokens = []
    
    def __enter__(self):
        # コンテキスト変数を設定
        if 'request_id' in self.context:
            token = request_id_var.set(self.context['request_id'])
            self.tokens.append(token)
        
        if 'user_id' in self.context:
            token = user_id_var.set(self.context['user_id'])
            self.tokens.append(token)
        
        if 'session_id' in self.context:
            token = session_id_var.set(self.context['session_id'])
            self.tokens.append(token)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # コンテキスト変数をリセット
        for token in self.tokens:
            request_id_var.reset(token)

def log_execution_time(logger: Optional[StructuredLogger] = None):
    """実行時間計測デコレータ"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            _logger = logger or get_logger(func.__module__)
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                _logger.performance(
                    operation=f"{func.__module__}.{func.__name__}",
                    duration_ms=duration_ms,
                    args_count=len(args),
                    kwargs_count=len(kwargs)
                )
                
                return result
            
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                _logger.error(
                    f"Error in {func.__name__}",
                    error=e,
                    operation=f"{func.__module__}.{func.__name__}",
                    duration_ms=duration_ms
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            _logger = logger or get_logger(func.__module__)
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                _logger.performance(
                    operation=f"{func.__module__}.{func.__name__}",
                    duration_ms=duration_ms,
                    args_count=len(args),
                    kwargs_count=len(kwargs)
                )
                
                return result
            
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                _logger.error(
                    f"Error in {func.__name__}",
                    error=e,
                    operation=f"{func.__module__}.{func.__name__}",
                    duration_ms=duration_ms
                )
                raise
        
        # 非同期関数か同期関数かを判定
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def log_api_call(logger: Optional[StructuredLogger] = None):
    """API呼び出しログデコレータ"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            _logger = logger or get_logger(func.__module__)
            
            # リクエスト情報の取得（FastAPIのRequestオブジェクトを想定）
            request = None
            for arg in args:
                if hasattr(arg, 'method') and hasattr(arg, 'url'):
                    request = arg
                    break
            
            # リクエストIDの生成
            request_id = str(uuid.uuid4())
            request_id_var.set(request_id)
            
            # APIコール開始ログ
            _logger.info(
                f"API call started: {func.__name__}",
                api_endpoint=func.__name__,
                method=request.method if request else None,
                path=str(request.url.path) if request else None,
                query_params=dict(request.query_params) if request else None
            )
            
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # APIコール成功ログ
                _logger.info(
                    f"API call completed: {func.__name__}",
                    api_endpoint=func.__name__,
                    duration_ms=duration_ms,
                    status_code=getattr(result, 'status_code', 200)
                )
                
                return result
            
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                # APIコールエラーログ
                _logger.error(
                    f"API call failed: {func.__name__}",
                    error=e,
                    api_endpoint=func.__name__,
                    duration_ms=duration_ms
                )
                raise
        
        return wrapper
    
    return decorator

# ロガーのシングルトンインスタンス管理
_loggers: Dict[str, StructuredLogger] = {}

def get_logger(name: str = __name__, level: str = "INFO") -> StructuredLogger:
    """ロガーの取得"""
    if name not in _loggers:
        _loggers[name] = StructuredLogger(name, level)
    return _loggers[name]

def configure_logging(
    level: str = "INFO",
    format: str = "json",
    output: str = "console"
):
    """ログ設定の初期化"""
    # ルートロガーの設定
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # 既存のハンドラーをクリア
    root_logger.handlers = []
    
    # フォーマッターの選択
    if format == "json":
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(name)s %(message)s'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    # ハンドラーの設定
    if output == "console":
        handler = logging.StreamHandler(sys.stdout)
    else:
        handler = logging.FileHandler(output)
    
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # サードパーティライブラリのログレベル調整
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

# デフォルトロガー
logger = get_logger(__name__)