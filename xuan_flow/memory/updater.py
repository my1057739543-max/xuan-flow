"""Memory updater — uses LLM to extract facts from conversations.

Simplified from deer-flow: no debounce queue, synchronous update.
Keeps core features: LLM fact extraction, content dedup, atomic write.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from xuan_flow.config.app_config import get_app_config
from xuan_flow.memory.prompt import MEMORY_UPDATE_PROMPT, format_conversation_for_update
from xuan_flow.memory.store import get_memory_data, save_memory_data
from xuan_flow.models.factory import create_chat_model

logger = logging.getLogger(__name__)


def _fact_content_key(content: Any) -> str | None:
    """Normalize fact content for deduplication."""
    if not isinstance(content, str):
        return None
    stripped = content.strip()
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

        # Apply updates
        updated_memory = _apply_updates(current_memory, update_data, thread_id, config.memory.max_facts)

        # Save atomically
        return save_memory_data(updated_memory)

    except json.JSONDecodeError as e:
        logger.warning("Failed to parse LLM memory response: %s", e)
        return False
    except Exception as e:
        logger.exception("Memory update failed: %s", e)
        return False


def _apply_updates(
    current_memory: dict[str, Any],
    update_data: dict[str, Any],
    thread_id: str | None,
    max_facts: int,
) -> dict[str, Any]:
    """Apply LLM-generated updates to memory (with deduplication)."""
    now = datetime.now(timezone.utc).isoformat()

    # Remove outdated facts
    facts_to_remove = set(update_data.get("factsToRemove", []))
    if facts_to_remove:
        current_memory["facts"] = [
            f for f in current_memory.get("facts", [])
            if f.get("id") not in facts_to_remove
        ]

    # Build existing content set for deduplication
    existing_keys = {
        _fact_content_key(f.get("content"))
        for f in current_memory.get("facts", [])
    }
    existing_keys.discard(None)

    # Add new facts (with dedup)
    for fact in update_data.get("newFacts", []):
        confidence = fact.get("confidence", 0.5)
        if confidence < 0.7:
            continue

        content = fact.get("content", "").strip()
        key = _fact_content_key(content)
        if key is None or key in existing_keys:
            continue

        current_memory.setdefault("facts", []).append({
            "id": f"fact_{uuid.uuid4().hex[:8]}",
            "content": content,
            "category": fact.get("category", "context"),
            "confidence": confidence,
            "createdAt": now,
            "source": thread_id or "unknown",
        })
        existing_keys.add(key)

    # Enforce max facts
    facts = current_memory.get("facts", [])
    if len(facts) > max_facts:
        current_memory["facts"] = sorted(
            facts, key=lambda f: f.get("confidence", 0), reverse=True
        )[:max_facts]

    return current_memory
