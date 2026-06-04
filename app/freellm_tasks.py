"""
freellmapi wrapper — Option A.
All task logic is implemented here.
freellmapi is called as a generic completion endpoint.
Prompts loaded from prompts/*.md files.
Responses cached by input hash.
"""

import hashlib
import json
import logging
import os
import re
import time as _time
from pathlib import Path
from typing import Optional

import requests

from app.db import get_ai_cache, set_ai_cache
from app.feedback_tracker import log_feedback, prompt_hash as _prompt_hash

logger = logging.getLogger(__name__)


def _tracked_call(
    task: str, prompt_content: str, result: Optional[dict], elapsed_ms: int
) -> None:
    try:
        version = _prompt_hash(prompt_content)
        model = _get_model()
        log_feedback(
            task=task,
            prompt_version=version,
            input_content=prompt_content[:500],
            result=result,
            response_time_ms=elapsed_ms,
            model_used=model,
        )
    except Exception as e:
        logger.warning("Feedback tracking failed for %s: %s", task, e)


# ── Configuration ──────────────────────────────────────────────────────────


def _get_base_url() -> str:
    return os.getenv("FREELLMAPI_URL", "http://localhost:11434")


def _get_model() -> str:
    return os.getenv("FREELLMAPI_MODEL", "llama3")


def _is_ai_enabled() -> bool:
    return os.getenv("AI_ENABLED", "true").lower() == "true"


# ── Prompt Loader ──────────────────────────────────────────────────────────

_prompt_cache: dict = {}


def _load_prompt(task_name: str) -> str:
    if task_name in _prompt_cache:
        return _prompt_cache[task_name]

    prompt_path = Path("prompts") / f"{task_name}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    content = prompt_path.read_text(encoding="utf-8")
    _prompt_cache[task_name] = content
    return content


def _reload_prompt(task_name: str) -> str:
    _prompt_cache.pop(task_name, None)
    return _load_prompt(task_name)


# ── Core LLM Call ──────────────────────────────────────────────────────────


def _call_llm(prompt: str, system: str = "", task: str = "generic") -> Optional[dict]:
    if not _is_ai_enabled():
        logger.debug("AI disabled — skipping LLM call")
        return None

    base_url = _get_base_url().rstrip("/")

    # Primary: OpenAI-compatible endpoint (works with freellmapi, Ollama, and OpenAI)
    api_key = os.getenv(
        "FREELLMAPI_API_KEY", os.getenv("OPENAI_API_KEY", "sk-no-key-required")
    )
    model = _get_model()

    for attempt, (api_base, key) in enumerate(
        [
            (base_url, api_key),
            (
                os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                os.getenv("OPENAI_API_KEY", ""),
            ),
        ]
    ):
        if not key or not api_base:
            continue
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            url_base = api_base.rstrip("/")
            if not url_base.endswith("/v1"):
                url_base += "/v1"
            resp = requests.post(
                f"{url_base}/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2,
                },
                timeout=30,
            )
            resp.raise_for_status()
            raw_text = resp.json()["choices"][0]["message"]["content"]
            return _parse_json_response(raw_text)
        except Exception as e:
            logger.warning("Attempt %d failed (%s): %s", attempt + 1, api_base, e)

    return None


def _parse_json_response(text: str) -> Optional[dict]:
    if not text:
        return None
    text = re.sub(r"```(?:json)?\n?", "", text).strip().strip("`")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]+\}", text)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    logger.warning("Could not parse JSON from LLM response: %s", text[:200])
    return None


def _cache_key(task: str, content: str) -> str:
    return hashlib.sha256(f"{task}:{content}".encode()).hexdigest()[:20]


# ── Task Functions ──────────────────────────────────────────────────────────


def _wrap_call(task: str, prompt_template: str, prompt: str) -> Optional[dict]:
    """Execute LLM call with timing and feedback tracking."""
    t_start = _time.monotonic()
    result = _call_llm(prompt, task=task)
    elapsed_ms = int((_time.monotonic() - t_start) * 1000)
    _tracked_call(task, prompt_template, result, elapsed_ms)
    return result


def classify_resource(
    title: str, url: str, body_text: str = "", existing_meta: dict = None
) -> Optional[dict]:
    existing_meta = existing_meta or {}
    content = f"TITLE: {title}\nURL: {url}\nTEXT_SNIPPET: {body_text[:800]}"
    cache_key = _cache_key("classify", content)

    cached = get_ai_cache(cache_key)
    if cached:
        logger.debug("AI cache hit: classify_resource")
        return cached

    try:
        prompt_template = _load_prompt("classify_resource")
    except FileNotFoundError:
        logger.warning("classify_resource.md not found — skipping AI classification")
        return None

    prompt = prompt_template.replace("{{TITLE}}", title)
    prompt = prompt.replace("{{URL}}", url)
    prompt = prompt.replace("{{TEXT_SNIPPET}}", body_text[:800])

    result = _wrap_call("classify_resource", prompt_template, prompt)

    if result:
        set_ai_cache(cache_key, "classify_resource", result, _get_model())

    return result


def summarize_resource(title: str, body_text: str, url: str = "") -> Optional[dict]:
    content = f"{title}:{body_text[:500]}"
    cache_key = _cache_key("summarize", content)

    cached = get_ai_cache(cache_key)
    if cached:
        return cached

    try:
        prompt_template = _load_prompt("summarize_resource")
    except FileNotFoundError:
        return None

    prompt = prompt_template.replace("{{TITLE}}", title)
    prompt = prompt.replace("{{BODY_TEXT}}", body_text[:1500])
    prompt = prompt.replace("{{URL}}", url)

    result = _wrap_call("summarize_resource", prompt_template, prompt)

    if result:
        set_ai_cache(cache_key, "summarize_resource", result, _get_model())

    return result


def generate_tags(
    title: str, body_text: str, domain: str = "", type_: str = ""
) -> Optional[dict]:
    content = f"{title}:{domain}:{body_text[:300]}"
    cache_key = _cache_key("tags", content)

    cached = get_ai_cache(cache_key)
    if cached:
        return cached

    try:
        prompt_template = _load_prompt("generate_tags")
    except FileNotFoundError:
        return None

    prompt = prompt_template.replace("{{TITLE}}", title)
    prompt = prompt.replace("{{BODY_TEXT}}", body_text[:800])
    prompt = prompt.replace("{{DOMAIN}}", domain)
    prompt = prompt.replace("{{TYPE}}", type_)

    result = _wrap_call("generate_tags", prompt_template, prompt)

    if result:
        set_ai_cache(cache_key, "generate_tags", result, _get_model())

    return result


def parse_query(natural_language_query: str) -> Optional[dict]:
    cache_key = _cache_key("query", natural_language_query)
    cached = get_ai_cache(cache_key)
    if cached:
        return cached

    try:
        prompt_template = _load_prompt("parse_query")
    except FileNotFoundError:
        return None

    prompt = prompt_template.replace("{{QUERY}}", natural_language_query)
    result = _wrap_call("parse_query", prompt_template, prompt)

    if result:
        set_ai_cache(cache_key, "parse_query", result, _get_model())

    return result


def suggest_related(
    resource_title: str, resource_domain: str, pool_titles: list
) -> Optional[dict]:
    pool_sample = pool_titles[:50]
    pool_str = "\n".join(f"- {t}" for t in pool_sample)

    content = f"{resource_title}:{resource_domain}:{pool_str[:500]}"
    cache_key = _cache_key("related", content)
    cached = get_ai_cache(cache_key)
    if cached:
        return cached

    try:
        prompt_template = _load_prompt("suggest_related")
    except FileNotFoundError:
        return None

    prompt = prompt_template.replace("{{TITLE}}", resource_title)
    prompt = prompt.replace("{{DOMAIN}}", resource_domain)
    prompt = prompt.replace("{{POOL_TITLES}}", pool_str)

    result = _wrap_call("suggest_related", prompt_template, prompt)

    if result:
        set_ai_cache(cache_key, "suggest_related", result, _get_model())

    return result


def generate_learning_path(goal: str, pool_resources: list) -> Optional[dict]:
    pool_str = json.dumps(pool_resources[:80], indent=None)[:3000]

    try:
        prompt_template = _load_prompt("generate_learning_path")
    except FileNotFoundError:
        return None

    prompt = prompt_template.replace("{{GOAL}}", goal)
    prompt = prompt.replace("{{POOL_RESOURCES}}", pool_str)

    return _wrap_call("generate_learning_path", prompt_template, prompt)


def generate_stack(mission: str, pool_resources: list) -> Optional[dict]:
    pool_str = json.dumps(pool_resources[:80], indent=None)[:3000]

    try:
        prompt_template = _load_prompt("generate_stack")
    except FileNotFoundError:
        return None

    prompt = prompt_template.replace("{{MISSION}}", mission)
    prompt = prompt.replace("{{POOL_RESOURCES}}", pool_str)

    return _wrap_call("generate_stack", prompt_template, prompt)


def gap_analysis(pool_stats: dict) -> Optional[dict]:
    stats_str = json.dumps(pool_stats, indent=2)[:2000]

    try:
        prompt_template = _load_prompt("gap_analysis")
    except FileNotFoundError:
        return None

    prompt = prompt_template.replace("{{POOL_STATS}}", stats_str)
    return _wrap_call("gap_analysis", prompt_template, prompt)


def rerank_search(query: str, results: list) -> Optional[dict]:
    results_str = json.dumps(
        [
            {
                "id": r.get("id", ""),
                "title": r.get("title", ""),
                "summary": (r.get("summary") or "")[:150],
                "domain": r.get("domain", ""),
                "type": r.get("type", ""),
                "tags": r.get("tags", []),
            }
            for r in results[:20]
        ],
        indent=None,
    )[:3000]

    cache_key = _cache_key("rerank", f"{query}:{results_str[:200]}")
    cached = get_ai_cache(cache_key)
    if cached:
        return cached

    try:
        prompt_template = _load_prompt("rerank_search")
    except FileNotFoundError:
        return None

    prompt = prompt_template.replace("{{QUERY}}", query)
    prompt = prompt.replace("{{RESULTS}}", results_str)

    result = _wrap_call("rerank_search", prompt_template, prompt)

    if result:
        set_ai_cache(cache_key, "rerank_search", result, _get_model())

    return result


def generate_gap_report(
    pool_stats: dict, audit_data: Optional[dict] = None
) -> Optional[dict]:
    stats_str = json.dumps(pool_stats, indent=2)[:2000]
    audit_str = json.dumps(audit_data or {}, indent=2)[:1500]

    cache_key = _cache_key("gap_report", stats_str[:500])
    cached = get_ai_cache(cache_key)
    if cached:
        return cached

    try:
        prompt_template = _load_prompt("gap_report")
    except FileNotFoundError:
        return None

    prompt = prompt_template.replace("{{POOL_STATS}}", stats_str)
    prompt = prompt.replace("{{AUDIT_DATA}}", audit_str)

    result = _wrap_call("generate_gap_report", prompt_template, prompt)

    if result:
        set_ai_cache(cache_key, "gap_report", result, _get_model())

    return result


def generate_briefing(
    pool_stats: dict, recent_activity: list, due_items: dict
) -> Optional[dict]:
    import datetime

    stats_str = json.dumps(pool_stats, indent=2)[:1500]
    recent_str = json.dumps(recent_activity[:20], indent=2)[:1500]
    due_str = json.dumps(due_items, indent=2)[:1000]
    today = datetime.date.today().isoformat()

    cache_key = _cache_key("briefing", today)
    cached = get_ai_cache(cache_key)
    if cached:
        return cached

    try:
        prompt_template = _load_prompt("briefing")
    except FileNotFoundError:
        return None

    prompt = prompt_template.replace("{{DATE}}", today)
    prompt = prompt.replace("{{POOL_STATS}}", stats_str)
    prompt = prompt.replace("{{RECENT_ACTIVITY}}", recent_str)
    prompt = prompt.replace("{{DUE_ITEMS}}", due_str)

    result = _wrap_call("briefing", prompt_template, prompt)

    if result:
        set_ai_cache(cache_key, "briefing", result, _get_model())

    return result


def improve_note(title: str, current_notes: str, summary: str = "") -> Optional[dict]:
    content = f"{title}:{current_notes[:300]}"
    cache_key = _cache_key("note", content)
    cached = get_ai_cache(cache_key)
    if cached:
        return cached

    try:
        prompt_template = _load_prompt("improve_note")
    except FileNotFoundError:
        return None

    prompt = prompt_template.replace("{{TITLE}}", title)
    prompt = prompt.replace("{{NOTES}}", current_notes)
    prompt = prompt.replace("{{SUMMARY}}", summary)

    result = _wrap_call("improve_note", prompt_template, prompt)

    if result:
        set_ai_cache(cache_key, "improve_note", result, _get_model())

    return result
