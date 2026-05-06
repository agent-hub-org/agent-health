from agent_common.config import CommonSettings
from agent_sdk.config import AgentSDKSettings


class Settings:
    """Composed settings — each layer keeps its own env semantics.

    pydantic-settings v2 replaces inherited model_config on subclassing,
    which silently drops AgentSDKSettings' AGENT_SDK_ env_prefix. Composing
    instead of inheriting preserves both: CommonSettings reads unprefixed
    infra vars, AgentSDKSettings reads AGENT_SDK_-prefixed agent vars.
    """

    def __init__(self) -> None:
        self._common = CommonSettings()
        self._sdk = AgentSDKSettings()

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        if hasattr(self._sdk, name):
            return getattr(self._sdk, name)
        if hasattr(self._common, name):
            return getattr(self._common, name)
        raise AttributeError(name)


settings = Settings()
