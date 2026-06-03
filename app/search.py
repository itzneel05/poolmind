"""
Search module for poolmind.
Keyword + FTS5 search with metadata filters.
Natural language query parsing via AI.
"""

import logging
import sqlite3
from typing import List, Optional

from app import db
from app.freellm_tasks import parse_query as ai_parse_query, rerank_search as ai_rerank
from models.resource import Resource

logger = logging.getLogger(__name__)


def search(
    query: str = "",
    domain: str = None,
    type_: str = None,
    skill_level: str = None,
    format_: str = None,
    cost: str = None,
    consumption_state: str = None,
    temporal_relevance: str = None,
    min_quality: int = None,
    limit: int = 10,
    natural_language: bool = False,
) -> List[Resource]:

    if natural_language and query:
        parsed = ai_parse_query(query)
        if parsed:
            keywords = parsed.get("keywords", [])
            if keywords:
                query = " OR ".join(keywords)

            logger.info(
                "AI parsed query -> domain=%s skill=%s type=%s  keywords=%s",
                parsed.get("domain"),
                parsed.get("skill_level"),
                parsed.get("type"),
                keywords,
            )

    fetch_limit = min(limit * 2, 50) if natural_language else limit
    results = _execute_search(
        fts_query=query,
        domain=domain,
        type_=type_,
        skill_level=skill_level,
        format_=format_,
        cost=cost,
        consumption_state=consumption_state,
        temporal_relevance=temporal_relevance,
        min_quality=min_quality,
        limit=fetch_limit,
    )

    if natural_language and query and len(results) > 1:
        reranked = _rerank_results(query, results)
        if reranked:
            results = reranked[:limit]

    return results


def _execute_search(
    fts_query: str = "",
    domain: str = None,
    type_: str = None,
    skill_level: str = None,
    format_: str = None,
    cost: str = None,
    consumption_state: str = None,
    temporal_relevance: str = None,
    min_quality: int = None,
    limit: int = 10,
) -> List[Resource]:

    from app.db import get_db_path

    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row

    try:
        conditions = ["r.consumption_state != 'archived'"]
        params = []

        use_fts = bool(fts_query and fts_query.strip())
        if use_fts:
            fts_safe = fts_query.replace('"', '""')

        if domain:
            conditions.append("r.domain = ?")
            params.append(domain)
        if type_:
            conditions.append("r.type = ?")
            params.append(type_)
        if skill_level:
            conditions.append("(r.skill_level = ? OR r.skill_level = 'all')")
            params.append(skill_level)
        if format_:
            conditions.append("r.format = ?")
            params.append(format_)
        if cost:
            conditions.append("r.cost = ?")
            params.append(cost)
        if consumption_state:
            conditions.append("r.consumption_state = ?")
            params.append(consumption_state)
        if temporal_relevance:
            conditions.append("r.temporal_relevance = ?")
            params.append(temporal_relevance)
        if min_quality:
            conditions.append("r.quality_score >= ?")
            params.append(min_quality)

        where_clause = " AND ".join(conditions)

        if use_fts:
            sql = f"""
                SELECT r.*, fts.rank
                FROM resources r
                JOIN resources_fts fts ON r.rowid = fts.rowid
                WHERE {where_clause}
                  AND resources_fts MATCH ?
                ORDER BY fts.rank
                LIMIT ?
            """
            params_with_fts = params + [fts_safe, limit]
            rows = conn.execute(sql, params_with_fts).fetchall()
        else:
            sql = f"""
                SELECT r.*
                FROM resources r
                WHERE {where_clause}
                ORDER BY
                    CASE WHEN r.quality_score IS NOT NULL THEN r.quality_score ELSE 0 END DESC,
                    r.added_on DESC
                LIMIT ?
            """
            params_with_limit = params + [limit]
            rows = conn.execute(sql, params_with_limit).fetchall()

        return [Resource.from_db_row(dict(r)) for r in rows]

    finally:
        conn.close()


def list_by_filter(
    domain: str = None,
    type_: str = None,
    skill_level: str = None,
    consumption_state: str = None,
    limit: int = 20,
) -> List[Resource]:
    return _execute_search(
        domain=domain,
        type_=type_,
        skill_level=skill_level,
        consumption_state=consumption_state,
        limit=limit,
    )


def get_recent(limit: int = 10) -> List[Resource]:
    return _execute_search(limit=limit)


def get_untouched(limit: int = 10) -> List[Resource]:
    return _execute_search(consumption_state="saved", limit=limit)


def _rerank_results(query: str, results: List[Resource]) -> Optional[List[Resource]]:
    """Use AI to re-rank search results by semantic relevance."""
    result_dicts = [
        {
            "id": r.id,
            "title": r.title,
            "summary": r.summary,
            "domain": r.domain,
            "type": r.type,
            "tags": r.tags,
        }
        for r in results
    ]
    if not result_dicts:
        return None

    reranked = ai_rerank(query=query, results=result_dicts)
    if not reranked or "ranked_ids" not in reranked:
        return None

    id_order = reranked["ranked_ids"]
    id_to_resource = {r.id: r for r in results}

    ordered = []
    for rid in id_order:
        if rid in id_to_resource:
            ordered.append(id_to_resource[rid])

    scores = reranked.get("scores", {})
    for r in ordered:
        r.relevance_score = scores.get(r.id)

    return ordered if ordered else None


def get_random(limit: int = 1) -> List[Resource]:
    from app.db import get_db_path

    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM resources WHERE consumption_state != 'archived' ORDER BY RANDOM() LIMIT ?",
            [limit],
        ).fetchall()
        return [Resource.from_db_row(dict(r)) for r in rows]
    finally:
        conn.close()
