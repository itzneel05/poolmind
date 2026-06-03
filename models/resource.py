"""
Universal Resource Schema (URS) v1.0
Pydantic model for all resource types in poolmind.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


def generate_id() -> str:
    return str(uuid.uuid4())[:8]


class Resource(BaseModel):
    """
    Universal Resource Schema v1.0
    Single schema for all 34+ resource types.
    """

    # ── Identity ──────────────────────────────────────────────────────────
    id: str = Field(default_factory=generate_id)
    title: str
    type: str = "article"
    url: str = "local"
    mirror_urls: List[str] = Field(default_factory=list)
    author: Optional[str] = None
    source_platform: str = "other"

    # ── Classification ────────────────────────────────────────────────────
    domain: str = "general"
    subdomain: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

    # ── Learning Metadata ─────────────────────────────────────────────────
    skill_level: str = "intermediate"
    prerequisites: List[str] = Field(default_factory=list)
    time_to_value: str = "30min"
    format: str = "text"
    learning_path: Optional[str] = None

    # ── Availability ──────────────────────────────────────────────────────
    cost: str = "free"
    language: str = "en"
    year_published: Optional[int] = None
    last_verified_alive: Optional[str] = None
    last_updated_by_author: Optional[str] = None
    is_still_maintained: Optional[bool] = None

    # ── Quality & Usage ───────────────────────────────────────────────────
    quality_score: Optional[int] = None
    personal_rating: Optional[int] = None
    times_used: int = 0
    last_used: Optional[str] = None
    consumption_state: str = "saved"
    temporal_relevance: str = "evergreen"

    # ── Context ───────────────────────────────────────────────────────────
    summary: Optional[str] = None
    why_it_matters: Optional[str] = None
    best_for: Optional[str] = None
    avoid_if: Optional[str] = None

    # ── Relationships ─────────────────────────────────────────────────────
    related_resources: List[str] = Field(default_factory=list)
    next_step_resource: Optional[str] = None

    # ── Provenance ────────────────────────────────────────────────────────
    added_by: str = "user"
    added_on: str = Field(default_factory=lambda: date.today().isoformat())
    notes: Optional[str] = None
    ai_confidence: Optional[int] = None

    # ── Sync ──────────────────────────────────────────────────────────────
    notion_page_id: Optional[str] = None
    notion_last_synced: Optional[str] = None

    # ── Runtime (not persisted) ──────────────────────────────────────────
    relevance_score: Optional[int] = (
        None  # AI relevance score for search ranking, not saved to DB
    )

    # ── AI Flags ──────────────────────────────────────────────────────────
    ai_disabled: bool = False
    ai_enriched: bool = False

    # ── Extended Metadata (type-specific, stored as JSON in DB) ───────────
    extended_meta: dict = Field(default_factory=dict)

    # ── Background Enrichment ─────────────────────────────────────────────
    enrichment_status: str = "pending"

    # ── Schema Version ────────────────────────────────────────────────────
    schema_version: str = "1.0"

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, v: List[str]) -> List[str]:
        seen = set()
        result = []
        for tag in v:
            normalized = tag.lower().strip().lstrip("#").replace(" ", "-")
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        return result[:15]

    @field_validator("quality_score", "personal_rating", "ai_confidence")
    @classmethod
    def clamp_score(cls, v: Optional[int]) -> Optional[int]:
        if v is None:
            return v
        return max(0, min(100, v))

    @field_validator("consumption_state")
    @classmethod
    def validate_consumption(cls, v: str) -> str:
        valid = {"saved", "skimmed", "studied", "mastered", "applied"}
        return v if v in valid else "saved"

    @field_validator("temporal_relevance")
    @classmethod
    def validate_temporal(cls, v: str) -> str:
        valid = {"evergreen", "time-sensitive", "historical", "emerging"}
        return v if v in valid else "evergreen"

    def to_dict(self) -> dict:
        d = self.model_dump(exclude={"relevance_score"})
        d["tags"] = ",".join(self.tags)
        d["mirror_urls"] = ",".join(self.mirror_urls)
        d["prerequisites"] = ",".join(self.prerequisites)
        d["related_resources"] = ",".join(self.related_resources)
        return d

    @classmethod
    def from_db_row(cls, row: dict) -> "Resource":
        row = dict(row)
        for list_field in ("tags", "mirror_urls", "prerequisites", "related_resources"):
            val = row.get(list_field) or ""
            row[list_field] = [x for x in val.split(",") if x]
        import json

        if isinstance(row.get("extended_meta"), str):
            try:
                row["extended_meta"] = json.loads(row["extended_meta"])
            except Exception:
                row["extended_meta"] = {}
        return cls(**row)
