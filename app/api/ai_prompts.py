"""
API: AI / Prompt endpoints — stats, evolution, corrections, restore.
"""

import json
import logging

from flask import Blueprint, jsonify, request

from app.feedback_tracker import (
    get_all_task_stats,
    get_task_stats,
    get_evolution_history,
    get_correction_details,
)
from app.prompt_evolution import evolve_prompt, evolve_all, list_backups, restore_prompt

logger = logging.getLogger(__name__)
ai_bp = Blueprint("api_ai", __name__, url_prefix="/api/ai")


@ai_bp.route("/prompts", methods=["GET"])
def prompt_stats():
    stats = get_all_task_stats()
    return jsonify({"prompts": stats})


@ai_bp.route("/prompts/<task>", methods=["GET"])
def prompt_task_detail(task):
    stats = get_task_stats(task)
    history = get_evolution_history(task=task)
    backups = list_backups(task)
    corrections = get_correction_details(task)
    return jsonify(
        {
            "stats": stats,
            "history": history,
            "backups": backups,
            "corrections": corrections,
        }
    )


@ai_bp.route("/evolve/preview", methods=["POST"])
def evolve_preview():
    data = request.get_json(force=True)
    task = data.get("task", "").strip()
    if not task:
        return jsonify({"error": "task_required"}), 400
    result = evolve_prompt(task=task, force=data.get("force", False), dry_run=True)
    return jsonify({"result": result})


@ai_bp.route("/evolve/run", methods=["POST"])
def evolve_run():
    data = request.get_json(force=True)
    task = data.get("task", "").strip()
    force = data.get("force", False)
    last_n = int(data.get("last_n", 50))

    if task:
        result = evolve_prompt(
            task=task, force=force, dry_run=False, last_n_feedback=last_n
        )
        return jsonify({"results": [result]})
    else:
        results = evolve_all(force=force, dry_run=False, last_n_feedback=last_n)
        return jsonify({"results": results})


@ai_bp.route("/evolve/<task>/deploy", methods=["POST"])
def evolve_deploy(task):
    result = evolve_prompt(task=task, force=True, dry_run=False)
    if result.get("evolved"):
        return jsonify({"result": result})
    return jsonify(
        {"error": "evolution_failed", "reason": result.get("reason", "unknown")}
    ), 500


@ai_bp.route("/prompts/<task>/restore", methods=["POST"])
def prompt_restore(task):
    data = request.get_json(force=True)
    version = data.get("version", "").strip()
    if not version:
        backups = list_backups(task)
        return jsonify({"backups": backups})
    success = restore_prompt(task, version_timestamp=version)
    if success:
        return jsonify({"restored": True, "task": task, "version": version})
    return jsonify({"error": "restore_failed", "version": version}), 404


@ai_bp.route("/corrections", methods=["GET"])
def corrections_log():
    from app.feedback_tracker import get_all_task_stats

    stats = get_all_task_stats()
    corrections_data = {}
    for s in stats:
        task = s["task"]
        corrections_data[task] = get_correction_details(task)
    return jsonify({"corrections": corrections_data})
