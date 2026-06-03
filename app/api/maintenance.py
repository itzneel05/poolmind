"""
API: Maintenance endpoints — audit, dedupe, dead-links, notion sync.
"""

import logging

from flask import Blueprint, jsonify, request

from app import db

logger = logging.getLogger(__name__)
maintenance_bp = Blueprint("api_maintenance", __name__, url_prefix="/api")


@maintenance_bp.route("/audit", methods=["POST"])
def run_audit():
    from app.audit import full_audit

    try:
        result = full_audit()
        return jsonify({"audit": result})
    except Exception as e:
        logger.error("Audit failed: %s", e)
        return jsonify({"error": str(e)[:200]}), 500


@maintenance_bp.route("/dedupe", methods=["POST"])
def run_dedupe():
    from app.dedupe import find_all_duplicates

    threshold = int(request.args.get("threshold", 85))
    try:
        dupes = find_all_duplicates(threshold=threshold)
        return jsonify({"duplicates": dupes, "count": len(dupes)})
    except Exception as e:
        logger.error("Dedupe failed: %s", e)
        return jsonify({"error": str(e)[:200]}), 500


@maintenance_bp.route("/dead-check", methods=["POST"])
def run_dead_check():
    from app.audit import dead_check

    limit = int(request.args.get("limit", 50))
    auto_tombstone = request.args.get("auto_tombstone", "0") == "1"
    try:
        results = dead_check(limit=limit, auto_tombstone=auto_tombstone)
        return jsonify({"dead_check": results})
    except Exception as e:
        logger.error("Dead check failed: %s", e)
        return jsonify({"error": str(e)[:200]}), 500


@maintenance_bp.route("/dead-links", methods=["GET"])
def list_dead_links():
    try:
        conn = db._get_conn()
        rows = conn.execute(
            "SELECT dl.*, r.title FROM dead_links dl LEFT JOIN resources r ON dl.resource_id = r.id ORDER BY dl.checked_at DESC"
        ).fetchall()
        conn.close()
        return jsonify({"dead_links": [dict(r) for r in rows]})
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 500


@maintenance_bp.route("/sync/notion/status", methods=["GET"])
def notion_sync_status():
    from app.notion_sync import get_sync_status

    try:
        status = get_sync_status()
        return jsonify({"status": status})
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 500


@maintenance_bp.route("/sync/notion/run", methods=["POST"])
def notion_sync_run():
    from app.notion_sync import sync_all_pending

    data = request.get_json(silent=True) or {}
    batch = int(data.get("batch_size", 10))
    try:
        result = sync_all_pending(batch_size=batch)
        return jsonify(
            {"synced": result.get("synced", 0), "failed": result.get("failed", 0)}
        )
    except Exception as e:
        logger.error("Notion sync failed: %s", e)
        return jsonify({"error": str(e)[:200]}), 500


@maintenance_bp.route("/sync/notion/log", methods=["GET"])
def notion_sync_log():
    from app.notion_sync import get_sync_log

    try:
        log = get_sync_log()
        return jsonify({"log": log})
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 500
