"""Management endpoints for the Gateway API."""

import logging
from fastapi import APIRouter, HTTPException

from xuan_flow.config.app_config import get_app_config

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/config")
async def get_config():
    """Get the current loaded application configuration."""
    try:
        config = get_app_config()
        # Convert to dict and mask sensitive info if needed
        data = config.model_dump()
        return {"status": "success", "config": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available_models")
async def get_available_models():
    """List all configured LLM models."""
    try:
        config = get_app_config()
        return {
            "status": "success", 
            "models": [
                {"name": m.name, "display_name": m.display_name} 
                for m in config.models
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/skills")
async def get_skills():
    """List all available skills."""
    try:
        from xuan_flow.skills.loader import load_skills
        skills = load_skills()
        return {
            "status": "success",
            "skills": [
                {
                    "name": s.name,
                    "description": s.description,
                    "category": s.category,
                    "enabled": s.enabled,
                    "path": s.get_workspace_path()
                }
                for s in skills
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory")
async def get_memory():
    """Get all facts stored in memory."""
    try:
        from xuan_flow.memory.store import get_memory_data
        data = get_memory_data()
        return {
            "status": "success",
            "memory": data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/working-memory")
async def get_working_memory():
    """Get the current L2 working memory markdown content."""
    try:
        from xuan_flow.memory.store import get_working_memory_markdown
        content = get_working_memory_markdown()
        return {
            "status": "success",
            "working_memory": content,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/clear-atomic")
async def clear_atomic_memory():
    """Clear L1 atomic memory JSON only. Does not clear MySQL."""
    try:
        from xuan_flow.memory.store import clear_atomic_memory as clear_atomic_memory_store
        ok = clear_atomic_memory_store()
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to clear atomic memory")
        return {"status": "success", "detail": "Atomic memory cleared"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/memory/clear-working")
async def clear_working_memory():
    """Clear L2 memory.md only. Does not clear MySQL."""
    try:
        from xuan_flow.memory.store import clear_working_memory_markdown
        ok = clear_working_memory_markdown()
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to clear working memory")
        return {"status": "success", "detail": "Working memory markdown cleared"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools")
async def get_tools():
    """List all available tools (including MCP and Subagents)."""
    try:
        from xuan_flow.tools.registry import get_available_tools
        # Enable subagents to see all tools available to the Lead Agent
        tools = await get_available_tools(subagent_enabled=True)
        return {
            "status": "success",
            "tools": [{"name": t.name, "description": t.description} for t in tools]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks")
async def get_tasks():
    """Get the current structured task list (todo list)."""
    try:
        from xuan_flow.tools.task_management import TASKS_FILE
        import json
        if not TASKS_FILE.exists():
            return {"status": "success", "tasks": []}
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            tasks = json.load(f)
        return {"status": "success", "tasks": tasks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance")
async def get_performance():
    """Get the current execution trace (performance metrics)."""
    try:
        from xuan_flow.utils.trace_logger import get_trace
        trace = get_trace()
        return {"status": "success", "performance": trace}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
