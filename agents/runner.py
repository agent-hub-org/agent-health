import asyncio
import logging

from agent_sdk.database.memory import save_memory
from database.mongo import MongoDB

from .agent import create_agent
from .context_builder import _build_dynamic_context, _build_system_prompt

logger = logging.getLogger("agent_health.runner")


async def run_query(
    query: str,
    session_id: str = "default",
    response_format: str | None = None,
    model_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    logger.info(
        "run_query — session='%s', user='%s', query='%s', model='%s'",
        session_id, user_id or "anonymous", query[:100], model_id or "default",
    )

    dynamic_context = await _build_dynamic_context(
        session_id, query, response_format=response_format, user_id=user_id
    )
    enriched_query = dynamic_context + query
    system_prompt = _build_system_prompt(response_format)

    agent = create_agent()
    result = await agent.arun(
        enriched_query,
        session_id=session_id,
        system_prompt=system_prompt,
        model_id=model_id,
        user_id=user_id,
    )

    logger.info("run_query finished — session='%s', steps: %d", session_id, len(result["steps"]))
    save_memory(user_id=user_id or session_id, query=query, response=result["response"])

    return result


async def create_stream(
    query: str,
    session_id: str = "default",
    response_format: str | None = None,
    model_id: str | None = None,
    user_id: str | None = None,
):
    dynamic_context = await _build_dynamic_context(
        session_id, query, response_format=response_format, user_id=user_id
    )
    enriched_query = dynamic_context + query
    system_prompt = _build_system_prompt(response_format)

    agent = create_agent()
    return agent.astream(
        enriched_query,
        session_id=session_id,
        system_prompt=system_prompt,
        model_id=model_id,
        user_id=user_id,
    )


async def stream_for_a2a(query: str, *, session_id: str = "default",
                         user_id: str | None = None,
                         response_format: str | None = None, model_id: str | None = None,
                         **kwargs):
    """Async generator for the A2A StreamingAgentExecutor. Streams chunks and saves to DB."""
    dynamic_context = await _build_dynamic_context(
        session_id, query, response_format=response_format, user_id=user_id
    )
    enriched_query = dynamic_context + query
    system_prompt = _build_system_prompt(response_format)
    agent = create_agent()
    stream = agent.astream(
        enriched_query, session_id=session_id, system_prompt=system_prompt,
        model_id=model_id, user_id=user_id,
    )

    response_parts: list[str] = []
    async for chunk in stream:
        yield chunk
        if not chunk.startswith("__PROGRESS__:") and not chunk.startswith("__ERROR__:"):
            response_parts.append(chunk)

    response_text = "".join(response_parts)
    logger.info("stream_for_a2a finished — session='%s', steps: %d", session_id, len(stream.steps))
    save_memory(user_id=user_id or session_id, query=query, response=response_text)
    try:
        await MongoDB.save_conversation(
            session_id=session_id,
            query=query,
            response=response_text,
            steps=stream.steps,
            user_id=user_id,
            plan=stream.plan,
        )
    except Exception as e:
        logger.error("stream_for_a2a: failed to save conversation: %s", e)
