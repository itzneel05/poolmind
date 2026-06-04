"""
Background task queue for poolmind.
Fire-and-forget enrichment, sync, and maintenance via thread pool.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from models.resource import Resource

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)


def enrich_resource(resource: Resource):
    """Run AI enrichment + Obsidian + Notion in background."""
    from app.freellm_tasks import (
        classify_resource as ai_classify,
        summarize_resource as ai_summarize,
        generate_tags as ai_tags,
        suggest_related as ai_related,
    )
    from app import db, obsidian_writer, notion_sync

    try:
        db._set_enrichment_status(resource.id, "in_progress")
        body_text = ""
        url = resource.url
        title = resource.title

        ai_class = ai_classify(title=title, url=url, body_text=body_text)
        if ai_class:
            updates = {}
            for key in (
                "type",
                "domain",
                "subdomain",
                "skill_level",
                "format",
                "temporal_relevance",
                "time_to_value",
                "cost",
            ):
                if key in ai_class and not getattr(resource, key, None):
                    updates[key] = ai_class[key]
            if ai_class.get("confidence"):
                updates["ai_confidence"] = ai_class["confidence"]
            if updates:
                db._update_resource_fields(resource.id, updates)

        ai_sum = ai_summarize(title=title, body_text=body_text, url=url)
        if ai_sum:
            updates = {}
            if not resource.summary:
                updates["summary"] = ai_sum.get("summary")
            updates["why_it_matters"] = ai_sum.get("why_it_matters")
            updates["best_for"] = ai_sum.get("best_for")
            updates["avoid_if"] = ai_sum.get("avoid_if")
            if not resource.quality_score:
                updates["quality_score"] = ai_sum.get("quality_score")
            if updates:
                db._update_resource_fields(resource.id, updates)

        if not resource.tags:
            ai_tag_result = ai_tags(
                title=title,
                body_text=body_text,
                domain=resource.domain or "",
                type_=resource.type or "",
            )
            if ai_tag_result and ai_tag_result.get("tags"):
                db._update_resource_fields(resource.id, {"tags": ai_tag_result["tags"]})

        pool_titles = [r["title"] for r in db.get_all_titles_and_ids()]
        if pool_titles and (
            _has_field_changed(resource, "title") or not resource.related_resources
        ):
            related_result = ai_related(
                resource_title=title,
                resource_domain=resource.domain or "general",
                pool_titles=pool_titles,
            )
            if related_result:
                from app.add_resource import _resolve_titles_to_ids

                related_ids = _resolve_titles_to_ids(
                    related_result.get("related_titles", [])
                )
                next_title = related_result.get("next_step_title")
                next_id = None
                if next_title:
                    matched = _resolve_titles_to_ids([next_title])
                    next_id = matched[0] if matched else None
                db._update_resource_fields(
                    resource.id,
                    {
                        "related_resources": related_ids,
                        "next_step_resource": next_id,
                    },
                )

        db._set_enrichment_status(resource.id, "complete")
        db._update_resource_fields(resource.id, {"ai_enriched": True})
        logger.info("Background enrich complete for %s", resource.id)

        if os.getenv("OBSIDIAN_SYNC_ENABLED", "true").lower() == "true":
            try:
                obsidian_writer.write_note(resource)
            except Exception as e:
                logger.error(
                    "Background Obsidian write failed for %s: %s", resource.id, e
                )

        if os.getenv("NOTION_SYNC_ENABLED", "true").lower() == "true":
            try:
                notion_sync.sync_resource(resource)
            except Exception as e:
                logger.error("Background Notion sync failed for %s: %s", resource.id, e)

    except Exception as e:
        logger.error("Background enrich failed for %s: %s", resource.id, e)
        try:
            db._set_enrichment_status(resource.id, "failed")
        except Exception:
            pass


def _has_field_changed(resource: Resource, field: str) -> bool:
    return bool(getattr(resource, field, None))


ENRICH_TIMEOUT = 120


def submit_enrichment(resource: Resource):
    """Queue a resource for background enrichment with a 2-minute timeout."""
    _executor.submit(_enrich_with_timeout, resource)
    logger.info(
        "Queued background enrich for %s (timeout: %ds)", resource.id, ENRICH_TIMEOUT
    )


def _enrich_with_timeout(resource: Resource):
    """Run enrich_resource but enforce a total timeout. If exceeded, mark as failed and drop."""
    import threading

    result_box = []
    error_box = []

    def _run():
        try:
            enrich_resource(resource)
            result_box.append(True)
        except Exception as e:
            error_box.append(e)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(ENRICH_TIMEOUT)

    if t.is_alive():
        logger.warning(
            "Enrichment timed out for %s after %ds — dropping",
            resource.id,
            ENRICH_TIMEOUT,
        )
        try:
            from app import db

            db._set_enrichment_status(resource.id, "failed")
        except Exception:
            pass
        return

    if error_box:
        logger.error("Enrichment failed for %s: %s", resource.id, error_box[0])


# ── Background Ingestion ──
import uuid as _uuid
import threading as _threading

_ingestion_jobs: dict = {}
_ingestion_lock = _threading.Lock()


def start_ingestion(
    entries,
    ai_disabled: bool = False,
    skip_notion_sync: bool = False,
    skip_obsidian: bool = False,
) -> str:
    from app.ingest_router import ingest_entries, build_ingestion_report

    job_id = _uuid.uuid4().hex[:12]
    total = len(entries)

    with _ingestion_lock:
        _ingestion_jobs[job_id] = {
            "status": "running",
            "total": total,
            "current": 0,
            "added": 0,
            "duplicates": 0,
            "failed": 0,
            "needs_review": 0,
            "errors": [],
            "done": False,
        }

    def _run():
        def _on_progress(current, total, result):
            with _ingestion_lock:
                job = _ingestion_jobs.get(job_id)
                if not job:
                    return
                job["current"] = current
                if result.action == "added":
                    job["added"] += 1
                elif result.action == "duplicate":
                    job["duplicates"] += 1
                elif result.error:
                    job["failed"] += 1
                    job["errors"].append(
                        {"title": result.entry.title or "", "error": result.error}
                    )

        results = ingest_entries(
            entries=entries,
            ai_disabled=ai_disabled,
            skip_notion_sync=skip_notion_sync,
            skip_obsidian=skip_obsidian,
            on_progress=_on_progress,
        )
        report = build_ingestion_report(results)

        with _ingestion_lock:
            job = _ingestion_jobs.get(job_id)
            if job:
                job["status"] = "complete"
                job["done"] = True
                job["added"] = report["added"]
                job["duplicates"] = report["duplicates"]
                job["failed"] = report["failed"]
                job["needs_review"] = report["needs_review"]
                job["report"] = report

    _executor.submit(_run)
    return job_id


def get_ingestion_status(job_id: str) -> dict:
    with _ingestion_lock:
        job = _ingestion_jobs.get(job_id)
        if not job:
            return {"status": "not_found", "done": True}
        return dict(job)
