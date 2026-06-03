"""
API: Resource CRUD + actions.
"""

import json
import logging

from flask import Blueprint, jsonify, request

from app import db
from app.add_resource import add_from_url, add_manual
from app.feedback_tracker import log_user_correction

logger = logging.getLogger(__name__)
resources_bp = Blueprint("api_resources", __name__, url_prefix="/api")


@resources_bp.route("/resources", methods=["GET"])
def list_resources():
    domain = request.args.get("domain") or None
    type_ = request.args.get("type") or None
    state = request.args.get("state") or None
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))

    if domain or type_ or state:
        from app.search import list_by_filter

        resources = list_by_filter(
            domain=domain, type_=type_, consumption_state=state, limit=limit
        )
    else:
        resources = db.get_all_resources(limit=limit)
    return jsonify(
        {"resources": [r.to_dict() for r in resources], "total": len(resources)}
    )


@resources_bp.route("/resource/<resource_id>", methods=["GET"])
def get_resource(resource_id):
    resource = db.get_resource(resource_id)
    if not resource:
        return jsonify({"error": "not_found"}), 404
    related = []
    for rid in resource.related_resources:
        r = db.get_resource(rid)
        if r:
            related.append(r.to_dict())
    return jsonify({"resource": resource.to_dict(), "related": related})


@resources_bp.route("/add", methods=["POST"])
def add_resource():
    data = request.get_json(force=True)
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "url_required"}), 400
    try:
        resource = add_from_url(
            url=url,
            notes=data.get("notes", ""),
            ai_disabled=data.get("ai_disabled", False),
            skip_notion=data.get("skip_notion", False),
            skip_obsidian=data.get("skip_obsidian", False),
            force=data.get("force", False),
        )
        if resource:
            return jsonify({"resource": resource.to_dict(), "action": "added"}), 201
        return jsonify({"error": "add_failed"}), 500
    except Exception as e:
        logger.error("API add failed: %s", e)
        return jsonify({"error": str(e)[:200]}), 500


@resources_bp.route("/add/manual", methods=["POST"])
def add_manual_resource():
    data = request.get_json(force=True)
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title_required"}), 400
    try:
        resource = add_manual(data)
        if resource:
            return jsonify({"resource": resource.to_dict(), "action": "added"}), 201
        return jsonify({"error": "add_failed"}), 500
    except Exception as e:
        logger.error("API add-manual failed: %s", e)
        return jsonify({"error": str(e)[:200]}), 500


@resources_bp.route("/resource/<resource_id>", methods=["PATCH"])
def update_resource(resource_id):
    resource = db.get_resource(resource_id)
    if not resource:
        return jsonify({"error": "not_found"}), 404
    data = request.get_json(force=True)
    allowed = {
        "title",
        "url",
        "type",
        "domain",
        "subdomain",
        "tags",
        "skill_level",
        "format",
        "cost",
        "author",
        "year_published",
        "language",
        "time_to_value",
        "learning_path",
        "prerequisites",
        "summary",
        "why_it_matters",
        "best_for",
        "avoid_if",
        "notes",
        "consumption_state",
        "personal_rating",
        "quality_score",
        "source_platform",
        "temporal_relevance",
        "extended_meta",
    }
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields:
        return jsonify({"error": "no_valid_fields"}), 400
    success = db.update_resource(resource_id, fields)
    if success:
        updated = db.get_resource(resource_id)
        return jsonify({"resource": updated.to_dict() if updated else None})
    return jsonify({"error": "update_failed"}), 500


@resources_bp.route("/resource/<resource_id>", methods=["DELETE"])
def delete_resource(resource_id):
    hard = request.args.get("hard", "0") == "1"
    data = request.get_json(silent=True) or {}
    hard = data.get("hard", hard)
    success = db.delete_resource(resource_id, hard=hard)
    if success:
        return jsonify({"deleted": True, "hard": hard})
    return jsonify({"error": "not_found"}), 404


@resources_bp.route("/resource/<resource_id>/rate", methods=["POST"])
def rate_resource(resource_id):
    data = request.get_json(force=True)
    score = data.get("score")
    if not isinstance(score, int) or not 1 <= score <= 10:
        return jsonify({"error": "score_must_be_1_to_10"}), 400
    success = db.update_resource(resource_id, {"personal_rating": score})
    if success:
        return jsonify({"rated": True, "score": score})
    return jsonify({"error": "not_found"}), 404


@resources_bp.route("/resource/<resource_id>/state", methods=["POST"])
def set_resource_state(resource_id):
    data = request.get_json(force=True)
    state = data.get("state", "").strip()
    valid = {"saved", "skimmed", "studied", "mastered", "applied"}
    if state not in valid:
        return jsonify({"error": f"invalid_state; must be: {', '.join(valid)}"}), 400
    success = db.update_resource(resource_id, {"consumption_state": state})
    if success:
        db.increment_used(resource_id)
        return jsonify({"state": state})
    return jsonify({"error": "not_found"}), 404


@resources_bp.route("/resource/<resource_id>/tags", methods=["POST"])
def set_resource_tags(resource_id):
    data = request.get_json(force=True)
    tags = data.get("tags", [])
    if not isinstance(tags, list):
        return jsonify({"error": "tags_must_be_array"}), 400
    resource = db.get_resource(resource_id)
    if not resource:
        return jsonify({"error": "not_found"}), 404
    combined = list(set(resource.tags + tags))[:15]
    db.update_resource(resource_id, {"tags": combined})
    return jsonify({"tags": combined})


@resources_bp.route("/resource/<resource_id>/note", methods=["POST"])
def add_resource_note(resource_id):
    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "text_required"}), 400
    resource = db.get_resource(resource_id)
    if not resource:
        return jsonify({"error": "not_found"}), 404
    existing = resource.notes or ""
    new_note = f"{existing}\n{text}".strip() if existing else text
    db.update_resource(resource_id, {"notes": new_note})
    return jsonify({"notes": new_note})


@resources_bp.route("/resource/<resource_id>/use", methods=["POST"])
def use_resource(resource_id):
    db.increment_used(resource_id)
    resource = db.get_resource(resource_id)
    if resource:
        return jsonify({"times_used": resource.times_used})
    return jsonify({"error": "not_found"}), 404


@resources_bp.route("/resource/<resource_id>/correct", methods=["POST"])
def correct_resource(resource_id):
    data = request.get_json(force=True)
    field = data.get("field", "").strip()
    old_value = data.get("old", "").strip()
    new_value = data.get("new", "").strip()
    if not field or not new_value:
        return jsonify({"error": "field_and_new_required"}), 400
    resource = db.get_resource(resource_id)
    if not resource:
        return jsonify({"error": "not_found"}), 404
    db.update_resource(resource_id, {field: new_value})
    task = _map_field_to_task(field)
    input_content = json.dumps(
        {"resource_id": resource_id, "field": field, "old": old_value}
    )
    log_user_correction(task, input_content, f"{field}: {old_value} -> {new_value}")
    return jsonify(
        {"corrected": True, "field": field, "old": old_value, "new": new_value}
    )


@resources_bp.route("/resource/<resource_id>/sync", methods=["POST"])
def sync_resource_notion(resource_id):
    from app.notion_sync import sync_resource

    resource = db.get_resource(resource_id)
    if not resource:
        return jsonify({"error": "not_found"}), 404
    try:
        result = sync_resource(resource)
        return jsonify({"synced": True, "result": result})
    except Exception as e:
        logger.error("Notion sync failed for %s: %s", resource_id, e)
        return jsonify({"error": str(e)[:200]}), 500


@resources_bp.route("/resource/<resource_id>/re-extract", methods=["POST"])
def re_extract_resource(resource_id):
    from app.extractors import extract_metadata
    from app.classifier import classify
    from app.normalizer import normalize_url
    from app.freellm_tasks import classify_resource as ai_classify, summarize_resource

    resource = db.get_resource(resource_id)
    if not resource:
        return jsonify({"error": "not_found"}), 404
    if not resource.url or resource.url == "local":
        return jsonify({"error": "no_url_to_extract"}), 400
    try:
        meta = extract_metadata(resource.url)
        if meta:
            meta["url"] = normalize_url(resource.url)
            import json as _json

            clean = {}
            for k, v in meta.items():
                if k.startswith("_"):
                    continue
                if isinstance(v, (dict, list)):
                    clean[k] = _json.dumps(v)
                else:
                    clean[k] = v
            db.update_resource(resource_id, clean)
        return jsonify({"re_extracted": True})
    except Exception as e:
        logger.error("Re-extract failed for %s: %s", resource_id, e)
        return jsonify({"error": str(e)[:200]}), 500


def _map_field_to_task(field: str) -> str:
    m = {
        "type": "classify_resource",
        "domain": "classify_resource",
        "subdomain": "classify_resource",
        "skill_level": "classify_resource",
        "format": "classify_resource",
        "time_to_value": "classify_resource",
        "cost": "classify_resource",
        "summary": "summarize_resource",
        "why_it_matters": "summarize_resource",
        "best_for": "summarize_resource",
        "avoid_if": "summarize_resource",
        "quality_score": "summarize_resource",
        "tags": "generate_tags",
        "notes": "improve_note",
    }
    return m.get(field, "classify_resource")
