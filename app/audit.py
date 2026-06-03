"""
Audit module for poolmind.
Dead link checking, low-confidence flagging, stale content detection,
gap analysis, and pool statistics.
"""

import logging
import os
import time
from typing import List, Optional

import requests

from app import db
from app.freellm_tasks import gap_analysis as ai_gap_analysis
from app.normalizer import get_wayback_url
from models.resource import Resource

logger = logging.getLogger(__name__)


def dead_check(
    limit: int = 50, update_db: bool = True, auto_tombstone: bool = False
) -> dict:
    interval = int(os.getenv("LINK_CHECK_INTERVAL_DAYS", "90"))
    stale = db.get_stale_resources(days=interval)[:limit]

    results = {
        "checked": 0,
        "alive": 0,
        "dead": [],
        "tombstoned": [],
        "redirected": [],
        "skipped": 0,
    }

    for resource in stale:
        if resource.url == "local":
            results["skipped"] += 1
            continue

        status = _check_url(resource.url)
        results["checked"] += 1

        if status["alive"]:
            results["alive"] += 1
            if update_db:
                db.update_last_verified(resource.id, alive=True)
        else:
            wayback = get_wayback_url(resource.url)
            dead_entry = {
                "id": resource.id,
                "title": resource.title,
                "url": resource.url,
                "status": status["http_status"],
                "wayback": wayback,
            }
            results["dead"].append(dead_entry)

            if update_db:
                db.update_last_verified(resource.id, alive=False, wayback_url=wayback)

            if auto_tombstone:
                db.update_resource(resource.id, {"consumption_state": "archived"})
                results["tombstoned"].append(dead_entry)
                logger.info(
                    "Tombstoned dead resource: %s %s", resource.id, resource.title
                )

        time.sleep(0.5)

    return results


def _check_url(url: str, timeout: int = 10) -> dict:
    try:
        resp = requests.head(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": "poolmind/1.0 (link-checker)"},
        )
        alive = resp.status_code < 400
        return {"alive": alive, "http_status": resp.status_code}
    except requests.exceptions.ConnectionError:
        return {"alive": False, "http_status": 0}
    except requests.exceptions.Timeout:
        return {"alive": False, "http_status": -1}
    except Exception as e:
        logger.warning("Link check error for %s: %s", url, e)
        return {"alive": False, "http_status": -2}


def get_low_confidence_resources(threshold: int = 70) -> List[Resource]:
    from app.db import get_db_path
    import sqlite3

    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT * FROM resources
               WHERE ai_confidence < ? AND ai_confidence IS NOT NULL
               AND consumption_state != 'archived'
               ORDER BY ai_confidence ASC
               LIMIT 50""",
            [threshold],
        ).fetchall()
        return [Resource.from_db_row(dict(r)) for r in rows]
    finally:
        conn.close()


def get_stale_content(months: int = 24) -> List[Resource]:
    from app.db import get_db_path
    import sqlite3

    cutoff_year = 2024 - (months // 12)
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT * FROM resources
               WHERE temporal_relevance IN ('time-sensitive', 'emerging')
               AND (year_published IS NOT NULL AND year_published < ?)
               AND consumption_state != 'archived'
               ORDER BY year_published ASC
               LIMIT 30""",
            [cutoff_year],
        ).fetchall()
        return [Resource.from_db_row(dict(r)) for r in rows]
    finally:
        conn.close()


def run_gap_analysis() -> Optional[dict]:
    stats = db.get_pool_stats()
    result = ai_gap_analysis(stats)
    return result


def run_gap_report() -> Optional[dict]:
    from app.freellm_tasks import generate_gap_report

    stats = db.get_pool_stats()
    low_conf = get_low_confidence_resources()
    stale = get_stale_content()
    audit_data = {
        "low_confidence_count": len(low_conf),
        "low_confidence_sample": [
            {"id": r.id, "title": r.title, "confidence": r.ai_confidence}
            for r in low_conf[:5]
        ],
        "stale_content_count": len(stale),
        "stale_sample": [
            {"id": r.id, "title": r.title, "year": r.year_published} for r in stale[:5]
        ],
    }
    return generate_gap_report(stats, audit_data)


def full_audit() -> dict:
    import datetime

    stats = db.get_pool_stats()
    low_conf = get_low_confidence_resources()
    stale = get_stale_content()
    gaps = run_gap_analysis()
    dead = dead_check(limit=20)

    return {
        "stats": stats,
        "low_confidence_count": len(low_conf),
        "low_confidence_sample": [
            {"id": r.id, "title": r.title, "ai_confidence": r.ai_confidence}
            for r in low_conf[:5]
        ],
        "stale_content_count": len(stale),
        "stale_sample": [
            {"id": r.id, "title": r.title, "year": r.year_published} for r in stale[:5]
        ],
        "dead_links": dead,
        "gaps": gaps,
    }
