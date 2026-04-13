"""Application settings via pydantic-settings.

Every setting can be overridden via environment variable with ``MAS_`` prefix
or via a ``.env`` file in the project root.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """MiCAR Compliance Agent configuration."""

    model_config = SettingsConfigDict(
        env_prefix="MAS_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # LLM provider
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    temperature: float = 0.0
    seed: int = 42

    # Prompt versioning
    prompt_version: str = "v1"

    # Rule engine
    rules_dir: Path = Path(__file__).parent / "rules" / "micar_v1"

    # Mock mode
    mock_mode: bool = False
    fixtures_dir: Path = Path("fixtures/mock_responses")

    # Audit logging
    audit_log_dir: Path = Path("audit_logs")
