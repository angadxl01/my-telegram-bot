import os
import re
import logging
import threading
import sqlite3
from flask import Flask
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    ConversationHandler,
    filters,
)

# ==================== EDIT YOUR DETAILS HERE ====================
BOT_TOKEN = "8794925442:AAFIHaUAJM8ZXt2guEN7Lq2kKyTTKzECWqw"
ADMIN_ID = 8895089247              # Aapka Numeric Telegram User ID
SUPPORT_USERNAME = "tgprimesoul"   # Support Username

API_ID = 36645562                   # my.telegram.org ka API_ID
API_HASH = "ccad405579d80b82492abbf4a7777907"    # my.telegram.org ka API_HASH

# Telegram Premium Sticker File ID Yahan Dalein:
PREMIUM_STICKER_ID = "CAACAgIAAxkBAAE_YOUR_STICKER_FILE_ID_HERE"
# ================================================================

MIN_DEPOSIT = 25

payment_settings = {
    "upi": "tgprimesoul@upi",
    "qr_url": "https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=upi://pay?pa=tgprimesoul@upi",
    "crypto": "USDT (TRC20): TYourUSDTWalletAddressHere"
}

WAITING_CAT, WAITING_AGE, WAITING_PRICE, WAITING_PHONE, WAITING_SESSION = range(5)

# --- HELPER FUNCTION FOR PREMIUM STICKER ---
async def send_premium_sticker(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        if PREMIUM_STICKER_ID and "YOUR_STICKER" not in PREMIUM_STICKER_ID:
            await context.bot.send_sticker(chat_id=chat_id, sticker=PREMIUM_STICKER_ID)
    except Exception:
        pass

# --- DATABASE ENGINE (SQLite3) ---
DB_NAME = "store.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (uid INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0, orders INTEGER DEFAULT 0);""")
    c.execute("""CREATE TABLE IF NOT EXISTS stock (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, age TEXT, price REAL, phone TEXT, session TEXT, is_sold INTEGER DEFAULT 0);""")
    c.execute("""CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, item_id INTEGER, phone TEXT, session TEXT);""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);""")
    conn.commit()
    conn.close()

init_db()

def get_setting(key, default=""):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row["value"] if row else default

def set_setting(key, value):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO settings (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value;
    """, (key, value))
    conn.commit()
    conn.close()

def get_user_db(uid):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT balance, orders FROM users WHERE uid = ?", (uid,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO users (uid, balance, orders) VALUES (?, 0.0, 0)", (uid,))
        conn.commit()
        balance, orders = 0.0, 0
    else:
        balance, orders = row["balance"], row["orders"]
    conn.close()
    return {"balance": balance, "orders": orders}

def update_balance_db(uid, amt):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO users (uid, balance, orders) VALUES (?, ?, 0)
        ON CONFLICT(uid) DO UPDATE SET balance = users.balance + ?;
    """, (uid, amt, amt))
    conn.commit()
    conn.close()

def clean_html(text):
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# --- FORCE JOIN CHECKER ---
async def check_force_join(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    channel_id = get_setting("force_channel_id", "")
    if user_id == ADMIN_ID or not channel_id:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        if member.status in ["creator", "administrator", "member"]:
            return True
        return False
    except Exception:
        return True

async def send_force_join_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_id = get_setting("force_channel_id", "")
    channel_url = f"https://t.me/{channel_id.replace('@', '')}"
    kb = [
        [InlineKeyboardButton("📢 Join Channel", url=channel_url)],
        [InlineKeyboardButton("🔄 Checked / Try Again", callback_data="btn_main")]
    ]
    txt = "⚠️ <b>Access Denied!</b>\n\nBot ko use karne ke liye pehle hamara official channel join karein."
    chat_id = update.effective_chat.id
    await send_premium_sticker(chat_id, context)
    
    if update.message:
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    else:
        await update.callback_query.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

# --- WEB SERVER ---
web_app = Flask('')

@web_app.route('/')
def home():
    return "Store Engine Online"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- USER SYSTEM ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    if not await check_force_join(u.id, context):
        await send_force_join_msg(update, context)
        return

    u_data = get_user_db(u.id)

    kb = [
        [InlineKeyboardButton("🛍️ Browse Categories", callback_data="btn_categories")],
        [InlineKeyboardButton("👤 Profile", callback_data="btn_profile"), InlineKeyboardButton("💳 Add Money", callback_data="btn_add_bal")],
        [InlineKeyboardButton("👨‍💻 Support", callback_data="btn_support")]
    ]
    txt = f"<b>❤️ Welcome to TG Store! 👋</b>\n\n🆔 <b>ID:</b> <code>{u.id}</code>\n💰 <b>Balance:</b> ₹{u_data['balance']:.2f}"

    await send_premium_sticker(u.id, context)

    if update.message:
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    else:
        await update.callback_query.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await check_force_join(q.from_user.id, context):
        await send_force_join_msg(update, context)
        return

    kb = [
        [InlineKeyboardButton("🔹 Normal Acc", callback_data="cat_normal")],
        [InlineKeyboardButton("⭐ Premium Acc", callback_data="cat_premium")],
        [InlineKeyboardButton("🛠️ Maked Acc", callback_data="cat_maked")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]
    ]
    await send_premium_sticker(q.from_user.id, context)
    await q.message.reply_text("<b>📂 Select Category:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def category_stock_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await check_force_join(q.from_user.id, context):
        await send_force_join_msg(update, context)
        return

    cat_type = q.data.replace("cat_", "").lower()

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, age, price FROM stock WHERE category = ? AND is_sold = 0", (cat_type,))
    filtered_items = c.fetchall()
    conn.close()

    await send_premium_sticker(q.from_user.id, context)

    if not filtered_items:
        kb = [[InlineKeyboardButton("🔙 Back", callback_data="btn_categories")]]
        await q.message.reply_text("❌ <b>Out of Stock!</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    kb = []
    for item in filtered_items:
        kb.append([InlineKeyboardButton(f"{item['age']} — ₹{item['price']:.2f}", callback_data=f"buy_{item['id']}")])
    kb.append([InlineKeyboardButton("🔙 Back", callback_data="btn_categories")])

    await q.message.reply_text("<b>🛍️ Available Accounts:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def buy_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not await check_force_join(q.from_user.id, context):
        await send_force_join_msg(update, context)
        return

    item_id = int(q.data.split("_")[1])

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, category, age, price FROM stock WHERE id = ? AND is_sold = 0", (item_id,))
    item = c.fetchone()
    conn.close()

    if not item:
        await q.message.reply_text("❌ Account already sold!")
        return

    u_data = get_user_db(q.from_user.id)
    kb = [
        [InlineKeyboardButton("⚡ Confirm & Buy", callback_data=f"pay_{item['id']}")],
        [InlineKeyboardButton("🔙 Back", callback_data="btn_categories")]
    ]
    txt = f"<b>📦 Category:</b> {item['category'].capitalize()} Acc\n<b>⏳ Age:</b> {item['age']}\n<b>💵 Price:</b> ₹{item['price']:.2f}\n\n<b>Your Balance:</b> ₹{u_data['balance']:.2f}"
    
    await send_premium_sticker(q.from_user.id, context)
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def pay_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    if not await check_force_join(uid, context):
        await send_force_join_msg(update, context)
        return

    item_id = int(q.data.split("_")[1])

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, price, phone, session FROM stock WHERE id = ? AND is_sold = 0", (item_id,))
    item = c.fetchone()

    if not item:
        await q.message.reply_text("❌ Item already sold.")
        conn.close()
        return

    price, phone, session_str = item["price"], item["phone"], item["session"]
    u_data = get_user_db(uid)

    if u_data["balance"] < price:
        conn.close()
        kb = [[InlineKeyboardButton("💳 Deposit", callback_data="btn_add_bal")], [InlineKeyboardButton("🔙 Back", callback_data="btn_categories")]]
        await send_premium_sticker(uid, context)
        await q.message.reply_text(f"❌ <b>Insufficient Balance!</b>\nPrice: ₹{price:.2f}\nYour Balance: ₹{u_data['balance']:.2f}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    c.execute("UPDATE users SET balance = balance - ?, orders = orders + 1 WHERE uid = ?", (price, uid))
    c.execute("UPDATE stock SET is_sold = 1 WHERE id = ?", (item_id,))
    c.execute("INSERT INTO purchases (uid, item_id, phone, session) VALUES (?, ?, ?, ?)", (uid, item_id, phone, session_str))
    conn.commit()
    conn.close()

    kb = [[InlineKeyboardButton("📩 GET OTP NOW", callback_data=f"get_otp_{item_id}")]]
    txt = (
        f"🎉 <b>Purchase Successful!</b>\n\n"
        f"📱 <b>Phone Number:</b> <code>{phone}</code>\n\n"
        f"<i>Telegram App me ye number enter karein, phir niche <b>GET OTP NOW</b> button par click karein.</i>"
    )
    await send_premium_sticker(uid, context)
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

# --- LIVE AUTO OTP FETCHING ---

async def fetch_live_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    item_id = int(q.data.replace("get_otp_", ""))

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT session, phone FROM purchases WHERE item_id = ?", (item_id,))
    purchase = c.fetchone()
    conn.close()

    if not purchase:
        await q.message.reply_text("❌ Purchase record not found.")
        return

    session_str, phone = purchase["session"], purchase["phone"]
    msg_status = await q.message.reply_text("🔄 <b>Checking Telegram System (777000)...</b>", parse_mode="HTML")

    try:
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            await msg_status.edit_text("❌ <b>Session Expired / Logged Out!</b>\nYeh session expire ho gaya hai.")
            await client.disconnect()
            return

        otp_found = None
        async for message in client.iter_messages(777000, limit=10):
            if message.text:
                match = re.search(r'\b\d{5,6}\b', message.text)
                if match:
                    otp_found = match.group(0)
                    break

        await client.disconnect()

        await send_premium_sticker(q.from_user.id, context)

        if otp_found:
            kb = [[InlineKeyboardButton("📩 GET OTP AGAIN", callback_data=f"get_otp_{item_id}")]]
            await msg_status.edit_text(f"🔑 <b>YOUR LOGIN OTP:</b> <code>{otp_found}</code>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        else:
            kb = [[InlineKeyboardButton("🔄 TRY AGAIN", callback_data=f"get_otp_{item_id}")]]
            await msg_status.edit_text("❌ <b>OTP nahi mila!</b>\n\n1. App par number daal kar OTP request bhejo.\n2. Phir 5 sec baad yahan 'TRY AGAIN' dabao.", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

    except Exception as e:
        await msg_status.edit_text(f"⚠️ <b>Session Error:</b>\n<code>{str(e)}</code>")

async def user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    u = q.from_user
    u_data = get_user_db(u.id)

    txt = f"<b>👤 PROFILE INFO</b>\n\n• Name: {clean_html(u.first_name)}\n• User ID: <code>{u.id}</code>\n• Balance: ₹{u_data['balance']:.2f}\n• Orders: {u_data['orders']}"
    kb = [[InlineKeyboardButton("💳 Deposit Money", callback_data="btn_add_bal")], [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]]
    
    await send_premium_sticker(u.id, context)
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def deposit_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    txt = f"<b>💳 DEPOSIT / ADD MONEY</b>\n\n⚠️ <b>Minimum Deposit:</b> ₹{MIN_DEPOSIT}\n\nSelect Payment Method:"
    kb = [
        [InlineKeyboardButton("🖼️ UPI QR Code", callback_data="dep_qr"), InlineKeyboardButton("📱 UPI ID", callback_data="dep_upi")],
        [InlineKeyboardButton("🌐 Crypto (USDT)", callback_data="dep_crypto")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]
    ]
    await send_premium_sticker(q.from_user.id, context)
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def deposit_method_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    method = q.data

    kb = [
        [InlineKeyboardButton("📤 Send Payment Proof", url=f"https://t.me/{SUPPORT_USERNAME}")],
        [InlineKeyboardButton("🔙 Back to Deposit", callback_data="btn_add_bal")]
    ]

    if method == "dep_qr":
        txt = f"<b>🖼️ UPI QR CODE</b>\n\n⚠️ <b>Minimum Deposit:</b> ₹{MIN_DEPOSIT}\n\n👉 QR Link: {payment_settings['qr_url']}\n👉 UPI ID: <code>{payment_settings['upi']}</code>\n\n<i>Payment ke baad proof Admin <b>@{SUPPORT_USERNAME}</b> ko bhejeyin.</i>"
    elif method == "dep_upi":
        txt = f"<b>📱 UPI PAYMENT</b>\n\n⚠️ <b>Minimum Deposit:</b> ₹{MIN_DEPOSIT}\n\n<b>UPI ID:</b> <code>{payment_settings['upi']}</code>\n\n<i>Payment ke baad proof Admin <b>@{SUPPORT_USERNAME}</b> ko bhejeyin.</i>"
    elif method == "dep_crypto":
        txt = f"<b>🌐 CRYPTO PAYMENT</b>\n\n<b>Details:</b> <code>{payment_settings['crypto']}</code>\n\n<i>Payment TXID Admin <b>@{SUPPORT_USERNAME}</b> ko bhejeyin.</i>"

    await send_premium_sticker(q.from_user.id, context)
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def support_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    txt = f"<b>👨‍💻 CUSTOMER SUPPORT</b>\n\nContact support for help:\n\n👤 <b>Admin:</b> @{SUPPORT_USERNAME}"
    kb = [[InlineKeyboardButton("📩 Contact @tgprimesoul", url=f"https://t.me/{SUPPORT_USERNAME}")], [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]]
    
    await send_premium_sticker(q.from_user.id, context)
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

# --- ADMIN CONTROL PANEL ---

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        if update.message:
            await update.message.reply_text("❌ Unauthorized Access!")
        return

    curr_ch = get_setting("force_channel_id", "OFF")

    kb = [
        [InlineKeyboardButton("➕ Add Stock", callback_data="adm_panel_add"), InlineKeyboardButton("📊 View Stock", callback_data="adm_panel_view")],
        [InlineKeyboardButton(f"📢 Force Join: [{curr_ch}]", callback_data="adm_panel_fjoin")],
        [InlineKeyboardButton("❌ Close", callback_data="adm_panel_close")]
    ]
    txt = "<b>⚡ ADMIN CONTROL PANEL</b>\n\nSelect an action below:"
    
    await send_premium_sticker(user_id, context)
    
    if update.message:
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    else:
        await update.callback_query.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        await q.answer("Unauthorized!", show_alert=True)
        return
    await q.answer()

    data = q.data
    if data == "adm_panel_add":
        await add_stock_start(update, context)
    elif data == "adm_panel_view":
        await cmd_viewstock(update, context)
    elif data == "adm_panel_fjoin":
        kb = [
            [InlineKeyboardButton("❌ Turn Off Force Join", callback_data="fjoin_off")],
            [InlineKeyboardButton("🔙 Back to Admin", callback_data="btn_admin_menu")]
        ]
        curr_ch = get_setting("force_channel_id", "None")
        txt = (
            f"<b>📢 FORCE JOIN SETTINGS</b>\n\n"
            f"Current Channel: <code>{curr_ch}</code>\n\n"
            f"Naya channel set karne ke liye chat par Username/ID bhejein:\n"
            f"• Example: <code>@mychannel</code>\n"
            f"• Note: Bot ko channel me <b>Admin</b> banana zaroori hai!"
        )
        await send_premium_sticker(q.from_user.id, context)
        await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    elif data == "fjoin_off":
        set_setting("force_channel_id", "")
        await q.message.reply_text("✅ Force Join has been Turned OFF!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin", callback_data="btn_admin_menu")]]))
    elif data == "btn_admin_menu":
        await cmd_admin(update, context)
    elif data == "adm_panel_close":
        await q.message.delete()

# --- CONVERSATION FLOW FOR ADDING STOCK ---

async def add_stock_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    kb = [
        [InlineKeyboardButton("🔹 Normal Acc", callback_data="addcat_normal")],
        [InlineKeyboardButton("⭐ Premium Acc", callback_data="addcat_premium")],
        [InlineKeyboardButton("🛠️ Maked Acc", callback_data="addcat_maked")]
    ]
    txt = "<b>[Step 1/5] Select Account Category:</b>"
    
    await send_premium_sticker(update.effective_user.id, context)
    
    if update.callback_query:
        await update.callback_query.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    else:
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return WAITING_CAT

async def add_stock_category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    category = q.data.replace("addcat_", "")
    context.user_data["add_cat"] = category

    await q.message.reply_text(f"Category Selected: <b>{category.upper()}</b>\n\n<b>[Step 2/5]</b> Send Account Age (e.g. <code>2023 Aged</code>):", parse_mode="HTML")
    return WAITING_AGE

async def add_stock_age_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["add_age"] = update.message.text.strip()
    await update.message.reply_text("<b>[Step 3/5]</b> Enter Price in ₹ (Only numbers, e.g. <code>50</code>):", parse_mode="HTML")
    return WAITING_PRICE

async def add_stock_price_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        price = float(text)
        context.user_data["add_price"] = price
        await update.message.reply_text("<b>[Step 4/5]</b> Send Phone Number (e.g. <code>+919876543210</code>):", parse_mode="HTML")
        return WAITING_PHONE
    except ValueError:
        await update.message.reply_text("❌ Invalid price! Enter numbers only (e.g. 50):")
        return WAITING_PRICE

async def add_stock_phone_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["add_phone"] = update.message.text.strip()
    await update.message.reply_text("<b>[Step 5/5] NOW PASTE THE TELETHON STRING SESSION:</b>", parse_mode="HTML")
    return WAITING_SESSION

async def add_stock_session_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session_str = update.message.text.strip()
    cat = context.user_data.get("add_cat")
    age = context.user_data.get("add_age")
    price = context.user_data.get("add_price")
    phone = context.user_data.get("add_phone")

    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO stock (category, age, price, phone, session) VALUES (?, ?, ?, ?, ?)",
              (cat, age, price, phone, session_str))
    conn.commit()
    conn.close()

    context.user_data.clear()
    await send_premium_sticker(update.effective_user.id, context)
    await update.message.reply_text(f"✅ <b>STOCK SUCCESSFULLY ADDED!</b>\n\n• Category: {cat.upper()}\n• Age: {age}\n• Price: ₹{price}\n• Phone: <code>{phone}</code>", parse_mode="HTML")
    return ConversationHandler.END

async def cancel_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled stock adding process.")
    return ConversationHandler.END

# --- GENERAL ADMIN COMMANDS ---

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    text = update.message.text.strip()

    if text.startswith("@") or text.startswith("-100"):
        set_setting("force_channel_id", text)
        await update.message.reply_text(f"✅ <b>Force Join Updated!</b>\n\nNew Channel: <code>{text}</code>\n<i>Ensure Bot is Admin in this Channel!</i>", parse_mode="HTML")

async def cmd_addbal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        raw_text = update.message.text.replace("/addbal", "").strip()
        uid, amt = raw_text.split("|")
        update_balance_db(int(uid.strip()), float(amt.strip()))
        await send_premium_sticker(update.effective_user.id, context)
        await update.message.reply_text(f"✅ Added ₹{amt.strip()} to <code>{uid.strip()}</code>", parse_mode="HTML")
    except Exception:
        await update.message.reply_text("Format: <code>/addbal UserID | Amount</code>", parse_mode="HTML")

async def cmd_viewstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, category, age, price, phone FROM stock WHERE is_sold = 0")
    items = c.fetchall()
    conn.close()

    if not items:
        txt = "Store is currently empty."
    else:
        txt = "<b>📊 AVAILABLE STOCK:</b>\n\n"
        for i in items:
            txt += f"• ID: {i['id']} [{i['category'].upper()}] | Age: {i['age']} — ₹{i['price']}\n  Phone: <code>{i['phone']}</code>\n\n"
    
    await send_premium_sticker(update.effective_user.id, context)
    
    if update.message:
        await update.message.reply_text(txt, parse_mode="HTML")
    else:
        await update.callback_query.message.reply_text(txt, parse_mode="HTML")

def main():
    threading.Thread(target=run_flask, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    # User Routes
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start, pattern="^btn_main$"))
    app.add_handler(CallbackQueryHandler(show_categories, pattern="^btn_categories$"))
    app.add_handler(CallbackQueryHandler(category_stock_list, pattern="^cat_"))
    app.add_handler(CallbackQueryHandler(buy_confirm, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(pay_item, pattern="^pay_"))
    app.add_handler(CallbackQueryHandler(fetch_live_otp, pattern="^get_otp_"))
    app.add_handler(CallbackQueryHandler(user_profile, pattern="^btn_profile$"))
    app.add_handler(CallbackQueryHandler(deposit_info, pattern="^btn_add_bal$"))
    app.add_handler(CallbackQueryHandler(deposit_method_handler, pattern="^dep_"))
    app.add_handler(CallbackQueryHandler(support_info, pattern="^btn_support$"))

    # Admin Command Route
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("addbal", cmd_addbal))
    app.add_handler(CommandHandler("viewstock", cmd_viewstock))
    app.add_handler(CallbackQueryHandler(admin_panel_callback, pattern="^(adm_panel_|fjoin_off|btn_admin_menu)"))

    # Admin Conversation Handler for Stock Adding Wizard
    add_wizard = ConversationHandler(
        entry_points=[
            CommandHandler("add", add_stock_start),
            CallbackQueryHandler(add_stock_start, pattern="^adm_panel_add$")
        ],
        states={
            WAITING_CAT: [CallbackQueryHandler(add_stock_category_selected, pattern="^addcat_")],
            WAITING_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_stock_age_received)],
            WAITING_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_stock_price_received)],
            WAITING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_stock_phone_received)],
            WAITING_SESSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_stock_session_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel_wizard)],
    )

    app.add_handler(add_wizard)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))

    app.run_polling()

if __name__ == "__main__":
    main()
