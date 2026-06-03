# poolmind — Architecture & Technical Reference

```
Cybersecurity Resource Pool — CLI + Web UI + REST API
Version 2.0  •  Python 3.14  •  SQLite + FTS5  •  Flask  •  freellmapi
```

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Data Model: Universal Resource Schema](#3-data-model-universal-resource-schema)
4. [Database Schema](#4-database-schema)
5. [Ingestion Pipeline](#5-ingestion-pipeline)
6. [Classification System](#6-classification-system)
7. [AI Integration](#7-ai-integration)
8. [Self-Adapting Prompt Evolution](#8-self-adapting-prompt-evolution)
9. [REST API Layer](#9-rest-api-layer)
10. [Web UI Architecture](#10-web-ui-architecture)
11. [CLI Architecture](#11-cli-architecture)
12. [Search Engine](#12-search-engine)
13. [Export & Sync Systems](#13-export--sync-systems)
14. [Design System](#14-design-system)
15. [File Tree](#15-file-tree)
16. [Data Flow Diagrams](#16-data-flow-diagrams)
17. [Configuration Reference](#17-configuration-reference)

---

## 1. System Overview

poolmind is a full-stack application for collecting, organizing, enriching, and retrieving cybersecurity learning resources. It follows a **rules-first, AI-second** philosophy — heuristics run before any AI call, and AI is only invoked when heuristic confidence falls below a configurable threshold (default 70%).

### Core Principles

- **Local-first**: SQLite database, no external services required. AI and cloud sync are optional.
- **Offline-capable**: Heuristic classification handles 80%+ of cases without any AI dependency.
- **Single schema**: Every resource type (article, tool, video, book, writeup, etc.) uses the same Universal Resource Schema (URS) — 65 fields.
- **Extensible by design**: Plug-in extractors, classifier rules, AI tasks, and export formats.
- **Self-improving prompts**: AI prompts evolve based on user corrections and feedback metrics.

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.14 |
| CLI Framework | Typer (click-based) |
| Web Framework | Flask 3.x |
| Database | SQLite 3 + FTS5 full-text search |
| Validation | Pydantic v2 |
| Templates | Jinja2 |
| Frontend | HTMX + vanilla JS + Lucide icons |
| CSS | Custom design system (CSS custom properties) |
| AI Backend | freellmapi (local) / OpenAI API (cloud) |
| Search | SQLite FTS5 + rapidfuzz fuzzy matching |
| Task Scheduling | Custom scheduler (watch mode) |

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER INTERFACES                              │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────────────────────┐  │
│  │   CLI    │  │   Web UI     │  │        REST API              │  │
│  │ (Typer)  │  │ (Flask+HTMX) │  │  (50+ endpoints)             │  │
│  └────┬─────┘  └──────┬───────┘  └──────────┬───────────────────┘  │
│       │               │                     │                       │
├───────┴───────────────┴─────────────────────┴───────────────────────┤
│                      APPLICATION LAYER                               │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Core Modules                                │   │
│  │  ┌────────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐  │   │
│  │  │extractors  │  │classifier │  │normalizer│  │dedupe    │  │   │
│  │  └────────────┘  └───────────┘  └──────────┘  └──────────┘  │   │
│  │  ┌────────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐  │   │
│  │  │search     │  │audit      │  │graph     │  │anki/site │  │   │
│  │  └────────────┘  └───────────┘  └──────────┘  └──────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    AI Layer (Optional)                         │   │
│  │  ┌──────────────┐  ┌────────────────┐  ┌──────────────────┐  │   │
│  │  │freellm_tasks │  │feedback_tracker│  │prompt_evolution  │  │   │
│  │  └──────────────┘  └────────────────┘  └──────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Sync Layer (Optional)                       │   │
│  │  ┌──────────────┐  ┌────────────────┐                         │   │
│  │  │notion_sync   │  │obsidian_writer │                         │   │
│  │  └──────────────┘  └────────────────┘                         │   │
│  └──────────────────────────────────────────────────────────────┘   │
├──────────────────────────────────────────────────────────────────────┤
│                        DATA LAYER                                    │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  SQLite + FTS5                                                │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐│   │
│  │  │resources │ │audit_log │ │ai_cache  │ │pool_config       ││   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘│   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────────────────┐ │   │
│  │  │dead_links│ │prompt_*  │ │resources_fts (FTS5 virtual)  │ │   │
│  │  └──────────┘ └──────────┘ └──────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────┐  ┌──────────────────────────┐             │
│  │  .env (config)       │  │  data/*.json (paths,     │             │
│  │                      │  │  stacks, exported data)   │             │
│  └──────────────────────┘  └──────────────────────────┘             │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Data Model: Universal Resource Schema

Everything in poolmind uses a single Pydantic model: `Resource` (defined in `models/resource.py`, 65 fields).

### Field Categories

**Identity** (5 fields)
```
id            str    UUID first 8 chars (e.g. "a1b2c3d4")
title         str    Required — resource title
type          str    One of 36 types (article, tool, book, writeup, ...)
url           str    Source URL, defaults to "local" for non-URL resources
mirror_urls   list   Wayback Machine / alternative URLs
```

**Classification** (4 fields)
```
domain        str    One of 29 domains (web, network, cloud, malware, ...)
subdomain     str    Optional finer-grained category
tags          list   Free-form string tags
source_platform str  Where the resource lives (github, youtube, hackerone, ...)
```

**Learning Metadata** (5 fields)
```
skill_level       str    beginner / intermediate / advanced / expert / all
prerequisites     list   Resource IDs that should be studied first
time_to_value     str    Estimated time to get value (e.g. "30min", "2h", "week")
format            str    text / video / interactive / audio / tool / hands-on / mixed
learning_path     str    Optional learning path name this resource belongs to
```

**Availability** (7 fields)
```
cost              str    free / freemium / paid / one-time / subscription
language          str    ISO language code (default "en")
year_published    int    Optional
last_verified_alive str  Date of last successful URL check
last_updated_by_author str When the author last updated it
is_still_maintained  int Boolean for tools/repos
```

**Quality & Engagement** (7 fields)
```
quality_score      int    AI-assigned or manual 1-10
personal_rating    int    User rating 1-10
times_used         int    Usage counter
last_used          str    ISO date of last use
consumption_state  str    saved / skimmed / studied / mastered / applied
temporal_relevance str    evergreen / time-sensitive / historical / emerging
```

**Content** (8 fields)
```
summary            str    Full paragraph description (AI-generated or manual)
why_it_matters     str    Strategic value statement
best_for           str    Recommended use cases
avoid_if           str    When NOT to use this resource
notes              str    User's personal notes
related_resources  list   IDs of related resources
next_step_resource str    ID of the recommended next resource to study
```

**Provenance** (9 fields)
```
added_by           str    "user" or "ai" or "import"
added_on           str    ISO timestamp
ai_confidence      int    0-100 how confident AI was in its enrichment
ai_disabled        bool   Was AI skipped for this resource
ai_enriched        bool   Was AI used at all
extended_meta      dict   JSON blob for extractor-specific metadata
schema_version     str    URS schema version
```

**Sync** (4 fields)
```
notion_page_id     str    Notion page ID after sync
notion_last_synced str    ISO timestamp of last Notion push
```

### Model Validation

The Pydantic model enforces:
- `title` is required
- `type` must be one of the 36 known types (validated via `field_validator`)
- `domain` must be one of the 29 known domains
- `tags` gets auto-parsed from comma-separated strings via `field_validator`
- `url` defaults to `"local"` if not provided
- `consumption_state` defaults to `"saved"`

---

## 4. Database Schema

SQLite database at `data/poolmind.db` with 9 tables + 3 FTS5 virtual tables.

### Table: `resources`

The main resource table — one row per resource, 44 columns mirroring the URS model. Key columns:

```sql
CREATE TABLE resources (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    type            TEXT DEFAULT 'article',
    url             TEXT DEFAULT 'local',
    domain          TEXT DEFAULT 'general',
    tags            TEXT DEFAULT '[]',       -- JSON array
    skill_level     TEXT DEFAULT 'intermediate',
    consumption_state TEXT DEFAULT 'saved',
    summary         TEXT,
    why_it_matters  TEXT,
    personal_rating INTEGER,
    times_used      INTEGER DEFAULT 0,
    ai_confidence   INTEGER,
    ai_disabled     INTEGER DEFAULT 0,
    extended_meta   TEXT,                    -- JSON blob
    notion_page_id  TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
    -- 30+ more columns
);
```

**Indexes**: 8 indexes on `domain`, `type`, `consumption_state`, `skill_level`, `ai_confidence`, `added_on`, plus composite indexes for common filter combinations.

### Table: `resources_fts` (FTS5 virtual table)

Full-text search over 8 columns:
```sql
CREATE VIRTUAL TABLE resources_fts USING fts5(
    id, title, summary, tags, author, subdomain, notes, why_it_matters,
    content='resources', content_rowid='rowid'
);
```

Triggers keep FTS in sync on INSERT/UPDATE/DELETE.

### Table: `audit_log`

```sql
CREATE TABLE audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action      TEXT NOT NULL,       -- add, edit, archive, delete, sync, rate, etc.
    resource_id TEXT,
    detail      TEXT,
    timestamp   TEXT DEFAULT (datetime('now'))
);
```

### Table: `ai_cache`

```sql
CREATE TABLE ai_cache (
    input_hash  TEXT PRIMARY KEY,
    task        TEXT NOT NULL,       -- classify_resource, summarize_resource, etc.
    response    TEXT NOT NULL,       -- JSON
    model       TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);
```

### Table: `dead_links`

```sql
CREATE TABLE dead_links (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id TEXT NOT NULL,
    url         TEXT NOT NULL,
    http_status INTEGER,
    checked_at  TEXT,
    wayback_url TEXT,
    resolved    INTEGER DEFAULT 0
);
```

### Tables: `prompt_feedback`, `prompt_evolution_log`

Track every AI response for prompt evolution:
- `prompt_feedback`: per-call metrics (structural success, field coverage, confidence, user corrections, response time)
- `prompt_evolution_log`: when prompts were evolved (old/new version, trigger reason, backup path)

### Tables: `pool_config`, `research_log`

- `pool_config`: key-value configuration store
- `research_log`: lightweight research note storage

---

## 5. Ingestion Pipeline

The complete add-from-URL pipeline (`add_resource.py:add_from_url()`) has 14 stages:

```
URL Input
  │
  ├── [1] Normalize URL
  │       strip tracking params, canonicalize, handle wayback
  │
  ├── [2] Dedupe Check
  │       exact URL match → fuzzy title match (rapidfuzz, threshold 85)
  │
  ├── [3] Extract Metadata
  │       7 extractors tried in order:
  │       • article (readability-lxml)        — general web pages
  │       • GitHub (PyGithub + REST API)      — repos
  │       • YouTube (yt-dlp)                  — videos/playlists
  │       • PDF (pymupdf)                     — PDF documents
  │       • HackerOne (BS4)                   — bug bounty reports
  │       • Bugcrowd (BS4)                    — bug bounty reports
  │       • generic (OpenGraph + meta tags)   — fallback
  │
  ├── [4] Heuristic Classify (6-pass)
  │       Pass 1: URL patterns (25pts)
  │       Pass 2: Platform detection (15pts)
  │       Pass 3: Domain keywords in title/body (20pts)
  │       Pass 4: Subdomain analysis (10pts)
  │       Pass 5: Skill level from body (5pts)
  │       Pass 6: Temporal relevance (5pts)
  │       → confidence score 0-100
  │
  ├── [5] Confidence Check
  │       confidence >= 70? → skip AI, use heuristic
  │       confidence < 70?  → proceed to AI enrichment
  │
  ├── [6] AI Classification
  │       AI determines: type, domain, subdomain, skill_level,
  │       format, temporal_relevance, time_to_value, cost
  │
  ├── [7] AI Summarization
  │       AI generates: summary (3-5 sentences), why_it_matters,
  │       best_for, avoid_if, quality_score
  │
  ├── [8] AI Tag Generation
  │       AI generates relevant tags from title + body + domain + type
  │
  ├── [9] Wayback Mirror Capture
  │       auto-fetch Wayback Machine URL as mirror
  │
  ├── [10] AI Related Resource Suggestion
  │       AI suggests related resources + next step from pool
  │
  ├── [11] Normalize Fields
  │       sanitize strings, strip tracking, parse tags, validate enums
  │
  ├── [12] Enforce Minimum Summary
  │       if summary < 80 chars → retry AI or construct fallback
  │
  ├── [13] Pydantic Validate
  │       validate against URS model, auto-fix on failure
  │
  └── [14] Save + Sync
        SQLite insert → FTS5 trigger → Obsidian note → Notion sync
```

### Add-Manual Pipeline

```
Manual Input (dict of fields)
  │
  ├── [1] Normalize Fields
  ├── [2] Enforce Minimum Summary
  ├── [3] Pydantic Validate
  └── [4] Save + Sync (if configured)
```

### Smart Bulk Ingest

The `pool ingest` command (`bulk_parser.py`) auto-detects input format from 9 patterns:

| Format | Example | Detection |
|--------|---------|-----------|
| Plain URLs | `https://...` | Line matches URL regex |
| Markdown links | `[Title](URL)` | Matches `[text](url)` pattern |
| Annotated | `URL \| notes` | Contains `\|` separator |
| Numbered | `1. URL` or `1) URL` | Starts with digit + punctuation |
| CSV-ish | `URL,notes` | Contains comma, first part is URL |
| Named | `Title: URL` or `Title - URL` | Text then separator then URL |
| Bracketed | `[Title] URL` | Text in brackets followed by URL |
| Quoted | `"Title" URL` | Quoted text followed by URL |
| Mixed | Any combination | Falls through to auto-detect |

---

## 6. Classification System

### Heuristic Classifier (`classifier.py`)

6-pass rule engine scoring 0-100. No dependencies, runs in milliseconds.

**Pass 1 — URL Patterns (25 points)**
```python
# Examples of pattern → type mappings:
"github.com/*"       → type: repository, domain: depends on content
"youtube.com/watch*" → type: video, platform: youtube
"hackerone.com/*"    → type: writeup, platform: hackerone
"arxiv.org/*"        → type: paper, domain: depends
"*.pdf"              → type: paper (tentative)
"reddit.com/*"       → type: thread, platform: reddit
```

**Pass 2 — Platform Detection (15 points)**
Checks URL against known platforms (30+): github, medium, youtube, arxiv, hackerone, bugcrowd, tryhackme, hackthebox, portswigger, etc.

**Pass 3 — Domain Keywords (20 points)**
Scans title + body for domain-specific keywords:
```python
DOMAIN_KEYWORDS = {
    "web": ["xss", "csrf", "sqli", "ssrf", "rce", "lfi", "owasp",
            "http", "cors", "hsts", "csp", "samesite", "waf"],
    "network": ["tcp", "udp", "dns", "bgp", "ospf", "vlan",
                "nmap", "wireshark", "pcap", "mitm"],
    "malware": ["ransomware", "trojan", "backdoor", "shellcode",
                "c2", "dropper", "packer", "rootkit"],
    "cloud": ["aws", "azure", "gcp", "iam", "s3", "lambda",
              "kubernetes", "docker", "terraform"],
    # ... 25+ domains
}
```

**Pass 4 — Subdomain (10 points)**
Analyzes the subdomain for clues (e.g., `docs.example.com` → format: documentation).

**Pass 5 — Skill Level (5 points)**
Detects beginner/intermediate/advanced/expert indicators in body text.

**Pass 6 — Temporal Relevance (5 points)**
Detects "evergreen" vs "time-sensitive" vs "historical" vs "emerging" based on content age, update frequency, and topic keywords.

### AI Classifier (`freellm_tasks.py:classify_resource()`)

Called only when heuristic confidence < 70%. Returns:
```json
{
  "type": "article",
  "domain": "web",
  "subdomain": "jwt",
  "skill_level": "intermediate",
  "confidence": 85,
  "format": "text",
  "temporal_relevance": "evergreen",
  "time_to_value": "30min",
  "cost": "free"
}
```

### Confidence Threshold

Configurable via `AI_CONFIDENCE_THRESHOLD` env var (default: 70). The threshold is compared against the heuristic's aggregate score. At 70+, heuristic results are used directly. Below 70, AI is invoked for each field that didn't meet the threshold.

---

## 7. AI Integration

### Architecture

```
poolmind
  │
  ├── freellm_tasks.py
  │     │
  │     ├── _load_prompt(task)        reads prompts/<task>.md
  │     ├── _wrap_call(task, prompt)  sends to AI backend
  │     ├── _cache_key(content)       creates SHA256 input hash
  │     └── get_ai_cache / set_ai_cache  SQLite cache
  │
  ├── prompts/*.md                   14 prompt templates
  │
  └── AI Backend (fallback chain)
        ├── freellmapi (local, port 3001)
        └── OpenAI API (cloud)
```

### Backend Selection

```python
def _call_llm(prompt: str, model: str = None) -> Optional[str]:
    # Try freellmapi first
    result = _try_freellmapi(prompt, model)
    if result: return result
    # Fall back to OpenAI
    result = _try_openai(prompt, model)
    return result
```

### AI Tasks (14 total)

| Task | Prompt File | Inputs | Output Fields |
|------|------------|--------|---------------|
| `classify_resource` | `classify_resource.md` | title, url, body_text | type, domain, subdomain, skill_level, format, temporal_relevance, time_to_value, cost, confidence |
| `summarize_resource` | `summarize_resource.md` | title, url, body_text | summary (3-5 sentence paragraph), why_it_matters, best_for, avoid_if, quality_score, confidence |
| `generate_tags` | `generate_tags.md` | title, body_text, domain, type | tags (list) |
| `suggest_related` | `suggest_related.md` | resource_title, resource_domain, pool_titles | related_titles (list), next_step_title |
| `generate_learning_path` | `generate_learning_path.md` | goal, pool_resources | path_name, weeks (list of week resources) |
| `generate_stack` | `generate_stack.md` | mission, pool_resources | stack_name, description, resources (list) |
| `gap_analysis` | `gap_analysis.md` | pool stats, domains, types | missing_domains, recommendations, coverage |
| `gap_report` | `gap_report.md` | pool stats, existing gaps | report with health score |
| `parse_query` | `parse_query.md` | query string | parsed intent, filters, keywords |
| `rerank_search` | `rerank_search.md` | query, results | reordered results with relevance scores |
| `improve_note` | `improve_note.md` | title, existing note | improved note |
| `schema_suggest` | `schema_suggest.md` | URL, extracted data | suggested schema fields |
| `briefing` | (uses multiple) | pool stats, new resources | daily briefing |
| `evolve_prompt` | `evolve_prompt.md` | task stats, current prompt | improved prompt |
| `generate_anki` | (uses multiple) | resource data | Anki card content |

### Caching

Every AI response is cached by SHA256(input_hash) in the `ai_cache` table:
```python
cache_key = hashlib.sha256(content.encode()).hexdigest()[:32]
```

Cache hit → skip API call. Cache is write-once, never invalidated (resources don't change often enough to warrant re-processing).

### AI Disabled Mode

When `AI_ENABLED=false` or `ai_disabled=true` on a resource:
- All AI tasks are skipped
- Heuristic classification is used exclusively
- Confidence is set to heuristic score

---

## 8. Self-Adapting Prompt Evolution

### Feedback Tracking

Every AI call logs to `prompt_feedback`:
```sql
-- Per-call metrics tracked:
structural_success   -- Did the AI return valid JSON?
field_coverage       -- What fraction of expected fields were populated?
confidence_reported  -- AI's self-reported confidence
user_corrected       -- Did the user correct this field?
correction_detail    -- What was the correction?
response_time_ms     -- How long did the AI take?
model_used           -- Which model handled the request
```

### Evolution Trigger

The system monitors each task's metrics:
- **Success rate** drops below 80%
- **User correction rate** exceeds 15%
- **Average confidence** drops below 60
- **Average field coverage** falls below 0.7
- **Insufficient data** (fewer than 10 calls) — no evolution

### Evolution Engine (`prompt_evolution.py`)

When triggered:
1. **Analyze** — Collect recent feedback for the task
2. **Generate** — Call AI with meta-prompt (`prompts/evolve_prompt.md`) to create an improved prompt
3. **Diff** — Compute `diff_summary` between current and proposed prompt
4. **Backup** — Save current prompt to `prompts/backups/<task>_<timestamp>.md`
5. **Deploy** — Write new prompt to `prompts/<task>.md`
6. **Log** — Record in `prompt_evolution_log` with old/new versions, trigger reason, sample size

### Rollback

Previous versions are stored in `prompts/backups/`. The API exposes:
- `POST /api/ai/prompts/<task>/restore` — restore any backup version

---

## 9. REST API Layer

### Blueprint Architecture

8 blueprints, each in `app/api/<module>.py`, registered via `app/api/__init__.py:register_blueprints()`:

| Blueprint | File | Prefix | Endpoints |
|-----------|------|--------|-----------|
| `api_resources` | `resources.py` | `/api` | 14 |
| `api_ingest` | `ingest.py` | `/api/ingest` | 3 |
| `api_search` | `search.py` | `/api/search` | 2 |
| `api_browse` | `browse.py` | `/api/resources` | 4 |
| `api_intel` | `intelligence.py` | `/api` | 9 |
| `api_maint` | `maintenance.py` | `/api` | 7 |
| `api_ai` | `ai_prompts.py` | `/api/ai` | 7 |
| `api_settings` | `settings.py` | `/api/settings` | 4 |

Total: ~50 endpoints.

### Response Format

All endpoints return JSON. Success:
```json
{"resource": {...}}  or  {"resources": [...]}  or  {"status": "ok"}
```

Errors:
```json
{"error": "not_found"}     // 404
{"error": "text_required"} // 422 with specific error code
{"error": "message..."}    // 500 with truncated message
```

### Key Design Decisions

- **No authentication** — local-first tool, not a multi-user service
- **No pagination cursors** — simple `limit`/`offset` params (SQLite OFFSET)
- **Implicit soft-delete** — DELETE sets `consumption_state='archived'` unless `hard=true`
- **Lazy imports** — AI modules imported inside functions, not at module level (avoids circular imports and speeds up non-AI paths)

---

## 10. Web UI Architecture

### Flask App Factory

`webui.py:create_app()` creates and configures the Flask application:
1. Set template/static folders
2. Register API blueprints
3. Define all page routes (20+)
4. Return app

### Routes (20+ pages)

```
/                                    Dashboard
/add                                 Quick URL form
/add/manual                          Manual entry form
/ingest                              Bulk ingest page
/resources                           Resource list with filters
/resources/random                    Random gem
/resources/untouched                 Untouched resources
/resources/recent                    Recent additions
/resources/by-state/<state>         Filtered by state
/resource/<id>                       Resource detail + actions
/resource/<id>/edit                  Edit form
/search                              Search (keyword + NL)
/intelligence/paths                  Learning paths list
/intelligence/paths/<id>            Path detail
/intelligence/stacks                 Tech stacks list
/intelligence/stacks/<id>           Stack detail
/intelligence/gap                    Gap analysis
/maintenance/audit                   Audit log
/maintenance/dedupe                  Duplicate finder
/maintenance/dead-links              Dead links manager
/maintenance/sync                    Notion sync dashboard
/ai/prompts                          Prompt stats dashboard
/ai/prompts/<task>                  Prompt detail + evolve
/ai/corrections                      Corrections log
/settings                            Configuration
/settings/taxonomy                   Taxonomy viewer
```

### Template Architecture

20 Jinja2 templates extending `layout.html`:

```
layout.html
├── dashboard.html
├── add.html
├── add_manual.html
├── ingest.html
├── list.html
├── detail.html
├── edit.html
├── search.html
├── random.html
├── untouched.html
├── recent.html
├── empty.html
├── intel_paths.html
├── intel_path.html
├── intel_stacks.html
├── intel_stack.html
├── intel_gap.html
├── maint_audit.html
├── maint_dedupe.html
├── maint_dead_links.html
├── maint_sync.html
├── ai_prompts.html
├── ai_prompt.html
├── ai_corrections.html
├── settings.html
└── taxonomy.html
```

### JavaScript Patterns

- **HTMX** loaded but not heavily used — most actions use vanilla `fetch()` API
- **Toast notifications** — global toast container in layout, `toast(msg, type)` function
- **Modal dialogs** — CSS overlay + flex centering, shown/hidden via JS
- **Async form submission** — `add.html` uses `async/await` with progress panel
- **Star rating** — click handler sends `POST /api/resource/<id>/rate` and updates visual
- **Dropdown nav** — click to toggle, click outside to close

### Data Flow

```
Page Load:
  Browser GET /route
    → Flask route handler
      → db.get_*() or search or file read
      → render_template("page.html", data)
      → HTML response with inline data

User Action (e.g., set state):
  User clicks dropdown option
    → JS: fetch(POST /api/resource/<id>/state, {state: "studied"})
      → Flask API endpoint
        → db.update_resource(...)
        → jsonify({"state": "studied"})
      → JS: toast("State: studied", "success")
```

---

## 11. CLI Architecture

### Framework

Uses **Typer** (built on Click) for auto-generated `--help`, argument validation, and type coercion. Single `app` object in `cli.py` with 35+ commands.

### Commands by Phase

**Phase 1 — Core CRUD**
```
init, add, add-manual, bulk, search, find, get, recent, random,
untouched, rate, note, state, tag, archive, use, correct, ingest
```

**Phase 2 — Learning & Review**
```
path, stack, gap, brief, due, progress, dedupe, dead-check, audit, stats, watch
```

**Phase 3 — Export & Sync**
```
serve, graph, anki, site, sync-notion, prompt-evolve, prompt-stats, prompt-corrections
```

### Wrappers

Two wrapper scripts for convenience:
- `pool.cmd` — Windows CMD: `cd /d "%~dp0" && .venv\Scripts\python.exe -m app.cli %*`
- `pool.sh` — Bash: `cd "$(dirname "$0")" && exec .venv/Scripts/python.exe -m app.cli "$@"`

---

## 12. Search Engine

### Architecture (`search.py`)

Three-tier search:

**Tier 1 — FTS5 Full-Text Search** (fastest)
```sql
SELECT * FROM resources_fts WHERE resources_fts MATCH ? ORDER BY rank
```
Searches across: title, summary, tags, author, subdomain, notes, why_it_matters

**Tier 2 — Metadata Filter** (combined with FTS5)
```python
# Applicable filters: domain, type, skill_level, format, cost, consumption_state
# Applied as SQL WHERE clauses after FTS5 match
```

**Tier 3 — AI Reranking** (optional, slowest)
When `--nl` flag is used, the FTS5 results are sent to AI (`rerank_search` task) which reorders by semantic relevance to the natural language query.

### Browse Functions

```python
get_random(limit=1)       # Random resource(s)
get_recent(limit=50)      # Most recently added
get_untouched(limit=50)   # Still in "saved" state
list_by_filter(domain, type_, consumption_state, limit=50)  # Metadata-only filter
```

### Duplicate Detection (`dedupe.py`)

Two-stage:
1. **Exact URL match** — `normalize_url(a) == normalize_url(b)`
2. **Fuzzy title match** — `rapidfuzz.fuzz.token_sort_ratio(title_a, title_b) >= 85`

---

## 13. Export & Sync Systems

### Obsidian Export (`obsidian_writer.py`)

Each resource becomes a markdown note at `vault/Resources/resource-<id>-<slug>.md`:
```markdown
---
id: a1b2c3d4
title: "Resource Title"
type: article
domain: web
tags: [tag1, tag2]
# ... all 45 URS fields as YAML frontmatter
---

## Summary

Full paragraph summary.

## Why It Matters

Strategic value.

## Best For

Use case 1, Use case 2, Use case 3

## Avoid If

When not to use this resource.

## Related Resources

- [[resource-e5f6g7h8-related-title]]

<!-- DATAVIEW: same-domain resources -->
```

### Notion Sync (`notion_sync.py`)

One-way: SQLite → Notion database. Property mapping in `config/notion.yaml` maps 28 URS fields to Notion properties.

Sync flow:
1. Read unsynced resources from DB (`notion_last_synced IS NULL`)
2. For each resource, build Notion property payload via `_build_properties()`
3. POST to Notion API `https://api.notion.com/v1/pages`
4. On success, store `notion_page_id` and `notion_last_synced` in DB
5. Rate-limited by `NOTION_RATE_LIMIT_SLEEP` (default 0.35s)

### Graph Export (`graph.py`)

Two formats:
- **D3.js**: Standalone HTML with force-directed graph. Nodes colored by domain, sized by quality_score. Edges from `related_resources`. Interactive: drag, hover for metadata tooltip.
- **Obsidian wiki-links**: Adds `[[wiki-links]]` between related resources in existing vault notes + generates `resource-hub.md` index organized by domain.

### Anki Export (`anki.py`)

Generates CSV with columns: `Title, URL, Type, Domain, Summary, Why It Matters, Tags`. One card per resource. Importable via Anki's standard CSV import.

### Static Site (`sitegen.py`)

Self-contained HTML file with:
- Stats bar (total/domain/type breakdown)
- Random resource pick
- Complete resource grid with expandable details

---

## 14. Design System

Defined in `static/style.css` (556 lines) and documented in `design-system.md`.

### CSS Custom Properties

```css
:root {
  --bg-base:       #0a0e1a;
  --bg-surface:    #111726;
  --bg-elevated:   #1a2138;
  --bg-hover:      #1f2942;
  --bg-active:     #252f4a;

  --border-faint:  #1f2942;
  --border-soft:   #2a3553;
  --border-strong: #3d4a6e;

  --text-primary:   #e8ecf4;
  --text-secondary: #a8b2cf;
  --text-tertiary:  #6b7795;
  --text-faint:     #4a5470;

  --accent:         #4d9fff;
  --accent-hover:   #6cb0ff;
  --accent-muted:   #2a5a99;
  --accent-glow:    rgba(77, 159, 255, 0.15);

  --success:        #4ade80;
  --warning:        #fbbf24;
  --danger:         #f87171;
  --info:           #60a5fa;
}
```

### Components

| Component | CSS Class | Description |
|-----------|-----------|-------------|
| HUD Card | `.hud-card` | Corner bracket decorations, subtle border, terminal-style |
| Stat Card | `.stat-card` | Large mono value + label + optional badge |
| Status Badge | `.stat-badge` | `[BRACKETED]` text, color-coded (ok/warn) |
| Type Chip | `.type-chip` | Color-coded by resource type (12 colors) |
| State Badge | `.state-badge` | Color by consumption state |
| Data Table | `.data-table` | Minimal border, hover rows, mono cells |
| Card | `.card` | Elevated surface with rounded corners |
| Empty State | `.empty-state` | Centered icon + message + action button |
| Modal | `.modal-overlay` + `.modal` | Centered dialog with backdrop |
| Toast | `.toast-container` + `.toast` | Fixed bottom-right notification |
| Progress Panel | `.progress-panel` | Step indicator for async operations |
| Tag | `.tag` | Inline `#tag` style |
| Action Card | `.action-card` | Quick action grid item with icon |

---

## 15. File Tree

```
poolmind/
│
├── app/                          # Python application package
│   ├── __init__.py               # Env loading (python-dotenv), logging setup
│   ├── cli.py                    # 35+ Typer CLI commands (1336 lines)
│   ├── webui.py                  # Flask app factory + 20+ page routes (544 lines)
│   ├── db.py                     # SQLite CRUD, stats, FTS5, pool_config (324 lines)
│   │
│   ├── api/                      # REST API blueprints
│   │   ├── __init__.py           # register_blueprints() hub
│   │   ├── resources.py          # CRUD + resource actions (14 endpoints)
│   │   ├── ingest.py             # Parse + run + SSE streaming (3 endpoints)
│   │   ├── search.py             # Keyword + NL search (2 endpoints)
│   │   ├── browse.py             # Random, untouched, recent, by-state (4 endpoints)
│   │   ├── intelligence.py       # Paths, stacks, gap analysis (9 endpoints)
│   │   ├── maintenance.py        # Audit, dedupe, dead-links, notion sync (7 endpoints)
│   │   ├── ai_prompts.py         # Prompt stats, evolution, corrections (7 endpoints)
│   │   └── settings.py           # Config, env vars, taxonomy (4 endpoints)
│   │
│   ├── add_resource.py           # 14-stage ingestion pipeline (251 lines)
│   ├── extractors.py             # 7 URL content extractors (300+ lines)
│   ├── classifier.py             # 6-pass heuristic classifier
│   ├── normalizer.py             # URL normalization + tracking-strip + wayback
│   ├── freellm_tasks.py          # 14 AI task wrappers + cache + fallback chain (461 lines)
│   ├── feedback_tracker.py       # AI feedback + correction tracking
│   ├── prompt_evolution.py       # Self-adapting prompt evolution engine
│   ├── bulk_parser.py            # Smart input parser (9 formats auto-detect)
│   ├── ingest_router.py          # Ingestion routing + dedupe + Notion for bulk
│   ├── search.py                 # FTS5 + metadata filter + AI rerank + browse
│   ├── dedupe.py                 # URL exact + fuzzy title (rapidfuzz) dedup
│   ├── audit.py                  # Dead link checker + gap analysis
│   ├── graph.py                  # D3.js + Obsidian wiki-link graph export
│   ├── notion_sync.py            # One-way SQLite → Notion push (207 lines)
│   ├── obsidian_writer.py        # YAML frontmatter markdown note writer
│   ├── anki.py                   # Anki-importable CSV deck export
│   └── sitegen.py                # Static HTML site generator
│
├── models/
│   └── resource.py               # URS Pydantic model (65 fields, 149 lines)
│
├── templates/                    # 20 Jinja2 HTML templates
│   ├── layout.html               # Base template (nav, toast, modal system)
│   ├── dashboard.html            # HUD stats, gem, quick actions, services status
│   ├── add.html                  # Quick URL form with async submission
│   ├── add_manual.html           # Manual entry with collapsible sections
│   ├── ingest.html               # Bulk ingest paste/upload/preview
│   ├── list.html                 # Filterable resource table
│   ├── detail.html               # 2-column detail + actions sidebar
│   ├── edit.html                 # Full edit form
│   ├── search.html               # Keyword + NL tabs
│   ├── random.html               # Single gem card
│   ├── untouched.html            # Untouched resources table
│   ├── recent.html               # Recent additions table
│   ├── empty.html                # Reusable 404/empty state
│   ├── intel_paths.html          # Learning paths list + generate modal
│   ├── intel_path.html           # Path detail with weekly breakdown
│   ├── intel_stacks.html         # Tech stacks list + generate modal
│   ├── intel_stack.html          # Stack detail with resource links
│   ├── intel_gap.html            # Gap analysis with run/display
│   ├── maint_audit.html          # Audit log table + run button
│   ├── maint_dedupe.html         # Duplicate finder + pair display
│   ├── maint_dead_links.html     # Dead links table with resolve
│   ├── maint_sync.html           # Notion sync status + history + run
│   ├── ai_prompts.html           # Prompt stats dashboard
│   ├── ai_prompt.html            # Task detail + evolve/corrections
│   ├── ai_corrections.html       # Corrections log table
│   ├── settings.html             # Config + env vars + notion section
│   └── taxonomy.html             # Full taxonomy tag display
│
├── static/
│   └── style.css                 # Design system v1.0 (556 lines)
│
├── prompts/                      # 14 AI prompt templates (Markdown)
│   ├── classify_resource.md
│   ├── summarize_resource.md
│   ├── generate_tags.md
│   ├── suggest_related.md
│   ├── generate_learning_path.md
│   ├── generate_stack.md
│   ├── gap_analysis.md
│   ├── gap_report.md
│   ├── parse_query.md
│   ├── rerank_search.md
│   ├── improve_note.md
│   ├── schema_suggest.md
│   ├── evolve_prompt.md
│   └── briefing.md
│   └── backups/                  # Auto-generated prompt version backups
│
├── config/
│   ├── settings.yaml             # App configuration defaults
│   ├── taxonomy.yaml             # 36 types, 29 domains, URL patterns
│   └── notion.yaml               # 28 Notion property mappings
│
├── scripts/
│   ├── init_db.py                # Database schema creation (9 tables, FTS5, triggers, indexes)
│   └── scheduler.py              # Background maintenance loop
│
├── data/
│   ├── poolmind.db               # SQLite database
│   ├── learning_paths.json       # Saved AI-generated learning paths
│   └── resource_stacks.json      # Saved AI-generated tech stacks
│
├── vault/Resources/              # Obsidian notes (generated)
│
├── .env                          # Environment variables (gitignored)
├── .env.example                  # Example env vars
├── requirements.txt              # Python dependencies
├── pool.cmd                      # Windows CLI wrapper
├── pool.sh                       # Bash CLI wrapper
├── start.cmd                     # One-click launcher (freellmapi + web UI)
├── stop.cmd                      # One-click stopper
├── USAGE.md                      # User documentation (775 lines)
├── GUIDE.md                      # Beginner-friendly guide (497 lines)
├── design-system.md              # UI/UX design system specification
└── README.md                     # Project readme
```

---

## 16. Data Flow Diagrams

### Resource Addition (URL)

```
User
  │ pool add <url>
  │ POST /api/add {"url": "..."}
  ▼
add_resource.py                  db.py                    freellmapi
────────────────────────────────────────────────────────────────────
normalize_url(url) ──────────► check_duplicate()
                                    │
extract_metadata(url)              ◄─┘
  │
  ├── article extractor (readability)
  ├── GitHub extractor
  ├── YouTube extractor
  ├── PDF extractor
  ├── HackerOne extractor
  ├── Bugcrowd extractor
  └── generic fallback
  │
  ▼
classifier(url, title, body)
  │ 6-pass heuristic → confidence score
  │
  ├── confidence >= 70? ────► skip AI, use heuristic
  │
  └── confidence < 70?
        │
        ▼
  freellm_tasks.py
    ├── classify_resource() ──► AI ──► type, domain, skill_level
    ├── summarize_resource() ─► AI ──► summary, why_it_matters
    ├── generate_tags() ─────► AI ──► tags
    └── suggest_related() ───► AI ──► related IDs
  │
  ▼
_enforce_summary()
  │ if summary < 80 chars → retry AI or construct fallback
  ▼
normalize_resource_fields()
  ▼
Resource(**extracted) ──────► Pydantic validation
  │
  ▼
db.insert_resource() ───────► SQLite INSERT + FTS5 trigger
  │
  ├── OBSIDIAN_SYNC_ENABLED? ──► obsidian_writer.write_note()
  └── NOTION_SYNC_ENABLED? ────► notion_sync.sync_resource()
```

### Search Flow

```
User query: "ssrf bypass techniques"
  │
  ▼
search.py:search("ssrf bypass techniques")
  │
  ├── FTS5 MATCH query ─────► resources_fts ──► ranked results
  │
  ├── domain/type/skill filters ──► SQL WHERE clauses
  │
  ├── AI rerank? (--nl flag)
  │     └── freellm_tasks.py:rerank_search()
  │           └── AI reorders by semantic relevance
  │
  └── Return results with scores
```

### AI Prompt Evolution Flow

```
User corrects AI field on resource
  │ POST /api/resource/<id>/correct
  ▼
feedback_tracker.py logs correction
  │ INSERT INTO prompt_feedback
  ▼
(Periodic or triggered)
prompt_evolution.py:evolve_prompt(task)
  │
  ├── Query recent feedback for task
  ├── Check triggers:
  │   • success_rate < 80%?
  │   • correction_rate > 15%?
  │   • avg_confidence < 60?
  │   • field_coverage < 0.7?
  │
  ├── If triggered:
  │   ├── Call AI with evolve_prompt.md meta-prompt
  │   ├── Generate improved prompt
  │   ├── Backup current prompt to prompts/backups/
  │   ├── Write new prompt to prompts/<task>.md
  │   └── Log evolution event
  │
  └── Return evolution result
```

---

## 17. Configuration Reference

### Environment Variables (`.env`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `FREELLMAPI_URL` | `http://localhost:3001` | AI backend URL |
| `FREELLMAPI_API_KEY` | — | AI backend API key |
| `FREELLMAPI_MODEL` | `auto` | AI model name |
| `AI_ENABLED` | `true` | Master AI toggle |
| `AI_CONFIDENCE_THRESHOLD` | `70` | Heuristic confidence minimum |
| `OPENAI_API_KEY` | — | OpenAI API key (fallback) |
| `OPENAI_BASE_URL` | — | OpenAI base URL |
| `OPENAI_MODEL` | — | OpenAI model name |
| `NOTION_TOKEN` | — | Notion integration token |
| `NOTION_DATABASE` | — | Notion database ID |
| `NOTION_SYNC_ENABLED` | `true` | Auto-sync on add |
| `OBSIDIAN_VAULT_PATH` | `vault` | Path to Obsidian vault |
| `OBSIDIAN_SYNC_ENABLED` | `true` | Auto-write on add |
| `POOLMIND_DB_PATH` | `data/poolmind.db` | Database file path |
| `GITHUB_TOKEN` | — | GitHub API token (rate limits) |
| `NOTION_RATE_LIMIT_SLEEP` | `0.35` | Seconds between Notion API calls |
| `AUTO_MIRROR_WAYBACK` | `true` | Auto-capture Wayback URLs |
| `LINK_CHECK_INTERVAL_DAYS` | `90` | Days before link re-check |
| `LOG_LEVEL` | `INFO` | Python logging level |

### Database Config Keys (`pool_config` table)

Stored as key-value pairs, editable via Settings UI or API. Examples:
- `theme` — UI theme preference
- `default_domain` — Default domain for new resources
- `watch_interval_hours` — Watch mode check interval

---

*Generated for poolmind v2.0 — June 2026*
