"""
Initialize the poolmind SQLite database.
Creates all tables including FTS5 virtual table.
Run once: python scripts/init_db.py
"""

import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import get_db_path

SCHEMA = """
-- ─────────────────────────────────────────────────
-- CORE RESOURCES TABLE
-- ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS resources (
    id                    TEXT PRIMARY KEY,
    title                 TEXT NOT NULL,
    type                  TEXT NOT NULL DEFAULT 'article',
    url                   TEXT NOT NULL DEFAULT 'local',
    mirror_urls           TEXT DEFAULT '',
    author                TEXT,
    source_platform       TEXT DEFAULT 'other',

    domain                TEXT DEFAULT 'general',
    subdomain             TEXT,
    tags                  TEXT DEFAULT '',

    skill_level           TEXT DEFAULT 'intermediate',
    prerequisites         TEXT DEFAULT '',
    time_to_value         TEXT DEFAULT '30min',
    format                TEXT DEFAULT 'text',
    learning_path         TEXT,

    cost                  TEXT DEFAULT 'free',
    language              TEXT DEFAULT 'en',
    year_published        INTEGER,
    last_verified_alive   TEXT,
    last_updated_by_author TEXT,
    is_still_maintained   INTEGER,

    quality_score         INTEGER,
    personal_rating       INTEGER,
    times_used            INTEGER DEFAULT 0,
    last_used             TEXT,
    consumption_state     TEXT DEFAULT 'saved',
    temporal_relevance    TEXT DEFAULT 'evergreen',

    summary               TEXT,
    why_it_matters        TEXT,
    best_for              TEXT,
    avoid_if              TEXT,

    related_resources     TEXT DEFAULT '',
    next_step_resource    TEXT,

    added_by              TEXT DEFAULT 'user',
    added_on              TEXT NOT NULL,
    notes                 TEXT,
    ai_confidence         INTEGER,

    ai_disabled           INTEGER DEFAULT 0,
    ai_enriched           INTEGER DEFAULT 0,

    extended_meta         TEXT DEFAULT '{}',
    schema_version        TEXT DEFAULT '1.0',

    notion_page_id        TEXT,
    notion_last_synced    TEXT,

    -- Trash support
    deleted_at            TEXT,
    deleted_reason        TEXT,
    deleted_by            TEXT DEFAULT 'user',
    original_state        TEXT,
    trash_expires_at      TEXT,

    created_at            TEXT DEFAULT (datetime('now')),
    updated_at            TEXT DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────────────
-- FTS5 VIRTUAL TABLE (full-text search)
-- ─────────────────────────────────────────────────
CREATE VIRTUAL TABLE IF NOT EXISTS resources_fts USING fts5(
    id UNINDEXED,
    title,
    summary,
    tags,
    author,
    subdomain,
    notes,
    why_it_matters,
    content='resources',
    content_rowid='rowid'
);

-- ─────────────────────────────────────────────────
-- TRIGGERS: Keep FTS5 in sync with resources table
-- ─────────────────────────────────────────────────
CREATE TRIGGER IF NOT EXISTS resources_ai AFTER INSERT ON resources BEGIN
    INSERT INTO resources_fts(rowid, id, title, summary, tags, author, subdomain, notes, why_it_matters)
    VALUES (new.rowid, new.id, new.title, new.summary, new.tags, new.author, new.subdomain, new.notes, new.why_it_matters);
END;

CREATE TRIGGER IF NOT EXISTS resources_ad AFTER DELETE ON resources BEGIN
    INSERT INTO resources_fts(resources_fts, rowid, id, title, summary, tags, author, subdomain, notes, why_it_matters)
    VALUES('delete', old.rowid, old.id, old.title, old.summary, old.tags, old.author, old.subdomain, old.notes, old.why_it_matters);
END;

CREATE TRIGGER IF NOT EXISTS resources_au AFTER UPDATE ON resources BEGIN
    INSERT INTO resources_fts(resources_fts, rowid, id, title, summary, tags, author, subdomain, notes, why_it_matters)
    VALUES('delete', old.rowid, old.id, old.title, old.summary, old.tags, old.author, old.subdomain, old.notes, old.why_it_matters);
    INSERT INTO resources_fts(rowid, id, title, summary, tags, author, subdomain, notes, why_it_matters)
    VALUES (new.rowid, new.id, new.title, new.summary, new.tags, new.author, new.subdomain, new.notes, new.why_it_matters);
END;

-- ─────────────────────────────────────────────────
-- AUDIT LOG
-- ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action      TEXT NOT NULL,
    resource_id TEXT,
    detail      TEXT,
    timestamp   TEXT DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────────────
-- AI RESPONSE CACHE
-- ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_cache (
    input_hash  TEXT PRIMARY KEY,
    task        TEXT NOT NULL,
    response    TEXT NOT NULL,
    model       TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────────────
-- RESEARCH LOG (daily brief cache)
-- ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS research_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT NOT NULL,
    findings    TEXT NOT NULL,
    actioned    INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────────────
-- POOL CONFIG (key-value store for runtime state)
-- ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pool_config (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────────────
-- DEAD LINK TRACKER
-- ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dead_links (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id     TEXT NOT NULL,
    url             TEXT NOT NULL,
    http_status     INTEGER,
    checked_at      TEXT DEFAULT (datetime('now')),
    wayback_url     TEXT,
    resolved        INTEGER DEFAULT 0
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_resources_domain      ON resources(domain);
CREATE INDEX IF NOT EXISTS idx_resources_type        ON resources(type);
CREATE INDEX IF NOT EXISTS idx_resources_skill       ON resources(skill_level);
CREATE INDEX IF NOT EXISTS idx_resources_consumption ON resources(consumption_state);
CREATE INDEX IF NOT EXISTS idx_resources_added_on    ON resources(added_on);
CREATE INDEX IF NOT EXISTS idx_resources_quality     ON resources(quality_score);
CREATE INDEX IF NOT EXISTS idx_resources_platform    ON resources(source_platform);
CREATE INDEX IF NOT EXISTS idx_resources_deleted_at  ON resources(deleted_at);
CREATE INDEX IF NOT EXISTS idx_dead_links_resource   ON dead_links(resource_id);

-- ─────────────────────────────────────────────────────────────────────
-- PROMPT FEEDBACK LOG
-- Tracks outcome of every AI task call
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prompt_feedback (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    task                TEXT NOT NULL,
    prompt_version      TEXT NOT NULL,
    input_hash          TEXT NOT NULL,
    structural_success  INTEGER NOT NULL,
    field_coverage      REAL DEFAULT 0.0,
    confidence_reported INTEGER,
    user_corrected      INTEGER DEFAULT 0,
    correction_detail   TEXT,
    response_time_ms    INTEGER,
    model_used          TEXT,
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_feedback_task      ON prompt_feedback(task);
CREATE INDEX IF NOT EXISTS idx_feedback_success   ON prompt_feedback(structural_success);

-- ─────────────────────────────────────────────────────────────────────
-- PROMPT EVOLUTION LOG
-- Records every time a prompt was rewritten
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS prompt_evolution_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    task                TEXT NOT NULL,
    old_prompt_version  TEXT NOT NULL,
    new_prompt_version  TEXT NOT NULL,
    trigger_reason      TEXT,
    feedback_sample_size INTEGER,
    success_rate_before REAL,
    backup_path         TEXT,
    evolved_by          TEXT DEFAULT 'ai',
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_evolution_task     ON prompt_evolution_log(task);
"""


def init_db() -> None:
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        print(f"Database initialized: {db_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
