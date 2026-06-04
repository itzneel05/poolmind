"""
Main resource ingestion pipeline.
Capture -> Extract -> Classify -> Normalize -> AI Enrich -> Validate -> Store
"""

import logging
import os
from typing import Optional

from models.resource import Resource
from app import db, classifier, normalizer, obsidian_writer, notion_sync
from app.extractors import extract_metadata
from app.freellm_tasks import (
    classify_resource as ai_classify,
    summarize_resource as ai_summarize,
    generate_tags as ai_tags,
    suggest_related as ai_related,
)
from app.dedupe import check_duplicate

logger = logging.getLogger(__name__)


def _enforce_summary(
    extracted: dict, title: str, url: str = "", body_text: str = ""
) -> dict:
    summary = (extracted.get("summary") or "").strip()
    if len(summary) >= 80:
        return extracted
    try:
        from app.freellm_tasks import summarize_resource

        ai_sum = summarize_resource(
            title=title, body_text=body_text or summary, url=url
        )
        if (
            ai_sum
            and ai_sum.get("summary")
            and len(ai_sum["summary"].strip()) > len(summary)
        ):
            extracted["summary"] = ai_sum["summary"]
            extracted["why_it_matters"] = ai_sum.get("why_it_matters")
            extracted["best_for"] = ai_sum.get("best_for")
            extracted["avoid_if"] = ai_sum.get("avoid_if")
            extracted["quality_score"] = ai_sum.get(
                "quality_score", extracted.get("quality_score")
            )
            return extracted
    except Exception:
        pass

    if len((extracted.get("summary") or "").strip()) < 80:
        domain = extracted.get("domain", "general")
        type_ = extracted.get("type", "resource")
        fallback = f"A {type_} in the {domain} domain"
        if extracted.get("why_it_matters"):
            fallback += f" covering: {extracted['why_it_matters']}"
        extracted["summary"] = fallback
    return extracted


def add_from_url(
    url: str,
    notes: str = "",
    ai_disabled: bool = False,
    skip_notion: bool = False,
    skip_obsidian: bool = False,
    force: bool = False,
) -> Optional[Resource]:

    url = normalizer.normalize_url(url)
    logger.info("Ingesting URL: %s", url)

    if not force:
        duplicate = check_duplicate(url=url)
        if duplicate:
            logger.warning("Duplicate detected: %s matches %s", url, duplicate.id)
            return duplicate

    extracted = extract_metadata(url)
    body_text = extracted.pop("_body_text", "")
    extraction_failed = extracted.pop("_extraction_failed", False)

    if extraction_failed:
        logger.warning(
            "Extraction failed for %s — proceeding with minimal metadata", url
        )

    heuristic = classifier.classify(
        url=url,
        title=extracted.get("title", ""),
        body_text=body_text,
        extracted=extracted,
    )
    heuristic_confidence = heuristic.pop("confidence", 0)
    heuristic_notes = heuristic.pop("heuristic_notes", [])

    for key in (
        "type",
        "domain",
        "subdomain",
        "skill_level",
        "format",
        "temporal_relevance",
    ):
        if key in heuristic and key not in extracted:
            extracted[key] = heuristic[key]
        elif key in heuristic and not extracted.get(key):
            extracted[key] = heuristic[key]

    ai_confidence = None
    ai_result = {}

    use_ai = (
        not ai_disabled
        and not extracted.get("ai_disabled", False)
        and classifier.needs_ai_enrichment(
            heuristic | {"confidence": heuristic_confidence}
        )
    )

    if use_ai:
        logger.info(
            "Heuristic confidence %d < threshold — calling AI", heuristic_confidence
        )

        ai_class = ai_classify(
            title=extracted.get("title", ""),
            url=url,
            body_text=body_text,
        )
        if ai_class:
            ai_result.update(ai_class)
            ai_confidence = ai_class.get("confidence", 70)

        ai_sum = ai_summarize(
            title=extracted.get("title", ""),
            body_text=body_text,
            url=url,
        )
        if ai_sum:
            if "summary" not in extracted or not extracted["summary"]:
                extracted["summary"] = ai_sum.get("summary")
            extracted["why_it_matters"] = ai_sum.get("why_it_matters")
            extracted["best_for"] = ai_sum.get("best_for")
            extracted["avoid_if"] = ai_sum.get("avoid_if")
            if not extracted.get("quality_score"):
                extracted["quality_score"] = ai_sum.get("quality_score")

        if not extracted.get("tags"):
            ai_tag_result = ai_tags(
                title=extracted.get("title", ""),
                body_text=body_text,
                domain=extracted.get("domain", ""),
                type_=extracted.get("type", ""),
            )
            if ai_tag_result:
                extracted["tags"] = ai_tag_result.get("tags", [])

        if ai_result:
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
                if key in ai_result and not extracted.get(key):
                    extracted[key] = ai_result[key]

        extracted["ai_enriched"] = True
    else:
        logger.info(
            "Using heuristic classification only (confidence: %d)", heuristic_confidence
        )
        ai_confidence = heuristic_confidence

    mirror_urls = extracted.get("mirror_urls", [])
    auto_mirror = os.getenv("AUTO_MIRROR_WAYBACK", "true").lower() == "true"
    if auto_mirror and url != "local" and not mirror_urls:
        wayback = normalizer.get_wayback_url(url)
        if wayback:
            mirror_urls = [wayback]
    extracted["mirror_urls"] = mirror_urls

    if notes:
        extracted["notes"] = notes

    extracted["ai_confidence"] = ai_confidence
    extracted["ai_disabled"] = ai_disabled
    extracted["added_by"] = "user"
    extracted["enrichment_status"] = "pending" if use_ai else "complete"
    extracted["ai_enriched"] = not use_ai

    extracted = _enforce_summary(
        extracted, title=extracted.get("title", ""), url=url, body_text=body_text
    )
    extracted = normalizer.normalize_resource_fields(extracted)

    try:
        resource = Resource(**extracted)
    except Exception as e:
        logger.error("Pydantic validation failed: %s\nData: %s", e, extracted)
        resource = Resource(
            title=extracted.get("title") or url,
            url=url,
            notes=f"[Auto-fallback] Validation error: {e}",
        )

    db.insert_resource(resource)
    logger.info("Saved resource %s to DB (fast path)", resource.id)

    if use_ai:
        from app.background import submit_enrichment

        submit_enrichment(resource)

    return resource


def add_manual(fields: dict) -> Optional[Resource]:
    fields["added_by"] = "user"
    if "url" not in fields:
        fields["url"] = "local"

    fields = normalizer.normalize_resource_fields(fields)
    fields = _enforce_summary(fields, title=fields.get("title", ""))

    try:
        resource = Resource(**fields)
    except Exception as e:
        logger.error("Manual add validation failed: %s", e)
        return None

    db.insert_resource(resource)

    if os.getenv("OBSIDIAN_SYNC_ENABLED", "true").lower() == "true":
        obsidian_writer.write_note(resource)

    if os.getenv("NOTION_SYNC_ENABLED", "true").lower() == "true":
        notion_sync.sync_resource(resource)

    return resource


def _resolve_titles_to_ids(titles: list) -> list:
    from rapidfuzz import process, fuzz

    all_resources = db.get_all_titles_and_ids()
    title_to_id = {r["title"]: r["id"] for r in all_resources}

    matched_ids = []
    for target in titles:
        match = process.extractOne(
            target,
            title_to_id.keys(),
            scorer=fuzz.token_sort_ratio,
            score_cutoff=80,
        )
        if match:
            matched_ids.append(title_to_id[match[0]])

    return matched_ids
