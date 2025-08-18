"""
プレビューAPIエンドポイント
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from typing import List, Optional
import uuid
from datetime import datetime, timedelta

from ...schemas.preview import (
    PreviewRequest, PreviewResponse, PreviewData,
    RefinementRequest, ApplyRequest, ApplyResponse,
    RollbackRequest, RollbackResponse, PreviewHistory,
    PreviewSession, Change, ChangeType, ApprovalStatus
)
from ...schemas.common import BaseResponse, PaginatedResponse, PaginationParams, StatusEnum
from ...core.security import JWTManager, TokenData, security, limiter, InputSanitizer
from ...services.preview.sandbox_engine import SandboxPreviewEngine

router = APIRouter()

# エンジンのインスタンス
preview_engine = SandboxPreviewEngine()

@router.post("/generate", response_model=BaseResponse[PreviewResponse])
@limiter.limit("20/minute")
async def generate_preview(
    request: PreviewRequest,
    background_tasks: BackgroundTasks,
    token_data: TokenData = Depends(JWTManager.verify_token)
):
    """
    プレビュー生成
    
    指定された変更内容でプレビューを生成します。
    """
    try:
        # セッションIDの生成または使用
        session_id = request.session_id or str(uuid.uuid4())
        preview_id = str(uuid.uuid4())
        
        # 変更内容のサニタイズ
        sanitized_modifications = InputSanitizer.sanitize_json(request.modifications)
        
        # プレビューの生成
        preview_data = await preview_engine.generate_preview(
            source_type=request.source_type,
            source_id=request.source_id,
            modifications=sanitized_modifications,
            target_element=request.target_element
        )
        
        # プレビューデータの作成
        preview = PreviewData(
            preview_id=preview_id,
            version=1,
            html=InputSanitizer.sanitize_html(preview_data.get("html", "")),
            css=preview_data.get("css", ""),
            javascript=preview_data.get("javascript", ""),
            changes=preview_data.get("changes", []),
            confidence=preview_data.get("confidence", 0.8),
            metadata=preview_data.get("metadata", {}),
            created_at=datetime.utcnow()
        )
        
        response = PreviewResponse(
            session_id=session_id,
            preview_id=preview_id,
            status=StatusEnum.COMPLETED,
            preview_data=preview,
            preview_url=f"/api/v1/preview/view/{preview_id}",
            expires_at=datetime.utcnow() + timedelta(hours=24),
            can_apply=True,
            warnings=preview_data.get("warnings", [])
        )
        
        # バックグラウンドでセッション統計を更新
        background_tasks.add_task(
            update_preview_session,
            session_id,
            token_data.user_id
        )
        
        return BaseResponse(
            success=True,
            data=response,
            request_id=preview_id
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview generation failed: {str(e)}")

@router.post("/refine", response_model=BaseResponse[PreviewResponse])
@limiter.limit("30/minute")
async def refine_preview(
    request: RefinementRequest,
    token_data: TokenData = Depends(JWTManager.verify_token)
):
    """
    プレビュー修正
    
    既存のプレビューを修正指示に基づいて更新します。
    """
    try:
        # 既存のプレビューを取得
        existing_preview = await preview_engine.get_preview(request.preview_id)
        if not existing_preview:
            raise HTTPException(status_code=404, detail="Preview not found")
        
        # 修正指示のサニタイズ
        sanitized_refinement = InputSanitizer.validate_prompt(request.refinement_text)
        
        # 修正の適用
        refined_data = await preview_engine.apply_refinement(
            preview_id=request.preview_id,
            refinement_text=sanitized_refinement,
            keep_history=request.keep_history
        )
        
        # 新しいバージョンの作成
        new_version = existing_preview.version + 1
        preview = PreviewData(
            preview_id=request.preview_id,
            version=new_version,
            html=InputSanitizer.sanitize_html(refined_data.get("html", "")),
            css=refined_data.get("css", ""),
            javascript=refined_data.get("javascript", ""),
            changes=refined_data.get("changes", []),
            confidence=refined_data.get("confidence", 0.85),
            metadata=refined_data.get("metadata", {}),
            created_at=datetime.utcnow()
        )
        
        response = PreviewResponse(
            session_id=existing_preview.session_id,
            preview_id=request.preview_id,
            status=StatusEnum.COMPLETED,
            preview_data=preview,
            preview_url=f"/api/v1/preview/view/{request.preview_id}",
            expires_at=datetime.utcnow() + timedelta(hours=24),
            can_apply=True,
            warnings=refined_data.get("warnings", [])
        )
        
        return BaseResponse(
            success=True,
            data=response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refinement failed: {str(e)}")

@router.post("/apply", response_model=BaseResponse[ApplyResponse])
@limiter.limit("5/minute")
async def apply_preview(
    request: ApplyRequest,
    background_tasks: BackgroundTasks,
    token_data: TokenData = Depends(JWTManager.verify_token)
):
    """
    プレビュー適用
    
    プレビューを本番環境に適用します。
    """
    try:
        # プレビューの取得
        preview = await preview_engine.get_preview(request.preview_id)
        if not preview:
            raise HTTPException(status_code=404, detail="Preview not found")
        
        # 承認チェック（必要に応じて）
        if request.approval_token:
            # TODO: 承認トークンの検証
            pass
        
        # ドライラン
        if request.dry_run:
            # 実際の適用はせず、シミュレーション結果を返す
            return BaseResponse(
                success=True,
                data=ApplyResponse(
                    apply_id=str(uuid.uuid4()),
                    status=ApprovalStatus.PENDING,
                    applied_changes=preview.changes,
                    rollback_id=None,
                    backup_id=str(uuid.uuid4()) if request.backup else None,
                    timestamp=datetime.utcnow()
                )
            )
        
        # バックアップの作成
        backup_id = None
        if request.backup:
            backup_id = await preview_engine.create_backup(
                preview_id=request.preview_id,
                target_environment=request.target_environment
            )
        
        # 実際の適用
        apply_result = await preview_engine.apply_to_production(
            preview_id=request.preview_id,
            target_environment=request.target_environment,
            user_id=token_data.user_id
        )
        
        apply_id = str(uuid.uuid4())
        
        # バックグラウンドで監査ログを記録
        background_tasks.add_task(
            log_apply_action,
            apply_id,
            request.preview_id,
            token_data.user_id
        )
        
        return BaseResponse(
            success=True,
            data=ApplyResponse(
                apply_id=apply_id,
                status=ApprovalStatus.APPLIED,
                applied_changes=apply_result.get("changes", []),
                rollback_id=apply_result.get("rollback_id"),
                backup_id=backup_id,
                timestamp=datetime.utcnow()
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Apply failed: {str(e)}")

@router.post("/rollback", response_model=BaseResponse[RollbackResponse])
@limiter.limit("5/minute")
async def rollback_preview(
    request: RollbackRequest,
    background_tasks: BackgroundTasks,
    token_data: TokenData = Depends(JWTManager.verify_token)
):
    """
    ロールバック
    
    適用済みの変更をロールバックします。
    """
    try:
        # ロールバックの実行
        rollback_result = await preview_engine.rollback(
            apply_id=request.apply_id,
            rollback_to=request.rollback_to,
            reason=request.reason,
            user_id=token_data.user_id
        )
        
        rollback_id = str(uuid.uuid4())
        
        # バックグラウンドで監査ログを記録
        background_tasks.add_task(
            log_rollback_action,
            rollback_id,
            request.apply_id,
            token_data.user_id,
            request.reason
        )
        
        return BaseResponse(
            success=True,
            data=RollbackResponse(
                rollback_id=rollback_id,
                status=StatusEnum.COMPLETED,
                rolled_back_changes=rollback_result.get("changes", []),
                timestamp=datetime.utcnow()
            )
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rollback failed: {str(e)}")

@router.get("/view/{preview_id}", response_class=HTMLResponse)
async def view_preview(
    preview_id: str,
    token_data: TokenData = Depends(JWTManager.verify_token)
):
    """
    プレビュー表示
    
    プレビューをHTML形式で表示します。
    """
    try:
        # プレビューの取得
        preview = await preview_engine.get_preview(preview_id)
        if not preview:
            raise HTTPException(status_code=404, detail="Preview not found")
        
        # サニタイズされたHTMLを生成
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Preview - {preview_id}</title>
            <style>
                {preview.css}
                
                /* プレビュー用の追加スタイル */
                .preview-banner {{
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    background: #4caf50;
                    color: white;
                    padding: 10px;
                    text-align: center;
                    z-index: 9999;
                }}
            </style>
        </head>
        <body>
            <div class="preview-banner">
                プレビューモード - ID: {preview_id} | Version: {preview.version}
            </div>
            <div style="margin-top: 50px;">
                {preview.html}
            </div>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_content)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview rendering failed: {str(e)}")

@router.get("/history/{preview_id}", response_model=BaseResponse[List[PreviewHistory]])
async def get_preview_history(
    preview_id: str,
    token_data: TokenData = Depends(JWTManager.verify_token)
):
    """
    プレビュー履歴取得
    
    プレビューのバージョン履歴を取得します。
    """
    # TODO: データベースから実際の履歴を取得
    history = await preview_engine.get_history(preview_id)
    
    return BaseResponse(
        success=True,
        data=history
    )

@router.get("/sessions", response_model=BaseResponse[PaginatedResponse[PreviewSession]])
async def get_preview_sessions(
    pagination: PaginationParams = Depends(),
    token_data: TokenData = Depends(JWTManager.verify_token)
):
    """
    プレビューセッション一覧
    
    ユーザーのプレビューセッション一覧を取得します。
    """
    # TODO: データベースから実際のセッションを取得
    mock_sessions = [
        PreviewSession(
            session_id=str(uuid.uuid4()),
            user_id=token_data.user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            preview_count=3,
            apply_count=1,
            rollback_count=0,
            metadata={}
        )
    ]
    
    response = PaginatedResponse(
        items=mock_sessions,
        total=1,
        page=pagination.page,
        per_page=pagination.per_page,
        pages=1,
        has_next=False,
        has_prev=False
    )
    
    return BaseResponse(
        success=True,
        data=response
    )

# ヘルパー関数
async def update_preview_session(session_id: str, user_id: str):
    """プレビューセッションの更新"""
    # TODO: データベースでセッション統計を更新
    pass

async def log_apply_action(apply_id: str, preview_id: str, user_id: str):
    """適用アクションのログ記録"""
    # TODO: 監査ログをデータベースに記録
    pass

async def log_rollback_action(rollback_id: str, apply_id: str, user_id: str, reason: str):
    """ロールバックアクションのログ記録"""
    # TODO: 監査ログをデータベースに記録
    pass