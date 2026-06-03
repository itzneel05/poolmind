# poolmind — Cybersecurity Resource Pool

CLI + Web UI tool to ingest, enrich, organize, search, visualize, and sync cybersecurity resources.

```
.\pool.cmd add https://github.com/swisskyrepo/PayloadsAllTheThings
.\pool.cmd search "ssrf bypass techniques"
.\pool.cmd path "first bug bounty in 30 days"
.\pool.cmd serve
```

---

## Installation

```bash
cd poolmind
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Initialize database:
```bash
python scripts/init_db.py
```

Quick wrappers (use `pool` instead of `python -m app.cli`):
- **Git Bash**: `./pool.sh <command>`
- **PowerShell**: `.\pool.cmd <command>`

---

## Configuration

Copy and edit `.env`:
```bash
cp .env.example .env
```

### Essential vars

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `NOTION_TOKEN` | No | — | Notion integration token |
| `NOTION_DATABASE_ID` | No | — | Notion database ID |
| `OBSIDIAN_VAULT_PATH` | No | `vault` | Path to Obsidian vault |
| `AI_ENABLED` | No | `true` | Enable/disable AI enrichment |
| `AI_CONFIDENCE_THRESHOLD` | No | `70` | Heuristic must score >= this to skip AI |
| `FREELLMAPI_URL` | No | `http://localhost:11434` | AI endpoint |
| `FREELLMAPI_MODEL` | No | `llama3` | AI model |
| `GITHUB_TOKEN` | No | — | GitHub API (higher rate limits) |
| `LINK_CHECK_INTERVAL_DAYS` | No | `90` | Days before link re-check |

Notion, AI, and GitHub are optional. poolmind works fully offline with heuristics alone.

---

## Quick Start

```bash
# Add your first resource
.\pool.cmd add https://github.com/swisskyrepo/PayloadsAllTheThings

# Add a book manually
.\pool.cmd add-manual --title "Web Application Hacker's Handbook" --type book --domain web -n "Read chapters 1-5"

# Search
.\pool.cmd search "sql injection"
.\pool.cmd search --domain web --skill beginner --limit 5

# See what's in your pool
.\pool.cmd stats
.\pool.cmd recent

# Discover something you forgot
.\pool.cmd random

# Rate what you've studied
.\pool.cmd rate <id> 8
.\pool.cmd state <id> studied

# Web dashboard
.\pool.cmd serve
# -> http://127.0.0.1:5000
```

---

## Ingestion

### `pool add <url> [options]`
Full 14-step ingestion pipeline for any URL.

```
pool add https://example.com/article                     # basic
pool add https://github.com/user/repo --force             # skip dedupe
pool add https://youtube.com/watch?v=abc123 --no-ai       # no AI enrichment
pool add https://blog.com/post -n "my notes here"         # with personal notes
pool add https://example.com --no-notion --no-obsidian    # skip syncs
```

**Pipeline**: normalize URL -> dedupe check -> extract metadata (article/GitHub/YouTube/PDF/HackerOne/Bugcrowd) -> heuristic classify (6-pass rules) -> AI enrich (if confidence < 70) -> add mirrors -> suggest related -> normalize fields -> Pydantic validate -> SQLite + FTS5 -> Obsidian note -> Notion sync

### `pool add-manual --title <title> [options]`
Add a resource without URL extraction.

```
pool add-manual -t "Practical Malware Analysis" --type book --domain malware -n "Chapter 7 is gold"
pool add-manual -t "My Notes on ROP" --type note --url local --domain exploit-dev
```

### `pool ingest [--file <path>]`
Smart bulk parser supporting 9 input formats. Auto-detects format — no flags needed.

```
pool ingest -f urls.txt             # from file
pool ingest                         # paste, Ctrl+D to finish
```

Supported input formats:
- **Plain URLs** — one per line
- **Markdown links** — `[Title](URL)` or `<URL>`
- **Annotated** — `URL | notes here`
- **Numbered** — `1. URL` or `1) URL`
- **CSV-ish** — `URL,notes`
- **Mixed** — any combination above
- **Named** — `Title: URL` or `Title - URL`
- **Bracketed** — `[Title] URL`
- **Quoted** — `"Title" URL`

### `pool bulk [--file <path>]`
Legacy bulk add — simple URL-per-line format only.

```
pool bulk -f urls.txt               # from file
pool bulk                           # paste URLs, Ctrl+D to finish
```

---

## Search & Discovery

### `pool search <query> [options]`
FTS5 full-text search across titles, summaries, tags, notes + optional AI reranking.

```
pool search "xss"                                         # keyword search
pool search "ssrf" --domain web --skill beginner           # filtered search
pool search --domain cloud --type tutorial --limit 20      # browse by metadata
pool search --nl "find short beginner ssrf resources"      # natural language query -> AI reranked
```

**Options**: `--domain`, `--type`, `--skill`, `--format`, `--cost`, `--min-quality`, `--limit`, `--nl`

### `pool find [options]`
Filter by metadata without text search.

```
pool find --domain web --skill beginner
pool find --type video --state saved
```

### `pool get <id>`
Full details for a specific resource by ID.

```
pool get a1b2c3d4
```

### `pool recent [--limit]`
Most recently added resources.

### `pool random`
Surface a random resource — forgotten gem mode.

### `pool untouched [--limit]`
Resources still in `saved` state (never engaged with).

---

## Learning Management

### `pool rate <id> <score>`
Rate a resource 1-10.

### `pool state <id> <state>`
Track consumption progress. States: `saved` -> `skimmed` -> `studied` -> `mastered` -> `applied`

```
pool state a1b2c3d4 studied
pool state a1b2c3d4 applied
```

### `pool tag <id> <tags>`
Add comma-separated tags.

```
pool tag a1b2c3d4 "jwt,oauth,authentication-bypass"
```

### `pool note <id> <text>`
Append personal notes.

```
pool note a1b2c3d4 "Excellent explanation of JWT attacks — revisit before pentest"
```

### `pool use <id>`
Increment usage counter.

### `pool archive <id> [--hard]`
Soft-delete (archive) or hard-delete.

```
pool archive a1b2c3d4           # soft (restorable)
pool archive a1b2c3d4 --hard    # permanent
```

### `pool path <goal>`
Generate a structured learning path from your pool (requires AI).

```
pool path "become a bug bounty hunter in 3 months"
pool path "learn cloud security from scratch"
```

### `pool stack <mission>`
Generate a curated resource bundle for a specific mission (requires AI).

```
pool stack "first web application pentest"
pool stack "preparing for OSCP"
```

### `pool progress`
Learning progress dashboard: bar chart by consumption state, domain distribution.

---

## Review & Maintenance

### `pool due [--limit]`
Resources needing attention: stale (90+ days unverified), untouched (saved state), low AI confidence.

### `pool dedupe [--threshold]`
Scan for duplicate resources (fuzzy title match via rapidfuzz).

```
pool dedupe
pool dedupe --threshold 90       # stricter (default 85)
```

### `pool dead-check [--limit] [--auto-tombstone]`
Check resources for broken links. Resources unverified for 90+ days are HEAD-checked. Wayback Machine URLs captured for dead links.

```
pool dead-check
pool dead-check --limit 100
pool dead-check --auto-tombstone    # auto-archive confirmed dead
```

### `pool audit`
Full health report: stats, dead links, low-confidence resources, stale content, AI gap analysis.

### `pool watch [--interval] [--auto-tombstone]`
Continuous maintenance loop. Runs dead check + low-confidence reviews on a schedule.

```
pool watch                         # every 24h
pool watch --interval 12 --auto-tombstone
```

### `pool stats`
Quick pool statistics (domain/type/state breakdown).

### `pool gap [--report]`
Identify gaps in your pool via AI.

```
pool gap                           # quick gap list
pool gap --report                  # detailed report with domain coverage,
                                   # type gaps, skill levels, priority
                                   # recommendations, pool health score (0-100)
```

### `pool brief`
Daily AI briefing showing new resources, items due, stale/dead counts, recommended focus, random gem, and tip.

---

## Export & Visualization

### `pool graph [--format] [--output]`
Export resource relationship graph.

```
pool graph --format d3                                         # interactive HTML (default)
pool graph --format obsidian                                   # wiki-links + hub index in vault
pool graph --format d3 --output my-graph.html --min-weight 2   # only strong connections
```

**d3 format**: standalone HTML with D3.js force-directed graph. Color-coded by domain, sized by quality, draggable, hover tooltips with metadata.

**obsidian format**: adds `[[wiki-links]]` between related resources in existing vault notes + creates `resource-hub.md` index by domain.

### `pool anki [--output] [--domain] [--type]`
Export resources as Anki-importable CSV. Each resource becomes a card with title/URL on front, summary/details on back.

```
pool anki                                           # all resources
pool anki --domain web --limit 30                    # web resources only
pool anki --output my-deck.csv                       # custom filename
```

Import in Anki: File > Import > select CSV > set delimiter to comma.

### `pool site [--output]`
Generate a self-contained static HTML site from the resource pool.

```
pool site                                            # poolmind-site.html
pool site --output ~/Desktop/pool-report.html        # custom path
```

Output includes: stats bar, domain/state breakdown, random pick, full resource grid with types/tags/metadata.

---

## REST API

poolmind exposes a full REST API with ~50 endpoints under `/api/`. All return JSON.

### Resources

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/resources` | List (query: `domain`, `type`, `state`, `limit`, `offset`) |
| GET | `/api/resource/<id>` | Detail + related |
| POST | `/api/add` | Add by URL `{"url", "notes", "ai_disabled", "skip_notion", "skip_obsidian", "force"}` |
| POST | `/api/add/manual` | Manual `{"title", "url", "type", "domain", ...}` |
| PATCH | `/api/resource/<id>` | Update fields |
| DELETE | `/api/resource/<id>` | Archive/hard-delete `{"hard": true}` |

### Resource Actions

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/resource/<id>/rate` | `{"score": 4}` |
| POST | `/api/resource/<id>/state` | `{"state": "studied"}` |
| POST | `/api/resource/<id>/tags` | `{"tags": ["jwt"]}` |
| POST | `/api/resource/<id>/note` | `{"text": "..."}` |
| POST | `/api/resource/<id>/use` | Increment counter |
| POST | `/api/resource/<id>/correct` | `{"field", "old", "new"}` |
| POST | `/api/resource/<id>/sync` | Force Notion sync |
| POST | `/api/resource/<id>/re-extract` | Re-run extraction |

### Browse & Search

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/resources/random` | Random |
| GET | `/api/resources/untouched` | Saved state |
| GET | `/api/resources/recent` | Recent |
| GET | `/api/resources/by-state/<state>` | Filter by state |
| GET | `/api/search?q=` | Keyword + filters |
| POST | `/api/search/nl` | NL search `{"query"}` |

### Bulk Ingest

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/ingest/parse` | Parse text `{"text"}` |
| POST | `/api/ingest/run` | Run ingestion |
| POST | `/api/ingest/run/stream` | SSE streaming |

### Intelligence

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/paths/generate` | `{"goal"}` |
| GET | `/api/paths` | List saved |
| GET | `/api/paths/<id>` | Detail |
| DELETE | `/api/paths/<id>` | Delete |
| POST | `/api/stacks/generate` | `{"mission"}` |
| GET | `/api/stacks` | List saved |
| GET | `/api/stacks/<id>` | Detail |
| DELETE | `/api/stacks/<id>` | Delete |
| POST | `/api/gap` | Gap analysis |

### Maintenance

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/audit` | Full audit |
| POST | `/api/dedupe` | Find duplicates |
| POST | `/api/dead-check` | Check dead links |
| GET | `/api/dead-links` | List dead |
| GET | `/api/sync/notion/status` | Sync status |
| POST | `/api/sync/notion/run` | Run sync |
| GET | `/api/sync/notion/log` | Sync history |

### AI Prompts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/ai/prompts` | All task stats |
| GET | `/api/ai/prompts/<task>` | Task detail |
| POST | `/api/ai/evolve/preview` | Dry-run evolve |
| POST | `/api/ai/evolve/run` | Execute evolve |
| POST | `/api/ai/evolve/<task>/deploy` | Deploy prompt |
| POST | `/api/ai/prompts/<task>/restore` | Restore backup |
| GET | `/api/ai/corrections` | All corrections |

### Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/settings` | All config |
| PATCH | `/api/settings` | Update config `{"key", "value"}` |
| GET | `/api/settings/env` | Env vars |
| GET | `/api/settings/taxonomy` | Taxonomy |

---

## Web UI

### `pool serve [--host] [--port] [--debug]`
Start the poolmind Flask web UI.

```
pool serve                                           # http://127.0.0.1:5000
pool serve --port 8080                               # custom port
pool serve --host 0.0.0.0 --debug                    # network-accessible + debug
```

### Navigation

Top nav bar with dropdown menus:

| Section | Items |
|---------|-------|
| Dashboard | `/` — HUD stats, gem of the day, quick actions, domain/state tables, recent |
| + Add | Quick URL, Manual entry, Bulk ingest |
| Resources | All resources, Recent, Untouched, Random gem |
| Intelligence | Learning paths, Tech stacks, Gap analysis |
| Maintenance | Audit log, Deduplicate, Dead links, Notion sync |
| AI | Prompts, Corrections |
| Search | Keyword + NL |
| Settings | Configuration, Taxonomy |

### Pages

| Route | Description |
|-------|-------------|
| `/` | Dashboard — stat cards (total, domains, dead links, low conf), random gem card, 6 quick action links, domain/state tables, recent additions |
| `/add` | Quick URL — URL input + notes + checkboxes (disable AI, skip Notion/Obsidian, force). Async submission with progress |
| `/add/manual` | Manual entry — collapsible sections: Required (title, url, type), Classification (domain, subdomain, tags), Context (summary, notes, why_it_matters, skill_level) |
| `/ingest` | Bulk ingest — paste/upload tabs, preview table with checkboxes, run with options |
| `/resources` | All resources — filter bar (domain/type/state selects), data-table with ID, title, domain, type chip, skill, quality, state badge |
| `/resources/random` | Random gem card |
| `/resources/untouched` | Resources in saved state |
| `/resources/recent` | Recently added |
| `/resources/by-state/<s>` | Filtered by consumption state |
| `/resource/<id>` | 2-column detail: main (type, domain, summary, why, best_for/avoid_if, notes, related), sidebar (star rating 1-10, state select, tags, notes, mark used, correct AI, archive) + metadata table |
| `/resource/<id>/edit` | Full edit form |
| `/search` | Keyword + NL tabs. Keyword: text + filters + results with scores. NL: natural language query |
| `/intelligence/paths` | Saved learning paths table. Generate button opens modal, calls `/api/paths/generate` |
| `/intelligence/paths/<id>` | Path detail: goal, weekly breakdowns with resources, delete |
| `/intelligence/stacks` | Saved tech stacks table. Generate modal calls `/api/stacks/generate` |
| `/intelligence/stacks/<id>` | Stack detail: mission, description, resources, delete |
| `/intelligence/gap` | Gap analysis: run button calls `/api/gap`, displays coverage stats and recommendations |
| `/maintenance/audit` | Audit log table. Run audit button calls `/api/audit` |
| `/maintenance/dedupe` | Duplicate finder: find button calls `/api/dedupe`, shows pair cards with scores and archive |
| `/maintenance/dead-links` | Dead links table with wayback/resolve. Check button calls `/api/dead-check` |
| `/maintenance/sync` | Notion sync status + history. Sync button calls `/api/sync/notion/run` |
| `/ai/prompts` | Prompt dashboard: tasks grid with calls/success/confidence/corrections. Click for detail |
| `/ai/prompts/<task>` | Task detail: stats, evolution status, corrections. Preview/run evolve buttons |
| `/ai/corrections` | All user corrections table |
| `/settings` | Config table + env vars status + data ops |
| `/settings/taxonomy` | All domains, types, states, levels, formats, costs displayed as tags |

### Design

- **Palette**: deep navy base (`#0a0e1a`), electric blue accent (`#4d9fff`)
- **Fonts**: Inter (UI), JetBrains Mono (code/data)
- **Icons**: Lucide via CDN
- **Components**: HUD stat cards with corner brackets, `[BRACKETED]` status badges, color-coded type chips, star rating, modals, toast notifications

---

## Sync

### `pool sync-notion [--batch]`
Push unsynced resources to Notion.

```
pool sync-notion
pool sync-notion --batch 5       # process 5 at a time
```

One-way sync: local SQLite -> Notion. Property mapping in `config/notion.yaml`.

---

## Resource Types (36)

```
article     tutorial    writeup     tool        repository
cheatsheet  book        course      video       playlist
paper       report      dataset     lab         ctf
framework   table       index       ranking     note
thread      newsletter  podcast     interview   config
template    extension   dashboard   search_engine  api
community   event       certification glossary   mindmap
other
```

## Domains (29)

```
web         network     mobile      cloud       api
wireless    iot         osint       soc         blueteam
redteam     purpleteam  malware     forensics   cryptography
reverse_engineering  exploit_dev  social_engineering  physical
governance  privacy     ai_security supply_chain  devsecops
identity    blockchain  ics_ot      career      general
```

## Skill Levels

```
beginner    intermediate    advanced    expert    all
```

## Consumption States

```
saved   ->   skimmed   ->   studied   ->   mastered   ->   applied
```

---

## Architecture

```
User URL
  |
  v
[1] Normalize URL ------------------- strip tracking, canonicalize, wayback
  |
  v
[2] Dedupe check -------------------- URL exact match -> fuzzy title match (rapidfuzz)
  |
  v
[3] Extract metadata ---------------- article (readability) / GitHub (PyGithub+REST)
  |                                   YouTube (yt-dlp) / PDF (pymupdf)
  |                                   HackerOne / Bugcrowd (BS4)
  v
[4] Heuristic classify -------------- 6-pass rules engine (0 AI needed)
  |    URL patterns 25pts             type, domain, subdomain,
  |    platform 15pts                 skill level, temporal relevance
  |    domain keywords 20pts
  |    subdomain 10pts
  |    skill level 5pts
  |    temporal 5pts
  |
  +-- confidence >= 70? ------------- skip AI, use heuristic
  |
  +-- confidence < 70? -------------- AI enrichment (freellmapi -> OpenAI)
  |     classify -> summarize -> tag -> relate
  v
[5] Normalize fields ---------------- sanitize, strip internal fields
  |
  v
[6] Validate (Pydantic) ------------- URS schema v1.0 (65 fields)
  |
  v
[7] SQLite + FTS5 ------------------- 7 tables, FTS5 triggers, 8 indexes
  |
  +-- [8] Obsidian note ------------- YAML frontmatter + Dataview + wiki-links
  |
  +-- [9] Notion sync --------------- one-way push (if configured)
  |
  x -- [10] Graph export ------------ D3.js HTML / Obsidian wiki-links (on-demand)
  x -- [11] Anki export ------------- CSV deck (on-demand)
  x -- [12] Static site ------------- HTML page (on-demand)
```

**Self-adapting prompts**: poolmind tracks every AI response confidence, user corrections, response times, and field coverage. When a task's success rate drops below 80% or user correction rate exceeds 15%, the evolution system generates a new prompt version, backs up the old one, and can deploy it. Prompt files are plain Markdown with `{{ variable }}` placeholders, stored under `prompts/`.

**Rules-first, AI-second**: Heuristics run before any AI call. AI is only called when heuristic confidence < threshold (default 70). Fully functional offline with no AI dependency.

---

## Obsidian Integration

Each resource becomes a markdown note in `vault/Resources/`:

```
vault/Resources/
+-- resource-a1b2c3d4-payloadsallthethings.md
+-- resource-e5f6g7h8-web-hacking-101.md
+-- resource-hub.md                 # index (generated by pool graph)
```

Each note includes:
- **YAML frontmatter** (all 40+ URS fields — queryable by Dataview plugin)
- **Summary, Why It Matters, Best For, Avoid If** sections
- **Tags** with `#` prefix
- **Related Resources** section with `[[wiki-links]]` (after running `pool graph --format obsidian`)
- **Dataview block** (auto-generated same-domain resource query)

---

## Notion Integration

One-way sync: local SQLite -> Notion. Notion is the dashboard — local is source of truth.

1. Create integration: https://www.notion.so/my-integrations
2. Share your database with the integration
3. Set `NOTION_TOKEN` and `NOTION_DATABASE_ID` in `.env`
4. Resources sync on add, or manually via `pool sync-notion`

Property mapping: `config/notion.yaml` (28 mapped properties).

---

## AI Integration (Optional)

### Option A: freellmapi (local, free)
```bash
# Clone and run
git clone https://github.com/tashfeenahmed/freellmapi
cd freellmapi && npm install && npm start
# -> http://localhost:3001/v1/chat/completions
```

Set in `.env`:
```
FREELLMAPI_URL=http://localhost:3001
FREELLMAPI_MODEL=llama3
```

### Option B: OpenAI (cloud, paid)
```
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
FREELLMAPI_MODEL=gpt-4o-mini
```

**Fallback chain**: freellmapi -> OpenAI. First available is used.

**AI handles**: classification, summarization, tag generation, query parsing, related resource suggestions, learning path generation, stack building, gap analysis, gap reports, daily briefings, search reranking.

Responses are cached by input hash in SQLite — identical requests skip API calls.

---

## Tips

- **Add a resource every time you find something useful** — the pool grows organically
- **Rate and tag everything** — enables powerful filtered search and AI recommendations
- **Use `pool random` daily** — rediscover forgotten gems
- **Update consumption state** — `pool due` and `pool progress` depend on accurate states
- **Run `pool audit` weekly** — catch dead links early
- **`pool brief` daily** — start your morning with a pool summary
- **`pool graph --format d3`** — visualize connections between your resources
- **`pool serve`** — browser dashboard for browsing without the CLI
- **Obsidian + Dataview** — build custom dashboards from resource frontmatter
- **Run `pool graph --format obsidian` after adding resources** — keeps wiki-links fresh

---

## Command Summary (35+)

| Command | Purpose |
|---------|---------|
| `init` | Initialize SQLite database |
| `add` | Add resource by URL (full pipeline) |
| `add-manual` | Add resource manually |
| `ingest` | Smart bulk parser (9 input formats) |
| `bulk` | Legacy bulk add URLs from file/stdin |
| `search` | Full-text search + AI reranking |
| `find` | Filter by metadata |
| `get` | Resource detail by ID |
| `recent` | Recently added |
| `random` | Random forgotten gem |
| `untouched` | Never-used resources |
| `rate` | Rate 1-10 |
| `note` | Append personal notes |
| `state` | Update consumption state |
| `tag` | Add tags |
| `correct` | Log AI field correction |
| `archive` | Soft/hard delete |
| `use` | Increment usage counter |
| `path` | AI learning path |
| `stack` | AI mission bundle |
| `gap` | AI gap analysis (+ `--report`) |
| `brief` | AI daily briefing |
| `graph` | D3/Obsidian graph export |
| `dedupe` | Find duplicates |
| `due` | Resources due for review |
| `progress` | Learning progress chart |
| `dead-check` | Check broken links |
| `audit` | Full pool audit |
| `stats` | Pool statistics |
| `watch` | Continuous maintenance |
| `prompt-evolve` | Run AI prompt evolution |
| `prompt-stats` | Show AI prompt statistics |
| `prompt-corrections` | Show user corrections |
| `serve` | Web UI (Flask) |
| `anki` | Anki CSV export |
| `site` | Static HTML site |
| `sync-notion` | Push to Notion |

---

## File Tree

```
poolmind/
+-- app/
|   +-- __init__.py            Env loading, logging
|   +-- cli.py                 35+ typer commands
|   +-- add_resource.py        14-step ingestion pipeline
|   +-- extractors.py          7 extractors (article, GitHub, YouTube, PDF, H1, Bugcrowd)
|   +-- classifier.py          6-pass heuristic classifier
|   +-- freellm_tasks.py       13 AI task wrappers + cache
|   +-- normalizer.py          URL normalization, mirroring
|   +-- db.py                  Full CRUD, stats, AI cache, FTS5, pool_config
|   +-- obsidian_writer.py     YAML frontmatter note writer
|   +-- notion_sync.py         One-way Notion push + get_sync_status/log
|   +-- search.py              FTS5 + metadata + NL + AI rerank + browse
|   +-- dedupe.py              URL + fuzzy title dedup
|   +-- audit.py               Dead check, gap analysis, low confidence
|   +-- graph.py               D3.js + Obsidian graph export
|   +-- webui.py               Flask web UI (all routes)
|   +-- anki.py                Anki CSV deck export
|   +-- sitegen.py             Static HTML site generator
|   +-- bulk_parser.py         Smart input parser (9 formats)
|   +-- ingest_router.py       Ingestion router
|   +-- feedback_tracker.py    AI feedback + correction tracking
|   +-- prompt_evolution.py    Self-adapting prompt evolution
|   +-- api/                   REST API (~50 endpoints)
|       +-- __init__.py        Blueprint registration hub
|       +-- resources.py       CRUD + actions (14 endpoints)
|       +-- ingest.py          Parse + run + SSE (3 endpoints)
|       +-- search.py          Keyword + NL (2 endpoints)
|       +-- browse.py          Random/untouched/recent/by-state (4)
|       +-- intelligence.py    Paths, stacks, gap (9 endpoints)
|       +-- maintenance.py     Audit, dedupe, dead-links, notion (7)
|       +-- ai_prompts.py      Prompt stats, evolve, corrections (7)
|       +-- settings.py        Config, env, taxonomy (4)
+-- models/resource.py         URS Pydantic model (65 fields)
+-- prompts/                   14 AI prompt .md files
+-- config/
|   +-- settings.yaml          App config
|   +-- taxonomy.yaml          36 types, 29 domains, URL patterns
|   +-- notion.yaml            28 Notion property mappings
+-- scripts/
|   +-- init_db.py             DB schema (7 tables, FTS5, triggers, indexes)
|   +-- scheduler.py           Maintenance loop (dead check, watch mode)
+-- templates/                 20 Flask HTML templates
+-- static/style.css           Design system v1.0 CSS
+-- vault/Resources/           Obsidian notes
+-- data/poolmind.db           SQLite database
+-- data/learning_paths.json   Saved learning paths
+-- data/resource_stacks.json  Saved tech stacks
+-- pool.sh                    Bash wrapper
+-- pool.cmd                   CMD wrapper
+-- .env.example
+-- .gitignore
+-- requirements.txt
```
