# poolmind — Complete Setup Guide

This guide covers every step: installing dependencies, configuring **freellmapi** (the AI proxy that powers poolmind), getting API keys from 16+ free LLM providers, setting up Notion/Obsidian sync, and running poolmind for the first time.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start (TL;DR)](#quick-start-tldr)
- [1. Clone & Install poolmind](#1-clone--install-poolmind)
- [2. Set Up freellmapi (AI Proxy)](#2-set-up-freellmapi-ai-proxy)
- [3. Get Provider API Keys](#3-get-provider-api-keys)
- [4. Add Keys to freellmapi Dashboard](#4-add-keys-to-freellmapi-dashboard)
- [5. Configure poolmind (.env)](#5-configure-poolmind-env)
- [6. Set Up Notion Sync (Optional)](#6-set-up-notion-sync-optional)
- [7. Set Up Obsidian Sync (Optional)](#7-set-up-obsidian-sync-optional)
- [8. Run Everything](#8-run-everything)
- [9. Verify It Works](#9-verify-it-works)

---

## Prerequisites

| Tool | Version | Why |
|---|---|---|
| Python | 3.13+ | poolmind backend |
| Node.js | 20+ | freellmapi (AI proxy) |
| npm | 10+ | freellmapi dependencies |
| Git | any | clone repos |

Check your versions:

```bash
python --version
node --version
npm --version
git --version
```

> **Windows users:** Use **Command Prompt** or **PowerShell** (not WSL). The `start.cmd` script launches both services in separate windows.

---

## Quick Start (TL;DR)

```bash
# 1. Clone poolmind
git clone https://github.com/itzneel05/poolmind.git
cd poolmind

# 2. Set up Python environment
python -m venv .venv
.venv\Scripts\activate && pip install -r requirements.txt    # Windows
source .venv/bin/activate && pip install -r requirements.txt  # macOS/Linux
cp .env.example .env

# 3. Clone freellmapi INSIDE poolmind
git clone https://github.com/tashfeenahmed/freellmapi.git
cd freellmapi
npm install
node -e "fs=require('fs');fs.writeFileSync('.env','ENCRYPTION_KEY='+require('crypto').randomBytes(32).toString('hex')+'\nPORT=3001\n')"
npm run dev
#   └─ Open http://localhost:5173, create account, add API keys

# 4. Open a NEW terminal, cd back to poolmind/, edit .env:
#    set FREELLMAPI_API_KEY to the unified key from the dashboard
python -m app.webui
# Open http://localhost:5000
```

---

## 1. Clone & Install poolmind

```bash
git clone https://github.com/itzneel05/poolmind.git
cd poolmind
```

**Create a virtual environment and install dependencies:**

```bash
python -m venv .venv

# Windows:
.venv\Scripts\activate

# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

**Copy the example environment file:**

```bash
cp .env.example .env
```

Leave `.env` uncommitted — it contains real secrets and is already in `.gitignore`. We'll fill it in step [5](#5-configure-poolmind-env).

---

## 2. Set Up freellmapi (AI Proxy)

poolmind uses **freellmapi** — an OpenAI-compatible proxy that aggregates free tiers from 16+ LLM providers behind a single endpoint. You run it locally alongside poolmind.

### Clone and install

```bash
# Make sure you're inside the poolmind directory first
# (skip this if you're already there from section 1)
cd /path/to/poolmind

git clone https://github.com/tashfeenahmed/freellmapi.git
cd freellmapi
npm install
```

### Generate encryption key and start

```bash
# Generate a 64-char hex encryption key for at-rest key storage
node -e "fs=require('fs');fs.writeFileSync('.env','ENCRYPTION_KEY='+require('crypto').randomBytes(32).toString('hex')+'\nPORT=3001\n')"
```

**Start freellmapi:**

```bash
npm run dev
```

This starts two things:
- **API server** on `http://localhost:3001`
- **Dashboard (Vite dev server)** on `http://localhost:5173`

Leave this terminal running. The first time you open the dashboard, you'll be asked to create an admin account (email + password). This is local-only — no data leaves your machine.

> **Windows tip:** If you prefer one-click startup, poolmind's `start.cmd` launches both freellmapi and poolmind together. See [Run Everything](#8-run-everything).

---

## 3. Get Provider API Keys

freellmapi can route requests through any of 16+ providers. You only need **one** to get started — add more later to increase your daily token budget and get fallback redundancy.

### Must-have providers (easiest to set up)

| Provider | Free Tier | Sign Up |
|---|---|---|
| **Google Gemini** | 1,500 RPM, 1M+ tokens/day | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) — click "Get API key" |
| **Groq** | 30 RPM, 14,400 RPD, ~6M tokens/day | [console.groq.com/keys](https://console.groq.com/keys) — "Create API Key" |
| **Cerebras** | 30 RPM, 14,400 RPD | [cloud.cerebras.ai](https://cloud.cerebras.ai) — sign up, go to API keys |
| **OpenRouter** | Aggregate of 21 free models | [openrouter.ai/keys](https://openrouter.ai/keys) — "Create Key" |

### High-value additions

| Provider | Free Tier | Sign Up |
|---|---|---|
| **SambaNova** | 100 RPM, ~2M tokens/day | [cloud.sambanova.ai](https://cloud.sambanova.ai) — API keys page |
| **Mistral** | 500 RPM, 1B tokens/month (capped) | [console.mistral.ai](https://console.mistral.ai) — API keys |
| **GitHub Models** | GPT-4.1, GPT-4o free (with PAT) | [github.com/settings/tokens](https://github.com/settings/tokens) — generate a classic PAT with `read:user` scope |
| **Cloudflare** | 10k requests/day | [dash.cloudflare.com](https://dash.cloudflare.com) — Workers AI > API Keys |
| **HuggingFace** | 30 RPM, 1M tokens/day | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) — "New token" with `read` role |
| **NVIDIA NIM** | 1k requests/day (evaluation) | [build.nvidia.com](https://build.nvidia.com) — sign up, API keys page |
| **Cohere** | 100 calls/min (trial) | [dashboard.cohere.com](https://dashboard.cohere.com) — API keys |
| **Z.ai (Zhipu)** | 500 RPM, 1M tokens/day | [open.bigmodel.cn](https://open.bigmodel.cn) — API keys (Chinese site, use browser translate) |

### Anonymous providers (no key needed)

These work without any API key — just enable them in the freellmapi fallback chain:

| Provider | Notes |
|---|---|
| **Pollinations** | GPT-OSS 20B, anonymous |
| **Kilo Gateway** | Free routes, anonymous |
| **LLM7** | GPT-OSS, Llama 3.1, anonymous |

### Local providers (no internet needed)

| Provider | Notes |
|---|---|
| **Ollama** | Run models locally via `ollama pull <model>`. freellmapi detects a local Ollama. **No API key needed.** |

### Tips for managing keys

- **Start with 2-3 providers** (e.g., Google Gemini + Groq + Cerebras). You can always add more.
- freellmapi rotates through providers automatically — if one is rate-limited, it falls over to the next.
- Keys are encrypted at rest (AES-256-GCM) before being stored in freellmapi's SQLite database.
- The unified API key (bearer token) is the **only key poolmind ever sees**. Your provider keys are never exposed to poolmind.

---

## 4. Add Keys to freellmapi Dashboard

1. Open **http://localhost:5173** in your browser
2. **Create an admin account** on first visit (email + password — stored locally)
3. Navigate to the **Keys** page (left sidebar)
4. For each provider you signed up for:
   - Click the **+ Add Key** button (or the provider's add button)
   - Paste the API key from the provider's dashboard
   - The status dot should turn green after the health check runs
5. Navigate to the **Fallback Chain** page
   - Drag providers into your preferred priority order
   - Gemini 2.5 Flash at the top is a good default (high caps, strong model)
   - Anonymous providers (Pollinations, Kilo, LLM7) at the bottom as catch-alls
6. Go back to the **Keys** page
   - Copy the **unified API key** from the header — it looks like `freellmapi-<64 hex chars>`
   - This is the key you put in poolmind's `.env`

---

## 5. Configure poolmind (.env)

Open `.env` (in the poolmind root directory) in a text editor. Here's every variable explained:

### AI Configuration

```env
# REQUIRED: freellmapi endpoint URL (default local port 3001)
FREELLMAPI_URL=http://localhost:3001

# REQUIRED: Your unified API key from the freellmapi Keys page
FREELLMAPI_API_KEY=freellmapi-your-64-char-key-here

# Model to use. "auto" lets freellmapi pick the best available.
# You can pin a specific model: gemini-2.5-flash, llama-4-scout, etc.
FREELLMAPI_MODEL=auto

# Set to false to disable AI features entirely (manual mode only)
AI_ENABLED=true

# Minimum AI confidence (0-100) below which results are flagged
AI_CONFIDENCE_THRESHOLD=70
```

### Optional: OpenAI Fallback

```env
# Optional: fallback OpenAI-compatible API (e.g., if freellmapi is down)
# Leave blank to use freellmapi only
OPENAI_API_KEY=
```

### GitHub (optional)

```env
# Optional: GitHub personal access token for richer repo metadata
# Increases API rate limit from 60 to 5000 requests/hour
# Create at: https://github.com/settings/tokens (classic PAT, no scopes needed)
GITHUB_TOKEN=
```

### Notion Sync (see step 6)

```env
NOTION_TOKEN=
NOTION_DATABASE=
NOTION_SYNC_ENABLED=true
```

### Obsidian Sync (see step 7)

```env
OBSIDIAN_VAULT_PATH=vault
OBSIDIAN_SYNC_ENABLED=true
```

### Paths & Behavior

```env
# Where the SQLite database lives (relative to poolmind root)
POOLMIND_DB_PATH=data/poolmind.db

# Logging: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO
```

---

## 6. Set Up Notion Sync (Optional)

poolmind can sync resources to a Notion database for a secondary view of your learning library.

### Step 1: Create a Notion Integration

1. Go to **https://www.notion.so/profile/integrations**
2. Click **"+ New integration"**
3. Name it `poolmind` and select the workspace where your database lives
4. Click **"Submit"** — copy the **Internal Integration Token** (starts with `ntn_` or `secret_`)

### Step 2: Create a Database

In your Notion workspace, create a new database (any name, e.g., "Poolmind Resources"). Add these properties (the names matter — they must match `config/notion.yaml`):

| Property Type | Property Name |
|---|---|
| Title | `Name` |
| Text | `Resource ID` |
| Select | `Type` |
| URL | `URL` |
| Select | `Domain` |
| Select | `Skill Level` |
| Select | `Format` |
| Select | `Cost` |
| Number | `Quality Score` |
| Number | `Personal Rating` |
| Select | `Temporal Relevance` |
| Select | `Consumption State` |
| Number | `Times Used` |
| Date | `Last Used` |
| Date | `Added On` |
| Date | `Last Verified` |
| Checkbox | `Maintained` |
| Number | `AI Confidence` |
| Text | `Author` |
| Select | `Platform` |
| Number | `Year Published` |
| Text | `Time to Value` |
| Multi-select | `Tags` |
| Text | `Summary` |
| Text | `Why It Matters` |
| Text | `Learning Path` |
| Text | `Added By` |

> **Tip:** You don't need every property. poolmind only syncs properties that exist. Start with `Name`, `URL`, `Type`, `Domain`, `Tags`, `Summary` — add the rest later.

### Step 3: Share the Database with Your Integration

1. Open your database in Notion
2. Click **"..."** (top-right) → **"Add connections"**
3. Select **"poolmind"** (the integration you just created)

### Step 4: Find Your Database ID

The database ID is in the URL of your database page:

```
https://www.notion.so/<workspace>/<database-id>?v=...
                                   ^^^^^^^^^^^^^^^^
                                   32-character hex string
```

Copy just the 32-character hex string (the part before the `?`).

### Step 5: Configure .env

```env
NOTION_TOKEN=ntn_your-integration-token
NOTION_DATABASE=your-32-char-database-id
NOTION_SYNC_ENABLED=true
```

### Customizing Property Mappings

If your Notion database uses different property names, edit `config/notion.yaml`:

```yaml
properties:
  title: "Name"               # Change "Name" to whatever your title property is called
  resource_id: "Resource ID"
  type: "Type"
  ...
```

---

## 7. Set Up Obsidian Sync (Optional)

poolmind can write resource notes to an Obsidian vault as Markdown files.

### Configure

```env
# Path to your Obsidian vault (relative or absolute)
OBSIDIAN_VAULT_PATH=/path/to/your/vault

# Set to true to enable syncing
OBSIDIAN_SYNC_ENABLED=true
```

Resources are written as individual `.md` files under `vault/poolmind/<resource-id>.md` with YAML frontmatter containing all metadata.

> **Note:** The default `OBSIDIAN_VAULT_PATH=vault` creates a local `vault/` directory — useful for testing without a real Obsidian vault.

---

## 8. Run Everything

### Option A: One-Click (Windows)

poolmind includes a `start.cmd` script that launches both services:

```bash
start.cmd
```

This opens two terminal windows:
- **freellmapi** on port 3001 (minimized)
- **poolmind** on port 5000

To stop both:

```bash
stop.cmd
```

### Option B: Manual (all platforms)

In **Terminal 1 — freellmapi** (from the poolmind directory):

```bash
cd freellmapi
npm run dev
```

In **Terminal 2 — poolmind**:

```bash
.venv\Scripts\activate      # Windows
source .venv/bin/activate    # macOS/Linux
python -m app.webui
```

### Option C: Docker (freellmapi only)

If you prefer Docker for freellmapi:

```bash
cd freellmapi
docker compose up -d
```

This runs freellmapi on port 3001. The dashboard is served directly on http://localhost:3001 (no separate Vite port). poolmind still runs natively.

---

## 9. Verify It Works

1. **Open poolmind** at **http://localhost:5000**
2. The dashboard should show:
   - **4 stat cards** at the top (Resources, Domains, Dead Links, Low Confidence)
   - **SERVICES section** with:
     - **AI API** — should show `[ONLINE]` with green `freellmapi` badge
     - **Notion Sync** — `[ON]` or `[OFF]` depending on your config
     - **AI calls** — your total call count
3. If AI API shows `[OFFLINE]`:
   - Is freellmapi running? Check http://localhost:3001/api/ping
   - Is the dashboard at http://localhost:5173 accessible?
   - Is the unified API key correct in `.env`?
   - Check the poolmind terminal for error logs

4. **Add a resource:**
   - Click **"+ Add resource"** or navigate to `/add`
   - Paste a URL to an article, video, or repo
   - poolmind will fetch metadata, classify it, and generate a summary via AI

5. **Test the Search:**
   - Navigate to `/search` and try keyword search
   - Switch to **Natural language** tab for AI-powered query parsing

6. **Explore AI features:**
   - `/intelligence/paths` — Learning paths
   - `/intelligence/gap` — Gap analysis (click "Run analysis")
   - `/ai/prompts` — Prompt evolution dashboard

---

## Troubleshooting

| Problem | Likely Cause | Fix |
|---|---|---|
| `[OFFLINE]` on dashboard | freellmapi not running | Start it: `npm run dev` in freellmapi directory |
| "Connection refused" on AI actions | freellmapi port wrong | Check `FREELLMAPI_URL` in `.env` defaults to `http://localhost:3001` |
| "Authentication failed" | Wrong unified API key | Copy it again from freellmapi Keys page header |
| Notion sync fails | Database not shared with integration | Open Notion database → "..." → "Add connections" → select your integration |
| `ModuleNotFoundError` | Virtual env not activated | Run `.venv\Scripts\activate` (Windows) or `source .venv/bin/activate` (macOS/Linux) |
| pip install fails | Missing build tools | Install Python dev headers: `apt install python3-dev` (Linux) or Xcode CLI tools (macOS) |
| npm install fails | Node.js < 20 | Upgrade Node.js to v20+ |
| "Port 5000 in use" | Another app on that port | Edit `app/webui.py` or set `PORT` env var |
| AI features slow | Rate limits hit | Add more provider keys to freellmapi for better fallback coverage |

---

## Where to Go Next

- **[USAGE.md](USAGE.md)** — Full REST API docs and Web UI walkthrough
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — Technical architecture and data flow
- **[GUIDE.md](GUIDE.md)** — Beginner-friendly project tour
- **freellmapi** → http://localhost:5173 — add keys, reorder fallback chain, view analytics
- **poolmind** → http://localhost:5000 — your resource dashboard
