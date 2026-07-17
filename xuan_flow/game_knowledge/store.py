"""Load local game knowledge files."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


GAME_DATA_DIR = Path("data/games")
CATALOG_FILE = GAME_DATA_DIR / "catalog.json"


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    """Load the game catalog JSON."""
    if not CATALOG_FILE.exists():
        return {"version": "1.0", "games": []}
    return json.loads(CATALOG_FILE.read_text(encoding="utf-8"))


def catalog_games() -> list[dict[str, Any]]:
    """Return all games in the catalog."""
    games = load_catalog().get("games", [])
    return games if isinstance(games, list) else []


def game_dir(game_id: str) -> Path:
    """Return the directory that stores detailed knowledge for a game."""
    return GAME_DATA_DIR / normalize_text(game_id)


def detailed_game_exists(game_id: str) -> bool:
    """Return whether detailed second-layer knowledge exists for a game."""
    path = game_dir(game_id)
    return path.exists() and path.is_dir()


@lru_cache(maxsize=64)
def load_game_json(game_id: str, filename: str) -> Any:
    """Load a JSON file from a detailed game directory."""
    path = game_dir(game_id) / filename
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=64)
def load_game_markdown(game_id: str, filename: str) -> str | None:
    """Load a Markdown file from a detailed game directory."""
    path = game_dir(game_id) / filename
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def load_game_profile(game_id: str) -> dict[str, Any] | None:
    """Load detailed game profile, if available."""
    data = load_game_json(game_id, "game.json")
    return data if isinstance(data, dict) else None


def load_game_items(game_id: str) -> list[dict[str, Any]]:
    """Load detailed item facts for a game."""
    data = load_game_json(game_id, "items.json")
    return data if isinstance(data, list) else []


def load_game_puzzles(game_id: str) -> list[dict[str, Any]]:
    """Load detailed puzzle facts for a game."""
    data = load_game_json(game_id, "puzzles.json")
    return data if isinstance(data, list) else []


def normalize_text(value: str | None) -> str:
    """Normalize text for lightweight matching."""
    return (value or "").strip().lower()
