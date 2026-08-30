"""Dynamic configuration manager for UI-driven settings."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from govagents.core.config import get_settings
from govagents.core.logging import get_logger

log = get_logger(__name__)


class DynamicConfig(BaseModel):
    """Configuration structure stored in JSON."""
    llm_provider: str = "gemini"
    llm_model: str = "gemini/gemini-2.0-flash"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    groq_api_key: str | None = None
    agent_prompts: dict[str, str] = {}


class DynamicSettingsManager:
    """Manages reading and writing dynamic UI settings."""

    def __init__(self, config_path: Path | None = None) -> None:
        settings = get_settings()
        self.config_path = config_path or Path("./data/ui_config.json")
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: DynamicConfig | None = None

    def get_config(self) -> DynamicConfig:
        """Load configuration from disk, falling back to static settings."""
        if self._cache:
            return self._cache

        if self.config_path.exists():
            try:
                with open(self.config_path) as f:
                    data = json.load(f)
                self._cache = DynamicConfig(**data)
                return self._cache
            except Exception as e:
                log.error("failed_to_load_ui_config", error=str(e))

        # Fallback to defaults from env/static settings
        static = get_settings()
        self._cache = DynamicConfig(
            llm_provider=static.llm_provider,
            llm_model=static.llm_model,
            llm_temperature=static.llm_temperature,
            llm_max_tokens=static.llm_max_tokens,
            gemini_api_key=static.gemini_api_key,
            openai_api_key=static.openai_api_key,
            anthropic_api_key=static.anthropic_api_key,
            groq_api_key=static.groq_api_key,
            agent_prompts={},
        )
        return self._cache

    def save_config(self, config: DynamicConfig) -> None:
        """Save configuration to disk."""
        try:
            with open(self.config_path, "w") as f:
                f.write(config.model_dump_json(indent=2))
            self._cache = config
            log.info("ui_config_saved")
        except Exception as e:
            log.error("failed_to_save_ui_config", error=str(e))
            raise


_manager: DynamicSettingsManager | None = None


def get_config_manager() -> DynamicSettingsManager:
    """Return the global DynamicSettingsManager singleton."""
    global _manager
    if _manager is None:
        _manager = DynamicSettingsManager()
    return _manager
