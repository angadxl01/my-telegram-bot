import os
import re
import random
import string
import logging
import threading
import sqlite3
from flask import Flask
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.account import ResetAuthorizationRequest, GetAuthorizationsRequest
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

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8794925442:AAFIHaUAJM8ZXt2guEN7Lq2kKyTTKzECWqw
ADMIN_ID = 8895089247              # Aapka Numeric Telegram User ID
SUPPORT_USERNAME = "tgprimesoul"   # Support Username

API_ID = 36645562                   # my.telegram.org ka API_ID
API_HASH = "ccad405579d80b82492abbf4a7777907"    # my.telegram.org ka API_HASH

PREMIUM_STICKER_ID = "CAACAgIAAxkBAAE_YOUR_STICKER_FILE_ID_HERE"

MIN_DEPOSIT = 25.0
REFERRAL_BONUS = 5.0
# =======================================================

WAITING_CAT, WAITING_AGE, WAITING_PRICE, WAITING_PHONE, WAITING_SESSION = range(5)
WAITING_BROADCAST_MSG, WAITING_DEL_ID, WAITING_GIVEALL_AMT, WAITING_SET_CHNL, WAITING_REDEEM_CODE, WAITING_GEN_VOUCHER = range(10, 16)

# --- DATABASE ENGINE ---
DB_NAME = "store.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (uid INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0, orders INTEGER DEFAULT 0, referred_by INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0);""")
    c.execute("""CREATE TABLE IF NOT EXISTS stock (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, age TEXT, price REAL, phone TEXT, session TEXT, is_sold INTEGER DEFAULT 0);""")
    c.execute("""CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, item_id INTEGER, phone TEXT, session TEXT, price REAL, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP);""")
    c.execute("""CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, amount REAL, type TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP);""")
    c.execute("""CREATE TABLE IF NOT EXISTS vouchers (code TEXT PRIMARY KEY, amount REAL, is_used INTEGER DEFAULT 0);""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);""")
    
    # Default Requirement Channel Setting
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('req_channel', '')")
    conn.commit()
    conn.close()

init_db()

def get_setting(key):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row["value"] if row else ""

def set_setting(key, val):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(val)))
    conn.commit()
    conn.close()

def get_user_db(uid, ref_id=0):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT balance, orders, referred_by, is_banned FROM users WHERE uid = ?", (uid,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO users (uid, balance, orders, referred_by, is_banned) VALUES (?, 0.0, 0, ?, 0)", (uid, ref_id))
        conn.commit()
        conn.close()
        return {"balance": 0.0, "orders": 0, "referred_by": ref_id, "is_banned": 0}
    conn.close()
    return {"balance": row["balance"], "orders": row["orders"], "referred_by": row["referred_by"], "is_banned": row["is_banned"]}

def update_balance_db(uid, amt, txn_type="Deposit"):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE uid = ?", (amt, uid))
    c.execute("INSERT INTO transactions (uid, amount, type) VALUES (?, ?, ?)", (uid, amt, txn_type))
    conn.commit()
    conn.close()

def clean_html(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") if text else ""

# --- FORCE JOIN CHECKER ---
async def check_force_join(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    req_channel = get_setting("req_channel")
    if not req_channel:
        return True
    
    try:
        member = await context.bot.get_chat_member(chat_id=req_channel, user_id=user_id)
        if member.status in ["creator", "administrator", "member"]:
            return True
        return False
    except Exception:
        # If channel ID invalid or bot not admin
        return True

async def send_force_join_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req_channel = get_setting("req_channel")
    channel_url = f"https://t.me/{req_channel.replace('@', '')}"
    
    kb = [
        [InlineKeyboardButton("📢 Join Main Channel", url=channel_url)],
        [InlineKeyboardButton("✅ Verify & Continue", callback_data="btn_main")]
    ]
    txt = (
        "<b>⚠️ ACCESS RESTRICTED!</b>\n\n"
        "<i>To use this bot, you must join our official update channel first!</i>\n\n"
        "👉 Click the button below to join, then press <b>Verify & Continue</b>."
    )
    if update.callback_query:
        await update.callback_query.answer("⚠️ Please join our channel first!", show_alert=True)
        await update.callback_query.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    else:
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

# --- WEB SERVER ENGINE ---
web_app = Flask('')
@web_app.route('/')
def home():
    return "TG Marketplace Engine Running"

def run_flask():
    web_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- START & MENU ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    
    # Force Join Check
    if not await check_force_join(u.id, context):
        await send_force_join_msg(update, context)
        return

    u_data = get_user_db(u.id)

    if u_data["is_banned"] == 1:
        await update.effective_message.reply_text("🚫 <b>ACCOUNT BANNED!</b>\nContact Admin for appeal.", parse_mode="HTML")
        return

    # Referral Check
    if context.args and len(context.args) > 0:
        try:
            ref_id = int(context.args[0])
            if ref_id != u.id and u_data["referred_by"] == 0:
                update_balance_db(ref_id, REFERRAL_BONUS, "Referral Bonus")
                try:
                    await context.bot.send_message(chat_id=ref_id, text=f"🎉 <b>New Referral Joined!</b>\n💰 <code>+₹{REFERRAL_BONUS:.2f}</code> added to your balance.", parse_mode="HTML")
                except Exception: pass
        except Exception: pass

    kb = [
        [InlineKeyboardButton("🛒 BROWSE STORE", callback_data="btn_categories")],
        [InlineKeyboardButton("👤 Profile & Wallet", callback_data="btn_profile"), InlineKeyboardButton("💳 Add Balance", callback_data="btn_add_bal")],
        [InlineKeyboardButton("🎁 Redeem Voucher", callback_data="btn_redeem"), InlineKeyboardButton("📢 Earn Money", callback_data="btn_refer")],
        [InlineKeyboardButton("👨‍💻 Customer Support", callback_data="btn_support")]
    ]
    
    txt = (
        f"<b>💎 WELCOME TO TG STORE 💎</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>👤 User ID:</b> <code>{u.id}</code>\n"
        f"<b>💰 Wallet Balance:</b> <code>₹{u_data['balance']:.2f}</code>\n"
        f"<b>🛒 Completed Orders:</b> <code>{u_data['orders']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>⚡ Premium & Verified Telegram Accounts with Instant OTP Engine.</i>"
    )

    if update.message:
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    else:
        await update.callback_query.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

# --- CATEGORY & STOCK SELECTION ---
async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    if not await check_force_join(q.from_user.id, context):
        await send_force_join_msg(update, context)
        return

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT category, COUNT(*) as cnt FROM stock WHERE is_sold = 0 GROUP BY category")
    stock_counts = {row["category"]: row["cnt"] for row in c.fetchall()}
    conn.close()

    normal_cnt = stock_counts.get("normal", 0)
    premium_cnt = stock_counts.get("premium", 0)
    maked_cnt = stock_counts.get("maked", 0)

    kb = [
        [InlineKeyboardButton(f"🔹 Normal Accounts [{normal_cnt}]", callback_data="cat_normal")],
        [InlineKeyboardButton(f"⭐ Premium Accounts [{premium_cnt}]", callback_data="cat_premium")],
        [InlineKeyboardButton(f"🛠️ Maked Accounts [{maked_cnt}]", callback_data="cat_maked")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]
    ]
    
    txt = (
        "<b>📂 SELECT CATEGORY</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Choose an account category to see available items:"
    )
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def category_stock_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cat_type = q.data.replace("cat_", "").lower()

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, age, price FROM stock WHERE category = ? AND is_sold = 0", (cat_type,))
    filtered_items = c.fetchall()
    conn.close()

    if not filtered_items:
        kb = [[InlineKeyboardButton("🔙 Back to Categories", callback_data="btn_categories")]]
        await q.message.reply_text("<b>❌ Out of Stock!</b>\n<i>Check back later or choose another category.</i>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    kb = []
    for item in filtered_items:
        kb.append([InlineKeyboardButton(f"⚡ {item['age']} — ₹{item['price']:.2f}", callback_data=f"buy_{item['id']}")])
    kb.append([InlineKeyboardButton("🔙 Back", callback_data="btn_categories")])

    await q.message.reply_text(f"<b>🛍️ AVAILABLE [{cat_type.upper()}] ACCOUNTS:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def buy_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    item_id = int(q.data.split("_")[1])

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, category, age, price FROM stock WHERE id = ? AND is_sold = 0", (item_id,))
    item = c.fetchone()
    conn.close()

    if not item:
        await q.message.reply_text("<b>❌ Account already sold!</b>", parse_mode="HTML")
        return

    u_data = get_user_db(q.from_user.id)
    kb = [
        [InlineKeyboardButton("⚡ CONFIRM & PURCHASE NOW", callback_data=f"pay_{item['id']}")],
        [InlineKeyboardButton("🔙 Back", callback_data="btn_categories")]
    ]
    txt = (
        f"<b>🛒 ORDER CONFIRMATION</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>📦 Category:</b> {item['category'].capitalize()} Acc\n"
        f"<b>⏳ Account Age:</b> {item['age']}\n"
        f"<b>💵 Price:</b> ₹{item['price']:.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>💳 Your Wallet Balance:</b> ₹{u_data['balance']:.2f}\n"
    )
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def pay_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    item_id = int(q.data.split("_")[1])

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, category, price, phone, session FROM stock WHERE id = ? AND is_sold = 0", (item_id,))
    item = c.fetchone()

    if not item:
        await q.message.reply_text("<b>❌ Item already sold!</b>", parse_mode="HTML")
        conn.close()
        return

    price, phone, session_str, category = item["price"], item["phone"], item["session"], item["category"]
    u_data = get_user_db(uid)

    if u_data["balance"] < price:
        needed = price - u_data["balance"]
        conn.close()
        kb = [[InlineKeyboardButton("💳 Top Up Wallet", callback_data="btn_add_bal")], [InlineKeyboardButton("🔙 Back", callback_data="btn_categories")]]
        await q.message.reply_text(f"<b>❌ INSUFFICIENT BALANCE!</b>\n\nYou need <b>₹{needed:.2f}</b> more to complete this purchase.", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    c.execute("UPDATE users SET balance = balance - ?, orders = orders + 1 WHERE uid = ?", (price, uid))
    c.execute("UPDATE stock SET is_sold = 1 WHERE id = ?", (item_id,))
    c.execute("INSERT INTO purchases (uid, item_id, phone, session, price) VALUES (?, ?, ?, ?, ?)", (uid, item_id, phone, session_str, price))
    c.execute("INSERT INTO transactions (uid, amount, type) VALUES (?, ?, ?)", (uid, -price, f"Bought {category.capitalize()} Acc"))
    conn.commit()
    conn.close()

    kb = [
        [InlineKeyboardButton("📩 GET OTP NOW", callback_data=f"get_otp_{item_id}")],
        [InlineKeyboardButton("🗑️ Terminate Active Sessions", callback_data=f"term_sess_{item_id}")]
    ]
    txt = (
        f"<b>🎉 PURCHASE SUCCESSFUL!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>📱 Phone Number:</b> <code>{phone}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>📌 Instructions:</b>\n"
        f"1. Enter phone number in Telegram App.\n"
        f"2. Click <b>GET OTP NOW</b> below to fetch code.\n"
        f"3. After login, click <b>Terminate Active Sessions</b> to remove bot access!"
    )
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
        await q.message.reply_text("<b>❌ Purchase record not found.</b>", parse_mode="HTML")
        return

    session_str = purchase["session"]
    msg_status = await q.message.reply_text("<code>🔄 Accessing Telegram OTP System...</code>", parse_mode="HTML")

    try:
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            await msg_status.edit_text("<b>❌ Session Expired / Logged Out!</b>", parse_mode="HTML")
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

        kb = [
            [InlineKeyboardButton("📩 REFRESH OTP", callback_data=f"get_otp_{item_id}")],
            [InlineKeyboardButton("🗑️ Terminate Active Sessions", callback_data=f"term_sess_{item_id}")]
        ]

        if otp_found:
            await msg_status.edit_text(f"<b>🔑 YOUR LOGIN OTP:</b> <code>{otp_found}</code>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        else:
            await msg_status.edit_text("<b>⌛ OTP NOT RECEIVED YET!</b>\n<i>Please request code in Telegram App first, then click Refresh.</i>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

    except Exception as e:
        await msg_status.edit_text(f"⚠️ <b>Error:</b> <code>{str(e)}</code>", parse_mode="HTML")

# --- TERMINATE SESSIONS LOGIC ---
async def terminate_other_sessions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    item_id = int(q.data.replace("term_sess_", ""))

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT session FROM purchases WHERE item_id = ?", (item_id,))
    purchase = c.fetchone()
    conn.close()

    if not purchase:
        await q.message.reply_text("<b>❌ Purchase record not found.</b>", parse_mode="HTML")
        return

    session_str = purchase["session"]
    msg_status = await q.message.reply_text("<code>🔄 Terminating active sessions & removing bot access...</code>", parse_mode="HTML")

    try:
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            await msg_status.edit_text("<b>❌ Session already invalid or logged out!</b>", parse_mode="HTML")
            await client.disconnect()
            return

        authorizations = await client(GetAuthorizationsRequest())
        
        for auth in authorizations.authorizations:
            if not auth.current:
                try:
                    await client(ResetAuthorizationRequest(hash=auth.hash))
                except Exception:
                    pass

        await client.log_out()
        await client.disconnect()

        kb = [[InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]]
        await msg_status.edit_text(
            "<b>✅ SESSIONS TERMINATED SUCCESSFULLY!</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔒 <b>Bot Access Revoked:</b> Bot session deleted. You are now the <b>Sole Owner</b> of this Telegram Account!",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="HTML"
        )

    except Exception as e:
        await msg_status.edit_text(
            f"<b>⚠️ Error:</b> <code>{str(e)}</code>\n\n"
            "<i>Note: Telegram prevents session termination on fresh login devices for 24 hours.</i>",
            parse_mode="HTML"
        )

# --- REDEEM VOUCHER WIZARD ---
async def redeem_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("<b>🎁 Enter Voucher Code:</b>\n<i>Paste your promotional code below.</i>", parse_mode="HTML")
    return WAITING_REDEEM_CODE

async def redeem_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    uid = update.effective_user.id

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT amount, is_used FROM vouchers WHERE code = ?", (code,))
    v = c.fetchone()

    if not v:
        await update.message.reply_text("<b>❌ Invalid Voucher Code!</b>", parse_mode="HTML")
        conn.close()
        return ConversationHandler.END

    if v["is_used"] == 1:
        await update.message.reply_text("<b>⚠️ This Voucher has already been redeemed!</b>", parse_mode="HTML")
        conn.close()
        return ConversationHandler.END

    amt = v["amount"]
    c.execute("UPDATE vouchers SET is_used = 1 WHERE code = ?", (code,))
    conn.commit()
    conn.close()

    update_balance_db(uid, amt, "Voucher Redeem")
    await update.message.reply_text(f"<b>🎉 VOUCHER REDEEMED!</b>\n\n💰 <b>₹{amt:.2f}</b> added to your wallet!", parse_mode="HTML")
    return ConversationHandler.END

# --- PROFILE & HISTORY ---
async def user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    u = q.from_user
    u_data = get_user_db(u.id)

    txt = (
        f"<b>👤 USER WALLET & PROFILE</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>• Name:</b> {clean_html(u.first_name)}\n"
        f"<b>• User ID:</b> <code>{u.id}</code>\n"
        f"<b>• Balance:</b> ₹{u_data['balance']:.2f}\n"
        f"<b>• Orders Completed:</b> {u_data['orders']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )
    kb = [
        [InlineKeyboardButton("📜 Order History", callback_data="btn_history_orders"), InlineKeyboardButton("💸 Txn Log", callback_data="btn_history_txns")],
        [InlineKeyboardButton("💳 Add Balance", callback_data="btn_add_bal")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]
    ]
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def view_history_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT phone, price, date FROM purchases WHERE uid = ? ORDER BY id DESC LIMIT 5", (q.from_user.id,))
    rows = c.fetchall()
    conn.close()

    txt = "<b>🛍️ LAST 5 PURCHASES:</b>\n━━━━━━━━━━━━━━━━━━━━━━\n" + ("\n".join([f"• <code>{r['phone']}</code> | ₹{r['price']} | {r['date']}" for r in rows]) if rows else "No orders yet.")
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Profile", callback_data="btn_profile")]]), parse_mode="HTML")

async def view_history_txns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT amount, type, date FROM transactions WHERE uid = ? ORDER BY id DESC LIMIT 5", (q.from_user.id,))
    rows = c.fetchall()
    conn.close()

    txt = "<b>💸 LAST 5 TRANSACTIONS:</b>\n━━━━━━━━━━━━━━━━━━━━━━\n" + ("\n".join([f"• ₹{r['amount']} ({r['type']}) - {r['date']}" for r in rows]) if rows else "No transactions yet.")
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Profile", callback_data="btn_profile")]]), parse_mode="HTML")

async def refer_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    bot_obj = await context.bot.get_me()
    txt = (
        f"<b>📢 REFER & EARN PROGRAM</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Invite friends and earn <b>₹{REFERRAL_BONUS:.2f}</b> on every user who joins!\n\n"
        f"<b>🔗 Your Referral Link:</b>\n"
        f"<code>https://t.me/{bot_obj.username}?start={q.from_user.id}</code>"
    )
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]]), parse_mode="HTML")

async def deposit_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    txt = (
        f"<b>💳 ADD WALLET BALANCE</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>• UPI ID:</b> <code>tgprimesoul@upi</code>\n"
        f"<b>• Min Deposit:</b> ₹{MIN_DEPOSIT}\n\n"
        f"<i>Send payment to UPI ID and submit screenshot proof to Admin below for manual approval.</i>"
    )
    kb = [[InlineKeyboardButton("📤 Send Payment Proof", url=f"https://t.me/{SUPPORT_USERNAME}")], [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]]
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def support_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(f"<b>👨‍💻 CUSTOMER SUPPORT:</b> @{SUPPORT_USERNAME}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]]), parse_mode="HTML")

# --- ULTRA PREMIUM ADMIN CONTROL PANEL ---
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return

    req_ch = get_setting("req_channel") or "Not Set ❌"

    kb = [
        [InlineKeyboardButton("📊 Dashboard Stats", callback_data="adm_stats"), InlineKeyboardButton("➕ Add Stock", callback_data="adm_panel_add")],
        [InlineKeyboardButton("📦 View Stock", callback_data="adm_panel_view"), InlineKeyboardButton("🗑️ Delete Stock", callback_data="adm_del_stock")],
        [InlineKeyboardButton("📢 Broadcast Msg", callback_data="adm_panel_broadcast"), InlineKeyboardButton("🎁 Mass Giveaway", callback_data="adm_giveall")],
        [InlineKeyboardButton(f"⚙️ Requirement Channel ({req_ch})", callback_data="adm_set_channel")],
        [InlineKeyboardButton("🎟️ Generate Voucher", callback_data="adm_gen_voucher")],
        [InlineKeyboardButton("❌ Close Panel", callback_data="adm_panel_close")]
    ]
    txt = (
        "<b>⚡ SAAS ADMIN CONTROL PANEL ⚡</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>Admin Commands Quick Reference:</b>\n"
        "• <code>/addbal UserID | Amt</code> - Add Balance\n"
        "• <code>/cutbal UserID | Amt</code> - Deduct Balance\n"
        "• <code>/ban UserID</code> | <code>/unban UserID</code>\n"
        "• <code>/genvoucher Code Amount</code> - Create Voucher"
    )
    if update.message:
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    else:
        await update.callback_query.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as total_u FROM users")
    tot_users = c.fetchone()["total_u"]
    c.execute("SELECT COUNT(*) as total_o, SUM(price) as rev FROM purchases")
    p_data = c.fetchone()
    tot_orders = p_data["total_o"] or 0
    revenue = p_data["rev"] or 0.0
    c.execute("SELECT COUNT(*) as active FROM stock WHERE is_sold = 0")
    active_stock = c.fetchone()["active"]
    conn.close()

    txt = (
        f"<b>📊 STORE LIVE ANALYTICS</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>Total Registered Users:</b> {tot_users}\n"
        f"🛒 <b>Total Orders Completed:</b> {tot_orders}\n"
        f"💰 <b>Total Store Revenue:</b> ₹{revenue:.2f}\n"
        f"📦 <b>In-Stock Inventory:</b> {active_stock} items"
    )
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin", callback_data="btn_admin_menu")]]), parse_mode="HTML")

# --- ADMIN SET CHANNEL WIZARD ---
async def set_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("<b>📢 Send Requirement Channel Username (e.g. @MyChannel):</b>\n<i>Make sure the bot is added as Admin in the channel!</i>", parse_mode="HTML")
    return WAITING_SET_CHNL

async def set_channel_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ch_name = update.message.text.strip()
    if not ch_name.startswith("@"):
        ch_name = "@" + ch_name
    set_setting("req_channel", ch_name)
    await update.message.reply_text(f"<b>✅ Requirement Channel Updated to:</b> {ch_name}", parse_mode="HTML")
    return ConversationHandler.END

# --- ADMIN VOUCHER GENERATOR ---
async def gen_voucher_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("<b>🎟️ Enter Voucher Amount (in ₹):</b>", parse_mode="HTML")
    return WAITING_GEN_VOUCHER

async def gen_voucher_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amt = float(update.message.text.strip())
        code = "TG-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO vouchers (code, amount) VALUES (?, ?)", (code, amt))
        conn.commit()
        conn.close()

        await update.message.reply_text(f"<b>✅ VOUCHER CREATED!</b>\n\n🎟️ <b>Code:</b> <code>{code}</code>\n💵 <b>Amount:</b> ₹{amt:.2f}", parse_mode="HTML")
    except Exception:
        await update.message.reply_text("<b>❌ Invalid Amount!</b>", parse_mode="HTML")
    return ConversationHandler.END

# --- ADMIN DELETION & GIVEAWAY WIZARDS ---
async def admin_del_stock_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("🗑️ <b>Send the Stock ID you want to DELETE:</b>", parse_mode="HTML")
    return WAITING_DEL_ID

async def admin_del_stock_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sid = int(update.message.text.strip())
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM stock WHERE id = ?", (sid,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"<b>✅ Stock ID <code>{sid}</code> deleted!</b>", parse_mode="HTML")
    except Exception:
        await update.message.reply_text("❌ Invalid Stock ID!")
    return ConversationHandler.END

async def admin_giveall_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("🎁 <b>Enter amount to give to ALL USERS:</b>", parse_mode="HTML")
    return WAITING_GIVEALL_AMT

async def admin_giveall_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amt = float(update.message.text.strip())
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET balance = balance + ?", (amt,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"<b>🎉 Added ₹{amt} bonus to ALL USERS!</b>", parse_mode="HTML")
    except Exception:
        await update.message.reply_text("❌ Invalid Amount!")
    return ConversationHandler.END

# --- BAN / UNBAN & BAL COMMANDS ---
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        uid = int(update.message.text.replace("/ban", "").strip())
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned = 1 WHERE uid = ?", (uid,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"🚫 User <code>{uid}</code> BANNED!", parse_mode="HTML")
    except Exception:
        await update.message.reply_text("Format: <code>/ban UserID</code>", parse_mode="HTML")

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        uid = int(update.message.text.replace("/unban", "").strip())
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET is_banned = 0 WHERE uid = ?", (uid,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ User <code>{uid}</code> UNBANNED!", parse_mode="HTML")
    except Exception:
        await update.message.reply_text("Format: <code>/unban UserID</code>", parse_mode="HTML")

async def cmd_addbal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        uid, amt = update.message.text.replace("/addbal", "").strip().split("|")
        update_balance_db(int(uid.strip()), float(amt.strip()), "Admin Added")
        await update.message.reply_text(f"✅ Added ₹{amt.strip()} to <code>{uid.strip()}</code>", parse_mode="HTML")
    except Exception:
        await update.message.reply_text("Format: <code>/addbal UserID | Amount</code>", parse_mode="HTML")

async def cmd_cutbal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        uid, amt = update.message.text.replace("/cutbal", "").strip().split("|")
        update_balance_db(int(uid.strip()), -float(amt.strip()), "Admin Cut")
        await update.message.reply_text(f"✂️ Deducted ₹{amt.strip()} from <code>{uid.strip()}</code>", parse_mode="HTML")
    except Exception:
        await update.message.reply_text("Format: <code>/cutbal UserID | Amount</code>", parse_mode="HTML")

async def cmd_viewstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, category, age, price, phone FROM stock WHERE is_sold = 0")
    items = c.fetchall()
    conn.close()

    txt = "<b>📊 INVENTORY LIST:</b>\n━━━━━━━━━━━━━━━━━━━━━━\n" + ("\n".join([f"• ID: {i['id']} [{i['category'].upper()}] | {i['age']} - ₹{i['price']} | <code>{i['phone']}</code>" for i in items]) if items else "Stock is empty.")
    await update.effective_message.reply_text(txt, parse_mode="HTML")

# --- BROADCAST WIZARD ---
async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("📢 <b>Send broadcast message:</b>", parse_mode="HTML")
    return WAITING_BROADCAST_MSG

async def admin_broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT uid FROM users WHERE is_banned = 0")
    users = c.fetchall()
    conn.close()

    sent = 0
    for u in users:
        try:
            await context.bot.copy_message(chat_id=u["uid"], from_chat_id=update.effective_chat.id, message_id=update.message.message_id)
            sent += 1
        except Exception: pass

    await update.message.reply_text(f"<b>✅ Broadcast Sent to {sent} users!</b>", parse_mode="HTML")
    return ConversationHandler.END

# --- STOCK ADDING WIZARD ---
async def add_stock_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🔹 Normal", callback_data="addcat_normal")], [InlineKeyboardButton("⭐ Premium", callback_data="addcat_premium")], [InlineKeyboardButton("🛠️ Maked", callback_data="addcat_maked")]]
    await update.effective_message.reply_text("<b>[Step 1/5] Select Category:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    return WAITING_CAT

async def add_stock_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["add_cat"] = q.data.replace("addcat_", "")
    await q.message.reply_text("<b>[Step 2/5]</b> Send Account Age:", parse_mode="HTML")
    return WAITING_AGE

async def add_stock_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["add_age"] = update.message.text.strip()
    await update.message.reply_text("<b>[Step 3/5]</b> Enter Price in ₹:", parse_mode="HTML")
    return WAITING_PRICE

async def add_stock_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["add_price"] = float(update.message.text.strip())
        await update.message.reply_text("<b>[Step 4/5]</b> Send Phone Number:", parse_mode="HTML")
        return WAITING_PHONE
    except ValueError:
        return WAITING_PRICE

async def add_stock_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["add_phone"] = update.message.text.strip()
    await update.message.reply_text("<b>[Step 5/5] NOW PASTE STRING SESSION:</b>", parse_mode="HTML")
    return WAITING_SESSION

async def add_stock_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cat, age, price, phone = context.user_data.get("add_cat"), context.user_data.get("add_age"), context.user_data.get("add_price"), context.user_data.get("add_phone")
    session_str = update.message.text.strip()

    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO stock (category, age, price, phone, session) VALUES (?, ?, ?, ?, ?)", (cat, age, price, phone, session_str))
    conn.commit()
    conn.close()

    await update.message.reply_text("<b>✅ NEW STOCK ADDED SUCCESSFULLY!</b>", parse_mode="HTML")
    return ConversationHandler.END

async def cancel_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Wizard Cancelled.")
    return ConversationHandler.END

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
    app.add_handler(CallbackQueryHandler(terminate_other_sessions, pattern="^term_sess_"))
    app.add_handler(CallbackQueryHandler(user_profile, pattern="^btn_profile$"))
    app.add_handler(CallbackQueryHandler(view_history_orders, pattern="^btn_history_orders$"))
    app.add_handler(CallbackQueryHandler(view_history_txns, pattern="^btn_history_txns$"))
    app.add_handler(CallbackQueryHandler(refer_info, pattern="^btn_refer$"))
    app.add_handler(CallbackQueryHandler(deposit_info, pattern="^btn_add_bal$"))
    app.add_handler(CallbackQueryHandler(support_info, pattern="^btn_support$"))

    # Admin Commands
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("addbal", cmd_addbal))
    app.add_handler(CommandHandler("cutbal", cmd_cutbal))
    app.add_handler(CommandHandler("viewstock", cmd_viewstock))

    # Admin Callbacks
    app.add_handler(CallbackQueryHandler(cmd_admin, pattern="^(adm_panel_close|btn_admin_menu)$"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^adm_stats$"))
    app.add_handler(CallbackQueryHandler(cmd_viewstock, pattern="^adm_panel_view$"))

    # Conversation Wizards
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(redeem_start, pattern="^btn_redeem$")],
        states={WAITING_REDEEM_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, redeem_finish)]},
        fallbacks=[CommandHandler("cancel", cancel_wizard)],
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(set_channel_start, pattern="^adm_set_channel$")],
        states={WAITING_SET_CHNL: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_channel_finish)]},
        fallbacks=[CommandHandler("cancel", cancel_wizard)],
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(gen_voucher_start, pattern="^adm_gen_voucher$")],
        states={WAITING_GEN_VOUCHER: [MessageHandler(filters.TEXT & ~filters.COMMAND, gen_voucher_finish)]},
        fallbacks=[CommandHandler("cancel", cancel_wizard)],
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("add", add_stock_start), CallbackQueryHandler(add_stock_start, pattern="^adm_panel_add$")],
        states={
            WAITING_CAT: [CallbackQueryHandler(add_stock_cat, pattern="^addcat_")],
            WAITING_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_stock_age)],
            WAITING_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_stock_price)],
            WAITING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_stock_phone)],
            WAITING_SESSION: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_stock_session)],
        },
        fallbacks=[CommandHandler("cancel", cancel_wizard)],
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_broadcast_start, pattern="^adm_panel_broadcast$")],
        states={WAITING_BROADCAST_MSG: [MessageHandler(filters.ALL & ~filters.COMMAND, admin_broadcast_send)]},
        fallbacks=[CommandHandler("cancel", cancel_wizard)],
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_del_stock_start, pattern="^adm_del_stock$")],
        states={WAITING_DEL_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_del_stock_finish)]},
        fallbacks=[CommandHandler("cancel", cancel_wizard)],
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_giveall_start, pattern="^adm_giveall$")],
        states={WAITING_GIVEALL_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_giveall_finish)]},
        fallbacks=[CommandHandler("cancel", cancel_wizard)],
    ))

    app.run_polling()

if __name__ == "__main__":
    main()
