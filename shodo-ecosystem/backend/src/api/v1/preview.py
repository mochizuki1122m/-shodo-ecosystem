"""
Preview API endpoints
MUST: OpenAPI compliant, BaseResponse pattern
"""

from fastapi import APIRouter, Depends, Request
import structlog

from ...schemas.base import BaseResponse, error_response
from ...schemas.preview import (
    PreviewRequest, PreviewData,
    RefineRequest, ApplyRequest
)
from ...services.preview.sandbox_engine import (
    SandboxPreviewEngine, Change
)
from ...services.database import get_redis
from ...core.security import InputSanitizer
from ...middleware.auth import get_current_user
from ...utils.correlation import get_correlation_id

logger = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/preview",
    tags=["Preview"],
    responses={
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    }
)

# Initialize engine with dependency injection
preview_engine = SandboxPreviewEngine(
    max_versions=100,
    cache_size=50
)

PREVIEW_PREFIX = "preview:obj:"
PREVIEW_TTL = 3600  # 1h default

@router.post(
    "/generate",
    response_model=BaseResponse[PreviewData],
    summary="Generate preview",
    description="Generate a sandbox preview with changes"
)
async def generate_preview(
    request: PreviewRequest,
    req: Request,
    current_user=Depends(get_current_user)
) -> BaseResponse[PreviewData]:
    """
    Generate preview in sandbox environment
    
    Processing:
    1. Validate changes
    2. Create virtual environment
    3. Apply changes
    4. Generate visual preview
    5. Calculate diff
    """
    correlation_id = get_correlation_id(req)
    
    try:
        logger.info(
            "Preview generation request",
            user_id=current_user.id,
            correlation_id=correlation_id,
            service_id=request.service_id,
            changes_count=len(request.changes)
        )
        
        # Convert request changes to engine format
        engine_changes = []
        for change in request.changes:
            engine_changes.append(Change(
                type=change.type,
                target=InputSanitizer.sanitize_string(change.target),
                property=InputSanitizer.sanitize_string(change.property),
                old_value=change.old_value,
                new_value=InputSanitizer.sanitize_string(change.new_value),
                metadata=change.metadata
            ))
        
        # Generate preview
        preview = await preview_engine.generate_preview(
            engine_changes,
            {
                "service_id": request.service_id,
                "context": request.context or {},
                "user_id": current_user.id
            }
        )
        
        # Store preview for later refinement (Redis if available)
        redis_client = get_redis()
        if redis_client:
            try:
                import json
                from dataclasses import asdict
                await redis_client.setex(
                    PREVIEW_PREFIX + preview.id,
                    PREVIEW_TTL,
                    json.dumps({
                        "id": preview.id,
                        "version_id": preview.version_id,
                        "service": preview.service,
                        "visual": preview.visual,
                        "diff": preview.diff,
                        "changes": [asdict(c) for c in preview.changes],
                        "confidence": preview.confidence,
                        "revert_token": preview.revert_token,
                    })
                )
            except Exception:
                pass
        else:
            # Fallback: no-op (avoid in-memory to support scale)
            logger.warning("Redis unavailable: preview not cached; refinement requires ID persistence")
        
        # Convert to response format
        response_data = PreviewData(
            id=preview.id,
            version_id=preview.version_id,
            service=preview.service,
            visual={
                "html": preview.visual.get("html", ""),
                "css": preview.visual.get("css", ""),
                "javascript": preview.visual.get("javascript", ""),
                "screenshot": preview.visual.get("screenshot")
            },
            diff=preview.diff,
            changes=[{
                "type": c.type,
                "target": c.target,
                "property": c.property,
                "old_value": c.old_value,
                "new_value": c.new_value
            } for c in preview.changes],
            confidence=preview.confidence,
            revert_token=preview.revert_token
        )
        
        logger.info(
            "Preview generated",
            user_id=current_user.id,
            correlation_id=correlation_id,
            preview_id=preview.id,
            confidence=preview.confidence
        )
        
        return BaseResponse(
            success=True,
            message="Preview generated successfully",
            correlation_id=correlation_id,
            data=response_data
        )
        
    except ValueError as e:
        logger.warning(
            "Preview validation error",
            user_id=current_user.id,
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
            "Preview generation error",
            user_id=current_user.id,
            correlation_id=correlation_id,
            error=str(e),
            exc_info=True
        )
        return error_response(
            code="PREVIEW_ERROR",
            message="Failed to generate preview",
            correlation_id=correlation_id
        )

@router.post(
    "/{preview_id}/refine",
    response_model=BaseResponse[PreviewData],
    summary="Refine preview",
    description="Refine existing preview with natural language"
)
async def refine_preview(
    preview_id: str,
    request: RefineRequest,
    req: Request,
    current_user=Depends(get_current_user)
) -> BaseResponse[PreviewData]:
    """
    Refine preview with natural language instructions
    """
    correlation_id = get_correlation_id(req)
    
    try:
        # Get existing preview
        current_preview = None
        redis_client = get_redis()
        if redis_client:
            try:
                import json
                data = await redis_client.get(PREVIEW_PREFIX + preview_id)
                if data:
                    obj = json.loads(data)
                    # Rehydrate minimal Preview for refine
                    from ...services.preview.sandbox_engine import Preview
                    current_preview = Preview(
                        id=obj["id"],
                        version_id=obj["version_id"],
                        service=obj["service"],
                        visual=obj.get("visual", {}),
                        diff=obj.get("diff", {}),
                        changes=[Change(**c) for c in obj.get("changes", [])],
                        created_at=None,
                        revert_token=obj.get("revert_token", ""),
                        confidence=obj.get("confidence", 0.0),
                        refinement_history=[]
                    )
            except Exception:
                current_preview = None
        if not current_preview:
            return error_response(
                code="NOT_FOUND",
                message=f"Preview {preview_id} not found",
                correlation_id=correlation_id
            )
        
        logger.info(
            "Preview refinement request",
            user_id=current_user.id,
            correlation_id=correlation_id,
            preview_id=preview_id,
            refinement_length=len(request.refinement)
        )
        
        # Refine the preview
        refined_preview = await preview_engine.refine_preview(
            current_preview,
            InputSanitizer.sanitize_string(request.refinement, max_length=1000)
        )
        
        # Store refined version
        redis_client = get_redis()
        if redis_client:
            try:
                import json
                from dataclasses import asdict
                await redis_client.setex(
                    PREVIEW_PREFIX + refined_preview.id,
                    PREVIEW_TTL,
                    json.dumps({
                        "id": refined_preview.id,
                        "version_id": refined_preview.version_id,
                        "service": refined_preview.service,
                        "visual": refined_preview.visual,
                        "diff": refined_preview.diff,
                        "changes": [asdict(c) for c in refined_preview.changes],
                        "confidence": refined_preview.confidence,
                        "revert_token": refined_preview.revert_token,
                    })
                )
            except Exception:
                pass
        
        # Convert to response
        response_data = PreviewData(
            id=refined_preview.id,
            version_id=refined_preview.version_id,
            service=refined_preview.service,
            visual={
                "html": refined_preview.visual.get("html", ""),
                "css": refined_preview.visual.get("css", ""),
                "javascript": refined_preview.visual.get("javascript", ""),
                "screenshot": refined_preview.visual.get("screenshot")
            },
            diff=refined_preview.diff,
            changes=[{
                "type": c.type,
                "target": c.target,
                "property": c.property,
                "old_value": c.old_value,
                "new_value": c.new_value
            } for c in refined_preview.changes],
            confidence=refined_preview.confidence,
            revert_token=refined_preview.revert_token
        )
        
        return BaseResponse(
            success=True,
            message="Preview refined successfully",
            correlation_id=correlation_id,
            data=response_data
        )
        
    except Exception as e:
        logger.error(
            "Preview refinement error",
            user_id=current_user.id,
            correlation_id=correlation_id,
            error=str(e),
            exc_info=True
        )
        return error_response(
            code="REFINEMENT_ERROR",
            message="Failed to refine preview",
            correlation_id=correlation_id
        )

@router.post(
    "/{preview_id}/apply",
    response_model=BaseResponse[dict],
    summary="Apply preview to production",
    description="Apply sandbox preview to production environment"
)
async def apply_preview(
    preview_id: str,
    request: ApplyRequest,
    req: Request,
    current_user=Depends(get_current_user)
) -> BaseResponse[dict]:
    """
    Apply preview to production with confirmation
    """
    correlation_id = get_correlation_id(req)
    
    try:
        if preview_id not in preview_storage:
            return error_response(
                code="NOT_FOUND",
                message=f"Preview {preview_id} not found",
                correlation_id=correlation_id
            )
        
        preview = preview_storage[preview_id]
        
        # Verify confirmation
        if not request.confirmed:
            return error_response(
                code="CONFIRMATION_REQUIRED",
                message="Please confirm the production deployment",
                correlation_id=correlation_id
            )
        
        logger.warning(
            "Applying preview to production",
            user_id=current_user.id,
            correlation_id=correlation_id,
            preview_id=preview_id,
            service=preview.service
        )
        
        # Apply to production
        result = await preview_engine.apply_to_production(preview)
        
        logger.info(
            "Preview applied to production",
            user_id=current_user.id,
            correlation_id=correlation_id,
            preview_id=preview_id,
            result=result
        )
        
        return BaseResponse(
            success=True,
            message="Preview applied to production successfully",
            correlation_id=correlation_id,
            data=result
        )
        
    except Exception as e:
        logger.error(
            "Production apply error",
            user_id=current_user.id,
            correlation_id=correlation_id,
            error=str(e),
            exc_info=True
        )
        return error_response(
            code="APPLY_ERROR",
            message="Failed to apply preview to production",
            correlation_id=correlation_id
        )

@router.post(
    "/rollback/{version_id}",
    response_model=BaseResponse[dict],
    summary="Rollback to previous version",
    description="Rollback to a specific version"
)
async def rollback_version(
    version_id: str,
    req: Request,
    current_user=Depends(get_current_user)
) -> BaseResponse[dict]:
    """
    Rollback to a previous version
    """
    correlation_id = get_correlation_id(req)
    
    try:
        logger.warning(
            "Rollback request",
            user_id=current_user.id,
            correlation_id=correlation_id,
            version_id=version_id
        )
        
        result = await preview_engine.rollback(version_id)
        
        logger.info(
            "Rollback completed",
            user_id=current_user.id,
            correlation_id=correlation_id,
            version_id=version_id,
            result=result
        )
        
        return BaseResponse(
            success=True,
            message="Rollback completed successfully",
            correlation_id=correlation_id,
            data=result
        )
        
    except ValueError as e:
        return error_response(
            code="VERSION_NOT_FOUND",
            message=str(e),
            correlation_id=correlation_id
        )
    except Exception as e:
        logger.error(
            "Rollback error",
            user_id=current_user.id,
            correlation_id=correlation_id,
            error=str(e),
            exc_info=True
        )
        return error_response(
            code="ROLLBACK_ERROR",
            message="Failed to rollback",
            correlation_id=correlation_id
        )

@router.get(
    "/health",
    response_model=BaseResponse[dict],
    summary="Preview service health check"
)
async def health_check(req: Request) -> BaseResponse[dict]:
    """Check preview service health"""
    correlation_id = get_correlation_id(req)
    
    health_data = {
        "service": "preview",
        "status": "healthy",
        "components": {
            "sandbox_engine": "healthy",
            "version_control": "healthy",
            "renderer": "healthy"
        },
        "stats": {
            "cached_previews": len(preview_storage),
            "max_versions": preview_engine.max_versions
        }
    }
    
    return BaseResponse(
        success=True,
        correlation_id=correlation_id,
        data=health_data
    )