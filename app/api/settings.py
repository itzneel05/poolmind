"""
API: Settings endpoints — config, taxonomy, env status.
"""

import logging
import os

from flask import Blueprint, jsonify, request

from app import db

logger = logging.getLogger(__name__)
settings_bp = Blueprint("api_settings", __name__, url_prefix="/api/settings")


@settings_bp.route("", methods=["GET"])
def get_settings():
    config = db.get_pool_config()
    return jsonify({"settings": config})


@settings_bp.route("", methods=["PATCH"])
def update_settings():
    data = request.get_json(force=True)
    updated = {}
    for key, value in data.items():
        db.set_config(key, str(value))
        updated[key] = str(value)
    return jsonify({"updated": updated})


_ENV_KEYS = [
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


def _get_env_file() -> str:
    from pathlib import Path

    return str(Path(__file__).resolve().parent.parent.parent / ".env")


def _read_env_file() -> dict:
    path = _get_env_file()
    if not os.path.exists(path):
        return {}
    result = {}
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip()
    return result


def _write_env_file(updates: dict) -> None:
    path = _get_env_file()
    current = _read_env_file()
    current.update(updates)

    # Build header order + sorted keys for readability
    sections = {
        "AI": [
            "FREELLMAPI_URL",
            "FREELLMAPI_API_KEY",
            "FREELLMAPI_MODEL",
            "AI_ENABLED",
            "AI_CONFIDENCE_THRESHOLD",
        ],
        "OpenAI": ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"],
        "Notion": ["NOTION_TOKEN", "NOTION_DATABASE", "NOTION_SYNC_ENABLED"],
        "Paths": ["OBSIDIAN_VAULT_PATH", "OBSIDIAN_SYNC_ENABLED", "POOLMIND_DB_PATH"],
        "GitHub": ["GITHUB_TOKEN"],
        "Behavior": ["LOG_LEVEL"],
    }
    written = set()
    lines = []
    for section, keys in sections.items():
        sec_lines = [k for k in keys if k in current]
        if sec_lines:
            lines.append(f"\n# {section}")
            for k in sec_lines:
                lines.append(f"{k}={current[k]}")
                written.add(k)

    # Any leftover keys not in sections
    extras = {k: v for k, v in current.items() if k not in written}
    if extras:
        lines.append("\n# Other")
        for k, v in extras.items():
            lines.append(f"{k}={v}")

    with open(path, "w") as f:
        f.write("\n".join(lines).lstrip("\n") + "\n")


@settings_bp.route("/env", methods=["GET"])
def env_status():
    file_env = _read_env_file()
    status = {}
    for k in _ENV_KEYS:
        runtime = os.getenv(k, "")
        raw = file_env.get(k, "")
        status[k] = {
            "set": bool(runtime),
            "value": runtime or raw or "",
            "in_file": k in file_env,
        }
    return jsonify({"env": status})


@settings_bp.route("/env", methods=["PATCH"])
def env_update():
    data = request.get_json(force=True)
    key = data.get("key", "").strip().upper()
    value = data.get("value", "").strip()
    if not key:
        return jsonify({"error": "key_required"}), 400
    if key not in _ENV_KEYS:
        return jsonify({"error": f"unknown_key:{key}"}), 400

    _write_env_file({key: value})
    os.environ[key] = value
    return jsonify({"updated": {key: value}})


@settings_bp.route("/taxonomy", methods=["GET"])
def get_taxonomy():
    from pathlib import Path
    import yaml

    tax_path = Path("config/taxonomy.yaml")
    if not tax_path.exists():
        return jsonify({"taxonomy": {}})
    try:
        tax = yaml.safe_load(tax_path.read_text())
        return jsonify({"taxonomy": tax})
    except Exception as e:
        return jsonify({"error": str(e)[:200]}), 500
