"""
Ingestion router for poolmind.

Takes parsed entries from bulk_parser and routes each one
to the correct ingestion method:
  - Has URL -> add_from_url (full extraction + AI pipeline)
  - Title only -> add_manual (minimal metadata, AI enrichment)
  - Notion page -> notion_page_extractor (specialized)
  - Extra URLs in entry -> queue as additional entries

Produces a detailed ingestion report with progress tracking.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from app.bulk_parser import ParsedEntry
from models.resource import Resource

logger = logging.getLogger(__name__)

REQUEST_DELAY = 1.0
NOTION_REQUEST_DELAY = 0.5


@dataclass
class IngestionResult:
    entry: ParsedEntry
    success: bool
    resource: Optional[Resource] = None
    action: str = ""
    error: Optional[str] = None
    elapsed_ms: int = 0


def ingest_entries(
    entries: List[ParsedEntry],
    ai_disabled: bool = False,
    skip_notion_sync: bool = False,
    skip_obsidian: bool = False,
    dry_run: bool = False,
    on_progress: Optional[Callable] = None,
) -> List[IngestionResult]:
    results: List[IngestionResult] = []
    total = len(entries)

    for idx, entry in enumerate(entries):
        t_start = time.monotonic()

        if dry_run:
            result = IngestionResult(
                entry=entry,
                success=True,
                action="dry_run",
                elapsed_ms=0,
            )
            results.append(result)
            if on_progress:
                on_progress(idx + 1, total, result)
            continue

        result = _route_entry(
            entry=entry,
            ai_disabled=ai_disabled,
            skip_notion_sync=skip_notion_sync,
            skip_obsidian=skip_obsidian,
        )
        result.elapsed_ms = int((time.monotonic() - t_start) * 1000)
        results.append(result)

        if on_progress:
            on_progress(idx + 1, total, result)

        if entry.url and idx < total - 1:
            delay = NOTION_REQUEST_DELAY if _is_notion_url(entry.url) else REQUEST_DELAY
            time.sleep(delay)

    return results


def _route_entry(
    entry: ParsedEntry,
    ai_disabled: bool,
    skip_notion_sync: bool,
    skip_obsidian: bool,
) -> IngestionResult:
    if entry.entry_type == "notion_page" and entry.url:
        return _ingest_notion_page(entry, ai_disabled, skip_notion_sync, skip_obsidian)

    if entry.url:
        return _ingest_url(entry, ai_disabled, skip_notion_sync, skip_obsidian)

    if entry.title and not entry.url:
        return _ingest_title_only(entry, ai_disabled, skip_notion_sync, skip_obsidian)

    return IngestionResult(
        entry=entry,
        success=False,
        action="skipped",
        error="no_url_no_title",
    )


def _ingest_url(
    entry: ParsedEntry,
    ai_disabled: bool,
    skip_notion_sync: bool,
    skip_obsidian: bool,
) -> IngestionResult:
    from app.add_resource import add_from_url
    from app.dedupe import check_duplicate

    dup = check_duplicate(url=entry.url, title=entry.title)
    if dup:
        return IngestionResult(
            entry=entry,
            success=True,
            resource=dup,
            action="duplicate",
        )

    try:
        resource = add_from_url(
            url=entry.url,
            notes=entry.notes or "",
            ai_disabled=ai_disabled,
            skip_notion=skip_notion_sync,
            skip_obsidian=skip_obsidian,
            force=False,
        )

        if (
            resource
            and entry.title
            and not _is_url_derived_title(entry.title, entry.url)
        ):
            from app import db

            db.update_resource(resource.id, {"title": entry.title})
            resource.title = entry.title

        if resource:
            return IngestionResult(
                entry=entry,
                success=True,
                resource=resource,
                action="added",
            )
        else:
            return IngestionResult(
                entry=entry,
                success=False,
                action="failed",
                error="add_from_url_returned_none",
            )

    except Exception as e:
        logger.error("Failed to ingest URL %s: %s", entry.url, e)
        return IngestionResult(
            entry=entry,
            success=False,
            action="failed",
            error=str(e)[:200],
        )


def _ingest_notion_page(
    entry: ParsedEntry,
    ai_disabled: bool,
    skip_notion_sync: bool,
    skip_obsidian: bool,
) -> IngestionResult:
    import os
    from app.add_resource import add_manual

    notion_token = os.getenv("NOTION_TOKEN", "")
    page_id = _extract_notion_page_id(entry.url)

    if notion_token and page_id:
        notion_meta = _fetch_notion_page_meta(page_id, notion_token)
        if notion_meta:
            fields = {
                "title": notion_meta.get("title") or entry.title or "Notion Page",
                "url": entry.url,
                "type": "note",
                "source_platform": "notion",
                "format": "text",
                "cost": "free",
                "notes": entry.notes or "",
                "summary": notion_meta.get("summary", ""),
                "added_by": "user",
            }
            resource = add_manual(fields)
            if resource:
                return IngestionResult(
                    entry=entry,
                    success=True,
                    resource=resource,
                    action="added",
                )

    title = entry.title or _title_from_notion_url_local(entry.url)
    resource = add_manual(
        {
            "title": title,
            "url": entry.url,
            "type": "note",
            "source_platform": "notion",
            "format": "text",
            "cost": "free",
            "notes": (entry.notes or "")
            + " [Notion page - content not extracted, auth required]",
            "added_by": "user",
            "ai_confidence": 40,
        }
    )

    if resource:
        return IngestionResult(
            entry=entry,
            success=True,
            resource=resource,
            action="added",
        )

    return IngestionResult(
        entry=entry,
        success=False,
        action="failed",
        error="notion_page_ingestion_failed",
    )


def _ingest_title_only(
    entry: ParsedEntry,
    ai_disabled: bool,
    skip_notion_sync: bool,
    skip_obsidian: bool,
) -> IngestionResult:
    from app.dedupe import check_duplicate
    from app.add_resource import add_manual

    dup = check_duplicate(title=entry.title)
    if dup:
        return IngestionResult(
            entry=entry,
            success=True,
            resource=dup,
            action="duplicate",
        )

    resource = add_manual(
        {
            "title": entry.title,
            "url": "local",
            "type": "note",
            "domain": "general",
            "notes": (entry.notes or "") + " [No URL provided - needs manual review]",
            "added_by": "user",
            "ai_confidence": 0,
            "consumption_state": "saved",
        }
    )

    if resource:
        return IngestionResult(
            entry=entry,
            success=True,
            resource=resource,
            action="needs_review",
        )

    return IngestionResult(
        entry=entry,
        success=False,
        action="failed",
        error="manual_add_failed",
    )


def _extract_notion_page_id(url: str) -> Optional[str]:
    import re

    match = re.search(
        r"([a-f0-9]{32}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})",
        url,
    )
    if match:
        return match.group(1).replace("-", "")
    return None


def _fetch_notion_page_meta(page_id: str, token: str) -> Optional[dict]:
    import requests

    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
    }

    try:
        resp = requests.get(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=headers,
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning(
                "Notion API returned %d for page %s", resp.status_code, page_id
            )
            return None

        data = resp.json()
        title = _extract_notion_title(data)
        summary = _fetch_notion_first_block(page_id, headers)

        return {"title": title, "summary": summary}

    except Exception as e:
        logger.warning("Notion API fetch failed for %s: %s", page_id, e)
        return None


def _extract_notion_title(page_data: dict) -> str:
    try:
        props = page_data.get("properties", {})
        for prop_name in ("Name", "Title", "title", "name"):
            prop = props.get(prop_name, {})
            if prop.get("type") == "title":
                texts = prop.get("title", [])
                if texts:
                    return "".join(t.get("plain_text", "") for t in texts).strip()
        for prop in props.values():
            if prop.get("type") == "title":
                texts = prop.get("title", [])
                if texts:
                    return "".join(t.get("plain_text", "") for t in texts).strip()
    except Exception:
        pass
    return "Notion Page"


def _fetch_notion_first_block(page_id: str, headers: dict) -> str:
    import requests

    try:
        resp = requests.get(
            f"https://api.notion.com/v1/blocks/{page_id}/children?page_size=5",
            headers=headers,
            timeout=10,
        )
        if resp.status_code != 200:
            return ""
        blocks = resp.json().get("results", [])
        text_parts = []
        for block in blocks:
            block_type = block.get("type", "")
            block_content = block.get(block_type, {})
            rich_texts = block_content.get("rich_text", [])
            for rt in rich_texts:
                text_parts.append(rt.get("plain_text", ""))
            if len(" ".join(text_parts)) > 400:
                break
        return " ".join(text_parts)[:500].strip()
    except Exception:
        return ""


def _title_from_notion_url_local(url: str) -> str:
    import re
    from urllib.parse import urlparse

    path = urlparse(url).path
    parts = [p for p in path.split("/") if p]
    if not parts:
        return "Notion Page"
    last = parts[-1]
    slug = re.sub(r"-[a-f0-9]{32}$", "", last)
    slug = re.sub(r"-[a-f0-9]{8,}$", "", slug)
    return slug.replace("-", " ").title() if slug else "Notion Page"


def _is_notion_url(url: str) -> bool:
    return "notion.so" in url.lower()


def _is_url_derived_title(title: str, url: str) -> bool:
    if not title or not url:
        return False
    from urllib.parse import urlparse

    path = urlparse(url).path.lower()
    title_words = title.lower().split()
    if len(title_words) < 2:
        return True
    matches = sum(1 for w in title_words if w in path)
    return matches / len(title_words) > 0.8


def build_ingestion_report(results: List[IngestionResult]) -> dict:
    total = len(results)
    added = [r for r in results if r.action == "added"]
    duplicates = [r for r in results if r.action == "duplicate"]
    failed = [r for r in results if r.action == "failed"]
    needs_review = [r for r in results if r.action == "needs_review"]
    skipped = [r for r in results if r.action == "skipped"]

    avg_time = sum(r.elapsed_ms for r in results) / total if total > 0 else 0

    return {
        "total": total,
        "added": len(added),
        "duplicates": len(duplicates),
        "failed": len(failed),
        "needs_review": len(needs_review),
        "skipped": len(skipped),
        "avg_time_ms": round(avg_time),
        "added_ids": [r.resource.id for r in added if r.resource],
        "failed_entries": [
            {
                "line": r.entry.line_number,
                "raw": r.entry.raw_line[:80],
                "error": r.error,
            }
            for r in failed
        ],
        "needs_review_entries": [
            {"id": r.resource.id if r.resource else None, "title": r.entry.title}
            for r in needs_review
        ],
    }
