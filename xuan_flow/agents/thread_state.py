"""ThreadState — LangGraph state definition for Xuan-Flow.

Inspired by deer-flow's ThreadState but simplified:
- No sandbox/thread_data/uploaded_files/viewed_images
- Keep title for auto-generated conversation titles
"""

from typing import Annotated, NotRequired

from langgraph.prebuilt.chat_agent_executor import AgentState


def merge_artifacts(existing: list[str] | None, new: list[str] | None) -> list[str]:
    """Reducer for artifacts — merge and deduplicate."""
    if existing is None:
        return new or []
    if new is None:
        return existing
    return list(dict.fromkeys(existing + new))


def merge_trace(existing: list[dict] | None, new: list[dict] | None) -> list[dict]:
    """Reducer for execution trace — append only."""
    if existing is None:
        return new or []
    if new is None:
        return existing
    return existing + (new or [])


class ThreadState(AgentState):
    """Shared state across all nodes in the LangGraph agent.

    Extends AgentState (which provides `messages` with add-only reducer).
    """
    title: NotRequired[str | None]
    artifacts: Annotated[list[str], merge_artifacts]
    tasks: NotRequired[list[dict]]
    trace: Annotated[list[dict], merge_trace]
