"""
API: Browse endpoints — random, untouched, recent, by-state.
"""

import logging

from flask import Blueprint, jsonify, request

from app import db
from app.search import get_random, get_recent, get_untouched

logger = logging.getLogger(__name__)
browse_bp = Blueprint("api_browse", __name__, url_prefix="/api/resources")


@browse_bp.route("/random", methods=["GET"])
def browse_random():
    count = int(request.args.get("count", 1))
    results = get_random(count)
    return jsonify({"resources": [r.to_dict() for r in results]})


@browse_bp.route("/untouched", methods=["GET"])
def browse_untouched():
    limit = int(request.args.get("limit", 20))
    results = get_untouched(limit=limit)
    return jsonify({"resources": [r.to_dict() for r in results], "total": len(results)})


@browse_bp.route("/recent", methods=["GET"])
def browse_recent():
    limit = int(request.args.get("limit", 20))
    results = get_recent(limit=limit)
    return jsonify({"resources": [r.to_dict() for r in results], "total": len(results)})


@browse_bp.route("/by-state/<state>", methods=["GET"])
def browse_by_state(state):
    from app.search import list_by_filter

    limit = int(request.args.get("limit", 50))
    results = list_by_filter(consumption_state=state, limit=limit)
    return jsonify({"resources": [r.to_dict() for r in results], "total": len(results)})
