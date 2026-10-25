# This File Create By NAGENDRA!!

from __future__ import annotations

import asyncio
import html
import json
import logging
import pathlib
import random
import re
import secrets
import string
import time
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import aiosqlite
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, RetryAfter, TelegramError, TimedOut, NetworkError, Forbidden, Conflict
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application,
    ApplicationBuilder,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)

# ---------------------------------------------------------------------------
# PTB version-safe `style` support
# ---------------------------------------------------------------------------
def _supports_button_style() -> bool:
    """Detect whether current PTB supports the `style` kwarg on buttons."""
    try:
        InlineKeyboardButton("t", callback_data="x", style="primary")
        return True
    except TypeError:
        return False
    except Exception:
        return False


_BUTTON_STYLE_OK = _supports_button_style()


def _kb_btn(text: str, **kwargs):
    """InlineKeyboardButton that silently drops `style` on unsupported PTB."""
    if not _BUTTON_STYLE_OK:
        kwargs.pop("style", None)
    return InlineKeyboardButton(text, **kwargs)


def _reply_btn(text: str, **kwargs):
    """KeyboardButton that silently drops `style` on unsupported PTB."""
    if not _BUTTON_STYLE_OK:
        kwargs.pop("style", None)
    return KeyboardButton(text, **kwargs)


def _safe_chat_type(chat) -> str:
    """Return chat type as plain string across PTB versions."""
    try:
        ct = chat.type
        return ct.value if hasattr(ct, "value") else str(ct)
    except Exception:
        return "unknown"


def _load_token() -> str:
    """Read the Telegram token from the hosting environment, never from source."""
    return os.environ.get("BOT_TOKEN", "8782291529:AAFVJEoBv2BJRQFshVIWA263rIgH4DKSIpY").strip()
BOT_TOKEN = _load_token()
OWNER_ID = 8388115033
OWNER_USERNAME = "NagendraOwnerBack"
BOT_USERNAME = "NAGENDRA_STORE_APP"

BASE_DIR = pathlib.Path(__file__).resolve().parent
DB_PATH = str(BASE_DIR / "database.db")
LOG_PATH = BASE_DIR / "magendrafilestorebotlogs.json"

def utcnow() -> datetime:
    """Naive UTC timestamp compatible with existing SQLite ISO timestamps."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def india_now() -> datetime:
    """Current Indian Standard Time (IST), without requiring third-party packages."""
    return datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=5, minutes=30)))

class IndiaTimeFormatter(logging.Formatter):
    """Render console timestamps in India Standard Time (IST)."""
    converter = staticmethod(lambda timestamp: time.gmtime(timestamp + 19800))

logging.basicConfig(
    format="%(asctime)s IST | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
for _handler in logging.getLogger().handlers:
    if isinstance(_handler, logging.StreamHandler) and not isinstance(_handler, logging.FileHandler):
        _handler.setFormatter(IndiaTimeFormatter("%(asctime)s IST | %(levelname)s | %(name)s | %(message)s"))

logging.getLogger("httpx").setLevel(logging.WARNING)

class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        item = {
            "timestamp": india_now().isoformat(timespec="seconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            item["exception"] = self.formatException(record.exc_info)
        return json.dumps(item, ensure_ascii=False)

# Use rotating JSON Lines logs so the log file cannot grow without bound.
# Keep the existing .json filename for compatibility; each line is one JSON object.
try:
    from logging.handlers import RotatingFileHandler

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _json_handler = RotatingFileHandler(
        LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3,
        encoding="utf-8", delay=True,
    )
    _json_handler.setFormatter(JsonLineFormatter())
    logging.getLogger().addHandler(_json_handler)
except OSError as exc:
    # File logging must not prevent the bot from starting on read-only hosts.
    logging.getLogger().warning("File logging disabled for %s: %s", LOG_PATH, exc)

log = logging.getLogger("NagendraFileStoreBot")

DEFAULT_SETTINGS = {
    "bot_name": "𝙉𝘼𝙂𝙀𝙉𝘿𝙍𝘼 𝙊𝙒𝙉𝙀𝙍 𝗙𝗜𝗟𝗘 𝗦𝗧𝗢𝗥𝗘 𝗕𝗢𝗧",
    "referral_reward": "20",
    "daily_bonus": "25",
    "premium_daily_bonus_multiplier": "4",
    "premium_daily_bonus": "80",
    "support_username": "NagendraOwnerBack",
    "payment_username": "NagendraOwnerBack",
    "force_join": "1",
    "maintenance": "0",
    "star_rate": "30",
    "welcome_message": "👋 <b>Welcome, {name}!</b>\n\n🏷 <b>{bot_name}</b>\n──────────\n💰 <b>Wallet:</b> {balance} Coins\n👥 <b>Referrals:</b> {refs}\n{premium_line}\n──────────\n\nUse the menu below to get started 👇",
    "coin_packages": json.dumps([
        {"coins": 100, "stars": 3},
        {"coins": 500, "stars": 15},
        {"coins": 1000, "stars": 28},
        {"coins": 2500, "stars": 65},
        {"coins": 5000, "stars": 120},
    ]),
    "premium_pricing": json.dumps([
        {"days": 7, "price": 45},
        {"days": 30, "price": 90},
        {"days": 90, "price": 200},
        {"days": 150, "price": 600},
    ]),
    "coin_rate_inr": "5",
    "inr_payment_details": "bKash (Send Money): 01XXXXXXXXX\nNagad (Send Money): 01XXXXXXXXX",
    "upi_payment_id": "9358163308@ptsbi",
    "spin_settings": json.dumps({
        "chance_coins_low": 50,
        "chance_coins_high": 30,
        "chance_file": 18,
        "chance_premium": 2,
        "coins_low_min": 20,
        "coins_low_max": 50,
        "coins_high_min": 67,
        "coins_high_max": 120,
        "premium_days": 1,
    }),
    "mystery_box_pricing": json.dumps([
        {"tier": "random", "label": "🎁 Random File", "price": 100},
        {"tier": "rare", "label": "💎 Rare File", "price": 500},
        {"tier": "premium", "label": "👑 Premium Project", "price": 1000},
    ]),
    "referral_milestones": json.dumps([
        {"count": 5, "reward": 100},
        {"count": 10, "reward": 250},
        {"count": 25, "reward": 700},
        {"count": 50, "reward": 1500},
    ]),
    "streak_rewards": json.dumps([
        {"days": 3, "reward": 30},
        {"days": 7, "reward": 100},
        {"days": 14, "reward": 250},
        {"days": 30, "reward": 600},
    ]),
}

FILE_TYPE_ICON = {
    "document": "📄", "video": "🎬", "audio": "🎵", "photo": "🖼",
    "voice": "🎙", "animation": "🎞", "video_note": "🎥",
}

USE_CUSTOM_EMOJI = False
CUSTOM_EMOJI: dict[str, str] = {}

DIVIDER = "──────────────────"

_db_lock = asyncio.Lock()

DUPLICATE_COOLDOWN_SECONDS = 0.6
FLOOD_WINDOW_SECONDS = 3.0
FLOOD_MAX_ACTIONS = 12

_last_action_by_key: dict[tuple[int, str], float] = {}
_recent_action_times: dict[int, list[float]] = {}

_user_action_locks: dict[int, asyncio.Lock] = {}
_user_action_locks_guard = asyncio.Lock()


async def get_user_action_lock(user_id: int) -> asyncio.Lock:
    async with _user_action_locks_guard:
        lock = _user_action_locks.get(user_id)
        if lock is None:
            lock = asyncio.Lock()
            _user_action_locks[user_id] = lock
        return lock


# ---------------------------------------------------------------------------
# GLOBAL GUARDS
# ---------------------------------------------------------------------------
async def group_restriction_guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat is None or chat.type == "private":
        return

    if update.callback_query:
        is_bot_trigger = True
    else:
        msg = update.message
        if msg is None or not msg.text:
            return
        normalized = _strip_theme_prefix(msg.text)
        is_bot_trigger = msg.text.startswith("/") or msg.text in TEXT_ROUTES or normalized in TEXT_ROUTES

    if not is_bot_trigger:
        return

    try:
        await update.effective_message.reply_text("📩 Please Use this bot in Bot DM.")
    except TelegramError:
        pass
    raise ApplicationHandlerStop


async def flood_guard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        return

    if update.callback_query:
        action_id = update.callback_query.data or ""
    elif update.message and update.message.text:
        action_id = update.message.text
    else:
        return

    now = time.monotonic()

    key = (user.id, action_id)
    last_same = _last_action_by_key.get(key, 0.0)
    _last_action_by_key[key] = now
    if now - last_same < DUPLICATE_COOLDOWN_SECONDS:
        if update.callback_query:
            try:
                await update.callback_query.answer()
            except TelegramError:
                pass
        raise ApplicationHandlerStop

    history = _recent_action_times.setdefault(user.id, [])
    history[:] = [t for t in history if now - t < FLOOD_WINDOW_SECONDS]
    history.append(now)
    if len(history) > FLOOD_MAX_ACTIONS:
        if update.callback_query:
            try:
                await update.callback_query.answer("⏳ Please slow down a little.", show_alert=False)
            except TelegramError:
                pass
        raise ApplicationHandlerStop


# ---------------------------------------------------------------------------
# ⭐ FORCE JOIN HARD GATE — runs BEFORE everything else
# ---------------------------------------------------------------------------
async def force_join_hard_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Block ALL user interactions (except /start, /help and the verify button)
    until the user has joined every required force channel.

    Admins and Owner bypass the gate. If force_join is disabled in settings,
    the gate does nothing.
    """
    user = update.effective_user
    if user is None:
        return

    # Never block owner/admins
    try:
        if await is_admin(user.id):
            return
    except Exception:
        # DB may not be ready on very first update — don't block owner
        if user.id == OWNER_ID:
            return

    # Respect the force_join setting
    try:
        if (await get_setting("force_join", "1")) != "1":
            return
    except Exception:
        log.exception("force_join_hard_gate: could not read force_join setting")
        if update.callback_query:
            try:
                await update.callback_query.answer(
                    "⚠️ Access check is temporarily unavailable. Please try again shortly.",
                    show_alert=True,
                )
            except TelegramError:
                pass
        elif update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "⚠️ Access check is temporarily unavailable. Please try again shortly."
                )
            except TelegramError:
                pass
        raise ApplicationHandlerStop

    # Allow the /start command through (it performs its own check + shows prompt)
    if update.message and update.message.text:
        txt = update.message.text.strip()
        if txt.startswith("/start") or txt.startswith("/help"):
            return

    # Allow the "Verify" callback through
    if update.callback_query:
        data = update.callback_query.data or ""
        if data == "verify_join":
            return

    # Check the actual join state
    try:
        missing = await check_force_join(context.bot, user.id)
    except Exception:
        log.exception("force_join_hard_gate: check_force_join failed")
        # Fail closed when the membership API cannot be checked; otherwise a
        # transient Telegram timeout would let users bypass required channels.
        if update.callback_query:
            try:
                await update.callback_query.answer(
                    "⚠️ Couldn't verify channel membership because Telegram is temporarily unavailable. Please try again.",
                    show_alert=True,
                )
            except TelegramError:
                pass
        elif update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "⚠️ Telegram is temporarily unavailable, so I couldn't verify your required channel membership. Please try again in a moment."
                )
            except TelegramError:
                pass
        raise ApplicationHandlerStop

    if not missing:
        return

    # User has NOT joined — block this update
    if update.callback_query:
        try:
            await update.callback_query.answer(
                "🔒 Please join the required channels first, then tap ✅ Verify.",
                show_alert=True,
            )
        except TelegramError:
            pass
    else:
        try:
            await send_force_join_prompt(update, missing)
        except TelegramError:
            pass

    raise ApplicationHandlerStop


class RateLimiter:
    def __init__(self, rate: float):
        self.interval = 1.0 / rate
        self._lock = asyncio.Lock()
        self._next_time = time.monotonic()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._next_time - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = time.monotonic()
            self._next_time = now + self.interval


TELEGRAM_SEND_LIMITER = RateLimiter(25)

# SQLite supports many readers but only one writer at a time. A small pool
# avoids write-lock storms under concurrent Telegram updates.
DB_POOL_SIZE = 2
_db_pool: "asyncio.Queue[aiosqlite.Connection] | None" = None


async def init_db_pool() -> None:
    global _db_pool
    _db_pool = asyncio.Queue(maxsize=DB_POOL_SIZE)
    for _ in range(DB_POOL_SIZE):
        conn = await aiosqlite.connect(DB_PATH, timeout=30)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode = WAL;")
        await conn.execute("PRAGMA synchronous = NORMAL;")
        await conn.execute("PRAGMA busy_timeout = 15000;")
        await conn.execute("PRAGMA foreign_keys = ON;")
        await _db_pool.put(conn)
    log.info("DB connection pool ready (%d connections)", DB_POOL_SIZE)


async def close_db_pool() -> None:
    if _db_pool is None:
        return
    while not _db_pool.empty():
        conn = await _db_pool.get()
        await conn.close()


class _PooledConnection:
    async def __aenter__(self) -> aiosqlite.Connection:
        assert _db_pool is not None, "DB pool not initialized"
        self.conn = await _db_pool.get()
        return self.conn

    async def __aexit__(self, exc_type, exc, tb) -> None:
        assert _db_pool is not None
        await _db_pool.put(self.conn)


def db_conn() -> _PooledConnection:
    return _PooledConnection()


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH, timeout=30) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                join_date TEXT,
                is_banned INTEGER DEFAULT 0,
                referred_by INTEGER,
                last_bonus_time TEXT,
                last_seen TEXT
            );

            CREATE TABLE IF NOT EXISTS files (
                file_pk INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_file_id TEXT NOT NULL,
                tg_file_unique_id TEXT,
                file_kind TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                description TEXT DEFAULT '',
                price INTEGER DEFAULT 0,
                upload_date TEXT,
                downloads_count INTEGER DEFAULT 0,
                uploaded_by INTEGER,
                premium_only INTEGER DEFAULT 0,
                is_deleted INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS wallet (
                user_id INTEGER PRIMARY KEY,
                coins INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS transactions (
                tx_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                tx_type TEXT,
                amount INTEGER,
                description TEXT,
                timestamp TEXT
            );

            CREATE TABLE IF NOT EXISTS payments (
                payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                stars INTEGER,
                coins INTEGER,
                screenshot_file_id TEXT,
                status TEXT DEFAULT 'pending',
                admin_id INTEGER,
                reason TEXT,
                timestamp TEXT,
                payment_method TEXT DEFAULT 'stars',
                amount_inr INTEGER
            );

            CREATE TABLE IF NOT EXISTS redeems (
                code TEXT PRIMARY KEY,
                coin_reward INTEGER DEFAULT 0,
                premium_days INTEGER DEFAULT 0,
                usage_limit INTEGER DEFAULT 0,
                used_count INTEGER DEFAULT 0,
                expiry_date TEXT,
                status TEXT DEFAULT 'active',
                created_by INTEGER,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS redeem_uses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT,
                user_id INTEGER,
                timestamp TEXT,
                UNIQUE(code, user_id)
            );

            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                new_user_id INTEGER UNIQUE,
                date TEXT,
                reward INTEGER
            );

            CREATE TABLE IF NOT EXISTS force_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                chat_id INTEGER,
                title TEXT,
                invite_link TEXT,
                chat_type TEXT,
                added_date TEXT
            );

            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                added_date TEXT
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_pk INTEGER,
                timestamp TEXT
            );

            CREATE TABLE IF NOT EXISTS premium (
                user_id INTEGER PRIMARY KEY,
                expiry_date TEXT,
                is_lifetime INTEGER DEFAULT 0,
                granted_by INTEGER,
                granted_at TEXT
            );

            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_pk INTEGER,
                price INTEGER,
                timestamp TEXT
            );

            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                subject TEXT,
                body TEXT,
                status TEXT DEFAULT 'open',
                admin_id INTEGER,
                created_at TEXT,
                closed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS admin_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_id INTEGER,
                action_text TEXT,
                timestamp TEXT
            );

            CREATE TABLE IF NOT EXISTS file_requests (
                request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                request_text TEXT,
                status TEXT DEFAULT 'open',
                timestamp TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_files_deleted ON files(is_deleted);
            CREATE INDEX IF NOT EXISTS idx_tx_user ON transactions(user_id);
            CREATE INDEX IF NOT EXISTS idx_purchases_user_file ON purchases(user_id, file_pk);
            CREATE INDEX IF NOT EXISTS idx_downloads_user ON downloads(user_id);
            """
        )
        await db.execute("""CREATE TABLE IF NOT EXISTS telegram_star_charges (
            charge_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            coins INTEGER NOT NULL,
            stars INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )""")
        await db.commit()

        migrations = [
            ("files", "premium_only", "INTEGER DEFAULT 0"),
            ("payments", "payment_method", "TEXT DEFAULT 'stars'"),
            ("payments", "amount_inr", "INTEGER"),
            ("redeems", "source", "TEXT DEFAULT 'admin'"),
            ("admins", "role", "TEXT DEFAULT 'junior'"),
            ("users", "login_streak", "INTEGER DEFAULT 0"),
            ("users", "last_login_date", "TEXT"),
            ("users", "referral_milestone_reached", "INTEGER DEFAULT 0"),
            ("force_channels", "chat_type", "TEXT"),
            ("force_channels", "invite_link", "TEXT"),
            ("users", "spin_count_today", "INTEGER DEFAULT 0"),
            ("users", "spin_reset_date", "TEXT"),
            ("files", "mystery_tier", "TEXT"),
            ("files", "featured", "INTEGER DEFAULT 0"),
            ("force_channels", "join_by_request", "INTEGER DEFAULT 0"),
            ("force_channels", "is_private", "INTEGER DEFAULT 0"),
        ]
        for table, column, coltype in migrations:
            try:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
                await db.commit()
                log.info("Migrated: added %s.%s", table, column)
            except aiosqlite.OperationalError:
                pass

        for k, v in DEFAULT_SETTINGS.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v)
            )
        await db.execute(
            "UPDATE settings SET value=? WHERE key='upi_payment_id'",
            ("9358163308@ptsbi",),
        )
        await db.execute(
            "INSERT OR IGNORE INTO admins (user_id, added_date) VALUES (?, ?)",
            (OWNER_ID, utcnow().isoformat()),
        )
        await db.commit()
    log.info("Database ready at %s", DB_PATH)


async def get_setting(key: str, default: str = "") -> str:
    async with db_conn() as db:
        cur = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = await cur.fetchone()
        return row[0] if row else default


async def set_setting(key: str, value: str) -> None:
    async with db_conn() as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        await db.commit()



async def get_json_setting(key: str, default, expected_type):
    """Load a JSON setting safely and repair invalid values to a known default.

    `default` should be a Python dict/list matching `expected_type`.
    """
    raw = await get_setting(key, json.dumps(default, ensure_ascii=False))
    try:
        value = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        value = None

    if not isinstance(value, expected_type):
        log.warning(
            "Invalid setting %s (expected %s); restoring defaults",
            key, expected_type.__name__,
        )
        value = default
        try:
            await set_setting(key, json.dumps(default, ensure_ascii=False))
        except Exception:
            log.exception("Could not repair setting %s", key)
    return value


async def ensure_user(user_id: int, username: str | None, first_name: str | None,
                       referred_by: int | None = None) -> bool:
    async with db_conn() as db:
        cur = await db.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
        exists = await cur.fetchone()
        now = utcnow().isoformat()
        if exists:
            await db.execute(
                "UPDATE users SET username=?, first_name=?, last_seen=? WHERE user_id=?",
                (username, first_name, now, user_id),
            )
            await db.commit()
            return False
        # INSERT OR IGNORE makes concurrent /start updates safe for the same user.
        cur = await db.execute(
            "INSERT OR IGNORE INTO users "
            "(user_id, username, first_name, join_date, referred_by, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, username, first_name, now, referred_by, now),
        )
        created = cur.rowcount == 1
        await db.execute(
            "UPDATE users SET username=?, first_name=?, last_seen=? WHERE user_id=?",
            (username, first_name, now, user_id),
        )
        await db.execute(
            "INSERT OR IGNORE INTO wallet (user_id, coins) VALUES (?, 0)", (user_id,)
        )
        await db.commit()
        return created


async def is_admin(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    async with db_conn() as db:
        cur = await db.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,))
        return (await cur.fetchone()) is not None


async def is_banned(user_id: int) -> bool:
    async with db_conn() as db:
        cur = await db.execute("SELECT is_banned FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return bool(row and row[0])


async def get_user_row(user_id: int):
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        return await cur.fetchone()


async def get_balance(user_id: int) -> int:
    async with db_conn() as db:
        cur = await db.execute("SELECT coins FROM wallet WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        if row is None:
            await db.execute("INSERT OR IGNORE INTO wallet (user_id, coins) VALUES (?, 0)", (user_id,))
            await db.commit()
            return 0
        return row[0]


async def add_coins(user_id: int, amount: int, tx_type: str, description: str = "") -> int:
    async with _db_lock:
        async with db_conn() as db:
            await db.execute(
                "INSERT INTO wallet (user_id, coins) VALUES (?, 0) "
                "ON CONFLICT(user_id) DO NOTHING", (user_id,)
            )
            await db.execute(
                "UPDATE wallet SET coins = coins + ? WHERE user_id=?", (amount, user_id)
            )
            await db.execute(
                "INSERT INTO transactions (user_id, tx_type, amount, description, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, tx_type, amount, description, utcnow().isoformat()),
            )
            await db.commit()
            cur = await db.execute("SELECT coins FROM wallet WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            return row[0]


async def remove_coins(user_id: int, amount: int, tx_type: str, description: str = "") -> bool:
    async with _db_lock:
        async with db_conn() as db:
            cur = await db.execute("SELECT coins FROM wallet WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            bal = row[0] if row else 0
            if bal < amount:
                return False
            await db.execute(
                "UPDATE wallet SET coins = coins - ? WHERE user_id=?", (amount, user_id)
            )
            await db.execute(
                "INSERT INTO transactions (user_id, tx_type, amount, description, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, tx_type, -amount, description, utcnow().isoformat()),
            )
            await db.commit()
            return True


async def get_premium(user_id: int):
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM premium WHERE user_id=?", (user_id,))
        return await cur.fetchone()


async def is_premium_active(user_id: int) -> bool:
    row = await get_premium(user_id)
    if not row:
        return False
    if row["is_lifetime"]:
        return True
    if row["expiry_date"] and datetime.fromisoformat(row["expiry_date"]) > utcnow():
        return True
    return False


async def grant_premium(user_id: int, days: int | None, admin_id: int) -> None:
    async with db_conn() as db:
        if days is None:
            await db.execute(
                "INSERT INTO premium (user_id, expiry_date, is_lifetime, granted_by, granted_at) "
                "VALUES (?, NULL, 1, ?, ?) ON CONFLICT(user_id) DO UPDATE SET "
                "expiry_date=NULL, is_lifetime=1, granted_by=excluded.granted_by, granted_at=excluded.granted_at",
                (user_id, admin_id, utcnow().isoformat()),
            )
        else:
            expiry = (utcnow() + timedelta(days=days)).isoformat()
            await db.execute(
                "INSERT INTO premium (user_id, expiry_date, is_lifetime, granted_by, granted_at) "
                "VALUES (?, ?, 0, ?, ?) ON CONFLICT(user_id) DO UPDATE SET "
                "expiry_date=excluded.expiry_date, is_lifetime=0, granted_by=excluded.granted_by, granted_at=excluded.granted_at",
                (user_id, expiry, admin_id, utcnow().isoformat()),
            )
        await db.commit()


async def remove_premium(user_id: int) -> None:
    async with db_conn() as db:
        await db.execute("DELETE FROM premium WHERE user_id=?", (user_id,))
        await db.commit()


# ---------------------------------------------------------------------------
# KEYBOARDS
# ---------------------------------------------------------------------------
def user_reply_keyboard(admin: bool) -> ReplyKeyboardMarkup:
    rows = [
        [_reply_btn("📁 Buy Files",   style="success"),
         _reply_btn("💰 My Wallet",   style="success")],
        [_reply_btn("🎁 Daily Bonus", style="success"),
         _reply_btn("🎰 Daily Spin",  style="success")],

        [_reply_btn("📦 Mystery Box",   style="danger"),
         _reply_btn("🚀 Invite Friends", style="danger")],
        [_reply_btn("🎟️ Redeem Code",   style="danger"),
         _reply_btn("📊 My Stats",      style="danger")],

        [_reply_btn("🏆 Leaderboard",   style="primary"),
         _reply_btn("🎫 Support Ticket", style="primary")],
        [_reply_btn("💎 Buy Premium",   style="primary"),
         _reply_btn("💬 Support",       style="primary")],
    ]
    if admin:
        rows.append([_reply_btn("👑 Admin Panel", style="danger")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def admin_reply_keyboard(is_owner: bool = True) -> ReplyKeyboardMarkup:
    admin_mgr_label = "🛡 Admin Manager" if is_owner else "📋 Admin List"
    buttons = ["📤 Upload File", "📂 Manage Files", "💰 Wallet Manager", "🎟 Redeem Manager"]
    if is_owner:
        buttons += ["📢 Force Channels"]
    buttons += ["📢 Broadcast", "👥 User Manager", "👥 All Users", "👑 Premium Manager", "📊 Statistics", "🛠 Maintenance"]
    if is_owner:
        buttons += ["⚙ Settings"]
    buttons += [admin_mgr_label]

    rows = [
        [_reply_btn(buttons[i], style="danger")] + (
            [_reply_btn(buttons[i + 1], style="danger")] if i + 1 < len(buttons) else []
        )
        for i in range(0, len(buttons), 2)
    ]
    rows.append([_reply_btn("⬅️ Back to Main", style="danger")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [_kb_btn("📤 Upload File", callback_data="ad:upload", style="success"),
         _kb_btn("📂 Manage Files", callback_data="ad:managefiles", style="primary")],
        [_kb_btn("💰 Wallet Manager", callback_data="ad:walletmgr", style="primary"),
         _kb_btn("🎟 Redeem Manager", callback_data="ad:redeemmgr", style="primary")],
        [_kb_btn("📢 Force Channels", callback_data="ad:fcmgr", style="primary"),
         _kb_btn("📢 Broadcast", callback_data="ad:broadcast", style="primary")],
        [_kb_btn("👥 User Manager", callback_data="ad:usermgr", style="primary"),
         _kb_btn("👑 Premium Manager", callback_data="ad:premiummgr", style="primary")],
        [_kb_btn("📊 Statistics", callback_data="ad:stats", style="primary"),
         _kb_btn("🛠 Maintenance", callback_data="ad:maintenance", style="danger")],
        [_kb_btn("⚙ Settings", callback_data="ad:settings", style="success"),
         _kb_btn("🛡 Admin Manager", callback_data="ad:adminmgr", style="danger")],
    ]
    return InlineKeyboardMarkup(rows)


def back_button(cb: str = "ad:home") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[_kb_btn("⬅️ Back", callback_data=cb, style="primary")]])


# ---------------------------------------------------------------------------
# FORCE JOIN helpers
# ---------------------------------------------------------------------------
async def list_force_channels():
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM force_channels ORDER BY id")
        return await cur.fetchall()


async def _detect_chat_join_type(bot, chat_id: int) -> dict:
    info = {
        "join_by_request": False,
        "is_private": False,
        "bot_can_verify": False,
        "invite_link": None,
        "title": None,
        "chat_type": None,
    }
    try:
        chat = await bot.get_chat(chat_id)
    except TelegramError as e:
        log.warning("get_chat failed for %s: %s", chat_id, e)
        return info

    info["title"] = chat.title
    info["chat_type"] = _safe_chat_type(chat)
    info["is_private"] = chat.username is None

    jbr = None
    try:
        jbr = getattr(chat, "join_by_request", None)
    except Exception:
        jbr = None

    if jbr is None:
        invite = getattr(chat, "invite_link", None)
        if invite:
            info["invite_link"] = invite
            if info["is_private"]:
                jbr = True

    info["join_by_request"] = bool(jbr) if jbr is not None else False

    if not info["invite_link"]:
        info["invite_link"] = getattr(chat, "invite_link", None)

    try:
        me = await bot.get_me()
        me_member = await bot.get_chat_member(chat_id, me.id)
        if me_member.status in ("administrator", "creator"):
            info["bot_can_verify"] = True
    except TelegramError as e:
        log.warning("bot membership check failed for %s: %s", chat_id, e)
        info["bot_can_verify"] = False

    return info


async def _get_chat_member_status(bot, chat_id: int, user_id: int):
    """Return Telegram's ChatMember object, or None when membership cannot be verified."""
    try:
        return await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
    except TelegramError as e:
        log.warning("get_chat_member failed for chat %s user %s: %s", chat_id, user_id, e)
        return None


async def _ensure_invite_link(bot, chat_id: int, existing_link: str | None) -> str | None:
    if existing_link and existing_link.startswith("https://t.me/"):
        return existing_link

    try:
        chat = await bot.get_chat(chat_id)
        if getattr(chat, "username", None):
            return f"https://t.me/{chat.username}"
        if getattr(chat, "invite_link", None):
            return chat.invite_link
    except TelegramError as e:
        log.warning("get_chat failed for %s: %s", chat_id, e)
        return None

    try:
        link_obj = await bot.create_chat_invite_link(chat_id=chat_id, name="Force Join Link")
        return link_obj.invite_link
    except TelegramError as e:
        log.warning("create_chat_invite_link failed for %s: %s", chat_id, e)
        return None


async def check_force_join(bot, user_id: int) -> list[dict]:
    if (await get_setting("force_join", "1")) != "1":
        return []
    channels = await list_force_channels()
    if not channels:
        return []

    missing: list[dict] = []
    for ch in channels:
        chat_id = ch["chat_id"]
        if chat_id is None:
            if ch["username"]:
                try:
                    chat = await bot.get_chat(ch["username"])
                    chat_id = chat.id
                except TelegramError as e:
                    log.warning("Could not resolve force channel %s: %s", ch["username"], e)
                    missing.append(dict(ch))
                    continue
            else:
                log.error("Force-join channel row %s has neither chat_id nor username", ch.get("id"))
                missing.append(dict(ch))
                continue

        keys = ch.keys()
        has_detect = "join_by_request" in keys and "is_private" in keys
        cached_jbr = ch["join_by_request"] if has_detect else None
        cached_priv = ch["is_private"] if has_detect else None

        if not has_detect or (cached_jbr is None and cached_priv is None):
            info = await _detect_chat_join_type(bot, chat_id)
            jbr_flag = 1 if info["join_by_request"] else 0
            priv_flag = 1 if info["is_private"] else 0
            async with db_conn() as db:
                await db.execute(
                    "UPDATE force_channels SET join_by_request=?, is_private=?, "
                    "title=COALESCE(title, ?), chat_type=COALESCE(chat_type, ?), "
                    "invite_link=COALESCE(invite_link, ?) WHERE id=?",
                    (jbr_flag, priv_flag, info["title"], info["chat_type"], info["invite_link"], ch["id"]),
                )
                await db.commit()
            join_by_request = info["join_by_request"]
            is_private = info["is_private"]
        else:
            join_by_request = bool(cached_jbr)
            is_private = bool(cached_priv)

        member = await _get_chat_member_status(bot, chat_id, user_id)
        status = getattr(member, "status", None)
        is_member = getattr(member, "is_member", True) if member is not None else False

        # Telegram's `restricted` status is only a valid membership when is_member=True.
        if status in ("creator", "administrator", "member") or (status == "restricted" and is_member):
            continue

        ch_dict = dict(ch)
        ch_dict["join_by_request"] = join_by_request
        ch_dict["is_private"] = is_private
        missing.append(ch_dict)

    return missing


async def send_force_join_prompt(update: Update, missing: list[dict]) -> None:
    buttons = []
    has_approval_channel = False
    has_unresolvable = False

    for ch in missing:
        if ch.get("username"):
            url = f"https://t.me/{ch['username'].lstrip('@')}"
        elif ch.get("invite_link"):
            url = ch["invite_link"]
        else:
            has_unresolvable = True
            log.warning("Force-join channel '%s' has no resolvable invite link.", ch.get("title"))
            continue

        is_approval = bool(ch.get("join_by_request"))
        if is_approval:
            has_approval_channel = True
            label = f"🔒 {ch['title']} (Approval Required)"
        else:
            label = f"📢 {ch['title']}"
        buttons.append([InlineKeyboardButton(label, url=url)])

    if not buttons and not has_unresolvable:
        return

    buttons.append([InlineKeyboardButton("✅ Verify", callback_data="verify_join")])

    text = (
        "🔒 <b>Access Restricted</b>\n\n"
        "To use this bot, please join <b>all</b> required channels/groups below, "
        "then tap <b>✅ Verify</b>.\n\n"
    )
    if has_approval_channel:
        text += (
            "⚠️ <b>Note:</b> Some channels have <b>Join Request Approval</b> enabled. "
            "After sending your join request, wait for admin approval before tapping Verify.\n\n"
        )
    if has_unresolvable:
        text += "⚠️ Some channels could not be resolved. Please contact support.\n\n"
    text += "<i>Joining alone won't unlock access — you must verify after joining.</i>"

    if update.callback_query:
        await update.callback_query.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML
        )
    else:
        await update.effective_message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML
        )


# ---- Conversation States ----
(UP_FILE, UP_NAME, UP_DESC, UP_PRICE, UP_PREVIEW) = range(5)
(BC_PKG, BC_STARS, BC_SCREENSHOT) = range(10, 13)
BC_CUSTOM_STARS = 13
(RD_CODE,) = range(20, 21)
(FC_ADD,) = range(30, 31)
(UM_SEARCH, UM_AMOUNT) = range(40, 42)
(RM_CODE, RM_COINS, RM_PREMIUM, RM_LIMIT, RM_EXPIRY, RM_DELETE) = range(50, 56)
(BR_CONTENT,) = range(60, 61)
(ST_VALUE,) = range(70, 71)
(EF_FIELD,) = range(80, 81)
(WB_IDS, WB_ACTION, WB_AMOUNT, WB_PREMIUM) = range(90, 94)
(INR_AMOUNT, INR_PROOF) = range(94, 96)
(GC_AMOUNT,) = range(96, 97)
(AM_ADD_USER, AM_ADD_ROLE) = range(97, 99)
(TK_SUBJECT, TK_BODY, TK_REPLY, TK_USER_REPLY) = range(99, 103)
(FR_TEXT,) = range(103, 104)
(MF_SEARCH,) = range(104, 105)
(WELCOME_SET,) = range(105, 106)


ADMIN_ONLY_MSG = "🚫 This action is for admins only."
OWNER_ONLY_MSG = "🚫 This is restricted to the Owner only. Senior/Junior admins don't have access to this section."
ADMIN_MAX_REDEEM_COINS = 300
ADMIN_MIN_REDEEM_COINS = 20
ADMIN_DAILY_REDEEM_LIMIT = 2


async def require_owner(update: Update) -> bool:
    if update.effective_user.id == OWNER_ID:
        return True
    if update.callback_query:
        await update.callback_query.answer(OWNER_ONLY_MSG, show_alert=True)
    else:
        await update.effective_message.reply_text(OWNER_ONLY_MSG)
    return False


def fmt_size(num: int) -> str:
    step = 1024.0
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < step:
            return f"{num:.1f} {unit}" if unit != "B" else f"{int(num)} {unit}"
        num /= step
    return f"{num:.1f} PB"


def fmt_date(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(iso).strftime("%d %b %Y, %H:%M")
    except Exception:
        return iso


async def _update_login_streak(bot, user_id: int) -> None:
    today = india_now().strftime("%Y-%m-%d")
    async with db_conn() as db:
        cur = await db.execute("SELECT login_streak, last_login_date FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        if not row:
            return
        streak, last_date = row[0] or 0, row[1]
        if last_date == today:
            return

        yesterday = (india_now().date() - timedelta(days=1)).strftime("%Y-%m-%d")
        new_streak = streak + 1 if last_date == yesterday else 1
        await db.execute(
            "UPDATE users SET login_streak=?, last_login_date=? WHERE user_id=?", (new_streak, today, user_id)
        )
        await db.commit()

    rewards = await get_json_setting("streak_rewards", json.loads(DEFAULT_SETTINGS["streak_rewards"]), list)
    for r in rewards:
        if r["days"] == new_streak:
            await add_coins(user_id, r["reward"], "login_streak", f"{new_streak}-day login streak bonus")
            try:
                await bot.send_message(
                    user_id,
                    f"🔥 <b>{new_streak}-Day Login Streak!</b>\n\n🪙 Bonus: <b>+{r['reward']} Coins</b>\n\nKeep it going!",
                    parse_mode=ParseMode.HTML,
                )
            except TelegramError:
                pass
            break


async def guard_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if user is None:
        return False

    await ensure_user(user.id, user.username, user.first_name)
    await _update_login_streak(context.bot, user.id)

    admin = await is_admin(user.id)

    maintenance = (await get_setting("maintenance", "0")) == "1"
    if maintenance and not admin:
        await update.effective_message.reply_text(
            "🚧 <b>Bot is under maintenance.</b>\nPlease try again later.",
            parse_mode=ParseMode.HTML,
        )
        return False

    if await is_banned(user.id):
        await update.effective_message.reply_text(
            "🚫 You have been banned from using this bot. Contact support if you think this is a mistake."
        )
        return False

    if not admin:
        missing = await check_force_join(context.bot, user.id)
        if missing:
            await add_coins(user.id, 0, "force_join_blocked", "User blocked by force-join")
            await send_force_join_prompt(update, missing)
            return False

    return True


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    args = context.args

    maintenance = (await get_setting("maintenance", "0")) == "1"
    admin = await is_admin(user.id)
    if maintenance and not admin:
        await update.effective_message.reply_text(
            "🚧 <b>Bot is under maintenance.</b>\nPlease try again later.",
            parse_mode=ParseMode.HTML,
        )
        return

    if await is_banned(user.id):
        await update.effective_message.reply_text("🚫 You have been banned from using this bot.")
        return

    referred_by = None
    if args and args[0].isdigit():
        ref_id = int(args[0])
        if ref_id != user.id:
            existing = await get_user_row(user.id)
            if existing is None:
                referred_by = ref_id

    is_new = await ensure_user(user.id, user.username, user.first_name, referred_by)

    if not admin:
        missing = await check_force_join(context.bot, user.id)
        if missing:
            await add_coins(user.id, 0, "force_join_blocked", "User blocked by force-join (start)")
            await send_force_join_prompt(update, missing)
            return

    await maybe_process_referral(context.bot, user.id)

    await show_main_menu(update, context)


async def maybe_process_referral(bot, user_id: int) -> None:
    row = await get_user_row(user_id)
    if row and row["referred_by"]:
        await process_referral(bot, row["referred_by"], user_id)


async def process_referral(bot, referrer_id: int, new_user_id: int) -> None:
    async with db_conn() as db:
        cur = await db.execute("SELECT 1 FROM users WHERE user_id=?", (referrer_id,))
        if not await cur.fetchone():
            return
        cur = await db.execute("SELECT 1 FROM referrals WHERE new_user_id=?", (new_user_id,))
        if await cur.fetchone():
            return
        reward = int(await get_setting("referral_reward", "20"))
        await db.execute(
            "INSERT INTO referrals (referrer_id, new_user_id, date, reward) VALUES (?, ?, ?, ?)",
            (referrer_id, new_user_id, utcnow().isoformat(), reward),
        )
        await db.commit()

    new_balance = await add_coins(referrer_id, reward, "referral", f"Referral bonus for inviting user {new_user_id}")

    new_user_row = await get_user_row(new_user_id)
    if new_user_row and new_user_row["username"]:
        uname = f"@{new_user_row['username']}"
    elif new_user_row and new_user_row["first_name"]:
        uname = new_user_row["first_name"]
    else:
        uname = f"User {new_user_id}"

    try:
        await bot.send_message(
            referrer_id,
            "🎉 <b>New Referral Alert!</b> 🎉\n\n"
            f"👤 <b>User:</b> {html.escape(uname)}\n"
            f"🪙 <b>You earned:</b> +{reward} coins\n"
            f"💰 <b>Your new balance:</b> {new_balance} coins",
            parse_mode=ParseMode.HTML,
        )
    except TelegramError:
        pass

    await _check_referral_milestone(bot, referrer_id)


async def _check_referral_milestone(bot, referrer_id: int) -> None:
    async with db_conn() as db:
        cur = await db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (referrer_id,))
        total = (await cur.fetchone())[0]
        cur = await db.execute("SELECT referral_milestone_reached FROM users WHERE user_id=?", (referrer_id,))
        row = await cur.fetchone()
        already_reached = row[0] if row and row[0] else 0

    milestones = await get_json_setting("referral_milestones", json.loads(DEFAULT_SETTINGS["referral_milestones"]), list)
    for m in sorted(milestones, key=lambda x: x["count"]):
        if total >= m["count"] > already_reached:
            await add_coins(referrer_id, m["reward"], "referral_milestone", f"Referral milestone: {m['count']} referrals")
            async with db_conn() as db:
                await db.execute("UPDATE users SET referral_milestone_reached=? WHERE user_id=?", (m["count"], referrer_id))
                await db.commit()
            try:
                await bot.send_message(
                    referrer_id,
                    f"🏆 <b>Referral Milestone Reached!</b>\n\n"
                    f"🚀 You've referred <b>{m['count']}</b> people!\n"
                    f"🪙 Bonus: <b>+{m['reward']} Coins</b>",
                    parse_mode=ParseMode.HTML,
                )
            except TelegramError:
                pass
            break


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    admin = await is_admin(user.id)

    bot_name = await get_setting("bot_name", "NAGENDRA FILE STORE")
    balance = await get_balance(user.id)

    async with db_conn() as db:
        cur = await db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user.id,))
        ref_count = (await cur.fetchone())[0]

    is_premium = await is_premium_active(user.id)
    premium_line = "👑 <b>Premium — Active</b>" if is_premium else "⭐ Premium: <i>Not Active</i>"
    name_tag = f"👑 {html.escape(user.first_name or 'Friend')}" if is_premium else html.escape(user.first_name or "Friend")

    text = (
        f"👋 <b>Welcome, {name_tag}!</b>\n\n"
        f"🏷 <b>{html.escape(bot_name)}</b>\n"
        f"──────────\n"
        f"💰 <b>Wallet:</b> {balance} Coins\n"
        f"👥 <b>Referrals:</b> {ref_count}\n"
        f"{premium_line}\n"
        f"──────────\n\n"
        f"Use the menu below to get started 👇"
    )
    await update.effective_message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=user_reply_keyboard(admin)
    )


async def cb_verify_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    try:
        missing = await check_force_join(context.bot, user.id)
    except (TelegramError, aiosqlite.Error) as exc:
        log.warning("Force-join verification temporarily failed for user %s: %s", user.id, exc)
        await query.answer("⚠️ Couldn't verify membership right now. Please try again shortly.", show_alert=True)
        return
    if missing:
        approval_channels = [ch for ch in missing if ch.get("join_by_request")]
        if approval_channels:
            names = ", ".join(f"<b>{html.escape(ch['title'])}</b>" for ch in approval_channels)
            await query.answer(
                f"⏳ Your join request for {names} is still pending admin approval. "
                f"Please wait for approval, then tap Verify again.",
                show_alert=True,
            )
        else:
            await query.answer(
                "❌ You haven't joined all required channels/groups yet. Please join them, then tap Verify again.",
                show_alert=True,
            )
        return
    await query.answer("✅ Verified! You can now use the bot.")
    try:
        await query.message.delete()
    except BadRequest:
        pass
    await ensure_user(user.id, user.username, user.first_name)
    await maybe_process_referral(context.bot, user.id)
    await show_main_menu(update, context)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard_user(update, context):
        return
    text = (
        "📖 <b>Help & Guide</b>\n\n"
        "📁 <b>Buy Files</b> — Browse and purchase files with coins.\n"
        "🪙 <b>Coins</b> — Buy coins with Telegram Stars, or earn them free via "
        "Daily Bonus, Referrals, and Redeem Codes.\n"
        "👥 <b>Referral</b> — Share your personal link, earn coins per new user.\n"
        "🎟️ <b>Redeem</b> — Enter a code from the admin to instantly get coins.\n"
        "💎 <b>Buy Premium</b> — Get premium via Stars or coin exchange.\n"
        "💬 <b>Support</b> — Reach out any time via the Support menu.\n"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def handle_support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard_user(update, context):
        return
    support_username = await get_setting("support_username", "NagendraOwnerBack")
    text = (
        "💬 <b>Support</b>\n\n"
        f"👤 Contact: @{html.escape(support_username)}\n"
        "🕒 Business Hours: 08:00 AM — 11:00 PM (IST)\n\n"
        "We usually reply within a few hours."
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


async def handle_support_ticket_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await guard_user(update, context):
        return ConversationHandler.END
    await update.effective_message.reply_text(
        "🎫 <b>Open a Support Ticket</b>\n\nWhat's the subject? (short, one line):",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[_kb_btn("❌ Cancel", callback_data="ticket:cancel", style="danger")]]),
    )
    return TK_SUBJECT


async def cb_ticket_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("❌ Cancelled.")
    context.user_data.pop("tk_subject", None)
    return ConversationHandler.END


async def conv_ticket_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    subject = update.message.text.strip()
    if len(subject) > 100:
        await update.message.reply_text("❌ Please keep the subject under 100 characters.")
        return TK_SUBJECT
    context.user_data["tk_subject"] = subject
    await update.message.reply_text("📝 Now describe your issue in detail:")
    return TK_BODY


async def conv_ticket_body(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    body = update.message.text.strip()
    subject = context.user_data.pop("tk_subject", "")
    user = update.effective_user

    async with db_conn() as db:
        await db.execute(
            "INSERT INTO tickets (user_id, subject, body, status, created_at) VALUES (?, ?, ?, 'open', ?)",
            (user.id, subject, body, utcnow().isoformat()),
        )
        await db.commit()
        cur = await db.execute("SELECT last_insert_rowid()")
        ticket_id = (await cur.fetchone())[0]

    await update.message.reply_text(
        f"✅ <b>Ticket #{ticket_id} Submitted!</b>\n\nOur team will get back to you soon.",
        parse_mode=ParseMode.HTML,
    )

    uname = f"@{user.username}" if user.username else "—"
    notify = (
        f"🎫 <b>New Support Ticket #{ticket_id}</b>\n\n"
        f"👤 From: {html.escape(uname)}\n🆔 User ID: <code>{user.id}</code>\n"
        f"📌 Subject: {html.escape(subject)}\n\n📝 {html.escape(body)}"
    )
    kb = InlineKeyboardMarkup([
        [_kb_btn("💬 Reply", callback_data=f"ticket:reply:{ticket_id}", style="primary"),
         _kb_btn("✅ Close", callback_data=f"ticket:close:{ticket_id}", style="success")],
    ])
    for admin_id in await get_all_admin_ids():
        try:
            await context.bot.send_message(admin_id, notify, parse_mode=ParseMode.HTML, reply_markup=kb)
        except TelegramError:
            pass
    return ConversationHandler.END


async def cb_ticket_reply_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not await is_admin(update.effective_user.id):
        await query.answer(ADMIN_ONLY_MSG, show_alert=True)
        return ConversationHandler.END
    await query.answer()
    ticket_id = int(query.data.split(":")[2])
    context.user_data["tk_reply_id"] = ticket_id
    await query.message.reply_text("💬 Type your reply — it will be sent to the user:")
    return TK_REPLY


async def conv_ticket_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ticket_id = context.user_data.pop("tk_reply_id", None)
    if ticket_id is None:
        await update.message.reply_text("❌ Something went wrong — please try again.")
        return ConversationHandler.END
    reply_text = update.message.text.strip()

    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM tickets WHERE ticket_id=?", (ticket_id,))
        ticket = await cur.fetchone()

    if not ticket:
        await update.message.reply_text("❌ Ticket not found.")
        return ConversationHandler.END
    if ticket["status"] != "open":
        await update.message.reply_text("🚫 This ticket is already closed.")
        return ConversationHandler.END

    user_kb = InlineKeyboardMarkup([[_kb_btn("💬 Reply", callback_data=f"ticket:ureply:{ticket_id}", style="primary")]])
    try:
        await context.bot.send_message(
            ticket["user_id"],
            f"🎫 <b>Support Reply (Ticket #{ticket_id})</b>\n\n{html.escape(reply_text)}",
            parse_mode=ParseMode.HTML,
            reply_markup=user_kb,
        )
        await update.message.reply_text("✅ Reply sent to the user.")
    except TelegramError:
        await update.message.reply_text("⚠️ Couldn't deliver the reply — the user may have blocked the bot.")

    await log_admin_action(context.bot, update.effective_user.id, f"💬 Replied to ticket #{ticket_id}")
    return ConversationHandler.END


async def cb_ticket_user_reply_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    ticket_id = int(query.data.split(":")[2])
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM tickets WHERE ticket_id=?", (ticket_id,))
        ticket = await cur.fetchone()

    if not ticket:
        await query.answer("❌ Ticket not found.", show_alert=True)
        return ConversationHandler.END
    if ticket["user_id"] != update.effective_user.id:
        await query.answer("🚫 This isn't your ticket.", show_alert=True)
        return ConversationHandler.END
    if ticket["status"] != "open":
        await query.answer("🚫 This ticket is already closed.", show_alert=True)
        return ConversationHandler.END

    await query.answer()
    context.user_data["tk_user_reply_id"] = ticket_id
    await query.message.reply_text(
        "💬 Type your reply:",
        reply_markup=InlineKeyboardMarkup([[_kb_btn("❌ Cancel", callback_data="ticket:cancel", style="danger")]]),
    )
    return TK_USER_REPLY


async def conv_ticket_user_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ticket_id = context.user_data.pop("tk_user_reply_id", None)
    if ticket_id is None:
        await update.message.reply_text("❌ Something went wrong — please try again.")
        return ConversationHandler.END
    reply_text = update.message.text.strip()
    user = update.effective_user

    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM tickets WHERE ticket_id=?", (ticket_id,))
        ticket = await cur.fetchone()

    if not ticket:
        await update.message.reply_text("❌ Ticket not found.")
        return ConversationHandler.END
    if ticket["status"] != "open":
        await update.message.reply_text("🚫 This ticket is already closed.")
        return ConversationHandler.END

    await update.message.reply_text("✅ Reply sent to support.")

    uname = f"@{user.username}" if user.username else "—"
    notify = (
        f"🎫 <b>Ticket #{ticket_id} — User Reply</b>\n\n"
        f"👤 From: {html.escape(uname)}\n🆔 User ID: <code>{user.id}</code>\n\n💬 {html.escape(reply_text)}"
    )
    kb = InlineKeyboardMarkup([
        [_kb_btn("💬 Reply", callback_data=f"ticket:reply:{ticket_id}", style="primary"),
         _kb_btn("✅ Close", callback_data=f"ticket:close:{ticket_id}", style="success")],
    ])
    for admin_id in await get_all_admin_ids():
        try:
            await context.bot.send_message(admin_id, notify, parse_mode=ParseMode.HTML, reply_markup=kb)
        except TelegramError:
            pass
    return ConversationHandler.END


async def cb_ticket_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await is_admin(update.effective_user.id):
        await query.answer(ADMIN_ONLY_MSG, show_alert=True)
        return
    ticket_id = int(query.data.split(":")[2])
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM tickets WHERE ticket_id=?", (ticket_id,))
        ticket = await cur.fetchone()
        if not ticket:
            await query.answer("❌ Not found.", show_alert=True)
            return
        await db.execute(
            "UPDATE tickets SET status='closed', admin_id=?, closed_at=? WHERE ticket_id=?",
            (update.effective_user.id, utcnow().isoformat(), ticket_id),
        )
        await db.commit()
    await query.answer("✅ Closed")
    try:
        await query.message.delete()
    except TelegramError:
        pass
    try:
        await context.bot.send_message(
            ticket["user_id"], f"✅ <b>Your ticket #{ticket_id} has been closed.</b>", parse_mode=ParseMode.HTML
        )
    except TelegramError:
        pass
    await log_admin_action(context.bot, update.effective_user.id, f"✅ Closed ticket #{ticket_id}")


async def handle_file_request_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await guard_user(update, context):
        return ConversationHandler.END
    await update.effective_message.reply_text(
        "📥 <b>Request a File</b>\n\nTell us what file/project you're looking for — we'll try to add it:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[_kb_btn("❌ Cancel", callback_data="freq:cancel", style="danger")]]),
    )
    return FR_TEXT


async def cb_file_request_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


async def conv_file_request_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    user = update.effective_user

    async with db_conn() as db:
        await db.execute(
            "INSERT INTO file_requests (user_id, request_text, status, timestamp) VALUES (?, ?, 'open', ?)",
            (user.id, text, utcnow().isoformat()),
        )
        await db.commit()
        cur = await db.execute("SELECT last_insert_rowid()")
        req_id = (await cur.fetchone())[0]

    await update.message.reply_text("✅ <b>Request Submitted!</b>\n\nThanks — we'll review it soon.", parse_mode=ParseMode.HTML)

    uname = f"@{user.username}" if user.username else "—"
    notify = (
        f"📥 <b>New File Request #{req_id}</b>\n\n"
        f"👤 From: {html.escape(uname)}\n🆔 User ID: <code>{user.id}</code>\n\n📝 {html.escape(text)}"
    )
    kb = InlineKeyboardMarkup([[_kb_btn("✅ Mark Fulfilled", callback_data=f"freq:done:{req_id}", style="success")]])
    for admin_id in await get_all_admin_ids():
        try:
            await context.bot.send_message(admin_id, notify, parse_mode=ParseMode.HTML, reply_markup=kb)
        except TelegramError:
            pass
    return ConversationHandler.END


async def cb_file_request_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await is_admin(update.effective_user.id):
        await query.answer(ADMIN_ONLY_MSG, show_alert=True)
        return
    req_id = int(query.data.split(":")[2])
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM file_requests WHERE request_id=?", (req_id,))
        req = await cur.fetchone()
        if not req:
            await query.answer("❌ Not found.", show_alert=True)
            return
        await db.execute("UPDATE file_requests SET status='fulfilled' WHERE request_id=?", (req_id,))
        await db.commit()
    await query.answer("✅ Marked fulfilled")
    try:
        await query.message.delete()
    except TelegramError:
        pass
    try:
        await context.bot.send_message(
            req["user_id"],
            f"✅ <b>Your file request has been fulfilled!</b>\n\n📝 {html.escape(req['request_text'])}\n\nCheck 📁 Buy Files!",
            parse_mode=ParseMode.HTML,
        )
    except TelegramError:
        pass
    await log_admin_action(context.bot, update.effective_user.id, f"✅ Fulfilled file request #{req_id}")


# ---------------------------------------------------------------------------
# WALLET
# ---------------------------------------------------------------------------
async def handle_my_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard_user(update, context):
        return
    await send_wallet_view(update, context)


async def send_wallet_view(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False) -> None:
    user = update.effective_user
    balance = await get_balance(user.id)
    async with db_conn() as db:
        cur = await db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user.id,))
        ref_count = (await cur.fetchone())[0]
    daily_status = await bonus_status_text(user.id)
    is_premium = await is_premium_active(user.id)
    premium_line = "👑 <b>Premium — Active</b>" if is_premium else "⭐ Premium: <i>Not Active</i>"

    text = (
        "💰 <b>My Wallet</b>\n"
        f"{DIVIDER}\n"
        f"🪙 <b>Coins:</b> {balance}\n"
        f"👥 <b>Total Referrals:</b> {ref_count}\n"
        f"🎁 <b>Daily Bonus:</b> {daily_status}\n"
        f"{premium_line}\n"
        f"{DIVIDER}"
    )
    buttons = [
        [_kb_btn("⭐ Buy Coins (Stars)", callback_data="wallet:buycoins", style="success"),
         _kb_btn("® Buy Coins (UPI)", callback_data="wallet:buyupi", style="primary")],
        [_kb_btn("📜 Transactions", callback_data="wallet:tx:0", style="primary")],
    ]
    if not is_premium:
        buttons.append([_kb_btn("💎 Buy Premium", callback_data="premium:menu", style="primary")])
    kb = InlineKeyboardMarkup(buttons)
    try:
        if edit and update.callback_query:
            await update.callback_query.edit_message_text(
                text, parse_mode=ParseMode.HTML, reply_markup=kb
            )
        else:
            message = update.effective_message
            if message is None:
                return
            await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    except (TimedOut, NetworkError) as exc:
        # These errors are usually temporary connectivity/Telegram API delays.
        # Do not automatically resend: a timed-out request may already have arrived.
        log.warning("Buy Files response timed out for user %s: %s",
                    getattr(update.effective_user, "id", "unknown"), exc)
        if update.callback_query:
            try:
                await update.callback_query.answer(
                    "Telegram is responding slowly. Please try again.", show_alert=True
                )
            except TelegramError:
                pass
    except TelegramError:
        log.exception("Telegram API error while showing Buy Files to user %s",
                      getattr(update.effective_user, "id", "unknown"))
        raise


async def cb_wallet_buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cb_premium_menu(update, context)


async def bonus_status_text(user_id: int) -> str:
    row = await get_user_row(user_id)
    if row and row["last_bonus_time"]:
        last = datetime.fromisoformat(row["last_bonus_time"])
        elapsed = utcnow() - last
        if elapsed < timedelta(hours=24):
            remaining = timedelta(hours=24) - elapsed
            h, rem = divmod(int(remaining.total_seconds()), 3600)
            m = rem // 60
            return f"⏳ Available in {h}h {m}m"
    return "✅ Available now"


async def cb_wallet_tx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    page = int(query.data.split(":")[2])
    per_page = 8
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM transactions WHERE user_id=? ORDER BY tx_id DESC LIMIT ? OFFSET ?",
            (user.id, per_page, page * per_page),
        )
        rows = await cur.fetchall()

    if not rows and page == 0:
        text = "📜 <b>Transactions</b>\n\nNo transactions yet."
    else:
        lines = ["📜 <b>Transactions</b>\n"]
        for r in rows:
            sign = "+" if r["amount"] >= 0 else ""
            lines.append(
                f"{sign}{r['amount']} 🪙 — {html.escape(r['tx_type'])} "
                f"<i>({fmt_date(r['timestamp'])})</i>"
            )
        text = "\n".join(lines)

    nav = []
    if page > 0:
        nav.append(_kb_btn("⬅️ Prev", callback_data=f"wallet:tx:{page-1}", style="primary"))
    if len(rows) == per_page:
        nav.append(_kb_btn("Next ➡️", callback_data=f"wallet:tx:{page+1}", style="primary"))
    buttons = [nav] if nav else []
    buttons.append([_kb_btn("⬅️ Back", callback_data="wallet:home", style="primary")])
    await query.answer()
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))


async def cb_wallet_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    await send_wallet_view(update, context, edit=True)


# ---------------------------------------------------------------------------
# BUY PREMIUM
# ---------------------------------------------------------------------------
async def handle_buy_premium_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard_user(update, context):
        return
    user = update.effective_user
    if await is_premium_active(user.id):
        await update.effective_message.reply_text(
            "👑 <b>You already have Premium active!</b>\n\nEnjoy your benefits.",
            parse_mode=ParseMode.HTML,
        )
        return
    balance = await get_balance(user.id)
    premium_pricing = await get_json_setting("premium_pricing", json.loads(DEFAULT_SETTINGS["premium_pricing"]), list)
    payment_username = await get_setting("payment_username", "NagendraOwnerBack")

    lines = [
        f"💎 <b>Buy Premium</b>\n{DIVIDER}",
        f"🪙 Your balance: <b>{balance}</b> coins\n",
        "<b>Available Payment Methods:</b>\n",
        "1️⃣ <b>⭐ Buy with Stars</b> — send Stars to "
        f"<code>@{html.escape(payment_username)}</code> and submit proof.",
        "2️⃣ <b>🪙 Exchange Coins → Premium</b> — use your wallet coins instantly.\n",
        "<b>Coin → Premium Plans:</b>",
    ]
    for p in premium_pricing:
        label = "Lifetime" if p["days"] == 0 else f"{p['days']} Days"
        lines.append(f"• {label} — 🪙 {p['price']} coins")
    text = "\n".join(lines)
    kb = InlineKeyboardMarkup([
        [_kb_btn("⭐ Buy with Stars", callback_data="wallet:buycoins", style="success")],
        [_kb_btn("🪙 Exchange Coins → Premium", callback_data="premium:exchange", style="primary")],
        [_kb_btn("⬅️ Back", callback_data="wallet:home", style="primary")],
    ])
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def cb_premium_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if await is_premium_active(update.effective_user.id):
        await query.edit_message_text("👑 <b>You already have Premium active!</b>", parse_mode=ParseMode.HTML)
        return
    balance = await get_balance(update.effective_user.id)
    premium_pricing = await get_json_setting("premium_pricing", json.loads(DEFAULT_SETTINGS["premium_pricing"]), list)
    payment_username = await get_setting("payment_username", "NagendraOwnerBack")
    lines = [
        f"💎 <b>Buy Premium</b>\n{DIVIDER}",
        f"🪙 Your balance: <b>{balance}</b> coins\n",
        "1️⃣ ⭐ Buy with Stars — pay to "
        f"<code>@{html.escape(payment_username)}</code>",
        "2️⃣ 🪙 Exchange Coins → Premium\n",
        "<b>Coin → Premium Plans:</b>",
    ]
    for p in premium_pricing:
        label = "Lifetime" if p["days"] == 0 else f"{p['days']} Days"
        lines.append(f"• {label} — 🪙 {p['price']} coins")
    kb = InlineKeyboardMarkup([
        [_kb_btn("⭐ Buy with Stars", callback_data="wallet:buycoins", style="success")],
        [_kb_btn("🪙 Exchange Coins → Premium", callback_data="premium:exchange", style="primary")],
        [_kb_btn("⬅️ Back", callback_data="wallet:home", style="primary")],
    ])
    await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=kb)


async def cb_premium_exchange_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    if await is_premium_active(user.id):
        await query.answer("✅ You already have Premium active.", show_alert=True)
        return
    pricing = await get_json_setting("premium_pricing", json.loads(DEFAULT_SETTINGS["premium_pricing"]), list)
    balance = await get_balance(user.id)
    lines = [
        f"🪙 <b>Exchange Coins → Premium</b>\n{DIVIDER}",
        f"💰 Your balance: <b>{balance}</b> coins\n",
        "<i>Tap a plan. Coins are deducted atomically and Premium activates instantly.</i>",
    ]
    buttons = []
    for p in pricing:
        label = "Lifetime" if p["days"] == 0 else f"{p['days']} Days"
        affordable = "✅" if balance >= p["price"] else "❌"
        lines.append(f"{affordable} {label} — 🪙 {p['price']} coins")
        buttons.append([_kb_btn(
            f"{affordable} {label} — {p['price']} coins",
            callback_data=f"premium:buy:{p['days']}:{p['price']}",
            style="success" if balance >= p["price"] else "danger",
        )])
    buttons.append([_kb_btn("⬅️ Back", callback_data="premium:menu", style="primary")])
    await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))


async def cb_premium_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    parts = query.data.split(":")
    if len(parts) != 4:
        await query.answer("❌ Invalid premium request.", show_alert=True)
        return
    _, _, days, price = parts
    days, price = int(days), int(price)

    lock = await get_user_action_lock(user.id)
    async with lock:
        if await is_premium_active(user.id):
            await query.answer("✅ You already have Premium active.", show_alert=True)
            return
        ok = await remove_coins(user.id, price, "premium_purchase",
                                f"Bought Premium ({'Lifetime' if days == 0 else f'{days} days'})")
        if not ok:
            await query.answer("❌ Not enough Coins for this plan.", show_alert=True)
            return
        await grant_premium(user.id, None if days == 0 else days, admin_id=0)

    await query.answer("👑 Premium activated!")
    label = "Lifetime" if days == 0 else f"{days} Days"
    await query.edit_message_text(
        f"🎉 <b>Premium Activated!</b>\n\n👑 Plan: <b>{label}</b>\n🪙 Paid: <b>{price} coins</b>\n\n"
        "Enjoy your Premium badge, bonus multiplier, and priority support!",
        parse_mode=ParseMode.HTML,
    )


# ---------------------------------------------------------------------------
# PAYMENTS
# ---------------------------------------------------------------------------
async def cb_buycoins_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show real Telegram Stars invoices; credit is granted only after Telegram confirms payment."""
    query = update.callback_query
    await query.answer()
    packages = await get_json_setting("coin_packages", json.loads(DEFAULT_SETTINGS["coin_packages"]), list)
    rows = []
    for index, package in enumerate(packages[:20]):
        try:
            coins, stars = int(package["coins"]), int(package["stars"])
        except (KeyError, TypeError, ValueError):
            continue
        if coins > 0 and stars > 0:
            rows.append([_kb_btn(f"🪙 {coins:,} Coins — ⭐ {stars}", callback_data=f"stars:coins:{index}", style="success")])
    rows.append([_kb_btn("✏️ Custom Stars Amount", callback_data="stars:coins:custom", style="primary")])
    rows.append([_kb_btn("⬅️ Back", callback_data="wallet:home", style="primary")])
    await query.edit_message_text(
        "⭐ <b>Buy Coins with Telegram Stars</b>\n\nChoose a package or enter a custom Stars amount. Telegram will securely process the payment, and coins are credited automatically after confirmation.",
        parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(rows))
    return ConversationHandler.END


async def cb_custom_stars_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not await guard_user(update, context):
        return ConversationHandler.END
    await query.message.reply_text(
        "✏️ Send the number of Telegram Stars you want to pay (1–10000).\n"
        "Coins are calculated using the current configured Stars rate. Send /cancel to stop."
    )
    return BC_CUSTOM_STARS


async def conv_custom_stars_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return ConversationHandler.END
    raw = (message.text or "").strip()
    if not raw.isdigit() or not 1 <= int(raw) <= 10000:
        await message.reply_text("❌ Enter a whole number from 1 to 10000 Stars, or /cancel.")
        return BC_CUSTOM_STARS
    stars = int(raw)
    try:
        rate = float(await get_setting("star_rate", "30"))
        coins = int(stars * rate / 30 * 100)
    except (TypeError, ValueError):
        coins = 0
    if coins <= 0:
        await message.reply_text("❌ The configured Stars-to-Coins rate is invalid. Please contact support.")
        return ConversationHandler.END
    payload = f"coins:{user.id}:{coins}:{stars}:{secrets.token_urlsafe(8)}"
    await context.bot.send_invoice(
        chat_id=message.chat_id,
        title=f"{coins:,} Coins",
        description=f"Custom purchase: {stars:,} Telegram Stars for {coins:,} coins.",
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"{coins:,} Coins", amount=stars)],
        start_parameter=f"customcoins_{stars}",
    )
    return ConversationHandler.END


async def cb_stars_coin_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not await guard_user(update, context):
        return
    try:
        index = int((query.data or "").split(":")[2])
        packages = await get_json_setting("coin_packages", json.loads(DEFAULT_SETTINGS["coin_packages"]), list)
        package = packages[index]
        coins, stars = int(package["coins"]), int(package["stars"])
        if coins <= 0 or stars <= 0 or stars > 100000:
            raise ValueError("invalid package")
    except (IndexError, KeyError, TypeError, ValueError):
        await query.answer("This package is invalid. Please reopen the wallet.", show_alert=True)
        return
    payload = f"coins:{update.effective_user.id}:{coins}:{stars}:{secrets.token_urlsafe(8)}"
    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title=f"{coins:,} Coins",
        description=f"Add {coins:,} coins to your Nagendra File Store wallet.",
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"{coins:,} Coins", amount=stars)],
        start_parameter=f"coins_{coins}_{stars}",
    )


async def precheckout_star_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.pre_checkout_query
    try:
        parts = (query.invoice_payload or "").split(":")
        valid = (len(parts) == 5 and parts[0] == "coins" and int(parts[1]) == query.from_user.id
                 and int(parts[2]) > 0 and int(parts[3]) == query.total_amount and query.currency == "XTR")
    except (TypeError, ValueError):
        valid = False
    await query.answer(ok=valid, error_message=None if valid else "Payment details are invalid. Please create a new invoice.")


async def successful_star_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user
    payment = message.successful_payment if message else None
    if not payment or not user:
        return
    try:
        parts = payment.invoice_payload.split(":")
        if len(parts) != 5 or parts[0] != "coins" or int(parts[1]) != user.id:
            raise ValueError("invalid payload")
        coins, expected_stars = int(parts[2]), int(parts[3])
        if payment.currency != "XTR" or payment.total_amount != expected_stars or coins <= 0:
            raise ValueError("payment amount mismatch")
        charge_id = payment.telegram_payment_charge_id
        async with db_conn() as db:
            await db.execute(
                "INSERT OR IGNORE INTO telegram_star_charges(charge_id,user_id,coins,stars,created_at) VALUES(?,?,?,?,?)",
                (charge_id, user.id, coins, expected_stars, utcnow().isoformat()))
            await db.commit()
            cur = await db.execute("SELECT changes()")
            inserted = (await cur.fetchone())[0] == 1
        if not inserted:
            await message.reply_text("✅ This Telegram Stars payment was already processed.")
            return
        balance = await add_coins(user.id, coins, "stars_purchase", f"Telegram Stars payment ({expected_stars} XTR)")
        await message.reply_text(
            f"✅ <b>Payment successful!</b>\n\n⭐ Paid: <b>{expected_stars} Stars</b>\n"
            f"🪙 Added: <b>{coins:,} coins</b>\n💰 Wallet balance: <b>{balance:,} coins</b>",
            parse_mode=ParseMode.HTML)
    except Exception:
        log.exception("Could not process successful Telegram Stars payment for user %s", user.id)
        await message.reply_text("Payment was received, but automatic credit needs support review. Please contact support with your Telegram payment receipt.")


async def cb_buycoins_paid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "⭐ How many Stars did you send? (numbers only)",
        reply_markup=InlineKeyboardMarkup([[_kb_btn("❌ Cancel", callback_data="buycoins:cancel", style="danger")]]),
    )
    return BC_STARS


async def conv_buycoins_stars(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("❌ Please send a valid number of Stars.")
        return BC_STARS
    context.user_data["bc_stars"] = int(text)
    await update.message.reply_text("📷 Please send your payment screenshot now.")
    return BC_SCREENSHOT


async def conv_buycoins_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.photo and not update.message.document:
        await update.message.reply_text("❌ Please send a screenshot as a photo or document.")
        return BC_SCREENSHOT

    file_id = update.message.photo[-1].file_id if update.message.photo else update.message.document.file_id
    stars = context.user_data.pop("bc_stars", None)
    if stars is None:
        await update.message.reply_text("❌ Session expired. Please start again.")
        return ConversationHandler.END
    user = update.effective_user

    async with db_conn() as db:
        cur = await db.execute("SELECT 1 FROM payments WHERE user_id=? AND status='pending'", (user.id,))
        if await cur.fetchone():
            await update.message.reply_text(
                "⚠️ You already have a pending payment request. Please wait for admin review."
            )
            return ConversationHandler.END

        packages = await get_json_setting("coin_packages", json.loads(DEFAULT_SETTINGS["coin_packages"]), list)
        coins = 0
        for p in packages:
            if p["stars"] == stars:
                coins = p["coins"]
                break
        if coins == 0:
            rate = float(await get_setting("star_rate", "30"))
            coins = int(stars * rate / 30 * 100)

        await db.execute(
            "INSERT INTO payments (user_id, stars, coins, screenshot_file_id, status, timestamp, payment_method) "
            "VALUES (?, ?, ?, ?, 'pending', ?, 'stars')",
            (user.id, stars, coins, file_id, utcnow().isoformat()),
        )
        await db.commit()
        cur = await db.execute("SELECT last_insert_rowid()")
        payment_id = (await cur.fetchone())[0]

    await update.message.reply_text(
        "✅ Your payment request has been submitted. You'll be notified once reviewed."
    )

    uname = f"@{user.username}" if user.username else "—"
    caption = (
        "💰 <b>New Payment Request</b>\n\n"
        f"👤 Username: {html.escape(uname)}\n"
        f"🆔 User ID: <code>{user.id}</code>\n"
        f"⭐ Stars: <b>{stars}</b>\n"
        f"🪙 Coins: <b>{coins}</b>\n"
        f"📅 Time: {fmt_date(utcnow().isoformat())}"
    )
    kb = InlineKeyboardMarkup([
        [_kb_btn("✅ Accept", callback_data=f"pay:accept:{payment_id}", style="success"),
         _kb_btn("❌ Reject", callback_data=f"pay:reject:{payment_id}", style="danger")]
    ])
    for admin_id in [OWNER_ID]:
        try:
            if update.message.photo:
                await context.bot.send_photo(admin_id, file_id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=kb)
            else:
                await context.bot.send_document(admin_id, file_id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=kb)
        except TelegramError:
            pass
    return ConversationHandler.END


async def cb_buycoins_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("❌ Cancelled.")
    context.user_data.pop("bc_stars", None)
    return ConversationHandler.END


async def handle_buy_coins_upi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.callback_query:
        await update.callback_query.answer()
    if not await guard_user(update, context):
        return
    upi_id = await get_setting("upi_payment_id", "9358163308@ptsbi")
    text = (
        "® <b>Buy Coins with UPI</b>\n"
        f"{DIVIDER}\n"
        f"💳 UPI ID: <code>{html.escape(upi_id)}</code>\n\n"
        "Send the amount via any UPI app (GPay, PhonePe, FamPay, etc.), then tap <b>® I Have Paid</b> below."
    )
    kb = InlineKeyboardMarkup([[_kb_btn("® I Have Paid", callback_data="buyupi:paid", style="primary")]])
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def cb_buyupi_paid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "💰 How many Rupees (₹) did you send? (numbers only)",
        reply_markup=InlineKeyboardMarkup([[_kb_btn("❌ Cancel", callback_data="buyupi:cancel", style="danger")]]),
    )
    return INR_AMOUNT


async def conv_buyupi_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("❌ Please send a valid amount.")
        return INR_AMOUNT
    context.user_data["upi_amount"] = int(text)
    await update.message.reply_text(
        "📷 Please send your UPI payment screenshot as a photo.\n"
    )
    return INR_PROOF


async def conv_buyupi_proof(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Accept photo screenshots only. Keep the amount in the session if the user
    # sends text, a document, or another unsupported message by mistake.
    if not update.message.photo:
        await update.message.reply_text(
            "❌ Screenshot required. Please send the payment screenshot as a photo.\n"
            "Text, transaction IDs, and documents are not accepted."
        )
        return INR_PROOF

    amount = context.user_data.get("upi_amount")
    if amount is None:
        await update.message.reply_text("❌ Something went wrong — please start again from ® Buy Coins (UPI).")
        return ConversationHandler.END

    file_id = update.message.photo[-1].file_id
    user = update.effective_user

    async with db_conn() as db:
        cur = await db.execute("SELECT 1 FROM payments WHERE user_id=? AND status='pending'", (user.id,))
        if await cur.fetchone():
            context.user_data.pop("upi_amount", None)
            await update.message.reply_text("⚠️ You already have a pending payment request. Please wait for admin review.")
            return ConversationHandler.END

        context.user_data.pop("upi_amount", None)
        rate = float(await get_setting("coin_rate_inr", "5"))
        coins = int(amount * rate)

        await db.execute(
            "INSERT INTO payments (user_id, coins, screenshot_file_id, status, timestamp, payment_method, amount_inr) "
            "VALUES (?, ?, ?, 'pending', ?, 'upi', ?)",
            (user.id, coins, file_id, utcnow().isoformat(), amount),
        )
        await db.commit()
        cur = await db.execute("SELECT last_insert_rowid()")
        payment_id = (await cur.fetchone())[0]

    await update.message.reply_text("✅ Your payment request has been submitted. You'll be notified once reviewed.")

    uname = f"@{user.username}" if user.username else "—"
    caption = (
        "💰 <b>New UPI Payment Request</b>\n\n"
        f"👤 Username: {html.escape(uname)}\n"
        f"🆔 User ID: <code>{user.id}</code>\n"
        f"💰 Amount: <b>₹{amount}</b>\n"
        f"🪙 Coins: <b>{coins}</b>\n"
        f"📅 Time: {fmt_date(utcnow().isoformat())}"
    )
    kb = InlineKeyboardMarkup([
        [_kb_btn("✅ Accept", callback_data=f"pay:accept:{payment_id}", style="success"),
         _kb_btn("❌ Reject", callback_data=f"pay:reject:{payment_id}", style="danger")]
    ])
    for admin_id in [OWNER_ID]:
        try:
            await context.bot.send_photo(
                admin_id, file_id, caption=caption,
                parse_mode=ParseMode.HTML, reply_markup=kb
            )
        except TelegramError:
            pass
    return ConversationHandler.END


async def cb_buyupi_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("❌ Cancelled.")
    context.user_data.pop("upi_amount", None)
    return ConversationHandler.END


async def get_all_admin_ids() -> list[int]:
    ids = {OWNER_ID}
    async with db_conn() as db:
        cur = await db.execute("SELECT user_id FROM admins")
        rows = await cur.fetchall()
        for r in rows:
            ids.add(r[0])
    return list(ids)


async def get_admin_role(user_id: int) -> str | None:
    if user_id == OWNER_ID:
        return "owner"
    async with db_conn() as db:
        cur = await db.execute("SELECT role FROM admins WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row else None


async def log_admin_action(bot, actor_id: int, action_text: str) -> None:
    async with db_conn() as db:
        await db.execute(
            "INSERT INTO admin_logs (actor_id, action_text, timestamp) VALUES (?, ?, ?)",
            (actor_id, action_text, utcnow().isoformat()),
        )
        await db.commit()

    if actor_id == OWNER_ID:
        return
    role = await get_admin_role(actor_id)
    actor_row = await get_user_row(actor_id)
    actor_label = f"@{actor_row['username']}" if actor_row and actor_row["username"] else str(actor_id)
    role_tag = f" [{role}]" if role else ""
    text = f"📋 <b>Admin Action</b>\n\n👤 By: {html.escape(actor_label)}{role_tag} (<code>{actor_id}</code>)\n{action_text}"

    recipients = {OWNER_ID}
    if role == "junior":
        async with db_conn() as db:
            cur = await db.execute("SELECT user_id FROM admins WHERE role='senior'")
            for r in await cur.fetchall():
                recipients.add(r[0])

    for uid in recipients:
        try:
            await bot.send_message(uid, text, parse_mode=ParseMode.HTML)
        except TelegramError:
            pass


async def cb_payment_accept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    admin = update.effective_user
    if not await require_owner(update):
        return
    payment_id = int(query.data.split(":")[2])
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM payments WHERE payment_id=?", (payment_id,))
        payment = await cur.fetchone()
        if not payment or payment["status"] != "pending":
            await query.answer("⚠️ Already processed.", show_alert=True)
            return
        await db.execute(
            "UPDATE payments SET status='accepted', admin_id=? WHERE payment_id=?",
            (admin.id, payment_id),
        )
        await db.commit()

    method_note = f"({payment['stars']} stars)" if payment["payment_method"] != "upi" else f"(₹{payment['amount_inr']})"
    await add_coins(payment["user_id"], payment["coins"], "payment", f"Payment accepted {method_note}")
    await query.answer("✅ Accepted")
    try:
        await query.message.delete()
    except (BadRequest, TelegramError):
        pass
    try:
        await context.bot.send_message(
            payment["user_id"],
            f"✅ <b>Payment Accepted!</b>\n🪙 {payment['coins']} Coins have been added to your wallet.",
            parse_mode=ParseMode.HTML,
        )
    except TelegramError:
        pass
    await log_admin_action(context.bot, admin.id, f"✅ Accepted payment #{payment_id} for user {payment['user_id']} ({payment['coins']} coins)")


async def cb_payment_reject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_owner(update):
        return
    payment_id = int(query.data.split(":")[2])
    context.user_data["reject_payment_id"] = payment_id
    context.user_data["reject_chat_msg"] = (query.message.chat_id, query.message.message_id)
    await query.answer()
    await query.message.reply_text("✏️ Enter rejection reason (or send - to skip):")
    context.user_data["awaiting_reject_reason"] = True


async def handle_reject_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.user_data.get("awaiting_reject_reason"):
        return
    context.user_data["awaiting_reject_reason"] = False
    reason = update.message.text.strip()
    reason = "" if reason == "-" else reason
    payment_id = context.user_data.pop("reject_payment_id", None)
    reject_chat_msg = context.user_data.pop("reject_chat_msg", None)
    if payment_id is None:
        await update.message.reply_text("❌ Session expired.")
        return

    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM payments WHERE payment_id=?", (payment_id,))
        payment = await cur.fetchone()
        if not payment or payment["status"] != "pending":
            await update.message.reply_text("⚠️ Already processed.")
            return
        await db.execute(
            "UPDATE payments SET status='rejected', admin_id=?, reason=? WHERE payment_id=?",
            (update.effective_user.id, reason, payment_id),
        )
        await db.commit()

    await update.message.reply_text("❌ Payment rejected and user notified.")
    if reject_chat_msg:
        try:
            await context.bot.delete_message(chat_id=reject_chat_msg[0], message_id=reject_chat_msg[1])
        except TelegramError:
            pass
    try:
        msg = "❌ <b>Payment Rejected</b>"
        if reason:
            msg += f"\nReason: {html.escape(reason)}"
        await context.bot.send_message(payment["user_id"], msg, parse_mode=ParseMode.HTML)
    except TelegramError:
        pass
    await log_admin_action(
        context.bot, update.effective_user.id,
        f"❌ Rejected payment #{payment_id} for user {payment['user_id']}" + (f"\nReason: {html.escape(reason)}" if reason else "")
    )


# ---------------------------------------------------------------------------
# DAILY BONUS, SPIN, MYSTERY BOX, INVITE, STATS
# ---------------------------------------------------------------------------
async def handle_daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard_user(update, context):
        return
    user = update.effective_user
    lock = await get_user_action_lock(user.id)
    async with lock:
        row = await get_user_row(user.id)
        now_ist = india_now()
        if row and row["last_bonus_time"]:
            # Bonus resets at midnight IST, not 24 hours after the last tap.
            last = datetime.fromisoformat(row["last_bonus_time"])
            last_ist = last.replace(tzinfo=timezone.utc).astimezone(
                timezone(timedelta(hours=5, minutes=30))
            )
            if last_ist.date() == now_ist.date():
                next_reset = (now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
                              + timedelta(days=1))
                remaining = next_reset - now_ist
                total_minutes = max(0, int(remaining.total_seconds() // 60))
                h, m = divmod(total_minutes, 60)
                await update.effective_message.reply_text(
                    "⏳ <b>Daily Bonus Already Claimed</b>\n"
                    f"Come back in <b>{h}h {m:02d}m</b> (resets at 12:00 AM IST).",
                    parse_mode=ParseMode.HTML,
                )
                return

        premium = await is_premium_active(user.id)
        if premium:
            reward = int(await get_setting("premium_daily_bonus", "40"))
            tx_label = "Premium daily bonus claim"
        else:
            reward = int(await get_setting("daily_bonus", "25"))
            tx_label = "Daily bonus claim"
        await add_coins(user.id, reward, "daily_bonus", tx_label)
        async with db_conn() as db:
            await db.execute(
                "UPDATE users SET last_bonus_time=? WHERE user_id=?",
                (utcnow().isoformat(), user.id),
            )
            await db.commit()
    badge = "\n👑 <i>Premium Daily Bonus</i>" if premium else ""
    await update.effective_message.reply_text(
        f"💰 <b>Daily Bonus Claimed!</b>\n🪙 You received <b>{reward} Coins</b>.{badge}",
        parse_mode=ParseMode.HTML,
    )


async def _spins_left(user_id: int) -> int:
    row = await get_user_row(user_id)
    today = india_now().strftime("%Y-%m-%d")
    used = row["spin_count_today"] if row and row["spin_reset_date"] == today else 0
    limit = 2 if await is_premium_active(user_id) else 1
    return max(0, limit - used)


async def handle_daily_spin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard_user(update, context):
        return
    user = update.effective_user
    left = await _spins_left(user.id)
    limit = 2 if await is_premium_active(user.id) else 1
    cfg = await get_json_setting("spin_settings", json.loads(DEFAULT_SETTINGS["spin_settings"]), dict)
    text = (
        "🎰 <b>Daily Spin</b>\n"
        f"{DIVIDER}\n"
        f"🎁 Coins (small): <b>{cfg.get('chance_coins_low',50)}%</b>\n"
        f"💎 Coins (big): <b>{cfg.get('chance_coins_high',30)}%</b>\n"
        f"📁 Random File: <b>{cfg.get('chance_file',18)}%</b>\n"
        f"👑 Premium: <b>{cfg.get('chance_premium',2)}%</b>\n"
        f"{DIVIDER}\n"
        f"🔄 Spins left today: <b>{left}/{limit}</b>"
    )
    if left <= 0:
        kb = None
        text += "\n\n⏳ Come back tomorrow for more spins!"
    else:
        kb = InlineKeyboardMarkup([[_kb_btn("🎰 SPIN NOW", callback_data="spin:go", style="success")]])
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def cb_spin_go(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    lock = await get_user_action_lock(user.id)

    async with lock:
        left = await _spins_left(user.id)
        if left <= 0:
            await query.answer("⏳ No spins left today — come back tomorrow!", show_alert=True)
            return
        await query.answer()

        today = india_now().strftime("%Y-%m-%d")
        row = await get_user_row(user.id)
        used_today = row["spin_count_today"] if row and row["spin_reset_date"] == today else 0
        async with db_conn() as db:
            await db.execute(
                "UPDATE users SET spin_count_today=?, spin_reset_date=? WHERE user_id=?",
                (used_today + 1, today, user.id),
            )
            await db.commit()

        symbols = ["🍒", "🍋", "🍇", "🍉", "🍊", "⭐", "💎", "7️⃣"]

        def render_reels(reel, locked, caption):
            row_ = "│".join(f"  {s}  " for s in reel)
            marks = "".join(("🔒" if locked[i] else "  ") for i in range(3))
            return (
                f"🎰 <b>DAILY SPIN</b> 🎰\n{DIVIDER}\n\n"
                f"   ┌─────┬─────┬─────┐\n"
                f"   │{row_}│\n"
                f"   └─────┴─────┴─────┘\n"
                f"     {marks}\n\n"
                f"<i>{caption}</i>"
            )

        try:
            await query.edit_message_text(
                f"🎰 <b>DAILY SPIN</b> 🎰\n{DIVIDER}\n\n"
                f"   ┌─────┬─────┬─────┐\n"
                f"   │  ❓  │  ❓  │  ❓  │\n"
                f"   └─────┴─────┴─────┘\n\n"
                f"<i>🎲 Pulling the lever...</i>",
                parse_mode=ParseMode.HTML,
            )
        except (BadRequest, TelegramError):
            pass
        await asyncio.sleep(0.5)

        frame_count = 16
        reel = [random.choice(symbols) for _ in range(3)]
        locked = [False, False, False]

        for i in range(frame_count):
            progress = i / frame_count
            if progress > 0.55:
                locked[0] = True
            if progress > 0.75:
                locked[1] = True
            if progress > 0.92:
                locked[2] = True
            for j in range(3):
                if not locked[j]:
                    reel[j] = random.choice(symbols)

            if progress < 0.55:
                caption = "🌪 Spinning" + "." * (1 + i % 3)
            elif progress < 0.85:
                caption = "⏳ Almost there..."
            else:
                caption = "🔥 Revealing..."

            try:
                await query.edit_message_text(render_reels(reel, locked, caption), parse_mode=ParseMode.HTML)
            except (BadRequest, TelegramError):
                pass
            await asyncio.sleep(0.18 + (progress ** 2) * 0.4)

        await asyncio.sleep(0.3)

        cfg = await get_json_setting("spin_settings", json.loads(DEFAULT_SETTINGS["spin_settings"]), dict)
        def _safe_int(key: str, default: int, minimum: int = 0) -> int:
            try:
                return max(minimum, int(cfg.get(key, default)))
            except (TypeError, ValueError, OverflowError):
                return default

        c_low = _safe_int("chance_coins_low", 50)
        c_high = _safe_int("chance_coins_high", 30)
        c_file = _safe_int("chance_file", 18)
        c_prem = _safe_int("chance_premium", 2)

        total = c_low + c_high + c_file + c_prem
        if total <= 0:
            c_low, c_high, c_file, c_prem = 50, 30, 18, 2
            total = 100

        roll = random.uniform(0, total)
        if roll < c_low:
            win_symbol, category = "🍒", "coins_low"
        elif roll < c_low + c_high:
            win_symbol, category = "7️⃣", "coins_high"
        elif roll < c_low + c_high + c_file:
            win_symbol, category = "⭐", "file"
        else:
            win_symbol, category = "💎", "premium"

        try:
            await query.edit_message_text(
                render_reels([win_symbol] * 3, [True, True, True], "🎉 <b>JACKPOT LOCKED IN!</b> 🎉"),
                parse_mode=ParseMode.HTML,
            )
        except (BadRequest, TelegramError):
            pass
        await asyncio.sleep(0.6)

        if category == "coins_low":
            low_min = _safe_int("coins_low_min", 20)
            low_max = max(low_min, _safe_int("coins_low_max", 50, low_min))
            amount = random.randint(low_min, low_max)
            await add_coins(user.id, amount, "daily_spin", f"Daily spin win: {amount} coins")
            result = f"🪙 <b>You won {amount} Coins!</b>"
        elif category == "coins_high":
            high_min = _safe_int("coins_high_min", 67)
            high_max = max(high_min, _safe_int("coins_high_max", 120, high_min))
            amount = random.randint(high_min, high_max)
            await add_coins(user.id, amount, "daily_spin", f"Daily spin win: {amount} coins")
            result = f"💎 <b>Jackpot! You won {amount} Coins!</b>"
        elif category == "file":
            async with db_conn() as db:
                db.row_factory = aiosqlite.Row
                cur = await db.execute(
                    "SELECT * FROM files WHERE is_deleted=0 AND price>0 ORDER BY RANDOM() LIMIT 1"
                )
                f = await cur.fetchone()
                if not f:
                    cur = await db.execute("SELECT * FROM files WHERE is_deleted=0 ORDER BY RANDOM() LIMIT 1")
                    f = await cur.fetchone()
            if f:
                async with db_conn() as db:
                    await db.execute(
                        "INSERT INTO purchases (user_id, file_pk, price, timestamp) VALUES (?, ?, 0, ?)",
                        (user.id, f["file_pk"], utcnow().isoformat()),
                    )
                    await db.commit()
                result = f"📁 <b>You won a file!</b>\n{html.escape(f['file_name'])}"
            else:
                low_min = _safe_int("coins_low_min", 20)
                low_max = max(low_min, _safe_int("coins_low_max", 50, low_min))
                amount = random.randint(low_min, low_max)
                await add_coins(user.id, amount, "daily_spin", "Daily spin fallback (no files available)")
                result = f"🪙 <b>You won {amount} Coins!</b> (no files were available)"
        else:
            days = _safe_int("premium_days", 1, 1)
            await grant_premium(user.id, days, admin_id=0)
            result = f"👑 <b>You won {days} Days of Premium!</b>"

        luck = random.randint(1, 100)
        final_text = (
            f"🎊 <b>SPIN RESULT</b> 🎊\n{DIVIDER}\n\n"
            f"   ┌─────┬─────┬─────┐\n"
            f"   │  {win_symbol}  │  {win_symbol}  │  {win_symbol}  │\n"
            f"   └─────┴─────┴─────┘\n\n"
            f"{result}\n\n"
            f"🍀 Your Luck: <b>{luck}%</b>\n{DIVIDER}"
        )
        try:
            await query.edit_message_text(final_text, parse_mode=ParseMode.HTML)
        except (BadRequest, TelegramError):
            await query.message.reply_text(final_text, parse_mode=ParseMode.HTML)


async def handle_mystery_box(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard_user(update, context):
        return
    pricing = await get_json_setting("mystery_box_pricing", json.loads(DEFAULT_SETTINGS["mystery_box_pricing"]), list)
    balance = await get_balance(update.effective_user.id)
    lines = [f"📦 <b>Mystery Box</b>\n{DIVIDER}", f"🪙 Your balance: <b>{balance}</b>\n"]
    buttons = []
    for p in pricing:
        lines.append(f"{p['label']} — 🪙 {p['price']}")
        buttons.append([_kb_btn(
            f"{p['label']} ({p['price']} coins)", callback_data=f"mystery:open:{p['tier']}:{p['price']}", style="success"
        )])
    await update.effective_message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cb_mystery_open(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    _, _, tier, price = query.data.split(":")
    price = int(price)
    lock = await get_user_action_lock(user.id)

    async with lock:
        ok = await remove_coins(user.id, price, "mystery_box", f"Opened {tier} mystery box")
        if not ok:
            await query.answer("❌ Not enough coins.", show_alert=True)
            return

        async with db_conn() as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM files WHERE is_deleted=0 AND mystery_tier=? ORDER BY RANDOM() LIMIT 1", (tier,)
            )
            f = await cur.fetchone()

        if not f:
            await add_coins(user.id, price, "mystery_box_refund", f"No files available in {tier} tier — refunded")
            await query.answer("😢 No files available in this box right now — refunded.", show_alert=True)
            return

        async with db_conn() as db:
            await db.execute(
                "INSERT INTO purchases (user_id, file_pk, price, timestamp) VALUES (?, ?, ?, ?)",
                (user.id, f["file_pk"], price, utcnow().isoformat()),
            )
            await db.commit()

    await query.answer("🎉 You won a file!")
    icon = FILE_TYPE_ICON.get(f["file_kind"], "📄")
    await query.edit_message_text(
        f"🎉 <b>Mystery Box Opened!</b>\n\n{icon} <b>{html.escape(f['file_name'])}</b>\n📦 {fmt_size(f['file_size'])}",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[_kb_btn("⬇️ Download Now", callback_data=f"file:dl:{f['file_pk']}", style="success")]]),
    )


async def handle_invite_friends(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard_user(update, context):
        return
    user = update.effective_user
    reward = await get_setting("referral_reward", "20")
    async with db_conn() as db:
        cur = await db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user.id,))
        count = (await cur.fetchone())[0]
    link = f"https://t.me/{BOT_USERNAME}?start={user.id}"
    text = (
        "🚀 <b>Invite Friends</b>\n\n"
        f"Earn <b>{reward} Coins</b> for every friend who joins using your link!\n\n"
        f"🔗 <code>{link}</code>\n\n"
        f"👥 Total Referrals: <b>{count}</b>"
    )
    await update.effective_message.reply_text(
        text, parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[_kb_btn("👥 My Referrals", callback_data="myrefs:0", style="primary")]]),
    )


async def cb_my_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":")[1])
    per_page = 10
    user = update.effective_user
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT new_user_id, date, reward FROM referrals WHERE referrer_id=? ORDER BY date DESC LIMIT ? OFFSET ?",
            (user.id, per_page, page * per_page),
        )
        rows = await cur.fetchall()

    if not rows and page == 0:
        text = "👥 <b>My Referrals</b>\n\nYou haven't referred anyone yet."
    else:
        lines = ["👥 <b>My Referrals</b>\n"]
        for r in rows:
            u = await get_user_row(r["new_user_id"])
            label = f"@{u['username']}" if u and u["username"] else (u["first_name"] if u else f"User {r['new_user_id']}")
            lines.append(f"• {html.escape(label or '—')} — 🪙 +{r['reward']} <i>({fmt_date(r['date'])})</i>")
        text = "\n".join(lines)

    nav = []
    if page > 0:
        nav.append(_kb_btn("⬅️ Prev", callback_data=f"myrefs:{page-1}", style="primary"))
    if len(rows) == per_page:
        nav.append(_kb_btn("Next ➡️", callback_data=f"myrefs:{page+1}", style="primary"))
    kb = InlineKeyboardMarkup([nav]) if nav else None
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def handle_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard_user(update, context):
        return
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT referrer_id, COUNT(*) as cnt FROM referrals GROUP BY referrer_id "
            "ORDER BY cnt DESC LIMIT 10"
        )
        rows = await cur.fetchall()

    if not rows:
        await update.effective_message.reply_text("🏆 <b>Leaderboard</b>\n\nNo referrals yet.", parse_mode=ParseMode.HTML)
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>Top 10 Referrals</b>\n"]
    for i, r in enumerate(rows):
        u = await get_user_row(r["referrer_id"])
        name = html.escape(u["first_name"] or "Unknown") if u else "Unknown"
        rank = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{rank} {name} — <b>{r['cnt']}</b> referrals")
    await update.effective_message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def handle_redeem_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard_user(update, context):
        return
    kb = InlineKeyboardMarkup([
        [_kb_btn("🔑 Redeem a Code", callback_data="redeem:enter", style="primary")],
        [_kb_btn("🎁 Convert Coins to Gift Code", callback_data="redeem:gift", style="primary")],
    ])
    await update.effective_message.reply_text(
        "🎟️ <b>Redeem Center</b>\n\nWhat would you like to do?",
        parse_mode=ParseMode.HTML,
        reply_markup=kb,
    )


async def cb_redeem_enter_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "🎟️ Please enter your redeem code:",
        reply_markup=InlineKeyboardMarkup([[_kb_btn("❌ Cancel", callback_data="redeem:cancel", style="danger")]]),
    )
    return RD_CODE


async def cb_redeem_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


async def handle_redeem_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    code = update.message.text.strip().upper()
    user = update.effective_user
    lock = await get_user_action_lock(user.id)

    admin = await is_admin(user.id)
    async with lock:
        async with db_conn() as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM redeems WHERE code=?", (code,))
            redeem = await cur.fetchone()

            if not redeem:
                await update.message.reply_text("❌ Invalid Redeem Code.", reply_markup=user_reply_keyboard(admin))
                return ConversationHandler.END

            if redeem["status"] != "active":
                await update.message.reply_text("❌ This code is no longer active.", reply_markup=user_reply_keyboard(admin))
                return ConversationHandler.END

            if redeem["expiry_date"]:
                try:
                    if datetime.fromisoformat(redeem["expiry_date"]) < utcnow():
                        await db.execute("UPDATE redeems SET status='expired' WHERE code=?", (code,))
                        await db.commit()
                        await update.message.reply_text("❌ This code has expired.", reply_markup=user_reply_keyboard(admin))
                        return ConversationHandler.END
                except ValueError:
                    pass

            if redeem["usage_limit"] and redeem["used_count"] >= redeem["usage_limit"]:
                await update.message.reply_text("❌ This code has reached its usage limit.", reply_markup=user_reply_keyboard(admin))
                return ConversationHandler.END

            cur = await db.execute(
                "SELECT 1 FROM redeem_uses WHERE code=? AND user_id=?", (code, user.id)
            )
            if await cur.fetchone():
                await update.message.reply_text("❌ You have already redeemed this code.", reply_markup=user_reply_keyboard(admin))
                return ConversationHandler.END

            await db.execute(
                "INSERT INTO redeem_uses (code, user_id, timestamp) VALUES (?, ?, ?)",
                (code, user.id, utcnow().isoformat()),
            )
            await db.execute("UPDATE redeems SET used_count = used_count + 1 WHERE code=?", (code,))
            await db.commit()

        if redeem["coin_reward"]:
            await add_coins(user.id, redeem["coin_reward"], "redeem", f"Redeem code {code}")
        if redeem["premium_days"]:
            await grant_premium(user.id, redeem["premium_days"], admin_id=0)

    msg = f"✅ <b>Redeem Successful!</b>\n🪙 +{redeem['coin_reward']} Coins"
    if redeem["premium_days"]:
        msg += f"\n⭐ +{redeem['premium_days']} Days Premium"
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=user_reply_keyboard(admin))
    return ConversationHandler.END


def _generate_gift_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "GIFT" + "".join(secrets.choice(alphabet) for _ in range(8))


async def cb_redeem_gift_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    balance = await get_balance(update.effective_user.id)
    await query.message.reply_text(
        f"🎁 <b>Convert Coins to Gift Code</b>\n\n"
        f"🪙 Your balance: <b>{balance}</b>\n\n"
        "Enter how many coins to convert into a one-time gift code:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[_kb_btn("❌ Cancel", callback_data="redeem:cancel", style="danger")]]),
    )
    return GC_AMOUNT


async def conv_gift_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("❌ Please enter a valid positive number of coins.")
        return GC_AMOUNT
    amount = int(text)
    user = update.effective_user
    lock = await get_user_action_lock(user.id)

    async with lock:
        ok = await remove_coins(user.id, amount, "gift_code_created", f"Converted {amount} coins to a gift code")
        if not ok:
            await update.message.reply_text("❌ You don't have enough coins for that.")
            return ConversationHandler.END

        code = _generate_gift_code()
        async with db_conn() as db:
            for _ in range(5):
                cur = await db.execute("SELECT 1 FROM redeems WHERE code=?", (code,))
                if not await cur.fetchone():
                    break
                code = _generate_gift_code()
            await db.execute(
                "INSERT INTO redeems (code, coin_reward, premium_days, usage_limit, status, created_by, created_at, source) "
                "VALUES (?, ?, 0, 1, 'active', ?, ?, 'user')",
                (code, amount, user.id, utcnow().isoformat()),
            )
            await db.commit()

    await update.message.reply_text(
        f"✅ <b>Gift Code Created!</b>\n\n🎟 Code: <code>{code}</code>\n🪙 Value: <b>{amount} Coins</b>\n\n"
        "Share this code with anyone — they can redeem it once via 🎟️ Redeem Code → Redeem a Code.",
        parse_mode=ParseMode.HTML,
    )
    return ConversationHandler.END


async def handle_my_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard_user(update, context):
        return
    user = update.effective_user
    row = await get_user_row(user.id)
    balance = await get_balance(user.id)
    async with db_conn() as db:
        cur = await db.execute("SELECT COUNT(*) FROM purchases WHERE user_id=?", (user.id,))
        purchased = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (user.id,))
        refs = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM redeem_uses WHERE user_id=?", (user.id,))
        redeems = (await cur.fetchone())[0]

    is_premium = await is_premium_active(user.id)
    premium_line = "👑 <b>Premium — Active</b>" if is_premium else "⭐ Premium: <i>Not Active</i>"
    text = (
        "📊 <b>My Stats</b>\n"
        f"{DIVIDER}\n"
        f"👤 <b>User ID:</b> <code>{user.id}</code>\n"
        f"📅 <b>Join Date:</b> {fmt_date(row['join_date']) if row else '—'}\n"
        f"🪙 <b>Coins:</b> {balance}\n"
        f"📁 <b>Purchased Files:</b> {purchased}\n"
        f"👥 <b>Referrals:</b> {refs}\n"
        f"🎟 <b>Redeem Count:</b> {redeems}\n"
        f"{premium_line}\n"
        f"{DIVIDER}"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


# ---------------------------------------------------------------------------
# FILE STORE
# ---------------------------------------------------------------------------
async def handle_buy_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard_user(update, context):
        return
    await send_file_list(update, context, page=0)


async def send_file_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int, edit: bool = False) -> None:
    per_page = 8
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT file_pk, file_name, price FROM files WHERE is_deleted=0 "
            "ORDER BY file_pk DESC LIMIT ? OFFSET ?",
            (per_page, page * per_page),
        )
        rows = await cur.fetchall()

    if not rows:
        text = "📁 <b>Buy Files</b>\n\nNo files available right now."
        kb = InlineKeyboardMarkup([[_kb_btn("📁 My Purchases", callback_data="purchases:0", style="primary")]])
    else:
        text = "📁 <b>Buy Files</b>\n\nSelect a file to view details:"
        buttons = []
        for r in rows:
            tag = "FREE" if r["price"] == 0 else f"🪙 {r['price']}"
            buttons.append([_kb_btn(f"📄 {r['file_name']} — {tag}", callback_data=f"file:view:{r['file_pk']}", style="primary")])
        nav = []
        if page > 0:
            nav.append(_kb_btn("⬅️ Prev", callback_data=f"files:list:{page-1}", style="primary"))
        if len(rows) == per_page:
            nav.append(_kb_btn("Next ➡️", callback_data=f"files:list:{page+1}", style="primary"))
        if nav:
            buttons.append(nav)
        buttons.append([_kb_btn("📁 My Purchases", callback_data="purchases:0", style="primary")])
        kb = InlineKeyboardMarkup(buttons)

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def cb_files_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    try:
        page = max(0, int((query.data or "files:list:0").split(":")[2]))
    except (IndexError, ValueError):
        page = 0
    await send_file_list(update, context, page, edit=True)


async def cb_file_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    file_pk = int(query.data.split(":")[2])
    user = update.effective_user

    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM files WHERE file_pk=? AND is_deleted=0", (file_pk,))
        f = await cur.fetchone()
        if not f:
            await query.answer("❌ File not found.", show_alert=True)
            return
        cur = await db.execute(
            "SELECT 1 FROM purchases WHERE user_id=? AND file_pk=?", (user.id, file_pk)
        )
        owned = bool(await cur.fetchone())

    await query.answer()
    icon = FILE_TYPE_ICON.get(f["file_kind"], "📄")
    text = (
        f"{icon} <b>{html.escape(f['file_name'])}</b>\n\n"
        f"📦 Size: <b>{fmt_size(f['file_size'])}</b>\n"
        f"📄 Description: {html.escape(f['description']) if f['description'] else '—'}\n"
    )
    if f["price"] == 0 or owned:
        text += "\n<b>FREE</b>" if f["price"] == 0 and not owned else "\n✅ <b>You own this file</b>"
        buttons = [[_kb_btn("⬇️ Download", callback_data=f"file:dl:{file_pk}", style="success")]]
    else:
        text += f"\n🪙 <b>{f['price']} Coins</b>"
        buttons = [[_kb_btn("🛒 Buy Now", callback_data=f"file:buy:{file_pk}", style="success")]]
    buttons.append([_kb_btn("⬅️ Back", callback_data="files:list:0", style="primary")])
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))


async def cb_file_buy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    file_pk = int(query.data.split(":")[2])
    user = update.effective_user
    lock = await get_user_action_lock(user.id)
    async with lock:
        async with db_conn() as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM files WHERE file_pk=? AND is_deleted=0", (file_pk,))
            f = await cur.fetchone()
            if not f:
                await query.answer("❌ File not found.", show_alert=True)
                return
            cur = await db.execute("SELECT 1 FROM purchases WHERE user_id=? AND file_pk=?", (user.id, file_pk))
            if await cur.fetchone():
                await query.answer("✅ You already own this file.", show_alert=True)
                return

        if f["price"] > 0:
            ok = await remove_coins(user.id, f["price"], "purchase", f"Purchased file: {f['file_name']}")
            if not ok:
                await query.answer("❌ Not enough Coins.", show_alert=True)
                await query.edit_message_text(
                    "❌ <b>Not enough Coins.</b>\n\nPlease top up your wallet to continue.",
                    parse_mode=ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([[_kb_btn("💰 Open Wallet", callback_data="wallet:home", style="primary")]]),
                )
                return

        async with db_conn() as db:
            await db.execute(
                "INSERT INTO purchases (user_id, file_pk, price, timestamp) VALUES (?, ?, ?, ?)",
                (user.id, file_pk, f["price"], utcnow().isoformat()),
            )
            await db.commit()

    await query.answer("✅ Purchased!")
    await query.edit_message_text(
        f"✅ <b>Purchase Successful!</b>\n\nYou now own <b>{html.escape(f['file_name'])}</b> forever.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[_kb_btn("⬇️ Download Now", callback_data=f"file:dl:{file_pk}", style="success")]]),
    )


async def cb_file_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    file_pk = int(query.data.split(":")[2])
    user = update.effective_user

    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM files WHERE file_pk=? AND is_deleted=0", (file_pk,))
        f = await cur.fetchone()
        if not f:
            await query.answer("❌ File not found.", show_alert=True)
            return
        if f["price"] > 0:
            cur = await db.execute("SELECT 1 FROM purchases WHERE user_id=? AND file_pk=?", (user.id, file_pk))
            if not await cur.fetchone():
                await query.answer("❌ You need to purchase this file first.", show_alert=True)
                return

    await query.answer("⬇️ Sending file...")
    try:
        await context.bot.send_document(
            chat_id=user.id, document=f["tg_file_id"], caption=f"📄 {html.escape(f['file_name'])}", parse_mode=ParseMode.HTML
        )
    except (BadRequest, TelegramError):
        try:
            await context.bot.send_message(user.id, "⚠️ Could not deliver file, please contact support.")
        except TelegramError:
            pass
        return

    async with db_conn() as db:
        await db.execute(
            "INSERT INTO downloads (user_id, file_pk, timestamp) VALUES (?, ?, ?)",
            (user.id, file_pk, utcnow().isoformat()),
        )
        await db.execute("UPDATE files SET downloads_count = downloads_count + 1 WHERE file_pk=?", (file_pk,))
        await db.commit()


async def cb_my_purchases(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":")[1])
    per_page = 8
    user = update.effective_user
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT p.*, f.file_name FROM purchases p JOIN files f ON p.file_pk=f.file_pk "
            "WHERE p.user_id=? ORDER BY p.id DESC LIMIT ? OFFSET ?",
            (user.id, per_page, page * per_page),
        )
        rows = await cur.fetchall()

    if not rows:
        text = "📁 <b>My Purchases</b>\n\nYou haven't purchased any files yet."
        kb = InlineKeyboardMarkup([[_kb_btn("⬅️ Back", callback_data="files:list:0", style="primary")]])
    else:
        text = "📁 <b>My Purchases</b>\n\n"
        buttons = []
        for r in rows:
            buttons.append([_kb_btn(f"⬇️ {r['file_name']}", callback_data=f"file:dl:{r['file_pk']}", style="success")])
        buttons.append([_kb_btn("⬅️ Back", callback_data="files:list:0", style="primary")])
        kb = InlineKeyboardMarkup(buttons)

    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


# ---------------------------------------------------------------------------
# ADMIN UPLOAD
# ---------------------------------------------------------------------------
async def cb_admin_upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await is_admin(update.effective_user.id):
        if update.callback_query:
            await update.callback_query.answer(ADMIN_ONLY_MSG, show_alert=True)
        else:
            await update.effective_message.reply_text(ADMIN_ONLY_MSG)
        return ConversationHandler.END
    if update.callback_query:
        await update.callback_query.answer()
    await update.effective_message.reply_text(
        "📤 <b>Upload File</b>\n\nSend me the file you want to add to the store.",
        parse_mode=ParseMode.HTML,
    )
    return UP_FILE


async def conv_upload_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    kind = None
    tg_file = None
    file_name = None
    file_size = 0

    if msg.document:
        kind, tg_file = "document", msg.document
        file_name, file_size = tg_file.file_name or "file", tg_file.file_size or 0
    elif msg.video:
        kind, tg_file = "video", msg.video
        file_name = tg_file.file_name or f"video_{tg_file.file_unique_id}.mp4"
        file_size = tg_file.file_size or 0
    elif msg.audio:
        kind, tg_file = "audio", msg.audio
        file_name = tg_file.file_name or f"audio_{tg_file.file_unique_id}.mp3"
        file_size = tg_file.file_size or 0
    elif msg.photo:
        tg_file = msg.photo[-1]
        kind = "photo"
        file_name = f"photo_{tg_file.file_unique_id}.jpg"
        file_size = tg_file.file_size or 0
    elif msg.voice:
        kind, tg_file = "voice", msg.voice
        file_name = f"voice_{tg_file.file_unique_id}.ogg"
        file_size = tg_file.file_size or 0
    elif msg.animation:
        kind, tg_file = "animation", msg.animation
        file_name = tg_file.file_name or f"gif_{tg_file.file_unique_id}.mp4"
        file_size = tg_file.file_size or 0
    else:
        await msg.reply_text("❌ Unsupported file type. Please send a valid file.")
        return UP_FILE

    context.user_data["up_kind"] = kind
    context.user_data["up_file_id"] = tg_file.file_id
    context.user_data["up_unique_id"] = tg_file.file_unique_id
    context.user_data["up_orig_name"] = file_name
    context.user_data["up_size"] = file_size

    await msg.reply_text(
        f"✅ File received ({fmt_size(file_size)}).\n\n📝 Enter File Name (or send - to use original filename):"
    )
    return UP_NAME


async def conv_upload_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    name = context.user_data.get("up_orig_name", "file") if text == "-" else text
    context.user_data["up_name"] = name
    await update.message.reply_text("📄 Enter Description (or send - to skip):")
    return UP_DESC


async def conv_upload_desc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    context.user_data["up_desc"] = "" if text == "-" else text
    await update.message.reply_text("💰 Enter Coin Price (0 = FREE):\n\nExample: 0, 50, 100, 250, 500, 1000")
    return UP_PRICE


async def conv_upload_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ Please enter a valid number.")
        return UP_PRICE
    context.user_data["up_price"] = int(text)
    return await show_upload_preview(update, context)


async def show_upload_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    d = context.user_data
    text = (
        "👀 <b>Preview</b>\n\n"
        f"📄 File Name: {html.escape(d.get('up_name',''))}\n"
        f"📦 File Size: {fmt_size(d.get('up_size',0))}\n"
        f"📄 Description: {html.escape(d.get('up_desc','')) if d.get('up_desc') else '—'}\n"
        f"💰 Coin Price: {d.get('up_price',0)}\n"
        f"📅 Upload Date: {fmt_date(utcnow().isoformat())}"
    )
    kb = InlineKeyboardMarkup([
        [_kb_btn("✅ Publish", callback_data="up:publish", style="success"),
         _kb_btn("✏️ Edit", callback_data="up:edit", style="primary")],
        [_kb_btn("❌ Cancel", callback_data="up:cancel", style="danger")],
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    return UP_PREVIEW


async def cb_upload_publish(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    d = context.user_data
    user = update.effective_user
    async with db_conn() as db:
        await db.execute(
            "INSERT INTO files (tg_file_id, tg_file_unique_id, file_kind, file_name, file_size, "
            "description, price, upload_date, uploaded_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (d["up_file_id"], d["up_unique_id"], d["up_kind"], d["up_name"], d["up_size"],
             d["up_desc"], d["up_price"], utcnow().isoformat(), user.id),
        )
        await db.commit()
    await query.edit_message_text("✅ <b>File Published Successfully!</b>", parse_mode=ParseMode.HTML)
    for key in ["up_kind", "up_file_id", "up_unique_id", "up_orig_name", "up_size", "up_name", "up_desc", "up_price"]:
        context.user_data.pop(key, None)
    return ConversationHandler.END


async def cb_upload_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("📝 Enter File Name (or send - to use original filename):")
    return UP_NAME


async def cb_upload_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    for key in ["up_kind", "up_file_id", "up_unique_id", "up_orig_name", "up_size", "up_name", "up_desc", "up_price"]:
        context.user_data.pop(key, None)
    try:
        await query.edit_message_text("❌ Upload cancelled.")
    except BadRequest:
        await query.message.reply_text("❌ Upload cancelled.")
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# MANAGE FILES
# ---------------------------------------------------------------------------
async def cb_admin_managefiles(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_admin(update.effective_user.id):
        if update.callback_query:
            await update.callback_query.answer(ADMIN_ONLY_MSG, show_alert=True)
        else:
            await update.effective_message.reply_text(ADMIN_ONLY_MSG)
        return
    if update.callback_query:
        await update.callback_query.answer()
    await send_manage_files_list(update, context, page=0)


async def send_manage_files_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int) -> None:
    viewer_id = update.effective_user.id
    is_owner = viewer_id == OWNER_ID
    per_page = 8
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        if is_owner:
            cur = await db.execute(
                "SELECT file_pk, file_name, price, downloads_count FROM files WHERE is_deleted=0 "
                "ORDER BY file_pk DESC LIMIT ? OFFSET ?",
                (per_page, page * per_page),
            )
        else:
            cur = await db.execute(
                "SELECT file_pk, file_name, price, downloads_count FROM files WHERE is_deleted=0 AND uploaded_by=? "
                "ORDER BY file_pk DESC LIMIT ? OFFSET ?",
                (viewer_id, per_page, page * per_page),
            )
        rows = await cur.fetchall()

    text = "📂 <b>Manage Files</b>\n\n"
    text += "Select a file to edit or delete:" if is_owner else "Files you've uploaded — select one to edit or delete:"
    buttons = []
    for r in rows:
        buttons.append([_kb_btn(
            f"📄 {r['file_name']} ({r['downloads_count']}⬇️)",
            callback_data=f"mf:view:{r['file_pk']}:{page}", style="primary",
        )])
    nav = []
    if page > 0:
        nav.append(_kb_btn("⬅️ Prev", callback_data=f"mf:list:{page-1}", style="primary"))
    if len(rows) == per_page:
        nav.append(_kb_btn("Next ➡️", callback_data=f"mf:list:{page+1}", style="primary"))
    if nav:
        buttons.append(nav)
    buttons.append([_kb_btn("🔍 Search Files", callback_data="mf:searchstart", style="primary")])
    buttons.append([_kb_btn("⬅️ Back to Admin Panel", callback_data="ad:home", style="primary")])

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))


async def cb_mf_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":")[2])
    await send_manage_files_list(update, context, page)


async def cb_mf_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("🔍 Enter a keyword to search your files by name:")
    return MF_SEARCH


async def conv_mf_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyword = update.message.text.strip()
    viewer_id = update.effective_user.id
    is_owner = viewer_id == OWNER_ID
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        if is_owner:
            cur = await db.execute(
                "SELECT file_pk, file_name FROM files WHERE is_deleted=0 AND file_name LIKE ? LIMIT 15",
                (f"%{keyword}%",),
            )
        else:
            cur = await db.execute(
                "SELECT file_pk, file_name FROM files WHERE is_deleted=0 AND uploaded_by=? AND file_name LIKE ? LIMIT 15",
                (viewer_id, f"%{keyword}%"),
            )
        rows = await cur.fetchall()

    if not rows:
        await update.message.reply_text("❌ No files matched that keyword.")
        return ConversationHandler.END

    buttons = [[_kb_btn(f"📄 {r['file_name']}", callback_data=f"mf:view:{r['file_pk']}:0", style="primary")] for r in rows]
    await update.message.reply_text(
        f"🔍 Found <b>{len(rows)}</b> matching file(s):", parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return ConversationHandler.END


async def cb_mf_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, _, file_pk, page = query.data.split(":")
    await _render_mf_view(update, int(file_pk), int(page))


async def _render_mf_view(update: Update, file_pk: int, page: int) -> None:
    query = update.callback_query
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM files WHERE file_pk=?", (file_pk,))
        f = await cur.fetchone()
    if not f:
        await query.edit_message_text("❌ File not found.")
        return
    if update.effective_user.id != OWNER_ID and f["uploaded_by"] != update.effective_user.id:
        await query.edit_message_text("🚫 You can only manage files you uploaded.")
        return
    text = (
        f"📄 <b>{html.escape(f['file_name'])}</b>\n\n"
        f"📦 Size: {fmt_size(f['file_size'])}\n"
        f"📄 Description: {html.escape(f['description']) if f['description'] else '—'}\n"
        f"💰 Price: {f['price']} coins\n"
        f"⬇️ Downloads: {f['downloads_count']}\n"
        f"🎁 Mystery Tier: {f['mystery_tier'] or 'None'}\n"
        f"📌 Featured: {'Yes' if f['featured'] else 'No'}\n"
        f"📅 Uploaded: {fmt_date(f['upload_date'])}"
    )
    feature_label = "📌 Unfeature" if f["featured"] else "📌 Make Featured"
    kb = InlineKeyboardMarkup([
        [_kb_btn("✏️ Edit Name", callback_data=f"mf:ename:{file_pk}", style="primary"),
         _kb_btn("✏️ Edit Desc", callback_data=f"mf:edesc:{file_pk}", style="primary")],
        [_kb_btn("✏️ Edit Price", callback_data=f"mf:eprice:{file_pk}", style="primary"),
         _kb_btn("🎁 Set Mystery Tier", callback_data=f"mf:etier:{file_pk}", style="primary")],
        [_kb_btn(feature_label, callback_data=f"mf:tfeat:{file_pk}:{page}", style="primary")],
        [_kb_btn("🗑 Delete File", callback_data=f"mf:delete:{file_pk}", style="danger")],
        [_kb_btn("⬅️ Back", callback_data=f"mf:list:{page}", style="primary")],
    ])
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def cb_mf_toggle_featured(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    _, _, file_pk, page = query.data.split(":")
    file_pk = int(file_pk)
    if not await _can_manage_file(update.effective_user.id, file_pk):
        await query.answer("🚫 You can only manage files you uploaded.", show_alert=True)
        return
    async with db_conn() as db:
        cur = await db.execute("SELECT featured FROM files WHERE file_pk=?", (file_pk,))
        row = await cur.fetchone()
        new_val = 0 if (row and row[0]) else 1
        await db.execute("UPDATE files SET featured=? WHERE file_pk=?", (new_val, file_pk))
        await db.commit()
    await query.answer("📌 Featured!" if new_val else "Unfeatured")
    await _render_mf_view(update, file_pk, int(page))


async def _can_manage_file(user_id: int, file_pk: int) -> bool:
    if user_id == OWNER_ID:
        return True
    async with db_conn() as db:
        cur = await db.execute("SELECT uploaded_by FROM files WHERE file_pk=?", (file_pk,))
        row = await cur.fetchone()
        return bool(row and row[0] == user_id)


async def cb_mf_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    _, field, file_pk = query.data.split(":")
    file_pk = int(file_pk)
    if not await _can_manage_file(update.effective_user.id, file_pk):
        await query.answer("🚫 You can only manage files you uploaded.", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    context.user_data["ef_file_pk"] = file_pk
    context.user_data["ef_field"] = field
    prompts = {
        "ename": "📝 Enter new File Name:",
        "edesc": "📄 Enter new Description:",
        "eprice": "💰 Enter new Coin Price:",
        "etier": "🎁 Enter Mystery Tier — <code>random</code>, <code>rare</code>, <code>premium</code>, or <code>none</code>:",
    }
    await query.message.reply_text(
        prompts[field], parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[_kb_btn("❌ Cancel", callback_data="mf:editcancel", style="danger")]]),
    )
    return EF_FIELD


async def cb_mf_edit_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    context.user_data.pop("ef_field", None)
    context.user_data.pop("ef_file_pk", None)
    await update.callback_query.message.reply_text("❌ Edit cancelled.")
    return ConversationHandler.END


async def conv_edit_field_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    field = context.user_data.pop("ef_field", None)
    file_pk = context.user_data.pop("ef_file_pk", None)
    if field is None or file_pk is None:
        await update.message.reply_text("❌ Session expired.")
        return ConversationHandler.END
    value = update.message.text.strip()

    column_map = {"ename": "file_name", "edesc": "description", "eprice": "price", "etier": "mystery_tier"}
    column = column_map[field]

    if field == "eprice":
        if not value.isdigit():
            await update.message.reply_text("❌ Please enter a valid number.")
            context.user_data["ef_field"] = field
            context.user_data["ef_file_pk"] = file_pk
            return EF_FIELD
        value = int(value)
    elif field == "etier":
        value = value.lower()
        if value not in ("random", "rare", "premium", "none"):
            await update.message.reply_text("❌ Must be one of: random, rare, premium, none.")
            context.user_data["ef_field"] = field
            context.user_data["ef_file_pk"] = file_pk
            return EF_FIELD
        value = None if value == "none" else value

    async with db_conn() as db:
        await db.execute(f"UPDATE files SET {column}=? WHERE file_pk=?", (value, file_pk))
        await db.commit()

    await update.message.reply_text("✅ File updated successfully.")
    return ConversationHandler.END


async def cb_mf_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    file_pk = int(query.data.split(":")[2])
    if not await _can_manage_file(update.effective_user.id, file_pk):
        await query.answer("🚫 You can only manage files you uploaded.", show_alert=True)
        return
    await query.answer()
    kb = InlineKeyboardMarkup([
        [_kb_btn("✅ Yes, Delete", callback_data=f"mf:delconfirm:{file_pk}", style="success"),
         _kb_btn("❌ No", callback_data=f"mf:view:{file_pk}:0", style="danger")],
    ])
    await query.edit_message_text("⚠️ Are you sure you want to delete this file?", reply_markup=kb)


async def cb_mf_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    file_pk = int(query.data.split(":")[2])
    if not await _can_manage_file(update.effective_user.id, file_pk):
        await query.answer("🚫 You can only manage files you uploaded.", show_alert=True)
        return
    async with db_conn() as db:
        await db.execute("UPDATE files SET is_deleted=1 WHERE file_pk=?", (file_pk,))
        await db.commit()
    await query.answer("🗑 Deleted")
    await query.edit_message_text("🗑 <b>File deleted successfully.</b>", parse_mode=ParseMode.HTML)


# ---------------------------------------------------------------------------
# FORCE CHANNELS
# ---------------------------------------------------------------------------
async def cb_admin_fcmgr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_owner(update):
        return
    kb = InlineKeyboardMarkup([
        [_kb_btn("➕ Add Channel", callback_data="fc:add", style="success"),
         _kb_btn("➖ Remove Channel", callback_data="fc:remove", style="danger")],
        [_kb_btn("📋 Channel List", callback_data="fc:list", style="primary")],
        [_kb_btn("⬅️ Back", callback_data="ad:home", style="primary")],
    ])
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("📢 <b>Force Channel Manager</b>", parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.effective_message.reply_text("📢 <b>Force Channel Manager</b>", parse_mode=ParseMode.HTML, reply_markup=kb)


async def cb_fc_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await require_owner(update):
        return ConversationHandler.END
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "➕ <b>Add Force-Join Channel/Group</b>\n\n"
        "You can add both <b>public</b> and <b>private</b> channels/groups.\n\n"
        "Send one of:\n"
        "• A public <b>@username</b>\n"
        "• A <b>https://t.me/username</b> link\n"
        "• A <b>https://t.me/+invite_hash</b> invite link (private)\n"
        "• A numeric <b>chat ID</b> (e.g. <code>-1001234567890</code>)\n\n"
        "<b>Important:</b>\n"
        "• I must already be a <b>member</b> of the chat.\n"
        "• For private chats, I need to be an <b>admin</b> so I can verify membership and generate invite links.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[_kb_btn("❌ Cancel", callback_data="fc:cancel", style="danger")]]),
    )
    return FC_ADD


async def cb_fc_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    context.user_data.pop("fc_pending_invite", None)
    await update.callback_query.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


async def conv_fc_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    try:
        text = (msg.text or "").strip()
        username = None
        invite_link = None
        chat = None

        if text.startswith("@") and re.match(r"^@[A-Za-z0-9_]{5,32}$", text):
            username = text
            try:
                chat = await context.bot.get_chat(username)
            except TelegramError as e:
                await msg.reply_text(f"❌ Couldn't find that channel/group: {html.escape(str(e))}")
                return FC_ADD
        else:
            m_pub = re.match(r"^https?://t\.me/([A-Za-z0-9_]{5,32})/?$", text)
            m_priv = re.match(r"^https?://t\.me/\+([A-Za-z0-9_-]+)/?$", text)
            if m_pub:
                username = f"@{m_pub.group(1)}"
                try:
                    chat = await context.bot.get_chat(username)
                except TelegramError as e:
                    await msg.reply_text(f"❌ Couldn't find that channel/group: {html.escape(str(e))}")
                    return FC_ADD
            elif m_priv:
                invite_link = text
                await msg.reply_text(
                    "🔒 This looks like a <b>private invite link</b>.\n\n"
                    "Telegram doesn't let bots resolve private invite links directly. "
                    "Please forward any message from that private chat to me, "
                    "OR send the numeric chat ID (e.g. <code>-1001234567890</code>).\n\n"
                    "<i>I'll remember this invite link and use it once you send the chat ID.</i>",
                    parse_mode=ParseMode.HTML,
                )
                context.user_data["fc_pending_invite"] = invite_link
                return FC_ADD
            elif re.match(r"^-?\d+$", text):
                try:
                    chat = await context.bot.get_chat(int(text))
                except TelegramError as e:
                    await msg.reply_text(f"❌ Couldn't resolve chat ID: {html.escape(str(e))}")
                    return FC_ADD
            else:
                await msg.reply_text(
                    "❌ Please send a valid @username, a https://t.me/username link, "
                    "a https://t.me/+invite link, or a numeric chat ID."
                )
                return FC_ADD

        if chat is None:
            await msg.reply_text("❌ Could not resolve the chat. Please try again.")
            return FC_ADD

        try:
            me = await context.bot.get_me()
            member = await context.bot.get_chat_member(chat.id, me.id)
            if member.status in ("left", "kicked"):
                await msg.reply_text(
                    "❌ I'm not currently a member of that chat. "
                    "Please add me first (as admin for private chats), then try again."
                )
                return FC_ADD
            if member.status not in ("administrator", "creator"):
                await msg.reply_text(
                    "⚠️ I'm a member but <b>not an admin</b> of that chat.\n\n"
                    "For <b>public</b> chats that's fine — I can still verify members.\n"
                    "For <b>private</b> chats, I <b>must be an admin</b> to verify membership and generate invite links.",
                    parse_mode=ParseMode.HTML,
                )
        except TelegramError as e:
            await msg.reply_text(f"❌ Couldn't verify my membership: {html.escape(str(e))}")
            return FC_ADD

        info = await _detect_chat_join_type(context.bot, chat.id)
        join_by_request = 1 if info["join_by_request"] else 0
        is_private = 1 if info["is_private"] else 0

        resolved_username = f"@{chat.username}" if chat.username else None
        if not resolved_username:
            pending_invite = context.user_data.pop("fc_pending_invite", None)
            resolved_link = await _ensure_invite_link(context.bot, chat.id, pending_invite or invite_link)
            if not resolved_link:
                await msg.reply_text(
                    "❌ <b>Cannot create an invite link for this private channel.</b>\n\n"
                    "Please promote me to admin with the <b>Invite Users</b> permission "
                    "(<code>can_invite_users</code>), then try again.\n\n"
                    "I will <u>not</u> save this channel until a valid link exists.",
                    parse_mode=ParseMode.HTML,
                )
                return ConversationHandler.END
            invite_link = resolved_link
            unique_key = f"id:{chat.id}"
        else:
            unique_key = resolved_username
            invite_link = f"https://t.me/{chat.username.lstrip('@')}"

        if info["is_private"] and not info["bot_can_verify"]:
            await msg.reply_text(
                "⚠️ <b>Warning:</b> This is a <b>private</b> channel and I'm not an admin there.\n"
                "I <b>cannot verify membership</b> for private channels unless I'm an admin.\n\n"
                "Please promote me to admin with <b>can_restrict_members</b> permission, "
                "otherwise users will be stuck at the verify screen.",
                parse_mode=ParseMode.HTML,
            )

        await _save_force_channel(
            unique_key=unique_key,
            chat_id=chat.id,
            username=resolved_username,
            title=chat.title,
            chat_type=_safe_chat_type(chat),
            invite_link=invite_link,
            join_by_request=join_by_request,
            is_private=is_private,
        )

        detection_note = ""
        if join_by_request:
            detection_note = "\n🔍 <b>Detected:</b> Join Request Approval is <b>ON</b> for this channel."
        elif is_private:
            detection_note = "\n🔍 <b>Detected:</b> Private channel with normal joining."

        await msg.reply_text(
            f"✅ Added: <b>{html.escape(chat.title)}</b>\n"
            f"Type: <code>{html.escape(_safe_chat_type(chat))}</code>"
            f"{detection_note}",
            parse_mode=ParseMode.HTML,
        )
        return ConversationHandler.END

    except Exception as e:
        log.exception("Unexpected error in conv_fc_add")
        await msg.reply_text(
            f"⚠️ <b>Something went wrong adding this channel.</b>\n<code>{html.escape(str(e))}</code>",
            parse_mode=ParseMode.HTML,
        )
        return ConversationHandler.END


async def _save_force_channel(
    unique_key: str,
    chat_id: int,
    username: str | None,
    title: str,
    chat_type: str,
    invite_link: str | None = None,
    join_by_request: int = 0,
    is_private: int = 0,
) -> None:
    async with db_conn() as db:
        await db.execute(
            "INSERT INTO force_channels "
            "(username, chat_id, title, chat_type, invite_link, added_date, join_by_request, is_private) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(username) DO UPDATE SET "
            "chat_id=excluded.chat_id, title=excluded.title, chat_type=excluded.chat_type, "
            "invite_link=excluded.invite_link, join_by_request=excluded.join_by_request, "
            "is_private=excluded.is_private",
            (
                unique_key, chat_id, title, chat_type, invite_link,
                utcnow().isoformat(), join_by_request, is_private,
            ),
        )
        await db.commit()


async def cb_fc_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_owner(update):
        return
    await query.answer()
    channels = await list_force_channels()
    if not channels:
        text = "📋 <b>Channel List</b>\n\nNo channels added yet."
    else:
        lines = ["📋 <b>Channel List</b>\n"]
        for ch in channels:
            kind = ch["chat_type"] or "unknown"
            markers = []
            try:
                if ch["join_by_request"]:
                    markers.append("🔒 Approval-based")
            except (KeyError, IndexError):
                pass
            try:
                if ch["is_private"]:
                    markers.append("🔐 Private")
            except (KeyError, IndexError):
                pass
            marker_str = f" — {', '.join(markers)}" if markers else ""
            lines.append(
                f"• <b>{html.escape(ch['title'])}</b> — <code>{kind}</code>{marker_str}\n"
                f"  ID: <code>{ch['chat_id']}</code> | added {fmt_date(ch['added_date'])}"
            )
        text = "\n".join(lines)
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=back_button("ad:fcmgr"))


async def cb_fc_remove_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_owner(update):
        return
    await query.answer()
    channels = await list_force_channels()
    if not channels:
        await query.edit_message_text("No channels to remove.", reply_markup=back_button("ad:fcmgr"))
        return
    buttons = [[_kb_btn(f"➖ {ch['title']}", callback_data=f"fc:rm:{ch['id']}", style="danger")] for ch in channels]
    buttons.append([_kb_btn("⬅️ Back", callback_data="ad:fcmgr", style="primary")])
    await query.edit_message_text("➖ Select a channel to remove:", reply_markup=InlineKeyboardMarkup(buttons))


async def cb_fc_remove_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_owner(update):
        return
    query = update.callback_query
    ch_id = int(query.data.split(":")[2])
    async with db_conn() as db:
        await db.execute("DELETE FROM force_channels WHERE id=?", (ch_id,))
        await db.commit()
    await query.answer("➖ Removed")
    await cb_fc_remove_menu(update, context)


# ---------------------------------------------------------------------------
# WALLET MANAGER
# ---------------------------------------------------------------------------
async def cb_admin_walletmgr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_admin(update.effective_user.id):
        if update.callback_query:
            await update.callback_query.answer(ADMIN_ONLY_MSG, show_alert=True)
        else:
            await update.effective_message.reply_text(ADMIN_ONLY_MSG)
        return
    is_owner = update.effective_user.id == OWNER_ID
    rows = [
        [_kb_btn("➕ Add Coins", callback_data="wm:add", style="success"),
         _kb_btn("➖ Remove Coins", callback_data="wm:remove", style="danger")],
        [_kb_btn("🔄 Reset Coins", callback_data="wm:reset", style="danger")],
    ]
    if is_owner:
        rows.append([_kb_btn("🎯 Set Exact Balance", callback_data="wm:setbal", style="primary")])
        rows.append([_kb_btn("👥 Bulk Manage Users", callback_data="wm:bulk", style="primary")])
        rows.append([_kb_btn("📋 Pending Payments", callback_data="pp:list:0", style="primary")])
    rows.append([_kb_btn("📜 Wallet History", callback_data="wm:history", style="primary")])
    rows.append([_kb_btn("⬅️ Back", callback_data="ad:home", style="primary")])
    kb = InlineKeyboardMarkup(rows)
    text = "💰 <b>Wallet Manager</b>\n\nEnter a User ID to manage their wallet, or view recent history."
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def cb_wm_action_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    action = query.data.split(":")[1]
    if action == "setbal" and not await require_owner(update):
        return ConversationHandler.END
    await query.answer()
    context.user_data["wm_action"] = action
    await query.message.reply_text(
        "👤 Enter the target User ID:",
        reply_markup=InlineKeyboardMarkup([[_kb_btn("❌ Cancel", callback_data="wm:cancel", style="danger")]]),
    )
    return UM_SEARCH


async def cb_wm_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    context.user_data.pop("wm_action", None)
    context.user_data.pop("wm_target", None)
    await update.callback_query.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


async def conv_wm_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ Please send a valid numeric User ID.")
        return UM_SEARCH
    target_id = int(text)
    row = await get_user_row(target_id)
    if not row:
        await update.message.reply_text("❌ User not found.")
        context.user_data.pop("wm_action", None)
        return ConversationHandler.END
    context.user_data["wm_target"] = target_id
    action = context.user_data.get("wm_action")
    if action == "reset":
        async with db_conn() as db:
            await db.execute("UPDATE wallet SET coins=0 WHERE user_id=?", (target_id,))
            await db.execute(
                "INSERT INTO transactions (user_id, tx_type, amount, description, timestamp) VALUES (?, ?, ?, ?, ?)",
                (target_id, "admin_reset", 0, "Admin reset wallet to 0", utcnow().isoformat()),
            )
            await db.commit()
        await update.message.reply_text(f"🔄 Wallet reset to 0 for user {target_id}.")
        await log_admin_action(context.bot, update.effective_user.id, f"🔄 Reset wallet to 0 for user {target_id}")
        return ConversationHandler.END

    if action == "setbal":
        await update.message.reply_text("🎯 Enter the exact balance to set:")
        return UM_AMOUNT

    await update.message.reply_text("🪙 Enter the amount:")
    return UM_AMOUNT


async def conv_wm_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    action = context.user_data.get("wm_action")
    min_ok = 0 if action == "setbal" else 1
    if not text.isdigit() or int(text) < min_ok:
        await update.message.reply_text(
            "❌ Please enter a valid number." if action == "setbal"
            else "❌ Please enter a valid positive number."
        )
        return UM_AMOUNT
    amount = int(text)
    target_id = context.user_data.pop("wm_target", None)
    action = context.user_data.pop("wm_action", None)
    if target_id is None or action is None:
        await update.message.reply_text("❌ Session expired.")
        return ConversationHandler.END

    if action == "setbal":
        async with db_conn() as db:
            await db.execute(
                "INSERT INTO wallet (user_id, coins) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET coins=excluded.coins",
                (target_id, amount),
            )
            await db.execute(
                "INSERT INTO transactions (user_id, tx_type, amount, description, timestamp) VALUES (?, ?, ?, ?, ?)",
                (target_id, "admin_setbal", amount, f"Admin set exact balance to {amount}", utcnow().isoformat()),
            )
            await db.commit()
        await update.message.reply_text(f"🎯 Balance for user {target_id} set to {amount} coins.")
        await log_admin_action(context.bot, update.effective_user.id, f"🎯 Set exact balance for user {target_id} to {amount} coins")
        return ConversationHandler.END

    if action == "add":
        new_bal = await add_coins(target_id, amount, "admin_gift", f"Admin added {amount} coins")
        await update.message.reply_text(f"✅ Added {amount} coins. New balance: {new_bal}")
        await log_admin_action(context.bot, update.effective_user.id, f"➕ Added {amount} coins to user {target_id}")
        try:
            await context.bot.send_message(target_id, f"🎁 <b>{amount} Coins</b> have been added to your wallet by admin!", parse_mode=ParseMode.HTML)
        except TelegramError:
            pass
    else:
        ok = await remove_coins(target_id, amount, "admin_deduct", f"Admin removed {amount} coins")
        if ok:
            await update.message.reply_text(f"✅ Removed {amount} coins.")
            await log_admin_action(context.bot, update.effective_user.id, f"➖ Removed {amount} coins from user {target_id}")
        else:
            await update.message.reply_text("❌ User doesn't have enough coins to remove that amount.")
    return ConversationHandler.END


async def cb_wm_bulk_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await require_owner(update):
        return ConversationHandler.END
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "👥 <b>Bulk Manage Users</b>\n\n"
        "Send the target users separated by space, comma, or newline — "
        "numeric User IDs, @usernames, or a mix:\n"
        "<code>111 222 @alice @bob</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[_kb_btn("❌ Cancel", callback_data="wb:cancel", style="danger")]]),
    )
    return WB_IDS


async def conv_wm_bulk_ids(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    tokens = [tok for tok in re.split(r"[\s,]+", raw) if tok]
    if not tokens:
        await update.message.reply_text("❌ Please send at least one User ID or @username.")
        return WB_IDS

    resolved: list[int] = []
    not_found: list[str] = []

    async with db_conn() as db:
        for tok in tokens:
            if tok.startswith("@"):
                uname = tok.lstrip("@")
                cur = await db.execute("SELECT user_id FROM users WHERE username=?", (uname,))
                row = await cur.fetchone()
                if row:
                    resolved.append(row[0])
                else:
                    not_found.append(tok)
            elif tok.isdigit():
                resolved.append(int(tok))
            else:
                not_found.append(tok)

    if not resolved:
        await update.message.reply_text(
            "❌ None of those could be resolved to a real user. Check the IDs/usernames and try again."
        )
        return WB_IDS

    context.user_data["wb_ids"] = resolved
    msg = f"✅ Resolved <b>{len(resolved)}</b> users.\n\nWhat should be applied to all of them?"
    if not_found:
        msg += f"\n\n⚠️ Not found (skipped): {', '.join(not_found[:15])}"
        if len(not_found) > 15:
            msg += f" (+{len(not_found) - 15} more)"
    kb = InlineKeyboardMarkup([
        [_kb_btn("➕ Add Coins", callback_data="wb:add", style="success"),
         _kb_btn("➖ Remove Coins", callback_data="wb:remove", style="danger")],
        [_kb_btn("🚫 Ban All", callback_data="wb:ban", style="danger"),
         _kb_btn("✅ Unban All", callback_data="wb:unban", style="success")],
        [_kb_btn("👑 Give Premium", callback_data="wb:premium", style="primary")],
        [_kb_btn("❌ Cancel", callback_data="wb:cancel", style="danger")],
    ])
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=kb)
    return WB_ACTION


async def cb_wb_action_coins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["wb_coin_action"] = "add" if query.data == "wb:add" else "remove"
    verb = "add to" if query.data == "wb:add" else "remove from"
    ids = context.user_data.get("wb_ids", [])
    await query.message.reply_text(f"🪙 Enter the coin amount to {verb} all {len(ids)} users:")
    return WB_AMOUNT


async def conv_wm_bulk_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("❌ Please enter a valid positive number.")
        return WB_AMOUNT
    amount = int(text)
    target_ids = context.user_data.pop("wb_ids", [])
    action = context.user_data.pop("wb_coin_action", None)
    is_add = action == "add"

    verb = "Adding" if is_add else "Removing"
    status_msg = await update.message.reply_text(f"⏳ {verb} {amount} coins for {len(target_ids)} users...")
    ok_list: list[int] = []
    skipped: list[int] = []

    async def process_one(uid: int) -> None:
        row = await get_user_row(uid)
        if not row:
            skipped.append(uid)
            return
        if is_add:
            await add_coins(uid, amount, "admin_gift", f"Bulk admin gift: {amount} coins")
            success = True
        else:
            success = await remove_coins(uid, amount, "admin_deduct", f"Bulk admin deduct: {amount} coins")
        if not success:
            skipped.append(uid)
            return
        ok_list.append(uid)
        await TELEGRAM_SEND_LIMITER.acquire()
        try:
            verb_msg = f"🎁 <b>{amount} Coins</b> have been added to your wallet by admin!" if is_add \
                else f"⚠️ <b>{amount} Coins</b> have been deducted from your wallet by admin."
            await context.bot.send_message(uid, verb_msg, parse_mode=ParseMode.HTML)
        except TelegramError:
            pass

    await asyncio.gather(*(process_one(uid) for uid in target_ids))

    past_verb = "Added" if is_add else "Removed"
    result = f"✅ <b>Bulk {past_verb} Complete</b>\n\n🪙 {past_verb} {amount} coins for <b>{len(ok_list)}</b> users."
    if skipped:
        result += f"\n⚠️ Skipped (not found or insufficient balance): {', '.join(str(u) for u in skipped[:20])}"
        if len(skipped) > 20:
            result += f" (+{len(skipped) - 20} more)"
    await status_msg.edit_text(result, parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def cb_wb_action_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    target_ids = context.user_data.pop("wb_ids", [])
    banned = 1 if query.data == "wb:ban" else 0
    async with db_conn() as db:
        for uid in target_ids:
            await db.execute("UPDATE users SET is_banned=? WHERE user_id=?", (banned, uid))
        await db.commit()
    action_word = "Banned" if banned else "Unbanned"
    await query.message.reply_text(f"✅ <b>{action_word}</b> {len(target_ids)} users.", parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def cb_wb_action_premium_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    kb = InlineKeyboardMarkup([
        [_kb_btn("7 Days", callback_data="wb:pset:7", style="primary"),
         _kb_btn("30 Days", callback_data="wb:pset:30", style="primary")],
        [_kb_btn("90 Days", callback_data="wb:pset:90", style="primary"),
         _kb_btn("Lifetime", callback_data="wb:pset:0", style="primary")],
    ])
    await query.message.reply_text("👑 Select Premium duration to grant to all selected users:", reply_markup=kb)
    return WB_PREMIUM


async def cb_wb_action_premium_set(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    days = int(query.data.split(":")[2])
    target_ids = context.user_data.pop("wb_ids", [])
    for uid in target_ids:
        await grant_premium(uid, None if days == 0 else days, update.effective_user.id)
        await TELEGRAM_SEND_LIMITER.acquire()
        try:
            label = "Lifetime" if days == 0 else f"{days} days"
            await context.bot.send_message(
                uid, f"👑 <b>You've been granted Premium!</b>\nDuration: {label}", parse_mode=ParseMode.HTML
            )
        except TelegramError:
            pass
    label = "Lifetime" if days == 0 else f"{days} Days"
    await query.message.reply_text(f"✅ Granted <b>{label}</b> Premium to {len(target_ids)} users.", parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def cb_wb_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.pop("wb_ids", None)
    context.user_data.pop("wb_coin_action", None)
    await query.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


async def cb_pending_payments_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_owner(update):
        return
    await query.answer()
    page = int(query.data.split(":")[2])
    per_page = 10
    async with db_conn() as db:
        total = (await (await db.execute("SELECT COUNT(*) FROM payments WHERE status='pending'")).fetchone())[0]
        cur = await db.execute(
            "SELECT * FROM payments WHERE status='pending' ORDER BY payment_id ASC LIMIT ? OFFSET ?",
            (per_page, page * per_page),
        )
        rows = await cur.fetchall()

    if not rows and page == 0:
        text = "📋 <b>Pending Payments</b>\n\nNothing pending right now — all caught up! ✅"
        buttons = [[_kb_btn("⬅️ Back", callback_data="ad:walletmgr", style="primary")]]
    else:
        text = f"📋 <b>Pending Payments</b>  —  Total: <b>{total}</b>\n\nTap Accept/Reject on any request below:\n"
        buttons = []
        for r in rows:
            urow = await get_user_row(r["user_id"])
            uname = f"@{urow['username']}" if urow and urow["username"] else (urow["first_name"] if urow else f"ID {r['user_id']}")
            text += f"\n👤 <b>{html.escape(uname or str(r['user_id']))}</b> — ⭐{r['stars']} → 🪙{r['coins']} <i>({fmt_date(r['timestamp'])})</i>"
            buttons.append([
                _kb_btn(f"✅ Accept #{r['payment_id']}", callback_data=f"pay:accept:{r['payment_id']}", style="success"),
                _kb_btn(f"❌ Reject #{r['payment_id']}", callback_data=f"pay:reject:{r['payment_id']}", style="danger"),
            ])
        nav = []
        if page > 0:
            nav.append(_kb_btn("⬅️ Prev", callback_data=f"pp:list:{page-1}", style="primary"))
        if (page + 1) * per_page < total:
            nav.append(_kb_btn("Next ➡️", callback_data=f"pp:list:{page+1}", style="primary"))
        if nav:
            buttons.append(nav)
        buttons.append([_kb_btn("⬅️ Back", callback_data="ad:walletmgr", style="primary")])

    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))


async def cb_wm_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM transactions ORDER BY tx_id DESC LIMIT 15")
        rows = await cur.fetchall()
    if not rows:
        text = "📜 No transactions yet."
    else:
        lines = ["📜 <b>Recent Wallet History</b>\n"]
        for r in rows:
            lines.append(f"👤 <code>{r['user_id']}</code> {'+' if r['amount']>=0 else ''}{r['amount']} — {html.escape(r['tx_type'])}")
        text = "\n".join(lines)
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=back_button("ad:walletmgr"))


# ---------------------------------------------------------------------------
# REDEEM MANAGER
# ---------------------------------------------------------------------------
async def cb_admin_redeemmgr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_admin(update.effective_user.id):
        if update.callback_query:
            await update.callback_query.answer(ADMIN_ONLY_MSG, show_alert=True)
        else:
            await update.effective_message.reply_text(ADMIN_ONLY_MSG)
        return
    is_owner = update.effective_user.id == OWNER_ID
    rows = [
        [_kb_btn("➕ Create Code", callback_data="rm:create", style="success")],
        [_kb_btn("📋 List Codes", callback_data="rm:list", style="primary")],
        [_kb_btn("🗑 Delete Code", callback_data="rm:delstart", style="danger")],
    ]
    if is_owner:
        rows.append([_kb_btn("🗑 Delete ALL Codes", callback_data="rm:delall", style="danger")])
    rows.append([_kb_btn("⬅️ Back", callback_data="ad:home", style="primary")])
    kb = InlineKeyboardMarkup(rows)
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("🎟 <b>Redeem Manager</b>", parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.effective_message.reply_text("🎟 <b>Redeem Manager</b>", parse_mode=ParseMode.HTML, reply_markup=kb)


async def cb_rm_create_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        async with db_conn() as db:
            cur = await db.execute(
                "SELECT COUNT(*) FROM redeems WHERE created_by=? AND created_at >= ?",
                (user_id, today_start),
            )
            count_today = (await cur.fetchone())[0]
        if count_today >= ADMIN_DAILY_REDEEM_LIMIT:
            await query.answer(
                f"🚫 Daily limit reached — admins can create up to {ADMIN_DAILY_REDEEM_LIMIT} redeem codes per day.",
                show_alert=True,
            )
            return ConversationHandler.END
    await query.answer()
    await query.message.reply_text(
        "🎟 Enter the redeem code (e.g. WELCOME500):",
        reply_markup=InlineKeyboardMarkup([[_kb_btn("❌ Cancel", callback_data="rm:cancel", style="danger")]]),
    )
    return RM_CODE


async def cb_rm_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    for k in ["rm_code", "rm_coins", "rm_premium", "rm_limit"]:
        context.user_data.pop(k, None)
    await update.callback_query.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


async def conv_rm_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    code = update.message.text.strip().upper()
    if not re.match(r"^[A-Z0-9_\-]{3,32}$", code):
        await update.message.reply_text("❌ Invalid code format. Use letters/numbers only (3-32 chars).")
        return RM_CODE
    async with db_conn() as db:
        cur = await db.execute("SELECT 1 FROM redeems WHERE code=?", (code,))
        if await cur.fetchone():
            await update.message.reply_text("❌ This code already exists. Try another.")
            return RM_CODE
    context.user_data["rm_code"] = code
    await update.message.reply_text("💰 Enter Coin Reward (e.g. 500):")
    return RM_COINS


async def conv_rm_coins(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ Please enter a valid number.")
        return RM_COINS
    if len(text) > 10 or int(text) > 2_147_483_647:
        await update.message.reply_text("❌ Coin reward is too large. Enter a valid 32-bit integer.")
        return RM_COINS
    amount = int(text)
    if update.effective_user.id != OWNER_ID:
        if amount > ADMIN_MAX_REDEEM_COINS or amount < ADMIN_MIN_REDEEM_COINS:
            await update.message.reply_text(
                f"🚫 Admins can only create codes worth between {ADMIN_MIN_REDEEM_COINS}–{ADMIN_MAX_REDEEM_COINS} coins."
            )
            return RM_COINS
    context.user_data["rm_coins"] = amount
    await update.message.reply_text("⭐ Enter Premium Reward in days (0 for none):")
    return RM_PREMIUM


async def conv_rm_premium(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ Please enter a valid number.")
        return RM_PREMIUM
    if len(text) > 6 or int(text) > 36500:
        await update.message.reply_text("❌ Premium duration must be between 0 and 36,500 days.")
        return RM_PREMIUM
    context.user_data["rm_premium"] = int(text)
    await update.message.reply_text("🔢 Enter Usage Limit (0 for unlimited):")
    return RM_LIMIT


async def conv_rm_limit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text("❌ Please enter a valid positive number (or 0 for unlimited).")
        return RM_LIMIT
    limit = int(text)
    if limit < 0 or limit > 2_147_483_647:
        await update.message.reply_text("❌ Limit is too large. Enter a number from 0 to 2,147,483,647.")
        return RM_LIMIT
    context.user_data["rm_limit"] = limit
    await update.message.reply_text("📅 Enter Expiry Date (DD-MM-YYYY) or send - for no expiry:")
    return RM_EXPIRY


async def conv_rm_expiry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    expiry_iso = None
    if text != "-":
        try:
            expiry_iso = datetime.strptime(text, "%d-%m-%Y").isoformat()
        except ValueError:
            await update.message.reply_text("❌ Invalid date format. Use DD-MM-YYYY or send -.")
            return RM_EXPIRY

    d = context.user_data
    async with db_conn() as db:
        await db.execute(
            "INSERT INTO redeems (code, coin_reward, premium_days, usage_limit, expiry_date, status, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'active', ?, ?)",
            (d["rm_code"], d["rm_coins"], d["rm_premium"], d["rm_limit"], expiry_iso,
             update.effective_user.id, utcnow().isoformat()),
        )
        await db.commit()

    await update.message.reply_text(
        f"✅ <b>Redeem Code Created!</b>\n\n🎟 Code: <code>{d['rm_code']}</code>\n💰 Coins: {d['rm_coins']}\n"
        f"⭐ Premium Days: {d['rm_premium']}\n🔢 Usage Limit: {d['rm_limit'] or 'Unlimited'}\n"
        f"📅 Expiry: {text if text != '-' else 'Never'}",
        parse_mode=ParseMode.HTML,
    )
    await log_admin_action(
        context.bot, update.effective_user.id,
        f"🎟 Created redeem code <code>{d['rm_code']}</code> — {d['rm_coins']} coins"
    )
    for k in ["rm_code", "rm_coins", "rm_premium", "rm_limit"]:
        context.user_data.pop(k, None)
    return ConversationHandler.END


async def cb_rm_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM redeems ORDER BY created_at DESC LIMIT 15")
        rows = await cur.fetchall()
    if not rows:
        text = "📋 No redeem codes yet."
    else:
        lines = ["📋 <b>Redeem Codes</b>\n"]
        for r in rows:
            lines.append(
                f"🎟 <code>{r['code']}</code> — {r['coin_reward']}🪙 | "
                f"{r['used_count']}/{r['usage_limit'] or '∞'} used | {r['status']}"
            )
        text = "\n".join(lines)
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=back_button("ad:redeemmgr"))


async def cb_rm_delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "🗑 Enter the exact redeem code to delete:",
        reply_markup=InlineKeyboardMarkup([[_kb_btn("❌ Cancel", callback_data="rm:delcancel", style="danger")]]),
    )
    return RM_DELETE


async def conv_rm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    code = update.message.text.strip().upper()
    async with db_conn() as db:
        cur = await db.execute("SELECT 1 FROM redeems WHERE code=?", (code,))
        if not await cur.fetchone():
            await update.message.reply_text("❌ No such code found. Please check and try again, or /cancel.")
            return RM_DELETE
        await db.execute("DELETE FROM redeems WHERE code=?", (code,))
        await db.execute("DELETE FROM redeem_uses WHERE code=?", (code,))
        await db.commit()
    await update.message.reply_text(f"✅ Deleted code: <code>{html.escape(code)}</code>", parse_mode=ParseMode.HTML)
    return ConversationHandler.END


async def cb_rm_delete_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


async def cb_rm_delete_all_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_owner(update):
        return
    query = update.callback_query
    await query.answer()
    async with db_conn() as db:
        cur = await db.execute("SELECT COUNT(*) FROM redeems")
        count = (await cur.fetchone())[0]
    if count == 0:
        await query.edit_message_text("No redeem codes to delete.", reply_markup=back_button("ad:redeemmgr"))
        return
    kb = InlineKeyboardMarkup([
        [_kb_btn("✅ Yes, Delete ALL", callback_data="rm:delallconfirm", style="success"),
         _kb_btn("❌ No", callback_data="ad:redeemmgr", style="danger")],
    ])
    await query.edit_message_text(
        f"⚠️ <b>Delete ALL {count} Redeem Codes?</b>\n\nThis cannot be undone.",
        parse_mode=ParseMode.HTML, reply_markup=kb,
    )


async def cb_rm_delete_all_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_owner(update):
        return
    query = update.callback_query
    async with db_conn() as db:
        cur = await db.execute("SELECT COUNT(*) FROM redeems")
        count = (await cur.fetchone())[0]
        await db.execute("DELETE FROM redeems")
        await db.execute("DELETE FROM redeem_uses")
        await db.commit()
    await query.answer("🗑 Deleted all codes")
    await query.edit_message_text(f"🗑 <b>Deleted {count} redeem codes.</b>", parse_mode=ParseMode.HTML)
    await log_admin_action(context.bot, update.effective_user.id, f"🗑 Deleted ALL {count} redeem codes")


# ---------------------------------------------------------------------------
# USER MANAGER
# ---------------------------------------------------------------------------
async def cb_admin_usermgr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await is_admin(update.effective_user.id):
        if update.callback_query:
            await update.callback_query.answer(ADMIN_ONLY_MSG, show_alert=True)
        else:
            await update.effective_message.reply_text(ADMIN_ONLY_MSG)
        return ConversationHandler.END
    if update.callback_query:
        await update.callback_query.answer()
    await update.effective_message.reply_text(
        "🔍 Enter User ID or @username to search:",
        reply_markup=InlineKeyboardMarkup([[_kb_btn("❌ Cancel", callback_data="um:cancel", style="danger")]]),
    )
    return UM_SEARCH


async def cb_um_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


async def conv_um_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        if text.isdigit():
            cur = await db.execute("SELECT * FROM users WHERE user_id=?", (int(text),))
        else:
            uname = text.lstrip("@")
            cur = await db.execute("SELECT * FROM users WHERE username=?", (uname,))
        row = await cur.fetchone()

    if not row:
        await update.message.reply_text("❌ User not found.")
        return ConversationHandler.END

    await send_user_profile(update.message, row["user_id"])
    return ConversationHandler.END


async def send_user_profile(message_or_query, target_id: int, edit: bool = False):
    row = await get_user_row(target_id)
    if not row:
        return
    balance = await get_balance(target_id)
    async with db_conn() as db:
        cur = await db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (target_id,))
        refs = (await cur.fetchone())[0]
    premium = "⭐ Active" if await is_premium_active(target_id) else "❌ None"
    banned = "🚫 Banned" if row["is_banned"] else "✅ Active"

    text = (
        f"👤 <b>User Profile</b>\n\n"
        f"🆔 ID: <code>{target_id}</code>\n"
        f"📛 Name: {html.escape(row['first_name'] or '—')}\n"
        f"🔗 Username: @{html.escape(row['username']) if row['username'] else '—'}\n"
        f"📅 Joined: {fmt_date(row['join_date'])}\n"
        f"🪙 Wallet: {balance}\n"
        f"👥 Referrals: {refs}\n"
        f"⭐ Premium: {premium}\n"
        f"🔒 Status: {banned}"
    )
    viewer_id = message_or_query.from_user.id
    is_owner = viewer_id == OWNER_ID
    rows = [
        [_kb_btn("➕ Add Coins", callback_data=f"um:addc:{target_id}", style="success"),
         _kb_btn("➖ Remove Coins", callback_data=f"um:remc:{target_id}", style="danger")],
    ]
    if is_owner:
        rows.append([_kb_btn("🚫 Ban", callback_data=f"um:ban:{target_id}", style="danger"),
                     _kb_btn("✅ Unban", callback_data=f"um:unban:{target_id}", style="success")])
    rows.append([_kb_btn("👑 Give Premium", callback_data=f"um:givep:{target_id}", style="primary"),
                 _kb_btn("❌ Remove Premium", callback_data=f"um:remp:{target_id}", style="danger")])
    rows.append([_kb_btn("⬅️ Back to Admin Panel", callback_data="ad:home", style="primary")])
    kb = InlineKeyboardMarkup(rows)
    if hasattr(message_or_query, "edit_message_text") and edit:
        await message_or_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await message_or_query.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def cb_admin_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_admin(update.effective_user.id):
        if update.callback_query:
            await update.callback_query.answer(ADMIN_ONLY_MSG, show_alert=True)
        else:
            await update.effective_message.reply_text(ADMIN_ONLY_MSG)
        return
    if update.callback_query:
        await update.callback_query.answer()
    await send_all_users_list(update, context, page=0)


async def send_all_users_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int) -> None:
    per_page = 10
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        total = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        cur = await db.execute(
            "SELECT user_id, username, first_name, is_banned FROM users "
            "ORDER BY join_date DESC LIMIT ? OFFSET ?",
            (per_page, page * per_page),
        )
        rows = await cur.fetchall()

    text = f"👥 <b>All Users</b>\n\n👥 Total Registered: <b>{total}</b>\n\nTap a user to view or manage their profile:"
    buttons = []
    for r in rows:
        label = f"@{r['username']}" if r["username"] else (r["first_name"] or f"ID {r['user_id']}")
        tag = "🚫 " if r["is_banned"] else "👤 "
        buttons.append([_kb_btn(f"{tag}{label}", callback_data=f"au:view:{r['user_id']}:{page}", style="primary")])
    nav = []
    if page > 0:
        nav.append(_kb_btn("⬅️ Prev", callback_data=f"au:list:{page-1}", style="primary"))
    if (page + 1) * per_page < total:
        nav.append(_kb_btn("Next ➡️", callback_data=f"au:list:{page+1}", style="primary"))
    if nav:
        buttons.append(nav)
    buttons.append([_kb_btn("⬅️ Back to Admin Panel", callback_data="ad:home", style="primary")])

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))


async def cb_au_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    page = int(query.data.split(":")[2])
    await send_all_users_list(update, context, page)


async def cb_au_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    target_id = int(query.data.split(":")[2])
    await send_user_profile(query, target_id, edit=True)


async def cb_um_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_owner(update):
        return
    query = update.callback_query
    action, target_id = query.data.split(":")[1], int(query.data.split(":")[2])
    banned = 1 if action == "ban" else 0
    async with db_conn() as db:
        await db.execute("UPDATE users SET is_banned=? WHERE user_id=?", (banned, target_id))
        await db.commit()
    await query.answer("✅ Updated")
    await log_admin_action(context.bot, update.effective_user.id, f"{'🚫 Banned' if banned else '✅ Unbanned'} user {target_id}")
    await send_user_profile(query, target_id, edit=True)


async def cb_um_premium(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    action, target_id = query.data.split(":")[1], int(query.data.split(":")[2])
    if action == "remp":
        await remove_premium(target_id)
        await query.answer("✅ Premium removed")
        await send_user_profile(query, target_id, edit=True)
        return
    kb = InlineKeyboardMarkup([
        [_kb_btn("7 Days", callback_data=f"um:pset:{target_id}:7", style="primary"),
         _kb_btn("30 Days", callback_data=f"um:pset:{target_id}:30", style="primary")],
        [_kb_btn("90 Days", callback_data=f"um:pset:{target_id}:90", style="primary"),
         _kb_btn("Lifetime", callback_data=f"um:pset:{target_id}:0", style="primary")],
        [_kb_btn("⬅️ Back", callback_data=f"um:back:{target_id}", style="primary")],
    ])
    await query.answer()
    await query.edit_message_text("👑 Select Premium Duration:", reply_markup=kb)


async def cb_um_pset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    _, _, target_id, days = query.data.split(":")
    target_id, days = int(target_id), int(days)
    await grant_premium(target_id, None if days == 0 else days, update.effective_user.id)
    await query.answer("✅ Premium granted")
    try:
        await context.bot.send_message(
            target_id,
            f"👑 <b>You've been granted Premium!</b>\nDuration: {'Lifetime' if days==0 else f'{days} days'}",
            parse_mode=ParseMode.HTML,
        )
    except TelegramError:
        pass
    await log_admin_action(
        context.bot, update.effective_user.id,
        f"👑 Granted {'Lifetime' if days == 0 else f'{days} days'} Premium to user {target_id}"
    )
    await send_user_profile(query, target_id, edit=True)


async def cb_um_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    target_id = int(query.data.split(":")[2])
    await query.answer()
    await send_user_profile(query, target_id, edit=True)


async def cb_um_coins_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    action, target_id = query.data.split(":")[1], int(query.data.split(":")[2])
    context.user_data["um_action"] = "add" if action == "addc" else "remove"
    context.user_data["um_target"] = target_id
    await query.message.reply_text(
        "🪙 Enter the coin amount:",
        reply_markup=InlineKeyboardMarkup([[_kb_btn("❌ Cancel", callback_data="um:coincancel", style="danger")]]),
    )
    return UM_AMOUNT


async def cb_um_coin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    context.user_data.pop("um_action", None)
    context.user_data.pop("um_target", None)
    await update.callback_query.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


async def conv_um_coins_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("❌ Please enter a valid positive number.")
        return UM_AMOUNT
    amount = int(text)
    target_id = context.user_data.pop("um_target", None)
    action = context.user_data.pop("um_action", None)
    if target_id is None or action is None:
        await update.message.reply_text("❌ Session expired.")
        return ConversationHandler.END
    if action == "add":
        await add_coins(target_id, amount, "admin_gift", "Admin added coins via User Manager")
        await update.message.reply_text(f"✅ Added {amount} coins to user {target_id}.")
    else:
        ok = await remove_coins(target_id, amount, "admin_deduct", "Admin removed coins via User Manager")
        await update.message.reply_text(
            f"✅ Removed {amount} coins from user {target_id}." if ok else "❌ Insufficient balance to remove that amount."
        )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# PREMIUM MANAGER
# ---------------------------------------------------------------------------
async def cb_admin_premiummgr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_admin(update.effective_user.id):
        if update.callback_query:
            await update.callback_query.answer(ADMIN_ONLY_MSG, show_alert=True)
        else:
            await update.effective_message.reply_text(ADMIN_ONLY_MSG)
        return
    if update.callback_query:
        await update.callback_query.answer()
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM premium ORDER BY granted_at DESC LIMIT 20")
        rows = await cur.fetchall()
    if not rows:
        text = "👑 <b>Premium Manager</b>\n\nNo premium users yet.\n\nUse 👥 User Manager to grant premium to a specific user."
    else:
        lines = ["👑 <b>Premium Users</b>\n"]
        for r in rows:
            status = "Lifetime" if r["is_lifetime"] else fmt_date(r["expiry_date"])
            lines.append(f"🆔 <code>{r['user_id']}</code> — {status}")
        text = "\n".join(lines)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=back_button("ad:home"))
    else:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)


# ---------------------------------------------------------------------------
# ADMIN MANAGER
# ---------------------------------------------------------------------------
async def cb_admin_adminmgr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_admin(update.effective_user.id):
        if update.callback_query:
            await update.callback_query.answer(ADMIN_ONLY_MSG, show_alert=True)
        else:
            await update.effective_message.reply_text(ADMIN_ONLY_MSG)
        return
    if update.callback_query:
        await update.callback_query.answer()

    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM admins ORDER BY added_date")
        rows = await cur.fetchall()

    lines = ["🛡 <b>Admin Manager</b>\n"]
    lines.append(f"👑 Owner: <code>{OWNER_ID}</code>")
    for r in rows:
        if r["user_id"] == OWNER_ID:
            continue
        u = await get_user_row(r["user_id"])
        label = f"@{u['username']}" if u and u["username"] else (u["first_name"] if u else "Unknown")
        role_tag = "🥇 Senior" if r["role"] == "senior" else "🥈 Junior"
        lines.append(f"🛡 <code>{r['user_id']}</code> — {html.escape(label or '—')} ({role_tag})")
    text = "\n".join(lines)

    buttons = []
    is_owner = update.effective_user.id == OWNER_ID
    if is_owner:
        buttons.append([_kb_btn("➕ Add Admin", callback_data="am:add", style="success"),
                         _kb_btn("➖ Remove Admin", callback_data="am:remove", style="danger")])
        buttons.append([_kb_btn("📜 Action Log", callback_data="am:log:0", style="primary")])
    buttons.append([_kb_btn("⬅️ Back", callback_data="ad:home", style="primary")])
    kb = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def cb_am_log_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await require_owner(update):
        return
    await query.answer()
    page = int(query.data.split(":")[2])
    per_page = 10
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM admin_logs ORDER BY log_id DESC LIMIT ? OFFSET ?", (per_page, page * per_page)
        )
        rows = await cur.fetchall()

    if not rows and page == 0:
        text = "📜 <b>Admin Action Log</b>\n\nNo actions recorded yet."
    else:
        lines = ["📜 <b>Admin Action Log</b>\n"]
        for r in rows:
            u = await get_user_row(r["actor_id"])
            label = f"@{u['username']}" if u and u["username"] else str(r["actor_id"])
            lines.append(f"👤 {html.escape(label)} — {r['action_text']}\n<i>{fmt_date(r['timestamp'])}</i>")
        text = "\n\n".join(lines)

    nav = []
    if page > 0:
        nav.append(_kb_btn("⬅️ Prev", callback_data=f"am:log:{page-1}", style="primary"))
    if len(rows) == per_page:
        nav.append(_kb_btn("Next ➡️", callback_data=f"am:log:{page+1}", style="primary"))
    buttons = [nav] if nav else []
    buttons.append([_kb_btn("⬅️ Back", callback_data="ad:adminmgr", style="primary")])
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))


async def cb_am_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if update.effective_user.id != OWNER_ID:
        await query.answer("🚫 Only the owner can add admins.", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    await query.message.reply_text(
        "👤 Send the User ID or @username to promote to admin:",
        reply_markup=InlineKeyboardMarkup([[_kb_btn("❌ Cancel", callback_data="am:cancel", style="danger")]]),
    )
    return AM_ADD_USER


async def cb_am_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    context.user_data.pop("am_target_id", None)
    await update.callback_query.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


async def conv_am_add_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("🚫 Only the owner can add admins.")
        return ConversationHandler.END
    text = update.message.text.strip()
    target_id = None
    async with db_conn() as db:
        if text.startswith("@"):
            cur = await db.execute("SELECT user_id FROM users WHERE username=?", (text.lstrip("@"),))
            row = await cur.fetchone()
            if row:
                target_id = row[0]
        elif text.isdigit():
            target_id = int(text)

    if target_id is None:
        await update.message.reply_text(
            "❌ Couldn't find that user. They need to have started the bot at least once. Try again, or /cancel."
        )
        return AM_ADD_USER

    context.user_data["am_target_id"] = target_id
    kb = InlineKeyboardMarkup([
        [_kb_btn("🥇 Senior Admin", callback_data="am:role:senior", style="primary"),
         _kb_btn("🥈 Junior Admin", callback_data="am:role:junior", style="primary")],
    ])
    await update.message.reply_text(
        "🛡 Choose their role:\n\n"
        "🥇 <b>Senior</b> — their actions are only reported to you (the Owner).\n"
        "🥈 <b>Junior</b> — their actions are reported to you AND all Senior admins.",
        parse_mode=ParseMode.HTML, reply_markup=kb,
    )
    return AM_ADD_ROLE


async def cb_am_add_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if update.effective_user.id != OWNER_ID:
        await query.answer("🚫 Only the owner can add admins.", show_alert=True)
        return ConversationHandler.END
    await query.answer()
    role = query.data.split(":")[2]
    target_id = context.user_data.pop("am_target_id", None)
    if target_id is None:
        await query.message.reply_text("❌ Something went wrong — please start again.")
        return ConversationHandler.END

    async with db_conn() as db:
        await db.execute(
            "INSERT INTO admins (user_id, added_date, role) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET role=excluded.role",
            (target_id, utcnow().isoformat(), role),
        )
        await db.commit()

    role_label = "Senior Admin 🥇" if role == "senior" else "Junior Admin 🥈"
    await query.message.reply_text(
        f"✅ User <code>{target_id}</code> is now a <b>{role_label}</b>.", parse_mode=ParseMode.HTML
    )
    try:
        await context.bot.send_message(
            target_id, f"🛡 <b>You've been made a {role_label} of this bot!</b>", parse_mode=ParseMode.HTML
        )
    except TelegramError:
        pass
    return ConversationHandler.END


async def cb_am_remove_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if update.effective_user.id != OWNER_ID:
        await query.answer("🚫 Only the owner can remove admins.", show_alert=True)
        return
    await query.answer()
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM admins WHERE user_id != ? ORDER BY added_date", (OWNER_ID,))
        rows = await cur.fetchall()
    if not rows:
        await query.edit_message_text("No sub-admins to remove.", reply_markup=back_button("ad:adminmgr"))
        return
    buttons = []
    for r in rows:
        u = await get_user_row(r["user_id"])
        label = f"@{u['username']}" if u and u["username"] else str(r["user_id"])
        buttons.append([_kb_btn(f"➖ {label}", callback_data=f"am:rm:{r['user_id']}", style="danger")])
    buttons.append([_kb_btn("⬅️ Back", callback_data="ad:adminmgr", style="primary")])
    await query.edit_message_text("➖ Select an admin to remove:", reply_markup=InlineKeyboardMarkup(buttons))


async def cb_am_remove_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if update.effective_user.id != OWNER_ID:
        await query.answer("🚫 Only the owner can remove admins.", show_alert=True)
        return
    target_id = int(query.data.split(":")[2])
    if target_id == OWNER_ID:
        await query.answer("🚫 Can't remove the owner.", show_alert=True)
        return
    async with db_conn() as db:
        await db.execute("DELETE FROM admins WHERE user_id=?", (target_id,))
        await db.commit()
    await query.answer("✅ Removed")
    await cb_am_remove_menu(update, context)


# ---------------------------------------------------------------------------
# BROADCAST
# ---------------------------------------------------------------------------
async def cb_admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await is_admin(update.effective_user.id):
        if update.callback_query:
            await update.callback_query.answer(ADMIN_ONLY_MSG, show_alert=True)
        else:
            await update.effective_message.reply_text(ADMIN_ONLY_MSG)
        return ConversationHandler.END
    if update.callback_query:
        await update.callback_query.answer()
    await update.effective_message.reply_text(
        "📢 Send the message you want to broadcast (text, photo, video, animation, sticker, document, voice, or audio).\n\n"
        "Send /cancel to abort.",
        reply_markup=InlineKeyboardMarkup([
            [_kb_btn("❌ Cancel Broadcast", callback_data="bc:cancel", style="danger")]
        ]),
    )
    return BR_CONTENT


async def cb_broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.message.reply_text("❌ Broadcast cancelled. Returning to Admin Panel.", reply_markup=admin_reply_keyboard())
    context.user_data.clear()
    return ConversationHandler.END


async def conv_broadcast_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    async with db_conn() as db:
        cur = await db.execute("SELECT user_id FROM users")
        all_users = [r[0] for r in await cur.fetchall()]

    status_msg = await msg.reply_text(f"📢 Broadcasting to {len(all_users)} users...")
    counters = {"done": 0, "failed": 0}
    counters_lock = asyncio.Lock()

    async def send_one(uid: int) -> None:
        await TELEGRAM_SEND_LIMITER.acquire()
        try:
            await context.bot.copy_message(chat_id=uid, from_chat_id=msg.chat_id, message_id=msg.message_id)
            async with counters_lock:
                counters["done"] += 1
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
            try:
                await context.bot.copy_message(chat_id=uid, from_chat_id=msg.chat_id, message_id=msg.message_id)
                async with counters_lock:
                    counters["done"] += 1
            except TelegramError:
                async with counters_lock:
                    counters["failed"] += 1
        except TelegramError:
            async with counters_lock:
                counters["failed"] += 1

    await asyncio.gather(*(send_one(uid) for uid in all_users))

    await status_msg.edit_text(
        f"✅ <b>Broadcast Complete</b>\n\n✅ Sent: {counters['done']}\n❌ Failed: {counters['failed']}",
        parse_mode=ParseMode.HTML,
    )
    await log_admin_action(
        context.bot, update.effective_user.id,
        f"📢 Sent a broadcast — reached {counters['done']}, failed {counters['failed']}"
    )
    return ConversationHandler.END


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    admin = await is_admin(update.effective_user.id)
    context.user_data.clear()
    if admin:
        await update.message.reply_text(
            "❌ Cancelled. Returning to Admin Panel.",
            reply_markup=admin_reply_keyboard(update.effective_user.id == OWNER_ID),
        )
    else:
        await update.message.reply_text("❌ Cancelled.", reply_markup=user_reply_keyboard(False))
    return ConversationHandler.END


async def cmd_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    context.user_data.clear()
    admin = await is_admin(user.id)
    if admin:
        await update.effective_message.reply_text(
            "⬅️ Back to Admin Panel.",
            reply_markup=admin_reply_keyboard(user.id == OWNER_ID),
        )
    else:
        await update.effective_message.reply_text(
            "⬅️ Back to Main Menu.", reply_markup=user_reply_keyboard(False)
        )
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# STATISTICS
# ---------------------------------------------------------------------------
async def cb_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_admin(update.effective_user.id):
        if update.callback_query:
            await update.callback_query.answer(ADMIN_ONLY_MSG, show_alert=True)
        else:
            await update.effective_message.reply_text(ADMIN_ONLY_MSG)
        return
    if update.callback_query:
        await update.callback_query.answer()

    async with db_conn() as db:
        total_users = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        active_users = (await (await db.execute(
            "SELECT COUNT(*) FROM users WHERE last_seen > ?",
            ((utcnow() - timedelta(days=7)).isoformat(),)
        )).fetchone())[0]
        premium_users = (await (await db.execute(
            "SELECT COUNT(*) FROM premium WHERE is_lifetime=1 OR expiry_date > ?",
            (utcnow().isoformat(),)
        )).fetchone())[0]
        total_files = (await (await db.execute("SELECT COUNT(*) FROM files WHERE is_deleted=0")).fetchone())[0]
        total_downloads = (await (await db.execute("SELECT COUNT(*) FROM downloads")).fetchone())[0]
        coins_distributed = (await (await db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE amount > 0"
        )).fetchone())[0]
        redeem_count = (await (await db.execute("SELECT COUNT(*) FROM redeem_uses")).fetchone())[0]
        referral_count = (await (await db.execute("SELECT COUNT(*) FROM referrals")).fetchone())[0]
        revenue_stars = (await (await db.execute(
            "SELECT COALESCE(SUM(stars),0) FROM payments WHERE status='accepted'"
        )).fetchone())[0]
        pending_payments = (await (await db.execute(
            "SELECT COUNT(*) FROM payments WHERE status='pending'"
        )).fetchone())[0]

    text = (
        "📊 <b>Statistics</b>\n\n"
        f"👥 Total Users: <b>{total_users}</b>\n"
        f"Active (7d): <b>{active_users}</b>\n"
        f"⭐ Premium Users: <b>{premium_users}</b>\n"
        f"📁 Total Files: <b>{total_files}</b>\n"
        f"⬇️ Downloads: <b>{total_downloads}</b>\n"
        f"🪙 Coins Distributed: <b>{coins_distributed}</b>\n"
        f"🎟 Redeem Count: <b>{redeem_count}</b>\n"
        f"🚀 Referral Count: <b>{referral_count}</b>\n"
        f"💰 Revenue: <b>{revenue_stars} ⭐</b>\n"
        f"⏳ Pending Payments: <b>{pending_payments}</b>"
    )
    kb = InlineKeyboardMarkup([
        [_kb_btn("📈 Top Downloaded Files", callback_data="stats:topfiles", style="primary")],
        [_kb_btn("⬅️ Back", callback_data="ad:home", style="primary")],
    ])
    if update.callback_query:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def cb_stats_top_files(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await is_admin(update.effective_user.id):
        await query.answer(ADMIN_ONLY_MSG, show_alert=True)
        return
    await query.answer()
    async with db_conn() as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT file_name, downloads_count, price FROM files WHERE is_deleted=0 "
            "ORDER BY downloads_count DESC LIMIT 10"
        )
        rows = await cur.fetchall()

    if not rows:
        text = "📈 <b>Top Downloaded Files</b>\n\nNo files yet."
    else:
        medals = ["🥇", "🥈", "🥉"]
        lines = ["📈 <b>Top 10 Downloaded Files</b>\n"]
        for i, r in enumerate(rows):
            rank = medals[i] if i < 3 else f"{i+1}."
            tag = "FREE" if r["price"] == 0 else f"{r['price']} coins"
            lines.append(f"{rank} {html.escape(r['file_name'])} — <b>{r['downloads_count']}</b> downloads ({tag})")
        text = "\n".join(lines)
    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=back_button("ad:stats"))


# ---------------------------------------------------------------------------
# MAINTENANCE
# ---------------------------------------------------------------------------
async def cb_admin_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_admin(update.effective_user.id):
        if update.callback_query:
            await update.callback_query.answer(ADMIN_ONLY_MSG, show_alert=True)
        else:
            await update.effective_message.reply_text(ADMIN_ONLY_MSG)
        return
    current = await get_setting("maintenance", "0")
    kb = InlineKeyboardMarkup([
        [_kb_btn("✅ Enable", callback_data="mt:on", style="success"),
         _kb_btn("❌ Disable", callback_data="mt:off", style="danger")],
        [_kb_btn("⬅️ Back", callback_data="ad:home", style="primary")],
    ])
    status = "🚧 ENABLED" if current == "1" else "✅ DISABLED"
    text = f"🛠 <b>Maintenance Mode</b>\n\nCurrent status: <b>{status}</b>"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)


async def cb_mt_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    val = "1" if query.data == "mt:on" else "0"
    await set_setting("maintenance", val)
    await query.answer("✅ Updated")
    await log_admin_action(context.bot, update.effective_user.id, f"🛠 Maintenance mode turned {'ON' if val == '1' else 'OFF'}")
    await cb_admin_maintenance(update, context)


# ---------------------------------------------------------------------------
# SETTINGS (Owner-only)
# ---------------------------------------------------------------------------
SETTINGS_FIELDS = {
    "referral_reward": "🚀 Referral Reward (coins)",
    "daily_bonus": "💰 Daily Bonus (coins)",
    "premium_daily_bonus": "👑 Premium Daily Bonus (coins)",
    "coin_packages": "🪙 Coin Packages (JSON list)",
    "premium_pricing": "👑 Premium Pricing (JSON list)",
    "coin_rate_inr": "💵 Coins per 1 Rupee (UPI)",
    "upi_payment_id": "® UPI Payment ID",
    "inr_payment_details": "💵 UPI Payment Details (notes)",
    "spin_settings": "🎰 Daily Spin Settings (JSON)",
    "mystery_box_pricing": "📦 Mystery Box Pricing (JSON)",
    "referral_milestones": "🚀 Referral Milestone Rewards (JSON)",
    "streak_rewards": "🔥 Login Streak Rewards (JSON)",
    "star_rate": "⭐ Star Rate",
    "support_username": "💬 Support Username",
    "payment_username": "💰 Payment Username (Stars)",
    "bot_name": "🏷 Bot Name",
    "force_join": "📢 Force Join (1/0)",
    "welcome_message": "👋 Welcome Message",
}


async def cb_admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_owner(update):
        return
    buttons = [[_kb_btn(label, callback_data=f"set:{key}", style="primary")] for key, label in SETTINGS_FIELDS.items()]
    buttons.append([_kb_btn("⬅️ Back", callback_data="ad:home", style="primary")])
    text = "⚙ <b>Settings</b>\n\nSelect a setting to edit:"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))


async def cb_settings_field(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await require_owner(update):
        return ConversationHandler.END
    query = update.callback_query
    await query.answer()
    key = query.data.split(":")[1]
    current = await get_setting(key, "")
    context.user_data["st_key"] = key
    await query.message.reply_text(
        f"✏️ Current value of <b>{SETTINGS_FIELDS.get(key, key)}</b>:\n<code>{html.escape(current)}</code>\n\n"
        f"Send the new value:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            _kb_btn("❌ Cancel", callback_data="st:cancel", style="danger")
        ]]),
    )
    return ST_VALUE


async def cb_settings_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    context.user_data.pop("st_key", None)
    try:
        await update.callback_query.message.reply_text(
            "❌ Cancelled.",
            reply_markup=admin_reply_keyboard(update.effective_user.id == OWNER_ID),
        )
    except TelegramError:
        pass
    return ConversationHandler.END


async def conv_settings_value(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    key = context.user_data.pop("st_key", None)
    if key is None:
        await update.message.reply_text("❌ Session expired.")
        return ConversationHandler.END
    value = update.message.text.strip()
    if key in ("coin_packages", "premium_pricing", "spin_settings",
               "mystery_box_pricing", "referral_milestones", "streak_rewards"):
        try:
            parsed = json.loads(value)
            expected = dict if key == "spin_settings" else list
            if not isinstance(parsed, expected):
                raise ValueError(f"{key} must be a JSON {expected.__name__}")
        except Exception:
            await update.message.reply_text(
                '❌ Invalid JSON. Example: [{"coins": 100, "stars": 3}, {"coins": 500, "stars": 15}]'
            )
            context.user_data["st_key"] = key
            return ST_VALUE
    await set_setting(key, value)
    await update.message.reply_text("✅ Setting updated successfully.")
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# ADMIN PANEL
# ---------------------------------------------------------------------------
async def handle_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_admin(update.effective_user.id):
        await update.effective_message.reply_text(ADMIN_ONLY_MSG)
        return
    is_owner = update.effective_user.id == OWNER_ID
    await update.effective_message.reply_text(
        "👑 <b>Admin Panel</b>\n\nAll admin controls are now available on your keyboard below.\n"
        "Tap <b>⬅️ Back to Main</b> anytime to return to the normal menu.",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_reply_keyboard(is_owner),
    )


async def handle_admin_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await is_admin(update.effective_user.id):
        return
    await update.effective_message.reply_text(
        "🏠 <b>Main Menu</b>", parse_mode=ParseMode.HTML, reply_markup=user_reply_keyboard(True)
    )


async def cb_admin_home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not await is_admin(update.effective_user.id):
        await query.answer(ADMIN_ONLY_MSG, show_alert=True)
        return
    await query.answer()
    await query.edit_message_text(
        "👑 <b>Admin Panel</b>\n\nSelect an option below:",
        parse_mode=ParseMode.HTML, reply_markup=admin_panel_keyboard(),
    )


# ---------------------------------------------------------------------------
# PERIODIC JOBS
# ---------------------------------------------------------------------------
async def job_expire_premium(context: ContextTypes.DEFAULT_TYPE) -> None:
    async with db_conn() as db:
        await db.execute(
            "DELETE FROM premium WHERE is_lifetime=0 AND expiry_date IS NOT NULL AND expiry_date < ?",
            (utcnow().isoformat(),),
        )
        await db.commit()


async def job_expire_redeem_codes(context: ContextTypes.DEFAULT_TYPE) -> None:
    now = utcnow().isoformat()
    async with db_conn() as db:
        cur = await db.execute(
            "SELECT code FROM redeems WHERE expiry_date IS NOT NULL AND expiry_date < ?", (now,)
        )
        expired = [r[0] for r in await cur.fetchall()]
        if expired:
            placeholders = ",".join("?" * len(expired))
            await db.execute(f"DELETE FROM redeems WHERE code IN ({placeholders})", expired)
            await db.execute(f"DELETE FROM redeem_uses WHERE code IN ({placeholders})", expired)
            await db.commit()
            log.info("Auto-deleted %d expired redeem code(s)", len(expired))


async def job_recheck_pending_joins(context: ContextTypes.DEFAULT_TYPE) -> None:
    cutoff = (utcnow() - timedelta(hours=24)).isoformat()
    async with db_conn() as db:
        cur = await db.execute(
            "SELECT DISTINCT user_id FROM transactions "
            "WHERE tx_type='force_join_blocked' AND timestamp > ?", (cutoff,)
        )
        user_ids = [r[0] for r in await cur.fetchall()]

    if not user_ids:
        return
    channels = await list_force_channels()
    if not channels:
        return
    for uid in user_ids:
        missing = await check_force_join(context.bot, uid)
        if not missing:
            try:
                await context.bot.send_message(
                    uid,
                    "✅ <b>Access Unlocked!</b>\n\nYour join request was approved. "
                    "You can now use the bot — send /start.",
                    parse_mode=ParseMode.HTML,
                )
            except Forbidden:
                # User blocked the bot or cannot receive DMs; skip without failing the job.
                log.info("Cannot notify user %s: bot is blocked or chat is inaccessible", uid)
            except (TimedOut, NetworkError) as exc:
                log.warning("Temporary network error notifying user %s: %s", uid, exc)
            except TelegramError as exc:
                log.warning("Telegram could not notify user %s: %s", uid, exc)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error = context.error
    if isinstance(error, Forbidden):
        # Expected Telegram condition: the recipient blocked the bot or chat is unavailable.
        user_id = getattr(getattr(update, "effective_user", None), "id", None)
        log.info("Message not delivered%s: bot blocked or chat inaccessible",
                 f" for user {user_id}" if user_id else "")
        return
    if isinstance(error, Conflict):
        log.error("Telegram polling conflict: another instance is using getUpdates. Stop duplicate bot processes and keep one running.")
        return
    if isinstance(error, BadRequest) and "message is not modified" in str(error).lower():
        log.debug("Skipped unchanged Telegram message edit.")
        return
    if isinstance(error, (TimedOut, NetworkError)):
        log.warning(
            "Temporary Telegram/network error while handling update; the user can retry: %s",
            error,
        )
        return
    log.error("Exception while handling update:", exc_info=error)


# ---------------------------------------------------------------------------
# TEXT ROUTER
# ---------------------------------------------------------------------------
TEXT_ROUTES = {
    "📁 Buy Files": handle_buy_files,
    "💰 My Wallet": handle_my_wallet,
    "🎁 Daily Bonus": handle_daily_bonus,
    "🎰 Daily Spin": handle_daily_spin,
    "📦 Mystery Box": handle_mystery_box,
    "🎫 Support Ticket": handle_support_ticket_prompt,
    "🚀 Invite Friends": handle_invite_friends,
    "📊 My Stats": handle_my_stats,
    "🏆 Leaderboard": handle_leaderboard,
    "💬 Support": handle_support,
    "👑 Admin Panel": handle_admin_panel,
    "📂 Manage Files": cb_admin_managefiles,
    "💰 Wallet Manager": cb_admin_walletmgr,
    "🎟 Redeem Manager": cb_admin_redeemmgr,
    "📢 Force Channels": cb_admin_fcmgr,
    "👥 All Users": cb_admin_all_users,
    "👑 Premium Manager": cb_admin_premiummgr,
    "🛡 Admin Manager": cb_admin_adminmgr,
    "📋 Admin List": cb_admin_adminmgr,
    "📊 Statistics": cb_admin_stats,
    "🛠 Maintenance": cb_admin_maintenance,
    "⚙ Settings": cb_admin_settings,
    "⬅️ Back to Main": handle_admin_back_to_main,

    "📁 Buy Files": handle_buy_files,
    "💰 My Wallet": handle_my_wallet,
    "🎁 Daily Bonus": handle_daily_bonus,
    "🎰 Daily Spin": handle_daily_spin,
    "📦 Mystery Box": handle_mystery_box,
    "🚀 Invite Friends": handle_invite_friends,
    "🎟️ Redeem Code": handle_redeem_prompt,
    "📊 My Stats": handle_my_stats,
    "🏆 Leaderboard": handle_leaderboard,
    "🎫 Support Ticket": handle_support_ticket_prompt,
    "💎 Buy Premium": handle_buy_premium_menu,
    "💬 Support": handle_support,
}

_EMOJI_PREFIX_RE = re.compile(r"^(?:[🟢🔴🟡]\s+)+")


def _strip_theme_prefix(text: str) -> str:
    return _EMOJI_PREFIX_RE.sub("", text).strip()


_MENU_LABELS = sorted(set(TEXT_ROUTES), key=len, reverse=True)
MENU_BUTTON_PATTERN = re.compile(r"^(?:" + "|".join(re.escape(x) for x in _MENU_LABELS) + r")$")
MENU_BUTTON_FILTER = filters.Regex(MENU_BUTTON_PATTERN)


async def conv_menu_escape(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Allow reply-keyboard navigation to cancel an active text form cleanly."""
    if update.message is None or not update.message.text:
        return ConversationHandler.END
    raw = update.message.text
    handler = TEXT_ROUTES.get(raw) or TEXT_ROUTES.get(_strip_theme_prefix(raw))
    if handler is not None:
        await handler(update, context)
    else:
        await update.message.reply_text("🏠 Menu action received. Please choose an option again.")
    return ConversationHandler.END


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None or update.message.text is None:
        return
    if context.user_data is not None and context.user_data.get("awaiting_reject_reason"):
        await handle_reject_reason(update, context)
        return
    raw = update.message.text
    handler = TEXT_ROUTES.get(raw)
    if handler is None:
        handler = TEXT_ROUTES.get(_strip_theme_prefix(raw))
    if handler:
        await handler(update, context)


# ---------------------------------------------------------------------------
# APPLICATION BUILDER
# ---------------------------------------------------------------------------
def build_application() -> Application:
    concurrent_updates = 64
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .concurrent_updates(concurrent_updates)
        .request(HTTPXRequest(
            connection_pool_size=concurrent_updates,
            pool_timeout=30.0,
            connect_timeout=30.0,
            read_timeout=45.0,
            write_timeout=45.0,
        ))
        .get_updates_request(HTTPXRequest(
            connection_pool_size=16,
            pool_timeout=30.0,
            connect_timeout=30.0,
            read_timeout=45.0,
            write_timeout=45.0,
        ))
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # ⭐ GLOBAL GUARDS (ordering matters: hard gate first, then group restriction, then flood)
    app.add_handler(MessageHandler(filters.ALL, force_join_hard_gate), group=-3)
    app.add_handler(CallbackQueryHandler(force_join_hard_gate), group=-3)
    app.add_handler(MessageHandler(filters.ALL, group_restriction_guard), group=-2)
    app.add_handler(CallbackQueryHandler(group_restriction_guard), group=-2)
    app.add_handler(MessageHandler(filters.ALL, flood_guard), group=-1)
    app.add_handler(CallbackQueryHandler(flood_guard), group=-1)

    # Core Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("back", cmd_back))

    # Verification
    app.add_handler(CallbackQueryHandler(cb_verify_join, pattern="^verify_join$"))

    # Wallet & Payments
    app.add_handler(CallbackQueryHandler(cb_wallet_home, pattern="^wallet:home$"))
    app.add_handler(CallbackQueryHandler(cb_wallet_tx, pattern="^wallet:tx:"))
    app.add_handler(CallbackQueryHandler(cb_wallet_buy_premium, pattern="^wallet:buypremium$"))
    app.add_handler(CallbackQueryHandler(handle_buy_coins_upi, pattern="^wallet:buyupi$"))
    app.add_handler(CallbackQueryHandler(cb_buycoins_start, pattern="^wallet:buycoins$"))
    app.add_handler(CallbackQueryHandler(cb_stars_coin_invoice, pattern=r"^stars:coins:\d+$"))
    custom_stars_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_custom_stars_start, pattern=r"^stars:coins:custom$")],
        states={BC_CUSTOM_STARS: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_custom_stars_amount)]},
        fallbacks=[CommandHandler("cancel", cmd_cancel), CommandHandler("back", cmd_back), MessageHandler(MENU_BUTTON_FILTER, conv_menu_escape)],
        per_message=False,
    )
    app.add_handler(custom_stars_conv)
    app.add_handler(PreCheckoutQueryHandler(precheckout_star_payment))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_star_payment))
    app.add_handler(CallbackQueryHandler(cb_payment_accept, pattern=r"^pay:accept:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_payment_reject, pattern=r"^pay:reject:\d+$"))

    app.add_handler(CallbackQueryHandler(cb_premium_menu, pattern="^premium:menu$"))
    app.add_handler(CallbackQueryHandler(cb_premium_exchange_menu, pattern="^premium:exchange$"))
    app.add_handler(CallbackQueryHandler(cb_premium_purchase, pattern=r"^premium:buy:\d+:\d+$"))

    buycoins_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_buycoins_paid, pattern="^buycoins:paid$")],
        states={
            BC_STARS: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_buycoins_stars)],
            BC_SCREENSHOT: [MessageHandler((filters.PHOTO | filters.Document.ALL) & ~filters.COMMAND, conv_buycoins_screenshot)],
        },
        fallbacks=[
            MessageHandler(MENU_BUTTON_FILTER, conv_menu_escape),
            CallbackQueryHandler(cb_buycoins_cancel, pattern="^buycoins:cancel$"),
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("back", cmd_back),
        ],
        per_message=False,
    )
    app.add_handler(buycoins_conv)

    buyupi_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_buyupi_paid, pattern="^buyupi:paid$")],
        states={
            INR_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_buyupi_amount)],
            # UPI proof must be a photo screenshot only.
            INR_PROOF: [MessageHandler(filters.ALL & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_buyupi_proof)],
        },
        fallbacks=[
            MessageHandler(MENU_BUTTON_FILTER, conv_menu_escape),
            CallbackQueryHandler(cb_buyupi_cancel, pattern="^buyupi:cancel$"),
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("back", cmd_back),
        ],
        per_message=False,
    )
    app.add_handler(buyupi_conv)

    app.add_handler(CallbackQueryHandler(cb_spin_go, pattern="^spin:go$"))
    app.add_handler(CallbackQueryHandler(cb_mystery_open, pattern=r"^mystery:open:\w+:\d+$"))

    # Ticket System
    ticket_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(🎫|🎫) Support Ticket$"), handle_support_ticket_prompt)],
        states={
            TK_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_ticket_subject)],
            TK_BODY: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_ticket_body)],
        },
        fallbacks=[
            MessageHandler(MENU_BUTTON_FILTER, conv_menu_escape),
            CallbackQueryHandler(cb_ticket_cancel, pattern="^ticket:cancel$"),
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("back", cmd_back),
        ],
        per_message=False,
    )
    app.add_handler(ticket_conv)

    ticket_reply_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_ticket_reply_start, pattern=r"^ticket:reply:\d+$")],
        states={TK_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_ticket_reply)]},
        fallbacks=[MessageHandler(MENU_BUTTON_FILTER, conv_menu_escape), CommandHandler("cancel", cmd_cancel), CommandHandler("back", cmd_back)],
        per_message=False,
    )
    app.add_handler(ticket_reply_conv)

    ticket_user_reply_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_ticket_user_reply_start, pattern=r"^ticket:ureply:\d+$")],
        states={TK_USER_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_ticket_user_reply)]},
        fallbacks=[
            MessageHandler(MENU_BUTTON_FILTER, conv_menu_escape),
            CallbackQueryHandler(cb_ticket_cancel, pattern="^ticket:cancel$"),
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("back", cmd_back),
        ],
        per_message=False,
    )
    app.add_handler(ticket_user_reply_conv)

    app.add_handler(CallbackQueryHandler(cb_ticket_close, pattern=r"^ticket:close:\d+$"))

    # File Requests
    freq_conv = ConversationHandler(
        entry_points=[CommandHandler("request", handle_file_request_prompt)],
        states={FR_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_file_request_text)]},
        fallbacks=[
            MessageHandler(MENU_BUTTON_FILTER, conv_menu_escape),
            CallbackQueryHandler(cb_file_request_cancel, pattern="^freq:cancel$"),
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("back", cmd_back),
        ],
        per_message=False,
    )
    app.add_handler(freq_conv)
    app.add_handler(CallbackQueryHandler(cb_file_request_done, pattern=r"^freq:done:\d+$"))

    # Redeem Center
    app.add_handler(MessageHandler(filters.Regex("^(🎟️|🎟️) Redeem Code$"), handle_redeem_prompt))
    app.add_handler(CallbackQueryHandler(cb_redeem_cancel, pattern="^redeem:cancel$"))

    redeem_enter_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_redeem_enter_start, pattern="^redeem:enter$")],
        states={RD_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, handle_redeem_code)]},
        fallbacks=[MessageHandler(MENU_BUTTON_FILTER, conv_menu_escape), CommandHandler("cancel", cmd_cancel), CommandHandler("back", cmd_back)],
        per_message=False,
    )
    app.add_handler(redeem_enter_conv)

    redeem_gift_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_redeem_gift_start, pattern="^redeem:gift$")],
        states={GC_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_gift_amount)]},
        fallbacks=[MessageHandler(MENU_BUTTON_FILTER, conv_menu_escape), CommandHandler("cancel", cmd_cancel), CommandHandler("back", cmd_back)],
        per_message=False,
    )
    app.add_handler(redeem_gift_conv)

    # File Store
    app.add_handler(CallbackQueryHandler(cb_files_list, pattern=r"^files:list:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_file_view, pattern=r"^file:view:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_file_buy, pattern=r"^file:buy:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_file_download, pattern=r"^file:dl:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_my_purchases, pattern=r"^purchases:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_my_referrals, pattern=r"^myrefs:\d+$"))

    # Admin Panel Callbacks
    app.add_handler(CallbackQueryHandler(cb_admin_home, pattern="^ad:home$"))
    app.add_handler(CallbackQueryHandler(cb_admin_managefiles, pattern="^ad:managefiles$"))
    app.add_handler(CallbackQueryHandler(cb_admin_walletmgr, pattern="^ad:walletmgr$"))
    app.add_handler(CallbackQueryHandler(cb_admin_redeemmgr, pattern="^ad:redeemmgr$"))
    app.add_handler(CallbackQueryHandler(cb_admin_fcmgr, pattern="^ad:fcmgr$"))
    app.add_handler(CallbackQueryHandler(cb_admin_premiummgr, pattern="^ad:premiummgr$"))
    app.add_handler(CallbackQueryHandler(cb_admin_adminmgr, pattern="^ad:adminmgr$"))
    app.add_handler(CallbackQueryHandler(cb_am_remove_menu, pattern="^am:remove$"))
    app.add_handler(CallbackQueryHandler(cb_am_log_view, pattern=r"^am:log:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_am_remove_confirm, pattern=r"^am:rm:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_stats, pattern="^ad:stats$"))
    app.add_handler(CallbackQueryHandler(cb_stats_top_files, pattern="^stats:topfiles$"))
    app.add_handler(CallbackQueryHandler(cb_admin_maintenance, pattern="^ad:maintenance$"))
    app.add_handler(CallbackQueryHandler(cb_mt_toggle, pattern="^mt:(on|off)$"))
    app.add_handler(CallbackQueryHandler(cb_admin_settings, pattern="^ad:settings$"))

    am_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_am_add_start, pattern="^am:add$")],
        states={
            AM_ADD_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_am_add_user)],
            AM_ADD_ROLE: [CallbackQueryHandler(cb_am_add_role, pattern=r"^am:role:(senior|junior)$")],
        },
        fallbacks=[
            MessageHandler(MENU_BUTTON_FILTER, conv_menu_escape),
            CallbackQueryHandler(cb_am_cancel, pattern="^am:cancel$"),
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("back", cmd_back),
        ],
        per_message=False,
    )
    app.add_handler(am_add_conv)

    # Admin Upload
    upload_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cb_admin_upload_start, pattern="^ad:upload$"),
            MessageHandler(filters.Regex("^📤 Upload File$"), cb_admin_upload_start),
        ],
        states={
            UP_FILE: [MessageHandler(
                (filters.Document.ALL | filters.VIDEO | filters.AUDIO | filters.PHOTO | filters.VOICE | filters.ANIMATION) & ~filters.COMMAND,
                conv_upload_file
            )],
            UP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_upload_name)],
            UP_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_upload_desc)],
            UP_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_upload_price)],
            UP_PREVIEW: [
                CallbackQueryHandler(cb_upload_publish, pattern="^up:publish$"),
                CallbackQueryHandler(cb_upload_edit, pattern="^up:edit$"),
                CallbackQueryHandler(cb_upload_cancel, pattern="^up:cancel$"),
            ],
        },
        fallbacks=[MessageHandler(MENU_BUTTON_FILTER, conv_menu_escape), CommandHandler("cancel", cmd_cancel), CommandHandler("back", cmd_back)],
        per_message=False,
    )
    app.add_handler(upload_conv)

    # Manage Files
    app.add_handler(CallbackQueryHandler(cb_mf_list, pattern=r"^mf:list:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_mf_view, pattern=r"^mf:view:\d+:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_mf_toggle_featured, pattern=r"^mf:tfeat:\d+:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_mf_delete, pattern=r"^mf:delete:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_mf_delete_confirm, pattern=r"^mf:delconfirm:\d+$"))

    edit_field_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_mf_edit_field, pattern=r"^mf:(ename|edesc|eprice|etier):\d+$")],
        states={EF_FIELD: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_edit_field_value)]},
        fallbacks=[
            MessageHandler(MENU_BUTTON_FILTER, conv_menu_escape),
            CallbackQueryHandler(cb_mf_edit_cancel, pattern="^mf:editcancel$"),
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("back", cmd_back),
        ],
        per_message=False,
    )
    app.add_handler(edit_field_conv)

    mf_search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_mf_search_start, pattern="^mf:searchstart$")],
        states={MF_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_mf_search)]},
        fallbacks=[MessageHandler(MENU_BUTTON_FILTER, conv_menu_escape), CommandHandler("cancel", cmd_cancel), CommandHandler("back", cmd_back)],
        per_message=False,
    )
    app.add_handler(mf_search_conv)

    # Force Channels
    fc_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_fc_add_start, pattern="^fc:add$")],
        states={FC_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_fc_add)]},
        fallbacks=[
            MessageHandler(MENU_BUTTON_FILTER, conv_menu_escape),
            CallbackQueryHandler(cb_fc_cancel, pattern="^fc:cancel$"),
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("back", cmd_back),
        ],
        per_message=False,
    )
    app.add_handler(fc_add_conv)
    app.add_handler(CallbackQueryHandler(cb_fc_list, pattern="^fc:list$"))
    app.add_handler(CallbackQueryHandler(cb_fc_remove_menu, pattern="^fc:remove$"))
    app.add_handler(CallbackQueryHandler(cb_fc_remove_confirm, pattern=r"^fc:rm:\d+$"))

    # Wallet Manager
    wm_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_wm_action_start, pattern="^wm:(add|remove|reset|setbal)$")],
        states={
            UM_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_wm_user_id)],
            UM_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_wm_amount)],
        },
        fallbacks=[
            MessageHandler(MENU_BUTTON_FILTER, conv_menu_escape),
            CallbackQueryHandler(cb_wm_cancel, pattern="^wm:cancel$"),
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("back", cmd_back),
        ],
        per_message=False,
    )
    app.add_handler(wm_conv)
    app.add_handler(CallbackQueryHandler(cb_wm_history, pattern="^wm:history$"))

    wb_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_wm_bulk_start, pattern="^wm:bulk$")],
        states={
            WB_IDS: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_wm_bulk_ids)],
            WB_ACTION: [
                CallbackQueryHandler(cb_wb_action_coins, pattern="^wb:(add|remove)$"),
                CallbackQueryHandler(cb_wb_action_ban, pattern="^wb:(ban|unban)$"),
                CallbackQueryHandler(cb_wb_action_premium_menu, pattern="^wb:premium$"),
                CallbackQueryHandler(cb_wb_cancel, pattern="^wb:cancel$"),
            ],
            WB_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_wm_bulk_amount)],
            WB_PREMIUM: [CallbackQueryHandler(cb_wb_action_premium_set, pattern=r"^wb:pset:\d+$")],
        },
        fallbacks=[MessageHandler(MENU_BUTTON_FILTER, conv_menu_escape), CommandHandler("cancel", cmd_cancel), CommandHandler("back", cmd_back)],
        per_message=False,
    )
    app.add_handler(wb_conv)

    app.add_handler(CallbackQueryHandler(cb_pending_payments_list, pattern=r"^pp:list:\d+$"))

    # Redeem Manager
    rm_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_rm_create_start, pattern="^rm:create$")],
        states={
            RM_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_rm_code)],
            RM_COINS: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_rm_coins)],
            RM_PREMIUM: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_rm_premium)],
            RM_LIMIT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_rm_limit)],
            RM_EXPIRY: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_rm_expiry)],
        },
        fallbacks=[
            MessageHandler(MENU_BUTTON_FILTER, conv_menu_escape),
            CallbackQueryHandler(cb_rm_cancel, pattern="^rm:cancel$"),
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("back", cmd_back),
        ],
        per_message=False,
    )
    app.add_handler(rm_conv)
    app.add_handler(CallbackQueryHandler(cb_rm_list, pattern="^rm:list$"))
    app.add_handler(CallbackQueryHandler(cb_rm_delete_all_confirm, pattern="^rm:delall$"))
    app.add_handler(CallbackQueryHandler(cb_rm_delete_all_execute, pattern="^rm:delallconfirm$"))

    rm_delete_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_rm_delete_start, pattern="^rm:delstart$")],
        states={RM_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_rm_delete)]},
        fallbacks=[
            MessageHandler(MENU_BUTTON_FILTER, conv_menu_escape),
            CallbackQueryHandler(cb_rm_delete_cancel, pattern="^rm:delcancel$"),
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("back", cmd_back),
        ],
        per_message=False,
    )
    app.add_handler(rm_delete_conv)

    # User Manager
    um_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cb_admin_usermgr, pattern="^ad:usermgr$"),
            MessageHandler(filters.Regex("^👥 User Manager$"), cb_admin_usermgr),
            CallbackQueryHandler(cb_um_coins_start, pattern=r"^um:(addc|remc):\d+$"),
        ],
        states={
            UM_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_um_search)],
            UM_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_um_coins_amount)],
        },
        fallbacks=[
            MessageHandler(MENU_BUTTON_FILTER, conv_menu_escape),
            CallbackQueryHandler(cb_um_cancel, pattern="^um:cancel$"),
            CallbackQueryHandler(cb_um_coin_cancel, pattern="^um:coincancel$"),
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("back", cmd_back),
        ],
        per_message=False,
    )
    app.add_handler(um_conv)
    app.add_handler(CallbackQueryHandler(cb_um_ban, pattern=r"^um:(ban|unban):\d+$"))
    app.add_handler(CallbackQueryHandler(cb_um_premium, pattern=r"^um:(givep|remp):\d+$"))
    app.add_handler(CallbackQueryHandler(cb_um_pset, pattern=r"^um:pset:\d+:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_um_back, pattern=r"^um:back:\d+$"))

    app.add_handler(CallbackQueryHandler(cb_au_list, pattern=r"^au:list:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_au_view, pattern=r"^au:view:\d+:\d+$"))

    # Broadcast
    broadcast_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cb_admin_broadcast_start, pattern="^ad:broadcast$"),
            MessageHandler(filters.Regex("^📢 Broadcast$"), cb_admin_broadcast_start),
        ],
        states={BR_CONTENT: [MessageHandler(
            (filters.TEXT | filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.Sticker.ALL |
             filters.Document.ALL | filters.VOICE | filters.AUDIO) & ~filters.COMMAND & ~MENU_BUTTON_FILTER,
            conv_broadcast_content
        )]},
        fallbacks=[
            MessageHandler(MENU_BUTTON_FILTER, conv_menu_escape),
            CallbackQueryHandler(cb_broadcast_cancel, pattern="^bc:cancel$"),
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("back", cmd_back),
        ],
        per_message=False,
    )
    app.add_handler(broadcast_conv)

    # Settings
    settings_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_settings_field, pattern=r"^set:\w+$")],
        states={ST_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~MENU_BUTTON_FILTER, conv_settings_value)]},
        fallbacks=[
            MessageHandler(MENU_BUTTON_FILTER, conv_menu_escape),
            CallbackQueryHandler(cb_settings_cancel, pattern="^st:cancel$"),
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("back", cmd_back),
        ],
        per_message=False,
    )
    app.add_handler(settings_conv)

    # Text Router
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    # Global Cancel / Back
    app.add_handler(CommandHandler("cancel", cmd_cancel), group=1)
    app.add_handler(CommandHandler("back", cmd_back), group=1)

    app.add_error_handler(error_handler)
    return app


async def post_init(app: Application) -> None:
    await init_db()
    await init_db_pool()
    if app.job_queue:
        # Keep APScheduler's displayed run times in India Standard Time too.
        # Preserve PTB's configured scheduler settings while changing timezone.
        # PTB's scheduler_configuration already contains a timezone key.
        # Override that value before configure() to avoid passing timezone twice.
        scheduler_config = dict(app.job_queue.scheduler_configuration)
        scheduler_config["timezone"] = ZoneInfo("Asia/Kolkata")
        app.job_queue.scheduler.configure(**scheduler_config)
        app.job_queue.run_repeating(job_expire_premium, interval=3600, first=10)
        app.job_queue.run_repeating(job_expire_redeem_codes, interval=3600, first=15)
        app.job_queue.run_repeating(job_recheck_pending_joins, interval=900, first=60)
        log.info("Scheduled jobs configured in Asia/Kolkata (IST).")
    log.info("Bot initialized and ready.")


async def post_shutdown(app: Application) -> None:
    await close_db_pool()


def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing. Set the Telegram bot token in your hosting "
            "Wispbyte environment variables as BOT_TOKEN. Never paste the token into source code."
        )
    app = build_application()
    log.info("Starting NAGENDRA FILE STORE BOT...")
    app.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()