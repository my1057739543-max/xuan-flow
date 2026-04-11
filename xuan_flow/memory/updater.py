"""Memory updater — uses LLM to extract facts from conversations.

Simplified from deer-flow: no debounce queue, synchronous update.
Keeps core features: LLM fact extraction, content dedup, atomic write.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from xuan_flow.config.app_config import get_app_config
from xuan_flow.memory.prompt import MEMORY_UPDATE_PROMPT, format_conversation_for_update
from xuan_flow.memory.store import (
    get_memory_data,
    save_memory_data,
    rebuild_working_memory,
    sync_memory_to_mysql,
)
from xuan_flow.models.factory import create_chat_model

logger = logging.getLogger(__name__)


def _fact_content_key(content: Any) -> str | None:
    """Normalize fact content for deduplication."""
    if not isinstance(content, str):
        return None
    stripped = " ".join(content.strip().split())
    return stripped if stripped else None


def update_memory_from_conversation(messages: list[Any], thread_id: str | None = None) -> bool:
    """Update memory by extracting facts from a conversation.

    Core flow from deer-flow:
    1. Format conversation for LLM
    2. Call LLM with current memory + conversation
    3. Parse structured fact output
    4. Deduplicate and merge
    5. Atomic save

    Args:
        messages: List of LangChain messages from the conversation.
        thread_id: Optional thread ID for tracking source.

    Returns:
        True if successful.
    """
    config = get_app_config()
    if not config.memory.enabled:
        return False

    if not messages:
        return False

    try:
        # Get current memory
        current_memory = get_memory_data()

        # Format conversation
        conversation_text = format_conversation_for_update(messages)
        if not conversation_text.strip():
            return False

        # Build prompt
        prompt = MEMORY_UPDATE_PROMPT.format(
            current_memory=json.dumps(current_memory, indent=2),
            conversation=conversation_text,
        )

        # Call LLM
        model = create_chat_model()
        response = model.invoke(prompt)
        response_text = response.content if isinstance(response.content, str) else str(response.content)
        response_text = response_text.strip()

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        update_data = json.loads(response_text)
        if not isinstance(update_data, dict):
            logger.warning("LLM memory response is not a JSON object")
            return False

        # Apply updates
        updated_memory = _apply_updates(current_memory, update_data, thread_id, config.memory.max_facts)

        # Save L1 atomically
        saved = save_memory_data(updated_memory)
        if not saved:
            return False

        # Build L2 working memory markdown using the latest user request as query.
        latest_user_query = _extract_latest_user_text(messages)
        rebuild_working_memory(latest_user_query, max_facts=config.memory.max_injection_facts)

        # Best-effort L3 sync (do not fail the pipeline if MySQL is unavailable).
        sync_memory_to_mysql(updated_memory, thread_id=thread_id)
        return True

    except json.JSONDecodeError as e:
        logger.warning("Failed to parse LLM memory response: %s", e)
        return False
    except Exception as e:
        logger.exception("Memory update failed: %s", e)
        return False


def _safe_float(value: Any, default: float = 0.5) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_latest_user_text(messages: list[Any]) -> str:
    """Extract latest user message content for query-aware working memory build."""
    for msg in reversed(messages):
        role = type(msg).__name__.lower()
        if "human" in role:
            content = getattr(msg, "content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return ""


def _apply_updates(
    current_memory: dict[str, Any],
    update_data: dict[str, Any],
    thread_id: str | None,
    max_facts: int,
) -> dict[str, Any]:
    """Apply LLM-generated updates to memory (with deduplication)."""
    now = datetime.now(timezone.utc).isoformat()
    current_memory.setdefault("facts", [])

    # Remove outdated facts
    raw_to_remove = update_data.get("factsToRemove", [])
    facts_to_remove = set(raw_to_remove) if isinstance(raw_to_remove, list) else set()
    if facts_to_remove:
        current_memory["facts"] = [
            f for f in current_memory.get("facts", [])
            if f.get("id") not in facts_to_remove
        ]

    # Build index by normalized content for upsert behavior
    existing_index: dict[str, dict[str, Any]] = {}
    for existing in current_memory.get("facts", []):
        key = _fact_content_key(existing.get("content"))
        if key is not None:
            existing_index[key] = existing

    # Add or merge facts (atomic fact upsert)
    raw_new_facts = update_data.get("newFacts", [])
    if not isinstance(raw_new_facts, list):
        raw_new_facts = []

    for fact in raw_new_facts:
        if not isinstance(fact, dict):
            continue
        confidence = _safe_float(fact.get("confidence", 0.5), default=0.5)
        confidence = max(0.0, min(1.0, confidence))
        if confidence < 0.7:
            continue

        content = fact.get("content", "")
        key = _fact_content_key(content)
        if key is None:
            continue

        existing = existing_index.get(key)
        if existing is not None:
            # Merge atomic fact: keep strongest confidence and refresh timestamp/source.
            existing["confidence"] = max(_safe_float(existing.get("confidence", 0.0), 0.0), confidence)
            existing["updatedAt"] = now
            if isinstance(fact.get("category"), str) and fact.get("category").strip():
                existing["category"] = fact.get("category")
            existing["source"] = thread_id or existing.get("source") or "unknown"
            continue

        new_fact = {
            "content": key,
            "category": fact.get("category", "context"),
            "confidence": confidence,
            "createdAt": now,
            "updatedAt": now,
            "source": thread_id or "unknown",
        }
        current_memory["facts"].append(new_fact)
        existing_index[key] = new_fact

    # Enforce max facts
    facts = current_memory.get("facts", [])
    if len(facts) > max_facts:
        current_memory["facts"] = sorted(
            facts,
            key=lambda f: (_safe_float(f.get("confidence", 0.0), 0.0), f.get("updatedAt", ""), f.get("createdAt", "")),
            reverse=True,
        )[:max_facts]

    return current_memory
