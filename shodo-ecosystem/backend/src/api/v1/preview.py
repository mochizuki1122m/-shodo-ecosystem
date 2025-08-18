"""
プレビュー生成・管理APIエンドポイント
"""

from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime
import json
import hashlib
from .auth import get_current_user

router = APIRouter()

# プレビューストレージ（本番環境ではDBを使用）
previews = {}
preview_history = {}

class GeneratePreviewRequest(BaseModel):
    changes: List[Dict[str, Any]]
    context: Optional[Dict[str, Any]] = None
    dry_run: bool = True

class RefinePreviewRequest(BaseModel):
    refinement: str
    changes: Optional[List[Dict[str, Any]]] = None

class ApplyPreviewRequest(BaseModel):
    confirm: bool = True
    rollback_enabled: bool = True

class PreviewResponse(BaseModel):
    id: str
    status: str  # "pending", "generated", "applied", "failed"
    changes: List[Dict[str, Any]]
    preview_url: Optional[str] = None
    applied_at: Optional[datetime] = None
    rollback_available: bool = False
    created_at: datetime
    updated_at: datetime

@router.post("/generate", response_model=PreviewResponse)
async def generate_preview(
    request: GeneratePreviewRequest,
    current_user: dict = Depends(get_current_user)
):
    """変更プレビューの生成"""
    
    # プレビューID生成
    preview_id = f"preview_{hashlib.md5(json.dumps(request.changes, sort_keys=True).encode()).hexdigest()[:8]}"
    
    # プレビュー生成ロジック
    preview_data = {
        "id": preview_id,
        "status": "generated",
        "changes": request.changes,
        "preview_url": f"/api/v1/preview/view/{preview_id}",
        "applied_at": None,
        "rollback_available": False,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "user_id": current_user["id"],
        "context": request.context,
        "dry_run": request.dry_run
    }
    
    # 変更の検証
    validation_errors = validate_changes(request.changes)
    if validation_errors:
        preview_data["status"] = "failed"
        preview_data["errors"] = validation_errors
    
    # ストレージに保存
    previews[preview_id] = preview_data
    
    # 履歴に追加
    user_email = current_user["email"]
    if user_email not in preview_history:
        preview_history[user_email] = []
    preview_history[user_email].append(preview_id)
    
    return PreviewResponse(
        id=preview_data["id"],
        status=preview_data["status"],
        changes=preview_data["changes"],
        preview_url=preview_data["preview_url"],
        applied_at=preview_data["applied_at"],
        rollback_available=preview_data["rollback_available"],
        created_at=preview_data["created_at"],
        updated_at=preview_data["updated_at"]
    )

@router.post("/refine/{preview_id}", response_model=PreviewResponse)
async def refine_preview(
    preview_id: str,
    request: RefinePreviewRequest,
    current_user: dict = Depends(get_current_user)
):
    """プレビューの精緻化"""
    
    # プレビュー取得
    if preview_id not in previews:
        raise HTTPException(status_code=404, detail="Preview not found")
    
    preview = previews[preview_id]
    
    # ユーザー権限チェック
    if preview["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # 既に適用済みの場合はエラー
    if preview["status"] == "applied":
        raise HTTPException(status_code=400, detail="Cannot refine applied preview")
    
    # 変更の更新
    if request.changes:
        preview["changes"] = request.changes
    
    # 精緻化の記録
    if "refinements" not in preview:
        preview["refinements"] = []
    preview["refinements"].append({
        "text": request.refinement,
        "timestamp": datetime.utcnow()
    })
    
    # 更新日時を更新
    preview["updated_at"] = datetime.utcnow()
    
    # 再検証
    validation_errors = validate_changes(preview["changes"])
    if validation_errors:
        preview["status"] = "failed"
        preview["errors"] = validation_errors
    else:
        preview["status"] = "generated"
    
    return PreviewResponse(
        id=preview["id"],
        status=preview["status"],
        changes=preview["changes"],
        preview_url=preview["preview_url"],
        applied_at=preview["applied_at"],
        rollback_available=preview["rollback_available"],
        created_at=preview["created_at"],
        updated_at=preview["updated_at"]
    )

@router.post("/apply/{preview_id}", response_model=PreviewResponse)
async def apply_preview(
    preview_id: str,
    request: ApplyPreviewRequest,
    current_user: dict = Depends(get_current_user)
):
    """プレビューの適用"""
    
    # プレビュー取得
    if preview_id not in previews:
        raise HTTPException(status_code=404, detail="Preview not found")
    
    preview = previews[preview_id]
    
    # ユーザー権限チェック
    if preview["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # ステータスチェック
    if preview["status"] != "generated":
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot apply preview with status: {preview['status']}"
        )
    
    # 確認チェック
    if not request.confirm:
        raise HTTPException(status_code=400, detail="Confirmation required")
    
    # 変更の適用（実際の実装では各サービスAPIを呼び出す）
    try:
        # ここで実際の変更を適用
        apply_result = apply_changes_to_services(preview["changes"])
        
        # ロールバック情報の保存
        if request.rollback_enabled:
            preview["rollback_data"] = create_rollback_data(preview["changes"])
            preview["rollback_available"] = True
        
        # ステータス更新
        preview["status"] = "applied"
        preview["applied_at"] = datetime.utcnow()
        preview["updated_at"] = datetime.utcnow()
        preview["apply_result"] = apply_result
        
    except Exception as e:
        preview["status"] = "failed"
        preview["error"] = str(e)
        preview["updated_at"] = datetime.utcnow()
        raise HTTPException(status_code=500, detail=f"Failed to apply changes: {str(e)}")
    
    return PreviewResponse(
        id=preview["id"],
        status=preview["status"],
        changes=preview["changes"],
        preview_url=preview["preview_url"],
        applied_at=preview["applied_at"],
        rollback_available=preview["rollback_available"],
        created_at=preview["created_at"],
        updated_at=preview["updated_at"]
    )

@router.post("/rollback/{preview_id}")
async def rollback_preview(
    preview_id: str,
    current_user: dict = Depends(get_current_user)
):
    """適用済みプレビューのロールバック"""
    
    # プレビュー取得
    if preview_id not in previews:
        raise HTTPException(status_code=404, detail="Preview not found")
    
    preview = previews[preview_id]
    
    # ユーザー権限チェック
    if preview["user_id"] != current_user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # ロールバック可能チェック
    if not preview.get("rollback_available", False):
        raise HTTPException(status_code=400, detail="Rollback not available")
    
    # ロールバック実行
    try:
        rollback_result = perform_rollback(preview.get("rollback_data", {}))
        
        preview["status"] = "rolled_back"
        preview["rollback_available"] = False
        preview["rolled_back_at"] = datetime.utcnow()
        preview["rollback_result"] = rollback_result
        
        return {
            "message": "Rollback successful",
            "result": rollback_result
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rollback failed: {str(e)}")

@router.get("/view/{preview_id}")
async def view_preview(preview_id: str):
    """プレビューの表示"""
    
    if preview_id not in previews:
        raise HTTPException(status_code=404, detail="Preview not found")
    
    preview = previews[preview_id]
    
    # HTMLプレビューの生成
    html = generate_preview_html(preview["changes"])
    
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)

@router.get("/history")
async def get_preview_history(
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """プレビュー履歴の取得"""
    
    user_email = current_user["email"]
    user_preview_ids = preview_history.get(user_email, [])
    
    # 最新のプレビューから取得
    user_previews = []
    for preview_id in user_preview_ids[-limit:][::-1]:
        if preview_id in previews:
            preview = previews[preview_id]
            user_previews.append({
                "id": preview["id"],
                "status": preview["status"],
                "created_at": preview["created_at"],
                "updated_at": preview["updated_at"],
                "changes_count": len(preview["changes"])
            })
    
    return {
        "previews": user_previews,
        "total": len(user_preview_ids)
    }

def validate_changes(changes: List[Dict]) -> List[str]:
    """変更の検証"""
    errors = []
    
    for i, change in enumerate(changes):
        if "action" not in change:
            errors.append(f"Change {i}: 'action' field is required")
        if "target" not in change:
            errors.append(f"Change {i}: 'target' field is required")
        
        # アクションタイプの検証
        valid_actions = ["create", "update", "delete", "modify"]
        if change.get("action") not in valid_actions:
            errors.append(f"Change {i}: Invalid action '{change.get('action')}'")
    
    return errors

def apply_changes_to_services(changes: List[Dict]) -> Dict:
    """実際のサービスに変更を適用（モック実装）"""
    results = []
    
    for change in changes:
        # ここで実際のサービスAPIを呼び出す
        result = {
            "action": change["action"],
            "target": change["target"],
            "status": "success",
            "timestamp": datetime.utcnow()
        }
        results.append(result)
    
    return {"results": results, "total": len(changes)}

def create_rollback_data(changes: List[Dict]) -> Dict:
    """ロールバックデータの作成"""
    rollback_data = {
        "original_state": {},
        "changes": changes,
        "created_at": datetime.utcnow()
    }
    
    # 変更前の状態を保存（実際の実装では各サービスから取得）
    for change in changes:
        if change["action"] == "update":
            # 更新前のデータを保存
            rollback_data["original_state"][change["target"]] = {
                "data": "original_data_here"
            }
    
    return rollback_data

def perform_rollback(rollback_data: Dict) -> Dict:
    """ロールバックの実行"""
    # 実際の実装では保存された状態に戻す
    return {
        "restored_items": len(rollback_data.get("original_state", {})),
        "timestamp": datetime.utcnow()
    }

def generate_preview_html(changes: List[Dict]) -> str:
    """プレビューHTMLの生成"""
    changes_html = ""
    for change in changes:
        changes_html += f"""
        <div class="change-item">
            <h3>{change.get('action', 'Unknown')} - {change.get('target', 'Unknown')}</h3>
            <pre>{json.dumps(change.get('data', {}), indent=2, ensure_ascii=False)}</pre>
        </div>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Preview</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .change-item {{ 
                border: 1px solid #ddd; 
                padding: 10px; 
                margin: 10px 0; 
                border-radius: 5px;
            }}
            h3 {{ color: #333; }}
            pre {{ background: #f5f5f5; padding: 10px; overflow-x: auto; }}
        </style>
    </head>
    <body>
        <h1>Changes Preview</h1>
        {changes_html}
    </body>
    </html>
    """