import asyncio
import json

from fastapi import APIRouter, Header, status
from fastapi.responses import JSONResponse, StreamingResponse
from app.schemas.analytics import ChatRequest, ChatResponse
from app.services.chat_graph import answer_query_graph

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    x_session_id: str = Header(None, alias="X-Session-ID")
):
    """
    Handles a chat query.  Runs Elastic hybrid search for retrieval context,
    then sends it to Gemini for a grounded answer.  Falls back to a
    DataFrame-derived canned answer if either service is unavailable.
    """
    if not x_session_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "missing_session_id", "message": "X-Session-ID header is required"}
        )

    try:
        message = await answer_query_graph(
            session_id=x_session_id,
            query=body.query,
            history=body.history,
        )
        return ChatResponse(message=message)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "chat_error", "message": str(e)}
        )


def _stream_event(event: str, data: dict) -> str:
    return json.dumps({"event": event, **data}, default=str) + "\n"


def _message_to_dict(message):
    if hasattr(message, "model_dump"):
        return message.model_dump()
    if hasattr(message, "dict"):
        return message.dict()
    return dict(message)


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    x_session_id: str = Header(None, alias="X-Session-ID")
):
    """
    Streams chat progress and the final assistant content as NDJSON.
    The graph still performs the grounded analysis once, then the completed
    answer is emitted incrementally so the UI does not wait on a blank panel.
    """
    if not x_session_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "missing_session_id", "message": "X-Session-ID header is required"}
        )

    async def event_generator():
        try:
            yield _stream_event("status", {"message": "Reading uploaded session context"})
            await asyncio.sleep(0)
            yield _stream_event("status", {"message": "Running analysis agents"})

            message = await answer_query_graph(
                session_id=x_session_id,
                query=body.query,
                history=body.history,
            )
            payload = _message_to_dict(message)
            content = payload.get("content") or "I couldn't find relevant data in your uploaded files for this question."

            yield _stream_event("metadata", {
                "message": {
                    **payload,
                    "content": "",
                }
            })

            words = content.split(" ")
            for index, word in enumerate(words):
                chunk = word if index == 0 else f" {word}"
                yield _stream_event("chunk", {"content": chunk})
                await asyncio.sleep(0)

            yield _stream_event("done", {
                "message": {
                    **payload,
                    "content": content,
                }
            })
        except Exception as e:
            yield _stream_event("error", {"message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
