"""
自然言語処理APIエンドポイント
"""

from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import httpx
import os
import json
import hashlib
from datetime import datetime
from .auth import get_current_user

router = APIRouter()

# AI サーバーのURL
AI_SERVER_URL = os.getenv("VLLM_URL", "http://localhost:8001")

# キャッシュストレージ（本番環境ではRedisを使用）
analysis_cache = {}
analysis_history = {}

class AnalyzeRequest(BaseModel):
    text: str
    context: Optional[Dict[str, Any]] = None
    use_cache: bool = True

class RefineRequest(BaseModel):
    refinement: str
    context: Optional[Dict[str, Any]] = None

class AnalysisResponse(BaseModel):
    id: str
    intent: str
    confidence: float
    entities: Dict[str, Any]
    service: Optional[str] = None
    suggestions: List[str] = []
    requires_confirmation: bool = False
    cached: bool = False
    timestamp: datetime

def get_cache_key(text: str, context: Optional[Dict] = None) -> str:
    """キャッシュキーの生成"""
    cache_data = f"{text}:{json.dumps(context or {}, sort_keys=True)}"
    return hashlib.md5(cache_data.encode()).hexdigest()

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_text(
    request: AnalyzeRequest,
    current_user: dict = Depends(get_current_user)
):
    """テキストの自然言語解析"""
    
    # キャッシュチェック
    cache_key = get_cache_key(request.text, request.context)
    if request.use_cache and cache_key in analysis_cache:
        cached_result = analysis_cache[cache_key]
        cached_result["cached"] = True
        return AnalysisResponse(**cached_result)
    
    try:
        # AIサーバーに解析リクエスト
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{AI_SERVER_URL}/v1/analyze",
                json={
                    "text": request.text,
                    "context": request.context
                },
                timeout=30.0
            )
            
            if response.status_code != 200:
                # フォールバック: 簡易ルールベース解析
                result = perform_simple_analysis(request.text)
            else:
                result = response.json()
        
        # 結果の整形
        analysis_id = f"analysis_{datetime.utcnow().timestamp()}"
        analysis_result = {
            "id": analysis_id,
            "intent": result.get("intent", "unknown"),
            "confidence": result.get("confidence", 0.5),
            "entities": result.get("entities", {}),
            "service": result.get("service"),
            "suggestions": result.get("suggestions", []),
            "requires_confirmation": result.get("confidence", 0.5) < 0.7,
            "cached": False,
            "timestamp": datetime.utcnow()
        }
        
        # キャッシュに保存
        analysis_cache[cache_key] = analysis_result
        
        # 履歴に保存
        user_email = current_user["email"]
        if user_email not in analysis_history:
            analysis_history[user_email] = []
        analysis_history[user_email].append({
            "id": analysis_id,
            "text": request.text,
            "result": analysis_result,
            "timestamp": datetime.utcnow()
        })
        
        return AnalysisResponse(**analysis_result)
        
    except httpx.RequestError as e:
        # ネットワークエラー時のフォールバック
        result = perform_simple_analysis(request.text)
        analysis_id = f"analysis_{datetime.utcnow().timestamp()}"
        
        return AnalysisResponse(
            id=analysis_id,
            intent=result["intent"],
            confidence=result["confidence"],
            entities=result["entities"],
            service=result.get("service"),
            suggestions=["AIサーバーが利用できないため、簡易解析を実行しました"],
            requires_confirmation=True,
            cached=False,
            timestamp=datetime.utcnow()
        )

@router.post("/refine/{analysis_id}", response_model=AnalysisResponse)
async def refine_analysis(
    analysis_id: str,
    request: RefineRequest,
    current_user: dict = Depends(get_current_user)
):
    """解析結果の精緻化"""
    
    # 履歴から元の解析を取得
    user_email = current_user["email"]
    user_history = analysis_history.get(user_email, [])
    
    original_analysis = None
    for item in user_history:
        if item["id"] == analysis_id:
            original_analysis = item
            break
    
    if not original_analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # 精緻化テキストを追加して再解析
    refined_text = f"{original_analysis['text']} {request.refinement}"
    
    return await analyze_text(
        AnalyzeRequest(
            text=refined_text,
            context=request.context,
            use_cache=False
        ),
        current_user
    )

@router.get("/history")
async def get_analysis_history(
    limit: int = 10,
    current_user: dict = Depends(get_current_user)
):
    """解析履歴の取得"""
    user_email = current_user["email"]
    user_history = analysis_history.get(user_email, [])
    
    # 最新のものから返す
    return {
        "history": user_history[-limit:][::-1],
        "total": len(user_history)
    }

@router.delete("/cache")
async def clear_cache(current_user: dict = Depends(get_current_user)):
    """キャッシュのクリア（管理者のみ）"""
    # TODO: 管理者権限チェック
    analysis_cache.clear()
    return {"message": "Cache cleared successfully"}

def perform_simple_analysis(text: str) -> Dict:
    """簡易的なルールベース解析（フォールバック用）"""
    text_lower = text.lower()
    
    # インテント検出
    if any(word in text_lower for word in ["エクスポート", "出力", "export", "download"]):
        intent = "export"
        confidence = 0.8
    elif any(word in text_lower for word in ["インポート", "取り込み", "import", "upload"]):
        intent = "import"
        confidence = 0.8
    elif any(word in text_lower for word in ["削除", "消去", "delete", "remove"]):
        intent = "delete"
        confidence = 0.75
    elif any(word in text_lower for word in ["作成", "新規", "create", "new"]):
        intent = "create"
        confidence = 0.75
    elif any(word in text_lower for word in ["更新", "変更", "update", "modify"]):
        intent = "update"
        confidence = 0.75
    elif any(word in text_lower for word in ["検索", "探す", "search", "find"]):
        intent = "search"
        confidence = 0.7
    else:
        intent = "unknown"
        confidence = 0.3
    
    # サービス検出
    service = None
    if "shopify" in text_lower or "ショッピファイ" in text:
        service = "shopify"
    elif "gmail" in text_lower or "メール" in text:
        service = "gmail"
    elif "stripe" in text_lower or "決済" in text or "支払" in text:
        service = "stripe"
    elif "slack" in text_lower or "スラック" in text:
        service = "slack"
    
    # エンティティ抽出
    entities = {}
    
    # 数値検出
    import re
    numbers = re.findall(r'\d+', text)
    if numbers:
        entities["numbers"] = numbers
    
    # 日付検出
    dates = re.findall(r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}日?', text)
    if dates:
        entities["dates"] = dates
    
    return {
        "intent": intent,
        "confidence": confidence,
        "entities": entities,
        "service": service,
        "suggestions": [] if confidence > 0.7 else ["もう少し詳しく教えてください"]
    }