"""Memory store — JSON file read/write with caching.

Simplified from deer-flow: only facts list, no user/history multi-dimensional structure.
Keeps atomic write (temp file + rename) from deer-flow.
"""

import json
import logging
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from xuan_flow.config.app_config import get_app_config

logger = logging.getLogger(__name__)

ALLOWED_FACT_CATEGORIES = {"preference", "knowledge", "context", "behavior", "goal"}

# ── Cache ────────────────────────────────────────────────────────────────────

_memory_cache: tuple[dict[str, Any], float | None] | None = None


def _get_working_memory_path() -> Path:
    """Get the path to memory.md from config."""
    config = get_app_config()
    return Path(config.memory.working_memory_path)


def _get_memory_path() -> Path:
    """Get the path to memory.json from config."""
    config = get_app_config()
    return Path(config.memory.storage_path)


def _create_empty_memory() -> dict[str, Any]:
    """Create an empty memory structure."""
    return {
        "version": "1.0",
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "facts": [],
    }


def _normalize_fact_content(content: Any) -> str | None:
    """Normalize fact content into a single-line canonical string."""
    if not isinstance(content, str):
        return None
    normalized = " ".join(content.strip().split())
    return normalized if normalized else None


def _build_fact_id(content: str, category: str) -> str:
    """Create a stable ID for an atomic fact."""
    digest = hashlib.sha1(f"{category}:{content}".encode("utf-8")).hexdigest()[:12]
    return f"fact_{digest}"


def _normalize_fact(fact: Any) -> dict[str, Any] | None:
    """Normalize and validate a single fact object."""
    if not isinstance(fact, dict):
        return None

    content = _normalize_fact_content(fact.get("content"))
    if content is None:
        return None

    category = fact.get("category") if isinstance(fact.get("category"), str) else "context"
    category = category.strip().lower() or "context"
    if category not in ALLOWED_FACT_CATEGORIES:
        category = "context"

    confidence = fact.get("confidence", 0.5)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    created_at = fact.get("createdAt") if isinstance(fact.get("createdAt"), str) else None
    updated_at = fact.get("updatedAt") if isinstance(fact.get("updatedAt"), str) else None
    source = fact.get("source") if isinstance(fact.get("source"), str) else "unknown"

    return {
        "id": fact.get("id") if isinstance(fact.get("id"), str) and fact.get("id").strip() else _build_fact_id(content, category),
        "content": content,
        "category": category,
        "confidence": confidence,
        "createdAt": created_at or datetime.now(timezone.utc).isoformat(),
        "updatedAt": updated_at or created_at or datetime.now(timezone.utc).isoformat(),
        "source": source,
    }


def _normalize_memory_schema(memory_data: Any) -> dict[str, Any]:
    """Normalize memory JSON into the expected schema with deduplicated facts."""
    if not isinstance(memory_data, dict):
        return _create_empty_memory()

    normalized: dict[str, Any] = {
        "version": str(memory_data.get("version", "1.0")),
        "lastUpdated": (
            memory_data.get("lastUpdated")
            if isinstance(memory_data.get("lastUpdated"), str)
            else datetime.now(timezone.utc).isoformat()
        ),
        "facts": [],
    }

    dedup_by_id: dict[str, dict[str, Any]] = {}
    for raw_fact in memory_data.get("facts", []):
        fact = _normalize_fact(raw_fact)
        if fact is None:
            continue

        existing = dedup_by_id.get(fact["id"])
        if existing is None or fact.get("confidence", 0.0) >= existing.get("confidence", 0.0):
            dedup_by_id[fact["id"]] = fact

    normalized["facts"] = list(dedup_by_id.values())
    return normalized


def get_memory_data() -> dict[str, Any]:
    """Get memory data (cached, auto-invalidates on file change)."""
    global _memory_cache

    file_path = _get_memory_path()

    try:
        current_mtime = file_path.stat().st_mtime if file_path.exists() else None
    except OSError:
        current_mtime = None

    if _memory_cache is not None:
        cached_data, cached_mtime = _memory_cache
        if cached_mtime == current_mtime:
            return cached_data

    # Load from file
    data = _load_from_file(file_path)
    _memory_cache = (data, current_mtime)
    return data


def reload_memory_data() -> dict[str, Any]:
    """Force reload memory from file."""
    global _memory_cache
    _memory_cache = None
    return get_memory_data()


def save_memory_data(memory_data: dict[str, Any]) -> bool:
    """Save memory data atomically (temp + rename).

    Atomic write pattern from deer-flow to prevent corruption.
    """
    global _memory_cache

    file_path = _get_memory_path()

    try:
        normalized_memory = _normalize_memory_schema(memory_data)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        normalized_memory["lastUpdated"] = datetime.now(timezone.utc).isoformat()

        # Atomic write: temp file → rename
        temp_path = file_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(normalized_memory, f, indent=2, ensure_ascii=False)
        temp_path.replace(file_path)

        # Update cache
        try:
            mtime = file_path.stat().st_mtime
        except OSError:
            mtime = None
        _memory_cache = (normalized_memory, mtime)

        logger.info("Memory saved to %s (%d facts)", file_path, len(normalized_memory.get("facts", [])))
        return True

    except OSError as e:
        logger.error("Failed to save memory: %s", e)
        return False


def _load_from_file(file_path: Path) -> dict[str, Any]:
    """Load memory from JSON file."""
    if not file_path.exists():
        return _create_empty_memory()

    try:
        with open(file_path, encoding="utf-8") as f:
            raw_data = json.load(f)
            return _normalize_memory_schema(raw_data)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load memory file: %s", e)
        return _create_empty_memory()


def format_memory_for_injection(memory_data: dict[str, Any], max_facts: int = 10) -> str:
    """Format memory facts for injection into system prompt."""
    facts = _normalize_memory_schema(memory_data).get("facts", [])
    if not facts:
        return ""

    limit = max(0, int(max_facts))
    if limit == 0:
        return ""

    # Prefer high-confidence and recently-updated facts.
    sorted_facts = sorted(
        facts,
        key=lambda f: (f.get("confidence", 0), f.get("updatedAt", ""), f.get("createdAt", "")),
        reverse=True,
    )[:limit]

    lines = ["Here's what you remember about the user from past conversations:"]
    for fact in sorted_facts:
        content = fact.get("content", "")
        category = fact.get("category", "")
        lines.append(f"- [{category}] {content}")

    return "\n".join(lines)


def _extract_keywords(text: str) -> set[str]:
    """Extract rough keywords for lightweight relevance ranking."""
    words = [w.strip(".,:;!?()[]{}\"'`)./\\") for w in text.lower().split()]
    return {w for w in words if len(w) >= 2}


def _relevance_score(content: str, query: str) -> float:
    """Simple token overlap score between query and fact content."""
    query_tokens = _extract_keywords(query)
    if not query_tokens:
        return 0.0
    content_tokens = _extract_keywords(content)
    if not content_tokens:
        return 0.0
    overlap = query_tokens.intersection(content_tokens)
    return len(overlap) / max(1, len(query_tokens))


def _build_working_memory_markdown(facts: list[dict[str, Any]], query: str, max_facts: int) -> str:
    """Build memory.md content with query-aware ranking."""
    ranked = sorted(
        facts,
        key=lambda f: (
            _relevance_score(str(f.get("content", "")), query),
            float(f.get("confidence", 0.0) or 0.0),
            str(f.get("updatedAt", "")),
        ),
        reverse=True,
    )

    selected = ranked[: max(0, int(max_facts))]
    now = datetime.now(timezone.utc).isoformat()
    lines = [
        "# Working Memory",
        "",
        f"GeneratedAt: {now}",
        f"Query: {query.strip() if isinstance(query, str) else ''}",
        f"SelectedFacts: {len(selected)}",
        "",
        "## Useful Memory For Current Request",
    ]

    for idx, fact in enumerate(selected, start=1):
        category = str(fact.get("category", "context"))
        confidence = float(fact.get("confidence", 0.0) or 0.0)
        content = str(fact.get("content", "")).strip()
        if not content:
            continue
        lines.append(f"{idx}. [{category}] ({confidence:.2f}) {content}")

    if len(lines) == 7:
        lines.append("1. [context] (0.00) No useful memory found for this request.")

    return "\n".join(lines) + "\n"


def rebuild_working_memory(query: str, max_facts: int | None = None) -> str:
    """Rebuild L2 memory.md from L1 JSON memory using current query."""
    config = get_app_config()
    memory_data = get_memory_data()
    json_facts = _normalize_memory_schema(memory_data).get("facts", [])
    mysql_facts = _load_memory_facts_from_mysql(limit=max(config.memory.max_facts, 200))

    dedup: dict[str, dict[str, Any]] = {}
    for fact in json_facts + mysql_facts:
        normalized = _normalize_fact(fact)
        if normalized is None:
            continue
        existing = dedup.get(normalized["id"])
        if existing is None or float(normalized.get("confidence", 0.0)) >= float(existing.get("confidence", 0.0)):
            dedup[normalized["id"]] = normalized

    facts = list(dedup.values())
    target_max = max_facts if max_facts is not None else config.memory.max_injection_facts

    content = _build_working_memory_markdown(facts, query or "", target_max)
    file_path = _get_working_memory_path()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return content


def get_working_memory_markdown() -> str:
    """Read L2 memory.md if available."""
    file_path = _get_working_memory_path()
    if not file_path.exists():
        return ""
    try:
        return file_path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("Failed to read working memory markdown: %s", e)
        return ""


def clear_atomic_memory() -> bool:
    """Clear L1 atomic memory JSON (facts only) and reset cache."""
    global _memory_cache
    empty_memory = _create_empty_memory()
    saved = save_memory_data(empty_memory)
    if saved:
        _memory_cache = None
    return saved


def clear_working_memory_markdown() -> bool:
    """Clear L2 memory.md content without touching L1/L3."""
    file_path = _get_working_memory_path()
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(
            "# Working Memory\n\nGeneratedAt: "+datetime.now(timezone.utc).isoformat()+"\nQuery: \nSelectedFacts: 0\n\n## Useful Memory For Current Request\n1. [context] (0.00) No useful memory found for this request.\n",
            encoding="utf-8",
        )
        return True
    except OSError as e:
        logger.warning("Failed to clear working memory markdown: %s", e)
        return False


def sync_memory_to_mysql(memory_data: dict[str, Any], thread_id: str | None = None) -> bool:
    """Best-effort sync from normalized memory facts to MySQL (L3)."""
    config = get_app_config()
    if not config.memory.mysql_enabled:
        return False

    try:
        import pymysql  # type: ignore
    except Exception:
        logger.warning("MySQL sync skipped: pymysql not installed")
        return False

    facts = _normalize_memory_schema(memory_data).get("facts", [])
    if not facts:
        return True

    table = config.memory.mysql_table
    try:
        conn = pymysql.connect(
            host=config.memory.mysql_host,
            port=int(config.memory.mysql_port),
            user=config.memory.mysql_user,
            password=config.memory.mysql_password,
            database=config.memory.mysql_database,
            charset="utf8mb4",
            autocommit=False,
        )
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS `{table}` (
                    id VARCHAR(64) PRIMARY KEY,
                    content TEXT NOT NULL,
                    category VARCHAR(32) NOT NULL,
                    confidence DOUBLE NOT NULL,
                    source VARCHAR(128) NOT NULL,
                    created_at VARCHAR(64) NOT NULL,
                    updated_at VARCHAR(64) NOT NULL,
                    thread_id VARCHAR(128) NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

            upsert_sql = f"""
                INSERT INTO `{table}`
                    (id, content, category, confidence, source, created_at, updated_at, thread_id)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    content=VALUES(content),
                    category=VALUES(category),
                    confidence=VALUES(confidence),
                    source=VALUES(source),
                    updated_at=VALUES(updated_at),
                    thread_id=VALUES(thread_id)
            """
            for fact in facts:
                cur.execute(
                    upsert_sql,
                    (
                        str(fact.get("id", "")),
                        str(fact.get("content", "")),
                        str(fact.get("category", "context")),
                        float(fact.get("confidence", 0.0) or 0.0),
                        str(fact.get("source", "unknown")),
                        str(fact.get("createdAt", "")),
                        str(fact.get("updatedAt", "")),
                        thread_id,
                    ),
                )

        conn.commit()
        conn.close()
        logger.info("Synced %d facts to MySQL table %s", len(facts), table)
        return True
    except Exception as e:
        logger.warning("MySQL sync failed: %s", e)
        return False


def _load_memory_facts_from_mysql(limit: int = 200) -> list[dict[str, Any]]:
    """Load fact candidates from MySQL for L2 working-memory generation."""
    config = get_app_config()
    if not config.memory.mysql_enabled:
        return []

    try:
        import pymysql  # type: ignore
    except Exception:
        return []

    table = config.memory.mysql_table
    try:
        conn = pymysql.connect(
            host=config.memory.mysql_host,
            port=int(config.memory.mysql_port),
            user=config.memory.mysql_user,
            password=config.memory.mysql_password,
            database=config.memory.mysql_database,
            charset="utf8mb4",
            autocommit=True,
        )
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, content, category, confidence, source, created_at, updated_at
                FROM `{table}`
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (int(limit),),
            )
            rows = cur.fetchall()
        conn.close()
    except Exception as e:
        logger.warning("MySQL load failed: %s", e)
        return []

    facts: list[dict[str, Any]] = []
    for row in rows:
        facts.append(
            {
                "id": row[0],
                "content": row[1],
                "category": row[2],
                "confidence": row[3],
                "source": row[4],
                "createdAt": row[5],
                "updatedAt": row[6],
            }
        )
    return facts
