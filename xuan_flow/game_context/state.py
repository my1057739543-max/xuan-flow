"""Persistent multi-game context store.

The store is intentionally separate from chat history and atomic long-term
memory. It tracks the player's current per-game progress state across turns.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STORE_FILE = Path.cwd() / ".xuan-flow" / "game_sessions.json"
DEFAULT_THREAD_ID = "default"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_game_id(value: str) -> str:
    """Convert a game name/alias into a stable lowercase id."""
    text = (value or "").strip().lower()
    if not text:
        raise ValueError("game_id or display_name is required")
    alias_map = {
        "锈湖": "rusty-lake",
        "绣湖": "rusty-lake",
        "rusty lake": "rusty-lake",
        "the room": "the-room",
        "未上锁的房间": "the-room",
        "机械迷城": "machinarium",
        "machinarium": "machinarium",
        "纸嫁衣": "paper-bride",
    }
    if text in alias_map:
        return alias_map[text]
    normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text).strip("-")
    return normalized or text


def list_game_contexts(thread_id: str = DEFAULT_THREAD_ID) -> dict[str, Any]:
    """Return all game contexts under one thread."""
    store = _load_store()
    thread = _ensure_thread(store, thread_id)
    return {
        "thread_id": thread_id,
        "active_game_id": thread.get("active_game_id"),
        "games": thread.get("games", {}),
    }


def get_game_context(
    game_id: str | None = None,
    *,
    thread_id: str = DEFAULT_THREAD_ID,
) -> dict[str, Any]:
    """Return one game context, defaulting to the active game."""
    store = _load_store()
    thread = _ensure_thread(store, thread_id)
    resolved_game_id = normalize_game_id(game_id) if game_id else thread.get("active_game_id")
    if not resolved_game_id:
        return {
            "thread_id": thread_id,
            "active_game_id": None,
            "context": None,
            "missing": ["game"],
        }

    context = thread.get("games", {}).get(resolved_game_id)
    return {
        "thread_id": thread_id,
        "active_game_id": thread.get("active_game_id"),
        "game_id": resolved_game_id,
        "context": context,
        "missing": _missing_core_fields(context),
    }


def update_game_context(
    *,
    game_id: str | None = None,
    display_name: str | None = None,
    thread_id: str = DEFAULT_THREAD_ID,
    set_active: bool = True,
    chapter: str | None = None,
    location: str | None = None,
    current_puzzle: str | None = None,
    inventory: list[str] | None = None,
    add_inventory: list[str] | None = None,
    remove_inventory: list[str] | None = None,
    spoiler_preference: str | None = None,
    solved_puzzles: list[str] | None = None,
    add_solved_puzzles: list[str] | None = None,
    notes: str | None = None,
    aliases: list[str] | None = None,
    last_user_query: str | None = None,
) -> dict[str, Any]:
    """Create or patch a game context under a thread."""
    resolved_game_id = normalize_game_id(game_id or display_name or "")
    store = _load_store()
    thread = _ensure_thread(store, thread_id)
    games = thread.setdefault("games", {})
    context = games.setdefault(resolved_game_id, _empty_game_context(resolved_game_id, display_name))

    if display_name:
        context["display_name"] = display_name
    if aliases is not None:
        context["aliases"] = _dedupe([*context.get("aliases", []), *aliases])
    if chapter is not None:
        context["chapter"] = chapter
    if location is not None:
        context["location"] = location
    if current_puzzle is not None:
        context["current_puzzle"] = current_puzzle
    if inventory is not None:
        context["inventory"] = _dedupe(inventory)
    if add_inventory:
        context["inventory"] = _dedupe([*context.get("inventory", []), *add_inventory])
    if remove_inventory:
        remove_set = set(remove_inventory)
        context["inventory"] = [item for item in context.get("inventory", []) if item not in remove_set]
    if spoiler_preference is not None:
        context["spoiler_preference"] = spoiler_preference
    if solved_puzzles is not None:
        context["solved_puzzles"] = _dedupe(solved_puzzles)
    if add_solved_puzzles:
        context["solved_puzzles"] = _dedupe([*context.get("solved_puzzles", []), *add_solved_puzzles])
    if notes is not None:
        context["notes"] = notes
    if last_user_query is not None:
        context["last_user_query"] = last_user_query

    context["updated_at"] = _now()
    if set_active:
        thread["active_game_id"] = resolved_game_id
    thread["updated_at"] = _now()
    _save_store(store)

    return {
        "thread_id": thread_id,
        "active_game_id": thread.get("active_game_id"),
        "game_id": resolved_game_id,
        "context": context,
        "missing": _missing_core_fields(context),
    }


def clear_game_context(
    game_id: str | None = None,
    *,
    thread_id: str = DEFAULT_THREAD_ID,
) -> dict[str, Any]:
    """Clear one game context, or all contexts for a thread when game_id is omitted."""
    store = _load_store()
    thread = _ensure_thread(store, thread_id)
    if game_id:
        resolved_game_id = normalize_game_id(game_id)
        thread.get("games", {}).pop(resolved_game_id, None)
        if thread.get("active_game_id") == resolved_game_id:
            thread["active_game_id"] = None
    else:
        thread["active_game_id"] = None
        thread["games"] = {}
    thread["updated_at"] = _now()
    _save_store(store)
    return list_game_contexts(thread_id)


def _empty_store() -> dict[str, Any]:
    return {"version": "1.0", "threads": {}}


def _empty_game_context(game_id: str, display_name: str | None) -> dict[str, Any]:
    return {
        "game_id": game_id,
        "display_name": display_name or game_id,
        "aliases": _dedupe([display_name, game_id] if display_name else [game_id]),
        "chapter": None,
        "location": None,
        "inventory": [],
        "current_puzzle": None,
        "spoiler_preference": None,
        "solved_puzzles": [],
        "notes": None,
        "last_user_query": None,
        "created_at": _now(),
        "updated_at": _now(),
    }


def _load_store() -> dict[str, Any]:
    if not STORE_FILE.exists():
        return _empty_store()
    try:
        with STORE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("threads"), dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return _empty_store()


def _save_store(store: dict[str, Any]) -> None:
    STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, ensure_ascii=False)
    tmp.replace(STORE_FILE)


def _ensure_thread(store: dict[str, Any], thread_id: str) -> dict[str, Any]:
    threads = store.setdefault("threads", {})
    return threads.setdefault(
        thread_id or DEFAULT_THREAD_ID,
        {
            "active_game_id": None,
            "games": {},
            "created_at": _now(),
            "updated_at": _now(),
        },
    )


def _missing_core_fields(context: dict[str, Any] | None) -> list[str]:
    if not context:
        return ["game"]
    missing = []
    for key in ("game_id", "chapter", "location"):
        if not context.get(key):
            missing.append(key)
    return missing


def _dedupe(values: list[str | None]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if not value:
            continue
        item = str(value).strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
