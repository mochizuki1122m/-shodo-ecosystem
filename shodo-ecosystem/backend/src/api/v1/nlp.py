"""
NLP APIエンドポイント
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from typing import List, Optional
import uuid
from datetime import datetime
import asyncio

from ...schemas.nlp import (
    NLPRequest, NLPResponse, NLPSession,
    NLPBatchRequest, NLPBatchResponse,
    RuleDefinition, RuleMatch, AIAnalysis
)
from ...schemas.common import BaseResponse, PaginatedResponse, PaginationParams, StatusEnum
from ...core.security import JWTManager, TokenData, security, limiter, InputSanitizer
from ...services.nlp.dual_path_engine import DualPathEngine

router = APIRouter()

# エンジンのインスタンス
nlp_engine = DualPathEngine()

@router.post("/analyze", response_model=BaseResponse[NLPResponse])
@limiter.limit("30/minute")
async def analyze_text(
    request: NLPRequest,
    background_tasks: BackgroundTasks,
    token_data: TokenData = Depends(JWTManager.verify_token)
):
    """
    テキスト解析
    
    ルールベースとAIベースのハイブリッド解析を実行します。
    """
    try:
        # セッションIDの生成または使用
        session_id = request.session_id or str(uuid.uuid4())
        analysis_id = str(uuid.uuid4())
        
        # テキストのサニタイズ
        sanitized_text = InputSanitizer.validate_prompt(request.text)
        
        # 解析の実行
        start_time = datetime.utcnow()
        
        # ルールベース解析
        rule_matches = await nlp_engine.analyze_with_rules(sanitized_text)
        
        # AI解析（オプション）
        ai_analysis = None
        if request.analysis_type in [AnalysisType.AI_BASED, AnalysisType.HYBRID]:
            ai_analysis = await nlp_engine.analyze_with_ai(
                sanitized_text,
                context=request.context
            )
        
        # 結果の統合
        combined_score = nlp_engine.calculate_combined_score(
            rule_matches,
            ai_analysis
        )
        
        processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        response = NLPResponse(
            session_id=session_id,
            analysis_id=analysis_id,
            status=StatusEnum.COMPLETED,
            rule_matches=rule_matches,
            ai_analysis=ai_analysis,
            combined_score=combined_score,
            processing_time_ms=processing_time,
            timestamp=datetime.utcnow()
        )
        
        # バックグラウンドで統計を更新
        background_tasks.add_task(
            update_session_stats,
            session_id,
            token_data.user_id,
            len(sanitized_text)
        )
        
        return BaseResponse(
            success=True,
            data=response,
            request_id=analysis_id
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@router.post("/analyze/batch", response_model=BaseResponse[NLPBatchResponse])
@limiter.limit("10/minute")
async def analyze_batch(
    request: NLPBatchRequest,
    token_data: TokenData = Depends(JWTManager.verify_token)
):
    """
    バッチテキスト解析
    
    複数のテキストを一括で解析します。
    """
    batch_id = str(uuid.uuid4())
    start_time = datetime.utcnow()
    
    results = []
    failed = 0
    
    # 並列または順次処理
    if request.parallel:
        # 並列処理
        tasks = []
        for item in request.items:
            task = analyze_single_item(item)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # エラーカウント
        for result in results:
            if isinstance(result, Exception):
                failed += 1
    else:
        # 順次処理
        for item in request.items:
            try:
                result = await analyze_single_item(item)
                results.append(result)
            except Exception as e:
                results.append(None)
                failed += 1
    
    processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
    
    response = NLPBatchResponse(
        batch_id=batch_id,
        total=len(request.items),
        completed=len(request.items) - failed,
        failed=failed,
        results=[r for r in results if r and not isinstance(r, Exception)],
        processing_time_ms=processing_time,
        timestamp=datetime.utcnow()
    )
    
    return BaseResponse(
        success=True,
        data=response,
        request_id=batch_id
    )

@router.get("/sessions", response_model=BaseResponse[PaginatedResponse[NLPSession]])
async def get_sessions(
    pagination: PaginationParams = Depends(),
    token_data: TokenData = Depends(JWTManager.verify_token)
):
    """
    セッション一覧取得
    
    ユーザーのNLPセッション一覧を取得します。
    """
    # TODO: データベースから実際のセッションを取得
    mock_sessions = [
        NLPSession(
            session_id=str(uuid.uuid4()),
            user_id=token_data.user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            analysis_count=5,
            total_tokens=1500,
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

@router.get("/sessions/{session_id}", response_model=BaseResponse[NLPSession])
async def get_session(
    session_id: str,
    token_data: TokenData = Depends(JWTManager.verify_token)
):
    """
    セッション詳細取得
    
    特定のNLPセッションの詳細を取得します。
    """
    # TODO: データベースから実際のセッションを取得
    session = NLPSession(
        session_id=session_id,
        user_id=token_data.user_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        analysis_count=5,
        total_tokens=1500,
        metadata={}
    )
    
    return BaseResponse(
        success=True,
        data=session
    )

@router.get("/rules", response_model=BaseResponse[List[RuleDefinition]])
async def get_rules(
    category: Optional[str] = None,
    is_active: Optional[bool] = True,
    token_data: TokenData = Depends(JWTManager.verify_token)
):
    """
    ルール一覧取得
    
    利用可能なルール定義の一覧を取得します。
    """
    # TODO: データベースから実際のルールを取得
    rules = nlp_engine.get_rules(category=category, is_active=is_active)
    
    return BaseResponse(
        success=True,
        data=rules
    )

@router.post("/rules", response_model=BaseResponse[RuleDefinition])
@limiter.limit("10/minute")
async def create_rule(
    rule: RuleDefinition,
    token_data: TokenData = Depends(JWTManager.verify_token)
):
    """
    ルール作成
    
    新しいルール定義を作成します（管理者のみ）。
    """
    if "admin" not in token_data.roles:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # TODO: データベースにルールを保存
    created_rule = nlp_engine.add_rule(rule)
    
    return BaseResponse(
        success=True,
        data=created_rule
    )

# ヘルパー関数
async def analyze_single_item(request: NLPRequest) -> NLPResponse:
    """単一アイテムの解析"""
    session_id = request.session_id or str(uuid.uuid4())
    analysis_id = str(uuid.uuid4())
    
    # サニタイズ
    sanitized_text = InputSanitizer.validate_prompt(request.text)
    
    # 解析実行
    rule_matches = await nlp_engine.analyze_with_rules(sanitized_text)
    ai_analysis = None
    
    if request.analysis_type in [AnalysisType.AI_BASED, AnalysisType.HYBRID]:
        ai_analysis = await nlp_engine.analyze_with_ai(
            sanitized_text,
            context=request.context
        )
    
    combined_score = nlp_engine.calculate_combined_score(
        rule_matches,
        ai_analysis
    )
    
    return NLPResponse(
        session_id=session_id,
        analysis_id=analysis_id,
        status=StatusEnum.COMPLETED,
        rule_matches=rule_matches,
        ai_analysis=ai_analysis,
        combined_score=combined_score,
        processing_time_ms=0,
        timestamp=datetime.utcnow()
    )

async def update_session_stats(session_id: str, user_id: str, text_length: int):
    """セッション統計の更新"""
    # TODO: データベースでセッション統計を更新
    pass