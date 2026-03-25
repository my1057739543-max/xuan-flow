"""Application configuration — reads config.yaml and resolves $ENV variables.

Inspired by deer-flow's config system with singleton caching and auto-reload.
"""

import logging
import os
from pathlib import Path
from typing import Any, Self

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

load_dotenv()

logger = logging.getLogger(__name__)


# ── Model Configuration ──────────────────────────────────────────────────────

class ModelConfig(BaseModel):
    """Configuration for a single LLM model."""
    name: str
    display_name: str = ""
    model: str = ""
    api_key: str = ""
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096

    model_config = ConfigDict(extra="allow")


# ── Memory Configuration ─────────────────────────────────────────────────────

class MemoryConfig(BaseModel):
    """Configuration for the memory system."""
    enabled: bool = True
    storage_path: str = ".xuan-flow/memory.json"
    max_facts: int = 50
    max_injection_facts: int = 10

    model_config = ConfigDict(extra="allow")


# ── Subagents Configuration ──────────────────────────────────────────────────

class SubagentsConfig(BaseModel):
    """Configuration for the subagent system."""
    enabled: bool = True

    model_config = ConfigDict(extra="allow")


# ── App Configuration ────────────────────────────────────────────────────────

class AppConfig(BaseModel):
    """Top-level application configuration."""
    models: list[ModelConfig] = Field(default_factory=list)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    subagents: SubagentsConfig = Field(default_factory=SubagentsConfig)
    mcp_servers: dict[str, dict[str, Any]] | None = Field(default_factory=dict, description="MCP servers configuration")

    model_config = ConfigDict(extra="allow", frozen=False)

    @classmethod
    def resolve_config_path(cls, config_path: str | None = None) -> Path:
        """Resolve config file path.

        Priority:
        1. Explicit config_path argument
        2. XUAN_FLOW_CONFIG_PATH env var
        3. config.yaml in CWD
        4. config.yaml in parent directory
        """
        if config_path:
            path = Path(config_path)
            if not path.exists():
                raise FileNotFoundError(f"Config file not found: {path}")
            return path

        env_path = os.getenv("XUAN_FLOW_CONFIG_PATH")
        if env_path:
            path = Path(env_path)
            if not path.exists():
                raise FileNotFoundError(f"Config file from XUAN_FLOW_CONFIG_PATH not found: {path}")
            return path

        # Check CWD, then parent
        for candidate in [Path.cwd() / "config.yaml", Path.cwd().parent / "config.yaml"]:
            if candidate.exists():
                return candidate

        raise FileNotFoundError("config.yaml not found in current or parent directory")

    @classmethod
    def resolve_env_variables(cls, config: Any) -> Any:
        """Recursively resolve $ENV_VAR references in config values."""
        if isinstance(config, str):
            if config.startswith("$"):
                env_name = config[1:]
                env_value = os.getenv(env_name)
                if env_value is None:
                    logger.warning("Environment variable %s not set (referenced as %s)", env_name, config)
                    return ""
                return env_value
            return config
        elif isinstance(config, dict):
            return {k: cls.resolve_env_variables(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [cls.resolve_env_variables(item) for item in config]
        return config

    @classmethod
    def from_file(cls, config_path: str | None = None) -> Self:
        """Load configuration from YAML file."""
        # Reload .env to pick up any changes while the server is running
        load_dotenv(override=True)
        
        resolved_path = cls.resolve_config_path(config_path)
        with open(resolved_path, encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}

        config_data = cls.resolve_env_variables(config_data)
        return cls.model_validate(config_data)

    def get_model_config(self, name: str) -> ModelConfig | None:
        """Get model config by name."""
        return next((m for m in self.models if m.name == name), None)


# ── Singleton Cache ──────────────────────────────────────────────────────────

_app_config: AppConfig | None = None
_app_config_path: Path | None = None
_app_config_mtime: float | None = None


def get_app_config(config_path: str | None = None) -> AppConfig:
    """Get the cached AppConfig singleton, auto-reload on file change."""
    global _app_config, _app_config_path, _app_config_mtime

    try:
        resolved_path = AppConfig.resolve_config_path(config_path)
    except FileNotFoundError:
        if _app_config is not None:
            return _app_config
        raise

    try:
        current_mtime = resolved_path.stat().st_mtime
    except OSError:
        current_mtime = None

    if (
        _app_config is None
        or _app_config_path != resolved_path
        or _app_config_mtime != current_mtime
    ):
        _app_config = AppConfig.from_file(str(resolved_path))
        _app_config_path = resolved_path
        _app_config_mtime = current_mtime

    return _app_config


def reset_app_config() -> None:
    """Clear the singleton cache (useful for testing)."""
    global _app_config, _app_config_path, _app_config_mtime
    _app_config = None
    _app_config_path = None
    _app_config_mtime = None
