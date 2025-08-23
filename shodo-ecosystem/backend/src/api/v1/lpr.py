"""
LPR (Limited Proxy Rights) API エンドポイント

LPRトークンの発行、検証、失効、ステータス確認のAPIを提供。
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Body, Query
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field, validator
import structlog

from ...services.auth.lpr_service import (
    get_lpr_service,
    LPRScope,
    LPRPolicy,
    DeviceFingerprint,
)
from ...services.auth.visible_login import (
    visible_login_detector,
    secure_session_storage,
    LoginDetectionRule,
)
from ...services.audit.audit_logger import (
    audit_logger,
    AuditEventType,
    AuditSeverity,
)
from ...middleware.auth import get_current_user
from ...schemas.base import BaseResponse, error_response

# 構造化ログ
logger = structlog.get_logger()

# APIルーター
router = APIRouter(prefix="/api/v1/lpr", tags=["LPR"])

# セキュリティ
security = HTTPBearer()

# ===== リクエスト/レスポンスモデル =====

class VisibleLoginRequest(BaseModel):
    """可視ログインリクエスト"""
    service_name: str = Field(..., description="対象サービス名")
    login_url: str = Field(..., description="ログインURL")
    auto_fill: Optional[Dict[str, str]] = Field(None, description="自動入力フィールド")
    custom_rules: Optional[List[Dict[str, Any]]] = Field(None, description="カスタム検知ルール")
    timeout: int = Field(default=120, ge=30, le=300, description="タイムアウト（秒）")

class LPRIssueRequest(BaseModel):
    """LPR発行リクエスト"""
    session_id: str = Field(..., description="可視ログインのセッションID")
    scopes: List[Dict[str, str]] = Field(..., description="要求スコープ")
    origins: List[str] = Field(..., description="許可オリジン")
    ttl_seconds: int = Field(default=3600, ge=300, le=86400, description="有効期限（秒）")
    policy: Optional[Dict[str, Any]] = Field(None, description="ポリシー設定")
    device_fingerprint: Dict[str, Any] = Field(..., description="デバイス指紋")
    purpose: str = Field(..., description="利用目的")
    consent: bool = Field(..., description="ユーザー同意")
    
    @validator('consent')
    def validate_consent(cls, v):
        if not v:
            raise ValueError("User consent is required")
        return v

class LPRRevokeRequest(BaseModel):
    """LPR失効リクエスト"""
    jti: str = Field(..., description="トークンID")
    reason: str = Field(..., description="失効理由")

class LPRVerifyRequest(BaseModel):
    """LPR検証リクエスト"""
    token: str = Field(..., description="LPRトークン")
    request_method: str = Field(..., description="リクエストメソッド")
    request_url: str = Field(..., description="リクエストURL")
    request_origin: str = Field(..., description="リクエストオリジン")
    device_fingerprint: Optional[Dict[str, Any]] = Field(None, description="デバイス指紋")

class LPRIssueResponse(BaseModel):
    """LPR発行レスポンス"""
    success: bool
    token: Optional[str] = None
    jti: Optional[str] = None
    expires_at: Optional[datetime] = None
    scopes: Optional[List[Dict[str, str]]] = None
    error: Optional[str] = None

class LPRTokenData(BaseModel):
    """LPRトークンデータ (BaseResponse用)"""
    token: str
    jti: str
    expires_at: Optional[str] = None
    scopes: List[Dict[str, str]] = []

class LPRVerifyData(BaseModel):
    """LPR検証結果データ (BaseResponse用)"""
    valid: bool
    jti: Optional[str] = None
    service: Optional[str] = None
    scopes: Optional[List[Dict[str, str]]] = None
    # 追加で必要なら subject などを拡張可能

class LPRStatusResponse(BaseModel):
    """LPRステータスレスポンス"""
    jti: str
    status: str
    issued_at: Optional[str] = None
    expires_at: Optional[str] = None
    subject: Optional[str] = None
    scopes: Optional[int] = None
    remaining_ttl: Optional[int] = None

class VisibleLoginResponse(BaseModel):
    """可視ログインレスポンス"""
    success: bool
    session_id: Optional[str] = None
    confidence: Optional[float] = None
    method: Optional[str] = None
    error: Optional[str] = None

# ===== エンドポイント =====

@router.post("/visible-login", response_model=VisibleLoginResponse)
async def start_visible_login(
    request: Request,
    body: VisibleLoginRequest,
    current_user: Dict = Depends(get_current_user),
) -> VisibleLoginResponse:
    """可視ログインを開始"""
    
    try:
        # カスタムルールの変換
        custom_rules = None
        if body.custom_rules:
            custom_rules = [
                LoginDetectionRule(**rule)
                for rule in body.custom_rules
            ]
        
        # 可視ログインの実行
        result = await visible_login_detector.detect_login(
            login_url=body.login_url,
            service_name=body.service_name,
            timeout=body.timeout,
            auto_fill=body.auto_fill,
            custom_rules=custom_rules,
        )
        
        if result.success:
            # セッションを一時保存
            session_id = await secure_session_storage.store_session(
                user_id=current_user["sub"],
                cookies=result.cookies,
                ttl_seconds=300,  # 5分間有効
            )
            
            # 監査ログ
            await audit_logger.log(
                event_type=AuditEventType.LOGIN_SUCCESS,
                who=current_user["sub"],
                what=body.service_name,
                where="visible_login",
                why=f"Service: {body.service_name}",
                how="playwright",
                result="success",
                details={
                    "confidence": result.confidence,
                    "method": result.method,
                    "session_id": session_id,
                }
            )
            
            return VisibleLoginResponse(
                success=True,
                session_id=session_id,
                confidence=result.confidence,
                method=result.method,
            )
        else:
            # 監査ログ
            await audit_logger.log(
                event_type=AuditEventType.LOGIN_FAILURE,
                who=current_user["sub"],
                what=body.service_name,
                where="visible_login",
                why=f"Service: {body.service_name}",
                how="playwright",
                result="failure",
                details={
                    "error": result.error_message,
                }
            )
            
            return VisibleLoginResponse(
                success=False,
                error=result.error_message,
            )
    
    except Exception as e:
        logger.error("Visible login failed", error=str(e))
        
        await audit_logger.log(
            event_type=AuditEventType.ERROR,
            who=current_user["sub"],
            what="visible_login",
            where="visible_login",
            result="error",
            severity=AuditSeverity.ERROR,
            details={"error": str(e)}
        )
        
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/issue", response_model=BaseResponse[LPRTokenData])
async def issue_lpr_token(
    request: Request,
    body: LPRIssueRequest,
    current_user: Dict = Depends(get_current_user),
) -> BaseResponse[LPRTokenData]:
    """LPRトークンを発行"""
    
    try:
        # セッションの検証
        session = await secure_session_storage.retrieve_session(body.session_id)
        if not session:
            return error_response(
                code="LPR_SESSION_INVALID",
                message="Invalid or expired session"
            )
        
        # セッションのユーザーと一致するか確認
        if session["user_id"] != current_user["sub"]:
            return error_response(
                code="LPR_SESSION_USER_MISMATCH",
                message="Session user mismatch"
            )
        
        # スコープの変換
        scopes = [
            LPRScope(
                method=scope["method"],
                url_pattern=scope["url_pattern"],
                # description は LPRScope に存在しないため除外
            )
            for scope in body.scopes
        ]
        
        # ポリシーの変換
        policy = None
        if body.policy:
            policy = LPRPolicy(**body.policy)
        
        # デバイス指紋の変換
        device_fingerprint = DeviceFingerprint(**body.device_fingerprint)
        
        # LPRトークンの発行
        lpr_service = await get_lpr_service()
        result = await lpr_service.issue_token(
            user_id=current_user["sub"],
            device_fingerprint=device_fingerprint,
            scopes=scopes,
            service=body.origins[0] if body.origins else "frontend",
            purpose=body.purpose,
            consent=body.consent,
            policy=policy,
        )
        
        # セッションを削除（1回限りの使用）
        await secure_session_storage.delete_session(body.session_id)
        
        # 監査ログ
        await audit_logger.log(
            event_type=AuditEventType.LPR_ISSUED,
            who=current_user["sub"],
            what=f"LPR:{result['jti']}",
            where="lpr_issue",
            why=body.purpose,
            how="api",
            result="success",
            correlation_id=result.get("correlation_id"),
            details={
                "jti": result['jti'],
                "scopes": len(scopes),
                "origins": body.origins,
                "ttl": 3600,
                "consent": body.consent,
            }
        )
        
        return BaseResponse[LPRTokenData](
            success=True,
            data=LPRTokenData(
                token=result['token'],
                jti=result['jti'],
                expires_at=result.get('expires_at'),
                scopes=body.scopes,
            )
        )
    
    except Exception as e:
        logger.error("LPR token issuance failed", error=str(e))
        
        await audit_logger.log(
            event_type=AuditEventType.ERROR,
            who=current_user["sub"],
            what="lpr_issue",
            where="lpr_issue",
            result="error",
            severity=AuditSeverity.ERROR,
            details={"error": str(e)}
        )
        
        return error_response(code="LPR_ISSUE_FAILED", message=str(e))

@router.post("/verify", response_model=BaseResponse[LPRVerifyData])
async def verify_lpr_token(
    request: Request,
    body: LPRVerifyRequest,
) -> BaseResponse[LPRVerifyData]:
    """LPRトークンを検証"""
    
    try:
        # デバイス指紋の変換
        device_fingerprint = None
        if body.device_fingerprint:
            device_fingerprint = DeviceFingerprint(**body.device_fingerprint)
        
        # トークン検証
        lpr_service = await get_lpr_service()
        verification = await lpr_service.verify_token(
            token=body.token,
            device_fingerprint=device_fingerprint,
            required_scope=LPRScope(body.request_method, body.request_url),
        )
        
        if verification.get("valid"):
            # 監査ログ
            await audit_logger.log(
                event_type=AuditEventType.LPR_VERIFIED,
                who=verification.get("user_id"),
                what=f"LPR:{verification.get('jti')}",
                where="lpr_verify",
                how="api",
                result="success",
                correlation_id=verification.get("correlation_id"),
                details={
                    "method": body.request_method,
                    "url": body.request_url,
                }
            )
            
            return BaseResponse[LPRVerifyData](
                success=True,
                data=LPRVerifyData(
                    valid=True,
                    jti=verification.get("jti"),
                    service=verification.get("service"),
                    scopes=verification.get("scopes"),
                ),
                correlation_id=verification.get("correlation_id")
            )
        else:
            # 監査ログ
            await audit_logger.log(
                event_type=AuditEventType.LPR_INVALID,
                who="unknown",
                what="lpr_verify",
                where="lpr_verify",
                how="api",
                result="failure",
                severity=AuditSeverity.WARNING,
                details={
                    "error": verification.get("error"),
                    "method": body.request_method,
                    "url": body.request_url,
                }
            )
            
            return error_response(
                code="LPR_VERIFICATION_FAILED",
                message=verification.get("error", "Verification failed")
            )
    
    except Exception as e:
        logger.error("LPR token verification failed", error=str(e))
        return error_response(code="LPR_VERIFY_ERROR", message=str(e))

@router.post("/revoke", response_model=BaseResponse[Dict[str, Any]])
async def revoke_lpr_token(
    request: Request,
    body: LPRRevokeRequest,
    current_user: Dict = Depends(get_current_user),
) -> BaseResponse[Dict[str, Any]]:
    """LPRトークンを失効"""
    
    try:
        # トークンの失効
        lpr_service = await get_lpr_service()
        success = await lpr_service.revoke_token(
            jti=body.jti,
            reason=body.reason,
            user_id=current_user["sub"],
        )
        
        if success:
            # 監査ログ
            await audit_logger.log(
                event_type=AuditEventType.LPR_REVOKED,
                who=current_user["sub"],
                what=f"LPR:{body.jti}",
                where="lpr_revoke",
                why=body.reason,
                how="api",
                result="success",
                details={
                    "jti": body.jti,
                    "reason": body.reason,
                }
            )
            
            return BaseResponse(success=True, data={"message": f"Token {body.jti} has been revoked"})
        else:
            return error_response(code="LPR_REVOKE_FAILED", message="Failed to revoke token")
    
    except Exception as e:
        logger.error("LPR token revocation failed", error=str(e))
        
        await audit_logger.log(
            event_type=AuditEventType.ERROR,
            who=current_user["sub"],
            what="lpr_revoke",
            where="lpr_revoke",
            result="error",
            severity=AuditSeverity.ERROR,
            details={"error": str(e)}
        )
        
        return error_response(code="LPR_REVOKE_ERROR", message=str(e))

@router.get("/status/{jti}", response_model=LPRStatusResponse)
async def get_lpr_status(
    jti: str,
    current_user: Dict = Depends(get_current_user),
) -> LPRStatusResponse:
    """LPRトークンのステータスを取得"""
    
    try:
        # ステータス取得
        lpr_service = await get_lpr_service()
        status = await lpr_service.get_token_status(jti)
        
        # 残りTTLの計算
        remaining_ttl = None
        if status.get("expires_at"):
            expires_at = datetime.fromisoformat(status["expires_at"])
            remaining = expires_at - datetime.now(timezone.utc)
            remaining_ttl = max(0, int(remaining.total_seconds()))
        
        return LPRStatusResponse(
            jti=jti,
            status=status["status"],
            issued_at=status.get("issued_at"),
            expires_at=status.get("expires_at"),
            subject=status.get("subject"),
            scopes=status.get("scopes"),
            remaining_ttl=remaining_ttl,
        )
    
    except Exception as e:
        logger.error("Failed to get LPR status", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list")
async def list_lpr_tokens(
    current_user: Dict = Depends(get_current_user),
    active_only: bool = Query(True, description="アクティブなトークンのみ"),
    limit: int = Query(100, ge=1, le=1000, description="取得件数"),
) -> Dict[str, Any]:
    """ユーザーのLPRトークン一覧を取得"""
    
    try:
        # TODO: ユーザーのトークン一覧を取得する実装
        # 現在は簡略化のためダミーデータを返す
        
        return {
            "tokens": [],
            "total": 0,
            "active": 0,
            "revoked": 0,
        }
    
    except Exception as e:
        logger.error("Failed to list LPR tokens", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/batch-revoke")
async def batch_revoke_tokens(
    request: Request,
    jtis: List[str] = Body(..., description="失効するトークンIDのリスト"),
    reason: str = Body(..., description="失効理由"),
    current_user: Dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """複数のLPRトークンを一括失効"""
    
    try:
        results = []
        
        lpr = await get_lpr_service()
        for jti in jtis:
            success = await lpr.revoke_token(
                jti=jti,
                reason=reason,
                user_id=current_user["sub"],
            )
            results.append({
                "jti": jti,
                "revoked": success,
            })
        
        # 監査ログ
        await audit_logger.log(
            event_type=AuditEventType.LPR_REVOKED,
            who=current_user["sub"],
            what="batch_revoke",
            where="lpr_batch_revoke",
            why=reason,
            how="api",
            result="success",
            details={
                "count": len(jtis),
                "jtis": jtis,
                "reason": reason,
            }
        )
        
        revoked_count = sum(1 for r in results if r["revoked"])
        
        return {
            "success": True,
            "total": len(jtis),
            "revoked": revoked_count,
            "failed": len(jtis) - revoked_count,
            "results": results,
        }
    
    except Exception as e:
        logger.error("Batch revocation failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/audit-log")
async def get_audit_log(
    current_user: Dict = Depends(get_current_user),
    event_type: Optional[str] = Query(None, description="イベントタイプ"),
    correlation_id: Optional[str] = Query(None, description="相関ID"),
    limit: int = Query(100, ge=1, le=1000, description="取得件数"),
) -> Dict[str, Any]:
    """LPR関連の監査ログを取得"""
    
    try:
        # 管理者権限チェック（簡略化）
        # if "admin" not in current_user.get("roles", []):
        #     raise HTTPException(status_code=403, detail="Admin access required")
        
        # 監査ログの検索
        event_type_enum = None
        if event_type:
            event_type_enum = AuditEventType(event_type)
        
        entries = await audit_logger.search(
            event_type=event_type_enum,
            correlation_id=correlation_id,
            limit=limit,
        )
        
        # 結果の整形
        logs = []
        for entry in entries:
            logs.append({
                "when": entry.when.isoformat(),
                "who": entry.who,
                "what": entry.what,
                "where": entry.where,
                "event_type": entry.event_type.value,
                "severity": entry.severity.value,
                "result": entry.result,
                "correlation_id": entry.correlation_id,
                "details": entry.details,
            })
        
        return {
            "logs": logs,
            "count": len(logs),
        }
    
    except Exception as e:
        logger.error("Failed to get audit log", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))