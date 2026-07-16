"""Tool wrapper for the local game intent router."""

from __future__ import annotations

import json

from langchain_core.tools import tool

from xuan_flow.game_intent.router import route_game_intent


@tool
def classify_game_intent(text: str) -> str:
    """Classify a single-player puzzle-game user query for agent routing.

    Use this before handling game-related user requests. It returns the
    predicted intent, confidence, recommended route, spoiler level, and
    whether current game context is required.
    """
    route = route_game_intent(text, device="cpu")
    return json.dumps(route.to_dict(), ensure_ascii=False)
