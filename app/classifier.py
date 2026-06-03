"""
Heuristic-first resource classifier.
Rules run BEFORE any AI call.
AI is called only when confidence < threshold.
"""

import logging
import os
import re
from pathlib import Path
from typing import Tuple
from urllib.parse import urlparse

import yaml

logger = logging.getLogger(__name__)

_TAXONOMY: dict = {}


def _load_taxonomy() -> dict:
    global _TAXONOMY
    if not _TAXONOMY:
        taxonomy_path = Path("config/taxonomy.yaml")
        with open(taxonomy_path) as f:
            _TAXONOMY = yaml.safe_load(f)
    return _TAXONOMY


def classify(
    url: str, title: str = "", body_text: str = "", extracted: dict = None
) -> dict:
    taxonomy = _load_taxonomy()
    extracted = extracted or {}
    notes = []

    result = {
        "type": extracted.get("type", "article"),
        "domain": "general",
        "subdomain": None,
        "skill_level": "intermediate",
        "format": extracted.get("format", "text"),
        "source_platform": extracted.get("source_platform", "other"),
        "temporal_relevance": "evergreen",
        "confidence": 0,
        "heuristic_notes": [],
    }

    confidence_points = 0

    url_lower = url.lower()
    parsed_parts = urlparse(url)
    host = parsed_parts.netloc.lower().replace("www.", "")
    path_lower = parsed_parts.path.lower()

    url_patterns = taxonomy.get("url_patterns", {})
    for pattern, meta in url_patterns.items():
        if pattern in url_lower:
            result["type"] = meta.get("type", result["type"])
            result["source_platform"] = meta.get("platform", result["source_platform"])
            confidence_points += 25
            notes.append(f"URL matched pattern: {pattern}")
            break

    platform = result["source_platform"]
    platform_type_map = {
        "youtube": "video",
        "github": "repository",
        "arxiv": "paper",
        "hackerone": "writeup",
        "bugcrowd": "writeup",
        "tryhackme": "lab",
        "hackthebox": "lab",
        "portswigger": "tutorial",
        "reddit": "community",
        "twitter": "thread",
        "substack": "newsletter",
    }
    if platform in platform_type_map:
        result["type"] = platform_type_map[platform]
        confidence_points += 15
        notes.append(f"Platform override: {platform} -> {result['type']}")

    type_format_map = {
        "video": "video",
        "podcast": "audio",
        "lab": "hands-on",
        "course": "mixed",
        "tutorial": "mixed",
        "repository": "tool",
        "tool": "tool",
    }
    if result["type"] in type_format_map:
        result["format"] = type_format_map[result["type"]]

    combined_text = f"{url_lower} {title.lower()} {body_text[:500].lower()}"
    domain_keywords = taxonomy.get("domain_keywords", {})

    domain_scores: dict[str, int] = {}
    for domain, keywords in domain_keywords.items():
        score = sum(1 for kw in keywords if kw in combined_text)
        if score > 0:
            domain_scores[domain] = score

    if domain_scores:
        best_domain = max(domain_scores, key=lambda d: domain_scores[d])
        result["domain"] = best_domain
        confidence_points += min(20, domain_scores[best_domain] * 5)
        notes.append(f"Domain matched: {best_domain}")

    subdomain_keywords = {
        "xss": ["xss", "cross-site scripting"],
        "sqli": ["sqli", "sql injection", "sqlmap"],
        "ssrf": ["ssrf", "server-side request forgery"],
        "idor": ["idor", "insecure direct object"],
        "csrf": ["csrf", "cross-site request forgery"],
        "xxe": ["xxe", "xml external entity"],
        "lfi": ["lfi", "local file inclusion"],
        "rfi": ["rfi", "remote file inclusion"],
        "oauth": ["oauth", "oidc", "openid connect"],
        "jwt": ["jwt", "json web token"],
        "buffer_overflow": ["buffer overflow", "bof", "stack overflow"],
        "rop": ["rop", "return oriented programming"],
        "heap": ["heap exploit", "heap spray", "use after free"],
        "aws": ["aws", "amazon web services", "s3 bucket", "iam role"],
        "kubernetes": ["kubernetes", "k8s", "kubectl", "pod"],
        "prompt_injection": ["prompt injection", "jailbreak", "llm attack"],
        "phishing": ["phishing", "spear phishing", "pretexting"],
        "log4j": ["log4j", "log4shell"],
    }
    for sub, keywords in subdomain_keywords.items():
        if any(kw in combined_text for kw in keywords):
            result["subdomain"] = sub
            confidence_points += 10
            notes.append(f"Subdomain detected: {sub}")
            break

    beginner_signals = [
        "beginner",
        "introduction to",
        "intro to",
        "basics",
        "101",
        "for beginners",
        "getting started",
        "what is",
    ]
    advanced_signals = [
        "advanced",
        "deep dive",
        "internals",
        "exploit development",
        "zero day",
        "0day",
        "research",
        "thesis",
    ]
    expert_signals = [
        "cve-",
        "poc",
        "proof of concept",
        "exploit chain",
        "novel technique",
    ]

    title_lower = title.lower()
    if any(s in title_lower or s in combined_text[:200] for s in expert_signals):
        result["skill_level"] = "expert"
        confidence_points += 5
    elif any(s in title_lower or s in combined_text[:200] for s in advanced_signals):
        result["skill_level"] = "advanced"
        confidence_points += 5
    elif any(s in title_lower or s in combined_text[:200] for s in beginner_signals):
        result["skill_level"] = "beginner"
        confidence_points += 5

    temporal_signals = {
        "emerging": [
            "2024",
            "2025",
            "new attack",
            "newly discovered",
            "recent",
            "emerging",
        ],
        "time-sensitive": [
            "patch now",
            "urgent",
            "critical vulnerability",
            "actively exploited",
        ],
        "historical": [
            "2019",
            "2018",
            "2017",
            "2016",
            "classic",
            "historical",
            "legacy",
        ],
    }
    for relevance, signals in temporal_signals.items():
        if any(s in combined_text for s in signals):
            result["temporal_relevance"] = relevance
            notes.append(f"Temporal: {relevance}")
            break

    result["confidence"] = min(confidence_points, 95)
    result["heuristic_notes"] = notes

    return result


def needs_ai_enrichment(classification: dict, threshold: int = None) -> bool:
    if threshold is None:
        threshold = int(os.getenv("AI_CONFIDENCE_THRESHOLD", "70"))
    return classification["confidence"] < threshold
