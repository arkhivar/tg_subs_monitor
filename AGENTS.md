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
  reaction_handlers.py      message_reaction + message_reaction_count updates (debug-verbose; keep as-is)
  comment_handlers.py       discussion-group text messages → comment events
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
- **`grist_simple_client.GristSimpleClient`** — the only Grist client. Its method names (`init_tables`, `init_events_table`, `upsert_user`, `upsert_chat`, `get_membership`, `add_subscriber`, `update_subscriber_leave`, `update_subscriber_rejoin`, `update_reaction_count`, `set_admin`, `get_all_memberships`, `add_event`) and its public attribute `api` are depended on by every handler — do not rename or restructure it. Handlers never call `api` directly; all Grist writes go through these methods.

## Grist schema contract

Four tables, fully reference-based (identity tables + state + timeline):

1. **Users** (identity, one row per Telegram user or pseudo-user) — API name `USERS_TABLE` in `config.py` (default `Users`). Columns: `tg_userid` (Text — Telegram user id as string, or pseudo-ids `channel_<chat_id>` / `admin_<bot_id>`), `tg_username`, `tg_firstname`, `tg_lastname` (Text).
2. **Chats** (identity, one row per monitored channel/group) — API name `CHATS_TABLE` (default `Chats`). Columns: `tg_chatid` (Text), `title` (Text), `type` (Text: channel/supergroup/...).
3. **Membership** (per user×chat aggregate state) — API name `MEMBERSHIP_TABLE` (default `Membership`). Columns: `tg_user` (Ref:Users), `chat` (Ref:Chats), `join_date`, `leave_date`, `rejoin_date`, `last_reacted` (Date), `current_status` (Text: `active`/`inactive`), `reaction_counter` (Numeric), `is_admin` (Toggle).
4. **Events** (append-only timeline, one row per event) — API name `EVENTS_TABLE` (default `Events`; Grist capitalizes table ids). Columns: `event_type` (Text: `join`/`leave`/`rejoin`/`reaction`/`comment`), `tg_user` (Ref:Users, empty for anonymous reactions), `chat` (Ref:Chats), `message_id` (Numeric, 0 when n/a), `reaction` (Text — emoji, only for reaction events), `comment_text` (Text — first 500 chars, only for comments), `event_date` (Date). grist-api 0.1.1 has **no table-creation method**, so `init_tables()`/`init_events_table()` probe and log the schema; create tables once in the Grist UI.

## Quirks to know before editing

- **Identity resolution is cached:** `upsert_user()`/`upsert_chat()` keep in-memory maps (tg id → Grist row id) so steady-state event writes cost no extra reads. There is no uniqueness constraint in Grist — the upsert is the only guard against duplicate identity rows.
- **Membership is keyed user×chat:** `get_membership(user_id, chat_id)` resolves the user ref via the cache, then matches `tg_user`+`chat` refs. This fixes the legacy bug where one user collided across multiple monitored chats.
- **Pseudo-users live in Users:** `channel_<chat_id>` aggregates anonymous channel reaction counts; `admin_<bot_id>` is the fallback for unattributable reactions. They get Membership rows like anyone else. `/stats` and `/reactions` count them — filter on `tg_userid` prefixes if you build per-user analytics.
- **Dates:** all date writes are `datetime.now()` **objects** (grist-api converts them to the Grist epoch) — the legacy ISO-string writes are gone. `_parse_datetime()` in command_handlers still accepts epochs/ISO strings defensively for display.
- **`/sync` is now real**: it calls `bot.get_chat_administrators` and upserts each non-bot admin (add if missing, set `is_admin=True` + reactivate if present). It was ported from the deleted `telegram_grist_webhook.py`. Note it syncs the chat where the command was issued.
- **grist-api `server=` kwarg**: verified against grist-api 0.1.1 — `GristDocAPI(doc_id, api_key=..., server=GRIST_SERVER)`; the client appends `/api/docs/<doc_id>/` itself, so `GRIST_SERVER` must be the bare instance URL without `/api`.
- **`GRIST_SERVER` config**: `config.py` holds `os.environ.get('GRIST_SERVER', 'https://api.getgrist.com')`; `grist_simple_client` and `tools/explore_grist_tables.py` must stay consistent with it.
- **Comment coverage**: `handlers/comment_handlers.py` records text messages in group/supergroup chats as `comment` events (commands, bot senders, and service messages ignored). Comments on channel posts arrive in the channel's **linked discussion group** — the bot must be a member there with message access (admin, or privacy mode disabled) to see them.
- **History note**: comments were never persisted by any earlier generation — only debug-logged; the events table is the first real comment/event storage.
- **Webhook config is guarded**: `WEBHOOK_PATH`/`WEBHOOK_URL` are `None` unless `WEBHOOK_HOST` is set, so polling mode needs no webhook vars. `bot.start_webhook()` exits with an error if `BOT_MODE=webhook` but `WEBHOOK_HOST` is unset.

## Run modes

- Polling (default): `python run_bot.py` — deletes any existing webhook, long-polls.
- Webhook: `BOT_MODE=webhook`, `WEBHOOK_HOST=https://...`, optional `PORT` (default 5000); aiohttp serves `POST /webhook/<TELEGRAM_BOT_TOKEN>`.

## Sibling widget repo

Any future Grist-side UI (dashboard custom widget) should reuse the shared design system in the sibling repo **`arkhivar/grist`**: `shared/base.css` and `shared/core.js`. Roadmap items: dashboard widget, dedicated reactions-event table, tests.
