"""
API: Ingest endpoints — parse preview + run ingestion.
"""

import json
import logging
import time

from flask import Blueprint, jsonify, request, Response

from app.bulk_parser import parse_bulk_input, parse_bulk_file, summarize_parse_results

logger = logging.getLogger(__name__)
ingest_bp = Blueprint("api_ingest", __name__, url_prefix="/api/ingest")


@ingest_bp.route("/parse", methods=["POST"])
def ingest_parse():
    data = request.get_json(force=True)
    text = data.get("text", "")
    if not text.strip():
        return jsonify({"error": "text_required"}), 400
    entries = parse_bulk_input(text)
    summary = summarize_parse_results(entries)
    parsed = [
        {
            "entry_type": e.entry_type,
            "url": e.url,
            "title": e.title,
            "notes": e.notes,
            "confidence": e.confidence,
            "line_number": e.line_number,
        }
        for e in entries
    ]
    return jsonify({"entries": parsed, "summary": summary})


@ingest_bp.route("/run", methods=["POST"])
def ingest_run():
    """Run ingestion from parsed entries. Returns job_id for polling."""
    from app.ingest_router import ingest_entries, build_ingestion_report

    data = request.get_json(force=True)
    entries_data = data.get("entries", [])
    selected = data.get("selected", None)
    ai_disabled = data.get("ai_disabled", False)
    skip_notion_sync = data.get("skip_notion_sync", False)
    skip_obsidian = data.get("skip_obsidian", False)

    from app.bulk_parser import ParsedEntry

    entries = []
    for ed in entries_data:
        entries.append(
            ParsedEntry(
                raw_line=ed.get("raw_line", ""),
                entry_type=ed.get("entry_type", "url_only"),
                url=ed.get("url"),
                title=ed.get("title"),
                notes=ed.get("notes"),
                confidence=ed.get("confidence", 1.0),
                line_number=ed.get("line_number", 0),
            )
        )

    if selected is not None:
        entries = [e for i, e in enumerate(entries) if i in selected]

    results = ingest_entries(
        entries=entries,
        ai_disabled=ai_disabled,
        skip_notion_sync=skip_notion_sync,
        skip_obsidian=skip_obsidian,
    )
    report = build_ingestion_report(results)

    return jsonify({"report": report})


@ingest_bp.route("/run/stream", methods=["POST"])
def ingest_run_stream():
    """Stream ingestion progress as SSE events."""
    from app.ingest_router import ingest_entries, build_ingestion_report

    data = request.get_json(force=True)
    entries_data = data.get("entries", [])
    selected = data.get("selected", None)
    ai_disabled = data.get("ai_disabled", False)
    skip_notion_sync = data.get("skip_notion_sync", False)
    skip_obsidian = data.get("skip_obsidian", False)

    from app.bulk_parser import ParsedEntry

    entries = []
    for ed in entries_data:
        entries.append(
            ParsedEntry(
                raw_line=ed.get("raw_line", ""),
                entry_type=ed.get("entry_type", "url_only"),
                url=ed.get("url"),
                title=ed.get("title"),
                notes=ed.get("notes"),
                confidence=ed.get("confidence", 1.0),
                line_number=ed.get("line_number", 0),
            )
        )

    if selected is not None:
        entries = [e for i, e in enumerate(entries) if i in selected]

    def generate():
        results = []

        def on_progress(current, total, result):
            entry = result.entry
            title = (entry.title or entry.url or "?")[:60]
            data_chunk = json.dumps(
                {
                    "current": current,
                    "total": total,
                    "action": result.action,
                    "title": title,
                    "error": result.error,
                    "complete": current >= total,
                }
            )
            results.append(result)
            yield f"data: {data_chunk}\n\n"

        if not entries:
            yield f"data: {json.dumps({'complete': True, 'total': 0, 'current': 0})}\n\n"
            return

        ingest_entries(
            entries=entries,
            ai_disabled=ai_disabled,
            skip_notion_sync=skip_notion_sync,
            skip_obsidian=skip_obsidian,
            on_progress=on_progress,
        )

        report = build_ingestion_report(results)
        yield f"data: {json.dumps({'complete': True, 'report': report})}\n\n"

    return Response(generate(), mimetype="text/event-stream")
