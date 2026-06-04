from fastapi import APIRouter, HTTPException
from app.services.scratchpad import get_artifact

router = APIRouter()


@router.get("/scratchpad/{session_id}/{report_id}")
async def get_scratchpad_artifact(session_id: str, report_id: str):
    artifact = get_artifact(session_id, report_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found or session expired.")
    return {"report_id": report_id, "session_id": session_id, **artifact}
