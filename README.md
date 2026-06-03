# poolmind — Cybersecurity Resource Pool

**poolmind** is a personal knowledge base for cybersecurity professionals, researchers, and learners. It helps you **collect, organize, enrich, search, and rediscover** cybersecurity resources — articles, tools, writeups, books, courses, CTFs, videos, and anything else you find useful.

---

## Features

- **Smart ingestion** — paste any URL; poolmind auto-extracts title, summary, tags, domain, type, skill level via heuristics + optional AI
- **Full-text search** — FTS5 across titles, summaries, tags, notes, with AI-powered natural language query support
- **Bulk import** — ingest from files, bookmarks, clipboard — auto-detects 9 input formats (URLs, markdown links, CSV, etc.)
- **Learning management** — track consumption state per resource (saved → skimmed → studied → mastered → applied), rate 1-10, add notes/tags
- **AI enrichment** — optional AI for classification, summarization, tag generation, quality scoring, gap analysis, learning paths, tech stacks, daily briefings
- **Intelligence** — generate AI-curated learning paths and tech stacks from your existing pool
- **Smart Trash Bin** — soft delete with restore, undo toast (10s window), bulk purge, nuke with backup, URL conflict detection on restore
- **Auto-purge** — configurable automatic cleanup of expired trash via scheduler
- **Duplicate detection** — fuzzy title matching via rapidfuzz
- **Dead link checker** — HEAD-check stale resources, capture Wayback Machine URLs
- **Obsidian sync** — each resource becomes a markdown note with YAML frontmatter + Dataview queries
- **Notion sync** — one-way push to a Notion database dashboard
- **Export** — Anki CSV decks, static HTML site, D3.js interactive graph, Obsidian wiki-link graph
- **Self-adapting prompts** — AI prompts evolve based on success rates and user corrections
- **REST API** — 50+ JSON endpoints for every operation
- **Full audit trail** — every add, edit, trash, restore, purge is logged

---

## Quick Start

```
git clone https://github.com/itzneel05/poolmind.git
cd poolmind
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python -m app.webui
```

Open **http://localhost:5000**

For AI features, poolmind uses [freellmapi](https://github.com/tashfeenahmed/freellmapi) — a free AI proxy that aggregates 16+ LLM providers:
```
git clone https://github.com/tashfeenahmed/freellmapi.git
cd freellmapi && npm install && npm run dev
```

See [SETUP.md](SETUP.md) for the full walkthrough.

---

## Stack

- **Backend**: Python / Flask
- **Database**: SQLite + FTS5
- **Frontend**: HTMX + vanilla JS
- **AI Proxy**: freellmapi (Google Gemini, Groq, Cerebras, OpenRouter, 13+ more)
- **AI Models**: optional — OpenAI, Ollama, or any OpenAI-compatible endpoint

---

## Docs

- [SETUP.md](SETUP.md) — everything you need to get running
- [USAGE.md](USAGE.md) — API endpoints and CLI commands
- [GUIDE.md](GUIDE.md) — tour of the web UI
- [ARCHITECTURE.md](ARCHITECTURE.md) — how it all fits together
