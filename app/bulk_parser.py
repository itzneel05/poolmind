"""
Smart bulk input parser for poolmind.

Handles mixed input formats:
- Pure URLs
- Title - URL pairs (various separators)
- Markdown links [Title](URL)
- Notion share links
- Title-only entries (no URL)
- Free text with embedded URLs
- List items with descriptions
- Comments (#) and section headers (==, --)

Produces a list of ParsedEntry objects ready for ingestion.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(
    r"https?://"
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
    r"localhost|"
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    r"(?::\d+)?"
    r"(?:[/?]\S*|/?)",
    re.IGNORECASE,
)

TITLE_URL_SEPARATORS = [
    r"\s+-\s+",
    r"\s+\|\s+",
    r"\s+→\s+",
    r"\s*//\s+",
]

SKIP_PATTERNS = [
    r"^\s*$",
    r"^\s*#{1,6}\s",
    r"^\s*={3,}",
    r"^\s*-{3,}",
    r"^\s*\*{3,}",
    r"^\s*#",
    r"^\s*<!--",
    r"^\s*>\s",
]

NOTION_URL_PATTERN = re.compile(
    r'https?://(?:www\.)?notion\.so/[^\s)"\'>]+', re.IGNORECASE
)


@dataclass
class ParsedEntry:
    raw_line: str
    entry_type: str
    url: Optional[str] = None
    title: Optional[str] = None
    notes: Optional[str] = None
    confidence: float = 1.0
    line_number: int = 0
    extra_urls: List[str] = field(default_factory=list)


def parse_bulk_input(text: str) -> List[ParsedEntry]:
    lines = text.splitlines()
    entries: List[ParsedEntry] = []
    seen_urls: set = set()

    i = 0
    while i < len(lines):
        line = lines[i]
        line_number = i + 1
        i += 1

        if _should_skip(line):
            continue

        lookahead = None
        if not URL_PATTERN.search(line) and i < len(lines):
            next_line = lines[i].strip()
            if URL_PATTERN.search(next_line) and not _should_skip(next_line):
                lookahead = next_line
                i += 1

        entry = _parse_line(line.strip(), line_number, lookahead=lookahead)
        if entry is None:
            continue

        if entry.url:
            normalized = _normalize_url_simple(entry.url)
            if normalized in seen_urls:
                logger.debug("Skipping duplicate URL: %s", entry.url)
                continue
            seen_urls.add(normalized)

        entries.append(entry)

    logger.info("Parsed %d entries from %d lines", len(entries), len(lines))
    return entries


def parse_bulk_file(path: str) -> List[ParsedEntry]:
    content = Path(path).read_text(encoding="utf-8", errors="replace")
    return parse_bulk_input(content)


def _parse_line(
    line: str,
    line_number: int,
    lookahead: Optional[str] = None,
) -> Optional[ParsedEntry]:
    if not line.strip():
        return None

    cleaned = re.sub(r"^[\-\*•]\s+", "", line)
    cleaned = re.sub(r"^\d+\.\s+", "", cleaned)
    cleaned = cleaned.strip()

    # Pattern 1: Markdown link [Title](URL)
    md_match = re.match(r"^\[(.+?)\]\((https?://[^\s)]+)\)", cleaned)
    if md_match:
        title = md_match.group(1).strip()
        url = md_match.group(2).strip()
        rest = cleaned[md_match.end() :].strip().lstrip("-").strip()
        return ParsedEntry(
            raw_line=line,
            entry_type="markdown_link",
            url=url,
            title=title,
            notes=rest or None,
            confidence=0.99,
            line_number=line_number,
        )

    # Pattern 2: Notion share URL
    notion_match = NOTION_URL_PATTERN.search(cleaned)
    if notion_match:
        url = notion_match.group(0)
        before = cleaned[: notion_match.start()].strip()
        title = _clean_title_fragment(before) if before else _title_from_notion_url(url)
        return ParsedEntry(
            raw_line=line,
            entry_type="notion_page",
            url=url,
            title=title,
            confidence=0.95,
            line_number=line_number,
        )

    # Pattern 3: Title - URL pairs
    for sep in TITLE_URL_SEPARATORS:
        sep_match = re.search(sep, cleaned)
        if sep_match:
            before_sep = cleaned[: sep_match.start()].strip()
            after_sep = cleaned[sep_match.end() :].strip()
            url_match = URL_PATTERN.match(after_sep)
            if url_match and before_sep:
                url = url_match.group(0)
                title = _clean_title_fragment(before_sep)
                rest = after_sep[url_match.end() :].strip().lstrip("-").strip()
                return ParsedEntry(
                    raw_line=line,
                    entry_type="title_url_pair",
                    url=url,
                    title=title,
                    notes=rest or None,
                    confidence=0.92,
                    line_number=line_number,
                )

    # Pattern 4: URL at start of line
    url_start_match = URL_PATTERN.match(cleaned)
    if url_start_match:
        url = url_start_match.group(0)
        rest = cleaned[url_start_match.end() :].strip().lstrip("-").strip()
        title = _clean_title_fragment(rest) if rest else None
        return ParsedEntry(
            raw_line=line,
            entry_type="url_only",
            url=url,
            title=title,
            confidence=0.95,
            line_number=line_number,
        )

    # Pattern 5: URL anywhere in line
    all_urls = URL_PATTERN.findall(cleaned)
    if all_urls:
        primary_url = all_urls[0]
        extra_urls = all_urls[1:] if len(all_urls) > 1 else []
        text_without_urls = URL_PATTERN.sub("", cleaned).strip()
        text_without_urls = re.sub(r"\s+", " ", text_without_urls).strip()
        text_without_urls = text_without_urls.strip("|-—").strip()
        title = _clean_title_fragment(text_without_urls) if text_without_urls else None
        return ParsedEntry(
            raw_line=line,
            entry_type="text_with_links",
            url=primary_url,
            title=title,
            confidence=0.80,
            line_number=line_number,
            extra_urls=extra_urls,
        )

    # Pattern 6: Lookahead - title on this line, URL on next
    if lookahead:
        url_match = URL_PATTERN.match(lookahead.strip())
        if url_match:
            url = url_match.group(0)
            title = _clean_title_fragment(cleaned)
            return ParsedEntry(
                raw_line=line,
                entry_type="title_url_pair",
                url=url,
                title=title,
                confidence=0.85,
                line_number=line_number,
            )

    # Pattern 7: Title only
    if len(cleaned) > 3 and not cleaned.startswith("http"):
        title = _clean_title_fragment(cleaned)
        if title:
            return ParsedEntry(
                raw_line=line,
                entry_type="title_only",
                url=None,
                title=title,
                confidence=0.60,
                line_number=line_number,
            )

    return None


def _should_skip(line: str) -> bool:
    for pattern in SKIP_PATTERNS:
        if re.match(pattern, line):
            return True
    return False


def _clean_title_fragment(text: str) -> Optional[str]:
    if not text:
        return None
    text = text.strip("\"'[](){}")
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip("|-—:,.")
    noise_prefixes = ["resource:", "link:", "url:", "ref:", "source:"]
    for prefix in noise_prefixes:
        if text.lower().startswith(prefix):
            text = text[len(prefix) :].strip()
    if len(text) < 3:
        return None
    return text


def _title_from_notion_url(url: str) -> str:
    path = urlparse(url).path
    parts = [p for p in path.split("/") if p]
    if not parts:
        return "Notion Page"
    last = parts[-1]
    slug = re.sub(r"-[a-f0-9]{32}$", "", last)
    slug = re.sub(r"-[a-f0-9]{8,}$", "", slug)
    if slug:
        return slug.replace("-", " ").title()
    return "Notion Page"


def _normalize_url_simple(url: str) -> str:
    url = url.lower().rstrip("/")
    url = re.sub(r"\?utm_[^&]*(&|$)", "?", url)
    url = re.sub(r"\?$", "", url)
    return url


def summarize_parse_results(entries: List[ParsedEntry]) -> dict:
    by_type = {}
    for e in entries:
        by_type[e.entry_type] = by_type.get(e.entry_type, 0) + 1
    has_url = sum(1 for e in entries if e.url)
    no_url = sum(1 for e in entries if not e.url)
    low_conf = sum(1 for e in entries if e.confidence < 0.7)
    return {
        "total": len(entries),
        "has_url": has_url,
        "title_only": no_url,
        "low_confidence": low_conf,
        "by_type": by_type,
    }
