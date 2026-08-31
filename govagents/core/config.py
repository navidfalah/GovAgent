"""Application configuration via Pydantic Settings."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """GovAgents application settings.

    Values are loaded from (in order of priority):
    1. Environment variables
    2. .env file
    3. configs/default.yaml
    4. Hardcoded defaults
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ───────────────────────────────────────────────────────────────────
    llm_provider: Literal["gemini", "openai", "anthropic", "groq", "ollama"] = "gemini"
    llm_model: str = "gemini/gemini-2.0-flash"
    llm_base_url: str | None = None
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096
    llm_timeout: int = 120

    # API Keys (passed through env)
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")

    # ── Vector DB ─────────────────────────────────────────────────────────────
    chroma_path: Path = Path("./data/chroma")
    chroma_collection: str = "govagents_policies"

    # ── Embeddings ────────────────────────────────────────────────────────────
    embedding_model: str = "all-MiniLM-L6-v2"

    # ── Policy Retrieval ─────────────────────────────────────────────────────
    retrieval_top_k: int = 5
    policy_sources_path: Path = Path("govagents/policies/sources")

    # ── Governance Engine ─────────────────────────────────────────────────────
    abstention_threshold: float = 0.45
    max_debate_rounds: int = 2
    disagreement_threshold: float = 0.3  # min confidence gap to trigger debate

    # ── Mini-Agent Swarms ─────────────────────────────────────────────────────
    mini_agents_per_module: int = 5  # target team size per governance module
    mini_agent_max_concurrency: int = 8  # global cap on concurrent mini-agent LLM calls
    enable_mini_agent_web_search: bool = True

    # ── Cross-Module Logic Gates ──────────────────────────────────────────────
    evidence_sufficiency_threshold: float = 0.4  # min avg mini-agent certainty before a clean approval
    correlated_concern_min_modules: int = 3  # modules independently flagging the same concern to escalate

    # ── API ───────────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: list[str] = ["*"]

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["console", "json"] = "console"

    # ── Storage ───────────────────────────────────────────────────────────────
    assessments_path: Path = Path("./data/assessments")

    @field_validator("chroma_path", "assessments_path", mode="before")
    @classmethod
    def ensure_path(cls, v: str | Path) -> Path:
        return Path(v)

    def get_litellm_model(self) -> str:
        """Return the model identifier for LiteLLM."""
        return self.llm_model

    def get_api_key(self) -> str | None:
        """Return the API key for the configured provider."""
        mapping = {
            "gemini": self.gemini_api_key,
            "openai": self.openai_api_key,
            "anthropic": self.anthropic_api_key,
            "groq": self.groq_api_key,
            "ollama": None,
        }
        return mapping.get(self.llm_provider)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Settings":
        """Load settings from a YAML file merged with env vars."""
        yaml_path = Path(path)
        if yaml_path.exists():
            with open(yaml_path) as f:
                yaml_data = yaml.safe_load(f) or {}
        else:
            yaml_data = {}
        return cls(**yaml_data)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
