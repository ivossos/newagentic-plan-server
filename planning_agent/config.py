"""Configuration module using Pydantic Settings."""

from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class PlanningConfig(BaseSettings):
    """Planning configuration with environment variable validation."""

    # Planning Connection (optional in mock mode)
    planning_url: Optional[str] = Field(None, alias="PLANNING_URL")
    planning_username: Optional[str] = Field(None, alias="PLANNING_USERNAME")
    planning_password: Optional[str] = Field(None, alias="PLANNING_PASSWORD")
    planning_api_version: str = Field("v3", alias="PLANNING_API_VERSION")
    planning_mock_mode: bool = Field(False, alias="PLANNING_MOCK_MODE")
    planning_skip_confirmation: bool = Field(False, alias="PLANNING_SKIP_CONFIRMATION")

    # Database (SQLite for sessions + feedback + RL)
    database_url: str = Field(
        "sqlite:///./planning_agent.db",
        alias="DATABASE_URL"
    )

    # Models - Claude Agent SDK
    anthropic_api_key: Optional[str] = Field(None, alias="ANTHROPIC_API_KEY")
    claude_model: str = Field("claude-opus-4-5-20251101", alias="CLAUDE_MODEL")

    # Server
    fastmcp_host: str = Field("127.0.0.1", alias="FASTMCP_HOST")
    fastmcp_port: int = Field(8001, alias="FASTMCP_PORT")

    # Reinforcement Learning Configuration
    rl_enabled: bool = Field(True, alias="RL_ENABLED")
    rl_exploration_rate: float = Field(0.1, alias="RL_EXPLORATION_RATE")
    rl_learning_rate: float = Field(0.3, alias="RL_LEARNING_RATE")
    rl_discount_factor: float = Field(0.95, alias="RL_DISCOUNT_FACTOR")
    rl_min_samples: int = Field(3, alias="RL_MIN_SAMPLES")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
        "populate_by_name": True,
    }


def load_config() -> PlanningConfig:
    """Load and validate configuration from environment variables."""
    return PlanningConfig()


# Global config instance
try:
    config = load_config()
except Exception as e:
    import warnings
    warnings.warn(f"Config loading failed: {e}. Using default mock mode configuration.", UserWarning)
    config = PlanningConfig(
        planning_mock_mode=True,
        database_url="sqlite:///./data/planning_agent.db"
    )
