"""
SQLite database connection and CRUD operations for poolmind.
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, List, Optional

from models.resource import Resource

logger = logging.getLogger(__name__)


def get_db_path() -> Path:
    import os

    raw = os.getenv("POOLMIND_DB_PATH", "data/poolmind.db")
    return Path(raw)


@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Write Operations ───────────────────────────────────────────────────────


def insert_resource(resource: Resource) -> None:
    d = resource.to_dict()
    d["extended_meta"] = json.dumps(d.get("extended_meta", {}))
    d["is_still_maintained"] = (
        int(d["is_still_maintained"]) if d["is_still_maintained"] is not None else None
    )
    d["ai_disabled"] = int(d["ai_disabled"])
    d["ai_enriched"] = int(d["ai_enriched"])

    columns = ", ".join(d.keys())
    placeholders = ", ".join(["?" for _ in d])
    sql = f"INSERT INTO resources ({columns}) VALUES ({placeholders})"

    with get_conn() as conn:
        conn.execute(sql, list(d.values()))
        _log_action(conn, "add", resource.id, f"Added: {resource.title}")

    logger.info("Inserted resource %s: %s", resource.id, resource.title)


def update_resource(resource_id: str, fields: dict) -> bool:
    fields["updated_at"] = datetime.now().isoformat()

    for list_field in ("tags", "mirror_urls", "prerequisites", "related_resources"):
        if list_field in fields and isinstance(fields[list_field], list):
            fields[list_field] = ",".join(fields[list_field])

    set_clause = ", ".join([f"{k} = ?" for k in fields])
    sql = f"UPDATE resources SET {set_clause} WHERE id = ?"

    with get_conn() as conn:
        cur = conn.execute(sql, list(fields.values()) + [resource_id])
        if cur.rowcount > 0:
            _log_action(
                conn, "edit", resource_id, f"Updated fields: {list(fields.keys())}"
            )
            return True
    return False


def increment_used(resource_id: str) -> None:
    sql = """
        UPDATE resources
        SET times_used = times_used + 1,
            last_used = ?,
            updated_at = ?
        WHERE id = ?
    """
    now = datetime.now().isoformat()
    with get_conn() as conn:
        conn.execute(sql, [now, now, resource_id])


def delete_resource(resource_id: str, hard: bool = False) -> bool:
    with get_conn() as conn:
        if hard:
            cur = conn.execute("DELETE FROM resources WHERE id = ?", [resource_id])
            _log_action(conn, "delete", resource_id, "Hard deleted")
        else:
            cur = conn.execute(
                "UPDATE resources SET consumption_state = 'archived', updated_at = ? WHERE id = ?",
                [datetime.now().isoformat(), resource_id],
            )
            _log_action(conn, "archive", resource_id, "Soft archived")
        return cur.rowcount > 0


# ── Read Operations ────────────────────────────────────────────────────────


def get_resource(resource_id: str) -> Optional[Resource]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM resources WHERE id = ?", [resource_id]
        ).fetchone()
    if row:
        return Resource.from_db_row(dict(row))
    return None


def get_by_url(url: str) -> Optional[Resource]:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM resources WHERE url = ?", [url]).fetchone()
    if row:
        return Resource.from_db_row(dict(row))
    return None


def get_all_resources(
    limit: int = 100, offset: int = 0, exclude_archived: bool = True
) -> List[Resource]:
    where = "WHERE consumption_state != 'archived'" if exclude_archived else ""
    sql = f"SELECT * FROM resources {where} ORDER BY added_on DESC LIMIT ? OFFSET ?"
    with get_conn() as conn:
        rows = conn.execute(sql, [limit, offset]).fetchall()
    return [Resource.from_db_row(dict(r)) for r in rows]


def get_all_titles_and_ids() -> List[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT id, title, url FROM resources").fetchall()
    return [dict(r) for r in rows]


def count_resources() -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as c FROM resources WHERE consumption_state != 'archived'"
        ).fetchone()
    return row["c"]


def get_stale_resources(days: int = 90) -> List[Resource]:
    sql = """
        SELECT * FROM resources
        WHERE (
            last_verified_alive IS NULL
            OR last_verified_alive < date('now', ?)
        )
        AND consumption_state != 'archived'
        AND url != 'local'
        ORDER BY last_verified_alive ASC
    """
    with get_conn() as conn:
        rows = conn.execute(sql, [f"-{days} days"]).fetchall()
    return [Resource.from_db_row(dict(r)) for r in rows]


def get_resources_by_domain(domain: str) -> List[Resource]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM resources WHERE domain = ? AND consumption_state != 'archived'",
            [domain],
        ).fetchall()
    return [Resource.from_db_row(dict(r)) for r in rows]


def get_unsynced_notion(limit: int = 50) -> List[Resource]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM resources WHERE notion_page_id IS NULL ORDER BY added_on DESC LIMIT ?",
            [limit],
        ).fetchall()
    return [Resource.from_db_row(dict(r)) for r in rows]


def update_notion_id(resource_id: str, notion_page_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE resources SET notion_page_id = ?, notion_last_synced = ?, updated_at = ? WHERE id = ?",
            [
                notion_page_id,
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                resource_id,
            ],
        )


def update_last_verified(
    resource_id: str, alive: bool, wayback_url: str = None
) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE resources SET last_verified_alive = ?, updated_at = ? WHERE id = ?",
            [
                datetime.now().date().isoformat(),
                datetime.now().isoformat(),
                resource_id,
            ],
        )
        if not alive:
            conn.execute(
                """INSERT INTO dead_links (resource_id, url, wayback_url)
                   SELECT id, url, ? FROM resources WHERE id = ?""",
                [wayback_url, resource_id],
            )


# ── Audit ──────────────────────────────────────────────────────────────────


def _log_action(
    conn: sqlite3.Connection, action: str, resource_id: str, detail: str
) -> None:
    conn.execute(
        "INSERT INTO audit_log (action, resource_id, detail) VALUES (?, ?, ?)",
        [action, resource_id, detail],
    )


def get_audit_log(limit: int = 50) -> List[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", [limit]
        ).fetchall()
    return [dict(r) for r in rows]


# ── AI Cache ──────────────────────────────────────────────────────────────


def get_ai_cache(input_hash: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT response FROM ai_cache WHERE input_hash = ?", [input_hash]
        ).fetchone()
    if row:
        return json.loads(row["response"])
    return None


def set_ai_cache(input_hash: str, task: str, response: dict, model: str = None) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO ai_cache (input_hash, task, response, model)
               VALUES (?, ?, ?, ?)""",
            [input_hash, task, json.dumps(response), model],
        )


# ── Stats ─────────────────────────────────────────────────────────────────


def get_pool_stats() -> dict:
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) as c FROM resources WHERE consumption_state != 'archived'"
        ).fetchone()["c"]

        by_domain = conn.execute(
            "SELECT domain, COUNT(*) as c FROM resources WHERE consumption_state != 'archived' GROUP BY domain ORDER BY c DESC"
        ).fetchall()

        by_type = conn.execute(
            "SELECT type, COUNT(*) as c FROM resources WHERE consumption_state != 'archived' GROUP BY type ORDER BY c DESC"
        ).fetchall()

        by_state = conn.execute(
            "SELECT consumption_state, COUNT(*) as c FROM resources GROUP BY consumption_state"
        ).fetchall()

        dead = conn.execute(
            "SELECT COUNT(*) as c FROM dead_links WHERE resolved = 0"
        ).fetchone()["c"]

        low_confidence = conn.execute(
            "SELECT COUNT(*) as c FROM resources WHERE ai_confidence < 70 AND ai_confidence IS NOT NULL"
        ).fetchone()["c"]

    return {
        "total": total,
        "by_domain": [dict(r) for r in by_domain],
        "by_type": [dict(r) for r in by_type],
        "by_state": [dict(r) for r in by_state],
        "dead_links": dead,
        "low_confidence": low_confidence,
    }


def get_pool_config() -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM pool_config").fetchall()
    return {r["key"]: r["value"] for r in rows}


def set_config(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO pool_config (key, value, updated_at) VALUES (?, ?, datetime('now'))",
            [key, value],
        )


def _get_conn():
    """Low-level connection (for maintenance API that needs direct SQL)."""
    import sqlite3

    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn
