#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADVANCED HOSTING PANEL  v3

 * Premium (custom) emojis in texts AND buttons (IDs from ORIGINAL below)
 * Every message is rendered in Telegram "quote" (blockquote) style
 * Any <name>.py file can be uploaded / hosted
 * Owner + Admins (add / remove admin from the panel)
 * Force-join channels (bot must be admin in the channel)
 * Per-user hosted-file limit (default + per-user override), owner = unlimited
 * Settings (admins, bans, channels, limits, users) persist in panel_data.json
"""

import asyncio
import hashlib
import html
import json
import os
import re
import signal
import subprocess
import sys
import time
import warnings
from datetime import datetime
from functools import wraps

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

try:
    import psutil
except ImportError:  # optional
    psutil = None

warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

# ==================== CONFIG ====================
# Token ko env var BOT_TOKEN se do (recommended). Neeche wala default purana token hai -
# BotFather se /revoke karke naya token env me daalo.
TOKEN = os.environ.get("BOT_TOKEN", "8607229810:AAERSXhBV_goVF7hPNPTmUGq0NumyzdWeTs")
OWNER_ID = 8388115033  # Owner: unlimited files + can add/remove admins

UPDATE_CHANNEL_URL = "https://t.me/ownernagendrah4x"

BASE_DIR = "users"
PENDING_DIR = "pending_uploads"
DB_FILE = "panel_data.json"

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
DEFAULT_LIMIT = 1                 # first-run default (admin panel se change hota hai)

# Premium emojis: "1" = on, "0" = off (plain emojis). Bot start par auto-test bhi hota hai.
PREMIUM = os.environ.get("PREMIUM_EMOJI", "1") != "0"

os.makedirs(BASE_DIR, exist_ok=True)
os.makedirs(PENDING_DIR, exist_ok=True)

HTML = ParseMode.HTML

# ==================== PREMIUM EMOJI POOL ====================
# (fallback emoji, custom emoji id)  -- same order as your list (1..49)
ORIGINAL = [
    ("😒", "6222005021614016071"),   # 1
    ("🍼", "6310073991738433329"),   # 2
    ("✅", "6309618368722770953"),   # 3
    ("😪", "6312263609015606057"),   # 4
    ("‼️", "6310012560821197814"),   # 5
    ("🧐", "6310087310432018431"),   # 6
    ("✨", "6312315895947467982"),   # 7
    ("❤️‍🔥", "6309579091246850317"),  # 8
    ("🤍", "6312215153194573209"),   # 9
    ("✔️", "6310103949135322908"),   # 10
    ("✅", "6309586272432169678"),   # 11
    ("💠", "6309958250959739643"),   # 12
    ("🧸", "6312114182808411673"),   # 13
    ("👍", "6309697344581410091"),   # 14
    ("📣", "6309618596356039410"),   # 15
    ("👑", "6310083389126876253"),   # 16
    ("🎁", "6312282231993801242"),   # 17
    ("🎁", "6312196994072847118"),   # 18
    ("🎁", "6309668976322420229"),   # 19
    ("⭐", "6309569217117035347"),   # 20
    ("🔝", "6309690717446873246"),   # 21
    ("🎁", "6309658290443787286"),   # 22
    ("🗓", "6309633203539811774"),   # 23
    ("😊", "6309630076803620076"),   # 24
    ("💭", "6310080687592447094"),   # 25
    ("👍", "5465465194056525619"),   # 26
    ("🥰", "5465262274031659421"),   # 27
    ("👋", "5462910521739063094"),   # 28
    ("✅", "6314482651113724077"),   # 29
    ("😄", "6311798614381302710"),   # 30
    ("🌹", "6314555236061025743"),   # 31
    ("🌷", "6312035834014996364"),   # 32
    ("🔥", "6312181703989269871"),   # 33
    ("😀", "6312100331538880288"),   # 34
    ("⚠️", "6312099300746728685"),   # 35
    ("‼️", "6312147825287239190"),   # 36
    ("❤️", "6311970614936607184"),   # 37
    ("❤️", "6314107928102050204"),   # 38
    ("1⃣", "6312061298876094689"),   # 39
    ("🕐", "6314601797801482624"),   # 40
    ("✨", "6312043448992011868"),   # 41
    ("🤖", "6314482200142157650"),   # 42
    ("😈", "6057368436848204867"),   # 43
    ("✅", "6055535246022022624"),   # 44
    ("✅", "6057607340109077778"),   # 45
    ("😈", "6057368436848204867"),   # 46
    ("👑", "6057721277001504261"),   # 47
    ("❤️‍🔥", "6057459838047230701"),  # 48
    ("😁", "6057351025050785455"),   # 49
]

# semantic name -> index (1-based) in ORIGINAL
EMO = {
    "no": 1, "bottle": 2, "ok": 3, "sleep": 4, "bang": 5, "think": 6, "spark": 7,
    "fire_heart": 8, "white": 9, "check": 10, "ok2": 11, "gem": 12, "bear": 13,
    "like": 14, "mega": 15, "crown": 16, "gift": 17, "star": 20, "top": 21,
    "cal": 23, "smile": 24, "thought": 25, "love": 27, "wave": 28, "laugh": 30,
    "rose": 31, "tulip": 32, "fire": 33, "grin": 34, "warn": 35, "heart": 37,
    "one": 39, "clock": 40, "bot": 42, "devil": 43, "happy": 49,
}


def ch(key):
    """plain fallback emoji"""
    return ORIGINAL[EMO[key] - 1][0]


def eid(key):
    return ORIGINAL[EMO[key] - 1][1]


def em(key):
    """emoji for message text (premium if enabled)"""
    if PREMIUM:
        c, i = ORIGINAL[EMO[key] - 1]
        return f'<tg-emoji emoji-id="{i}">{c}</tg-emoji>'
    return ch(key)


# ==================== TEXT HELPERS (QUOTE STYLE) ====================
def esc(text) -> str:
    return html.escape(str(text))


def q(body: str, expandable: bool = False) -> str:
    return f"<blockquote{' expandable' if expandable else ''}>{body}</blockquote>"


def msg(key: str, title: str, *blocks: str) -> str:
    """Title line + every block inside its own quote."""
    return f"{em(key)} <b>{title}</b>\n" + "\n".join(q(b) for b in blocks if b)


def fmt_limit(n: int) -> str:
    return "Unlimited ♾" if n == 0 else str(n)


def format_duration(seconds) -> str:
    try:
        seconds = int(seconds)
    except Exception:
        return "N/A"
    d, r = divmod(seconds, 86400)
    h_, r = divmod(r, 3600)
    m_, s_ = divmod(r, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h_:
        parts.append(f"{h_}h")
    if m_:
        parts.append(f"{m_}m")
    parts.append(f"{s_}s")
    return " ".join(parts)


# ==================== BUTTON HELPERS (PREMIUM ICON + COLOUR) ====================
def ibtn(key, text, cb=None, style=None, url=None):
    kw = {}
    if cb is not None:
        kw["callback_data"] = cb
    if url:
        kw["url"] = url
    extra = {}
    if style:
        extra["style"] = style
    if PREMIUM:
        extra["icon_custom_emoji_id"] = eid(key)
        label = text
    else:
        label = f"{ch(key)} {text}"
    try:
        return InlineKeyboardButton(label, **kw, **extra)
    except TypeError:  # older library without style/icon support
        return InlineKeyboardButton(f"{ch(key)} {text}", **kw)


def kbtn(key, text, style=None):
    extra = {}
    if style:
        extra["style"] = style
    if PREMIUM:
        extra["icon_custom_emoji_id"] = eid(key)
        label = text
    else:
        label = f"{ch(key)} {text}"
    try:
        return KeyboardButton(label, **extra)
    except TypeError:
        return KeyboardButton(f"{ch(key)} {text}")


def norm(text: str) -> str:
    """strip leading emoji/symbols so reply-keyboard labels match with or without emoji"""
    return re.sub(r"^[^A-Za-z0-9]+", "", text or "").strip().lower()


def main_kb(uid=None):
    rows = [
        [kbtn("gift", "Upload File", "primary"), kbtn("gem", "View Files", "primary")],
        [kbtn("fire", "Run Bot", "success"), kbtn("sleep", "Stop Bot", "danger")],
        [kbtn("top", "Bot Speed", "success"), kbtn("think", "Manual Install", "primary")],
        [kbtn("devil", "Delete Files", "danger"), kbtn("thought", "Live Logs", "primary")],
        [kbtn("warn", "View Errors", "primary"), kbtn("mega", "Update Channel", "success")],
        [kbtn("star", "Statistics", "primary")],
    ]
    if uid is not None and is_staff(uid):
        rows.append([kbtn("crown", "Admin Panel", "primary")])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False)


# ==================== DATABASE (JSON) ====================
def _default_db():
    return {
        "admins": [],
        "banned": [],
        "channels": [],            # {"id": int, "title": str, "link": str|None}
        "default_limit": DEFAULT_LIMIT,
        "user_limits": {},         # {"uid": int}  (0 = unlimited)
        "users": {},               # {"uid": {"name":..., "username":..., "t":...}}
        "pending": {},             # approval_id -> info
    }


def load_db():
    base = _default_db()
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in base.items():
            data.setdefault(k, v)
        return data
    except FileNotFoundError:
        return base
    except Exception as e:
        print(f"[db] corrupt {DB_FILE}: {e} -> moved to .bad")
        try:
            os.replace(DB_FILE, DB_FILE + ".bad")
        except OSError:
            pass
        return base


DB = load_db()


def save_db():
    tmp = DB_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(DB, f, ensure_ascii=False, indent=1)
    os.replace(tmp, DB_FILE)


# ==================== ROLES / LIMITS ====================
def is_owner(uid) -> bool:
    return uid == OWNER_ID


def is_admin(uid) -> bool:
    return uid in DB["admins"]


def is_staff(uid) -> bool:
    return is_owner(uid) or is_admin(uid)


def is_banned(uid) -> bool:
    return uid in DB["banned"] and not is_owner(uid)


def user_limit(uid) -> int:
    """0 = unlimited"""
    if is_owner(uid):
        return 0
    v = DB["user_limits"].get(str(uid))
    return int(v) if v is not None else int(DB["default_limit"])


def track_user(user):
    key = str(user.id)
    if key not in DB["users"]:
        DB["users"][key] = {
            "name": user.first_name or "",
            "username": user.username or "",
            "t": int(time.time()),
        }
        save_db()


def all_user_ids():
    ids = {int(k) for k in DB["users"]}
    if os.path.isdir(BASE_DIR):
        for n in os.listdir(BASE_DIR):
            if n.isdigit():
                ids.add(int(n))
    return sorted(ids)


def staff_ids():
    return [OWNER_ID] + [a for a in DB["admins"] if a != OWNER_ID]


# ==================== FILES / PROCESSES ====================
PROCS = {}  # (uid_str, name) -> Popen


def user_dir(uid) -> str:
    return os.path.join(BASE_DIR, str(uid))


def pid_path(uid, name) -> str:
    return os.path.join(user_dir(uid), f"{name}.pid")


def log_path(uid, name, kind) -> str:  # kind: out | err
    return os.path.join(user_dir(uid), "logs", f"{name}.{kind}.log")


def sanitize_filename(name: str) -> str:
    name = os.path.basename(name or "")
    name = re.sub(r"[^\w\.\-]", "_", name)
    return name


def normalize_py_name(name: str):
    """returns clean '<stem>.py' or None if not a python file"""
    name = sanitize_filename(name)
    if not name.lower().endswith(".py"):
        return None
    stem = name[:-3].lstrip(".")
    if not stem:
        return None
    return stem[:90] + ".py"


def h(name: str) -> str:
    return hashlib.md5(name.encode("utf-8")).hexdigest()[:10]


def hosted_py(uid):
    d = user_dir(uid)
    if not os.path.isdir(d):
        return []
    return sorted(
        f for f in os.listdir(d)
        if f.lower().endswith(".py") and os.path.isfile(os.path.join(d, f))
    )


def resolve(uid, hh):
    for n in hosted_py(uid):
        if h(n) == hh:
            return n
    return None


def _rm(path):
    try:
        os.remove(path)
    except OSError:
        pass


def read_pid(uid, name):
    try:
        with open(pid_path(uid, name), "r") as f:
            return int(f.read().strip())
    except Exception:
        return None


def alive(uid, name) -> bool:
    key = (str(uid), name)
    p = PROCS.get(key)
    if p is not None:
        if p.poll() is None:
            return True
        PROCS.pop(key, None)
        _rm(pid_path(uid, name))
        return False
    pid = read_pid(uid, name)
    if pid is None:
        _rm(pid_path(uid, name))
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        _rm(pid_path(uid, name))
        return False
    except PermissionError:
        return True
    except OSError:
        _rm(pid_path(uid, name))
        return False
    if psutil:
        try:
            if psutil.Process(pid).status() == psutil.STATUS_ZOMBIE:
                _rm(pid_path(uid, name))
                return False
        except Exception:
            pass
    return True


def running_files(uid):
    return [n for n in hosted_py(uid) if alive(uid, n)]


def pending_names(uid):
    return [i["file_name"] for i in DB["pending"].values() if i["user_id"] == uid]


def can_add(uid, fname) -> bool:
    lim = user_limit(uid)
    if lim == 0:
        return True
    existing = set(hosted_py(uid)) | set(pending_names(uid))
    return fname in existing or len(existing) < lim


def tail(path, n=3000) -> str:
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - n))
            return f.read().decode("utf-8", "ignore")
    except OSError:
        return ""


# ==================== PIP SAFETY ====================
PKG_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.\-]*(\[[A-Za-z0-9_,\-]+\])?(==[A-Za-z0-9_.\-]+)?$"
)
ALLOWED_OPTS = {"--no-cache-dir", "--no-deps", "--quiet", "-q"}


def parse_pip(cmd: str):
    """Return list of safe args for `python -m pip install ...` or None."""
    parts = (cmd or "").strip().split()
    if len(parts) < 3:
        return None
    if parts[0].lower() in ("pip", "pip3"):
        rest = parts[1:]
    elif len(parts) > 3 and parts[0].lower() in ("python", "python3") and parts[1:3] == ["-m", "pip"]:
        rest = parts[3:]
    else:
        return None
    if not rest or rest[0].lower() != "install":
        return None
    args = rest[1:]
    pkgs = 0
    for a in args:
        if a.startswith("-"):
            if a not in ALLOWED_OPTS:
                return None
        elif PKG_RE.match(a):
            pkgs += 1
        else:
            return None
    return args if pkgs else None


# ==================== SEND / EDIT HELPERS ====================
async def show(update: Update, text: str, kb=None):
    """Edit the callback message if possible, otherwise reply."""
    cq = update.callback_query
    if cq:
        try:
            await cq.edit_message_text(text, reply_markup=kb, parse_mode=HTML)
            return
        except BadRequest as e:
            if "not modified" in str(e).lower():
                return
    await update.effective_message.reply_text(text, reply_markup=kb, parse_mode=HTML)


async def alert(update: Update, text: str):
    cq = update.callback_query
    if cq:
        try:
            await cq.answer(text, show_alert=True)
        except TelegramError:
            pass


# ==================== FORCE JOIN ====================
JOIN_OK = {}  # uid -> expiry


async def missing_channels(bot, uid):
    if not DB["channels"]:
        return []
    if JOIN_OK.get(uid, 0) > time.time():
        return []
    miss = []
    for c in DB["channels"]:
        try:
            m = await bot.get_chat_member(c["id"], uid)
            st = m.status
            if st in ("left", "kicked") or (st == "restricted" and not getattr(m, "is_member", True)):
                miss.append(c)
        except TelegramError as e:
            # bot kicked / channel deleted -> fail open so nobody gets locked out
            print(f"[force-join] cannot check {c['id']}: {e}")
    if not miss:
        JOIN_OK[uid] = time.time() + 90
    return miss


async def send_join_prompt(update: Update, miss):
    rows = []
    lines = []
    for c in miss:
        lines.append(f"{em('mega')} <b>{esc(c['title'])}</b>")
        if c.get("link"):
            rows.append([ibtn("mega", f"Join {c['title'][:28]}", url=c["link"], style="primary")])
    rows.append([ibtn("ok", "Joined — Verify", cb="verify_join", style="success")])
    text = msg(
        "warn", "JOIN REQUIRED",
        "Bot use karne ke liye pehle ye channel(s) join karein:\n\n" + "\n".join(lines),
        "Join karke neeche <b>Verify</b> dabayein.",
    )
    await update.effective_message.reply_text(text, reply_markup=InlineKeyboardMarkup(rows), parse_mode=HTML)


# ==================== ACCESS GATE ====================
async def access_ok(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False
    uid = user.id
    track_user(user)
    if is_staff(uid):
        return True
    if is_banned(uid):
        text = msg("devil", "YOU ARE BANNED", "Aapko admin ne ban kiya hai.\nContact admin.")
        if update.callback_query:
            await alert(update, "🚫 You are banned!")
        else:
            await update.effective_message.reply_text(text, parse_mode=HTML)
        return False
    miss = await missing_channels(context.bot, uid)
    if miss:
        if update.callback_query:
            await alert(update, "Pehle channel join karein!")
        await send_join_prompt(update, miss)
        return False
    return True


def guarded(fn):
    @wraps(fn)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *a, **kw):
        if not await access_ok(update, context):
            return
        return await fn(update, context, *a, **kw)
    return wrapper


# ==================== TEXTS ====================
def welcome_text(user) -> str:
    uid = user.id
    used = len(hosted_py(uid))
    lim = fmt_limit(user_limit(uid))
    text = msg(
        "wave", f"Welcome {esc(user.first_name or 'User')}!",
        f"{em('gem')} <b>Your ID:</b> <code>{uid}</code>\n"
        f"{em('bot')} <b>Hosted files:</b> <code>{used}</code> / <code>{lim}</code>",
        f"{em('fire')} Ultra fast .py hosting\n"
        f"{em('crown')} Admin approval system\n"
        f"{em('thought')} Live logs &amp; error logs\n"
        f"{em('think')} Manual package install\n"
        f"{em('top')} Real-time speed monitor\n"
        f"{em('star')} Premium panel UI",
        f"{em('warn')} Koi bhi <code>.py</code> file upload kar sakte hain.\n"
        f"{em('mega')} Updates ke liye <b>Update Channel</b> dabayein.",
    )
    if is_staff(uid):
        text += "\n" + q(f"{em('crown')} <b>Admin:</b> /admin ya <b>Admin Panel</b> button")
    return text


def help_text() -> str:
    return msg(
        "bot", "ADVANCED HOSTING PANEL",
        f"{em('gift')} <b>Upload:</b> koi bhi <code>.py</code> file document ki tarah bhejo. Admin approve karega → host.\n"
        f"{em('fire')} <b>Run Bot:</b> file chuno aur run karo\n"
        f"{em('sleep')} <b>Stop Bot:</b> force stop\n"
        f"{em('top')} <b>Bot Speed:</b> ping, CPU, RAM, uptime\n"
        f"{em('think')} <b>Manual Install:</b> <code>pip install package</code>\n"
        f"{em('gem')} <b>View Files:</b> file par click → options\n"
        f"{em('thought')} <b>Live Logs / Errors:</b> har file ke alag logs",
        f"{em('warn')} <b>Rules:</b>\n"
        "• Sirf <code>.py</code> files, max 10 MB\n"
        "• Files ki limit admin set karta hai\n"
        "• Admin approval zaroori",
    )


# ==================== START / HELP / EMOJIS ====================
@guarded
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        welcome_text(update.effective_user),
        reply_markup=main_kb(update.effective_user.id),
        parse_mode=HTML,
    )


@guarded
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(help_text(), reply_markup=main_kb(update.effective_user.id), parse_mode=HTML)


async def emojis_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Staff test: shows the whole premium emoji list in your original order."""
    uid = update.effective_user.id
    if not is_staff(uid):
        return
    out = []
    for i, (c, e) in enumerate(ORIGINAL, start=1):
        out.append(f'<tg-emoji emoji-id="{e}">{c}</tg-emoji>')
        if i == 22:
            out.append("  ")
        elif i == 45:
            out.append(" ")
    await update.effective_message.reply_text("".join(out), parse_mode=HTML)


@guarded
async def update_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([[ibtn("mega", "Join Update Channel", url=UPDATE_CHANNEL_URL, style="success")]])
    await update.effective_message.reply_text(
        msg(
            "mega", "UPDATE CHANNEL",
            "Hamare official update channel se judiye!\n\n"
            f"{em('ok')} New features ki updates\n"
            f"{em('ok')} Bug fixes aur improvements\n"
            f"{em('ok')} Important announcements",
            "Neeche button par click karein 👇",
        ),
        reply_markup=kb, parse_mode=HTML,
    )


# ==================== STATISTICS ====================
@guarded
async def get_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ids = all_user_ids()
    files = running = 0
    for u in ids:
        files += len(hosted_py(u))
        running += len(running_files(u))
    uid = update.effective_user.id
    text = msg(
        "star", "GLOBAL STATISTICS",
        f"{em('gem')} <b>Total Users:</b> <code>{len(ids)}</code>\n"
        f"{em('fire')} <b>Running Files:</b> <code>{running}</code>\n"
        f"{em('sleep')} <b>Stopped Files:</b> <code>{files - running}</code>\n"
        f"{em('gift')} <b>Hosted Files:</b> <code>{files}</code>\n"
        f"{em('clock')} <b>Pending Approvals:</b> <code>{len(DB['pending'])}</code>\n"
        f"{em('devil')} <b>Banned Users:</b> <code>{len(DB['banned'])}</code>",
        f"{em('crown')} <b>Admins:</b> <code>{len(DB['admins'])}</code>\n"
        f"{em('mega')} <b>Force-join Channels:</b> <code>{len(DB['channels'])}</code>\n"
        f"{em('bot')} <b>Default Limit:</b> <code>{fmt_limit(DB['default_limit'])}</code>\n"
        f"{em('one')} <b>Your Limit:</b> <code>{fmt_limit(user_limit(uid))}</code> "
        f"(used <code>{len(hosted_py(uid))}</code>)",
    )
    await update.effective_message.reply_text(text, parse_mode=HTML)


# ==================== BOT SPEED ====================
def proc_stats(pid):
    mem = cpu = up = thr = "N/A"
    if psutil:
        try:
            p = psutil.Process(pid)
            mem = f"{p.memory_info().rss / (1024 * 1024):.2f} MB"
            cpu = f"{p.cpu_percent(interval=0.05):.1f} %"
            up = format_duration(time.time() - p.create_time())
            thr = str(p.num_threads())
            return mem, cpu, up, thr
        except Exception:
            pass
    try:
        with open(f"/proc/{pid}/statm") as fh:
            pages = int(fh.read().split()[1])
        mem = f"{pages * 4096 / (1024 * 1024):.2f} MB"
    except Exception:
        pass
    return mem, cpu, up, thr


async def speed_view(context, uid):
    t0 = time.perf_counter()
    a0 = time.perf_counter()
    try:
        await context.bot.get_me()
        api_ms = (time.perf_counter() - a0) * 1000
    except Exception:
        api_ms = -1
    s0 = time.perf_counter()
    try:
        os.listdir(user_dir(uid)) if os.path.exists(user_dir(uid)) else None
    except Exception:
        pass
    sys_ms = (time.perf_counter() - s0) * 1000

    if api_ms < 0:
        rating = f"{em('no')} Unknown"
    elif api_ms < 150:
        rating = f"{em('top')} Ultra Fast"
    elif api_ms < 350:
        rating = f"{em('fire')} Fast"
    elif api_ms < 700:
        rating = f"{em('clock')} Normal"
    else:
        rating = f"{em('sleep')} Slow"

    run = running_files(uid)
    total_ms = (time.perf_counter() - t0) * 1000
    blocks = [
        f"{em('clock')} <b>Response:</b> <code>{total_ms:.1f} ms</code>\n"
        f"{em('mega')} <b>Telegram Ping:</b> <code>{api_ms:.1f} ms</code>\n"
        f"{em('gem')} <b>System Latency:</b> <code>{sys_ms:.2f} ms</code>\n"
        f"{em('star')} <b>Rating:</b> {rating}"
    ]
    if run:
        for n in run[:6]:
            pid = read_pid(uid, n)
            mem, cpu, up, thr = proc_stats(pid) if pid else ("N/A",) * 4
            blocks.append(
                f"{em('fire')} <b>{esc(n)}</b>\n"
                f"PID: <code>{pid}</code> • RAM: <code>{mem}</code>\n"
                f"CPU: <code>{cpu}</code> • Threads: <code>{thr}</code>\n"
                f"Uptime: <code>{up}</code>"
            )
    else:
        blocks.append(f"{em('sleep')} Koi file run nahi ho rahi.")
    blocks.append(f"{em('cal')} <b>Server Time:</b> <code>{datetime.now().strftime('%H:%M:%S')}</code>")
    kb = InlineKeyboardMarkup([[ibtn("spark", "Refresh Speed", "spd", "primary")]])
    return msg("top", "BOT SPEED MONITOR", *blocks), kb


@guarded
async def bot_speed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wait = await update.effective_message.reply_text(msg("clock", "Measuring speed...", ""), parse_mode=HTML)
    text, kb = await speed_view(context, update.effective_user.id)
    await wait.edit_text(text, reply_markup=kb, parse_mode=HTML)


# ==================== UPLOAD ====================
def approval_keyboard(aid):
    return InlineKeyboardMarkup([[
        ibtn("ok", "APPROVE", f"ap_ok_{aid}", "success"),
        ibtn("no", "REJECT", f"ap_no_{aid}", "danger"),
    ]])


@guarded
async def upload_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.effective_message
    user = update.effective_user
    uid = user.id
    doc = m.document
    if not doc or not doc.file_name:
        await m.reply_text(msg("no", "Invalid file", "File ka naam nahi mila."), parse_mode=HTML)
        return

    fname = normalize_py_name(doc.file_name)
    if not fname:
        await m.reply_text(
            msg("no", "Only .py files allowed!",
                f"Aapne bheja: <code>{esc(doc.file_name)}</code>\nSirf <code>.py</code> extension wali file bhejein."),
            parse_mode=HTML,
        )
        return
    if doc.file_size and doc.file_size > MAX_FILE_SIZE:
        await m.reply_text(
            msg("no", "File too large!", f"Max {MAX_FILE_SIZE // (1024 * 1024)} MB"), parse_mode=HTML)
        return
    if alive(uid, fname):
        await m.reply_text(
            msg("warn", "File is running!", f"<code>{esc(fname)}</code> chal rahi hai.\nPehle Stop karein."),
            parse_mode=HTML)
        return
    if not can_add(uid, fname):
        await m.reply_text(
            msg("warn", "LIMIT REACHED",
                f"Aapki limit <code>{fmt_limit(user_limit(uid))}</code> file(s) hai.\n"
                "Purani file delete karein ya admin se limit badhwayein."),
            parse_mode=HTML)
        return

    try:
        tg_file = await doc.get_file()
        size = doc.file_size or 0

        # ---------- staff: auto host ----------
        if is_staff(uid):
            os.makedirs(user_dir(uid), exist_ok=True)
            tmp = os.path.join(user_dir(uid), f".{fname}.tmp")
            await tg_file.download_to_drive(tmp)
            os.replace(tmp, os.path.join(user_dir(uid), fname))
            await m.reply_text(
                msg("ok", "FILE HOSTED!",
                    f"{em('gift')} <b>File:</b> <code>{esc(fname)}</code>\n"
                    f"{em('crown')} <b>Status:</b> Auto-approved (staff)",
                    "Ab Run Bot se chalayein."),
                reply_markup=InlineKeyboardMarkup([[ibtn("fire", "Run Now", f"r:{h(fname)}", "success")]]),
                parse_mode=HTML)
            return

        # ---------- normal user: pending approval ----------
        pdir = os.path.join(PENDING_DIR, str(uid))
        os.makedirs(pdir, exist_ok=True)
        aid = f"{uid}_{int(time.time())}"
        ppath = os.path.join(pdir, f"{aid}_{fname}")
        await tg_file.download_to_drive(ppath)

        DB["pending"][aid] = {
            "user_id": uid,
            "file_name": fname,
            "pending_path": ppath,
            "timestamp": time.time(),
            "user_name": user.first_name or "",
            "username": user.username or "",
        }
        save_db()

        admin_text = msg(
            "bang", "NEW UPLOAD REQUEST",
            f"{em('smile')} <b>User:</b> {esc(user.first_name)} (@{esc(user.username or 'N/A')})\n"
            f"{em('gem')} <b>User ID:</b> <code>{uid}</code>\n"
            f"{em('gift')} <b>File:</b> <code>{esc(fname)}</code>\n"
            f"{em('star')} <b>Size:</b> {size} bytes\n"
            f"{em('clock')} <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "Approve karo → file host ho jayegi.",
        )
        notified = 0
        for sid in staff_ids():
            try:
                await context.bot.send_message(sid, admin_text, reply_markup=approval_keyboard(aid), parse_mode=HTML)
                await context.bot.send_document(
                    sid, doc.file_id,
                    caption=f"📄 From <code>{uid}</code> — <code>{esc(fname)}</code>", parse_mode=HTML)
                notified += 1
            except TelegramError as e:
                print(f"[upload] cannot notify {sid}: {e}")

        if not notified:
            DB["pending"].pop(aid, None)
            save_db()
            _rm(ppath)
            await m.reply_text(
                msg("no", "Admin unreachable", "Admin ko notify nahi ho paya. Baad me try karein."),
                parse_mode=HTML)
            return

        await m.reply_text(
            msg("ok", "FILE UPLOADED!",
                f"{em('gift')} <b>File:</b> <code>{esc(fname)}</code>\n"
                f"{em('star')} <b>Size:</b> {size} bytes\n"
                f"{em('clock')} <b>Status:</b> Pending Admin Approval",
                f"{em('crown')} Admin approve karega to file host ho jayegi."),
            parse_mode=HTML)
    except Exception as e:
        await m.reply_text(msg("no", "Upload failed", esc(str(e))), parse_mode=HTML)


# ==================== APPROVE / REJECT ====================
async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, aid: str):
    cq = update.callback_query
    admin = update.effective_user
    if not is_staff(admin.id):
        await alert(update, "❌ Not authorized")
        return

    info = DB["pending"].get(aid)
    if not info:
        await cq.answer()
        await show(update, msg("warn", "Request expired", "Ye request pehle hi handle ho chuki hai."))
        return

    uid = info["user_id"]
    fname = info["file_name"]
    ppath = info["pending_path"]

    if action == "ok":
        have = set(hosted_py(uid))
        lim = user_limit(uid)
        if fname not in have and lim and len(have) >= lim:
            await alert(update, f"User ki limit ({lim}) full hai. Pehle limit badhao (Admin → User Limits).")
            return
        if alive(uid, fname):
            await alert(update, "User ki ye file abhi run ho rahi hai. Pehle stop karwao.")
            return
        os.makedirs(user_dir(uid), exist_ok=True)
        try:
            os.replace(ppath, os.path.join(user_dir(uid), fname))
        except Exception as e:
            await alert(update, f"Approve failed: {e}")
            return
        DB["pending"].pop(aid, None)
        save_db()
        await cq.answer("Approved")
        await show(update, msg(
            "ok", "APPROVED",
            f"{em('gem')} <b>User:</b> <code>{uid}</code>\n"
            f"{em('gift')} <b>File:</b> <code>{esc(fname)}</code>\n"
            f"{em('crown')} <b>By:</b> {esc(admin.first_name)}",
            "User ko notification bhej di gayi hai.",
        ))
        try:
            await context.bot.send_message(
                uid,
                msg("gift", "FILE APPROVED!",
                    f"{em('gift')} <b>File:</b> <code>{esc(fname)}</code>\n"
                    f"{em('ok')} <b>Status:</b> Approved by Admin",
                    "Ab aap Run Bot kar sakte hain!"),
                reply_markup=InlineKeyboardMarkup([[ibtn("fire", "Run Bot Now", f"r:{h(fname)}", "success")]]),
                parse_mode=HTML)
        except TelegramError:
            pass
    else:
        _rm(ppath)
        DB["pending"].pop(aid, None)
        save_db()
        await cq.answer("Rejected")
        await show(update, msg(
            "no", "REJECTED",
            f"{em('gem')} <b>User:</b> <code>{uid}</code>\n"
            f"{em('gift')} <b>File:</b> <code>{esc(fname)}</code>\n"
            f"{em('crown')} <b>By:</b> {esc(admin.first_name)}",
        ))
        try:
            await context.bot.send_message(
                uid,
                msg("no", "FILE REJECTED",
                    f"{em('gift')} <b>File:</b> <code>{esc(fname)}</code>",
                    "Aapki file admin ne reject kar di.\nDetails ke liye admin se contact karein."),
                parse_mode=HTML)
        except TelegramError:
            pass


# ==================== VIEW FILES ====================
def files_view(uid):
    files = hosted_py(uid)
    run = set(running_files(uid))
    lim = fmt_limit(user_limit(uid))
    if not files:
        return (
            msg("gem", "YOUR FILES",
                f"{em('sleep')} Abhi koi file nahi hai.\nUpload ke liye <b>Upload File</b> dabayein.",
                f"{em('bot')} Limit: <code>0</code> / <code>{lim}</code>"),
            InlineKeyboardMarkup([[ibtn("spark", "Refresh", "files", "primary")]]),
        )
    rows = []
    for n in files:
        kb_ = os.path.getsize(os.path.join(user_dir(uid), n)) / 1024
        on = n in run
        rows.append([ibtn("fire" if on else "bot", f"{n} ({kb_:.1f} KB)", f"f:{h(n)}", "success" if on else "primary")])
    rows.append([ibtn("spark", "Refresh", "files", "primary"), ibtn("devil", "Delete", "dm", "danger")])
    text = msg(
        "gem", "YOUR FILES",
        f"{em('smile')} <b>User ID:</b> <code>{uid}</code>\n"
        f"{em('gift')} <b>Files:</b> <code>{len(files)}</code> / <code>{lim}</code>\n"
        f"{em('fire')} <b>Running:</b> <code>{len(run)}</code>",
        "File par click karke options dekhein 👇",
    )
    return text, InlineKeyboardMarkup(rows)


@guarded
async def view_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, kb = files_view(update.effective_user.id)
    await show(update, text, kb)


def file_menu(uid, name):
    path = os.path.join(user_dir(uid), name)
    size = os.path.getsize(path)
    on = alive(uid, name)
    rows = []
    if on:
        rows.append([ibtn("sleep", "Stop This Bot", f"s:{h(name)}", "danger")])
    else:
        rows.append([ibtn("fire", "Run This Bot", f"r:{h(name)}", "success")])
    row = []
    if size < 50000:
        row.append(ibtn("think", "View Code", f"v:{h(name)}", "primary"))
    row.append(ibtn("devil", "Delete", f"d:{h(name)}", "danger"))
    rows.append(row)
    rows.append([
        ibtn("thought", "Logs", f"lg:{h(name)}", "primary"),
        ibtn("warn", "Errors", f"er:{h(name)}", "primary"),
    ])
    rows.append([ibtn("top", "Back", "files", "primary")])
    text = msg(
        "gift", f"FILE: {esc(name)}",
        f"{em('star')} <b>Size:</b> {size} bytes ({size / 1024:.1f} KB)\n"
        f"{em('fire') if on else em('sleep')} <b>Status:</b> {'Running' if on else 'Stopped'}",
    )
    return text, InlineKeyboardMarkup(rows)


# ==================== DELETE ====================
def delete_menu(uid):
    files = hosted_py(uid)
    if not files:
        return (msg("sleep", "Delete", "Delete karne ke liye koi file nahi."),
                InlineKeyboardMarkup([[ibtn("top", "Back", "files", "primary")]]))
    rows = [[ibtn("devil", n, f"d:{h(n)}", "danger")] for n in files]
    rows.append([ibtn("top", "Cancel", "files", "primary")])
    return msg("devil", "SELECT FILE TO DELETE", "Jis file ko delete karna hai usse chuno 👇"), InlineKeyboardMarkup(rows)


@guarded
async def show_delete_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, kb = delete_menu(update.effective_user.id)
    await show(update, text, kb)


def delete_file(uid, name):
    if alive(uid, name):
        return False, "Pehle file Stop karein."
    try:
        os.remove(os.path.join(user_dir(uid), name))
    except Exception as e:
        return False, str(e)
    for kind in ("out", "err"):
        _rm(log_path(uid, name, kind))
    _rm(pid_path(uid, name))
    return True, ""


# ==================== RUN / STOP ====================
async def run_file(update: Update, context: ContextTypes.DEFAULT_TYPE, uid, name):
    path = os.path.join(user_dir(uid), name)
    back = InlineKeyboardMarkup([[ibtn("top", "Back", "files", "primary")]])
    if not os.path.isfile(path):
        await show(update, msg("no", "File not found", esc(name)), back)
        return
    if alive(uid, name):
        await show(update, msg("warn", "Already running", f"<code>{esc(name)}</code> pehle se chal rahi hai."), back)
        return
    lim = user_limit(uid)
    if lim and len(running_files(uid)) >= lim:
        await show(update, msg(
            "warn", "LIMIT REACHED",
            f"Aap ek saath max <code>{lim}</code> file(s) chala sakte hain.\nPehle koi file Stop karein."), back)
        return

    os.makedirs(os.path.join(user_dir(uid), "logs"), exist_ok=True)
    out_p, err_p = log_path(uid, name, "out"), log_path(uid, name, "err")
    try:
        out = open(out_p, "a", encoding="utf-8")
        err = open(err_p, "a", encoding="utf-8")
        out.write(f"\n{'=' * 50}\n[{datetime.now()}] Starting {name}\n{'=' * 50}\n")
        out.flush()
        env = {k: v for k, v in os.environ.items() if k != "BOT_TOKEN"}
        proc = subprocess.Popen(
            [sys.executable, "-u", name],
            cwd=user_dir(uid),
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            start_new_session=True,
            env=env,
        )
        out.close()
        err.close()
        PROCS[(str(uid), name)] = proc
        with open(pid_path(uid, name), "w") as f:
            f.write(str(proc.pid))
        await show(update, msg(
            "fire", f"{esc(name)} STARTED!",
            f"{em('gem')} <b>PID:</b> <code>{proc.pid}</code>",
            "Logs dekhne ke liye neeche button dabayein."),
            InlineKeyboardMarkup([
                [ibtn("thought", "Live Logs", f"lg:{h(name)}", "primary")],
                [ibtn("top", "Bot Speed", "spd", "success")],
                [ibtn("top", "Back", "files", "primary")],
            ]))
    except Exception as e:
        await show(update, msg("no", "Failed to start", esc(str(e))), back)


async def stop_file(update: Update, context: ContextTypes.DEFAULT_TYPE, uid, name):
    back = InlineKeyboardMarkup([[ibtn("top", "Back", "files", "primary")]])
    if not alive(uid, name):
        await show(update, msg("warn", "Not running", f"<code>{esc(name)}</code> chal nahi rahi."), back)
        return
    pid = read_pid(uid, name)
    proc = PROCS.get((str(uid), name))
    if pid is None and proc is not None:
        pid = proc.pid
    try:
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass
        if proc is not None:
            try:
                await asyncio.to_thread(proc.wait, 3)
            except Exception:
                pass
        PROCS.pop((str(uid), name), None)
        _rm(pid_path(uid, name))
        try:
            with open(log_path(uid, name, "out"), "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now()}] {name} stopped manually\n")
        except OSError:
            pass
        await show(update, msg("sleep", f"{esc(name)} STOPPED!", "Process kill ho gaya."), back)
    except Exception as e:
        await show(update, msg("warn", "Error", esc(str(e))), back)


@guarded
async def run_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    files = hosted_py(uid)
    if not files:
        await update.effective_message.reply_text(
            msg("no", "No file found!", "Pehle <code>.py</code> file upload karein (admin approval ke baad)."),
            parse_mode=HTML)
        return
    rows = []
    for n in files:
        on = alive(uid, n)
        rows.append([ibtn("fire" if on else "bot", f"{n}  {'• running' if on else ''}".strip(),
                          f"s:{h(n)}" if on else f"r:{h(n)}", "danger" if on else "success")])
    rows.append([ibtn("top", "Cancel", "cancel", "primary")])
    await update.effective_message.reply_text(
        msg("bot", "SELECT FILE TO RUN", "File chuno (running file par click = stop) 👇"),
        reply_markup=InlineKeyboardMarkup(rows), parse_mode=HTML)


@guarded
async def stop_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    run = running_files(uid)
    if not run:
        await update.effective_message.reply_text(msg("no", "No file is running!", ""), parse_mode=HTML)
        return
    rows = [[ibtn("sleep", f"Stop {n}", f"s:{h(n)}", "danger")] for n in run]
    rows.append([ibtn("top", "Cancel", "cancel", "primary")])
    await update.effective_message.reply_text(
        msg("sleep", "RUNNING FILES", "Stop karne ke liye file chuno 👇"),
        reply_markup=InlineKeyboardMarkup(rows), parse_mode=HTML)


# ==================== LOGS ====================
def log_view(uid, name, kind):
    path = log_path(uid, name, kind)
    on = alive(uid, name)
    data = tail(path, 3000) if os.path.exists(path) else ""
    cb = f"lg:{h(name)}" if kind == "out" else f"er:{h(name)}"
    title, key = ("LIVE LOGS", "thought") if kind == "out" else ("ERROR LOG", "warn")
    if not data.strip():
        body = "Log khali hai." if kind == "out" else "Koi error nahi mila 🎉"
        data_html = ""
    else:
        data_html = f"\n<pre>{esc(data)}</pre>"
    head = msg(
        key, title,
        f"{em('gift')} <b>File:</b> <code>{esc(name)}</code>\n"
        f"{em('fire') if on else em('sleep')} <b>Status:</b> {'Running' if on else 'Stopped'}"
        + ("" if data.strip() else f"\n\n{body}"),
    )
    kb = InlineKeyboardMarkup([
        [ibtn("spark", "Refresh", cb, "primary")],
        [ibtn("top", "Back", f"f:{h(name)}", "primary")],
    ])
    return head + data_html, kb


async def logs_entry(update: Update, kind: str):
    uid = update.effective_user.id
    names = [n for n in hosted_py(uid) if os.path.exists(log_path(uid, n, kind))]
    if not names:
        text = "Abhi koi log nahi.\nPehle apni file run karein." if kind == "out" else "Koi error log nahi mila."
        await update.effective_message.reply_text(
            msg("sleep" if kind == "out" else "ok", "NO LOGS" if kind == "out" else "NO ERRORS", text),
            parse_mode=HTML)
        return
    if len(names) == 1:
        text, kb = log_view(uid, names[0], kind)
        await update.effective_message.reply_text(text, reply_markup=kb, parse_mode=HTML)
        return
    pre = "lg" if kind == "out" else "er"
    rows = [[ibtn("thought" if kind == "out" else "warn", n, f"{pre}:{h(n)}", "primary")] for n in names]
    await update.effective_message.reply_text(
        msg("thought", "SELECT FILE", "Kis file ke logs dekhne hain?"),
        reply_markup=InlineKeyboardMarkup(rows), parse_mode=HTML)


@guarded
async def live_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await logs_entry(update, "out")


@guarded
async def view_errors(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await logs_entry(update, "err")


# ==================== MANUAL INSTALL ====================
@guarded
async def manual_install_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting_install"] = True
    await update.effective_message.reply_text(
        msg("think", "MANUAL PACKAGE INSTALL",
            "Command bhejein:\n"
            "• <code>pip install package_name</code>\n"
            "• <code>pip install requests aiohttp==3.9.5</code>",
            f"{em('warn')} <b>Security Rules:</b>\n"
            "• Sirf simple <code>pip install</code> allowed\n"
            "• URL / path / dangerous options blocked\n"
            "• Shell operators blocked\n\n"
            "Cancel ke liye /cancel"),
        parse_mode=HTML)


async def handle_manual_install(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    uid = update.effective_user.id
    command = update.effective_message.text.strip()
    args = parse_pip(command)
    if args is None:
        await update.effective_message.reply_text(
            msg("no", "Invalid or unsafe command!",
                "✅ Allowed:\n<code>pip install package_name</code>\n<code>pip install pkg1 pkg2==1.0</code>\n\n"
                "❌ Blocked: shell operators, URLs, dangerous options"),
            parse_mode=HTML)
        return True

    context.user_data["awaiting_install"] = False
    os.makedirs(user_dir(uid), exist_ok=True)
    await update.effective_message.reply_text(
        msg("clock", "Installing...", f"<code>{esc(command)}</code>\nPlease wait..."), parse_mode=HTML)
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, "-m", "pip", "install", *args],
            cwd=user_dir(uid), capture_output=True, text=True, timeout=300,
        )
        with open(os.path.join(user_dir(uid), "install.log"), "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 50}\nCommand: {command}\nReturn: {result.returncode}\n"
                    f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}\n{'=' * 50}\n")
        if result.returncode == 0:
            await update.effective_message.reply_text(
                msg("ok", "Installation successful!", "Package install ho gaya.")
                + f"\n<pre>{esc(result.stdout[-1500:])}</pre>", parse_mode=HTML)
        else:
            err = result.stderr or result.stdout
            await update.effective_message.reply_text(
                msg("no", "Installation failed!", "Error neeche hai.") + f"\n<pre>{esc(err[-1500:])}</pre>",
                parse_mode=HTML)
    except subprocess.TimeoutExpired:
        await update.effective_message.reply_text(msg("clock", "Timeout!", "Install 5 minute me complete nahi hua."), parse_mode=HTML)
    except Exception as e:
        await update.effective_message.reply_text(msg("no", "Error", esc(str(e))), parse_mode=HTML)
    return True


# ==================== ADMIN PANEL ====================
def admin_kb(uid):
    rows = [
        [ibtn("mega", "Broadcast", "adm_broadcast", "primary")],
        [ibtn("gem", "All Users", "adm_users", "primary"), ibtn("clock", "Pending", "adm_pending", "primary")],
        [ibtn("devil", "Ban User", "adm_ban", "danger"), ibtn("ok", "Unban User", "adm_unban", "success")],
        [ibtn("star", "User Limits", "adm_limits", "primary"), ibtn("top", "Force Join", "adm_channels", "primary")],
    ]
    if is_owner(uid):
        rows.append([ibtn("crown", "Add Admin", "adm_addadm", "success"), ibtn("no", "Remove Admin", "adm_rmadm", "danger")])
    rows.append([ibtn("spark", "Refresh", "adm_refresh", "primary")])
    return InlineKeyboardMarkup(rows)


def cancel_kb():
    return InlineKeyboardMarkup([[ibtn("no", "Cancel", "adm_cancel", "danger")]])


def back_kb():
    return InlineKeyboardMarkup([[ibtn("top", "Back", "adm_refresh", "primary")]])


def admin_home_text(uid) -> str:
    return msg(
        "crown", "ADMIN PANEL",
        f"{em('gem')} <b>Users:</b> <code>{len(all_user_ids())}</code>   "
        f"{em('clock')} <b>Pending:</b> <code>{len(DB['pending'])}</code>\n"
        f"{em('devil')} <b>Banned:</b> <code>{len(DB['banned'])}</code>   "
        f"{em('crown')} <b>Admins:</b> <code>{len(DB['admins'])}</code>\n"
        f"{em('mega')} <b>Force-join:</b> <code>{len(DB['channels'])}</code>   "
        f"{em('star')} <b>Default limit:</b> <code>{fmt_limit(DB['default_limit'])}</code>",
        "Option chuno 👇\n<code>/cancel</code> se koi bhi action cancel hota hai.",
    )


ADMIN_STATE = {}  # uid -> {"action": str}


@guarded
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_staff(uid):
        await update.effective_message.reply_text(msg("no", "Not authorized!", ""), parse_mode=HTML)
        return
    ADMIN_STATE.pop(uid, None)
    await update.effective_message.reply_text(admin_home_text(uid), reply_markup=admin_kb(uid), parse_mode=HTML)


def users_view():
    lines = []
    for u in all_user_ids()[:40]:
        info = DB["users"].get(str(u), {})
        nm = esc(info.get("name") or "—")
        run = len(running_files(u))
        flag = "🚫" if u in DB["banned"] else ""
        role = "👑" if is_owner(u) else ("🛡" if is_admin(u) else "")
        lim = fmt_limit(user_limit(u))
        lines.append(f"{'🟢' if run else '🔴'}{flag}{role} <code>{u}</code> {nm} — {len(hosted_py(u))}/{lim} files")
    total = len(all_user_ids())
    extra = f"\n\n... +{total - 40} more" if total > 40 else ""
    return msg("gem", f"ALL USERS ({total})", "\n".join(lines) + extra if lines else "No users yet."), back_kb()


def pending_view():
    if not DB["pending"]:
        return msg("ok", "PENDING APPROVALS", "Koi pending request nahi."), back_kb()
    rows = []
    lines = []
    for aid, info in list(DB["pending"].items())[:15]:
        lines.append(
            f"• <code>{info['user_id']}</code> — <code>{esc(info['file_name'])}</code> "
            f"({datetime.fromtimestamp(info['timestamp']).strftime('%H:%M')})")
        rows.append([
            ibtn("ok", f"Approve {info['file_name'][:16]}", f"ap_ok_{aid}", "success"),
            ibtn("no", "Reject", f"ap_no_{aid}", "danger"),
        ])
    rows.append([ibtn("top", "Back", "adm_refresh", "primary")])
    return msg("clock", "PENDING APPROVALS", "\n".join(lines)), InlineKeyboardMarkup(rows)


def limits_view():
    ov = DB["user_limits"]
    lines = "\n".join(f"• <code>{k}</code> → <code>{fmt_limit(v)}</code>" for k, v in list(ov.items())[:25]) or "— koi override nahi —"
    text = msg(
        "star", "FILE LIMITS",
        f"{em('bot')} <b>Default limit (har user):</b> <code>{fmt_limit(DB['default_limit'])}</code>\n"
        f"{em('crown')} <b>Owner:</b> Unlimited ♾",
        f"<b>Per-user overrides:</b>\n{lines}",
    )
    kb = InlineKeyboardMarkup([
        [ibtn("bot", "Set Default Limit", "adm_deflimit", "primary")],
        [ibtn("gem", "Set User Limit", "adm_userlimit", "success")],
        [ibtn("top", "Back", "adm_refresh", "primary")],
    ])
    return text, kb


def channels_view():
    rows = []
    lines = []
    for i, c in enumerate(DB["channels"]):
        lines.append(f"{i + 1}. <b>{esc(c['title'])}</b> — <code>{c['id']}</code>")
        rows.append([ibtn("no", f"Remove {c['title'][:24]}", f"adm_chdel_{i}", "danger")])
    rows.append([ibtn("ok", "Add Channel", "adm_addch", "success")])
    rows.append([ibtn("top", "Back", "adm_refresh", "primary")])
    body = "\n".join(lines) if lines else "Koi force-join channel set nahi hai."
    text = msg(
        "mega", "FORCE JOIN",
        body,
        f"{em('warn')} Pehle bot ko channel me <b>Admin</b> banao, phir <b>Add Channel</b> dabao.\n"
        "Users ko in channels ko join karna hoga tabhi bot use kar payenge.",
    )
    return text, InlineKeyboardMarkup(rows)


def admins_remove_view():
    if not DB["admins"]:
        return msg("sleep", "REMOVE ADMIN", "Koi admin nahi hai."), back_kb()
    rows = []
    for a in DB["admins"]:
        info = DB["users"].get(str(a), {})
        label = f"{info.get('name') or 'Admin'} ({a})"
        rows.append([ibtn("no", label[:40], f"adm_rmadm_{a}", "danger")])
    rows.append([ibtn("top", "Back", "adm_refresh", "primary")])
    return msg("no", "REMOVE ADMIN", "Jisko hatana hai usse chuno 👇"), InlineKeyboardMarkup(rows)


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    cq = update.callback_query
    uid = update.effective_user.id
    if not is_staff(uid):
        await alert(update, "❌ Not authorized")
        return
    owner_only = data in ("adm_addadm", "adm_rmadm") or data.startswith("adm_rmadm_")
    if owner_only and not is_owner(uid):
        await alert(update, "❌ Sirf owner ye kar sakta hai")
        return
    await cq.answer()

    if data in ("adm_refresh", "adm_cancel"):
        ADMIN_STATE.pop(uid, None)
        await show(update, admin_home_text(uid), admin_kb(uid))
    elif data == "adm_users":
        t, k = users_view()
        await show(update, t, k)
    elif data == "adm_pending":
        t, k = pending_view()
        await show(update, t, k)
    elif data == "adm_limits":
        t, k = limits_view()
        await show(update, t, k)
    elif data == "adm_channels":
        t, k = channels_view()
        await show(update, t, k)
    elif data == "adm_rmadm":
        t, k = admins_remove_view()
        await show(update, t, k)
    elif data == "adm_broadcast":
        ADMIN_STATE[uid] = {"action": "broadcast"}
        await show(update, msg("mega", "BROADCAST MODE",
                               "Jo message sabhi users ko bhejna hai wo bhejein.\nHTML formatting supported."),
                   cancel_kb())
    elif data == "adm_ban":
        ADMIN_STATE[uid] = {"action": "ban"}
        await show(update, msg("devil", "BAN USER", "Jis user ko ban karna hai uski ID bhejein:"), cancel_kb())
    elif data == "adm_unban":
        if not DB["banned"]:
            await show(update, msg("ok", "UNBAN USER", "Koi banned user nahi."), back_kb())
            return
        ADMIN_STATE[uid] = {"action": "unban"}
        lst = "\n".join(f"• <code>{b}</code>" for b in DB["banned"])
        await show(update, msg("ok", "UNBAN USER", f"Banned users:\n{lst}", "Unban karne wali ID bhejein:"), cancel_kb())
    elif data == "adm_addadm":
        ADMIN_STATE[uid] = {"action": "add_admin"}
        await show(update, msg("crown", "ADD ADMIN", "Naye admin ki Telegram User ID bhejein:"), cancel_kb())
    elif data.startswith("adm_rmadm_"):
        target = int(data[len("adm_rmadm_"):])
        if target in DB["admins"]:
            DB["admins"].remove(target)
            save_db()
            try:
                await context.bot.send_message(
                    target, msg("no", "ADMIN REMOVED", "Aap ab admin nahi hain."),
                    reply_markup=main_kb(target), parse_mode=HTML)
            except TelegramError:
                pass
        t, k = admins_remove_view()
        await show(update, t, k)
    elif data == "adm_deflimit":
        ADMIN_STATE[uid] = {"action": "def_limit"}
        await show(update, msg(
            "star", "SET DEFAULT LIMIT",
            f"Abhi default: <code>{fmt_limit(DB['default_limit'])}</code>\n\n"
            "Har user kitni files host kar sakta hai? Number bhejein (jaise <code>2</code>, <code>5</code>).\n"
            "<code>0</code> = unlimited."), cancel_kb())
    elif data == "adm_userlimit":
        ADMIN_STATE[uid] = {"action": "user_limit"}
        await show(update, msg(
            "gem", "SET USER LIMIT",
            "Format: <code>USER_ID LIMIT</code>\n\n"
            "• <code>123456789 3</code> → us user ko 3 files\n"
            "• <code>123456789 unlimited</code> → unlimited\n"
            "• <code>123456789 reset</code> → default par wapas"), cancel_kb())
    elif data == "adm_addch":
        ADMIN_STATE[uid] = {"action": "add_channel"}
        await show(update, msg(
            "mega", "ADD CHANNEL",
            "Channel ka <code>@username</code>, <code>t.me/username</code> ya ID (<code>-100...</code>) bhejein.",
            f"{em('warn')} Bot pehle us channel me <b>Admin</b> hona chahiye.\n"
            "Private channel ke liye <code>-100...</code> ID bhejein."), cancel_kb())
    elif data.startswith("adm_chdel_"):
        idx = int(data[len("adm_chdel_"):])
        if 0 <= idx < len(DB["channels"]):
            DB["channels"].pop(idx)
            save_db()
            JOIN_OK.clear()
        t, k = channels_view()
        await show(update, t, k)


# ---------- admin text input ----------
def parse_chat_ref(t: str):
    t = t.strip()
    m = re.match(r"^(?:https?://)?t\.me/([A-Za-z0-9_]{4,})/?$", t)
    if m:
        return "@" + m.group(1)
    if re.match(r"^@[A-Za-z0-9_]{4,}$", t):
        return t
    if re.match(r"^-?\d{5,}$", t):
        return int(t)
    return None


async def handle_admin_state(update: Update, context: ContextTypes.DEFAULT_TYPE, st: dict) -> bool:
    uid = update.effective_user.id
    m = update.effective_message
    text = m.text.strip()
    action = st["action"]
    ADMIN_STATE.pop(uid, None)

    async def done(t, kb=None):
        await m.reply_text(t, reply_markup=kb or admin_kb(uid), parse_mode=HTML)

    if action == "broadcast":
        body = f"{em('mega')} <b>ANNOUNCEMENT</b>\n" + q(text)
        sent = failed = 0
        for u in all_user_ids():
            try:
                try:
                    await context.bot.send_message(u, body, parse_mode=HTML)
                except BadRequest:  # admin wrote invalid HTML -> send escaped
                    await context.bot.send_message(
                        u, f"{em('mega')} <b>ANNOUNCEMENT</b>\n" + q(esc(text)), parse_mode=HTML)
                sent += 1
            except TelegramError:
                failed += 1
            await asyncio.sleep(0.05)
        await done(msg("ok", "BROADCAST COMPLETE", f"{em('ok')} Sent: <code>{sent}</code>\n{em('no')} Failed: <code>{failed}</code>"))
        return True

    if action in ("ban", "unban", "add_admin"):
        if not re.fullmatch(r"\d{5,}", text):
            await done(msg("no", "Invalid user ID!", "Sirf number (Telegram ID) bhejein."))
            return True
        target = int(text)

        if action == "ban":
            if is_staff(target):
                await done(msg("no", "Cannot ban", "Owner/Admin ko ban nahi kar sakte."))
                return True
            if target not in DB["banned"]:
                DB["banned"].append(target)
                save_db()
            await done(msg("devil", "USER BANNED", f"<code>{target}</code> ban ho gaya."))
            try:
                await context.bot.send_message(target, msg("devil", "YOU ARE BANNED", "Aapko admin ne ban kiya hai.\nContact admin."), parse_mode=HTML)
            except TelegramError:
                pass
        elif action == "unban":
            if target in DB["banned"]:
                DB["banned"].remove(target)
                save_db()
                await done(msg("ok", "USER UNBANNED", f"<code>{target}</code> unban ho gaya."))
                try:
                    await context.bot.send_message(target, msg("ok", "YOU ARE UNBANNED", "Ab aap bot use kar sakte hain."), parse_mode=HTML)
                except TelegramError:
                    pass
            else:
                await done(msg("no", "Not banned", f"<code>{target}</code> banned nahi hai."))
        else:  # add_admin
            if is_owner(target):
                await done(msg("no", "Already owner", "Ye owner hai."))
            elif target in DB["admins"]:
                await done(msg("warn", "Already admin", f"<code>{target}</code> pehle se admin hai."))
            else:
                DB["admins"].append(target)
                if target in DB["banned"]:
                    DB["banned"].remove(target)
                save_db()
                await done(msg("crown", "ADMIN ADDED", f"<code>{target}</code> ab admin hai."))
                try:
                    await context.bot.send_message(
                        target,
                        msg("crown", "YOU ARE NOW ADMIN!", "Aapko admin banaya gaya hai.\n/admin se panel kholein."),
                        reply_markup=main_kb(target), parse_mode=HTML)
                except TelegramError:
                    pass
        return True

    if action == "def_limit":
        if not re.fullmatch(r"\d{1,4}", text):
            await done(msg("no", "Invalid number", "0 ya usse bada number bhejein."))
            return True
        DB["default_limit"] = int(text)
        save_db()
        await done(msg("star", "DEFAULT LIMIT UPDATED", f"Ab har user max <code>{fmt_limit(DB['default_limit'])}</code> file(s) host kar sakta hai."))
        return True

    if action == "user_limit":
        parts = text.split()
        if len(parts) != 2 or not parts[0].isdigit():
            await done(msg("no", "Invalid format", "Format: <code>USER_ID LIMIT</code>"))
            return True
        target, val = int(parts[0]), parts[1].lower()
        if is_owner(target):
            await done(msg("crown", "Owner", "Owner ki limit hamesha unlimited hai."))
            return True
        if val in ("reset", "default"):
            DB["user_limits"].pop(str(target), None)
            res = f"default (<code>{fmt_limit(DB['default_limit'])}</code>)"
        elif val in ("unlimited", "0"):
            DB["user_limits"][str(target)] = 0
            res = "<code>Unlimited ♾</code>"
        elif val.isdigit():
            DB["user_limits"][str(target)] = int(val)
            res = f"<code>{int(val)}</code>"
        else:
            await done(msg("no", "Invalid limit", "Number, <code>unlimited</code> ya <code>reset</code> bhejein."))
            return True
        save_db()
        await done(msg("star", "USER LIMIT UPDATED", f"<code>{target}</code> ki limit: {res}"))
        try:
            await context.bot.send_message(
                target, msg("star", "LIMIT UPDATED", f"Aapki file limit ab: {res}"), parse_mode=HTML)
        except TelegramError:
            pass
        return True

    if action == "add_channel":
        ref = parse_chat_ref(text)
        if ref is None:
            await done(msg("no", "Invalid channel",
                           "<code>@username</code>, <code>t.me/username</code> ya <code>-100...</code> ID bhejein.\n"
                           "Private invite link (t.me/+...) se ID nahi mil sakti."))
            return True
        try:
            chat = await context.bot.get_chat(ref)
        except TelegramError as e:
            await done(msg("no", "Channel not found", f"{esc(str(e))}\nBot us channel me admin hai?"))
            return True
        try:
            me = await context.bot.get_chat_member(chat.id, context.bot.id)
            is_adm = me.status in ("administrator", "creator")
        except TelegramError:
            is_adm = False
        if not is_adm:
            await done(msg("warn", "Bot is not admin",
                           f"<b>{esc(chat.title)}</b> me pehle bot ko <b>Admin</b> banao, phir dobara add karo."))
            return True
        if any(c["id"] == chat.id for c in DB["channels"]):
            await done(msg("warn", "Already added", esc(chat.title)))
            return True
        link = f"https://t.me/{chat.username}" if chat.username else None
        if not link:
            try:
                link = await context.bot.export_chat_invite_link(chat.id)
            except TelegramError:
                link = None
        DB["channels"].append({"id": chat.id, "title": chat.title or str(chat.id), "link": link})
        save_db()
        JOIN_OK.clear()
        extra = "" if link else "\n\n⚠️ Invite link nahi ban saka (bot ko 'Invite Users' permission do)."
        await done(msg("mega", "CHANNEL ADDED",
                       f"<b>{esc(chat.title)}</b> (<code>{chat.id}</code>)\nAb users ko ye channel join karna hoga.{extra}"))
        return True

    return False


# ==================== BROADCAST / PENDING COMMANDS ====================
async def admin_broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_staff(uid):
        return
    if not context.args:
        await update.effective_message.reply_text(
            msg("mega", "BROADCAST", "Usage: <code>/broadcast Your message</code>\nYa Admin Panel → Broadcast"),
            parse_mode=HTML)
        return
    text = " ".join(context.args)
    body = f"{em('mega')} <b>ANNOUNCEMENT</b>\n" + q(esc(text))
    sent = failed = 0
    for u in all_user_ids():
        try:
            await context.bot.send_message(u, body, parse_mode=HTML)
            sent += 1
        except TelegramError:
            failed += 1
        await asyncio.sleep(0.05)
    await update.effective_message.reply_text(
        msg("ok", "BROADCAST DONE", f"Sent: <code>{sent}</code>\nFailed: <code>{failed}</code>"), parse_mode=HTML)


async def admin_pending_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_staff(update.effective_user.id):
        return
    t, k = pending_view()
    await update.effective_message.reply_text(t, reply_markup=k, parse_mode=HTML)


# ==================== CANCEL ====================
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cleared = False
    if uid in ADMIN_STATE:
        ADMIN_STATE.pop(uid, None)
        cleared = True
    if context.user_data.get("awaiting_install"):
        context.user_data["awaiting_install"] = False
        cleared = True
    if cleared:
        kb = admin_kb(uid) if is_staff(uid) else None
        await update.effective_message.reply_text(msg("no", "Cancelled", ""), reply_markup=kb, parse_mode=HTML)
    else:
        await update.effective_message.reply_text(msg("think", "Nothing to cancel", ""), parse_mode=HTML)


# ==================== CALLBACK ROUTER ====================
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq = update.callback_query
    data = cq.data or ""
    uid = update.effective_user.id

    if data.startswith("adm_"):
        await admin_callback(update, context, data)
        return

    m = re.match(r"^ap_(ok|no)_(.+)$", data)
    if m:
        await handle_approval(update, context, m.group(1), m.group(2))
        return

    if data == "noop":
        await cq.answer()
        return

    if data == "verify_join":
        JOIN_OK.pop(uid, None)
        track_user(update.effective_user)
        miss = [] if is_staff(uid) else await missing_channels(context.bot, uid)
        if miss:
            await cq.answer("❌ Abhi tak join nahi kiya!", show_alert=True)
            return
        await cq.answer("✅ Verified!")
        try:
            await cq.message.delete()
        except TelegramError:
            pass
        await context.bot.send_message(
            uid, welcome_text(update.effective_user), reply_markup=main_kb(uid), parse_mode=HTML)
        return

    if not await access_ok(update, context):
        return
    await cq.answer()

    if data == "cancel":
        await show(update, msg("no", "Cancelled", ""))
    elif data == "files":
        t, k = files_view(uid)
        await show(update, t, k)
    elif data == "dm":
        t, k = delete_menu(uid)
        await show(update, t, k)
    elif data == "spd":
        t, k = await speed_view(context, uid)
        await show(update, t, k)
    elif re.match(r"^(f|r|s|v|d|lg|er):[0-9a-f]{10}$", data):
        kind, hh = data.split(":")
        name = resolve(uid, hh)
        if not name:
            await show(update, msg("no", "File not found!", "File delete ho chuki hai ya mili nahi."),
                       InlineKeyboardMarkup([[ibtn("top", "Back", "files", "primary")]]))
            return
        if kind == "f":
            t, k = file_menu(uid, name)
            await show(update, t, k)
        elif kind == "r":
            await run_file(update, context, uid, name)
        elif kind == "s":
            await stop_file(update, context, uid, name)
        elif kind == "v":
            try:
                with open(os.path.join(user_dir(uid), name), "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(2500)
            except Exception:
                content = "Preview nahi ho saka."
            await show(update,
                       msg("think", esc(name), "Pehle 2500 characters:") + f"\n<pre>{esc(content)}</pre>",
                       InlineKeyboardMarkup([[ibtn("top", "Back", f"f:{hh}", "primary")]]))
        elif kind == "d":
            ok, err = delete_file(uid, name)
            if ok:
                await show(update, msg("ok", "DELETED", f"<code>{esc(name)}</code> delete ho gayi."),
                           InlineKeyboardMarkup([
                               [ibtn("devil", "Delete Another", "dm", "danger")],
                               [ibtn("top", "Back", "files", "primary")]]))
            else:
                await show(update, msg("warn", "Cannot delete", esc(err)),
                           InlineKeyboardMarkup([[ibtn("top", "Back", f"f:{hh}", "primary")]]))
        elif kind == "lg":
            t, k = log_view(uid, name, "out")
            await show(update, t, k)
        elif kind == "er":
            t, k = log_view(uid, name, "err")
            await show(update, t, k)


# ==================== TEXT ROUTER ====================
async def upload_info(update, context):
    uid = update.effective_user.id
    await update.effective_message.reply_text(
        msg("gift", "UPLOAD INSTRUCTIONS",
            f"{em('check')} Koi bhi <code>.py</code> file document ki tarah bhejein\n"
            f"{em('check')} Max <code>10 MB</code>\n"
            f"{em('check')} Admin approval required\n"
            f"{em('check')} Aapki limit: <code>{len(hosted_py(uid))}</code> / <code>{fmt_limit(user_limit(uid))}</code>"),
        parse_mode=HTML)


async def open_admin_panel(update, context):
    await admin_panel(update, context)


ROUTES = {
    "upload file": upload_info,
    "view files": view_files,
    "run bot": run_bot,
    "stop bot": stop_bot,
    "bot speed": bot_speed,
    "manual install": manual_install_prompt,
    "delete files": show_delete_menu,
    "live logs": live_logs,
    "view errors": view_errors,
    "update channel": update_channel,
    "statistics": get_statistics,
    "admin panel": open_admin_panel,
}


@guarded
async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.effective_message
    if not m or not m.text:
        return
    uid = update.effective_user.id
    label = norm(m.text)

    if is_staff(uid) and uid in ADMIN_STATE:
        if await handle_admin_state(update, context, ADMIN_STATE[uid]):
            return

    if context.user_data.get("awaiting_install"):
        if label in ROUTES:
            context.user_data["awaiting_install"] = False
        else:
            await handle_manual_install(update, context)
            return

    handler = ROUTES.get(label)
    if handler:
        await handler(update, context)
    else:
        await m.reply_text(
            msg("think", "Unknown command", "Neeche ke buttons use karein."),
            reply_markup=main_kb(uid), parse_mode=HTML)


# ==================== ERRORS / STARTUP ====================
async def on_error(update, context):
    print(f"[error] {context.error!r}")


async def post_init(app):
    """Self-test: if premium emoji buttons are rejected, fall back to plain emojis."""
    global PREMIUM
    try:
        await app.bot.send_message(
            OWNER_ID,
            f"{em('ok')} <b>Panel online</b> — premium emoji: <code>{'ON' if PREMIUM else 'OFF'}</code>",
            parse_mode=HTML,
            reply_markup=InlineKeyboardMarkup([[ibtn("bot", "Panel Ready", "noop", "success")]]),
        )
    except BadRequest as e:
        if PREMIUM:
            PREMIUM = False
            print(f"[premium] rejected by Telegram ({e}) -> falling back to plain emojis")
            try:
                await app.bot.send_message(
                    OWNER_ID,
                    f"{em('warn')} <b>Premium emoji buttons rejected</b> — plain emojis use ho rahe hain.\n"
                    f"<code>{esc(str(e))}</code>",
                    parse_mode=HTML)
            except TelegramError:
                pass
    except TelegramError as e:
        print(f"[startup] owner not reachable yet: {e}")


def main():
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("broadcast", admin_broadcast_cmd))
    app.add_handler(CommandHandler("pending", admin_pending_cmd))
    app.add_handler(CommandHandler("emojis", emojis_command))

    app.add_handler(MessageHandler(filters.Document.ALL, upload_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, router))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_error_handler(on_error)

    print("=" * 60)
    print("ADVANCED HOSTING PANEL — v3")
    print("=" * 60)
    print(f"Owner: {OWNER_ID} | Admins: {len(DB['admins'])} | Channels: {len(DB['channels'])}")
    print(f"Default limit: {fmt_limit(DB['default_limit'])} | Premium emoji: {PREMIUM}")
    print(f"Base: {os.path.abspath(BASE_DIR)}")
    print("=" * 60)
    app.run_polling()


if __name__ == "__main__":
    main()
