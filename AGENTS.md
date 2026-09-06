# AGENTS.md — handoff for AI coding agents

## Project purpose

`tg_subs_monitor` is a Telegram bot that tracks channel/group subscriber activity — joins, leaves, rejoins, and message reactions — and persists everything into a **Grist** document (self-hosted or getgrist.com). The Grist document is the source of truth **and** the UI. There is intentionally **no web framework** in this repo: do not reintroduce one; build any dashboard as a Grist page or custom widget instead.

## Layout after cleanup

```
bot.py                      aiogram 3 entry point (polling default; aiohttp webhook when BOT_MODE=webhook)
config.py                   env-driven config, import-time validation of required vars
grist_simple_client.py      THE Grist client — thin wrapper over grist-api's GristDocAPI
handlers/
  __init__.py
  command_handlers.py       /start /help /stats /reactions /status /sync
  member_handlers.py        join/leave/rejoin + admin-status changes
  reaction_handlers.py      message_reaction + message_reaction_count updates
utils/logger.py             shared logger ('tg_grist_bot')
run_bot.py                  asyncio entry with signal handling
run_telegram_bot.sh         thin wrapper around run_bot.py
tools/explore_grist_tables.py   REST inspection of the Grist doc (metadata, tables, sample rows)
pyproject.toml              aiogram, aiohttp, grist-api, requests
.github/workflows/notify.yml    owner's notification plumbing — do not touch
```

## The one surviving stack, and why

Earlier iterations of this repo contained several competing generations (a RAM-based bot, a web-based webhook server, a non-aiogram library bot, multiple redundant aiogram mains, three dead Grist clients). All were deleted. What remains is:

- **aiogram 3** (`bot.py` + `handlers/*`, router-based, async setup functions that receive the Grist client)
- **`grist_simple_client.GristSimpleClient`** — the only Grist client. Its method names (`init_table`, `get_subscriber`, `add_subscriber`, `update_subscriber_leave`, `update_subscriber_rejoin`, `update_reaction_count`, `update_admin_reaction`, `get_all_subscribers`) and its public attributes `api` / `table_name` are depended on by every handler — do not rename or restructure it.

## Grist schema contract

One table whose **API name** is `SUBSCRIBERS_TABLE` in `config.py` (currently `Table1`; the UI display name is irrelevant). Columns: `user_id` (Text), `username`, `first_name`, `last_name` (Text), `join_date`, `leave_date`, `rejoin_date`, `last_reacted` (Date), `current_status` (Text: `active`/`inactive`), `reaction_counter` (Numeric), `is_admin` (Toggle).

## Quirks to know before editing

- **`user_id` is stored as Text.** All lookups stringify IDs. Keep that.
- **Pseudo-rows in the same table:** `channel_<chat_id>` aggregates anonymous channel reaction counts; `admin_<bot_id>` is a fallback record for reactions we cannot attribute. `/stats` and `/reactions` count these rows as "subscribers" — acceptable for now, but filter them if you build per-user analytics.
- **Dates:** the code writes `datetime.now().isoformat()` strings into Grist Date columns. Grist expects epoch timestamps for Date columns; whether the doc actually stores these strings correctly is **unverified — verify against the real doc next session** and migrate to `datetime` objects (grist-api converts those) if needed.
- **`/sync` is now real**: it calls `bot.get_chat_administrators` and upserts each non-bot admin (add if missing, set `is_admin=True` + reactivate if present). It was ported from the deleted `telegram_grist_webhook.py`. Note it syncs the chat where the command was issued.
- **grist-api `server=` kwarg**: verified against grist-api 0.1.1 — `GristDocAPI(doc_id, api_key=..., server=GRIST_SERVER)`; the client appends `/api/docs/<doc_id>/` itself, so `GRIST_SERVER` must be the bare instance URL without `/api`.
- **`GRIST_SERVER` config**: `config.py` holds `os.environ.get('GRIST_SERVER', 'https://api.getgrist.com')`; `grist_simple_client` and `tools/explore_grist_tables.py` must stay consistent with it.
- **Webhook config is guarded**: `WEBHOOK_PATH`/`WEBHOOK_URL` are `None` unless `WEBHOOK_HOST` is set, so polling mode needs no webhook vars. `bot.start_webhook()` exits with an error if `BOT_MODE=webhook` but `WEBHOOK_HOST` is unset.

## Run modes

- Polling (default): `python run_bot.py` — deletes any existing webhook, long-polls.
- Webhook: `BOT_MODE=webhook`, `WEBHOOK_HOST=https://...`, optional `PORT` (default 5000); aiohttp serves `POST /webhook/<TELEGRAM_BOT_TOKEN>`.

## Sibling widget repo

Any future Grist-side UI (dashboard custom widget) should reuse the shared design system in the sibling repo **`arkhivar/grist`**: `shared/base.css` and `shared/core.js`. Roadmap items: dashboard widget, dedicated reactions-event table, tests.
