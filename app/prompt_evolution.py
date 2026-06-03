"""
Self-adaptation engine for poolmind.
Rewrites prompts/*.md files based on observed AI performance.
Backs up every prompt before overwriting.
"""

import hashlib
import json
import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from app import feedback_tracker
from app.feedback_tracker import (
    get_task_stats,
    get_correction_details,
    get_failure_examples,
    log_evolution,
    prompt_hash,
    REQUIRED_FIELDS,
)

logger = logging.getLogger(__name__)

PROMPT_DIR = Path("prompts")
VERSION_DIR = Path("data/prompt_versions")

MANDATORY_PLACEHOLDERS = {
    "classify_resource": ["{{TITLE}}", "{{URL}}", "{{TEXT_SNIPPET}}"],
    "summarize_resource": ["{{TITLE}}", "{{BODY_TEXT}}", "{{URL}}"],
    "generate_tags": ["{{TITLE}}", "{{BODY_TEXT}}", "{{DOMAIN}}", "{{TYPE}}"],
    "parse_query": ["{{QUERY}}"],
    "suggest_related": ["{{TITLE}}", "{{DOMAIN}}", "{{POOL_TITLES}}"],
    "generate_learning_path": ["{{GOAL}}", "{{POOL_RESOURCES}}"],
    "generate_stack": ["{{MISSION}}", "{{POOL_RESOURCES}}"],
    "gap_analysis": ["{{POOL_STATS}}"],
    "improve_note": ["{{TITLE}}", "{{NOTES}}", "{{SUMMARY}}"],
    "schema_suggest": ["{{POOL_SIZE}}", "{{DOMAINS}}"],
    "rerank_search": ["{{QUERY}}", "{{RESULTS}}"],
    "generate_gap_report": ["{{POOL_STATS}}", "{{AUDIT_DATA}}"],
    "briefing": ["{{DATE}}", "{{POOL_STATS}}", "{{RECENT_ACTIVITY}}", "{{DUE_ITEMS}}"],
}


def evolve_prompt(
    task: str,
    force: bool = False,
    dry_run: bool = False,
    last_n_feedback: int = 50,
) -> dict:
    result = {
        "evolved": False,
        "task": task,
        "reason": "",
        "old_version": "",
        "new_version": None,
        "backup_path": None,
        "improved_prompt": None,
        "diff_summary": None,
    }

    prompt_path = PROMPT_DIR / f"{task}.md"
    if not prompt_path.exists():
        result["reason"] = f"prompt_file_not_found:{prompt_path}"
        return result

    current_prompt = prompt_path.read_text(encoding="utf-8")
    old_version = prompt_hash(current_prompt)
    result["old_version"] = old_version

    stats = get_task_stats(task, last_n=last_n_feedback)
    if not force and not stats["needs_evolution"]:
        result["reason"] = f"healthy:{stats['reason']}"
        return result

    trigger_reason = stats.get("reason", "forced")
    corrections = get_correction_details(task, limit=10)
    failures = get_failure_examples(task, limit=5)
    corrections_text = _format_corrections(corrections)
    failures_text = _format_failures(failures)
    required_fields = REQUIRED_FIELDS.get(task, [])
    mandatory_placeholders = MANDATORY_PLACEHOLDERS.get(task, [])

    improved_prompt = _call_evolution_ai(
        task=task,
        current_prompt=current_prompt,
        stats=stats,
        corrections_text=corrections_text,
        failures_text=failures_text,
        required_fields=required_fields,
        mandatory_placeholders=mandatory_placeholders,
    )
    if not improved_prompt:
        result["reason"] = "ai_evolution_failed"
        return result

    validation = _validate_prompt(
        task=task,
        prompt=improved_prompt,
        mandatory_placeholders=mandatory_placeholders,
        required_fields=required_fields,
    )
    if not validation["valid"]:
        result["reason"] = f"validation_failed:{validation['issues']}"
        return result

    new_version = prompt_hash(improved_prompt)
    result["new_version"] = new_version
    if old_version == new_version:
        result["reason"] = "no_change_detected"
        return result

    if dry_run:
        result["evolved"] = True
        result["reason"] = f"dry_run:{trigger_reason}"
        result["improved_prompt"] = improved_prompt
        result["diff_summary"] = _diff_summary(current_prompt, improved_prompt)
        return result

    backup_path = _backup_prompt(task, current_prompt, old_version)
    result["backup_path"] = str(backup_path)

    prompt_path.write_text(improved_prompt, encoding="utf-8")

    try:
        from app.freellm_tasks import _reload_prompt

        _reload_prompt(task)
    except Exception as e:
        logger.warning("Failed to reload prompt cache: %s", e)

    try:
        log_evolution(
            task=task,
            old_version=old_version,
            new_version=new_version,
            trigger_reason=trigger_reason,
            feedback_sample_size=stats.get("total_calls", 0),
            success_rate_before=stats.get("success_rate") or 0.0,
            backup_path=str(backup_path),
        )
    except Exception as e:
        logger.warning("Failed to log evolution: %s", e)

    result["evolved"] = True
    result["reason"] = trigger_reason
    result["diff_summary"] = _diff_summary(current_prompt, improved_prompt)
    return result


def evolve_all(
    force: bool = False, dry_run: bool = False, last_n_feedback: int = 50
) -> list:
    results = []
    for task in REQUIRED_FIELDS:
        r = evolve_prompt(
            task=task, force=force, dry_run=dry_run, last_n_feedback=last_n_feedback
        )
        results.append(r)
    return results


def _call_evolution_ai(
    task: str,
    current_prompt: str,
    stats: dict,
    corrections_text: str,
    failures_text: str,
    required_fields: list,
    mandatory_placeholders: list,
) -> Optional[str]:
    meta_prompt_path = PROMPT_DIR / "evolve_prompt.md"
    if not meta_prompt_path.exists():
        return None

    meta_template = meta_prompt_path.read_text(encoding="utf-8")
    meta = meta_template
    meta = meta.replace("{{TASK_NAME}}", task)
    meta = meta.replace("{{CURRENT_PROMPT}}", current_prompt)
    meta = meta.replace("{{SUCCESS_RATE}}", str(stats.get("success_rate", "unknown")))
    meta = meta.replace(
        "{{AVG_FIELD_COVERAGE}}", str(stats.get("avg_field_coverage", "unknown"))
    )
    meta = meta.replace(
        "{{AVG_CONFIDENCE}}", str(stats.get("avg_confidence", "unknown"))
    )
    meta = meta.replace(
        "{{USER_CORRECTION_RATE}}", str(stats.get("user_correction_rate", "unknown"))
    )
    meta = meta.replace("{{TRIGGER_REASON}}", stats.get("reason", "unknown"))
    meta = meta.replace("{{CORRECTIONS}}", corrections_text or "None recorded.")
    meta = meta.replace("{{FAILURES}}", failures_text or "None recorded.")
    meta = meta.replace("{{REQUIRED_FIELDS}}", ", ".join(required_fields))
    meta = meta.replace("{{MANDATORY_PLACEHOLDERS}}", ", ".join(mandatory_placeholders))

    # Try freellmapi (OpenAI-compatible)
    base_url = os.getenv("FREELLMAPI_URL", "")
    model = os.getenv("FREELLMAPI_MODEL", "llama3")
    if base_url:
        import requests

        api_url = base_url.rstrip("/")
        if not api_url.endswith("/v1"):
            api_url += "/v1"
        try:
            resp = requests.post(
                f"{api_url}/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": meta}],
                    "temperature": 0.4,
                    "max_tokens": 4096,
                },
                timeout=120,
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            fenced = re.search(r"```(?:markdown)?\n([\s\S]+?)```", raw)
            return fenced.group(1).strip() if fenced else (raw if raw else None)
        except Exception as e:
            logger.error("Evolution AI call failed: %s", e)

    # Fallback: OpenAI
    openai_key = os.getenv("OPENAI_API_KEY", "")
    openai_base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if openai_key:
        import requests

        try:
            resp = requests.post(
                f"{openai_base}/chat/completions",
                headers={"Authorization": f"Bearer {openai_key}"},
                json={
                    "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a prompt engineering expert. Output only the improved prompt text. No commentary.",
                        },
                        {"role": "user", "content": meta},
                    ],
                    "temperature": 0.4,
                },
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error("OpenAI fallback failed: %s", e)
    return None


def _validate_prompt(
    task: str, prompt: str, mandatory_placeholders: list, required_fields: list
) -> dict:
    issues = []
    for placeholder in mandatory_placeholders:
        if placeholder not in prompt:
            issues.append(f"missing_placeholder:{placeholder}")
    json_signals = ["Return ONLY valid JSON", "valid JSON", "```json", "JSON output"]
    if not any(s.lower() in prompt.lower() for s in json_signals):
        issues.append("missing_json_instruction")
    if required_fields:
        missing = [f for f in required_fields if f not in prompt]
        if len(missing) > len(required_fields) * 0.4:
            issues.append(f"too_many_missing_fields:{missing}")
    if len(prompt.strip()) < 100:
        issues.append(f"prompt_too_short:{len(prompt)}_chars")
    if len(prompt) > 8000:
        issues.append(f"prompt_too_long:{len(prompt)}_chars")
    return {"valid": len(issues) == 0, "issues": issues}


def _backup_prompt(task: str, content: str, version: str) -> Path:
    backup_dir = VERSION_DIR / task
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{timestamp}_{version}.md"
    backup_path.write_text(content, encoding="utf-8")
    return backup_path


def restore_prompt(task: str, version_timestamp: str = None) -> bool:
    backup_dir = VERSION_DIR / task
    if not backup_dir.exists():
        return False
    backups = sorted(backup_dir.glob("*.md"), reverse=True)
    if not backups:
        return False
    if version_timestamp:
        target = next((b for b in backups if version_timestamp in b.name), None)
        if not target:
            return False
    else:
        target = backups[0]
    prompt_path = PROMPT_DIR / f"{task}.md"
    current = prompt_path.read_text(encoding="utf-8")
    _backup_prompt(task, current, prompt_hash(current) + "_pre_restore")
    shutil.copy(target, prompt_path)
    try:
        from app.freellm_tasks import _reload_prompt

        _reload_prompt(task)
    except Exception:
        pass
    return True


def list_backups(task: str) -> list:
    backup_dir = VERSION_DIR / task
    if not backup_dir.exists():
        return []
    backups = sorted(backup_dir.glob("*.md"), reverse=True)
    return [
        {
            "filename": b.name,
            "path": str(b),
            "size_bytes": b.stat().st_size,
            "created": datetime.fromtimestamp(b.stat().st_mtime).isoformat(),
        }
        for b in backups
    ]


def _diff_summary(old: str, new: str) -> str:
    old_lines = old.splitlines()
    new_lines = new.splitlines()
    added = sum(1 for line in new_lines if line not in old_lines)
    removed = sum(1 for line in old_lines if line not in new_lines)
    old_len = len(old)
    new_len = len(new)
    delta = new_len - old_len
    return f"+{added} lines / -{removed} lines | length: {old_len} -> {new_len} ({'+' if delta >= 0 else ''}{delta} chars)"


def _format_corrections(corrections: list) -> str:
    if not corrections:
        return "No user corrections recorded."
    lines = ["User corrections (most recent first):"]
    for i, c in enumerate(corrections, 1):
        lines.append(
            f"{i}. [{c.get('created_at', '')[:10]}] {c.get('correction_detail', 'No detail')}"
        )
    return "\n".join(lines)


def _format_failures(failures: list) -> str:
    if not failures:
        return "No failures recorded."
    lines = ["Recent failures:"]
    for i, f in enumerate(failures, 1):
        lines.append(
            f"{i}. [{f.get('created_at', '')[:10]}] {f.get('correction_detail', 'Structural failure')}"
        )
    return "\n".join(lines)
