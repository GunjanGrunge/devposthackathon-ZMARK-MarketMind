import json

from fastapi import APIRouter, HTTPException
from plotly.utils import PlotlyJSONEncoder

from app.services.scratchpad import get_artifact

router = APIRouter()


@router.get("/scratchpad/{session_id}/{report_id}")
async def get_scratchpad_artifact(session_id: str, report_id: str):
    artifact = get_artifact(session_id, report_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found or session expired.")
    payload = {"report_id": report_id, "session_id": session_id, **artifact}
    return json.loads(json.dumps(payload, cls=PlotlyJSONEncoder))
