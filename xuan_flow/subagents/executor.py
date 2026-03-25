"""Sub-agent execution engine.

Simplified from deer-flow: synchronous sequential execution instead of
dual thread pool with async/timeout. Each sub-agent runs in its own
isolated context (key design from deer-flow).
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from xuan_flow.agents.thread_state import ThreadState
from xuan_flow.models.factory import create_chat_model
from xuan_flow.subagents.config import SubagentConfig
from xuan_flow.tools.registry import get_available_tools

logger = logging.getLogger(__name__)


class SubagentStatus(Enum):
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SubagentResult:
    """Result of a sub-agent execution."""
    task_id: str
    status: SubagentStatus
    result: str | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


def _filter_tools(all_tools, allowed: list[str] | None, disallowed: list[str] | None):
    """Filter tools based on sub-agent config."""
    filtered = all_tools
    if allowed is not None:
        allowed_set = set(allowed)
        filtered = [t for t in filtered if t.name in allowed_set]
    if disallowed is not None:
        disallowed_set = set(disallowed)
        filtered = [t for t in filtered if t.name not in disallowed_set]
    return filtered


class SubagentExecutor:
    """Executes a sub-agent with its own isolated context."""

    def __init__(self, config: SubagentConfig, parent_model: str | None = None):
        self.config = config
        self.parent_model = parent_model

    async def execute(self, task: str) -> SubagentResult:
        """Execute a task asynchronously with isolated context.

        Key design from deer-flow: the sub-agent gets a FRESH state with only
        the task description — no Lead Agent history leaks in.
        """
        task_id = str(uuid.uuid4())[:8]
        result = SubagentResult(
            task_id=task_id,
            status=SubagentStatus.COMPLETED,
            started_at=datetime.now(),
        )

        try:
            from langgraph.prebuilt import create_react_agent
            from xuan_flow.tools.registry import get_available_tools

            # Resolve model
            model_name = self.parent_model if self.config.model == "inherit" else self.config.model
            model = create_chat_model(name=model_name)

            # Get all tools (excluding task to prevent recursion), then filter
            all_tools = await get_available_tools(subagent_enabled=False, exclude_task=True)
            tools = _filter_tools(all_tools, self.config.tools, self.config.disallowed_tools)

            # Create agent with isolated context
            agent = create_react_agent(
                model=model,
                tools=tools,
                prompt=self.config.system_prompt,
                state_schema=ThreadState,
            )

            # CRITICAL: Fresh state — only the task, no parent history
            state = {"messages": [HumanMessage(content=task)]}

            logger.info("[%s] Sub-agent '%s' starting: %s", task_id, self.config.name, task[:100])

            # Asynchronous execution
            final_state = await agent.ainvoke(state, config={"recursion_limit": self.config.max_turns})

            # Extract final AI message
            messages = final_state.get("messages", [])
            last_ai = None
            for msg in reversed(messages):
                if isinstance(msg, AIMessage):
                    last_ai = msg
                    break

            if last_ai is not None:
                content = last_ai.content
                result.result = content if isinstance(content, str) else str(content)
            else:
                result.result = "No response generated."

            result.status = SubagentStatus.COMPLETED
            logger.info("[%s] Sub-agent '%s' completed", task_id, self.config.name)

        except Exception as e:
            logger.exception("[%s] Sub-agent '%s' failed", task_id, self.config.name)
            result.status = SubagentStatus.FAILED
            result.error = str(e)

        result.completed_at = datetime.now()
        return result
