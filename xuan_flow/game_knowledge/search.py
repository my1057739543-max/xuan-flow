"""Lightweight search over local game knowledge."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from xuan_flow.game_knowledge.store import (
    catalog_games,
    detailed_game_exists,
    load_game_items,
    load_game_markdown,
    load_game_profile,
    load_game_puzzles,
    normalize_text,
)


KNOWLEDGE_HIT_LOG_FILE = Path.cwd() / ".xuan-flow" / "game_knowledge_hits.jsonl"


def list_supported_games() -> list[dict[str, Any]]:
    """Return catalog entries with fields useful for UI and routing."""
    return [
        {
            "game_id": game.get("game_id"),
            "display_name": game.get("display_name"),
            "aliases": game.get("aliases", []),
            "genres": game.get("genres", []),
            "routes": game.get("routes", []),
            "spoiler_sensitivity": game.get("spoiler_sensitivity"),
            "knowledge_status": game.get("knowledge_status", "unknown"),
            "has_detailed_knowledge": detailed_game_exists(str(game.get("game_id", ""))),
        }
        for game in catalog_games()
    ]


def get_game_by_id(game_id: str) -> dict[str, Any] | None:
    """Find a game by game_id, alias, display name, or partial id."""
    query = normalize_text(game_id)
    if not query:
        return None

    for game in catalog_games():
        if _matches_game(game, query):
            return _merge_detailed_profile(game)

    profile = load_game_profile(query)
    if profile:
        profile["has_detailed_knowledge"] = True
        return profile
    return None


def resolve_game_id(game_id: str) -> str | None:
    """Resolve an arbitrary game name or alias to a canonical game_id."""
    game = get_game_by_id(game_id)
    if not game:
        return None
    resolved = game.get("game_id")
    return str(resolved) if resolved else None


def search_game_catalog(query: str, *, limit: int = 5) -> list[dict[str, Any]]:
    """Search the game catalog by id, display name, alias, genre, route, and summary."""
    q = _expand_query(normalize_text(query))
    if not q:
        return []

    scored: list[tuple[int, dict[str, Any]]] = []
    for game in catalog_games():
        fields = [
            game.get("game_id", ""),
            game.get("display_name", ""),
            game.get("summary", ""),
            " ".join(game.get("aliases", [])),
            " ".join(game.get("genres", [])),
            " ".join(game.get("routes", [])),
        ]
        text = normalize_text(" ".join(str(field) for field in fields))
        score = 0
        if normalize_text(game.get("game_id")) == q:
            score += 100
        if q in [normalize_text(alias) for alias in game.get("aliases", [])]:
            score += 80
        if q in normalize_text(game.get("display_name", "")):
            score += 60
        if q in text:
            score += 20
        for token in q.split():
            if token and token in text:
                score += 5
        if score:
            scored.append((score, _merge_detailed_profile(game)))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [game for _, game in scored[: max(1, limit)]]


def search_game_items(
    game_id: str,
    query: str,
    *,
    chapter: str | None = None,
    location: str | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Search item facts inside a game's detailed knowledge base."""
    resolved = resolve_game_id(game_id) or normalize_text(game_id)
    items = load_game_items(resolved)
    results = _search_records(
        items,
        query,
        limit=limit,
        filters={"chapter": chapter, "location_area": location},
        searchable_keys=("item_id", "name", "aliases", "location", "acquisition_hint", "uses"),
    )
    return _knowledge_response(resolved, "items", results)


def search_game_puzzles(
    game_id: str,
    query: str,
    *,
    chapter: str | None = None,
    location: str | None = None,
    spoiler_level: str = "low",
    limit: int = 5,
) -> dict[str, Any]:
    """Search puzzle facts and return spoiler-controlled hints or solutions."""
    resolved = resolve_game_id(game_id) or normalize_text(game_id)
    puzzles = load_game_puzzles(resolved)
    matches = _search_records(
        puzzles,
        query,
        limit=limit,
        filters={"chapter": chapter, "location": location},
        searchable_keys=("puzzle_id", "name", "aliases", "location", "hint_layers", "solution"),
    )
    sanitized = [_sanitize_puzzle_result(match, spoiler_level) for match in matches]
    return _knowledge_response(resolved, "puzzles", sanitized, spoiler_level=spoiler_level)


def search_game_walkthrough(game_id: str, query: str, *, limit: int = 3) -> dict[str, Any]:
    """Search a game's walkthrough notes and return short matched excerpts."""
    resolved = resolve_game_id(game_id) or normalize_text(game_id)
    text = load_game_markdown(resolved, "walkthrough.md") or ""
    excerpts = _search_markdown(text, query, limit=limit)
    return _knowledge_response(resolved, "walkthrough", excerpts)


def search_game_lore(game_id: str, query: str, *, limit: int = 3) -> dict[str, Any]:
    """Search a game's lore notes and return short matched excerpts."""
    resolved = resolve_game_id(game_id) or normalize_text(game_id)
    text = load_game_markdown(resolved, "lore.md") or ""
    excerpts = _search_markdown(text, query, limit=limit)
    return _knowledge_response(resolved, "lore", excerpts)


def _merge_detailed_profile(game: dict[str, Any]) -> dict[str, Any]:
    merged = dict(game)
    game_id = str(game.get("game_id", ""))
    profile = load_game_profile(game_id)
    if profile:
        merged.update(profile)
        merged["has_detailed_knowledge"] = True
    else:
        merged["has_detailed_knowledge"] = detailed_game_exists(game_id)
    return merged


def _matches_game(game: dict[str, Any], query: str) -> bool:
    game_id_value = normalize_text(game.get("game_id"))
    display_name = normalize_text(game.get("display_name"))
    aliases = [normalize_text(alias) for alias in game.get("aliases", [])]
    if game_id_value == query or query in aliases:
        return True
    searchable = " ".join([game_id_value, display_name, *aliases])
    return query in searchable


def _search_records(
    records: list[dict[str, Any]],
    query: str,
    *,
    limit: int,
    filters: dict[str, str | None],
    searchable_keys: tuple[str, ...],
) -> list[dict[str, Any]]:
    q = _expand_query(normalize_text(query))
    scored: list[tuple[int, dict[str, Any]]] = []
    for record in records:
        if not _passes_filters(record, filters):
            continue
        text = _record_text(record, searchable_keys)
        score = _score_text(q, text)
        if score:
            scored.append((score, dict(record)))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [record for _, record in scored[: max(1, limit)]]


def _passes_filters(record: dict[str, Any], filters: dict[str, str | None]) -> bool:
    for key, value in filters.items():
        if not value:
            continue
        actual = normalize_text(record.get(key))
        if normalize_text(value) not in actual:
            return False
    return True


def _record_text(record: dict[str, Any], keys: tuple[str, ...]) -> str:
    values: list[str] = []
    for key in keys:
        value = record.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif value is not None:
            values.append(str(value))
    return normalize_text(" ".join(values))


def _score_text(query: str, text: str) -> int:
    if not query:
        return 0
    score = 0
    if query in text:
        score += 40
    for token in query.split():
        if token and token in text:
            score += 10
    return score


def _sanitize_puzzle_result(record: dict[str, Any], spoiler_level: str) -> dict[str, Any]:
    result = dict(record)
    spoiler = normalize_text(spoiler_level)
    hints = result.get("hint_layers", [])
    if not isinstance(hints, list):
        hints = []

    if spoiler in {"none", "low"}:
        result.pop("solution", None)
        result["hint_layers"] = hints[:1] if spoiler == "none" else hints[:2]
        result["solution_hidden"] = True
    elif spoiler == "medium":
        result.pop("solution", None)
        result["hint_layers"] = hints
        result["solution_hidden"] = True
    else:
        result["solution_hidden"] = False
    return result


def _search_markdown(text: str, query: str, *, limit: int) -> list[dict[str, Any]]:
    if not text:
        return []
    q = _expand_query(normalize_text(query))
    blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
    scored: list[tuple[int, dict[str, Any]]] = []
    for index, block in enumerate(blocks):
        score = _score_text(q, normalize_text(block))
        if score:
            scored.append((score, {"block_index": index, "excerpt": block[:700]}))
    if not scored and blocks:
        scored.append((1, {"block_index": 0, "excerpt": blocks[0][:700]}))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [item for _, item in scored[: max(1, limit)]]


def _knowledge_response(
    game_id: str,
    knowledge_type: str,
    results: list[dict[str, Any]],
    *,
    spoiler_level: str | None = None,
) -> dict[str, Any]:
    profile = load_game_profile(game_id)
    response = {
        "game_id": game_id,
        "display_name": (profile or {}).get("display_name"),
        "knowledge_type": knowledge_type,
        "knowledge_status": (profile or {}).get("knowledge_status", "missing"),
        "coverage_notes": (profile or {}).get("coverage_notes"),
        "spoiler_level": spoiler_level,
        "result_count": len(results),
        "results": results,
    }
    _append_knowledge_hit_log(response)
    return response


def _append_knowledge_hit_log(response: dict[str, Any]) -> None:
    """Append a compact JSONL audit record for local game knowledge hits."""
    try:
        KNOWLEDGE_HIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        result_ids = []
        for item in response.get("results", []):
            if isinstance(item, dict):
                result_ids.append(item.get("item_id") or item.get("puzzle_id") or item.get("block_index"))
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "game_id": response.get("game_id"),
            "display_name": response.get("display_name"),
            "knowledge_type": response.get("knowledge_type"),
            "knowledge_status": response.get("knowledge_status"),
            "spoiler_level": response.get("spoiler_level"),
            "result_count": response.get("result_count"),
            "result_ids": result_ids,
        }
        with KNOWLEDGE_HIT_LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        return


def _expand_query(query: str) -> str:
    """Expand common Chinese terms into searchable English keywords."""
    expansions = {
        "推理": "deduction mystery logic_puzzle",
        "解谜": "puzzle puzzle_adventure logic_puzzle escape_room",
        "密室": "escape_room room_escape locked drawer key door",
        "剧情": "narrative lore mystery story",
        "侦探": "detective deduction murder_mystery",
        "机关": "mechanical_puzzle box_puzzle puzzle device",
        "语言": "language_puzzle",
        "钥匙": "key golden_key locked drawer",
        "金钥匙": "golden key golden_key pillow",
        "枕头": "pillow bed key",
        "电源": "power cord stereo",
        "电线": "power cord stereo",
        "抽屉": "drawer desk locked drawer",
        "螺丝刀": "screwdriver doorknob door",
        "门": "door doorknob escape",
        "音响": "stereo power cord",
        "透镜": "lens eyepiece null",
        "镜片": "lens eyepiece null",
        "书": "book linking book page",
        "面板": "panel path grid",
        "手表": "watch memento mortem death scene",
        "符号": "glyph grapheme symbol language",
    }
    terms = [query]
    for key, value in expansions.items():
        if key in query:
            terms.append(value)
    return " ".join(terms)
