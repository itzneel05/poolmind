"""
API: Search endpoints — keyword + natural language.
"""

import logging

from flask import Blueprint, jsonify, request

from app.search import search

logger = logging.getLogger(__name__)
search_bp = Blueprint("api_search", __name__, url_prefix="/api/search")


@search_bp.route("", methods=["GET"])
def search_resources():
    q = request.args.get("q", "").strip()
    domain = request.args.get("domain") or None
    type_ = request.args.get("type") or None
    skill = request.args.get("skill") or None
    format_ = request.args.get("format") or None
    cost = request.args.get("cost") or None
    state = request.args.get("state") or None
    min_quality = request.args.get("min_quality", type=int) or None
    limit = int(request.args.get("limit", 50))

    filters = {}
    if domain:
        filters["domain"] = domain
    if type_:
        filters["type_"] = type_

    results = search(
        query=q,
        domain=domain,
        type_=type_,
        skill_level=skill,
        format_=format_,
        cost=cost,
        min_quality=min_quality,
        limit=limit,
        natural_language=False,
    )
    return jsonify({"results": [r.to_dict() for r in results], "total": len(results)})


@search_bp.route("/nl", methods=["POST"])
def search_natural_language():
    data = request.get_json(force=True)
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "query_required"}), 400

    from app.freellm_tasks import parse_query

    parsed = parse_query(query)
    domain = data.get("domain") or (parsed.get("domain") if parsed else None)
    skill = data.get("skill") or (parsed.get("skill_level") if parsed else None)
    limit = int(data.get("limit", 50))

    results = search(
        query=query,
        domain=domain,
        skill_level=skill,
        limit=limit,
        natural_language=False,
    )
    return jsonify(
        {
            "parsed_query": parsed,
            "results": [r.to_dict() for r in results],
            "total": len(results),
        }
    )
