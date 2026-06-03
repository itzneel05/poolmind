"""
Duplicate detection for poolmind.
URL exact match first, then fuzzy title match.
"""

import logging
from typing import Optional

from rapidfuzz import fuzz, process

from app import db
from app.normalizer import normalize_url
from models.resource import Resource

logger = logging.getLogger(__name__)


def check_duplicate(
    url: str = None,
    title: str = None,
    threshold: int = 85,
) -> Optional[Resource]:

    if url and url != "local":
        normalized = normalize_url(url)
        existing = db.get_by_url(normalized)
        if existing:
            logger.info("Exact URL duplicate: %s == %s", url, existing.id)
            return existing

    if title:
        all_resources = db.get_all_titles_and_ids()
        if not all_resources:
            return None

        title_to_id = {r["title"]: r["id"] for r in all_resources}

        match = process.extractOne(
            title,
            title_to_id.keys(),
            scorer=fuzz.token_sort_ratio,
            score_cutoff=threshold,
        )

        if match:
            matched_title, score, _ = match
            matched_id = title_to_id[matched_title]
            logger.info(
                "Fuzzy title duplicate: '%s' matches '%s' (score: %d)",
                title,
                matched_title,
                score,
            )
            return db.get_resource(matched_id)

    return None


def find_all_duplicates(threshold: int = 85) -> list:
    all_resources = db.get_all_titles_and_ids()
    titles = [r["title"] for r in all_resources]
    id_map = {r["title"]: r["id"] for r in all_resources}

    duplicates = []
    seen_pairs = set()

    for i, title_a in enumerate(titles):
        matches = process.extract(
            title_a,
            titles,
            scorer=fuzz.token_sort_ratio,
            limit=5,
            score_cutoff=threshold,
        )
        for matched_title, score, _ in matches:
            if matched_title == title_a:
                continue
            pair = tuple(sorted([title_a, matched_title]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            duplicates.append(
                {
                    "resource_a": {"id": id_map[title_a], "title": title_a},
                    "resource_b": {"id": id_map[matched_title], "title": matched_title},
                    "score": score,
                }
            )

    return sorted(duplicates, key=lambda x: x["score"], reverse=True)
