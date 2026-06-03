# poolmind — Cybersecurity Resource Pool

Your personal library for organizing, enriching, and rediscovering everything you learn about cybersecurity.

```
  ╔═══════════════════════════════════════════════════╗
  ║  poolmind — Cybersecurity Resource Pool v2.0      ║
  ║  your brain's external hard drive for security    ║
  ╚═══════════════════════════════════════════════════╝
```

---

## What is poolmind?

poolmind is a tool that helps you **collect, organize, and learn from** cybersecurity resources — articles, tools, writeups, books, courses, videos, and anything else you find useful.

Think of it as a **smart bookmark manager on steroids**:
- Save a URL and it automatically extracts the title, summary, tags, and domain
- AI enriches everything with why-it-matters, skill level, and quality scores
- Search across all your resources with keywords or natural language
- Get AI-generated learning paths and gap analysis
- Export to Obsidian, Notion, Anki, or a static HTML site

---

## Quick Start (5 minutes)

### 1. Install

```bash
# Open a terminal in the poolmind folder
cd poolmind

# Create a virtual environment (isolated Python)
python -m venv .venv

# Activate it
.venv\Scripts\activate          # Windows
source .venv/bin/activate        # Mac / Linux

# Install dependencies
pip install -r requirements.txt

# Initialize the database
python scripts/init_db.py
```

### 2. Add your first resource

```bash
# Using the wrapper (Windows)
pool add https://github.com/swisskyrepo/PayloadsAllTheThings

# Or directly
python -m app.cli add https://github.com/swisskyrepo/PayloadsAllTheThings
```

### 3. Open the web dashboard

```bash
pool serve
# Open http://127.0.0.1:5000 in your browser
```

That's it. You now have a working resource library.

---

## One-Click Start (Easiest)

If you have everything installed, just double-click **`start.cmd`** in the `poolmind` folder. It will:

1. Start the AI backend (freellmapi) in a separate window
2. Wait 8 seconds for it to boot
3. Start the web UI at `http://127.0.0.1:5000`

To stop everything: run **`stop.cmd`** or close the terminal windows.

---

## The Four Ways to Add Resources

### Way 1: Quick URL (Web UI)

1. Open the dashboard at `http://127.0.0.1:5000`
2. Click **"+ Add"** in the nav bar, then **"Quick URL"**
3. Paste a URL and click **"Add Resource"**
4. Watch the progress panel — extraction, classification, AI enrichment

Optional checkboxes:
- **Disable AI enrichment** — faster, uses rules only (no AI)
- **Skip Notion sync** — don't push to Notion
- **Skip Obsidian** — don't create an Obsidian note
- **Force** — skip duplicate check

### Way 2: Manual Entry (Web UI)

1. Click **"+ Add" > "Manual entry"**
2. Fill in the required fields (Title, URL, Type)
3. Expand the **Classification** and **Context** sections to add tags, domain, summary, notes
4. Click **"Add Resource"**

### Way 3: CLI

```bash
# Add a URL (full pipeline: extract + classify + AI enrich)
pool add https://example.com/article

# Skip AI (faster)
pool add https://example.com/article --no-ai

# Add with personal notes
pool add https://example.com/article -n "Great explanation of JWT attacks"

# Add manually (book, note, local resource)
pool add-manual --title "Practical Malware Analysis" --type book --domain malware

# Bulk add from a file
pool ingest -f urls.txt
```

### Way 4: Bulk Ingest (Web UI)

1. Click **"+ Add" > "Bulk ingest"**
2. Paste multiple URLs (one per line) or upload a file
3. Click **"Preview"** to see what was parsed
4. Check the entries you want, click **"Ingest"**

poolmind automatically detects the input format:
```
# Plain URLs
https://example.com/article1
https://example.com/article2

# Markdown links
[Article Title](https://example.com)

# Named format
Article Title: https://example.com

# CSV-ish
https://example.com, notes about this resource
```

---

## Exploring Your Library

### Dashboard

When you open `http://127.0.0.1:5000`, you'll see:

| Section | What it shows |
|---------|---------------|
| **Stats** | Total resources, domains covered, dead links, low-confidence items |
| **Services** | AI API status (`[ONLINE]`/`[OFFLINE]`), Notion sync status, AI call count |
| **Gem of the Day** | A random resource you might have forgotten about |
| **Quick Actions** | Links to add, random gem, untouched, recent |
| **By Domain** | How many resources per security domain |
| **By State** | How many resources in each consumption state |
| **Recent Additions** | Your most recently added resources |

### Browsing Resources

Click **"Resources"** in the nav bar, then choose:

| Page | What you see |
|------|-------------|
| **All resources** | Table with ID, title, domain, type, skill level, quality score, state. Use the filter bar to narrow by domain, type, or state |
| **Recent** | Most recently added |
| **Untouched** | Resources you saved but haven't looked at yet |
| **Random gem** | One random resource — great for rediscovery |

### Viewing a Resource

Click any resource to see its **detail page**. It has two columns:

**Left (main):**
- Type chip (color-coded) and domain tag
- Summary (full paragraph)
- Why it matters
- Best for / Avoid if
- Notes you've added
- Related resources

**Right (sidebar):**

| Action | How it works |
|--------|-------------|
| **Star rating** | Click a star (1-10) to rate the resource |
| **State** | Dropdown: saved → skimmed → studied → mastered → applied |
| **Tags** | Type a tag and click "+" to add it |
| **Notes** | Write notes and click "Save note" |
| **Mark used** | Increments the usage counter |
| **Correct AI field** | Opens a modal to fix any AI-generated field |
| **Archive** | Soft-deletes the resource |

### Searching

The **Search** page has two tabs:

- **Keyword** — Type a query, optionally filter by domain and type. Results show relevance scores
- **Natural Language** — Type a question like "find short beginner resources about SSRF" and AI finds relevant results

---

## Intelligence Features

### Learning Paths

Generate a structured learning path from your existing resources:

1. Go to **"Intelligence > Learning paths"** in the nav
2. Click **"Generate new path"**
3. Type a goal like "learn web application pentesting from scratch"
4. AI analyzes your pool and creates a week-by-week path using your resources

### Tech Stacks

Similar to paths but focused on a mission:

1. Go to **"Intelligence > Tech stacks"**
2. Click **"Generate new stack"**
3. Type a mission like "build a cloud security monitoring pipeline"
4. AI curates a bundle of your resources for that mission

### Gap Analysis

See what areas your pool is missing:

1. Go to **"Intelligence > Gap analysis"**
2. Click **"Run analysis"**
3. Displays coverage stats (domains covered, total resources, recommendations)

---

## Maintenance

### Audit Log

Every action is recorded. Go to **"Maintenance > Audit log"** to see a timeline of adds, edits, archives, and syncs.

### Find Duplicates

1. Go to **"Maintenance > Deduplicate"**
2. Click **"Find duplicates"**
3. Shows pairs of similar resources with match percentage
4. Click "Archive" to remove duplicates

### Dead Links

1. Go to **"Maintenance > Dead links"**
2. Click **"Check now"** to test all links
3. Shows dead links with HTTP status, Wayback Machine link, and a Resolve button

### Notion Sync

1. Go to **"Maintenance > Notion sync"**
2. See sync status and history
3. Click **"Sync now"** to push unsynced resources to Notion

---

## Settings

### Configuration

The **Settings** page has two sections:

- **Configuration** — key-value pairs stored in the database
- **Environment** — environment variables from your `.env` file

To edit any setting, click the "Edit" button next to it. Environment variable changes are saved to `.env` and take effect immediately.

### Notion Sync Setup

In the **Notion Sync** section of Settings:

1. Click **"Set"** next to `NOTION_TOKEN` and paste your Notion integration token
2. Click **"Edit"** next to `NOTION_DATABASE` and enter your database ID
3. Toggle `NOTION_SYNC_ENABLED` to `true`
4. Click **"Test connection"** to verify everything works

### Taxonomy

The **Taxonomy** page shows all valid values for domains (29), types (36+), states, skill levels, formats, and costs.

---

## Design System

poolmind uses a dark, terminal-inspired design:

- **Background**: Deep navy (`#0a0e1a`)
- **Accent**: Electric blue (`#4d9fff`)
- **Fonts**: Inter for UI, JetBrains Mono for code and data
- **Icons**: Lucide (loaded from CDN)
- **Badges**: Terminal-style `[BRACKETED]` status indicators
- **Type chips**: Color-coded by resource type
- **Cards**: HUD-style with corner bracket decorations
- **Transitions**: 150ms smooth

---

## CLI Reference

### Quick Wrappers

```bash
# Windows
pool <command>

# Git Bash
./pool.sh <command>
```

### All Commands

| Command | What it does |
|---------|--------------|
| `pool init` | Initialize or reset the database |
| `pool add <url>` | Add a resource by URL |
| `pool add-manual -t "Title"` | Add a resource manually |
| `pool ingest -f file` | Smart bulk import (auto-detects format) |
| `pool bulk -f file` | Legacy simple bulk import |
| `pool search "query"` | Full-text search |
| `pool find --domain web` | Filter resources by metadata |
| `pool get <id>` | Show full resource details |
| `pool recent` | Show recently added |
| `pool random` | Show a random resource |
| `pool untouched` | Show never-used resources |
| `pool rate <id> <score>` | Rate 1-10 |
| `pool state <id> <state>` | Update consumption state |
| `pool tag <id> "tags"` | Add tags |
| `pool note <id> "text"` | Add a note |
| `pool use <id>` | Mark as used |
| `pool correct <id> --field type --new article` | Correct an AI field |
| `pool archive <id>` | Soft-delete |
| `pool path "goal"` | Generate a learning path |
| `pool stack "mission"` | Generate a tech stack |
| `pool gap` | Run gap analysis |
| `pool brief` | Daily AI briefing |
| `pool stats` | Show pool statistics |
| `pool dedupe` | Find duplicates |
| `pool dead-check` | Check dead links |
| `pool audit` | Full health report |
| `pool watch` | Continuous maintenance loop |
| `pool serve` | Start web UI |
| `pool graph --format d3` | Export resource graph |
| `pool anki` | Export Anki deck CSV |
| `pool site` | Export static HTML site |
| `pool sync-notion` | Push to Notion |

---

## REST API

poolmind has a full REST API (50+ endpoints) at `http://localhost:5000/api/`. Every web UI action calls these endpoints — you can use them directly too.

### Quick Example

```bash
# List all resources
curl http://localhost:5000/api/resources

# Add a resource
curl -X POST http://localhost:5000/api/add \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","ai_disabled":true}'

# Rate a resource
curl -X POST http://localhost:5000/api/resource/abc12345/rate \
  -H "Content-Type: application/json" \
  -d '{"score":8}'

# Search
curl "http://localhost:5000/api/search?q=ssrf"
```

### Endpoint Categories

| Category | Endpoints |
|----------|-----------|
| **Resources** | GET/POST/PATCH/DELETE `/api/resource/<id>` |
| **Actions** | `/rate`, `/state`, `/tags`, `/note`, `/use`, `/correct`, `/sync`, `/re-extract` |
| **Browse** | `/random`, `/untouched`, `/recent`, `/by-state/<state>` |
| **Search** | GET `/api/search?q=`, POST `/api/search/nl` |
| **Ingest** | POST `/api/ingest/parse`, `/run`, `/run/stream` |
| **Intelligence** | `/api/paths/*`, `/api/stacks/*`, `/api/gap` |
| **Maintenance** | `/api/audit`, `/dedupe`, `/dead-check`, `/dead-links`, `/sync/notion/*` |
| **AI Prompts** | `/api/ai/prompts`, `/ai/evolve/*`, `/ai/corrections` |
| **Settings** | GET/PATCH `/api/settings`, `/api/settings/env`, `/taxonomy` |

---

## AI Integration

poolmind uses AI for:
- Classification (type, domain, skill level)
- Summarization (paragraph-length summaries)
- Tag generation
- Learning paths and tech stacks
- Gap analysis
- Natural language search
- Quality scoring

### Option A: freellmapi (free, local)

```bash
# In a separate terminal:
cd freellmapi
npm install
npm run dev
# -> http://localhost:3001
```

Set in `.env`:
```
FREELLMAPI_URL=http://localhost:3001
FREELLMAPI_MODEL=auto
```

### Option B: OpenAI (cloud, paid)

Set in `.env`:
```
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

### How AI Works

1. **Heuristics run first** — URL patterns, keywords, platform detection
2. **If confidence >= 70%** — use heuristic, skip AI (fast, offline)
3. **If confidence < 70%** — call AI for classification, summary, tags
4. **Every AI response is tracked** — confidence, field coverage, user corrections
5. **Prompt evolution** — if quality drops, the system suggests improved prompts

The dashboard shows AI API status (`[ONLINE]`/`[OFFLINE]`) so you always know if AI is available.

---

## Consumption States

Track your progress through each resource:

```
saved  →  skimmed  →  studied  →  mastered  →  applied
```

- **saved**: Bookmarked but not looked at yet
- **skimmed**: Quick scan, got the gist
- **studied**: Read/watched thoroughly
- **mastered**: You can explain it to someone else
- **applied**: Used it in a real project or test

---

## Tips for Daily Use

1. **Add something every day** — Even one link a day builds a valuable library
2. **Rate and tag everything** — Makes search and AI recommendations much better
3. **Check "Untouched" weekly** — Rediscover things you meant to read
4. **Update consumption state** — So `pool due` and the dashboard know what needs attention
5. **Run `pool audit` weekly** — Catch dead links before you need them
6. **Use the random gem** — Start each session by rediscovering something
7. **Run gap analysis monthly** — See what domains you're neglecting
8. **The dashboard tells you everything** — Start there, navigate into what needs attention

---

## File Structure

```
poolmind/
├── app/                        # Python backend
│   ├── api/                    # REST API (50+ endpoints)
│   ├── cli.py                  # CLI commands
│   ├── webui.py                # Flask web UI routes
│   ├── add_resource.py         # Resource ingestion pipeline
│   ├── extractors.py           # URL content extractors
│   ├── classifier.py           # Heuristic classifier
│   ├── freellm_tasks.py        # AI task wrappers
│   ├── db.py                   # Database operations
│   ├── search.py               # Search engine
│   └── ...                     # 15+ more modules
├── templates/                  # 20 HTML templates
├── static/style.css            # Design system CSS
├── prompts/                    # 14 AI prompt files
├── data/poolmind.db            # SQLite database
├── start.cmd                   # One-click launcher
├── stop.cmd                    # One-click stopper
├── pool.cmd / pool.sh          # CLI wrappers
└── .env                        # Environment variables
```
