"""Memory middleware — triggers memory update after conversations.

Simplified from deer-flow: no debounce queue, just synchronous update
after conversation completes.
"""

import logging
import threading
from typing import Any

from xuan_flow.memory.updater import update_memory_from_conversation

logger = logging.getLogger(__name__)


def update_memory_background(messages: list[Any], thread_id: str | None = None):
    """Update memory in a background thread to not block the response."""
    def _update():
        try:
            update_memory_from_conversation(messages, thread_id)
        except Exception as e:
            logger.exception("Background memory update failed: %s", e)

    thread = threading.Thread(target=_update, daemon=True)
    thread.start()
