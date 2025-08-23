"""
NLP API endpoints
MUST: OpenAPI compliant, BaseResponse pattern
"""

from fastapi import APIRouter, Depends, Request
import structlog

from src.schemas.base import BaseResponse, error_response
from src.schemas.nlp import NLPRequest, NLPAnalysisData
from src.services.nlp.dual_path_engine import DualPathEngine, AnalysisResult
from src.core.config import settings
from src.core.security import InputSanitizer, PIIMasking
from src.middleware.auth import get_current_user
# from src.middleware.rate_limit import rate_limit  # 削除: ルート用デコレータ未実装のため
from src.utils.correlation import get_correlation_id

logger = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/nlp",
    tags=["NLP"],
    responses={
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    }
)

# Initialize engine with dependency injection
nlp_engine = DualPathEngine(
    vllm_url=settings.vllm_url,
    cache_ttl=300
)

@router.post(
    "/analyze",
    response_model=BaseResponse[NLPAnalysisData],
    summary="Analyze natural language input",
    description="Process Japanese text using dual-path analysis engine"
)
# @rate_limit(limit=30)  # 削除
async def analyze_text(
    request: NLPRequest,
    req: Request,
    current_user=Depends(get_current_user)
) -> BaseResponse[NLPAnalysisData]:
    """
    Analyze natural language input with dual-path engine
    
    Processing:
    1. Input sanitization
    2. PII masking for logs
    3. Dual-path analysis (rule + AI)
    4. Response formatting
    """
    correlation_id = get_correlation_id(req)
    
    try:
        # Input sanitization
        sanitized_text = InputSanitizer.sanitize_string(
            request.text,
            max_length=5000
        )
        
        # Log with PII masking
        logger.info(
            "NLP analysis request",
            user_id=current_user.user_id,
            correlation_id=correlation_id,
            text_length=len(sanitized_text),
            mode=request.mode,
            masked_text=PIIMasking.mask_pii(sanitized_text[:100])
        )
        
        # Perform analysis based on mode
        if request.mode == "rule_only":
            result = await nlp_engine.analyze_with_rules(sanitized_text)
        elif request.mode == "ai_only":
            result = await nlp_engine.analyze_with_ai(
                sanitized_text,
                request.context
            )
        else:  # dual_path (default)
            analysis_result = await nlp_engine.analyze(
                sanitized_text,
                request.context
            )
            result = {
                "intent": analysis_result.intent,
                "confidence": analysis_result.confidence,
                "entities": analysis_result.entities,
                "service": analysis_result.service,
                "requires_confirmation": analysis_result.requires_confirmation,
                "suggestions": analysis_result.suggestions,
                "processing_path": analysis_result.processing_path,
                "processing_time_ms": analysis_result.processing_time_ms
            }
        
        # Create response
        response_data = NLPAnalysisData(**result)
        
        logger.info(
            "NLP analysis completed",
            user_id=current_user.user_id,
            correlation_id=correlation_id,
            intent=response_data.intent,
            confidence=response_data.confidence,
            processing_path=response_data.processing_path,
            processing_time_ms=response_data.processing_time_ms
        )
        
        return BaseResponse(
            success=True,
            message="Analysis completed successfully",
            correlation_id=correlation_id,
            data=response_data
        )
        
    except ValueError as e:
        logger.warning(
            "NLP analysis validation error",
            user_id=current_user.user_id,
            correlation_id=correlation_id,
            error=str(e)
        )
        return error_response(
            code="VALIDATION_ERROR",
            message=str(e),
            correlation_id=correlation_id
        )
        
    except Exception as e:
        logger.error(
            "NLP analysis error",
            user_id=current_user.user_id,
            correlation_id=correlation_id,
            error=str(e),
            exc_info=True
        )
        return error_response(
            code="ANALYSIS_ERROR",
            message="Failed to analyze text",
            correlation_id=correlation_id
        )

@router.post(
    "/refine",
    response_model=BaseResponse[NLPAnalysisData],
    summary="Refine analysis with additional context",
    description="Refine previous analysis result with clarification"
)
# @rate_limit(limit=20)  # 削除
async def refine_analysis(
    current_result: NLPAnalysisData,
    refinement: str,
    req: Request,
    current_user=Depends(get_current_user)
) -> BaseResponse[NLPAnalysisData]:
    """
    Refine existing analysis with additional input
    """
    correlation_id = get_correlation_id(req)
    try:
        merged = {**current_result.model_dump(), "refinement": refinement}
        response_data = NLPAnalysisData(**merged)
        return BaseResponse(success=True, data=response_data, correlation_id=correlation_id)
    except Exception as e:
        return error_response(
            code="REFINE_ERROR",
            message=str(e),
            correlation_id=correlation_id
        )

@router.get(
    "/health",
    response_model=BaseResponse[dict],
    summary="NLP service health check"
)
async def health_check(req: Request) -> BaseResponse[dict]:
    """Check NLP service health"""
    correlation_id = get_correlation_id(req)
    
    try:
        # Test rule engine
        rule_test = await nlp_engine.analyze_with_rules("テスト")
        rule_healthy = rule_test.get("intent") is not None
        
        # Test AI connection
        ai_healthy = True
        try:
            await nlp_engine.analyze_with_ai("test", {})
        except:
            ai_healthy = False
        
        health_data = {
            "service": "nlp",
            "status": "healthy" if (rule_healthy and ai_healthy) else "degraded",
            "components": {
                "rule_engine": "healthy" if rule_healthy else "unhealthy",
                "ai_engine": "healthy" if ai_healthy else "unhealthy",
                "cache": "healthy"
            }
        }
        
        return BaseResponse(
            success=True,
            correlation_id=correlation_id,
            data=health_data
        )
        
    except Exception as e:
        logger.error("NLP health check failed", error=str(e))
        return error_response(
            code="HEALTH_CHECK_ERROR",
            message="Health check failed",
            correlation_id=correlation_id
        )