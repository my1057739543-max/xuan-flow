"""Trace persistence utility for performance monitoring."""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

TRACE_FILE = Path.cwd() / ".xuan-flow" / "trace.json"

def save_trace(trace: List[Dict[str, Any]]):
    """Save the execution trace to a file for frontend sync."""
    try:
        TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TRACE_FILE, "w", encoding="utf-8") as f:
            json.dump(trace, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error saving trace: {e}")

def get_trace() -> List[Dict[str, Any]]:
    """Retrieve the current execution trace."""
    try:
        if not TRACE_FILE.exists():
            return []
        with open(TRACE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading trace: {e}")
        return []

def clear_trace():
    """Clear the trace file."""
    try:
        if TRACE_FILE.exists():
            TRACE_FILE.unlink()
    except Exception as e:
        logger.error(f"Error clearing trace: {e}")
