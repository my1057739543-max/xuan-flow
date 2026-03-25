"""Subagent configuration definition.

Mirrors deer-flow's SubagentConfig dataclass.
"""

from dataclasses import dataclass, field


@dataclass
class SubagentConfig:
    """Configuration for a sub-agent.

    Attributes:
        name: Unique identifier.
        description: When the lead agent should delegate to this sub-agent.
        system_prompt: System prompt guiding the sub-agent's behavior.
        tools: Optional allowlist of tool names. None = inherit all (except task).
        disallowed_tools: Tool names to always deny (defaults to ["task"]).
        model: Model name or "inherit" to use parent's model.
        max_turns: Max LangGraph recursion limit.
    """
    name: str
    description: str
    system_prompt: str
    tools: list[str] | None = None
    disallowed_tools: list[str] | None = field(default_factory=lambda: ["task"])
    model: str = "inherit"
    max_turns: int = 30
