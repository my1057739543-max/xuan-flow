"""Task management tool for structured agent execution."""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Define the tasks file path
TASKS_FILE = Path.cwd() / ".xuan-flow" / "tasks.json"

@tool
def manage_tasks(tasks: List[Dict[str, Any]]) -> str:
    """Create or update the structured execution plan (Internal Todo List).
    
    INTERNAL TOOL ONLY: Using this tool updates the 'Execution Plan' UI panel.
    DO NOT explain or output the JSON content of this tool in your response text.
    
    Args:
        tasks: A list of task objects, e.g. [{"content": "Task 1", "status": "in_progress"}, ...]
        
    Returns:
        JSON string containing the updated task list.
    """
    try:
        # Ensure directory exists for Frontend sync
        TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=2, ensure_ascii=False)
            
        # Return structured JSON so the Graph can update the State
        return json.dumps({"tasks": tasks}, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error managing tasks: {e}")
        return f"Error: {e}"

@tool
def get_task_list() -> str:
    """Retrieve the current structured task list.
    
    Use this to remind yourself of your progress or what steps are remaining.
    """
    try:
        if not TASKS_FILE.exists():
            return "No active task list found. Create one with manage_tasks if needed."
            
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            tasks = json.load(f)
            
        formatted = "\n".join([f"- [{t.get('status', 'pending')}] {t.get('content')}" for t in tasks])
        return f"Current task list:\n{formatted}"
    except Exception as e:
        return f"Error reading tasks: {e}"

def clear_tasks():
    """Clear the tasks file to reset the progress UI."""
    try:
        if TASKS_FILE.exists():
            TASKS_FILE.unlink()
            return True
    except Exception as e:
        logger.error(f"Error clearing tasks: {e}")
    return False
