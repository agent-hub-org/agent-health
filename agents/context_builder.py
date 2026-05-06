import asyncio
import logging
from datetime import datetime, timezone

from agent_sdk.database.memory import get_memories
from agent_sdk.memory import SemanticMemoryManager
from database.mongo import MongoDB

from .prompts import SYSTEM_PROMPT, RESPONSE_FORMAT_INSTRUCTIONS

logger = logging.getLogger("agent_health.context_builder")

# Inlined from agent_common.utils.text — update to agent_common import once submodule is added
_TRIVIAL_FOLLOWUPS: frozenset[str] = frozenset({
    "yes", "no", "sure", "ok", "okay", "please", "yes please",
    "no thanks", "proceed", "go ahead", "continue", "yeah", "yep",
})

_semantic_memory: SemanticMemoryManager | None = None


def _get_semantic_memory() -> SemanticMemoryManager:
    global _semantic_memory
    if _semantic_memory is None:
        _semantic_memory = SemanticMemoryManager()
    return _semantic_memory


def _build_system_prompt(response_format: str | None = None) -> str:
    fmt = RESPONSE_FORMAT_INSTRUCTIONS.get(response_format or "detailed", "")
    if fmt:
        return SYSTEM_PROMPT + "\n" + fmt
    return SYSTEM_PROMPT


async def _build_dynamic_context(
    session_id: str,
    query: str,
    response_format: str | None = None,
    user_id: str | None = None,
) -> str:
    """Build dynamic context block to prepend to user query.

    Injects: today's date, long-term memories, health profile, and format hints.
    Mem0 search and MongoDB profile fetch run in parallel via asyncio.gather().
    """
    mem_key = user_id or session_id
    is_trivial = query.strip().lower() in _TRIVIAL_FOLLOWUPS or len(query.strip()) <= 10

    async def _get_mem():
        if is_trivial:
            return [], None
        return await asyncio.to_thread(get_memories, user_id=mem_key, query=query)

    async def _get_profile():
        if not user_id:
            return None
        return await MongoDB.get_profile(user_id)

    (memories, mem_err), profile = await asyncio.gather(_get_mem(), _get_profile())

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    year = today[:4]

    parts = []
    parts.append(f"Today's date: {today}. Include the year ({year}) in search queries.")

    if user_id:
        parts.append(f"Current user_id: {user_id} — pass this to log_progress, get_progress_summary, and log_nutrition.")

    if memories:
        memory_lines = "\n".join(f"- {m}" for m in memories)
        parts.append(f"User context (long-term memory):\n{memory_lines}")
        logger.info("Injected %d memories into context for session='%s'", len(memories), session_id)

    if mem_err:
        parts.append(f"Note: {mem_err}")
        logger.warning("Mem0 degradation for session='%s': %s", session_id, mem_err)

    if profile:
        profile_parts = []
        if profile.get("goals"):
            profile_parts.append(f"Goals: {profile['goals']}")
        if profile.get("fitness_level"):
            profile_parts.append(f"Fitness level: {profile['fitness_level']}")
        if profile.get("available_equipment"):
            equip = profile["available_equipment"]
            equipment_str = ", ".join(equip) if isinstance(equip, list) else str(equip)
            profile_parts.append(f"Equipment: {equipment_str}")
        if profile.get("dietary_restrictions"):
            restrictions = profile["dietary_restrictions"]
            restrictions_str = ", ".join(restrictions) if isinstance(restrictions, list) else str(restrictions)
            profile_parts.append(f"Dietary restrictions: {restrictions_str}")
        if profile.get("injuries_or_limitations"):
            profile_parts.append(f"Injuries/limitations: {profile['injuries_or_limitations']}")
        if profile.get("age"):
            profile_parts.append(f"Age: {profile['age']}")
        if profile.get("weight_kg"):
            profile_parts.append(f"Weight: {profile['weight_kg']} kg")
        if profile.get("height_cm"):
            profile_parts.append(f"Height: {profile['height_cm']} cm")
        if profile.get("sessions_per_week"):
            profile_parts.append(f"Sessions per week: {profile['sessions_per_week']}")
        if profile.get("minutes_per_session"):
            profile_parts.append(f"Minutes per session: {profile['minutes_per_session']}")

        if profile_parts:
            parts.append(
                "[HEALTH_PROFILE]\n"
                + "\n".join(profile_parts)
                + "\n[/HEALTH_PROFILE]"
            )
            logger.info("Injected health profile into context for user='%s'", user_id)

    context_block = "\n\n".join(parts)
    return f"[CONTEXT]\n{context_block}\n[/CONTEXT]\n\n"
