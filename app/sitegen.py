"""
Static site generator for poolmind.
Generates a self-contained HTML file (or directory) with all resources.
"""

import logging
from datetime import date
from pathlib import Path
from typing import Optional

from app import db
from app.search import get_recent, get_random

logger = logging.getLogger(__name__)


def generate_site(output_path: str = "poolmind-site.html") -> dict:
    resources = db.get_all_resources(limit=500)
    stats = db.get_pool_stats()
    recent = get_recent(limit=5)
    rand = get_random(1)

    today = date.today().isoformat()
    random_resource = rand[0] if rand else None

    rows_html = ""
    for r in resources:
        tags_html = (
            " ".join(f"<span class='tag'>{t}</span>" for t in r.tags[:8])
            if r.tags
            else ""
        )
        summary = (r.summary or "")[:200]
        rows_html += f"""
        <div class="resource-card">
            <div class="card-header">
                <span class="type-badge type-{r.type}">{r.type}</span>
                <span class="domain-tag">{r.domain}</span>
                <span class="level-tag">{r.skill_level}</span>
            </div>
            <h3><a href="{r.url}" target="_blank">{r.title[:80]}</a></h3>
            <p class="summary">{summary}</p>
            <div class="card-meta">
                <span>Quality: {r.quality_score or "?"}/10</span>
                <span>State: {r.consumption_state}</span>
                <span>Cost: {r.cost}</span>
            </div>
            <div class="tags">{tags_html}</div>
        </div>"""

    domain_rows = ""
    for d in stats["by_domain"]:
        bar_w = max(1, round(d["c"] / max(stats["total"], 1) * 30))
        domain_rows += f"""
        <tr>
            <td>{d["domain"]}</td>
            <td><div class="bar"><div class="bar-fill" style="width:{bar_w}em"></div></div></td>
            <td class="num">{d["c"]}</td>
        </tr>"""

    state_rows = ""
    for s in stats["by_state"]:
        state_rows += (
            f"<tr><td>{s['consumption_state']}</td><td class='num'>{s['c']}</td></tr>"
        )

    recent_html = ""
    for r in recent:
        recent_html += f"<li><a href='{r.url}'>{r.title[:60]}</a> <span class='dim'>({r.type})</span></li>"

    random_html = ""
    if random_resource:
        random_html = f"""
        <div class="random-card">
            <h3>{random_resource.title}</h3>
            <p>{random_resource.summary[:200] if random_resource.summary else ""}</p>
            <p class="dim">{random_resource.domain} | {random_resource.type}</p>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>poolmind - Resource Pool ({today})</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f0f1a; color: #d0d0d0; line-height: 1.6; }}
a {{ color: #58a6ff; }}
.container {{ max-width: 1000px; margin: 0 auto; padding: 2rem 1rem; }}
h1 {{ font-size: 1.8rem; color: #fff; margin-bottom: 0.5rem; }}
h2 {{ font-size: 1.3rem; color: #e0e0e0; margin: 1.5rem 0 1rem; }}
.stats-row {{ display: flex; gap: 1rem; margin: 1.5rem 0; flex-wrap: wrap; }}
.stat {{ background: #1a1a30; border: 1px solid #2a2a4a; border-radius: 8px; padding: 1rem 1.5rem; text-align: center; min-width: 100px; }}
.stat-num {{ display: block; font-size: 1.8rem; font-weight: 700; color: #58a6ff; }}
.stat-label {{ font-size: 0.8rem; color: #8b8ba0; }}
.resource-card {{ background: #1a1a30; border: 1px solid #2a2a4a; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }}
.resource-card h3 {{ margin-bottom: 0.5rem; }}
.summary {{ color: #aaa; font-size: 0.9rem; margin-bottom: 0.5rem; }}
.card-header {{ display: flex; gap: 0.5rem; margin-bottom: 0.5rem; align-items: center; }}
.card-meta {{ display: flex; gap: 1rem; font-size: 0.8rem; color: #6b6b80; margin-bottom: 0.5rem; }}
.tags {{ display: flex; flex-wrap: wrap; gap: 0.3rem; }}
.tag {{ background: #222240; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem; color: #8b8ba0; }}
.type-badge {{ font-size: 0.7rem; padding: 2px 8px; border-radius: 4px; font-weight: 600; text-transform: uppercase; }}
.type-article {{ background: #1a3a5a; color: #58a6ff; }}
.type-repository {{ background: #2a3a2a; color: #3fb950; }}
.type-book {{ background: #3a2a3a; color: #d2a8ff; }}
.type-writeup {{ background: #3a2a1a; color: #f0883e; }}
.domain-tag, .level-tag {{ font-size: 0.7rem; padding: 2px 8px; border-radius: 4px; background: #222240; color: #8b8ba0; }}
.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }}
@media (max-width: 768px) {{ .two-col {{ grid-template-columns: 1fr; }} }}
.card {{ background: #1a1a30; border: 1px solid #2a2a4a; border-radius: 8px; padding: 1rem; }}
table {{ width: 100%; border-collapse: collapse; }}
td {{ padding: 6px 8px; border-bottom: 1px solid #222240; font-size: 0.9rem; }}
.num {{ text-align: right; color: #8b8ba0; }}
.bar {{ background: #222240; border-radius: 4px; height: 1rem; }}
.bar-fill {{ background: #58a6ff; border-radius: 4px; height: 1rem; }}
.dim {{ color: #6b6b80; }}
.random-card {{ background: linear-gradient(135deg, #1a1a30, #1a2a3a); border: 1px solid #2a4a5a; border-radius: 8px; padding: 1.25rem; }}
.random-card h3 {{ color: #58a6ff; }}
.footer {{ margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #222240; font-size: 0.8rem; color: #6b6b80; text-align: center; }}
ul {{ list-style: none; }}
li {{ padding: 4px 0; }}
</style>
</head>
<body>
<div class="container">
    <h1>poolmind</h1>
    <p class="dim">Cybersecurity Resource Pool &mdash; Generated {today}</p>

    <div class="stats-row">
        <div class="stat"><span class="stat-num">{stats["total"]}</span><span class="stat-label">Resources</span></div>
        <div class="stat"><span class="stat-num">{len(stats["by_domain"])}</span><span class="stat-label">Domains</span></div>
        <div class="stat"><span class="stat-num">{stats["dead_links"]}</span><span class="stat-label">Dead Links</span></div>
        <div class="stat"><span class="stat-num">{stats["low_confidence"]}</span><span class="stat-label">Low Confidence</span></div>
    </div>

    {"<h2>Random Pick</h2>" + random_html if random_html else ""}

    <div class="two-col">
        <div class="card">
            <h2>By Domain</h2>
            <table>{domain_rows}</table>
        </div>
        <div class="card">
            <h2>By State</h2>
            <table>{state_rows}</table>
        </div>
    </div>

    <h2>Recent Additions</h2>
    <ul>{recent_html}</ul>

    <h2>All Resources ({len(resources)})</h2>
    {rows_html}

    <div class="footer">
        Generated by poolmind | {len(resources)} resources | {today}
    </div>
</div>
</body>
</html>"""

    path = Path(output_path)
    path.write_text(html, encoding="utf-8")
    logger.info("Wrote static site: %s (%d resources)", path, len(resources))
    return {"path": str(path), "resources": len(resources)}
