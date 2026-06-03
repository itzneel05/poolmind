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


# ── Trash ──────────────────────────────────────────────────────────────────


def _ensure_enrichment_column():
    """Add enrichment_status column to existing databases."""
    try:
        with get_conn() as conn:
            conn.execute(
                "ALTER TABLE resources ADD COLUMN enrichment_status TEXT DEFAULT 'pending'"
            )
    except Exception:
        pass


def _set_enrichment_status(resource_id: str, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE resources SET enrichment_status = ?, updated_at = ? WHERE id = ?",
            [status, datetime.now().isoformat(), resource_id],
        )


def _update_resource_fields(resource_id: str, fields: dict):
    if not fields:
        return
    sets = []
    vals = []
    for key, val in fields.items():
        if isinstance(val, list):
            sets.append(f"{key} = ?")
            vals.append(",".join(str(v) for v in val))
        elif val is not None:
            sets.append(f"{key} = ?")
            vals.append(str(val))
    if not sets:
        return
    sets.append("updated_at = ?")
    vals.append(datetime.now().isoformat())
    vals.append(resource_id)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE resources SET {', '.join(sets)} WHERE id = ?",
            vals,
        )


def _ensure_trash_columns():
    """Add trash columns to existing databases (safe to run repeatedly)."""
    cols = [
        "deleted_at TEXT",
        "deleted_reason TEXT",
        "deleted_by TEXT DEFAULT 'user'",
        "original_state TEXT",
        "trash_expires_at TEXT",
    ]
    for col_def in cols:
        col_name = col_def.split()[0]
        try:
            with get_conn() as conn:
                conn.execute(f"ALTER TABLE resources ADD COLUMN {col_def}")
        except Exception:
            pass
    try:
        with get_conn() as conn:
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_resources_deleted_at ON resources(deleted_at)"
            )
    except Exception:
        pass


def trash_resources(resource_ids: list, reason: str = None) -> dict:
    now = datetime.now().isoformat()
    trashed = 0
    for rid in resource_ids:
        res = get_resource(rid)
        if not res:
            continue
        orig_state = res.consumption_state
        with get_conn() as conn:
            cur = conn.execute(
                """UPDATE resources SET deleted_at = ?, deleted_reason = ?,
                   deleted_by = 'user', original_state = ?, updated_at = ?
                   WHERE id = ?""",
                [now, reason, orig_state, now, rid],
            )
            if cur.rowcount > 0:
                trashed += 1
                _log_action(conn, "trash", rid, reason or "No reason given")
    return {"trashed": trashed}


def restore_resources(resource_ids: list) -> dict:
    restored = 0
    for rid in resource_ids:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT original_state FROM resources WHERE id = ? AND deleted_at IS NOT NULL",
                [rid],
            ).fetchone()
            if not row:
                continue
            orig = row["original_state"] or "saved"
            cur = conn.execute(
                """UPDATE resources SET deleted_at = NULL, deleted_reason = NULL,
                   deleted_by = 'user', original_state = NULL,
                   trash_expires_at = NULL, consumption_state = ?,
                   updated_at = ?
                   WHERE id = ?""",
                [orig, datetime.now().isoformat(), rid],
            )
            if cur.rowcount > 0:
                restored += 1
                _log_action(conn, "restore", rid, f"Restored to state: {orig}")
    return {"restored": restored}


def check_restore_conflicts(resource_ids: list) -> list:
    """Check if restoring resources would create URL conflicts with active resources."""
    conflicts = []
    for rid in resource_ids:
        trashed = get_resource(rid, include_trashed=True)
        if not trashed or not trashed.url or trashed.url == "local":
            continue
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT id, title FROM resources WHERE url = ? AND deleted_at IS NULL AND id != ?",
                [trashed.url, rid],
            ).fetchall()
            for r in rows:
                conflicts.append(
                    {
                        "trashed_id": rid,
                        "existing_id": r["id"],
                        "existing_title": r["title"],
                        "url": trashed.url,
                    }
                )
    return conflicts


def purge_resources(resource_ids: list) -> dict:
    purged = 0
    for rid in resource_ids:
        with get_conn() as conn:
            cur = conn.execute(
                "DELETE FROM resources WHERE id = ? AND deleted_at IS NOT NULL",
                [rid],
            )
            if cur.rowcount > 0:
                purged += 1
                _log_action(conn, "purge", rid, "Permanently deleted")
                _cleanup_orphan_references(conn, rid)
    return {"purged": purged}


def _cleanup_orphan_references(conn, purged_id: str):
    """Remove references to a purged resource from other resources."""
    rows = conn.execute(
        "SELECT id, related_resources FROM resources WHERE related_resources IS NOT NULL AND related_resources != ''"
    ).fetchall()
    for row in rows:
        ids = [r.strip() for r in row["related_resources"].split(",")]
        if purged_id in ids:
            cleaned = [r for r in ids if r != purged_id]
            conn.execute(
                "UPDATE resources SET related_resources = ?, updated_at = ? WHERE id = ?",
                [",".join(cleaned), datetime.now().isoformat(), row["id"]],
            )
    conn.execute(
        "UPDATE resources SET next_step_resource = NULL, updated_at = ? WHERE next_step_resource = ?",
        [datetime.now().isoformat(), purged_id],
    )


def get_trashed_resources(
    search_q: str = None,
    domain: str = None,
    type_: str = None,
    sort: str = "deleted_at",
    limit: int = 50,
    offset: int = 0,
) -> list:
    where = ["deleted_at IS NOT NULL"]
    params = []
    if search_q:
        where.append("(title LIKE ? OR id LIKE ?)")
        params.extend([f"%{search_q}%", f"%{search_q}%"])
    if domain:
        where.append("domain = ?")
        params.append(domain)
    if type_:
        where.append("type = ?")
        params.append(type_)
    order = "deleted_at DESC" if sort == "deleted_at" else "title ASC"
    sql = f"SELECT * FROM resources WHERE {' AND '.join(where)} ORDER BY {order} LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_trash_count() -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as c FROM resources WHERE deleted_at IS NOT NULL"
        ).fetchone()
    return row["c"]


def get_trash_stats() -> dict:
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) as c FROM resources WHERE deleted_at IS NOT NULL"
        ).fetchone()["c"]
        oldest = conn.execute(
            "SELECT MIN(deleted_at) as o FROM resources WHERE deleted_at IS NOT NULL"
        ).fetchone()["o"]
        expiring = conn.execute(
            """SELECT COUNT(*) as c FROM resources
               WHERE deleted_at IS NOT NULL
               AND trash_expires_at IS NOT NULL
               AND trash_expires_at < datetime('now', '+7 days')"""
        ).fetchone()["c"]
        by_domain = conn.execute(
            "SELECT domain, COUNT(*) as c FROM resources WHERE deleted_at IS NOT NULL GROUP BY domain ORDER BY c DESC"
        ).fetchall()
    return {
        "total": total,
        "oldest": oldest,
        "expiring_soon": expiring,
        "by_domain": [dict(r) for r in by_domain],
    }


def purge_expired_trash() -> dict:
    """Automatically purge resources past their trash_expires_at date."""
    ids = []
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT id FROM resources
               WHERE deleted_at IS NOT NULL
               AND trash_expires_at IS NOT NULL
               AND trash_expires_at < datetime('now')"""
        ).fetchall()
        ids = [r["id"] for r in rows]
    if not ids:
        return {"purged": 0}
    result = purge_resources(ids)
    logger.info("Auto-purge: removed %d expired items", result["purged"])
    return result


def nuke_trash(confirmation: str) -> dict:
    if confirmation != "NUKE":
        return {"error": "Confirmation phrase 'NUKE' required"}
    ids = []
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id FROM resources WHERE deleted_at IS NOT NULL"
        ).fetchall()
        ids = [r["id"] for r in rows]
    if not ids:
        return {"nuked": 0}
    result = purge_resources(ids)
    return result


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


def get_resource(resource_id: str, include_trashed: bool = False) -> Optional[Resource]:
    where = "id = ?" if include_trashed else "id = ? AND deleted_at IS NULL"
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT * FROM resources WHERE {where}", [resource_id]
        ).fetchone()
    if row:
        return Resource.from_db_row(dict(row))
    return None


def get_by_url(url: str) -> Optional[Resource]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM resources WHERE url = ? AND deleted_at IS NULL", [url]
        ).fetchone()
    if row:
        return Resource.from_db_row(dict(row))
    return None


def get_all_resources(
    limit: int = 100, offset: int = 0, exclude_archived: bool = True
) -> List[Resource]:
    where = "WHERE deleted_at IS NULL"
    if exclude_archived:
        where += " AND consumption_state != 'archived'"
    sql = f"SELECT * FROM resources {where} ORDER BY added_on DESC LIMIT ? OFFSET ?"
    with get_conn() as conn:
        rows = conn.execute(sql, [limit, offset]).fetchall()
    return [Resource.from_db_row(dict(r)) for r in rows]


def get_all_titles_and_ids() -> List[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, url FROM resources WHERE deleted_at IS NULL"
        ).fetchall()
    return [dict(r) for r in rows]


def count_resources() -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as c FROM resources WHERE deleted_at IS NULL AND consumption_state != 'archived'"
        ).fetchone()
    return row["c"]


def get_stale_resources(days: int = 90) -> List[Resource]:
    sql = """
        SELECT * FROM resources
        WHERE deleted_at IS NULL
        AND (
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
            "SELECT * FROM resources WHERE deleted_at IS NULL AND domain = ? AND consumption_state != 'archived'",
            [domain],
        ).fetchall()
    return [Resource.from_db_row(dict(r)) for r in rows]


def get_unsynced_notion(limit: int = 50) -> List[Resource]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM resources WHERE deleted_at IS NULL AND notion_page_id IS NULL ORDER BY added_on DESC LIMIT ?",
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


def count_audit_entries() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) as c FROM audit_log").fetchone()
    return row["c"]


def get_audit_log(limit: int = 50, offset: int = 0) -> List[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            [limit, offset],
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
            "SELECT COUNT(*) as c FROM resources WHERE deleted_at IS NULL AND consumption_state != 'archived'"
        ).fetchone()["c"]

        trashed = conn.execute(
            "SELECT COUNT(*) as c FROM resources WHERE deleted_at IS NOT NULL"
        ).fetchone()["c"]

        by_domain = conn.execute(
            "SELECT domain, COUNT(*) as c FROM resources WHERE deleted_at IS NULL AND consumption_state != 'archived' GROUP BY domain ORDER BY c DESC"
        ).fetchall()

        by_type = conn.execute(
            "SELECT type, COUNT(*) as c FROM resources WHERE deleted_at IS NULL AND consumption_state != 'archived' GROUP BY type ORDER BY c DESC"
        ).fetchall()

        by_state = conn.execute(
            "SELECT consumption_state, COUNT(*) as c FROM resources WHERE deleted_at IS NULL GROUP BY consumption_state"
        ).fetchall()

        dead = conn.execute(
            "SELECT COUNT(*) as c FROM dead_links WHERE resolved = 0"
        ).fetchone()["c"]

        low_confidence = conn.execute(
            "SELECT COUNT(*) as c FROM resources WHERE ai_confidence < 70 AND ai_confidence IS NOT NULL"
        ).fetchone()["c"]

    return {
        "total": total,
        "trashed": trashed,
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
