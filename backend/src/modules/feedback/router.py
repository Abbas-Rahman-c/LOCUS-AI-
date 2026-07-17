from fastapi import APIRouter, HTTPException
from modules.feedback.schemas import FeedbackRequest
from modules.feedback.service import store_feedback

router = APIRouter(prefix="/feedback", tags=["feedback"])

@router.post("")
async def submit_feedback(request: FeedbackRequest):
    if request.signal not in ["up", "down"]:
        raise HTTPException(status_code=400, detail="Signal must be 'up' or 'down'")
    
    await store_feedback(request)
    return {"status": "success", "message": "Feedback received"}
