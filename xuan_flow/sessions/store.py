"""JSON-based session storage for conversation history."""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path.cwd() / ".xuan-flow" / "sessions"
INDEX_FILE = SESSIONS_DIR / "index.json"

TITLE_MAX_LENGTH = 48


def _ensure_dir() -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def generate_session_id() -> str:
    return uuid.uuid4().hex[:12]


def _infer_title(messages: list[dict[str, Any]]) -> str:
    """Use the first user message as the session title, truncated."""
    for msg in messages:
        if msg.get("role") == "user":
            text = msg.get("content", "").strip()
            if text:
                return text[:TITLE_MAX_LENGTH].replace("\n", " ")
    return "New Chat"


def _load_index() -> list[dict[str, Any]]:
    _ensure_dir()
    if not INDEX_FILE.exists():
        return []
    try:
        return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load session index: %s", e)
        return []


def _save_index(index: list[dict[str, Any]]) -> None:
    _ensure_dir()
    INDEX_FILE.write_text(
        json.dumps(index, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def list_sessions() -> list[dict[str, Any]]:
    """Return list of {id, title, created_at, message_count} sorted by updated_at desc."""
    return _load_index()


def get_session(session_id: str) -> dict[str, Any] | None:
    """Load a full session by ID, including messages."""
    _ensure_dir()
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load session %s: %s", session_id, e)
        return None


def save_session(
    session_id: str,
    messages: list[dict[str, Any]],
    title: str | None = None,
) -> dict[str, Any]:
    """Persist a session and update the index.

    Creates or updates the session file, then upserts the index entry.
    Returns the session dict.
    """
    _ensure_dir()
    now = datetime.now(timezone.utc).isoformat()

    existing = get_session(session_id)
    if existing:
        session = existing
        session["messages"] = messages
        session["updated_at"] = now
        if title:
            session["title"] = title
    else:
        resolved_title = title or _infer_title(messages)
        session = {
            "id": session_id,
            "title": resolved_title,
            "created_at": now,
            "updated_at": now,
            "messages": messages,
        }

    path = SESSIONS_DIR / f"{session_id}.json"
    path.write_text(
        json.dumps(session, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Update index
    index = _load_index()
    now_ts = datetime.now(timezone.utc).isoformat()
    entry = {
        "id": session_id,
        "title": session["title"],
        "created_at": session.get("created_at", now_ts),
        "updated_at": now_ts,
        "message_count": len(messages),
    }
    for i, e in enumerate(index):
        if e["id"] == session_id:
            index[i] = entry
            break
    else:
        index.insert(0, entry)

    # Sort by updated_at desc
    index.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    _save_index(index)

    return session


def delete_session(session_id: str) -> bool:
    """Delete a session file and remove from index."""
    _ensure_dir()
    path = SESSIONS_DIR / f"{session_id}.json"
    deleted = False
    if path.exists():
        try:
            path.unlink()
            deleted = True
        except OSError as e:
            logger.warning("Failed to delete session file %s: %s", session_id, e)

    index = _load_index()
    new_index = [e for e in index if e["id"] != session_id]
    if len(new_index) != len(index):
        _save_index(new_index)
        deleted = True

    return deleted
