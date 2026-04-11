import asyncio
import json
import logging
from typing import AsyncGenerator, Dict

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from xuan_flow.agents.lead_agent import make_lead_agent
from xuan_flow.agents.middlewares.memory_middleware import update_memory_background
from xuan_flow.tools.task_management import clear_tasks
from xuan_flow.utils.trace_logger import clear_trace

logger = logging.getLogger(__name__)
router = APIRouter()

# Track running tasks by thread_id
RUNNING_TASKS: Dict[str, asyncio.Task] = {}


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    # Thread ID for future session management
    thread_id: str | None = None
    # Optional model name override
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
        # ignoring other roles for now in simplified flow
    return lc_msgs


@router.post("/cancel")
async def cancel_chat(request: CancelRequest):
    """Cancel a running chat task for a given thread_id."""
    # Reset the task progress UI and performance trace
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
    # Clear previous task progress
    clear_tasks()
    
    thread_id = request.thread_id or "default-thread"
    
    # Check if a task is already running for this thread
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

    # Create and track the task
    task = asyncio.create_task(_run_agent())
    RUNNING_TASKS[thread_id] = task

    try:
        result = await task
        response_messages = result.get("messages", [])
        
        # Trigger background memory update
        if response_messages:
            background_tasks.add_task(update_memory_background, response_messages, request.thread_id)
            
        # Get the last AI message
        if response_messages and isinstance(response_messages[-1], AIMessage):
            content = response_messages[-1].content
            content_str = content if isinstance(content, str) else str(content)
            return {"role": "assistant", "content": content_str}
            
        return {"role": "assistant", "content": "No response generated."}

    except asyncio.CancelledError:
        return {"role": "assistant", "content": "任务已取消。"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup
        if RUNNING_TASKS.get(thread_id) == task:
            del RUNNING_TASKS[thread_id]


@router.post("/stream")
async def chat_stream(request: ChatRequest, background_tasks: BackgroundTasks):
    """Server-Sent Events (SSE) streaming endpoint."""
    # Clear previous task progress
    clear_tasks()
    
    thread_id = request.thread_id or "default-thread"
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
                "data": json.dumps({"status": "completed"})
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
                update_memory_background(
                    [*lc_messages, AIMessage(content=assistant_content)],
                    thread_id,
                )
            if RUNNING_TASKS.get(thread_id) == task:
                del RUNNING_TASKS[thread_id]
    return EventSourceResponse(_stream_generator())
