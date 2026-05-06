import logging
import os

from agent_sdk.agents import BaseAgent
from agent_sdk.checkpoint import get_default_checkpointer
from tools.fitness_plan import generate_fitness_plan
from tools.progress_tracker import log_progress, get_progress_summary, log_nutrition

from .config import MCP_SERVERS
from .context_builder import _get_semantic_memory
from .prompts import SYSTEM_PROMPT

logger = logging.getLogger("agent_health.agent")

_agent_instance: BaseAgent | None = None


def create_agent() -> BaseAgent:
    global _agent_instance
    if _agent_instance is None:
        logger.info("Creating health agent (singleton) with MCP servers")
        _agent_instance = BaseAgent(
            tools=[generate_fitness_plan, log_progress, get_progress_summary, log_nutrition],
            mcp_servers=MCP_SERVERS,
            system_prompt=SYSTEM_PROMPT,
            checkpointer=get_default_checkpointer(os.getenv("MONGO_DB_NAME", "agent_health")),
            semantic_memory=_get_semantic_memory(),
        )
    return _agent_instance
