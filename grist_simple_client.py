"""
Grist client for the Telegram subscriber monitor.

Reference-based schema (see AGENTS.md):
  Users      identity, one row per Telegram user (or pseudo-user)
  Chats      identity, one row per monitored channel/group
  Membership per user-per-chat aggregate state, Refs to Users + Chats
  Events     append-only timeline, Refs to Users + Chats

All identity resolution goes through upsert_user()/upsert_chat(), which keep
in-memory caches (tg_userid -> row id, tg_chatid -> row id) so steady-state
operation costs no extra reads.
"""

import os
import logging
from datetime import datetime
from grist_api.grist_api import GristDocAPI

logger = logging.getLogger(__name__)


def _record_to_dict(record, fields):
    """Convert a grist-api record object to a plain dict over `fields` (plus 'id')."""
    if isinstance(record, dict):
        return {f: record.get(f) for f in ['id'] + fields}
    result = {'id': getattr(record, 'id', None)}
    for f in fields:
        result[f] = getattr(record, f, None)
    return result


def _to_ts(value):
    """
    Convert a date-ish value to a Grist epoch timestamp (seconds).

    Grist Date/DateTime columns expect numeric epoch seconds; grist-api's
    to_grist() would serialize datetimes as ISO strings, which Grist parses
    lossily (observed: time truncated to the hour) — so we convert ourselves.
    Returns None for unparseable input.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
        except ValueError:
            return None
    return None


USER_FIELDS = ['tg_userid', 'tg_username', 'tg_firstname', 'tg_lastname']
CHAT_FIELDS = ['tg_chatid', 'title', 'type']
MEMBERSHIP_FIELDS = ['tg_user', 'chat', 'join_date', 'leave_date', 'rejoin_date',
                     'current_status', 'reaction_counter', 'last_reacted', 'is_admin']


class GristSimpleClient:
    """Client for the reference-based Grist schema (Users/Chats/Membership/Events)."""

    def __init__(self):
        """Initialize the Grist client with API credentials from environment variables."""
        self.api_key = os.environ.get("GRIST_API_KEY")
        self.doc_id = os.environ.get("GRIST_DOC_ID")

        from config import USERS_TABLE, CHATS_TABLE, MEMBERSHIP_TABLE, EVENTS_TABLE, GRIST_SERVER
        self.users_table = USERS_TABLE
        self.chats_table = CHATS_TABLE
        self.membership_table = MEMBERSHIP_TABLE
        self.events_table_name = EVENTS_TABLE

        # tg_userid (str) -> Users row id; tg_chatid (str) -> Chats row id.
        # None means "not loaded yet".
        self._users_by_tg = None
        self._chats_by_tg = None

        if not self.api_key or not self.doc_id:
            logger.error("Missing GRIST_API_KEY or GRIST_DOC_ID environment variables")
            self.api = None
        else:
            try:
                # grist-api's GristDocAPI accepts a `server` kwarg (verified for
                # 0.1.1) and appends '/api/docs/<doc_id>/' itself, so pass the
                # bare instance base URL from GRIST_SERVER (no '/api' suffix).
                self.api = GristDocAPI(self.doc_id, api_key=self.api_key, server=GRIST_SERVER)
                logger.info(f"Initialized Grist client for document: {self.doc_id} on server: {GRIST_SERVER}")
            except Exception as e:
                logger.error(f"Error initializing Grist client: {e}")
                self.api = None

    # ------------------------------------------------------------------
    # Table probes
    # ------------------------------------------------------------------

    def _probe_table(self, table_name, schema_hint):
        """Fetch a table to prove it exists; log the schema hint if it doesn't."""
        if not self.api:
            logger.error("Grist API client not initialized")
            return False
        try:
            response = self.api.fetch_table(table_name)
            count = len(response) if isinstance(response, list) else '?'
            logger.info(f"Table '{table_name}' exists with {count} records")
            return True
        except Exception as e:
            if "Table not found" in str(e):
                logger.error(f"Table '{table_name}' doesn't exist. Required columns: {schema_hint}")
            else:
                logger.error(f"Error checking table '{table_name}': {e}")
            return False

    def init_tables(self):
        """Probe the Users, Chats and Membership tables. All three are required."""
        ok = True
        ok &= self._probe_table(self.users_table,
                                "tg_userid (Text), tg_username (Text), tg_firstname (Text), tg_lastname (Text)")
        ok &= self._probe_table(self.chats_table,
                                "tg_chatid (Text), title (Text), type (Text)")
        ok &= self._probe_table(self.membership_table,
                                "tg_user (Ref:Users), chat (Ref:Chats), join_date (Date), leave_date (Date), "
                                "rejoin_date (Date), current_status (Text), reaction_counter (Numeric), "
                                "last_reacted (Date), is_admin (Toggle)")
        return bool(ok)

    def init_events_table(self):
        """Probe the events table (additive: caller may warn but keep running)."""
        return self._probe_table(self.events_table_name,
                                 "event_type (Text: join/leave/rejoin/reaction/comment), tg_user (Ref:Users), "
                                 "chat (Ref:Chats), message_id (Numeric, 0 when n/a), reaction (Text - emoji, "
                                 "only for reactions), comment_text (Text - excerpt, only for comments), "
                                 "event_date (Date)")

    # ------------------------------------------------------------------
    # Identity caches and upserts
    # ------------------------------------------------------------------

    def _load_users_cache(self):
        self._users_by_tg = {}
        try:
            for record in self.api.fetch_table(self.users_table) or []:
                row = _record_to_dict(record, USER_FIELDS)
                if row['tg_userid'] is not None and row['id'] is not None:
                    self._users_by_tg[str(row['tg_userid'])] = row['id']
        except Exception as e:
            logger.error(f"Error loading Users cache: {e}")

    def _load_chats_cache(self):
        self._chats_by_tg = {}
        try:
            for record in self.api.fetch_table(self.chats_table) or []:
                row = _record_to_dict(record, CHAT_FIELDS)
                if row['tg_chatid'] is not None and row['id'] is not None:
                    self._chats_by_tg[str(row['tg_chatid'])] = row['id']
        except Exception as e:
            logger.error(f"Error loading Chats cache: {e}")

    def upsert_user(self, user_id, username='', first_name='', last_name=''):
        """
        Return the Users row id for a Telegram user id, creating the row if needed.

        Also accepts pseudo-ids ('channel_<chat_id>', 'admin_<bot_id>') — they
        live in Users like any other identity.

        Returns:
            int: Users row id, or None on failure
        """
        if not self.api:
            logger.error("Grist API client not initialized")
            return None
        tg_userid = str(user_id)
        if self._users_by_tg is None:
            self._load_users_cache()
        if tg_userid in self._users_by_tg:
            return self._users_by_tg[tg_userid]
        try:
            result = self.api.add_records(self.users_table, [{
                'tg_userid': tg_userid,
                'tg_username': username or '',
                'tg_firstname': first_name or '',
                'tg_lastname': last_name or '',
            }])
            row_id = result[0] if isinstance(result, (list, tuple)) else result
            self._users_by_tg[tg_userid] = row_id
            logger.info(f"✅ Created Users row {row_id} for tg_userid={tg_userid}")
            return row_id
        except Exception as e:
            logger.error(f"❌ Error upserting user {tg_userid}: {e}")
            return None

    def upsert_chat(self, chat_id, title='', chat_type=''):
        """
        Return the Chats row id for a Telegram chat id, creating the row if needed.

        Returns:
            int: Chats row id, or None on failure
        """
        if not self.api:
            logger.error("Grist API client not initialized")
            return None
        tg_chatid = str(chat_id)
        if self._chats_by_tg is None:
            self._load_chats_cache()
        if tg_chatid in self._chats_by_tg:
            return self._chats_by_tg[tg_chatid]
        try:
            result = self.api.add_records(self.chats_table, [{
                'tg_chatid': tg_chatid,
                'title': title or '',
                'type': chat_type or '',
            }])
            row_id = result[0] if isinstance(result, (list, tuple)) else result
            self._chats_by_tg[tg_chatid] = row_id
            logger.info(f"✅ Created Chats row {row_id} for tg_chatid={tg_chatid} ({title})")
            return row_id
        except Exception as e:
            logger.error(f"❌ Error upserting chat {tg_chatid}: {e}")
            return None

    # ------------------------------------------------------------------
    # Membership
    # ------------------------------------------------------------------

    def get_membership(self, user_id, chat_id=None):
        """
        Get the membership record for a Telegram user id.

        Args:
            user_id: Telegram user id (or pseudo-id), matched via Users.tg_userid
            chat_id: Optional Telegram chat id; when given, matches the
                     membership for that specific chat, otherwise the first
                     membership found for the user

        Returns:
            dict: Membership fields (plus resolved 'tg_userid') or None
        """
        if not self.api:
            logger.error("Grist API client not initialized")
            return None
        tg_userid = str(user_id)
        if self._users_by_tg is None:
            self._load_users_cache()
        user_ref = self._users_by_tg.get(tg_userid)
        if user_ref is None:
            return None
        chat_ref = None
        if chat_id is not None:
            if self._chats_by_tg is None:
                self._load_chats_cache()
            chat_ref = self._chats_by_tg.get(str(chat_id))
            if chat_ref is None:
                return None
        try:
            for record in self.api.fetch_table(self.membership_table) or []:
                row = _record_to_dict(record, MEMBERSHIP_FIELDS)
                if row['tg_user'] == user_ref and (chat_ref is None or row['chat'] == chat_ref):
                    row['tg_userid'] = tg_userid
                    return row
            return None
        except Exception as e:
            logger.error(f"Error fetching membership for {tg_userid}: {e}")
            return None

    def add_subscriber(self, user_data, chat_id=None, chat_title='', chat_type=''):
        """
        Add a membership for a user (upserting the Users/Chats rows as needed).

        Mirrors the legacy semantics: if a membership already exists and is
        inactive, it is updated as a rejoin; if active, it is a no-op.

        Args:
            user_data: Dict with user_id, username, first_name, last_name and
                       optional join_date/current_status/reaction_counter/
                       last_reacted/is_admin/leave_date
            chat_id: Telegram chat id the membership belongs to (required for
                     a meaningful membership; without it only the user is upserted)
            chat_title/chat_type: Used when the Chats row has to be created

        Returns:
            bool: Success status
        """
        if not self.api:
            logger.error("Grist API client not initialized")
            return False
        user_id = user_data.get('user_id', user_data.get('id'))
        if user_id is None:
            logger.error("❌ add_subscriber called without user_id")
            return False

        user_ref = self.upsert_user(user_id,
                                    username=user_data.get('username', ''),
                                    first_name=user_data.get('first_name', ''),
                                    last_name=user_data.get('last_name', ''))
        if user_ref is None:
            return False
        if chat_id is None:
            # Identity-only upsert (e.g. /start in a private chat)
            return True
        chat_ref = self.upsert_chat(chat_id, title=chat_title, chat_type=chat_type)
        if chat_ref is None:
            return False

        existing = self.get_membership(user_id, chat_id)
        if existing:
            if existing.get('current_status') == 'inactive':
                logger.info(f"♻️ Membership for {user_id} in chat {chat_id} was inactive, marking rejoin")
                return self.update_subscriber_rejoin(user_id, chat_id, existing.get('id'))
            logger.info(f"✅ Membership for {user_id} in chat {chat_id} already active, no changes")
            return True

        record = {
            'tg_user': user_ref,
            'chat': chat_ref,
            'join_date': _to_ts(user_data.get('join_date')) or datetime.now().timestamp(),
            'current_status': user_data.get('current_status', 'active'),
            'reaction_counter': int(user_data.get('reaction_counter', 0) or 0),
            'is_admin': bool(user_data.get('is_admin', False)),
        }
        leave_date = _to_ts(user_data.get('leave_date'))
        if leave_date is not None:
            record['leave_date'] = leave_date
        rejoin_date = _to_ts(user_data.get('rejoin_date'))
        if rejoin_date is not None:
            record['rejoin_date'] = rejoin_date
        last_reacted = _to_ts(user_data.get('last_reacted'))
        if last_reacted is not None:
            record['last_reacted'] = last_reacted
        try:
            self.api.add_records(self.membership_table, [record])
            logger.info(f"✅ Added membership for user {user_id} in chat {chat_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Error adding membership: {e}")
            return False

    def _update_membership(self, user_id, chat_id, record_id, update_fields, what):
        """Shared tail of the leave/rejoin updaters."""
        if not record_id:
            membership = self.get_membership(user_id, chat_id)
            if not membership:
                logger.error(f"❌ No membership found for user {user_id} (chat {chat_id})")
                return False
            record_id = membership.get('id')
        try:
            update_data = dict(update_fields)
            for date_field in ('join_date', 'leave_date', 'rejoin_date', 'last_reacted'):
                if date_field in update_data:
                    ts = _to_ts(update_data[date_field])
                    if ts is not None:
                        update_data[date_field] = ts
                    else:
                        del update_data[date_field]
            update_data['id'] = record_id
            self.api.update_records(self.membership_table, [update_data])
            logger.info(f"✅ Updated {what} for user {user_id} (membership {record_id})")
            return True
        except Exception as e:
            logger.error(f"❌ Error updating {what} in Grist: {e}")
            return False

    def update_subscriber_leave(self, user_id, chat_id=None, record_id=None):
        """Mark a membership inactive with leave_date=now."""
        logger.info(f"🔴 LEAVE: user {user_id}, chat {chat_id}")
        return self._update_membership(
            user_id, chat_id, record_id,
            {'leave_date': datetime.now(), 'current_status': 'inactive'},
            'leave status')

    def update_subscriber_rejoin(self, user_id, chat_id=None, record_id=None):
        """Mark a membership active with rejoin_date=now."""
        logger.info(f"🟢 REJOIN: user {user_id}, chat {chat_id}")
        return self._update_membership(
            user_id, chat_id, record_id,
            {'rejoin_date': datetime.now(), 'current_status': 'active'},
            'rejoin status')

    def update_reaction_count(self, user_id, chat_id=None, increment=1):
        """
        Increment reaction_counter and stamp last_reacted on a membership.

        Returns:
            bool: Success status (False when no membership exists)
        """
        if not self.api:
            logger.error("Grist API client not initialized")
            return False
        membership = self.get_membership(user_id, chat_id)
        if not membership:
            logger.error(f"❌ No membership found for user {user_id} (chat {chat_id})")
            return False
        current = int(membership.get('reaction_counter') or 0)
        return self._update_membership(
            user_id, chat_id, membership.get('id'),
            {'reaction_counter': current + increment, 'last_reacted': datetime.now()},
            f'reaction count {current} → {current + increment}')

    def set_admin(self, user_id, chat_id, is_admin):
        """Set the is_admin flag on a membership. False when no membership exists."""
        membership = self.get_membership(user_id, chat_id)
        if not membership:
            return False
        return self._update_membership(
            user_id, chat_id, membership.get('id'),
            {'is_admin': bool(is_admin)},
            f'admin status → {bool(is_admin)}')

    def get_all_memberships(self, status=None, limit=None):
        """
        Get all membership records with user fields resolved (tg_userid,
        tg_username, tg_firstname merged in for display).

        Args:
            status: Optional 'active'/'inactive' filter
            limit: Optional cap on returned records

        Returns:
            list: Membership dicts
        """
        if not self.api:
            logger.error("Grist API client not initialized")
            return []
        if self._users_by_tg is None:
            self._load_users_cache()
        users_by_ref = {v: k for k, v in (self._users_by_tg or {}).items()}
        try:
            # Fetch user details once for display fields
            user_details = {}
            for record in self.api.fetch_table(self.users_table) or []:
                row = _record_to_dict(record, USER_FIELDS)
                user_details[row['id']] = row

            records = []
            for record in self.api.fetch_table(self.membership_table) or []:
                row = _record_to_dict(record, MEMBERSHIP_FIELDS)
                user = user_details.get(row['tg_user'], {})
                row['tg_userid'] = user.get('tg_userid') or users_by_ref.get(row['tg_user'], '')
                row['username'] = user.get('tg_username', '')
                row['first_name'] = user.get('tg_firstname', '')
                records.append(row)

            if status:
                records = [r for r in records if r.get('current_status') == status]
            if limit and isinstance(limit, int) and limit > 0:
                records = records[:limit]
            logger.info(f"Found {len(records)} memberships")
            return records
        except Exception as e:
            logger.error(f"Error fetching memberships: {e}")
            return []

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def add_event(self, event_data):
        """
        Add a single event row to the append-only events table.

        Accepted keys (identity fields are resolved to Refs internally):
            event_type, user_id ('' for anonymous), username, first_name,
            last_name, chat_id, chat_title, chat_type, message_id, reaction,
            comment_text, event_date (datetime preferred)

        Returns:
            bool: Success status
        """
        if not self.api:
            logger.error("❌ Grist API client not initialized")
            return False
        try:
            event_date = _to_ts(event_data.get('event_date'))
            if event_date is None:
                if event_data.get('event_date') is not None:
                    logger.warning(f"⚠️ Unparseable event_date '{event_data.get('event_date')}', using now()")
                event_date = datetime.now().timestamp()

            record = {
                'event_type': event_data.get('event_type', ''),
                'message_id': int(event_data.get('message_id', 0) or 0),
                'reaction': event_data.get('reaction', '') or '',
                'comment_text': event_data.get('comment_text', '') or '',
                'event_date': event_date,
            }

            user_id = event_data.get('user_id')
            if user_id not in (None, ''):
                user_ref = self.upsert_user(user_id,
                                            username=event_data.get('username', ''),
                                            first_name=event_data.get('first_name', ''),
                                            last_name=event_data.get('last_name', ''))
                if user_ref is not None:
                    record['tg_user'] = user_ref

            chat_id = event_data.get('chat_id')
            if chat_id not in (None, ''):
                chat_ref = self.upsert_chat(chat_id,
                                            title=event_data.get('chat_title', ''),
                                            chat_type=event_data.get('chat_type', ''))
                if chat_ref is not None:
                    record['chat'] = chat_ref

            self.api.add_records(self.events_table_name, [record])
            logger.info(f"✅ Recorded event '{record['event_type']}'")
            return True
        except Exception as e:
            logger.error(f"❌ Error recording event: {e}")
            return False


# For testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    client = GristSimpleClient()
    print(f"Init result: {client.init_tables()}")
    print(f"Found {len(client.get_all_memberships())} memberships")
