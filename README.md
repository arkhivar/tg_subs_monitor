# tg_subs_monitor

A Telegram bot that tracks channel subscriber activity — joins, leaves, rejoins, and message reactions — and writes everything into a [Grist](https://www.getgrist.com/) document. The Grist document is both the database and the UI: there is no web framework in this repo.

## What it does

- Records every join / leave / rejoin of a channel or group member, keeping historical dates (`join_date`, `leave_date`, `rejoin_date`).
- Counts reactions per subscriber (`reaction_counter`, `last_reacted`) for the emojis listed in `TRACKED_REACTIONS`.
- Handles anonymous channel reactions via aggregate pseudo-records (see below).
- `/sync` command: pulls the chat administrator roster and upserts admins into Grist with `is_admin=True`.

## Architecture

- **`bot.py`** — aiogram 3 entry point. Polling is the default; set `BOT_MODE=webhook` (plus `WEBHOOK_HOST`) to serve updates over an aiohttp webhook instead.
- **`handlers/`** — aiogram routers: `member_handlers.py` (join/leave), `reaction_handlers.py` (reactions), `command_handlers.py` (`/start`, `/help`, `/stats`, `/reactions`, `/status`, `/sync`).
- **`grist_simple_client.py`** — thin wrapper around `grist-api`'s `GristDocAPI`. All bot-to-Grist traffic goes through the Grist REST API.
- **`config.py`** — environment-driven configuration; import-time validation of required variables.

### The Grist document is the source of truth AND the UI

All subscriber data lives in one Grist table. To view, filter, or group subscribers, use Grist grids directly. To build dashboards, add Grist summary pages or custom widgets inside the same document — a shared widget design system lives in the sibling repo `arkhivar/grist` (`shared/base.css` + `shared/core.js`).

## Setup

### Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | yes | — | Bot token from @BotFather |
| `GRIST_API_KEY` | yes | — | Grist API key |
| `GRIST_DOC_ID` | yes | — | Grist document ID (the part of the URL after `/doc/`) |
| `GRIST_SERVER` | no | `https://api.getgrist.com` | Base URL of the Grist instance. For self-hosted Grist set e.g. `https://grist.internal.example.com` — **no `/api` suffix**, the client appends `/api/docs/...` itself |
| `BOT_MODE` | no | `polling` | `polling` or `webhook` |
| `WEBHOOK_HOST` | webhook only | — | Public HTTPS base URL of this bot; required in webhook mode |
| `PORT` | no | `5000` | Port the aiohttp webhook server listens on |
| `LOG_LEVEL` | no | `INFO` | Python logging level |

### Grist table schema

Create one table in your Grist document. The bot reads the table's **API name** from `SUBSCRIBERS_TABLE` in `config.py` (currently `Table1`). Note that a table's *display name* in the Grist UI (e.g. "subscribers") is **not** the same as its *API name* — check "Raw Data" view or the document's `/structure` endpoint (`tools/explore_grist_tables.py` prints it) and set `SUBSCRIBERS_TABLE` accordingly.

Columns:

| Column | Type | Notes |
|---|---|---|
| `user_id` | Text | Telegram user ID stored as **text**; also pseudo-IDs `channel_<chat_id>` and `admin_<bot_id>` |
| `username` | Text | |
| `first_name` | Text | |
| `last_name` | Text | |
| `join_date` | Date | |
| `leave_date` | Date | |
| `rejoin_date` | Date | |
| `current_status` | Text | `active` / `inactive` |
| `reaction_counter` | Numeric | |
| `last_reacted` | Date | |
| `is_admin` | Toggle | |

## Running

```bash
# plain pip / venv
pip install .
python run_bot.py            # or: ./run_telegram_bot.sh

# or with uv (lockfile is generated on the target machine)
uv sync && uv run python run_bot.py
```

Webhook mode (optional): set `BOT_MODE=webhook`, `WEBHOOK_HOST=https://<public-url>`, and optionally `PORT`. The bot then serves Telegram updates at `POST /webhook/<TELEGRAM_BOT_TOKEN>` via aiohttp.

## Development tools

- `tools/explore_grist_tables.py` — inspects the Grist document over the REST API: document metadata, table list with column types, and sample rows for candidate table names. Honors `GRIST_SERVER`.

## Roadmap

- Grist-side dashboard widget for subscriber stats, reusing the `arkhivar/grist` design system (`shared/base.css`, `shared/core.js`).
- Dedicated reactions-event table (one row per reaction) instead of only an aggregate counter.
- Automated tests.
