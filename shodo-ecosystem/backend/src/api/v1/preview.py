"""
Preview API endpoints
MUST: OpenAPI compliant, BaseResponse pattern
"""

from fastapi import APIRouter, Depends
import structlog

from src.schemas.base import BaseResponse, error_response
from src.schemas.preview import (
    PreviewRequest, PreviewData,
    RefineRequest, ApplyRequest
)
from src.services.preview.sandbox_engine import (
    SandboxPreviewEngine, Change
)
from src.core.security import InputSanitizer
from src.middleware.auth import get_current_user
from src.utils.correlation import get_correlation_id

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/preview", tags=["Preview"])

engine = SandboxPreviewEngine()

@router.post("/generate", response_model=BaseResponse[PreviewData])
async def generate_preview(request: PreviewRequest, user=Depends(get_current_user)):
    sanitized = InputSanitizer.sanitize_string(request.resource_id)
    preview = await engine.generate_preview(request.resource_type, sanitized, request.changes)
    return BaseResponse(success=True, data=preview)

@router.post("/refine", response_model=BaseResponse[PreviewData])
async def refine_preview(request: RefineRequest, user=Depends(get_current_user)):
    refined = await engine.refine(request.previous_preview, request.refinement)
    return BaseResponse(success=True, data=refined)

@router.post("/apply", response_model=BaseResponse[PreviewData])
async def apply_changes(request: ApplyRequest, user=Depends(get_current_user)):
    applied = await engine.apply_changes(request.change_plan)
    return BaseResponse(success=True, data=applied)