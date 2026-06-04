"""
Notion sync module for poolmind.
One-way sync: local SQLite -> Notion database.
Notion is the dashboard — local is source of truth.
"""

import logging
import os
import time
from typing import Optional

import requests
import yaml

from app import db
from models.resource import Resource

logger = logging.getLogger(__name__)

NOTION_VERSION = "2022-06-28"
RATE_LIMIT_SLEEP = float(os.getenv("NOTION_RATE_LIMIT_SLEEP", "0.35"))


def _get_token() -> str:
    token = os.getenv("NOTION_TOKEN", "")
    if not token:
        raise ValueError("NOTION_TOKEN not set in environment")
    return token


def _get_database_id() -> str:
    db_id = os.getenv("NOTION_DATABASE_ID", "") or os.getenv("NOTION_DATABASE", "")
    if not db_id:
        raise ValueError("NOTION_DATABASE not set in environment")
    return db_id


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_token()}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _load_property_map() -> dict:
    config_path = "config/notion.yaml"
    try:
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        return cfg.get("properties", {})
    except Exception:
        logger.warning("notion.yaml not found — using default property names")
        return {}


def archive_resource(notion_page_id: str) -> bool:
    """Archive a Notion page (move to trash in Notion)."""
    if not os.getenv("NOTION_SYNC_ENABLED", "true").lower() == "true":
        return False
    try:
        _get_token()
    except ValueError:
        return False
    time.sleep(RATE_LIMIT_SLEEP)
    resp = requests.patch(
        f"https://api.notion.com/v1/pages/{notion_page_id}",
        headers=_headers(),
        json={"archived": True},
        timeout=30,
    )
    return resp.status_code == 200


def unarchive_resource(notion_page_id: str) -> bool:
    """Unarchive a Notion page (restore from trash in Notion)."""
    if not os.getenv("NOTION_SYNC_ENABLED", "true").lower() == "true":
        return False
    try:
        _get_token()
    except ValueError:
        return False
    time.sleep(RATE_LIMIT_SLEEP)
    resp = requests.patch(
        f"https://api.notion.com/v1/pages/{notion_page_id}",
        headers=_headers(),
        json={"archived": False},
        timeout=30,
    )
    return resp.status_code == 200


def sync_resource(resource: Resource) -> Optional[str]:
    if not os.getenv("NOTION_SYNC_ENABLED", "true").lower() == "true":
        return None

    try:
        token = _get_token()
        database_id = _get_database_id()
    except ValueError as e:
        logger.warning("Notion sync skipped: %s", e)
        return None

    props = _build_properties(resource)
    payload = {"properties": props}

    time.sleep(RATE_LIMIT_SLEEP)

    if resource.notion_page_id:
        resp = requests.patch(
            f"https://api.notion.com/v1/pages/{resource.notion_page_id}",
            headers=_headers(),
            json=payload,
            timeout=30,
        )
    else:
        payload["parent"] = {"database_id": database_id}
        resp = requests.post(
            "https://api.notion.com/v1/pages",
            headers=_headers(),
            json=payload,
            timeout=30,
        )

    if resp.status_code in (200, 201):
        page_id = resp.json()["id"]
        db.update_notion_id(resource.id, page_id)
        logger.info("Notion sync success: %s -> %s", resource.id, page_id)
        return page_id
    else:
        logger.error(
            "Notion sync failed for %s: %d %s",
            resource.id,
            resp.status_code,
            resp.text[:200],
        )
        return None


def get_sync_status() -> dict:
    token = os.getenv("NOTION_TOKEN", "")
    database_id = os.getenv("NOTION_DATABASE", "") or os.getenv(
        "NOTION_DATABASE_ID", ""
    )
    enabled = os.getenv("NOTION_SYNC_ENABLED", "true").lower() == "true"
    unsynced_count = len(db.get_unsynced_notion(limit=9999))
    return {
        "configured": bool(token and database_id),
        "has_token": bool(token),
        "has_database": bool(database_id),
        "enabled": enabled,
        "unsynced_count": unsynced_count,
        "database_id": database_id,
        "token_set": bool(token),
    }


def notion_page_url(page_id: str) -> Optional[str]:
    """Build a Notion page URL from a Notion page UUID."""
    if not page_id:
        return None
    return f"https://www.notion.so/{page_id.replace('-', '')}"


def notion_database_url() -> Optional[str]:
    """Build a Notion database URL from the configured database ID."""
    db_id = os.getenv("NOTION_DATABASE", "") or os.getenv("NOTION_DATABASE_ID", "")
    if not db_id:
        return None
    return f"https://www.notion.so/{db_id.replace('-', '')}"


def get_sync_log(limit: int = 50) -> list:
    return [
        r for r in db.get_audit_log(limit) if r.get("action") in ("sync", "notion_sync")
    ]


def sync_all_pending(batch_size: int = 10) -> dict:
    unsynced = db.get_unsynced_notion(limit=batch_size)
    results = {"synced": 0, "failed": 0}

    for resource in unsynced:
        page_id = sync_resource(resource)
        if page_id:
            results["synced"] += 1
        else:
            results["failed"] += 1

    return results


def _build_properties(resource: Resource) -> dict:
    prop_map = _load_property_map()

    def prop_name(key: str) -> str:
        return prop_map.get(key, key.replace("_", " ").title())

    props = {}

    props[prop_name("title")] = {
        "title": [{"text": {"content": resource.title[:2000]}}]
    }

    for field, value in [
        ("resource_id", resource.id),
        ("subdomain", resource.subdomain or ""),
        ("summary", (resource.summary or "")[:2000]),
        ("why_it_matters", (resource.why_it_matters or "")[:2000]),
        ("author", resource.author or ""),
        ("time_to_value", resource.time_to_value),
        ("learning_path", resource.learning_path or ""),
    ]:
        if value:
            props[prop_name(field)] = {"rich_text": [{"text": {"content": str(value)}}]}

    if resource.url and resource.url != "local":
        props[prop_name("url")] = {"url": resource.url}

    for field, value in [
        ("type", resource.type),
        ("domain", resource.domain),
        ("skill_level", resource.skill_level),
        ("format", resource.format),
        ("cost", resource.cost),
        ("temporal_relevance", resource.temporal_relevance),
        ("consumption_state", resource.consumption_state),
        ("source_platform", resource.source_platform),
    ]:
        if value:
            props[prop_name(field)] = {"select": {"name": value}}

    if resource.tags:
        props[prop_name("tags")] = {
            "multi_select": [{"name": t[:100]} for t in resource.tags[:15]]
        }

    for field, value in [
        ("quality_score", resource.quality_score),
        ("personal_rating", resource.personal_rating),
        ("times_used", resource.times_used),
        ("ai_confidence", resource.ai_confidence),
        ("year_published", resource.year_published),
    ]:
        if value is not None:
            props[prop_name(field)] = {"number": value}

    if resource.is_still_maintained is not None:
        props[prop_name("is_still_maintained")] = {
            "checkbox": bool(resource.is_still_maintained)
        }

    for field, value in [
        ("added_on", resource.added_on),
        ("last_used", resource.last_used),
        ("last_verified_alive", resource.last_verified_alive),
    ]:
        if value:
            try:
                props[prop_name(field)] = {"date": {"start": value}}
            except Exception:
                pass

    return props
