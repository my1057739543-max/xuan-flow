"""LangChain tools for multi-game player context."""

from __future__ import annotations

import json
from typing import Literal

from langchain_core.tools import tool

from xuan_flow.game_context.state import (
    clear_game_context as clear_context_state,
    get_game_context as get_context_state,
    list_game_contexts as list_context_state,
    update_game_context as update_context_state,
)


@tool
def list_game_contexts(thread_id: str = "default") -> str:
    """List all remembered game contexts for a conversation thread."""
    return json.dumps(list_context_state(thread_id=thread_id), ensure_ascii=False)


@tool
def get_game_context(game_id: str | None = None, thread_id: str = "default") -> str:
    """Get the active game context or a specific game's context.

    Use this after `classify_game_intent` returns `needs_game_context=true`.
    If game_id is omitted, the active game for the thread is returned.
    """
    return json.dumps(get_context_state(game_id=game_id, thread_id=thread_id), ensure_ascii=False)


@tool
def update_game_context(
    game_id: str | None = None,
    display_name: str | None = None,
    thread_id: str = "default",
    set_active: bool = True,
    chapter: str | None = None,
    location: str | None = None,
    current_puzzle: str | None = None,
    inventory: list[str] | None = None,
    add_inventory: list[str] | None = None,
    remove_inventory: list[str] | None = None,
    spoiler_preference: Literal["none", "low", "medium", "high"] | None = None,
    solved_puzzles: list[str] | None = None,
    add_solved_puzzles: list[str] | None = None,
    notes: str | None = None,
    aliases: list[str] | None = None,
    last_user_query: str | None = None,
) -> str:
    """Create or update a per-game player context.

    Use this when the player provides game name, chapter, location, inventory,
    current puzzle, solved puzzle, or spoiler preference. Supports multiple
    games under the same thread and can switch the active game.
    """
    result = update_context_state(
        game_id=game_id,
        display_name=display_name,
        thread_id=thread_id,
        set_active=set_active,
        chapter=chapter,
        location=location,
        current_puzzle=current_puzzle,
        inventory=inventory,
        add_inventory=add_inventory,
        remove_inventory=remove_inventory,
        spoiler_preference=spoiler_preference,
        solved_puzzles=solved_puzzles,
        add_solved_puzzles=add_solved_puzzles,
        notes=notes,
        aliases=aliases,
        last_user_query=last_user_query,
    )
    return json.dumps(result, ensure_ascii=False)


@tool
def clear_game_context(game_id: str | None = None, thread_id: str = "default") -> str:
    """Clear one game context, or all game contexts for the thread if game_id is omitted."""
    return json.dumps(clear_context_state(game_id=game_id, thread_id=thread_id), ensure_ascii=False)
