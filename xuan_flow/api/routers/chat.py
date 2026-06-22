import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from xuan_flow.agents.lead_agent import make_lead_agent
from xuan_flow.agents.middlewares.memory_middleware import update_memory_background
from xuan_flow.sessions.store import (
    list_sessions,
    get_session,
    save_session,
    delete_session,
    generate_session_id,
)
from xuan_flow.tools.task_management import clear_tasks
from xuan_flow.utils.trace_logger import clear_trace

logger = logging.getLogger(__name__)
router = APIRouter()

# Track running tasks by thread_id
RUNNING_TASKS: dict[str, asyncio.Task] = {}


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    thread_id: str | None = None
    model: str | None = None


class CancelRequest(BaseModel):
    thread_id: str


def _convert_messages(api_msgs: list[ChatMessage]) -> list[BaseMessage]:
    """Convert API messages to LangChain messages."""
    lc_msgs = []
    for m in api_msgs:
        if m.role == "user":
            lc_msgs.append(HumanMessage(content=m.content))
        elif m.role == "assistant":
            lc_msgs.append(AIMessage(content=m.content))
    return lc_msgs


def _to_api_messages(lc_msgs: list[BaseMessage]) -> list[dict]:
    """Convert LangChain messages to API-friendly dict list."""
    result = []
    for m in lc_msgs:
        role = "user" if isinstance(m, HumanMessage) else "assistant"
        content = m.content if isinstance(m.content, str) else str(m.content)
        result.append({"role": role, "content": content})
    return result


def _auto_save_session(thread_id: str, api_messages: list[dict]) -> None:
    """Persist session to disk after a conversation turn."""
    try:
        save_session(thread_id, api_messages)
    except Exception as e:
        logger.warning("Failed to auto-save session %s: %s", thread_id, e)


# ── Session Management Endpoints ──────────────────────────────────────────


@router.get("/sessions")
async def list_all_sessions():
    """Return all saved sessions (lightweight index)."""
    return {"sessions": list_sessions()}


@router.get("/sessions/{session_id}")
async def get_session_by_id(session_id: str):
    """Return a full session including messages."""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/sessions/{session_id}")
async def delete_session_by_id(session_id: str):
    """Delete a session."""
    ok = delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}


# ── Chat Endpoints ────────────────────────────────────────────────────────


@router.post("/cancel")
async def cancel_chat(request: CancelRequest):
    """Cancel a running chat task for a given thread_id."""
    clear_tasks()
    clear_trace()

    thread_id = request.thread_id
    if thread_id in RUNNING_TASKS:
        task = RUNNING_TASKS[thread_id]
        task.cancel()
        logger.info("Cancelled task for thread: %s", thread_id)
        return {"status": "cancelled", "thread_id": thread_id}
    return {"status": "not_found", "thread_id": thread_id}


@router.post("/sync")
async def chat_sync(request: ChatRequest, background_tasks: BackgroundTasks):
    """Synchronous chat endpoint (waits for full response)."""
    clear_tasks()

    thread_id = request.thread_id or generate_session_id()

    if thread_id in RUNNING_TASKS and not RUNNING_TASKS[thread_id].done():
        logger.warning("Task already running for thread %s, cancelling old one", thread_id)
        RUNNING_TASKS[thread_id].cancel()

    async def _run_agent():
        try:
            agent = await make_lead_agent(model_name=request.model)
            lc_messages = _convert_messages(request.messages)
            if not lc_messages:
                raise ValueError("No messages provided")

            result = await agent.ainvoke(
                {"messages": lc_messages},
                config={"recursion_limit": 50}
            )
            return result
        except asyncio.CancelledError:
            logger.info("Agent task cancelled")
            raise
        except Exception as e:
            logger.exception("Agent invocation failed")
            raise e

    task = asyncio.create_task(_run_agent())
    RUNNING_TASKS[thread_id] = task

    try:
        result = await task
        response_messages = result.get("messages", [])

        if response_messages:
            background_tasks.add_task(update_memory_background, response_messages, request.thread_id)

        if response_messages and isinstance(response_messages[-1], AIMessage):
            content = response_messages[-1].content
            content_str = content if isinstance(content, str) else str(content)

            # Auto-save session
            all_msgs = _to_api_messages(_convert_messages(request.messages))
            all_msgs.append({"role": "assistant", "content": content_str})
            _auto_save_session(thread_id, all_msgs)

            return {"role": "assistant", "content": content_str, "thread_id": thread_id}

        return {"role": "assistant", "content": "No response generated.", "thread_id": thread_id}

    except asyncio.CancelledError:
        return {"role": "assistant", "content": "任务已取消。", "thread_id": thread_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if RUNNING_TASKS.get(thread_id) == task:
            del RUNNING_TASKS[thread_id]


@router.post("/stream")
async def chat_stream(request: ChatRequest, background_tasks: BackgroundTasks):
    """Server-Sent Events (SSE) streaming endpoint."""
    clear_tasks()

    thread_id = request.thread_id or generate_session_id()
    lc_messages = _convert_messages(request.messages)
    if not lc_messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    async def _stream_generator() -> AsyncGenerator[dict, None]:
        task = asyncio.current_task()
        RUNNING_TASKS[thread_id] = task
        assistant_content = ""

        try:
            agent = await make_lead_agent(model_name=request.model)

            async for chunk, metadata in agent.astream(
                {"messages": lc_messages},
                stream_mode="messages",
                config={"recursion_limit": 50}
            ):
                if isinstance(chunk, AIMessage) and chunk.content:
                    chunk_content = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                    assistant_content += chunk_content
                    yield {
                        "event": "message",
                        "data": json.dumps({"content": chunk_content})
                    }

            yield {
                "event": "done",
                "data": json.dumps({"status": "completed", "thread_id": thread_id})
            }

        except asyncio.CancelledError:
            logger.info("Stream task cancelled for thread %s", thread_id)
            yield {
                "event": "message",
                "data": json.dumps({"content": "\n\n*任务已取消*"})
            }
        except Exception as e:
            logger.exception("Streaming failed")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)})
            }
        finally:
            if assistant_content.strip() and lc_messages:
                # Auto-save session
                api_msgs = _to_api_messages(lc_messages)
                api_msgs.append({"role": "assistant", "content": assistant_content})
                _auto_save_session(thread_id, api_msgs)

                update_memory_background(
                    [*lc_messages, AIMessage(content=assistant_content)],
                    thread_id,
                )
            if RUNNING_TASKS.get(thread_id) == task:
                del RUNNING_TASKS[thread_id]

    return EventSourceResponse(_stream_generator())
