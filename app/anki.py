"""
Anki deck export for poolmind.
Generates a CSV file compatible with Anki's standard import format.
Import in Anki: File > Import > select CSV > set delimiter to comma.
"""

import csv
import logging
from pathlib import Path
from typing import List, Optional

from app import db
from models.resource import Resource

logger = logging.getLogger(__name__)


def export_csv(
    output_path: str = "poolmind-anki.csv",
    domain: Optional[str] = None,
    type_: Optional[str] = None,
    limit: int = 200,
) -> dict:
    if domain or type_:
        from app.search import list_by_filter

        resources = list_by_filter(domain=domain, type_=type_, limit=limit)
    else:
        resources = db.get_all_resources(limit=limit)

    row_count = 0
    path = Path(output_path)

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Front", "Back", "Tags"])
        for r in resources:
            front = _build_front(r)
            back = _build_back(r)
            tags = (
                " ".join(f"poolmind::{t}" for t in r.tags[:8]) if r.tags else "poolmind"
            )
            writer.writerow([front, back, tags])
            row_count += 1

    logger.info("Wrote Anki CSV: %s (%d cards)", path, row_count)
    return {"path": str(path), "cards": row_count}


def _build_front(r: Resource) -> str:
    lines = [f"<h3>{r.title}</h3>"]
    lines.append(f"<p><a href='{r.url}'>{r.url[:80]}</a></p>")
    lines.append(f"<p><b>{r.domain}</b> | {r.type} | {r.skill_level} | {r.cost}</p>")
    return "<br>".join(lines)


def _build_back(r: Resource) -> str:
    parts = []
    if r.summary:
        parts.append(f"<p>{r.summary}</p>")
    if r.why_it_matters:
        parts.append(f"<p><b>Why:</b> {r.why_it_matters}</p>")
    if r.best_for:
        parts.append(f"<p><b>Best for:</b> {r.best_for}</p>")
    if r.avoid_if:
        parts.append(f"<p><b>Avoid if:</b> {r.avoid_if}</p>")
    parts.append(
        f"<p><small>Quality: {r.quality_score or '?'}/10 | "
        f"Confidence: {r.ai_confidence or '?'}% | "
        f"State: {r.consumption_state}</small></p>"
    )
    return "<br>".join(parts)
