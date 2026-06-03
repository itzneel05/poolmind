"""
Flask web UI for poolmind.
Routes: dashboard, resource list, detail, search, add, ingest, browse.
API blueprints registered for all REST endpoints.
"""

import logging
from pathlib import Path

from flask import Flask, render_template, request

from app import db
from app.search import (
    search,
    count_search,
    get_random,
    get_recent,
    get_untouched,
    list_by_filter,
)
from app.db import count_audit_entries
from app.api import register_blueprints
from models.resource import Resource

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parent.parent / "templates"),
        static_folder=str(Path(__file__).resolve().parent.parent / "static"),
        static_url_path="/static",
    )

    register_blueprints(app)

    db._ensure_trash_columns()
    db._ensure_enrichment_column()

    @app.context_processor
    def inject_globals():
        return {
            "ai_status_global": _get_ai_status(),
            "trash_count": db.get_trash_count(),
        }

    # ── Dashboard ──
    @app.route("/")
    def dashboard():
        stats = db.get_pool_stats()
        recent = db.get_all_resources(limit=10)
        random_gem = get_random(1)
        ai_status = _get_ai_status()
        notion_status = _get_notion_status()
        return render_template(
            "dashboard.html",
            stats=stats,
            recent=recent,
            random_gem=random_gem[0] if random_gem else None,
            ai_status=ai_status,
            notion_status=notion_status,
        )

    # ── Add Resource ──
    @app.route("/add")
    def add_page():
        return render_template("add.html")

    @app.route("/add/manual")
    def add_manual_page():
        return render_template("add_manual.html")

    # ── Bulk Ingest ──
    @app.route("/ingest")
    def ingest_page():
        return render_template("ingest.html")

    @app.route("/ingest/preview")
    def ingest_preview_page():
        return render_template("ingest_preview.html")

    # ── Resource List ──
    @app.route("/resources")
    def resource_list():
        domain = request.args.get("domain") or None
        type_ = request.args.get("type") or None
        state = request.args.get("state") or None
        page = int(request.args.get("page", 1))
        per_page = 25
        offset = (page - 1) * per_page
        if domain or type_ or state:
            resources = list_by_filter(
                domain=domain,
                type_=type_,
                consumption_state=state,
                limit=per_page,
                offset=offset,
            )
        else:
            resources = db.get_all_resources(limit=per_page, offset=offset)
        total = db.count_resources()
        stats = db.get_pool_stats()
        all_domains = [d["domain"] for d in stats["by_domain"]]
        all_types = [t["type"] for t in stats["by_type"]]
        return render_template(
            "list.html",
            resources=resources,
            domains=all_domains,
            types=all_types,
            current_domain=domain or "",
            current_type=type_ or "",
            current_state=state or "",
            stats=stats,
            page=page,
            per_page=per_page,
            total=total,
        )

    # ── Browse ──
    @app.route("/resources/random")
    def random_page():
        gem = get_random(1)
        return render_template("random.html", resource=gem[0] if gem else None)

    @app.route("/resources/untouched")
    def untouched_page():
        limit = int(request.args.get("limit", 50))
        results = get_untouched(limit=limit)
        return render_template("untouched.html", resources=results)

    @app.route("/resources/recent")
    def recent_page():
        limit = int(request.args.get("limit", 50))
        results = get_recent(limit=limit)
        return render_template("recent.html", resources=results)

    @app.route("/resources/by-state/<state>")
    def by_state_page(state):
        limit = int(request.args.get("limit", 50))
        results = list_by_filter(consumption_state=state, limit=limit)
        return render_template(
            "list.html",
            resources=results,
            domains=[],
            types=[],
            current_domain="",
            current_type="",
            current_state=state,
            stats=db.get_pool_stats(),
        )

    # ── Resource Detail ──
    @app.route("/resource/<resource_id>")
    def resource_detail(resource_id: str):
        resource = db.get_resource(resource_id)
        if not resource:
            return render_template("detail.html", resource=None), 404
        related = []
        for rid in resource.related_resources:
            r = db.get_resource(rid)
            if r:
                related.append(r)
        all_states = ["saved", "skimmed", "studied", "mastered", "applied"]
        return render_template(
            "detail.html", resource=resource, related=related, all_states=all_states
        )

    @app.route("/resource/<resource_id>/edit")
    def resource_edit(resource_id: str):
        resource = db.get_resource(resource_id)
        if not resource:
            return render_template("detail.html", resource=None), 404
        all_states = ["saved", "skimmed", "studied", "mastered", "applied"]
        return render_template("edit.html", resource=resource, all_states=all_states)

    # ── Intelligence: Learning Paths ──
    @app.route("/intelligence/paths")
    def intel_paths():
        paths = []
        try:
            import json
            from pathlib import Path

            f = Path("data/learning_paths.json")
            if f.exists():
                paths = json.loads(f.read_text())
        except Exception:
            pass
        return render_template("intel_paths.html", paths=paths)

    @app.route("/intelligence/paths/<path_id>")
    def intel_path_detail(path_id):
        path_data = None
        try:
            import json
            from pathlib import Path

            f = Path("data/learning_paths.json")
            if f.exists():
                all_p = json.loads(f.read_text())
                path_data = next((p for p in all_p if p.get("id") == path_id), None)
        except Exception:
            pass
        if not path_data:
            return render_template("empty.html", title="Path Not Found"), 404
        resources_in_path = []
        week_ids = set()
        for w in path_data.get("weeks", []):
            for r in w.get("resources", []):
                rid = r.get("resource_id") or r.get("id", "")
                if rid:
                    week_ids.add(rid)
        for rid in week_ids:
            r = db.get_resource(rid)
            if r:
                resources_in_path.append(r)
        return render_template(
            "intel_path.html", path=path_data, resources=resources_in_path
        )

    # ── Intelligence: Tech Stacks ──
    @app.route("/intelligence/stacks")
    def intel_stacks():
        stacks = []
        try:
            import json
            from pathlib import Path

            f = Path("data/resource_stacks.json")
            if f.exists():
                stacks = json.loads(f.read_text())
        except Exception:
            pass
        return render_template("intel_stacks.html", stacks=stacks)

    @app.route("/intelligence/stacks/<stack_id>")
    def intel_stack_detail(stack_id):
        stack_data = None
        try:
            import json
            from pathlib import Path

            f = Path("data/resource_stacks.json")
            if f.exists():
                all_s = json.loads(f.read_text())
                stack_data = next((s for s in all_s if s.get("id") == stack_id), None)
        except Exception:
            pass
        if not stack_data:
            return render_template("empty.html", title="Stack Not Found"), 404
        resources_in_stack = []
        for r in stack_data.get("resources", []):
            rid = r.get("resource_id") or r.get("id", "")
            if rid:
                res = db.get_resource(rid)
                if res:
                    resources_in_stack.append(res)
        return render_template(
            "intel_stack.html", stack=stack_data, resources=resources_in_stack
        )

    # ── Intelligence: Gap Analysis ──
    @app.route("/intelligence/gap")
    def intel_gap():
        return render_template("intel_gap.html")

    # ── Maintenance: Audit ──
    @app.route("/maintenance/audit")
    def maint_audit():
        page = int(request.args.get("page", 1))
        per_page = 25
        offset = (page - 1) * per_page
        log = db.get_audit_log(limit=per_page, offset=offset)
        total = db.count_audit_entries()
        return render_template(
            "maint_audit.html",
            log=log,
            page=page,
            per_page=per_page,
            total=total,
        )

    # ── Maintenance: Dedupe ──
    @app.route("/maintenance/dedupe")
    def maint_dedupe():
        return render_template("maint_dedupe.html")

    # ── Maintenance: Dead Links ──
    @app.route("/maintenance/dead-links")
    def maint_dead_links():
        dead = []
        try:
            import sqlite3

            conn = sqlite3.connect(db.get_db_path())
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM dead_links ORDER BY checked_at DESC"
            ).fetchall()
            dead = [dict(r) for r in rows]
            conn.close()
        except Exception:
            pass
        return render_template("maint_dead_links.html", dead_links=dead)

    # ── Maintenance: Notion Sync ──
    @app.route("/maintenance/sync")
    def maint_sync():
        status = _get_notion_status()
        sync_log = []
        try:
            from app.notion_sync import get_sync_log

            sync_log = get_sync_log(50)
        except Exception:
            pass
        return render_template("maint_sync.html", status=status, sync_log=sync_log)

    # ── AI: Prompt Dashboard ──
    @app.route("/ai/prompts")
    def ai_prompts():
        from app.feedback_tracker import get_all_task_stats

        stats = get_all_task_stats()
        return render_template("ai_prompts.html", stats=stats)

    @app.route("/ai/prompts/<task>")
    def ai_prompt_detail(task):
        from app.feedback_tracker import get_all_task_stats

        all_stats = get_all_task_stats()
        task_stat = next((s for s in all_stats if s.get("task") == task), None)
        corrections = []
        try:
            import json
            import sqlite3

            conn = sqlite3.connect(db.get_db_path())
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM prompt_feedback WHERE task = ? AND user_corrected = 1 ORDER BY created_at DESC LIMIT 50",
                [task],
            ).fetchall()
            corrections = [dict(r) for r in rows]
            conn.close()
        except Exception:
            pass
        return render_template(
            "ai_prompt.html", task=task, stat=task_stat, corrections=corrections
        )

    # ── AI: Corrections Log ──
    @app.route("/ai/corrections")
    def ai_corrections():
        corrections = []
        try:
            import json
            import sqlite3

            conn = sqlite3.connect(db.get_db_path())
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM prompt_feedback WHERE user_corrected = 1 ORDER BY created_at DESC LIMIT 100"
            ).fetchall()
            corrections = [dict(r) for r in rows]
            conn.close()
        except Exception:
            pass
        return render_template("ai_corrections.html", corrections=corrections)

    # ── Settings ──
    @app.route("/settings")
    def settings_page():
        config = db.get_pool_config()
        env_status = _get_env_status()
        return render_template("settings.html", config=config, env=env_status)

    @app.route("/settings/taxonomy")
    def taxonomy_page():
        taxonomy = {
            "domains": _TAXONOMY_DOMAINS,
            "types": _TAXONOMY_TYPES,
            "states": _TAXONOMY_STATES,
            "skill_levels": _TAXONOMY_SKILL_LEVELS,
            "formats": _TAXONOMY_FORMATS,
            "costs": _TAXONOMY_COSTS,
            "temporal_relevance": _TAXONOMY_TEMPORAL,
            "source_platforms": _TAXONOMY_PLATFORMS,
        }
        return render_template("taxonomy.html", taxonomy=taxonomy)

    # ── Search ──
    @app.route("/search")
    def search_route():
        q = request.args.get("q", "")
        domain = request.args.get("domain") or None
        type_ = request.args.get("type") or None
        page = int(request.args.get("page", 1))
        per_page = 25
        offset = (page - 1) * per_page
        results = []
        total = 0
        if q:
            results = search(query=q, domain=domain, type_=type_, limit=per_page)
            total = count_search(query=q, domain=domain, type_=type_)
        return render_template(
            "search.html",
            query=q,
            results=results,
            page=page,
            per_page=per_page,
            total=total,
        )

    # ── Trash ──
    @app.route("/trash")
    def trash_page():
        search_q = request.args.get("search") or None
        domain = request.args.get("domain") or None
        type_ = request.args.get("type") or None
        sort = request.args.get("sort", "deleted_at")
        page = int(request.args.get("page", 1))
        per_page = 25
        offset = (page - 1) * per_page
        results = db.get_trashed_resources(
            search_q=search_q,
            domain=domain,
            type_=type_,
            sort=sort,
            limit=per_page,
            offset=offset,
        )
        stats = db.get_trash_stats()
        all_domains = [d["domain"] for d in stats["by_domain"]]
        return render_template(
            "trash.html",
            resources=results,
            stats=stats,
            domains=all_domains,
            current_domain=domain or "",
            current_type=type_ or "",
            search_q=search_q or "",
            current_sort=sort,
            page=page,
            per_page=per_page,
            total=stats["total"],
        )

    return app


_TAXONOMY_DOMAINS = [
    "web",
    "network",
    "mobile",
    "cloud",
    "api",
    "wireless",
    "iot",
    "osint",
    "soc",
    "blueteam",
    "redteam",
    "purpleteam",
    "malware",
    "forensics",
    "cryptography",
    "reverse_engineering",
    "exploit_dev",
    "social_engineering",
    "physical",
    "governance",
    "privacy",
    "ai_security",
    "supply_chain",
    "devsecops",
    "identity",
    "blockchain",
    "ics_ot",
    "career",
    "general",
]
_TAXONOMY_TYPES = [
    "article",
    "tutorial",
    "writeup",
    "tool",
    "repository",
    "cheatsheet",
    "book",
    "course",
    "video",
    "playlist",
    "paper",
    "report",
    "dataset",
    "lab",
    "ctf",
    "framework",
    "table",
    "index",
    "ranking",
    "note",
    "thread",
    "newsletter",
    "podcast",
    "interview",
    "config",
    "template",
    "extension",
    "dashboard",
    "search_engine",
    "api",
    "community",
    "event",
    "certification",
    "glossary",
    "mindmap",
    "other",
]
_TAXONOMY_STATES = ["saved", "skimmed", "studied", "mastered", "applied"]
_TAXONOMY_SKILL_LEVELS = ["beginner", "intermediate", "advanced", "expert", "all"]
_TAXONOMY_FORMATS = [
    "text",
    "video",
    "interactive",
    "audio",
    "tool",
    "hands-on",
    "mixed",
]
_TAXONOMY_COSTS = ["free", "freemium", "paid", "one-time", "subscription"]
_TAXONOMY_TEMPORAL = ["evergreen", "time-sensitive", "historical", "emerging"]
_TAXONOMY_PLATFORMS = [
    "github",
    "medium",
    "youtube",
    "arxiv",
    "personal_blog",
    "hackerone",
    "bugcrowd",
    "intigriti",
    "portswigger",
    "tryhackme",
    "hackthebox",
    "twitter",
    "reddit",
    "discord",
    "vimeo",
    "notion",
    "gitbook",
    "confluence",
    "substack",
    "pdf",
    "other",
]


def _get_env_status() -> dict:
    import os

    keys = [
        "FREELLMAPI_URL",
        "FREELLMAPI_API_KEY",
        "FREELLMAPI_MODEL",
        "AI_ENABLED",
        "AI_CONFIDENCE_THRESHOLD",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
        "NOTION_TOKEN",
        "NOTION_DATABASE",
        "NOTION_SYNC_ENABLED",
        "OBSIDIAN_VAULT_PATH",
        "OBSIDIAN_SYNC_ENABLED",
        "POOLMIND_DB_PATH",
        "GITHUB_TOKEN",
        "LOG_LEVEL",
    ]

    try:
        from app.api.settings import _read_env_file

        file_env = _read_env_file()
    except Exception:
        file_env = {}

    status = {}
    for k in keys:
        runtime = os.getenv(k, "")
        raw = file_env.get(k, "")
        status[k] = {
            "set": bool(runtime),
            "value": runtime or raw or "",
            "in_file": k in file_env,
        }
    return status


def _get_ai_status() -> dict:
    import os
    import requests as _req

    url = os.getenv("FREELLMAPI_URL", "http://localhost:3001").rstrip("/")
    api_running = False
    try:
        r = _req.get(f"{url}/api/ping", timeout=3)
        api_running = r.status_code == 200
    except Exception:
        api_running = False

    try:
        from app.feedback_tracker import get_all_task_stats

        stats = get_all_task_stats()
        needs_evo = sum(1 for s in stats if s.get("needs_evolution"))
        total = sum(s.get("total_calls", 0) for s in stats)
        return {
            "api_running": api_running,
            "api_url": url,
            "needs_evolution": needs_evo,
            "total_calls": total,
        }
    except Exception:
        return {
            "api_running": api_running,
            "api_url": url,
            "needs_evolution": 0,
            "total_calls": 0,
        }


def _get_notion_status() -> dict:
    try:
        from app.notion_sync import get_sync_status

        return get_sync_status()
    except Exception:
        return {"pending": 0, "last_sync": None}


def run_server(host: str = "127.0.0.1", port: int = 5000, debug: bool = False):
    app = create_app()
    print(f"poolmind UI: http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_server(debug=True)
