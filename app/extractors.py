"""
Metadata extractors for different resource types.
Each extractor takes a URL and returns a partial dict
that will be merged into a Resource model.
"""

import logging
import re
from typing import Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; poolmind/1.0; +https://github.com/you/poolmind)"
    )
}
TIMEOUT = 15


# ── Dispatcher ────────────────────────────────────────────────────────────


def extract_metadata(url: str) -> dict:
    parsed = urlparse(url)
    host = parsed.netloc.lower().replace("www.", "")

    try:
        if "github.com" in host:
            return extract_github(url)
        elif "youtube.com" in host or "youtu.be" in host:
            return extract_youtube(url)
        elif url.lower().endswith(".pdf") or "pdf" in url.lower():
            return extract_pdf(url)
        elif "hackerone.com/reports" in url:
            return extract_hackerone(url)
        elif "bugcrowd.com" in host:
            return extract_bugcrowd(url)
        else:
            return extract_article(url)
    except Exception as e:
        logger.warning("Extraction failed for %s: %s", url, e)
        return {"url": url, "_extraction_failed": True}


# ── Generic Article Extractor ─────────────────────────────────────────────


def extract_article(url: str) -> dict:
    try:
        from readability import Document
        from bs4 import BeautifulSoup

        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()

        doc = Document(resp.text)
        soup = BeautifulSoup(resp.text, "lxml")

        title = doc.title() or _og_tag(soup, "title") or url

        author = (
            _meta_tag(soup, "author")
            or _og_tag(soup, "article:author")
            or _json_ld_field(soup, "author")
        )

        published = (
            _meta_tag(soup, "article:published_time")
            or _meta_tag(soup, "datePublished")
            or _json_ld_field(soup, "datePublished")
        )
        year = _parse_year(published)

        summary = _meta_tag(soup, "description") or _og_tag(soup, "description")
        if summary:
            summary = summary[:500]

        body_html = doc.summary()
        body_soup = BeautifulSoup(body_html, "lxml")
        body_text = body_soup.get_text(separator=" ", strip=True)[:2000]

        return {
            "url": url,
            "title": _clean_title(title),
            "author": author,
            "year_published": year,
            "summary": summary,
            "_body_text": body_text,
            "source_platform": _detect_platform(url),
        }

    except Exception as e:
        logger.warning("Article extraction failed for %s: %s", url, e)
        return {"url": url, "title": _title_from_url(url)}


# ── GitHub Extractor ──────────────────────────────────────────────────────


def extract_github(url: str) -> dict:
    import os

    repo_path = _parse_github_path(url)
    if not repo_path:
        return extract_article(url)

    token = os.getenv("GITHUB_TOKEN")

    try:
        from github import Github

        g = Github(token) if token else Github()
        repo = g.get_repo(repo_path)

        topics = repo.get_topics()
        languages = list(repo.get_languages().keys())[:5]

        last_commit = None
        try:
            commits = repo.get_commits()
            last_commit = commits[0].commit.author.date.isoformat()
        except Exception:
            pass

        return {
            "url": url,
            "title": repo.name,
            "author": repo.owner.login,
            "summary": repo.description or "",
            "year_published": repo.created_at.year,
            "last_updated_by_author": last_commit,
            "is_still_maintained": _repo_is_maintained(last_commit),
            "source_platform": "github",
            "type": "repository",
            "cost": "free",
            "tags": topics[:10] + [lang.lower() for lang in languages[:5]],
            "extended_meta": {
                "stars": repo.stargazers_count,
                "forks": repo.forks_count,
                "language": repo.language,
                "topics": topics,
                "open_issues": repo.open_issues_count,
                "license": repo.license.spdx_id if repo.license else None,
            },
            "_body_text": repo.description or "",
        }

    except Exception as e:
        logger.warning("PyGithub failed for %s, using REST: %s", url, e)

    try:
        api_url = f"https://api.github.com/repos/{repo_path}"
        headers = HEADERS.copy()
        if token:
            headers["Authorization"] = f"token {token}"
        resp = requests.get(api_url, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        return {
            "url": url,
            "title": data.get("name", repo_path),
            "author": data.get("owner", {}).get("login"),
            "summary": data.get("description", ""),
            "year_published": _parse_year(data.get("created_at", "")),
            "last_updated_by_author": data.get("pushed_at"),
            "is_still_maintained": _repo_is_maintained(data.get("pushed_at")),
            "source_platform": "github",
            "type": "repository",
            "cost": "free",
            "extended_meta": {
                "stars": data.get("stargazers_count", 0),
                "forks": data.get("forks_count", 0),
                "language": data.get("language"),
                "license": data.get("license", {}).get("spdx_id")
                if data.get("license")
                else None,
            },
            "_body_text": data.get("description", ""),
        }

    except Exception as e:
        logger.warning("GitHub REST fallback failed for %s: %s", url, e)
        return {
            "url": url,
            "title": repo_path,
            "source_platform": "github",
            "type": "repository",
        }


# ── YouTube Extractor ─────────────────────────────────────────────────────


def extract_youtube(url: str) -> dict:
    try:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        duration_min = int(info.get("duration", 0) / 60)
        time_to_value = _duration_to_ttv(duration_min)

        return {
            "url": url,
            "title": info.get("title", ""),
            "author": info.get("uploader") or info.get("channel"),
            "summary": (info.get("description") or "")[:500],
            "year_published": _parse_year(str(info.get("upload_date", ""))),
            "source_platform": "youtube",
            "type": "video",
            "format": "video",
            "cost": "free",
            "time_to_value": time_to_value,
            "extended_meta": {
                "duration_minutes": duration_min,
                "view_count": info.get("view_count"),
                "like_count": info.get("like_count"),
                "channel_id": info.get("channel_id"),
                "tags": info.get("tags", [])[:10],
            },
            "_body_text": (info.get("description") or "")[:2000],
        }

    except Exception as e:
        logger.warning("YouTube extraction failed for %s: %s", url, e)
        return {
            "url": url,
            "source_platform": "youtube",
            "type": "video",
            "format": "video",
        }


# ── PDF Extractor ─────────────────────────────────────────────────────────


def extract_pdf(url: str) -> dict:
    try:
        import io
        import pymupdf

        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()

        doc = pymupdf.open(stream=io.BytesIO(resp.content), filetype="pdf")
        meta = doc.metadata

        text = ""
        for page in doc[:3]:
            text += page.get_text()
            if len(text) > 2000:
                break

        return {
            "url": url,
            "title": meta.get("title") or _title_from_url(url),
            "author": meta.get("author"),
            "year_published": _parse_year(meta.get("creationDate", "")),
            "format": "text",
            "type": "paper",
            "source_platform": "pdf",
            "_body_text": text[:2000],
        }

    except Exception as e:
        logger.warning("PDF extraction failed for %s: %s", url, e)
        return {"url": url, "type": "paper", "source_platform": "pdf"}


# ── HackerOne Writeup Extractor ───────────────────────────────────────────


def extract_hackerone(url: str) -> dict:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "lxml")

        title_tag = soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else _title_from_url(url)

        bounty_text = None
        for span in soup.find_all("span"):
            text = span.get_text(strip=True)
            if "$" in text and any(c.isdigit() for c in text):
                bounty_text = text
                break

        body = soup.get_text(separator=" ", strip=True)

        vuln_type = None
        vuln_keywords = [
            "xss",
            "csrf",
            "ssrf",
            "sqli",
            "idor",
            "xxe",
            "rce",
            "buffer overflow",
            "privilege escalation",
            "information disclosure",
            "subdomain takeover",
            "open redirect",
            "authentication bypass",
        ]
        body_lower = body.lower()
        for kw in vuln_keywords:
            if kw in body_lower:
                vuln_type = kw
                break

        return {
            "url": url,
            "title": title,
            "type": "writeup",
            "source_platform": "hackerone",
            "domain": "web",
            "cost": "free",
            "format": "text",
            "extended_meta": {
                "bounty_amount_text": bounty_text,
                "platform": "hackerone",
                "vulnerability_type": vuln_type,
            },
            "tags": [vuln_type] if vuln_type else [],
            "_body_text": body[:2000],
        }

    except Exception as e:
        logger.warning("HackerOne extraction failed for %s: %s", url, e)
        return {"url": url, "type": "writeup", "source_platform": "hackerone"}


def extract_bugcrowd(url: str) -> dict:
    """Extract Bugcrowd submission metadata."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(resp.text, "lxml")

        title_tag = soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else _title_from_url(url)

        body = soup.get_text(separator=" ", strip=True)

        return {
            "url": url,
            "title": title,
            "type": "writeup",
            "source_platform": "bugcrowd",
            "domain": "web",
            "cost": "free",
            "format": "text",
            "extended_meta": {
                "platform": "bugcrowd",
            },
            "_body_text": body[:2000],
        }
    except Exception as e:
        logger.warning("Bugcrowd extraction failed for %s: %s", url, e)
        return {"url": url, "type": "writeup", "source_platform": "bugcrowd"}


# ── Helpers ────────────────────────────────────────────────────────────────


def _og_tag(soup, property: str) -> Optional[str]:
    tag = soup.find("meta", property=f"og:{property}")
    if tag:
        return tag.get("content", "").strip()
    tag = soup.find("meta", attrs={"name": f"og:{property}"})
    return tag.get("content", "").strip() if tag else None


def _meta_tag(soup, name: str) -> Optional[str]:
    tag = soup.find("meta", attrs={"name": name}) or soup.find(
        "meta", attrs={"property": name}
    )
    return tag.get("content", "").strip() if tag else None


def _json_ld_field(soup, field: str) -> Optional[str]:
    import json

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                data = data[0]
            val = data.get(field)
            if isinstance(val, dict):
                return val.get("name") or val.get("url")
            return str(val) if val else None
        except Exception:
            pass
    return None


def _parse_year(date_str: str) -> Optional[int]:
    if not date_str:
        return None
    match = re.search(r"(20\d{2}|19\d{2})", str(date_str))
    return int(match.group(1)) if match else None


def _parse_github_path(url: str) -> Optional[str]:
    match = re.match(r"https?://github\.com/([^/]+/[^/]+?)(?:/.*)?$", url)
    return match.group(1) if match else None


def _repo_is_maintained(last_commit_str: Optional[str]) -> Optional[bool]:
    if not last_commit_str:
        return None
    try:
        from datetime import datetime, timezone

        last = datetime.fromisoformat(last_commit_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta_months = (now - last).days / 30
        return delta_months < 12
    except Exception:
        return None


def _duration_to_ttv(minutes: int) -> str:
    if minutes <= 10:
        return "5min"
    elif minutes <= 35:
        return "30min"
    elif minutes <= 130:
        return "2hr"
    elif minutes <= 500:
        return "1day"
    else:
        return "1week+"


def _detect_platform(url: str) -> str:
    url_lower = url.lower()
    platforms = {
        "medium.com": "medium",
        "github.com": "github",
        "youtube.com": "youtube",
        "youtu.be": "youtube",
        "arxiv.org": "arxiv",
        "hackerone.com": "hackerone",
        "bugcrowd.com": "bugcrowd",
        "portswigger.net": "portswigger",
        "tryhackme.com": "tryhackme",
        "hackthebox.com": "hackthebox",
        "reddit.com": "reddit",
        "twitter.com": "twitter",
        "x.com": "twitter",
        "substack.com": "substack",
    }
    for pattern, platform in platforms.items():
        if pattern in url_lower:
            return platform
    return "other"


def _title_from_url(url: str) -> str:
    path = urlparse(url).path
    parts = [p for p in path.split("/") if p]
    if parts:
        last = parts[-1]
        last = re.sub(r"\.[a-z]{2,4}$", "", last)
        last = re.sub(r"[-_]", " ", last)
        return last.title()
    return url


def _clean_title(title: str) -> str:
    suffixes = [
        " - Medium",
        " | Medium",
        " – Medium",
        " - GitHub",
        " | GitHub",
        " - YouTube",
        " | YouTube",
        " - DEV Community",
        " | DEV",
        " | HackerOne",
    ]
    for suffix in suffixes:
        if title.endswith(suffix):
            title = title[: -len(suffix)]
    return title.strip()
