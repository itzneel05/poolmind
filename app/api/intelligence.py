"""
API: Intelligence endpoints — learning paths, stacks, gap analysis.
"""

import json
import logging

from flask import Blueprint, jsonify, request

from app import db

logger = logging.getLogger(__name__)
intelligence_bp = Blueprint("api_intel", __name__, url_prefix="/api")


@intelligence_bp.route("/paths/generate", methods=["POST"])
def generate_path():
    from app.freellm_tasks import generate_learning_path

    data = request.get_json(force=True)
    goal = data.get("goal", "").strip()
    if not goal:
        return jsonify({"error": "goal_required"}), 400

    all_resources = db.get_all_resources(limit=200)
    pool_data = [
        {
            "id": r.id,
            "title": r.title,
            "domain": r.domain,
            "skill_level": r.skill_level,
            "time_to_value": r.time_to_value,
            "type": r.type,
        }
        for r in all_resources
    ]

    result = generate_learning_path(goal=goal, pool_resources=pool_data)
    if not result:
        return jsonify({"error": "generation_failed"}), 500

    path_id = _save_path(goal, result)
    return jsonify({"path": result, "path_id": path_id})


@intelligence_bp.route("/paths", methods=["GET"])
def list_paths():
    paths = _load_paths()
    return jsonify({"paths": paths})


@intelligence_bp.route("/paths/<path_id>", methods=["GET"])
def get_path(path_id):
    paths = _load_paths()
    p = next((x for x in paths if x.get("id") == path_id), None)
    if not p:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"path": p})


@intelligence_bp.route("/paths/<path_id>", methods=["DELETE"])
def delete_path(path_id):
    import os
    from pathlib import Path

    paths_file = Path("data/learning_paths.json")
    if not paths_file.exists():
        return jsonify({"error": "not_found"}), 404
    paths = json.loads(paths_file.read_text())
    paths = [p for p in paths if p.get("id") != path_id]
    paths_file.write_text(json.dumps(paths, indent=2))
    return jsonify({"deleted": True})


@intelligence_bp.route("/stacks/generate", methods=["POST"])
def generate_stack():
    from app.freellm_tasks import generate_stack as ai_stack

    data = request.get_json(force=True)
    mission = data.get("mission", "").strip()
    if not mission:
        return jsonify({"error": "mission_required"}), 400

    all_resources = db.get_all_resources(limit=200)
    pool_data = [
        {"id": r.id, "title": r.title, "domain": r.domain, "type": r.type}
        for r in all_resources
    ]

    result = ai_stack(mission=mission, pool_resources=pool_data)
    if not result:
        return jsonify({"error": "stack_generation_failed"}), 500

    stack_id = _save_stack(mission, result)
    return jsonify({"stack": result, "stack_id": stack_id})


@intelligence_bp.route("/stacks", methods=["GET"])
def list_stacks():
    stacks = _load_stacks()
    return jsonify({"stacks": stacks})


@intelligence_bp.route("/stacks/<stack_id>", methods=["GET"])
def get_stack(stack_id):
    stacks = _load_stacks()
    s = next((x for x in stacks if x.get("id") == stack_id), None)
    if not s:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"stack": s})


@intelligence_bp.route("/stacks/<stack_id>", methods=["DELETE"])
def delete_stack(stack_id):
    import os
    from pathlib import Path

    stacks_file = Path("data/resource_stacks.json")
    if not stacks_file.exists():
        return jsonify({"error": "not_found"}), 404
    stacks = json.loads(stacks_file.read_text())
    stacks = [s for s in stacks if s.get("id") != stack_id]
    stacks_file.write_text(json.dumps(stacks, indent=2))
    return jsonify({"deleted": True})


@intelligence_bp.route("/gap", methods=["POST"])
def gap_analysis():
    from app.audit import run_gap_report

    report = run_gap_report()
    if not report:
        return jsonify({"error": "gap_report_failed"}), 500
    return jsonify({"gap_report": report})


def _save_path(goal: str, result: dict) -> str:
    import json
    import os
    from datetime import datetime
    from pathlib import Path

    paths_file = Path("data/learning_paths.json")
    paths = json.loads(paths_file.read_text()) if paths_file.exists() else []
    path_id = f"path_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    paths.append(
        {
            "id": path_id,
            "goal": goal,
            "path_name": result.get("path_name", goal),
            "weeks": result.get("weeks", []),
            "created_at": datetime.now().isoformat(),
        }
    )
    paths_file.parent.mkdir(parents=True, exist_ok=True)
    paths_file.write_text(json.dumps(paths, indent=2))
    return path_id


def _save_stack(mission: str, result: dict) -> str:
    import json
    import os
    from datetime import datetime
    from pathlib import Path

    stacks_file = Path("data/resource_stacks.json")
    stacks = json.loads(stacks_file.read_text()) if stacks_file.exists() else []
    stack_id = f"stack_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    stacks.append(
        {
            "id": stack_id,
            "mission": mission,
            "stack_name": result.get("stack_name", mission),
            "description": result.get("description", ""),
            "resources": result.get("resources", []),
            "created_at": datetime.now().isoformat(),
        }
    )
    stacks_file.parent.mkdir(parents=True, exist_ok=True)
    stacks_file.write_text(json.dumps(stacks, indent=2))
    return stack_id


def _load_paths() -> list:
    import json
    from pathlib import Path

    paths_file = Path("data/learning_paths.json")
    if not paths_file.exists():
        return []
    return json.loads(paths_file.read_text())


def _load_stacks() -> list:
    import json
    from pathlib import Path

    stacks_file = Path("data/resource_stacks.json")
    if not stacks_file.exists():
        return []
    return json.loads(stacks_file.read_text())
