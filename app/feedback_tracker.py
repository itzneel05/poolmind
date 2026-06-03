"""
Prompt feedback tracker for poolmind self-adaptation system.
Every AI task call is wrapped with this module.
Outcomes are logged to prompt_feedback table.
"""

import hashlib
import logging
import sqlite3
from contextlib import contextmanager
from typing import Optional

from app.db import get_db_path

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = {
    "classify_resource": [
        "type",
        "domain",
        "subdomain",
        "skill_level",
        "format",
        "temporal_relevance",
        "time_to_value",
        "cost",
        "confidence",
    ],
    "summarize_resource": [
        "summary",
        "why_it_matters",
        "best_for",
        "avoid_if",
        "quality_score",
        "confidence",
    ],
    "generate_tags": ["tags", "confidence"],
    "parse_query": ["domain", "skill_level", "keywords", "confidence"],
    "suggest_related": ["related_titles", "next_step_title", "confidence"],
    "generate_learning_path": ["path_name", "weeks"],
    "generate_stack": ["stack_name", "resources"],
    "gap_analysis": ["gaps", "priority_gaps", "coverage_score"],
    "improve_note": ["improved_notes", "suggestions", "confidence"],
    "schema_suggest": ["add_fields", "remove_fields", "taxonomy_updates"],
    "rerank_search": ["ranked_ids", "scores"],
    "generate_gap_report": [
        "executive_summary",
        "domain_coverage",
        "priority_recommendations",
        "pool_health_score",
    ],
    "briefing": ["summary", "recommended_focus", "random_gem"],
}

EVOLUTION_THRESHOLD = 0.70
MIN_SAMPLES_FOR_EVOLUTION = 10


def prompt_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:8]


def input_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:12]


@contextmanager
def _conn():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def log_feedback(
    task: str,
    prompt_version: str,
    input_content: str,
    result: Optional[dict],
    response_time_ms: int,
    model_used: str = "",
) -> None:
    i_hash = input_hash(input_content)
    structural_success = 1 if result is not None else 0
    field_coverage = 0.0
    confidence_reported = None
    if result and task in REQUIRED_FIELDS:
        required = REQUIRED_FIELDS[task]
        populated = sum(
            1
            for f in required
            if result.get(f) is not None and result.get(f) != "" and result.get(f) != []
        )
        field_coverage = populated / len(required) if required else 1.0
        confidence_reported = result.get("confidence")
    try:
        with _conn() as conn:
            conn.execute(
                """INSERT INTO prompt_feedback
                   (task, prompt_version, input_hash, structural_success,
                    field_coverage, confidence_reported, response_time_ms, model_used)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    task,
                    prompt_version,
                    i_hash,
                    structural_success,
                    round(field_coverage, 3),
                    confidence_reported,
                    response_time_ms,
                    model_used,
                ],
            )
    except Exception as e:
        logger.warning("Failed to log feedback for task %s: %s", task, e)


def log_user_correction(task: str, input_content: str, correction_detail: str) -> None:
    i_hash = input_hash(input_content)
    try:
        with _conn() as conn:
            conn.execute(
                """UPDATE prompt_feedback
                   SET user_corrected = 1, correction_detail = ?
                   WHERE task = ? AND input_hash = ?
                   ORDER BY created_at DESC LIMIT 1""",
                [correction_detail, task, i_hash],
            )
    except Exception as e:
        logger.warning("Failed to log user correction: %s", e)


def get_task_stats(task: str, last_n: int = 50) -> dict:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT structural_success, field_coverage, confidence_reported,
                      user_corrected, response_time_ms
               FROM prompt_feedback
               WHERE task = ?
               ORDER BY created_at DESC LIMIT ?""",
            [task, last_n],
        ).fetchall()
    if not rows:
        return {
            "task": task,
            "total_calls": 0,
            "success_rate": None,
            "avg_field_coverage": None,
            "avg_confidence": None,
            "user_correction_rate": None,
            "avg_response_time_ms": None,
            "needs_evolution": False,
            "reason": "insufficient_data",
        }
    rows = [dict(r) for r in rows]
    total = len(rows)
    successes = sum(1 for r in rows if r["structural_success"])
    corrections = sum(1 for r in rows if r["user_corrected"])
    coverages = [r["field_coverage"] for r in rows if r["field_coverage"] is not None]
    confidences = [
        r["confidence_reported"] for r in rows if r["confidence_reported"] is not None
    ]
    times = [r["response_time_ms"] for r in rows if r["response_time_ms"] is not None]

    success_rate = successes / total
    correction_rate = corrections / total
    avg_coverage = sum(coverages) / len(coverages) if coverages else None
    avg_confidence = sum(confidences) / len(confidences) if confidences else None
    avg_time = sum(times) / len(times) if times else None

    needs_evolution = False
    reason = "healthy"
    if total >= MIN_SAMPLES_FOR_EVOLUTION:
        if success_rate < EVOLUTION_THRESHOLD:
            needs_evolution = True
            reason = f"low_success_rate:{success_rate:.2f}"
        elif avg_coverage and avg_coverage < 0.6:
            needs_evolution = True
            reason = f"low_field_coverage:{avg_coverage:.2f}"
        elif correction_rate > 0.3:
            needs_evolution = True
            reason = f"high_correction_rate:{correction_rate:.2f}"
        elif avg_confidence and avg_confidence < 50:
            needs_evolution = True
            reason = f"low_avg_confidence:{avg_confidence:.1f}"
    else:
        reason = f"insufficient_data:{total}/{MIN_SAMPLES_FOR_EVOLUTION}"

    return {
        "task": task,
        "total_calls": total,
        "success_rate": round(success_rate, 3),
        "avg_field_coverage": round(avg_coverage, 3) if avg_coverage else None,
        "avg_confidence": round(avg_confidence, 1) if avg_confidence else None,
        "user_correction_rate": round(correction_rate, 3),
        "avg_response_time_ms": round(avg_time) if avg_time else None,
        "needs_evolution": needs_evolution,
        "reason": reason,
    }


def get_all_task_stats(last_n: int = 50) -> list:
    return [get_task_stats(t, last_n) for t in REQUIRED_FIELDS]


def get_failure_examples(task: str, limit: int = 5) -> list:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT input_hash, correction_detail, created_at
               FROM prompt_feedback
               WHERE task = ? AND (structural_success = 0 OR user_corrected = 1)
               ORDER BY created_at DESC LIMIT ?""",
            [task, limit],
        ).fetchall()
    return [dict(r) for r in rows]


def get_correction_details(task: str, limit: int = 10) -> list:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT correction_detail, created_at
               FROM prompt_feedback
               WHERE task = ? AND user_corrected = 1 AND correction_detail IS NOT NULL
               ORDER BY created_at DESC LIMIT ?""",
            [task, limit],
        ).fetchall()
    return [dict(r) for r in rows]


def log_evolution(
    task: str,
    old_version: str,
    new_version: str,
    trigger_reason: str,
    feedback_sample_size: int,
    success_rate_before: float,
    backup_path: str,
) -> None:
    with _conn() as conn:
        conn.execute(
            """INSERT INTO prompt_evolution_log
               (task, old_prompt_version, new_prompt_version, trigger_reason,
                feedback_sample_size, success_rate_before, backup_path)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                task,
                old_version,
                new_version,
                trigger_reason,
                feedback_sample_size,
                success_rate_before,
                backup_path,
            ],
        )


def get_evolution_history(task: str = None) -> list:
    with _conn() as conn:
        if task:
            rows = conn.execute(
                "SELECT * FROM prompt_evolution_log WHERE task = ? ORDER BY created_at DESC",
                [task],
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM prompt_evolution_log ORDER BY created_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]
