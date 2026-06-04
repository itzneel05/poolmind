"""
URL normalization and resource data normalization.
Cleans and standardizes URLs and field values before DB insert.
"""

import hashlib
import re
from typing import Optional
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl


def normalize_url(url: str) -> str:
    if not url or url == "local":
        return url

    url = re.sub(
        r"https?://youtu\.be/([a-zA-Z0-9_-]+).*",
        r"https://www.youtube.com/watch?v=\1",
        url,
    )

    # Rewrite Medium articles through freedium to bypass paywall
    if (
        re.match(r"https?://([a-zA-Z0-9-]+\.)?medium\.com/", url)
        and "freedium" not in url
    ):
        url = "https://freedium-mirror.cfd/" + url
        return url

    try:
        parsed = urlparse(url)
    except Exception:
        return url

    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()

    STRIP_PARAMS = {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
        "ref",
        "referrer",
        "source",
        "_ga",
    }
    params = parse_qsl(parsed.query, keep_blank_values=False)
    cleaned_params = [(k, v) for k, v in params if k.lower() not in STRIP_PARAMS]
    clean_query = urlencode(cleaned_params)

    path = parsed.path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    normalized = urlunparse((scheme, netloc, path, parsed.params, clean_query, ""))
    return normalized


def get_wayback_url(url: str) -> Optional[str]:
    import requests

    try:
        api = f"https://archive.org/wayback/available?url={url}"
        resp = requests.get(api, timeout=10)
        data = resp.json()
        snapshot = data.get("archived_snapshots", {}).get("closest", {})
        if snapshot.get("available"):
            return snapshot["url"]
    except Exception:
        pass

    return f"https://web.archive.org/web/*/{url}"


def url_to_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def content_to_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def normalize_resource_fields(fields: dict) -> dict:
    for key, val in fields.items():
        if isinstance(val, str):
            fields[key] = val.strip()

    if "url" in fields:
        fields["url"] = normalize_url(fields["url"])

    if "title" in fields:
        fields["title"] = re.sub(r"\s+", " ", fields["title"]).strip()

    if "tags" in fields and isinstance(fields["tags"], str):
        fields["tags"] = [t.strip() for t in fields["tags"].split(",") if t.strip()]

    if "mirror_urls" in fields and isinstance(fields["mirror_urls"], str):
        fields["mirror_urls"] = [
            u.strip() for u in fields["mirror_urls"].split(",") if u.strip()
        ]

    if "year_published" in fields:
        try:
            fields["year_published"] = int(str(fields["year_published"])[:4])
        except (ValueError, TypeError):
            fields["year_published"] = None

    internal_keys = [k for k in fields if k.startswith("_")]
    for key in internal_keys:
        fields.pop(key)

    return fields
