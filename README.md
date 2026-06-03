# poolmind

a place to save all the stuff you learn. links, articles, videos, tools — anything you find useful. poolmind saves it, organizes it, and helps you find it later.

## what it does

- save a link, it grabs the title and summary
- tag things by domain, type, skill level
- search by keyword or just describe what you need
- bulk import from your bookmarks, notes, whatever
- sync to Notion or Obsidian if you use those
- dashboard shows what you got, what's untouched, what needs attention

## how it runs

poolmind uses [freellmapi](https://github.com/tashfeenahmed/freellmapi) for AI stuff — summarising, classifying, search, all that. freellmapi is a free proxy that talks to google gemini, groq, cerebras, and a bunch of other free AI providers. big thanks to tashfeenahmed for making it.

you clone freellmapi inside poolmind like this:

```
git clone https://github.com/tashfeenahmed/freellmapi.git
cd freellmapi
npm install
```

see [SETUP.md](SETUP.md) for the full walkthrough.

## quick start

```
git clone https://github.com/itzneel05/poolmind.git
cd poolmind
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

then set up freellmapi (instructions above), add your API keys at http://localhost:5173, put the unified key in `.env`, and run:

```
python -m app.webui
```

open http://localhost:5000

## stack

- python / flask
- sqlite
- htmx + vanilla js
- freellmapi (ai proxy)

## docs

- [SETUP.md](SETUP.md) — everything you need to get running
- [USAGE.md](USAGE.md) — api endpoints and cli commands
- [GUIDE.md](GUIDE.md) — tour of the web ui
- [ARCHITECTURE.md](ARCHITECTURE.md) — how it all fits together
