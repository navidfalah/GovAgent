"""Configuration API routes."""

from fastapi import APIRouter
from pydantic import BaseModel

from govagents.core.config_manager import DynamicConfig, get_config_manager

router = APIRouter(prefix="/api/config", tags=["config"])


class ConfigUpdate(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_temperature: float | None = None
    llm_max_tokens: int | None = None
    gemini_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    groq_api_key: str | None = None
    agent_configs: dict[str, dict] | None = None


@router.get("", response_model=DynamicConfig)
async def get_config() -> DynamicConfig:
    """Get current dynamic configuration."""
    mgr = get_config_manager()
    return mgr.get_config()


@router.post("", response_model=DynamicConfig)
async def update_config(update: ConfigUpdate) -> DynamicConfig:
    """Update dynamic configuration."""
    mgr = get_config_manager()
    current = mgr.get_config()
    
    # Update fields that were provided
    update_data = update.model_dump(exclude_unset=True)
    new_config_data = current.model_dump()
    new_config_data.update(update_data)
    
    new_config = DynamicConfig(**new_config_data)
    mgr.save_config(new_config)
    
    return new_config
