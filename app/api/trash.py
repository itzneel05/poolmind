"""
API: Trash endpoints — soft delete, restore, purge, nuke.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request

from app import db
from app.obsidian_writer import (
    move_note_to_trash,
    restore_note_from_trash,
    delete_note_by_id,
)
from app.notion_sync import archive_resource, unarchive_resource

logger = logging.getLogger(__name__)
trash_bp = Blueprint("api_trash", __name__, url_prefix="/api/trash")


@trash_bp.route("", methods=["GET"])
def list_trash():
    search_q = request.args.get("search") or None
    domain = request.args.get("domain") or None
    type_ = request.args.get("type") or None
    sort = request.args.get("sort", "deleted_at")
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    results = db.get_trashed_resources(
        search_q=search_q,
        domain=domain,
        type_=type_,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return jsonify({"results": results, "total": len(results)})


@trash_bp.route("/stats", methods=["GET"])
def trash_stats():
    stats = db.get_trash_stats()
    return jsonify(stats)


@trash_bp.route("", methods=["POST"])
def trash_resources():
    data = request.get_json(force=True)
    ids = data.get("ids", [])
    reason = data.get("reason")
    if not ids:
        return jsonify({"error": "no_ids"}), 400
    result = db.trash_resources(ids, reason=reason)
    for rid in ids:
        res = db.get_resource(rid, include_trashed=True)
        if res:
            move_note_to_trash(rid)
            if res.notion_page_id:
                archive_resource(res.notion_page_id)
    return jsonify(result)


@trash_bp.route("/restore/check", methods=["POST"])
def restore_check():
    data = request.get_json(force=True)
    ids = data.get("ids", [])
    if not ids:
        return jsonify({"conflicts": []})
    conflicts = db.check_restore_conflicts(ids)
    return jsonify({"conflicts": conflicts})


@trash_bp.route("/restore", methods=["POST"])
def restore_resources():
    data = request.get_json(force=True)
    ids = data.get("ids", [])
    if not ids:
        return jsonify({"error": "no_ids"}), 400
    if not data.get("force"):
        conflicts = db.check_restore_conflicts(ids)
        if conflicts:
            return jsonify({"error": "conflicts", "conflicts": conflicts}), 409
    result = db.restore_resources(ids)
    for rid in ids:
        restore_note_from_trash(rid)
        res = db.get_resource(rid)
        if res and res.notion_page_id:
            unarchive_resource(res.notion_page_id)
    return jsonify(result)


@trash_bp.route("/purge", methods=["POST"])
def purge_resources():
    data = request.get_json(force=True)
    ids = data.get("ids", [])
    if not ids:
        return jsonify({"error": "no_ids"}), 400
    _backup_before_purge(ids)
    result = db.purge_resources(ids)
    for rid in ids:
        try:
            delete_note_by_id(rid)
        except Exception:
            pass
    return jsonify(result)


@trash_bp.route("/nuke", methods=["POST"])
def nuke_trash():
    data = request.get_json(force=True)
    confirmation = data.get("confirmation", "")
    if confirmation != "NUKE":
        return jsonify({"error": "confirmation_required"}), 400
    ids = []
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT id FROM resources WHERE deleted_at IS NOT NULL"
        ).fetchall()
        ids = [r["id"] for r in rows]
    if not ids:
        return jsonify({"nuked": 0})
    backup_path = _backup_before_purge(ids, label="nuke")
    result = db.purge_resources(ids)
    result["backup"] = backup_path
    for rid in ids:
        try:
            delete_note_by_id(rid)
        except Exception:
            pass
    return jsonify(result)


@trash_bp.route("/empty-expired", methods=["POST"])
def empty_expired():
    ids = []
    with db.get_conn() as conn:
        rows = conn.execute(
            """SELECT id FROM resources
               WHERE deleted_at IS NOT NULL
               AND trash_expires_at IS NOT NULL
               AND trash_expires_at < datetime('now')"""
        ).fetchall()
        ids = [r["id"] for r in rows]
    if not ids:
        return jsonify({"purged": 0})
    _backup_before_purge(ids, label="empty-expired")
    result = db.purge_resources(ids)
    for rid in ids:
        try:
            delete_note_by_id(rid)
        except Exception:
            pass
    return jsonify(result)


def _backup_before_purge(ids: list, label: str = "purge") -> str:
    backup_dir = Path("data/backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = backup_dir / f"trash_{label}_{timestamp}.json"
    rows = []
    for rid in ids:
        with db.get_conn() as conn:
            row = conn.execute("SELECT * FROM resources WHERE id = ?", [rid]).fetchone()
        if row:
            rows.append(dict(row))
    path.write_text(json.dumps(rows, indent=2, default=str))
    return str(path)
