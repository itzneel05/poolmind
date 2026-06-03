"""
Obsidian vault writer for poolmind.
Writes one markdown note per resource with full YAML frontmatter.
"""

import logging
import os
import re
from pathlib import Path
from typing import Optional

from models.resource import Resource

logger = logging.getLogger(__name__)


def get_vault_path() -> Path:
    raw = os.getenv("OBSIDIAN_VAULT_PATH", "vault")
    return Path(raw)


def get_resource_folder() -> Path:
    return get_vault_path() / "Resources"


def slug(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:60]


def note_filename(resource: Resource) -> str:
    return f"resource-{resource.id}-{slug(resource.title)}.md"


def write_note(resource: Resource) -> Path:
    folder = get_resource_folder()
    folder.mkdir(parents=True, exist_ok=True)

    filepath = folder / note_filename(resource)
    content = _render_note(resource)

    filepath.write_text(content, encoding="utf-8")
    logger.info("Wrote Obsidian note: %s", filepath)
    return filepath


def delete_note(resource: Resource) -> bool:
    filepath = get_resource_folder() / note_filename(resource)
    if filepath.exists():
        filepath.unlink()
        return True
    return False


def delete_note_by_id(resource_id: str) -> bool:
    """Delete an Obsidian note by resource ID (searches Resources/ and Trash/)."""
    for folder in (get_resource_folder(), get_trash_folder()):
        if not folder.exists():
            continue
        for f in folder.iterdir():
            if f.is_file() and f.name.startswith(f"resource-{resource_id}-"):
                f.unlink()
                logger.info("Deleted Obsidian note: %s", f.name)
                return True
    return False


def get_trash_folder() -> Path:
    return get_vault_path() / "Trash"


def move_note_to_trash(resource_id: str) -> bool:
    """Move a resource note from Resources/ to Trash/."""
    src_folder = get_resource_folder()
    dst_folder = get_trash_folder()
    dst_folder.mkdir(parents=True, exist_ok=True)
    for f in src_folder.iterdir():
        if f.is_file() and f.name.startswith(f"resource-{resource_id}-"):
            dst_path = dst_folder / f.name
            f.rename(dst_path)
            logger.info("Moved Obsidian note to Trash: %s", f.name)
            return True
    return False


def restore_note_from_trash(resource_id: str) -> bool:
    """Move a resource note from Trash/ back to Resources/."""
    src_folder = get_trash_folder()
    dst_folder = get_resource_folder()
    dst_folder.mkdir(parents=True, exist_ok=True)
    if not src_folder.exists():
        return False
    for f in src_folder.iterdir():
        if f.is_file() and f.name.startswith(f"resource-{resource_id}-"):
            dst_path = dst_folder / f.name
            f.rename(dst_path)
            logger.info("Restored Obsidian note from Trash: %s", f.name)
            return True
    return False


def _render_note(resource: Resource) -> str:
    tags_yaml = (
        "\n".join(f"  - {t}" for t in resource.tags) if resource.tags else "  []"
    )
    prereqs_yaml = (
        "\n".join(f"  - {p}" for p in resource.prerequisites)
        if resource.prerequisites
        else "  []"
    )
    mirrors_yaml = (
        "\n".join(f"  - {m}" for m in resource.mirror_urls)
        if resource.mirror_urls
        else "  []"
    )
    related_yaml = (
        "\n".join(f"  - {r}" for r in resource.related_resources)
        if resource.related_resources
        else "  []"
    )

    maintained_str = (
        str(resource.is_still_maintained).lower()
        if resource.is_still_maintained is not None
        else "null"
    )
    learning_path_str = str(resource.learning_path) if resource.learning_path else ""
    year_published_str = str(resource.year_published) if resource.year_published else ""
    last_verified_str = (
        str(resource.last_verified_alive) if resource.last_verified_alive else ""
    )
    last_updated_str = (
        str(resource.last_updated_by_author) if resource.last_updated_by_author else ""
    )
    quality_str = str(resource.quality_score) if resource.quality_score else ""
    personal_str = str(resource.personal_rating) if resource.personal_rating else ""
    last_used_str = str(resource.last_used) if resource.last_used else ""
    ai_conf_str = str(resource.ai_confidence) if resource.ai_confidence else ""
    next_step_str = (
        str(resource.next_step_resource) if resource.next_step_resource else ""
    )

    frontmatter = f"""---
id: {resource.id}
title: "{_escape_yaml(resource.title)}"
type: {resource.type}
url: "{resource.url}"
mirror_urls:
{mirrors_yaml}
author: "{resource.author or ""}"
source_platform: {resource.source_platform}

domain: {resource.domain}
subdomain: {resource.subdomain or ""}
tags:
{tags_yaml}

skill_level: {resource.skill_level}
prerequisites:
{prereqs_yaml}
time_to_value: {resource.time_to_value}
format: {resource.format}
learning_path: {learning_path_str}

cost: {resource.cost}
language: {resource.language}
year_published: {year_published_str}
last_verified_alive: {last_verified_str}
last_updated_by_author: {last_updated_str}
is_still_maintained: {maintained_str}

quality_score: {quality_str}
personal_rating: {personal_str}
times_used: {resource.times_used}
last_used: {last_used_str}
consumption_state: {resource.consumption_state}
temporal_relevance: {resource.temporal_relevance}

related_resources:
{related_yaml}
next_step_resource: {next_step_str}

added_by: {resource.added_by}
added_on: {resource.added_on}
ai_confidence: {ai_conf_str}
ai_enriched: {str(resource.ai_enriched).lower()}
schema_version: {resource.schema_version}
---"""

    type_emoji = _type_emoji(resource.type)
    quality_str_display = (
        f"{resource.quality_score}/10" if resource.quality_score else "Not scored"
    )

    body = f"""
# {type_emoji} {resource.title}

> **{resource.domain.upper()}** | {resource.type} | {resource.skill_level} | {resource.time_to_value} | {resource.cost}

## Links
- **Primary**: [{resource.url}]({resource.url})"""

    if resource.mirror_urls:
        for m in resource.mirror_urls:
            body += f"\n- **Mirror**: [{m}]({m})"

    body += f"""

## Summary
{resource.summary or "_No summary yet._"}

## Why It Matters
{resource.why_it_matters or "_Not specified._"}

## Best For
{resource.best_for or "_Not specified._"}

## Avoid If
{resource.avoid_if or "_Not specified._"}

## Quality
- **Score**: {quality_str_display}
- **Personal Rating**: {resource.personal_rating or "Not rated"}
- **AI Confidence**: {resource.ai_confidence or "N/A"}%
- **Temporal Relevance**: {resource.temporal_relevance}
- **Maintained**: {maintained_str}

## Learning Context
- **Skill Level**: {resource.skill_level}
- **Prerequisites**: {", ".join(resource.prerequisites) if resource.prerequisites else "None listed"}
- **Learning Path**: {learning_path_str or "Not assigned"}
- **Next Step**: {next_step_str or "Not linked"}

## Notes
{resource.notes or "_No notes yet._"}

## Tags
{" ".join("#" + t for t in resource.tags) if resource.tags else "_No tags._"}

---
*Added: {resource.added_on} | Source: {resource.source_platform} | ID: `{resource.id}`*
"""

    dataview_block = """
## Related (Same Domain)
```dataview
TABLE domain, skill_level, quality_score, consumption_state
FROM "Resources"
WHERE domain = this.domain
SORT quality_score DESC
LIMIT 5
```
"""

    return frontmatter + body + dataview_block


def _escape_yaml(text: str) -> str:
    return text.replace('"', '\\"').replace("\n", " ")


def _type_emoji(type_: str) -> str:
    emoji_map = {
        "article": "📄",
        "tutorial": "📚",
        "writeup": "✍️",
        "tool": "🔧",
        "repository": "📦",
        "cheatsheet": "📋",
        "book": "📕",
        "course": "🎓",
        "video": "🎬",
        "playlist": "▶️",
        "paper": "🔬",
        "report": "📊",
        "dataset": "🗃️",
        "lab": "🧪",
        "ctf": "🏁",
        "framework": "🏗️",
        "table": "📐",
        "index": "🗂️",
        "ranking": "🏆",
        "note": "📝",
        "thread": "🧵",
        "newsletter": "📨",
        "podcast": "🎙️",
        "interview": "🎤",
        "config": "⚙️",
        "template": "📄",
        "extension": "🧩",
        "dashboard": "📈",
        "search_engine": "🔍",
        "api": "🔌",
        "community": "👥",
        "event": "📅",
        "certification": "🎯",
        "glossary": "📖",
        "mindmap": "🗺️",
        "other": "📎",
    }
    return emoji_map.get(type_, "📎")
