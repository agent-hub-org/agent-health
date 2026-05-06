import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from agent_common.server.models import AskRequest, AskResponse
from agent_sdk.server.sse import create_sse_stream
from agent_sdk.server.session import verify_session_ownership
from agent_sdk.database.memory import save_memory
from agents.runner import run_query, create_stream
from database.mongo import MongoDB

from app import limiter

router = APIRouter(tags=["agent"])
logger = logging.getLogger("agent_health.api")


@router.post("/ask", response_model=AskResponse)
@limiter.limit("30/minute")
async def ask(body: AskRequest, request: Request):
    user_id = request.headers.get("X-User-Id") or None
    is_new = body.session_id is None
    session_id = body.session_id or MongoDB.generate_session_id()

    if not is_new:
        await verify_session_ownership(session_id, user_id, MongoDB)

    logger.info(
        "POST /ask — session='%s' (%s), user='%s', query='%s'",
        session_id, "new" if is_new else "existing", user_id or "anonymous", body.query[:100],
    )

    result = await run_query(
        body.query,
        session_id=session_id,
        response_format=body.response_format,
        model_id=body.model_id,
        user_id=user_id,
    )
    response = result["response"]
    steps = result["steps"]

    await MongoDB.save_conversation(
        session_id=session_id,
        query=body.query,
        response=response,
        steps=steps,
        user_id=user_id,
        plan=result.get("plan"),
    )

    logger.info(
        "POST /ask complete — session='%s', response length: %d chars, tool_calls: %d",
        session_id, len(response),
        sum(1 for s in steps if s.get("action") == "tool_call"),
    )

    return AskResponse(session_id=session_id, query=body.query, response=response)


@router.post("/ask/stream")
@limiter.limit("30/minute")
async def ask_stream(body: AskRequest, request: Request):
    """Stream the agent's response as Server-Sent Events (SSE)."""
    user_id = request.headers.get("X-User-Id") or None
    is_new = body.session_id is None
    session_id = body.session_id or MongoDB.generate_session_id()

    if not is_new:
        await verify_session_ownership(session_id, user_id, MongoDB)

    logger.info(
        "POST /ask/stream — session='%s', user='%s', query='%s'",
        session_id, user_id or "anonymous", body.query[:100],
    )

    stream = await create_stream(
        body.query,
        session_id=session_id,
        response_format=body.response_format,
        model_id=body.model_id,
        user_id=user_id,
    )

    async def _on_complete(response_text: str, steps: list, plan: str | None) -> None:
        asyncio.create_task(asyncio.to_thread(
            save_memory, user_id=user_id or session_id, query=body.query, response=response_text,
        ))
        await MongoDB.save_conversation(
            session_id=session_id, query=body.query, response=response_text,
            steps=steps, user_id=user_id, plan=plan,
        )

    return StreamingResponse(
        create_sse_stream(stream, session_id=session_id, query=body.query, on_complete=_on_complete),
        media_type="text/event-stream",
    )
