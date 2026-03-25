"""Sub-agent registry — lookup available sub-agents by name."""

from xuan_flow.subagents.builtins import BUILTIN_SUBAGENTS
from xuan_flow.subagents.config import SubagentConfig


def get_subagent_config(name: str) -> SubagentConfig | None:
    """Get a sub-agent configuration by name."""
    return BUILTIN_SUBAGENTS.get(name)


def list_subagents() -> list[SubagentConfig]:
    """List all available sub-agent configurations."""
    return list(BUILTIN_SUBAGENTS.values())


def get_subagent_names() -> list[str]:
    """Get all available sub-agent names."""
    return list(BUILTIN_SUBAGENTS.keys())
