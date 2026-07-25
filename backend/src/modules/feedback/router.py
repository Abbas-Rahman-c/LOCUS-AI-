from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import TenantContext, get_current_tenant
from modules.feedback.schemas import FeedbackRequest
from modules.feedback.service import store_feedback

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("")
async def submit_feedback(
    request: FeedbackRequest,
    ctx: TenantContext = Depends(get_current_tenant),
):
    if request.signal not in ["up", "down"]:
        raise HTTPException(status_code=400, detail="Signal must be 'up' or 'down'")

    await store_feedback(ctx.tenant_id, request)
    return {"status": "success", "message": "Feedback received"}