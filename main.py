import requests, random, time, re
from faker import Faker
import sys
import time
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler, CallbackQueryHandler

TOKEN = "8720553369:AAHjHJPaXscx_AatAWB3eDr3RBzNvFBNBRk"
CHANNEL_ID = -1004483412145
CHANNEL_LINK = "https://t.me/faaaaaahrandi"

fake = Faker()
USERNAME = 1

# ========= CYBER STARTUP EFFECTS (COSMETIC ONLY) =========
import sys, random, time

GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
DIM = "\033[2m"
RESET = "\033[0m"

def type_text(text, delay=0.015, color=GREEN):
    for c in text:
        sys.stdout.write(color + c + RESET)
        sys.stdout.flush()
        time.sleep(delay)
    print()

def matrix_rain(duration=2.5, width=64):
    end = time.time() + duration
    while time.time() < end:
        line = "".join(random.choice("01░▒▓") for _ in range(width))
        print(GREEN + line + RESET)
        time.sleep(0.05)

def tor_proxy_chain():
    type_text("🌐 Initializing network stack...", 0.02, CYAN)
    time.sleep(0.4)
    hops = [
        "127.0.0.1  ➜  LOCALHOST",
        "10.8.0.1   ➜  VPN GATEWAY",
        "172.16.5.23➜  PROXY NODE",
        "185.220.101.1 ➜ TOR ENTRY",
        "185.220.101.12➜ TOR MIDDLE",
        "185.220.101.44➜ TOR EXIT"
    ]
    for h in hops:
        type_text(f"🔁 Routing via {h}", 0.02, YELLOW)
        time.sleep(0.25)
    type_text("✅ Anonymous route established", 0.02, GREEN)

def live_scan_logs(lines=14):
    scans = [
        "Scanning open ports .......... OK",
        "Checking rate limits ......... BYPASSED",
        "Fingerprinting endpoints .... MATCHED",
        "Rotating user-agents ......... DONE",
        "Proxy health check ........... STABLE",
        "TLS handshake ................ VERIFIED",
        "Anti-bot heuristics .......... EVADED",
        "Session entropy .............. HIGH",
        "Queueing payloads ............ READY",
        "Throttle control ............. ADAPTIVE",
        "I/O buffers .................. FLUSHED",
        "Integrity check .............. PASSED",
        "Latency ...................... LOW",
        "Engine status ................ ARMED"
    ]
    for i in range(min(lines, len(scans))):
        type_text(f"[SCAN] {scans[i]}", 0.02, DIM + GREEN)
        time.sleep(0.12)

def hacker_startup():
    print("\033c", end="")  # clear screen

    # Matrix intro
    matrix_rain(2.0)

    print(GREEN + "="*66 + RESET)
    type_text("🤖 TELEGRAM REPORT BOT  |  ROOT ACCESS ENABLED", 0.01, CYAN)
    print(GREEN + "="*66 + RESET)
    print()

    type_text("👁 ACCESS LEVEL   : ROOT", 0.01, GREEN)
    type_text("🛡 MODE           : STEALTH", 0.01, GREEN)
    type_text("🔐 ENCRYPTION    : AES-256", 0.01, GREEN)
    type_text("🌐 NETWORK       : ANONYMOUS", 0.01, GREEN)
    print()

    tor_proxy_chain()
    print()
    live_scan_logs()
    print()

    type_text(f"📡 CHANNEL ID     : {CHANNEL_ID}", 0.01, CYAN)
    type_text(f"🔗 CHANNEL LINK   : {CHANNEL_LINK}", 0.01, CYAN)
    print()

    type_text("⚠ UNAUTHORIZED ACCESS WILL BE LOGGED & TRACED", 0.01, RED)
    print(GREEN + "="*66 + RESET)
    time.sleep(0.6)

# ================= CORE FUNCTIONS (SAME) =================
def load_reports():
    try:
        with open("report.txt", "r", encoding="utf-8") as file:
            return [line.strip() for line in file if line.strip()]
    except:
        return [
            "This user @username is violating Telegram rules.",
            "@username is sending spam messages.",
            "This account @username is impersonating someone."
        ]

def is_valid_username(username):
    try:
        response = requests.get(f"https://t.me/{username}", timeout=5)
        return "tgme_page_title" in response.text
    except:
        return False

def generate_data(username, message):
    name = fake.name()
    email = fake.email().split("@")[0] + "@" + random.choice(
        ["gmail.com", "yahoo.com", "outlook.com", "rediffmail.com"]
    )
    number = '7' + ''.join([str(random.randint(0, 9)) for _ in range(9)])
    final_msg = message.replace("@username", f"@{username}")
    return {
        "message": final_msg,
        "legal_name": name,
        "email": email,
        "phone": number,
        "setln": ""
    }, name, email, number, final_msg

def load_proxies():
    try:
        with open("STAR.txt", "r") as f:
            return [line.strip() for line in f if line.strip()]
    except:
        return []

def send_data(data, proxy=None):
    headers = {
        "Host": "telegram.org",
        "origin": "https://telegram.org",
        "content-type": "application/x-www-form-urlencoded",
        "user-agent": "Mozilla/5.0",
        "referer": "https://telegram.org/support"
    }
    try:
        proxies = None
        if proxy:
            proxies = {
                'http': f'socks4://{proxy}',
                'https': f'socks4://{proxy}'
            }
        res = requests.post("https://telegram.org/support", data=data, headers=headers, proxies=proxies, timeout=10)
        success = "Thank you" in res.text or res.status_code == 200
        return success, proxy if proxy else "direct"
    except:
        return False, proxy if proxy else "direct"

# ================= SUBSCRIPTION CHECK (SAME) =================
def check_subscription(update, context):
    user_id = update.effective_user.id
    try:
        chat_member = context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except:
        return True

# ================= BOT COMMANDS =================
def start(update: Update, context: CallbackContext):
    print("\n" + "="*60)
    print(f"[ACCESS] User {update.effective_user.id} initiated /start")
    print("="*60)

    if not check_subscription(update, context):
        keyboard = [
            [InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)],
            [InlineKeyboardButton("✅ I've Joined", callback_data="check_joined")]
        ]
        update.message.reply_text(
            "🛑 **ACCESS DENIED**\n\n"
            "🔐 Channel verification required.\n"
            "Join the channel to unlock access.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    update.message.reply_text(
        "🛡 **SECURE ACCESS GRANTED**\n\n"
        "👁 Status: VERIFIED\n"
        "🎯 Send target **@username** (without @)\n"
        "⚙️ Initializing report engine...",
        parse_mode="Markdown"
    )
    return USERNAME

def button_handler(update, context):
    query = update.callback_query
    query.answer()
    if check_subscription(update, context):
        query.message.edit_text(
            "✅ **VERIFICATION PASSED**\nUse /start to continue.",
            parse_mode="Markdown"
        )

def handle_username(update: Update, context: CallbackContext):
    if not check_subscription(update, context):
        update.message.reply_text("❌ Access revoked. Join channel again.")
        return ConversationHandler.END

    username = update.message.text.strip().lstrip('@')
    context.user_data["username"] = username

    if not re.match(r'^[a-zA-Z0-9_]{5,32}$', username):
        update.message.reply_text("❌ Invalid username format.")
        return ConversationHandler.END

    update.message.reply_text("🔍 Scanning target on Telegram...")
    if not is_valid_username(username):
        update.message.reply_text("❌ Target not found.")
        return ConversationHandler.END

    update.message.reply_text("✅ Target verified. Launching report sequence...")

    reports = load_reports()
    total = len(reports)
    success_count = 0
    progress_message = update.message.reply_text("⚙️ Initializing report modules...")

    report_log = []
    proxies = load_proxies()
    proxy_index = 0
    success_by_proxy = {}

    for i, msg in enumerate(reports):
        if i % 10 == 0 and not check_subscription(update, context):
            progress_message.edit_text("❌ Subscription lost. Process aborted.")
            return ConversationHandler.END

        form_data, name, email, number, final_msg = generate_data(username, msg)
        proxy = proxies[proxy_index] if proxies else None
        success, used_proxy = send_data(form_data, proxy)

        if success:
            success_count += 1
            success_by_proxy[used_proxy] = success_by_proxy.get(used_proxy, 0) + 1
            report_log.append(
                f"Report {i+1}\nName: {name}\nEmail: {email}\nPhone: {number}\nProxy: {used_proxy}\nMessage: {final_msg}\n---\n"
            )

        if proxies:
            proxy_index = (proxy_index + 1) % len(proxies)

        time.sleep(2)

        percent = int(((i + 1) / total) * 100)
        bar = "█" * (percent // 10) + "▒" * (10 - percent // 10)
        stats = "\n".join(f"🌐 {p}: {c}" for p, c in success_by_proxy.items())

        progress_message.edit_text(
            f"📊 [{bar}] {percent}%\n"
            f"📤 Sent: {i+1}/{total}\n"
            f"✅ Success: {success_count}\n\n{stats}"
        )

        if len(report_log) > 0 and len(report_log) % 50 == 0:
            fname = f"reports_{username}.txt"
            with open(fname, "w", encoding="utf-8") as f:
                f.writelines(report_log)
            update.message.reply_document(
                document=open(fname, "rb"),
                caption=f"📋 Logs: {success_count} successful reports"
            )

        if success_count > 0 and success_count % 50 == 0:
            update.message.reply_text(f"✅ {success_count} reports sent successfully.")

    progress_message.edit_text(
        f"✅ **MISSION COMPLETE**\n"
        f"📨 Successful reports: {success_count}/{total}"
    )
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END

def channel_command(update: Update, context: CallbackContext):
    keyboard = [[InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)]]
    update.message.reply_text(
        f"📢 **CHANNEL ACCESS REQUIRED**\n\n{CHANNEL_LINK}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("channel", channel_command))
    dp.add_handler(CallbackQueryHandler(button_handler))

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={USERNAME: [MessageHandler(Filters.text & ~Filters.command, handle_username)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    dp.add_handler(conv)

    hacker_startup()

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()