"""task() tool — delegates a sub-task to a sub-agent.

This is the bridge between the Lead Agent and the Sub-Agent system.
The Lead Agent calls task() when it decides to decompose work.
"""

import logging
from typing import Literal

from langchain_core.tools import tool

from xuan_flow.subagents.executor import SubagentExecutor
from xuan_flow.subagents.registry import get_subagent_config, get_subagent_names

logger = logging.getLogger(__name__)


@tool
async def task(
    description: str,
    prompt: str,
    subagent_type: str = "researcher",
) -> str:
    """Delegate a sub-task to a specialized sub-agent for execution.

    Use this when the user's request requires specialized work that can be
    decomposed. Each sub-agent runs in isolation with its own context.

    Args:
        description: Brief description of what this sub-task is about (shown to user).
        prompt: Detailed instructions for the sub-agent to follow.
        subagent_type: Which sub-agent to use. Options: "researcher" (web research),
                       "coder" (code generation/review).

    Returns:
        The sub-agent's result as text.
    """
    # Validate subagent type
    config = get_subagent_config(subagent_type)
    if config is None:
        available = ", ".join(get_subagent_names())
        return f"Error: Unknown sub-agent type '{subagent_type}'. Available: {available}"

    logger.info("Task delegated to '%s': %s", subagent_type, description)

    # Execute with isolated context
    executor = SubagentExecutor(config=config)
    result = await executor.execute(task=prompt)

    if result.error:
        return f"Sub-agent '{subagent_type}' failed: {result.error}"

    return result.result or "Sub-agent completed but returned no output."
