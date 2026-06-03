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


def submit_enrichment(resource: Resource):
    """Queue a resource for background enrichment."""
    _executor.submit(enrich_resource, resource)
    logger.info("Queued background enrich for %s", resource.id)
