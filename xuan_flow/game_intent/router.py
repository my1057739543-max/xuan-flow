"""Business routing rules on top of the game intent classifier."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from xuan_flow.game_intent.classifier import IntentPrediction, get_game_intent_classifier


PRIMARY_CONFIDENCE_THRESHOLD = 0.60
AMBIGUOUS_CONFIDENCE_THRESHOLD = 0.40
SECONDARY_CONFIDENCE_THRESHOLD = 0.15
SPOILER_AUXILIARY_INTENTS = {"spoiler_control"}
HINT_COMPATIBLE_INTENTS = {"hint_request", "puzzle_solution", "item_location", "walkthrough_request"}
LOW_SPOILER_RE = re.compile(r"别剧透|不要剧透|不剧透|低剧透|只给.*提示|只要.*提示|别.*答案|不要.*答案")
ROUTE_LOG_FILE = Path.cwd() / ".xuan-flow" / "game_intent_routes.jsonl"


@dataclass(frozen=True)
class IntentRoute:
    """Final routing decision consumed by the lead agent."""

    text: str
    intent: str
    confidence: float
    route_to: str
    spoiler_level: str
    needs_game_context: bool
    domain: str | None
    status: str
    secondary_intent: str | None
    predictions: list[IntentPrediction]

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "intent": self.intent,
            "confidence": round(self.confidence, 4),
            "route_to": self.route_to,
            "spoiler_level": self.spoiler_level,
            "needs_game_context": self.needs_game_context,
            "domain": self.domain,
            "status": self.status,
            "secondary_intent": self.secondary_intent,
            "predictions": [prediction.to_dict() for prediction in self.predictions],
        }


def route_game_intent(
    text: str,
    *,
    model_dir: str = "models/game_intent_classifier",
    device: str | None = None,
    top_k: int = 3,
) -> IntentRoute:
    """Classify and normalize a game-domain query into an agent route.

    Routing policy:
    - high-confidence top-1 intents are accepted directly;
    - explicit low-spoiler wording is treated as a deterministic safety signal;
    - spoiler_control is an auxiliary preference when it is close to a concrete task intent;
    - low-confidence queries fall back to general_agent and should usually be clarified.
    """
    classifier = get_game_intent_classifier(model_dir=model_dir, device=device)
    predictions = classifier.predict(text, top_k=top_k)
    if not predictions:
        raise RuntimeError("intent classifier returned no predictions")

    primary = predictions[0]
    secondary = predictions[1] if len(predictions) > 1 else None
    explicit_low_spoiler = bool(LOW_SPOILER_RE.search(text))

    status = "accepted"
    secondary_intent: str | None = None
    intent = primary.intent
    confidence = primary.confidence
    route_to = primary.route_to or "general_agent"
    spoiler_level = primary.spoiler_level or "none"
    needs_game_context = bool(primary.needs_game_context)
    domain = primary.domain

    if explicit_low_spoiler and primary.intent in HINT_COMPATIBLE_INTENTS:
        secondary_intent = "spoiler_control"
        spoiler_level = "low"
        if primary.confidence < PRIMARY_CONFIDENCE_THRESHOLD:
            status = "accepted_with_auxiliary_spoiler_control"

    elif (
        secondary
        and secondary.confidence >= SECONDARY_CONFIDENCE_THRESHOLD
        and secondary.intent in SPOILER_AUXILIARY_INTENTS
        and primary.intent in HINT_COMPATIBLE_INTENTS
    ):
        secondary_intent = secondary.intent
        spoiler_level = _merge_spoiler_level(spoiler_level, secondary.spoiler_level)
        if primary.confidence < PRIMARY_CONFIDENCE_THRESHOLD:
            status = "accepted_with_auxiliary_spoiler_control"

    elif primary.intent in SPOILER_AUXILIARY_INTENTS and secondary and secondary.intent in HINT_COMPATIBLE_INTENTS:
        # "别剧透，钥匙在哪" can rank spoiler_control first. Keep the concrete
        # game task as the route, but preserve low-spoiler behavior.
        secondary_intent = primary.intent
        intent = secondary.intent
        confidence = max(primary.confidence, secondary.confidence)
        route_to = secondary.route_to or route_to
        spoiler_level = _merge_spoiler_level(secondary.spoiler_level, primary.spoiler_level)
        needs_game_context = bool(secondary.needs_game_context)
        domain = secondary.domain
        status = "accepted_with_auxiliary_spoiler_control"

    elif primary.confidence < AMBIGUOUS_CONFIDENCE_THRESHOLD:
        status = "needs_clarification"
        route_to = "general_agent"
        needs_game_context = False

    elif primary.confidence < PRIMARY_CONFIDENCE_THRESHOLD:
        status = "low_confidence"

    route = IntentRoute(
        text=text,
        intent=intent,
        confidence=confidence,
        route_to=route_to,
        spoiler_level=spoiler_level,
        needs_game_context=needs_game_context,
        domain=domain,
        status=status,
        secondary_intent=secondary_intent,
        predictions=predictions,
    )
    _append_route_log(route)
    return route


def _merge_spoiler_level(primary: str | None, auxiliary: str | None) -> str:
    """Prefer the more conservative spoiler level when safety is explicit."""
    if auxiliary == "low":
        return "low"
    return primary or auxiliary or "none"


def _append_route_log(route: IntentRoute) -> None:
    """Append a JSONL audit record for offline routing evaluation."""
    try:
        ROUTE_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **route.to_dict(),
        }
        with ROUTE_LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        # Routing should never fail just because the local audit log cannot be written.
        return
