"""Memory store — JSON file read/write with caching.

Simplified from deer-flow: only facts list, no user/history multi-dimensional structure.
Keeps atomic write (temp file + rename) from deer-flow.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from xuan_flow.config.app_config import get_app_config

logger = logging.getLogger(__name__)

# ── Cache ────────────────────────────────────────────────────────────────────

_memory_cache: tuple[dict[str, Any], float | None] | None = None


def _get_memory_path() -> Path:
    """Get the path to memory.json from config."""
    config = get_app_config()
    return Path(config.memory.storage_path)


def _create_empty_memory() -> dict[str, Any]:
    """Create an empty memory structure."""
    return {
        "version": "1.0",
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "facts": [],
    }


def get_memory_data() -> dict[str, Any]:
    """Get memory data (cached, auto-invalidates on file change)."""
    global _memory_cache

    file_path = _get_memory_path()

    try:
        current_mtime = file_path.stat().st_mtime if file_path.exists() else None
    except OSError:
        current_mtime = None

    if _memory_cache is not None:
        cached_data, cached_mtime = _memory_cache
        if cached_mtime == current_mtime:
            return cached_data

    # Load from file
    data = _load_from_file(file_path)
    _memory_cache = (data, current_mtime)
    return data


def reload_memory_data() -> dict[str, Any]:
    """Force reload memory from file."""
    global _memory_cache
    _memory_cache = None
    return get_memory_data()


def save_memory_data(memory_data: dict[str, Any]) -> bool:
    """Save memory data atomically (temp + rename).

    Atomic write pattern from deer-flow to prevent corruption.
    """
    global _memory_cache

    file_path = _get_memory_path()

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        memory_data["lastUpdated"] = datetime.now(timezone.utc).isoformat()

        # Atomic write: temp file → rename
        temp_path = file_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(memory_data, f, indent=2, ensure_ascii=False)
        temp_path.replace(file_path)

        # Update cache
        try:
            mtime = file_path.stat().st_mtime
        except OSError:
            mtime = None
        _memory_cache = (memory_data, mtime)

        logger.info("Memory saved to %s (%d facts)", file_path, len(memory_data.get("facts", [])))
        return True

    except OSError as e:
        logger.error("Failed to save memory: %s", e)
        return False


def _load_from_file(file_path: Path) -> dict[str, Any]:
    """Load memory from JSON file."""
    if not file_path.exists():
        return _create_empty_memory()

    try:
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load memory file: %s", e)
        return _create_empty_memory()


def format_memory_for_injection(memory_data: dict[str, Any], max_facts: int = 10) -> str:
    """Format memory facts for injection into system prompt."""
    facts = memory_data.get("facts", [])
    if not facts:
        return ""

    # Sort by confidence descending, take top N
    sorted_facts = sorted(facts, key=lambda f: f.get("confidence", 0), reverse=True)[:max_facts]

    lines = ["Here's what you remember about the user from past conversations:"]
    for fact in sorted_facts:
        content = fact.get("content", "")
        category = fact.get("category", "")
        lines.append(f"- [{category}] {content}")

    return "\n".join(lines)
