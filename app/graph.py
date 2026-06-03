"""
Resource graph visualization for poolmind.
Builds node-edge graphs from the resource pool and exports to
Obsidian (wiki-links) or standalone D3.js HTML.
"""

import json
import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

from app import db
from app.obsidian_writer import get_resource_folder, note_filename, slug
from models.resource import Resource

logger = logging.getLogger(__name__)


# ── Graph Data Builder ────────────────────────────────────────────────────


def build_graph_data(
    min_edge_weight: int = 1,
) -> dict:
    resources = db.get_all_resources(limit=500, exclude_archived=True)
    node_map = {}
    edge_map = {}

    for r in resources:
        node_map[r.id] = {
            "id": r.id,
            "title": r.title,
            "type": r.type,
            "domain": r.domain,
            "tags": r.tags,
            "skill_level": r.skill_level,
            "quality_score": r.quality_score or 0,
            "consumption_state": r.consumption_state,
            "url": r.url,
        }

    # Edges from explicit related_resources
    for r in resources:
        for related_id in r.related_resources:
            if related_id in node_map:
                _add_edge(edge_map, r.id, related_id, weight=5, source="related")

    # Implicit edges: shared domain
    domain_groups = _group_by(resources, "domain")
    for _domain, group in domain_groups.items():
        ids = [r.id for r in group]
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                _add_edge(edge_map, ids[i], ids[j], weight=2, source="domain")

    # Implicit edges: shared type
    type_groups = _group_by(resources, "type")
    for _type, group in type_groups.items():
        if len(group) > 1 and len(group) <= 20:
            ids = [r.id for r in group]
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    _add_edge(edge_map, ids[i], ids[j], weight=1, source="type")

    # Filter by minimum weight
    edges = [e for e in edge_map.values() if e["weight"] >= min_edge_weight]

    return {
        "nodes": list(node_map.values()),
        "edges": edges,
        "node_count": len(node_map),
        "edge_count": len(edges),
    }


def _add_edge(edge_map: dict, id_a: str, id_b: str, weight: int, source: str) -> None:
    key = tuple(sorted([id_a, id_b]))
    if key in edge_map:
        edge_map[key]["weight"] += weight
        if source not in edge_map[key]["sources"]:
            edge_map[key]["sources"].append(source)
    else:
        edge_map[key] = {
            "source": key[0],
            "target": key[1],
            "weight": weight,
            "sources": [source],
        }


def _group_by(resources: List[Resource], field: str) -> dict:
    groups = {}
    for r in resources:
        val = getattr(r, field, "unknown")
        groups.setdefault(val, []).append(r)
    return groups


# ── Obsidian Export ────────────────────────────────────────────────────────


def export_obsidian_links(graph_data: dict) -> dict:
    folder = get_resource_folder()
    node_ids = {n["id"] for n in graph_data["nodes"]}
    stats = {"notes_updated": 0, "hub_written": False, "links_added": 0}

    # Build link map: resource_id -> set of related resource IDs
    link_map: dict[str, set] = {}
    for edge in graph_data["edges"]:
        link_map.setdefault(edge["source"], set()).add(edge["target"])
        link_map.setdefault(edge["target"], set()).add(edge["source"])

    wiki_link_pattern = re.compile(r"\[\[resource-[^\]]+\]\]")

    for node in graph_data["nodes"]:
        rid = node["id"]
        if rid not in link_map:
            continue

        note_path = folder / note_filename(
            Resource(id=rid, title=node["title"], url="local", type=node["type"])
        )
        if not note_path.exists():
            continue

        existing_links = set(
            wiki_link_pattern.findall(note_path.read_text(encoding="utf-8"))
        )

        new_links = []
        for target_id in link_map[rid]:
            if target_id not in node_ids:
                continue
            target_node = next(
                (n for n in graph_data["nodes"] if n["id"] == target_id), None
            )
            if not target_node:
                continue
            link_text = f"resource-{target_id}-{slug(target_node['title'])}"
            wiki = f"[[{link_text}|{target_node['title'][:50]}]]"
            if wiki not in existing_links:
                new_links.append(wiki)

        if not new_links:
            continue

        text = note_path.read_text(encoding="utf-8")
        # Insert wiki-links before the "## Tags" section
        links_section = (
            "\n\n## Related Resources\n" + "\n".join(f"- {l}" for l in new_links) + "\n"
        )
        if "## Related Resources" not in text:
            text = text.replace("## Tags", links_section + "\n## Tags")
            stats["links_added"] += len(new_links)
            stats["notes_updated"] += 1
            note_path.write_text(text, encoding="utf-8")

    # Write hub index
    hub_path = folder / "resource-hub.md"
    hub_lines = [
        "# Resource Hub",
        "",
        "All resources in the pool, organized by domain:",
        "",
    ]
    by_domain = {}
    for node in graph_data["nodes"]:
        by_domain.setdefault(node["domain"], []).append(node)

    for domain in sorted(by_domain):
        hub_lines.append(f"## {domain.title()}")
        for node in sorted(by_domain[domain], key=lambda n: n["title"].lower()):
            note_name = f"resource-{node['id']}-{slug(node['title'])}"
            hub_lines.append(f"- [[{note_name}|{node['title']}]]  ({node['type']})")
        hub_lines.append("")

    hub_lines.append("---")
    hub_lines.append(f"*{len(graph_data['nodes'])} resources | Generated by poolmind*")

    hub_path.write_text("\n".join(hub_lines), encoding="utf-8")
    stats["hub_written"] = True
    logger.info("Wrote resource hub: %s", hub_path)

    return stats


# ── D3.js HTML Export ────────────────────────────────────────────────────


def export_d3_html(graph_data: dict, output_path: Optional[str] = None) -> str:
    nodes_json = json.dumps(
        [
            {
                "id": n["id"],
                "title": n["title"][:40],
                "type": n["type"],
                "domain": n["domain"],
                "quality": n.get("quality_score", 0),
                "state": n.get("consumption_state", "saved"),
            }
            for n in graph_data["nodes"]
        ]
    )

    edges_json = json.dumps(
        [
            {"source": e["source"], "target": e["target"], "weight": e["weight"]}
            for e in graph_data["edges"]
        ]
    )

    domain_colors = {
        "web": "#e74c3c",
        "network": "#3498db",
        "cloud": "#2ecc71",
        "general": "#95a5a6",
        "mobile": "#9b59b6",
        "iot": "#1abc9c",
        "osint": "#f39c12",
        "re": "#e67e22",
        "crypto": "#34495e",
        "social": "#e91e63",
    }
    domain_colors_json = json.dumps(domain_colors)
    node_count = graph_data["node_count"]
    edge_count = graph_data["edge_count"]

    html = _D3_TEMPLATE.replace("__NODES_JSON__", nodes_json)
    html = html.replace("__EDGES_JSON__", edges_json)
    html = html.replace("__DOMAIN_COLORS__", domain_colors_json)
    html = html.replace("__NODE_COUNT__", str(node_count))
    html = html.replace("__EDGE_COUNT__", str(edge_count))

    if output_path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html, encoding="utf-8")
        logger.info("Wrote D3 graph: %s", path)

    return html


_D3_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>poolmind - Resource Graph</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; overflow: hidden; }
#graph { width: 100vw; height: 100vh; }
.node circle { stroke: #fff; stroke-width: 1.5px; cursor: pointer; }
.node text { fill: #ccc; font-size: 10px; pointer-events: none; text-shadow: 0 1px 2px rgba(0,0,0,0.8); }
.link { stroke: #555; stroke-opacity: 0.4; }
.link:hover { stroke-opacity: 0.8; }
.tooltip { position: absolute; background: rgba(0,0,0,0.85); color: #fff; padding: 8px 12px; border-radius: 6px; font-size: 13px; pointer-events: none; display: none; max-width: 300px; line-height: 1.4; border: 1px solid #444; }
#legend { position: absolute; bottom: 20px; left: 20px; background: rgba(0,0,0,0.7); padding: 12px 16px; border-radius: 8px; font-size: 12px; line-height: 1.8; }
#legend .swatch { display: inline-block; width: 12px; height: 12px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
#title { position: absolute; top: 20px; left: 20px; font-size: 18px; font-weight: bold; color: #fff; background: rgba(0,0,0,0.6); padding: 8px 16px; border-radius: 8px; }
#stats { position: absolute; top: 20px; right: 20px; font-size: 12px; color: #888; background: rgba(0,0,0,0.6); padding: 8px 16px; border-radius: 8px; }
</style>
</head>
<body>
<div id="title">poolmind - Resource Graph</div>
<div id="stats">__NODE_COUNT__ nodes | __EDGE_COUNT__ edges</div>
<div id="legend"></div>
<div class="tooltip" id="tooltip"></div>
<svg id="graph"></svg>
<script>
const nodes = __NODES_JSON__;
const edges = __EDGES_JSON__;

const domainColors = __DOMAIN_COLORS__;

const color = d => domainColors[d.domain] || "#95a5a6";
const size = d => Math.max(5, Math.min(20, 3 + (d.quality || 0) * 1.5));

const width = window.innerWidth;
const height = window.innerHeight;

const svg = d3.select("#graph")
    .attr("width", width)
    .attr("height", height);

const defs = svg.append("defs");
defs.append("marker")
    .attr("id", "arrow")
    .attr("viewBox", "0 -5 10 10")
    .attr("refX", 20)
    .attr("refY", 0)
    .attr("markerWidth", 6)
    .attr("markerHeight", 6)
    .attr("orient", "auto")
    .append("path")
    .attr("d", "M0,-5L10,0L0,5")
    .attr("fill", "#555");

const simulation = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(edges).id(d => d.id).distance(100))
    .force("charge", d3.forceManyBody().strength(-200))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collision", d3.forceCollide().radius(d => size(d) + 10));

const link = svg.append("g")
    .selectAll("line")
    .data(edges)
    .join("line")
    .attr("class", "link")
    .attr("stroke-width", d => Math.max(0.5, d.weight))
    .attr("marker-end", "url(#arrow)");

const node = svg.append("g")
    .selectAll("g")
    .data(nodes)
    .join("g")
    .attr("class", "node")
    .call(d3.drag()
        .on("start", (event, d) => { if (!event.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
        .on("drag", (event, d) => { d.fx = event.x; d.fy = event.y; })
        .on("end", (event, d) => { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; })
    );

node.append("circle")
    .attr("r", d => size(d))
    .attr("fill", d => color(d))
    .on("mouseover", (event, d) => {
        const tip = document.getElementById("tooltip");
        tip.innerHTML = `<b>${d.title}</b><br>Type: ${d.type} | Domain: ${d.domain}<br>Quality: ${d.quality || 'N/A'} | State: ${d.state}<br>ID: ${d.id}`;
        tip.style.display = "block";
        tip.style.left = (event.pageX + 15) + "px";
        tip.style.top = (event.pageY - 10) + "px";
    })
    .on("mousemove", (event) => {
        const tip = document.getElementById("tooltip");
        tip.style.left = (event.pageX + 15) + "px";
        tip.style.top = (event.pageY - 10) + "px";
    })
    .on("mouseout", () => { document.getElementById("tooltip").style.display = "none"; });

node.append("text")
    .text(d => d.title.length > 20 ? d.title.slice(0, 18) + "..." : d.title)
    .attr("dx", d => size(d) + 5)
    .attr("dy", 4);

simulation.on("tick", () => {
    link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
    node.attr("transform", d => `translate(${d.x},${d.y})`);
});

const legendDomains = [...new Set(nodes.map(n => n.domain))].sort();
const legend = document.getElementById("legend");
legend.innerHTML = "<b>Domains</b><br>" + legendDomains.map(d =>
    `<span class="swatch" style="background:${domainColors[d]}"></span>${d}`
).join("<br>");
</script>
</body>
</html>"""
