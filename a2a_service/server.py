import logging

from agent_sdk.a2a.factory import create_a2a_app as _create

from .agent_card import HEALTH_AGENT_CARD
from .executor import HealthAgentExecutor

logger = logging.getLogger("agent_health.a2a_server")


def create_a2a_app():
    """Build the A2A Starlette application for the health agent."""
    app = _create(HEALTH_AGENT_CARD, HealthAgentExecutor, "agent_health")
    logger.info("A2A application created for Health Agent")
    return app
