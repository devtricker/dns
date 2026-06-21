"""
🦆  Dynu DDNS Telegram Bot  🦆
─────────────────────────────────
Create & manage DDNS hostnames
via Telegram with style!
"""
import asyncio
import json
import os
import random
import re
import string
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction, ParseMode
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ═══════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════
CONFIG_FILE = "ddns_config.json"
DYNU_API_KEY = "6rn185EWYn16o09521C0FxERo8g6Xve5"
IP_UPDATE_PASS = "devtronex123"

DYNU_DOMAINS = [
    "opik.net", "freedynamicdns.net", "freedynamicdns.org", "dynu.com", "dynu.net",
    "ddnsfree.com", "ddnsking.com", "ddns.us", "dyns.cx", "dyn-o-saur.com",
    "my03.com", "myforum.site", "mywire.org", "onthewifi.com", "raspberryip.com",
]

# Conversation states
WAIT_DOMAIN, WAIT_SUBDOMAIN, WAIT_IP, WAIT_HOSTNAME_UPDATE, WAIT_IP_UPDATE, WAIT_RENAME_NAME, WAIT_DELETE_CONFIRM = range(7)

# ═══════════════════════════════════════
# EMOJI KIT (Premium Styled)
# ═══════════════════════════════════════
E = {
    "duck": "🦆", "globe": "🌐", "server": "🖥️", "key": "🔑",
    "rocket": "🚀", "sparkles": "✨", "star": "⭐", "crown": "👑",
    "check": "✅", "cross": "❌", "warning": "⚠️", "info": "ℹ️",
    "link": "🔗", "lock": "🔒", "unlock": "🔓", "refresh": "🔄",
    "plus": "➕", "list": "📋", "home": "🏠", "tools": "🛠️",
    "lightning": "⚡", "fire": "🔥", "heart": "❤️", "gift": "🎁",
    "party": "🎉", "confetti": "🎊", "rainbow": "🌈", "diamond": "💎",
    "bot": "🤖", "wave": "👋", "cool": "😎", "pray": "🙏",
    "clock": "⏰", "hourglass": "⏳", "target": "🎯", "shield": "🛡️",
    "globe_asia": "🌏", "satellite": "📡", "antenna": "📶", "cloud": "☁️",
    "sun": "☀️", "moon": "🌙", "zap": "⚡", "bulb": "💡",
    "book": "📖", "pen": "✍️", "magnify": "🔎", "wrench": "🔧",
    "package": "📦", "inbox": "📥", "outbox": "📤", "chart": "📊",
    "medal": "🏅", "trophy": "🏆", "gem": "💠", "orb": "🔮",
    "cyber": "🌐", "matrix": "👾", "alien": "👽", "ghost": "👻",
}

# ═══════════════════════════════════════
# CORE FUNCTIONS
# ═══════════════════════════════════════
def get_public_ip():
    for url in ["https://api.ipify.org", "https://httpbin.org/ip"]:
        try:
            r = requests.get(url, timeout=5)
            return r.text.strip() if "ipify" in url else r.json()["origin"]
        except:
            pass
    return None

def is_valid_ip(ip_str):
    """Validate IPv4 address"""
    m = re.match(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$', ip_str.strip())
    if not m:
        return False
    return all(0 <= int(g) <= 255 for g in m.groups())

def api_call(method, path, data=None):
    h = {"accept": "application/json", "API-Key": DYNU_API_KEY}
    url = f"https://api.dynu.com/v2{path}"
    try:
        if method == "GET":
            r = requests.get(url, headers=h, timeout=30)
        elif method == "POST":
            h["Content-Type"] = "application/json"
            r = requests.post(url, headers=h, json=data, timeout=30)
        elif method == "DELETE":
            r = requests.delete(url, headers=h, timeout=30)
        elif method == "PUT":
            h["Content-Type"] = "application/json"
            r = requests.put(url, headers=h, json=data, timeout=30)
        return r.json() if r.text else {}, r.status_code
    except Exception as e:
        return None, str(e)

def list_hostnames():
    data, status = api_call("GET", "/dns")
    if status != 200:
        return []
    return data.get("domains", [])

def create_hostname_api(hostname, ip):
    print(f"Creating {hostname} → {ip}")
    data = {"name": hostname, "group": "", "ipv4Address": ip, "ttl": 120}
    _, status = api_call("POST", "/dns", data)
    r = requests.get("https://api.dynu.com/nic/update", params={
        "hostname": hostname, "myip": ip, "password": IP_UPDATE_PASS
    }, timeout=30)
    resp = r.text.strip()
    if "good" in resp.lower() or "nochg" in resp.lower():
        return True, resp
    return False, resp

def update_ip_api(hostname, ip):
    r = requests.get("https://api.dynu.com/nic/update", params={
        "hostname": hostname, "myip": ip, "password": IP_UPDATE_PASS
    }, timeout=30)
    resp = r.text.strip()
    if "good" in resp.lower():
        return "updated", resp
    elif "nochg" in resp.lower():
        return "unchanged", resp
    return "failed", resp

def delete_hostname_api(hostname_id):
    """Delete a hostname by ID. Returns (success, message)."""
    _, status = api_call("DELETE", f"/dns/{hostname_id}")
    if status == 200:
        return True, "Deleted"
    return False, f"HTTP {status}"

def rename_hostname_api(hostname_id, new_name):
    """Rename a hostname. Returns (success, message)."""
    _, status = api_call("PUT", f"/dns/{hostname_id}", {"name": new_name})
    if status == 200:
        return True, "Renamed"
    return False, f"HTTP {status}"

# ═══════════════════════════════════════
# KEYBOARDS
# ═══════════════════════════════════════
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{E['list']}  My Hostnames", callback_data="list_hosts")],
        [InlineKeyboardButton(f"{E['plus']}  Create New Hostname", callback_data="create_new")],
        [InlineKeyboardButton(f"{E['refresh']}  Update IP", callback_data="update_ip_menu")],
        [InlineKeyboardButton(f"{E['wrench']}  Rename Hostname", callback_data="rename_menu")],
        [InlineKeyboardButton(f"{E['cross']}  Delete Hostname", callback_data="delete_menu")],
        [InlineKeyboardButton(f"{E['magnify']}  Check Current IP", callback_data="check_ip")],
        [InlineKeyboardButton(f"{E['book']}  Help & Info", callback_data="help")],
    ])

def back_button():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{E['home']}  « Back to Menu", callback_data="main_menu")]
    ])

def domains_keyboard():
    btns = []
    row = []
    for i, d in enumerate(DYNU_DOMAINS[:9], 1):
        row.append(InlineKeyboardButton(d, callback_data=f"domain_{d}"))
        if len(row) == 3:
            btns.append(row)
            row = []
    if row:
        btns.append(row)
    btns.append([InlineKeyboardButton(f"{E['home']}  « Cancel", callback_data="main_menu")])
    return InlineKeyboardMarkup(btns)

# ═══════════════════════════════════════
# COMMAND HANDLERS
# ═══════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """🚀 /start - Beautiful Welcome"""
    user = update.effective_user
    name = user.first_name or "Friend"
    
    # Send typing action
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    await asyncio.sleep(0.5)
    
    # --- PREMIUM WELCOME MESSAGE ---
    welcome = f"""
{E['sparkles']} *WELCOME TO DUCK DNS BOT* {E['sparkles']}
{E['crown']} ━━━━━━━━━━━━━━━━━━━━ {E['crown']}

{E['wave']} Hey *{name}*! 
{E['bot']} I'm your personal *DDNS Manager Bot*

{E['diamond']} *I can help you:*
{E['globe']}  Create free DDNS hostnames
{E['refresh']}  Auto-update your dynamic IP
{E['list']}  Manage all your hostnames
{E['lightning']}  Monitor DNS status

{E['rainbow']} ━━━━━━━━━━━━━━━━━━━━ {E['rainbow']}
{E['star']} _Powered by Dynu API v2_
{E['fire']} _Premium Experience • Fast & Reliable_
{E['sparkles']} ━━━━━━━━━━━━━━━━━━━━ {E['sparkles']}

{E['target']} *Choose an option below:* ⤵️
"""
    await update.message.reply_text(
        welcome,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_menu()
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ℹ️ Help & Info"""
    query = update.callback_query
    if query:
        await query.answer()
    
    help_text = f"""
{E['book']} *HELP & INFO* {E['book']}
{E['diamond']} ━━━━━━━━━━━━━━━━━━━━ {E['diamond']}

{E['globe']} *What is DDNS?*
Dynamic DNS lets you access your device
using a fixed hostname even when your
IP address keeps changing!

{E['satellite']} *How it works:*
{E['plus']}  Create a free hostname
{E['refresh']}  Bot auto-updates your IP
{E['globe_asia']}  Access from anywhere!

{E['tools']} *Commands:*
/start  {E['rocket']} Main menu
/help   {E['book']} This help
/ip     {E['magnify']} Check current IP

{E['shield']} *Privacy:*
Your credentials are stored locally
and never shared.

{E['sparkles']} ━━━━━━━━━━━━━━━━━━━━ {E['sparkles']}
{E['star']} Enjoy premium DDNS management!
"""
    if query:
        await query.edit_message_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_button()
        )
    else:
        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_button()
        )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ALL inline button presses"""
    query = update.callback_query
    await query.answer()
    data = query.data
    
    # --- MAIN MENU ---
    if data == "main_menu":
        welcome = f"""
{E['sparkles']} *MAIN MENU* {E['sparkles']}
{E['diamond']} ━━━━━━━━━━━━━━━━━━━━ {E['diamond']}

{E['target']} *Choose an option:* ⤵️
"""
        await query.edit_message_text(
            welcome,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_menu()
        )
    
    # --- CHECK IP ---
    elif data == "check_ip":
        await query.edit_message_text(
            f"{E['magnify']} *Checking your IP...* {E['lightning']}",
            parse_mode=ParseMode.MARKDOWN
        )
        ip = get_public_ip()
        if ip:
            text = f"""
{E['globe']} *YOUR PUBLIC IP* {E['globe']}
{E['diamond']} ━━━━━━━━━━━━━━━━━━━━ {E['diamond']}

{E['satellite']} *IP Address:*
`{ip}`

{E['globe_asia']} *Location:* Auto-detected
{E['clock']} *Checked:* {datetime.now().strftime('%H:%M:%S')}

{E['sparkles']} ━━━━━━━━━━━━━━━━━━━━ {E['sparkles']}
"""
        else:
            text = f"{E['cross']} Could not detect IP. Check your internet connection."
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_button()
        )
    
    # --- LIST HOSTNAMES ---
    elif data == "list_hosts":
        await query.edit_message_text(
            f"{E['list']} *Fetching your hostnames...* {E['hourglass']}",
            parse_mode=ParseMode.MARKDOWN
        )
        hosts = list_hostnames()
        if hosts:
            lines = []
            for i, h in enumerate(hosts, 1):
                ip = h.get('ipv4Address', 'N/A')
                status_icon = E['check'] if ip != 'N/A' else E['warning']
                lines.append(f"{status_icon} `{h['name']}`\n   {E['link']} → `{ip}`")
            
            text = f"""
{E['list']} *YOUR HOSTNAMES* {E['list']}
{E['diamond']} ━━━━━━━━━━━━━━━━━━━━ {E['diamond']}

{chr(10).join(lines)}

{E['chart']} *Total:* {len(hosts)} hostname(s)
{E['sparkles']} ━━━━━━━━━━━━━━━━━━━━ {E['sparkles']}
"""
        else:
            text = f"""
{E['list']} *NO HOSTNAMES* {E['list']}
{E['diamond']} ━━━━━━━━━━━━━━━━━━━━ {E['diamond']}

{E['warning']} You haven't created any hostnames yet!

{E['plus']} Tap *Create New Hostname* to get started!
"""
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_button()
        )
    
    # --- CREATE NEW HOSTNAME ---
    elif data == "create_new":
        text = f"""
{E['plus']} *CREATE NEW HOSTNAME* {E['plus']}
{E['diamond']} ━━━━━━━━━━━━━━━━━━━━ {E['diamond']}

{E['target']} *Step 1/3:* Pick a domain

{E['globe']} Choose from the options below
or type your own domain:
"""
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=domains_keyboard()
        )
    
    # --- DOMAIN SELECTED ---
    elif data.startswith("domain_"):
        domain = data.replace("domain_", "")
        context.user_data["new_domain"] = domain
        
        text = f"""
{E['plus']} *CREATE NEW HOSTNAME* {E['plus']}
{E['diamond']} ━━━━━━━━━━━━━━━━━━━━ {E['diamond']}

{E['globe']} *Domain:* `{domain}`

{E['target']} *Step 2/3:* Reply with subdomain name

{E['pen']} Example: `myserver` → `myserver.{domain}`
{E['bot']} Or send `/auto` for random name!
"""
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{E['bot']}  Auto-Generate Name", callback_data="auto_name")],
                [InlineKeyboardButton(f"{E['home']}  « Cancel", callback_data="main_menu")],
            ])
        )
        return WAIT_SUBDOMAIN

    # --- AUTO NAME ---
    elif data == "auto_name":
        domain = context.user_data.get("new_domain", "opik.net")
        sub = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        full = f"{sub}.{domain}"
        context.user_data["new_full"] = full
        
        text = f"""
{E['bot']} *AUTO-GENERATED* {E['bot']}
{E['diamond']} ━━━━━━━━━━━━━━━━━━━━ {E['diamond']}

{E['globe']} *Hostname:* `{full}`

{E['target']} *Step 3/3:* Reply with IP address

{E['pen']} Example: `56.228.42.116`
{E['bot']} Or send /autoip for current IP!
"""
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{E['magnify']}  Use Current IP", callback_data="auto_ip")],
                [InlineKeyboardButton(f"{E['home']}  « Cancel", callback_data="main_menu")],
            ])
        )
        return WAIT_IP
    
    # --- UPDATE IP MENU ---
    elif data == "update_ip_menu":
        hosts = list_hostnames()
        if hosts:
            btns = []
            for h in hosts:
                btns.append([InlineKeyboardButton(
                    f"{E['globe']} {h['name']} → {h.get('ipv4Address', '?')}",
                    callback_data=f"updateip_{h['name']}"
                )])
            btns.append([InlineKeyboardButton(f"{E['home']}  « Cancel", callback_data="main_menu")])
            keyboard = InlineKeyboardMarkup(btns)
            
            text = f"""
{E['refresh']} *UPDATE IP* {E['refresh']}
{E['diamond']} ━━━━━━━━━━━━━━━━━━━━ {E['diamond']}

{E['target']} Pick a hostname to update:
"""
        else:
            keyboard = back_button()
            text = f"{E['warning']} No hostnames to update!"
        
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    
    # --- UPDATE SPECIFIC HOSTNAME IP ---
    elif data.startswith("updateip_"):
        hostname = data.replace("updateip_", "")
        context.user_data["update_hostname"] = hostname
        
        text = f"""
{E['refresh']} *UPDATE IP* {E['refresh']}
{E['diamond']} ━━━━━━━━━━━━━━━━━━━━ {E['diamond']}

{E['globe']} *Hostname:* `{hostname}`

{E['target']} Reply with the new IP address

{E['pen']} Example: `56.228.42.116`
{E['bot']} Or send /autoip for current IP!
"""
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{E['magnify']}  Use Current IP", callback_data="auto_ip_update")],
                [InlineKeyboardButton(f"{E['home']}  « Cancel", callback_data="main_menu")],
            ])
        )
        return WAIT_IP_UPDATE
    
    # --- AUTO IP for creation ---
    elif data == "auto_ip":
        ip = get_public_ip()
        if not ip:
            await query.edit_message_text(
                f"{E['cross']} Could not detect IP! Please type it manually.",
                reply_markup=back_button()
            )
            context.user_data.clear()
            return ConversationHandler.END
        
        full = context.user_data.get("new_full", "unknown.opik.net")
        await query.edit_message_text(
            f"{E['hourglass']} Using current IP: `{ip}`\nCreating `{full}`...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        success, resp = create_hostname_api(full, ip)
        if success:
            text = f"""
{E['party']} *HOSTNAME CREATED!* {E['confetti']}
{E['crown']} ━━━━━━━━━━━━━━━━━━━━ {E['crown']}

{E['globe']} *Hostname:* `{full}`
{E['satellite']} *IP:* `{ip}`
{E['check']} *Status:* Active {E['fire']}

{E['clock']} DNS propagation: ~2-5 min
{E['lightning']} Response: `{resp}`
"""
        else:
            text = f"{E['cross']} Failed: `{resp}`"
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())
        context.user_data.clear()
        return ConversationHandler.END
    
    # --- AUTO IP for update ---
    elif data == "auto_ip_update":
        ip = get_public_ip()
        if not ip:
            await query.edit_message_text(
                f"{E['cross']} Could not detect IP! Please type it manually.",
                reply_markup=back_button()
            )
            context.user_data.clear()
            return ConversationHandler.END
        
        hostname = context.user_data.get("update_hostname", "unknown")
        await query.edit_message_text(
            f"{E['hourglass']} Using current IP: `{ip}`\nUpdating `{hostname}`...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        status, resp = update_ip_api(hostname, ip)
        if status == "updated":
            text = f"""
{E['check']} *IP UPDATED!* {E['rocket']}
{E['globe']} *Hostname:* `{hostname}`
{E['satellite']} *New IP:* `{ip}`
"""
        elif status == "unchanged":
            text = f"""
{E['info']} *IP UNCHANGED* {E['info']}
{E['globe']} *Hostname:* `{hostname}`
{E['link']} *IP:* `{ip}` (already set)
"""
        else:
            text = f"{E['cross']} Update failed: `{resp}`"
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())
        context.user_data.clear()
        return ConversationHandler.END
    
    # --- RENAME MENU ---
    elif data == "rename_menu":
        hosts = list_hostnames()
        if hosts:
            btns = []
            for h in hosts:
                btns.append([InlineKeyboardButton(
                    f"{E['globe']} {h['name']}",
                    callback_data=f"renid_{h['id']}"
                )])
            btns.append([InlineKeyboardButton(f"{E['home']}  « Cancel", callback_data="main_menu")])
            keyboard = InlineKeyboardMarkup(btns)
            text = f"""
{E['wrench']} *RENAME HOSTNAME* {E['wrench']}
{E['diamond']} ━━━━━━━━━━━━━━━━━━━━ {E['diamond']}

{E['target']} Pick a hostname to rename:
"""
        else:
            keyboard = back_button()
            text = f"{E['warning']} No hostnames to rename!"
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    
    # --- RENAME SPECIFIC HOSTNAME ---
    elif data.startswith("renid_"):
        hostname_id = int(data.replace("renid_", ""))
        # Find hostname name
        hosts = list_hostnames()
        old_name = "unknown"
        for h in hosts:
            if h['id'] == hostname_id:
                old_name = h['name']
                break
        context.user_data["rename_id"] = hostname_id
        context.user_data["rename_old"] = old_name
        
        text = f"""
{E['wrench']} *RENAME HOSTNAME* {E['wrench']}
{E['diamond']} ━━━━━━━━━━━━━━━━━━━━ {E['diamond']}

{E['globe']} *Current:* `{old_name}`

{E['target']} Reply with the new hostname:
{E['pen']} Example: `mynewserver.opik.net`
"""
        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{E['home']}  « Cancel", callback_data="main_menu")]
            ])
        )
        return WAIT_RENAME_NAME
    
    # --- DELETE MENU ---
    elif data == "delete_menu":
        hosts = list_hostnames()
        if hosts:
            btns = []
            for h in hosts:
                btns.append([InlineKeyboardButton(
                    f"{E['cross']} {h['name']}",
                    callback_data=f"delid_{h['id']}"
                )])
            btns.append([InlineKeyboardButton(f"{E['home']}  « Cancel", callback_data="main_menu")])
            keyboard = InlineKeyboardMarkup(btns)
            text = f"""
{E['cross']} *DELETE HOSTNAME* {E['cross']}
{E['diamond']} ━━━━━━━━━━━━━━━━━━━━ {E['diamond']}

{E['warning']} *WARNING:* This cannot be undone!

{E['target']} Pick a hostname to delete:
"""
        else:
            keyboard = back_button()
            text = f"{E['warning']} No hostnames to delete!"
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    
    # --- DELETE CONFIRMATION ---
    elif data.startswith("delid_"):
        hostname_id = int(data.replace("delid_", ""))
        hosts = list_hostnames()
        hostname = "unknown"
        for h in hosts:
            if h['id'] == hostname_id:
                hostname = h['name']
                break
        context.user_data["delete_id"] = hostname_id
        context.user_data["delete_name"] = hostname
        
        text = f"""
{E['cross']} *CONFIRM DELETE* {E['cross']}
{E['diamond']} ━━━━━━━━━━━━━━━━━━━━ {E['diamond']}

{E['warning']} Are you sure you want to delete:

{E['globe']} *`{hostname}`*

{E['fire']} This action *cannot be undone*!
"""
        await query.edit_message_text(
            text, parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{E['check']}  Yes, Delete It!", callback_data="confirm_delete"),
                 InlineKeyboardButton(f"{E['home']}  « Cancel", callback_data="main_menu")],
            ])
        )
        return WAIT_DELETE_CONFIRM
    
    # --- CONFIRMED DELETE ---
    elif data == "confirm_delete":
        hostname_id = context.user_data.get("delete_id")
        hostname = context.user_data.get("delete_name", "unknown")
        
        success, resp = delete_hostname_api(hostname_id)
        if success:
            text = f"""
{E['check']} *HOSTNAME DELETED!* {E['check']}
{E['diamond']} ━━━━━━━━━━━━━━━━━━━━ {E['diamond']}

{E['cross']} *`{hostname}`* has been permanently deleted.

{E['sparkles']} ━━━━━━━━━━━━━━━━━━━━ {E['sparkles']}
"""
        else:
            text = f"{E['cross']} Delete failed: `{resp}`"
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())
        context.user_data.clear()
        return ConversationHandler.END
    
    # --- HELP ---
    elif data == "help":
        await help_cmd(update, context)

async def receive_subdomain(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive subdomain name from user text, then ask for IP"""
    sub = update.message.text.strip().lower()
    if sub.startswith("/"):
        sub = sub.replace("/", "").replace("auto", "")
    if not sub:
        sub = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    
    domain = context.user_data.get("new_domain", "opik.net")
    full = f"{sub}.{domain}"
    context.user_data["new_full"] = full
    
    text = f"""
{E['plus']} *CREATE NEW HOSTNAME* {E['plus']}
{E['diamond']} ━━━━━━━━━━━━━━━━━━━━ {E['diamond']}

{E['globe']} *Hostname:* `{full}`

{E['target']} *Step 3/3:* Reply with IP address

{E['pen']} Example: `56.228.42.116`
{E['bot']} Or tap the button below for auto IP!
"""
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{E['magnify']}  Use Current IP", callback_data="auto_ip")],
            [InlineKeyboardButton(f"{E['home']}  « Cancel", callback_data="main_menu")],
        ])
    )
    return WAIT_IP

async def receive_ip_for_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive IP for new hostname creation"""
    ip = update.message.text.strip()
    if not is_valid_ip(ip):
        await update.message.reply_text(
            f"{E['cross']} Invalid IP format! Please enter a valid IPv4 address like `56.228.42.116`\n{E['home']} Or /cancel to abort",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAIT_IP
    
    full = context.user_data.get("new_full", "unknown.opik.net")
    
    await update.message.reply_chat_action(action=ChatAction.TYPING)
    msg = await update.message.reply_text(
        f"{E['hourglass']} Creating `{full}` → `{ip}`...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    success, resp = create_hostname_api(full, ip)
    
    if success:
        text = f"""
{E['party']} *HOSTNAME CREATED!* {E['confetti']}
{E['crown']} ━━━━━━━━━━━━━━━━━━━━ {E['crown']}

{E['globe']} *Hostname:* `{full}`
{E['satellite']} *IP:* `{ip}`
{E['check']} *Status:* Active {E['fire']}

{E['clock']} DNS propagation: ~2-5 min
{E['lightning']} Response: `{resp}`

{E['sparkles']} ━━━━━━━━━━━━━━━━━━━━ {E['sparkles']}
{E['star']} Ready to use! Enjoy! {E['rainbow']}
"""
    else:
        text = f"{E['cross']} Failed: `{resp}`"
    
    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())
    context.user_data.clear()
    return ConversationHandler.END

async def receive_ip_for_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive IP for updating existing hostname"""
    ip = update.message.text.strip()
    if not is_valid_ip(ip):
        await update.message.reply_text(
            f"{E['cross']} Invalid IP format! Please enter a valid IPv4 address like `56.228.42.116`\n{E['home']} Or /cancel to abort",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAIT_IP_UPDATE
    
    hostname = context.user_data.get("update_hostname", "unknown")
    
    await update.message.reply_chat_action(action=ChatAction.TYPING)
    msg = await update.message.reply_text(
        f"{E['hourglass']} Updating `{hostname}` → `{ip}`...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    status, resp = update_ip_api(hostname, ip)
    if status == "updated":
        text = f"""
{E['check']} *IP UPDATED!* {E['rocket']}
{E['diamond']} ━━━━━━━━━━━━━━━━━━━━ {E['diamond']}

{E['globe']} *Hostname:* `{hostname}`
{E['satellite']} *New IP:* `{ip}`
{E['check']} *Status:* Updated successfully!

{E['sparkles']} DNS propagating globally...
"""
    elif status == "unchanged":
        text = f"""
{E['info']} *IP UNCHANGED* {E['info']}
{E['diamond']} ━━━━━━━━━━━━━━━━━━━━ {E['diamond']}

{E['globe']} *Hostname:* `{hostname}`
{E['link']} *IP:* `{ip}`
{E['check']} Already up-to-date!
"""
    else:
        text = f"{E['cross']} Update failed: `{resp}`"
    
    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())
    context.user_data.clear()
    return ConversationHandler.END

async def receive_rename_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive new hostname for rename"""
    new_name = update.message.text.strip().lower()
    old_name = context.user_data.get("rename_old", "unknown")
    rename_id = context.user_data.get("rename_id")
    
    if not new_name or "." not in new_name:
        await update.message.reply_text(
            f"{E['cross']} Please enter full hostname (e.g. `myserver.opik.net`)!\n{E['home']} Or /cancel",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAIT_RENAME_NAME
    
    await update.message.reply_chat_action(action=ChatAction.TYPING)
    msg = await update.message.reply_text(
        f"{E['hourglass']} Renaming `{old_name}` → `{new_name}`...",
        parse_mode=ParseMode.MARKDOWN
    )
    
    success, resp = rename_hostname_api(rename_id, new_name)
    if success:
        text = f"""
{E['check']} *HOSTNAME RENAMED!* {E['party']}
{E['diamond']} ━━━━━━━━━━━━━━━━━━━━ {E['diamond']}

{E['globe']} *Old:* `{old_name}`
{E['sparkles']} *New:* `{new_name}`

{E['clock']} DNS propagation: ~2-5 min
{E['sparkles']} ━━━━━━━━━━━━━━━━━━━━ {E['sparkles']}
"""
    else:
        text = f"{E['cross']} Rename failed: `{resp}`"
    
    await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_button())
    context.user_data.clear()
    return ConversationHandler.END

async def ip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quick /ip command"""
    await update.message.reply_chat_action(action=ChatAction.TYPING)
    ip = get_public_ip()
    if ip:
        text = f"""
{E['globe']} *Current IP*
{E['satellite']} `{ip}`
"""
    else:
        text = f"{E['cross']} Could not detect IP."
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel conversation"""
    context.user_data.clear()
    text = f"{E['check']} Operation cancelled. {E['wave']}"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=back_button())
    else:
        await update.message.reply_text(text, reply_markup=back_button())
    return ConversationHandler.END

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle unknown commands"""
    await update.message.reply_text(
        f"{E['warning']} Unknown command!\n{E['info']} Use /start or /help",
        reply_markup=main_menu()
    )

# ═══════════════════════════════════════
# MAIN
# ═══════════════════════════════════════
def main():
    # ⚠️ REPLACE WITH YOUR BOT TOKEN from @BotFather
    BOT_TOKEN = "8958250692:AAG6CyJnim9Dafom-CDmIeGj72ENi4BTvPw"
    
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print(f"\n{E['warning']}  Please set your BOT_TOKEN in the script!")
        print(f"{E['info']}  1. Go to @BotFather on Telegram")
        print(f"   2. Send /newbot and follow instructions")
        print(f"   3. Copy the token and paste in BOT_TOKEN variable")
        print(f"   4. Run this script again!\n")
        return
    
    print(f"""
{E['sparkles']}  ═══════════════════════════════ {E['sparkles']}
{E['bot']}     DUCK DNS TELEGRAM BOT {E['bot']}
{E['diamond']}  ═══════════════════════════════ {E['diamond']}
{E['rocket']}  Starting bot... {E['rocket']}
{E['check']}  Premium features enabled!
{E['sparkles']}  ═══════════════════════════════ {E['sparkles']}
""")
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Create conversation handler for hostname creation & update flow
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_handler, pattern="^(create_new|auto_name|domain_)"),
            CallbackQueryHandler(button_handler, pattern="^updateip_"),
            CallbackQueryHandler(button_handler, pattern="^renid_"),
            CallbackQueryHandler(button_handler, pattern="^delid_"),
        ],
        states={
            WAIT_SUBDOMAIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_subdomain),
                CallbackQueryHandler(button_handler, pattern="^(auto_name|main_menu)$"),
            ],
            WAIT_IP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ip_for_create),
                CallbackQueryHandler(button_handler, pattern="^(auto_ip|main_menu)$"),
            ],
            WAIT_IP_UPDATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ip_for_update),
                CallbackQueryHandler(button_handler, pattern="^(auto_ip_update|main_menu)$"),
            ],
            WAIT_RENAME_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_rename_name),
                CallbackQueryHandler(button_handler, pattern="^main_menu$"),
            ],
            WAIT_DELETE_CONFIRM: [
                CallbackQueryHandler(button_handler, pattern="^(confirm_delete|main_menu)$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern="^main_menu$"),
        ],
        allow_reentry=True,
    )
    
    # Register handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("ip", ip_command))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    
    print(f"  {E['check']}  Bot is RUNNING!")
    print(f"  {E['link']}  Open Telegram and send /start")
    print(f"  {E['info']}  Press Ctrl+C to stop\n")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    # Create event loop BEFORE run_polling tries to get it
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main()
