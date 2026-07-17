"""LangChain tools for local game knowledge lookup."""

from __future__ import annotations

import json

from langchain_core.tools import tool

from xuan_flow.game_knowledge.search import (
    get_game_by_id,
    list_supported_games as list_games,
    search_game_catalog,
    search_game_items as search_items,
    search_game_lore as search_lore,
    search_game_puzzles as search_puzzles,
    search_game_walkthrough as search_walkthrough,
)


@tool
def list_supported_games() -> str:
    """List games currently known by the local game catalog."""
    return json.dumps(list_games(), ensure_ascii=False)


@tool
def get_game_profile(game_id: str) -> str:
    """Get a game profile by id or alias."""
    return json.dumps(get_game_by_id(game_id), ensure_ascii=False)


@tool
def search_supported_games(query: str, limit: int = 5) -> str:
    """Search supported games by name, alias, genre, route, or summary."""
    return json.dumps(search_game_catalog(query, limit=limit), ensure_ascii=False)


@tool
def search_game_items(
    game_id: str,
    query: str,
    chapter: str | None = None,
    location: str | None = None,
    limit: int = 5,
) -> str:
    """Search item locations, acquisition hints, and uses for a detailed game entry."""
    return json.dumps(
        search_items(game_id, query, chapter=chapter, location=location, limit=limit),
        ensure_ascii=False,
    )


@tool
def search_game_puzzles(
    game_id: str,
    query: str,
    chapter: str | None = None,
    location: str | None = None,
    spoiler_level: str = "low",
    limit: int = 5,
) -> str:
    """Search puzzle hints or solutions for a detailed game entry with spoiler control."""
    return json.dumps(
        search_puzzles(
            game_id,
            query,
            chapter=chapter,
            location=location,
            spoiler_level=spoiler_level,
            limit=limit,
        ),
        ensure_ascii=False,
    )


@tool
def search_game_walkthrough(game_id: str, query: str, limit: int = 3) -> str:
    """Search walkthrough notes for a detailed game entry."""
    return json.dumps(search_walkthrough(game_id, query, limit=limit), ensure_ascii=False)


@tool
def search_game_lore(game_id: str, query: str, limit: int = 3) -> str:
    """Search lore and background notes for a detailed game entry."""
    return json.dumps(search_lore(game_id, query, limit=limit), ensure_ascii=False)
