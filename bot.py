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
BOT_TOKEN = "8715769463:AAGuis4-gd9vF0Tew1fKGpdVCgtpioqX5bU"
MAIN_ADMIN_ID = 8895089247         # Main Numeric Admin ID
SUPPORT_USERNAME = "tgprimesoul"   # Support Username

API_ID = 36645562                   # my.telegram.org ka API_ID
API_HASH = "ccad405579d80b82492abbf4a7777907"    # my.telegram.org ka API_HASH

MIN_DEPOSIT = 25.0
REFERRAL_BONUS = 5.0
UPI_ID = "angadxl@fam"
# =======================================================

WAITING_CAT, WAITING_AGE, WAITING_PRICE, WAITING_PHONE, WAITING_SESSION = range(5)
WAITING_BROADCAST_MSG, WAITING_DEL_ID, WAITING_GIVEALL_AMT, WAITING_SET_CHNL, WAITING_REDEEM_CODE, WAITING_GEN_VOUCHER = range(10, 16)
WAITING_PROOF_AMT, WAITING_PROOF_SS = range(20, 22)

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
    c.execute("""CREATE TABLE IF NOT EXISTS admins (uid INTEGER PRIMARY KEY);""")
    c.execute("""CREATE TABLE IF NOT EXISTS deposits (txnid TEXT PRIMARY KEY, uid INTEGER, amount REAL, status TEXT DEFAULT 'PENDING', date TIMESTAMP DEFAULT CURRENT_TIMESTAMP);""")
    
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('req_channel', '')")
    c.execute("INSERT OR IGNORE INTO admins (uid) VALUES (?)", (MAIN_ADMIN_ID,))
    conn.commit()
    conn.close()

init_db()

def is_admin(uid: int) -> bool:
    if uid == MAIN_ADMIN_ID:
        return True
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT uid FROM admins WHERE uid = ?", (uid,))
    row = c.fetchone()
    conn.close()
    return True if row else False

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
        return True

async def send_force_join_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req_channel = get_setting("req_channel")
    channel_url = "https://t.me/Soulidsssbot"
    kb = [
        [InlineKeyboardButton("📢 Join Main Channel", url=channel_url)],
        [InlineKeyboardButton("✅ Verify & Continue", callback_data="btn_main")]
    ]
    txt = (
        "<b>⚠️ ACCESS RESTRICTED!</b>\n\n"
        "<i>To use this bot, you must join our official channel first!</i>\n\n"
        "👉 Click below to join, then press <b>Verify & Continue</b>."
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
    return "TG Store Engine Live"

def run_flask():
    web_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- START & MENU ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    
    if not await check_force_join(u.id, context):
        await send_force_join_msg(update, context)
        return

    u_data = get_user_db(u.id)

    if u_data["is_banned"] == 1:
        await update.effective_message.reply_text("🚫 <b>ACCOUNT BANNED!</b>", parse_mode="HTML")
        return

    if context.args and len(context.args) > 0:
        try:
            ref_id = int(context.args[0])
            if ref_id != u.id and u_data["referred_by"] == 0:
                update_balance_db(ref_id, REFERRAL_BONUS, "Referral Bonus")
                try:
                    await context.bot.send_message(chat_id=ref_id, text=f"🎉 <b>New Referral!</b>\n💰 <code>+₹{REFERRAL_BONUS:.2f}</code> added.", parse_mode="HTML")
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
        f"<b>🛒 Orders:</b> <code>{u_data['orders']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>⚡ High Quality Telegram Accounts with Instant OTP Engine.</i>"
    )

    if update.message:
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    else:
        await update.callback_query.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

# --- CATEGORIES & PURCHASES ---
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
    
    txt = "<b>📂 SELECT CATEGORY:</b>"
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
        kb = [[InlineKeyboardButton("🔙 Back", callback_data="btn_categories")]]
        await q.message.reply_text("<b>❌ Out of Stock!</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
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
        f"<b>💳 Balance:</b> ₹{u_data['balance']:.2f}\n"
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
        await q.message.reply_text(f"<b>❌ INSUFFICIENT BALANCE!</b>\nNeed <b>₹{needed:.2f}</b> more.", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
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
        f"<b>📌 Steps:</b>\n"
        f"1. Enter number in Telegram App.\n"
        f"2. Click <b>GET OTP NOW</b>.\n"
        f"3. After login, click <b>Terminate Active Sessions</b>."
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
    msg_status = await q.message.reply_text("<code>🔄 Fetching OTP...</code>", parse_mode="HTML")

    try:
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            await msg_status.edit_text("<b>❌ Session Expired!</b>", parse_mode="HTML")
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
            await msg_status.edit_text(f"<b>🔑 YOUR OTP:</b> <code>{otp_found}</code>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        else:
            await msg_status.edit_text("<b>⌛ OTP NOT RECEIVED YET!</b>\nRequest code in Telegram first.", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

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
    msg_status = await q.message.reply_text("<code>🔄 Terminating sessions...</code>", parse_mode="HTML")

    try:
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            await msg_status.edit_text("<b>❌ Session already invalid!</b>", parse_mode="HTML")
            await client.disconnect()
            return

        authorizations = await client(GetAuthorizationsRequest())
        
        for auth in authorizations.authorizations:
            if not auth.current:
                try:
                    await client(ResetAuthorizationRequest(hash=auth.hash))
                except Exception: pass

        await client.log_out()
        await client.disconnect()

        kb = [[InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]]
        await msg_status.edit_text(
            "<b>✅ SESSIONS TERMINATED!</b>\n\n"
            "🔒 <b>Bot Session Closed:</b> I no longer have access to this Telegram account.",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="HTML"
        )

    except Exception as e:
        await msg_status.edit_text(f"<b>⚠️ Error:</b> <code>{str(e)}</code>", parse_mode="HTML")

# --- PAYMENT & SS UPLOAD SYSTEM ---
async def deposit_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    txt = (
        f"<b>💳 ADD MONEY TO WALLET</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>• UPI ID:</b> <code>{UPI_ID}</code>\n"
        f"<b>• Min Deposit:</b> ₹{MIN_DEPOSIT}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Pay via PhonePe/GPay/Paytm and click below to upload proof.</i>"
    )
    kb = [
        [InlineKeyboardButton("📤 Upload Payment Screenshot", callback_data="btn_upload_ss")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]
    ]
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def upload_ss_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(f"<b>💵 Enter the exact Amount paid (Min ₹{MIN_DEPOSIT}):</b>", parse_mode="HTML")
    return WAITING_PROOF_AMT

async def upload_ss_amt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amt = float(update.message.text.strip())
        if amt < MIN_DEPOSIT:
            await update.message.reply_text(f"<b>❌ Minimum Deposit is ₹{MIN_DEPOSIT}! Try again:</b>", parse_mode="HTML")
            return WAITING_PROOF_AMT

        context.user_data["deposit_amt"] = amt
        await update.message.reply_text("<b>📸 Send Payment Screenshot now:</b>", parse_mode="HTML")
        return WAITING_PROOF_SS
    except ValueError:
        await update.message.reply_text("<b>❌ Enter valid numeric amount!</b>", parse_mode="HTML")
        return WAITING_PROOF_AMT

async def upload_ss_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("<b>❌ Please send a valid Screenshot/Photo!</b>", parse_mode="HTML")
        return WAITING_PROOF_SS

    u = update.effective_user
    amt = context.user_data.get("deposit_amt")
    txnid = "TXN" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    photo_file_id = update.message.photo[-1].file_id

    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO deposits (txnid, uid, amount) VALUES (?, ?, ?)", (txnid, u.id, amt))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"<b>✅ PAYMENT PROOF SUBMITTED!</b>\n\n"
        f"<b>• Txn ID:</b> <code>{txnid}</code>\n"
        f"<b>• Amount:</b> ₹{amt:.2f}\n"
        f"<b>• Status:</b> Pending Admin Approval ⏳",
        parse_mode="HTML"
    )

    admin_kb = [
        [
            InlineKeyboardButton("✅ APPROVE", callback_data=f"dep_appr_{txnid}"),
            InlineKeyboardButton("❌ REJECT", callback_data=f"dep_rej_{txnid}")
        ]
    ]

    admin_txt = (
        f"<b>📥 NEW PAYMENT PROOF</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>• User:</b> {clean_html(u.first_name)} (<code>{u.id}</code>)\n"
        f"<b>• Txn ID:</b> <code>{txnid}</code>\n"
        f"<b>• Amount:</b> ₹{amt:.2f}"
    )

    try:
        await context.bot.send_photo(chat_id=MAIN_ADMIN_ID, photo=photo_file_id, caption=admin_txt, reply_markup=InlineKeyboardMarkup(admin_kb), parse_mode="HTML")
    except Exception: pass

    return ConversationHandler.END

async def admin_handle_deposit_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    if not is_admin(q.from_user.id):
        return

    data = q.data
    txnid = data.split("_")[2]

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT uid, amount, status FROM deposits WHERE txnid = ?", (txnid,))
    dep = c.fetchone()

    if not dep:
        await q.message.reply_text("<b>❌ Transaction record not found!</b>", parse_mode="HTML")
        conn.close()
        return

    if dep["status"] != "PENDING":
        await q.message.reply_text(f"<b>⚠️ Transaction already {dep['status']}!</b>", parse_mode="HTML")
        conn.close()
        return

    uid, amt = dep["uid"], dep["amount"]

    if data.startswith("dep_appr_"):
        c.execute("UPDATE deposits SET status = 'APPROVED' WHERE txnid = ?", (txnid,))
        conn.commit()
        conn.close()

        update_balance_db(uid, amt, "Deposit Approval")

        await q.message.edit_caption(caption=f"{q.message.caption_html}\n\n<b>✅ APPROVED by Admin!</b>", parse_mode="HTML")
        try:
            await context.bot.send_message(chat_id=uid, text=f"<b>🎉 DEPOSIT APPROVED!</b>\n💰 <code>₹{amt:.2f}</code> added to wallet.", parse_mode="HTML")
        except Exception: pass

    elif data.startswith("dep_rej_"):
        c.execute("UPDATE deposits SET status = 'REJECTED' WHERE txnid = ?", (txnid,))
        conn.commit()
        conn.close()

        await q.message.edit_caption(caption=f"{q.message.caption_html}\n\n<b>❌ REJECTED by Admin!</b>", parse_mode="HTML")
        try:
            await context.bot.send_message(chat_id=uid, text=f"<b>❌ DEPOSIT REJECTED!</b>\nTransaction <code>{txnid}</code> was declined.", parse_mode="HTML")
        except Exception: pass

# --- REDEEM VOUCHER ---
async def redeem_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("<b>🎁 Send Voucher Code:</b>", parse_mode="HTML")
    return WAITING_REDEEM_CODE

async def redeem_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    uid = update.effective_user.id

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT amount, is_used FROM vouchers WHERE code = ?", (code,))
    v = c.fetchone()

    if not v:
        await update.message.reply_text("<b>❌ Invalid Voucher!</b>", parse_mode="HTML")
        conn.close()
        return ConversationHandler.END

    if v["is_used"] == 1:
        await update.message.reply_text("<b>⚠️ Voucher already used!</b>", parse_mode="HTML")
        conn.close()
        return ConversationHandler.END

    amt = v["amount"]
    c.execute("UPDATE vouchers SET is_used = 1 WHERE code = ?", (code,))
    conn.commit()
    conn.close()

    update_balance_db(uid, amt, "Voucher Redeem")
    await update.message.reply_text(f"<b>🎉 REDEEMED! ₹{amt:.2f} added.</b>", parse_mode="HTML")
    return ConversationHandler.END

# --- PROFILE & HISTORY ---
async def user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    u = q.from_user
    u_data = get_user_db(u.id)

    txt = (
        f"<b>👤 USER PROFILE</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>• Name:</b> {clean_html(u.first_name)}\n"
        f"<b>• User ID:</b> <code>{u.id}</code>\n"
        f"<b>• Balance:</b> ₹{u_data['balance']:.2f}\n"
        f"<b>• Orders:</b> {u_data['orders']}\n"
    )
    kb = [
        [InlineKeyboardButton("📜 Orders", callback_data="btn_history_orders"), InlineKeyboardButton("💸 Txns", callback_data="btn_history_txns")],
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

    txt = "<b>🛍️ LAST 5 ORDERS:</b>\n" + ("\n".join([f"• <code>{r['phone']}</code> | ₹{r['price']} | {r['date']}" for r in rows]) if rows else "No orders yet.")
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Profile", callback_data="btn_profile")]]), parse_mode="HTML")

async def view_history_txns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT amount, type, date FROM transactions WHERE uid = ? ORDER BY id DESC LIMIT 5", (q.from_user.id,))
    rows = c.fetchall()
    conn.close()

    txt = "<b>💸 LAST 5 TRANSACTIONS:</b>\n" + ("\n".join([f"• ₹{r['amount']} ({r['type']}) - {r['date']}" for r in rows]) if rows else "No txns.")
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Profile", callback_data="btn_profile")]]), parse_mode="HTML")

async def refer_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    bot_obj = await context.bot.get_me()
    txt = f"<b>📢 REFER & EARN</b>\n\nEarn <b>₹{REFERRAL_BONUS:.2f}</b> per refer!\n\n<code>https://t.me/{bot_obj.username}?start={q.from_user.id}</code>"
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]]), parse_mode="HTML")

async def support_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(f"<b>👨‍💻 SUPPORT:</b> @{SUPPORT_USERNAME}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]]), parse_mode="HTML")

# --- ADMIN PANEL ---
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return

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
        "<b>⚡ ADMIN CONTROL PANEL ⚡</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
        "<b>Commands:</b>\n"
        "• <code>/add category | age | price | phone | session</code> (Direct Add)\n"
        "• <code>/admingive UserID</code> - Give Admin Access\n"
        "• <code>/addbal UserID | Amt</code> - Add Balance\n"
        "• <code>/cutbal UserID | Amt</code> - Deduct Balance\n"
        "• <code>/ban UserID</code> | <code>/unban UserID</code>"
    )
    if update.message:
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    else:
        await update.callback_query.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def cmd_admingive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        new_admin_id = int(update.message.text.replace("/admingive", "").strip())
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO admins (uid) VALUES (?)", (new_admin_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"<b>👑 SUCCESS! User <code>{new_admin_id}</code> is now an ADMIN!</b>", parse_mode="HTML")
        try:
            await context.bot.send_message(chat_id=new_admin_id, text="<b>🎉 Congratulations! You have been granted Admin Rights!</b>\nType /admin to open panel.", parse_mode="HTML")
        except Exception: pass
    except Exception:
        await update.message.reply_text("<b>Format:</b> <code>/admingive UserID</code>", parse_mode="HTML")

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
        f"<b>📊 LIVE STATS</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Users: {tot_users}\n"
        f"🛒 Orders: {tot_orders}\n"
        f"💰 Revenue: ₹{revenue:.2f}\n"
        f"📦 Available Stock: {active_stock}"
    )
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin", callback_data="btn_admin_menu")]]), parse_mode="HTML")

async def set_channel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("<b>📢 Send Requirement Channel Username (e.g. @MyChannel):</b>\nMake sure Bot is Admin in Channel!", parse_mode="HTML")
    return WAITING_SET_CHNL

async def set_channel_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ch_name = update.message.text.strip()
    if not ch_name.startswith("@"):
        ch_name = "@" + ch_name
    set_setting("req_channel", ch_name)
    await update.message.reply_text(f"<b>✅ Requirement Channel set to {ch_name}</b>", parse_mode="HTML")
    return ConversationHandler.END

async def gen_voucher_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("<b>🎟️ Enter Voucher Amount (₹):</b>", parse_mode="HTML")
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

        await update.message.reply_text(f"<b>✅ VOUCHER CREATED!</b>\n🎟️ Code: <code>{code}</code>\n💵 Amount: ₹{amt:.2f}", parse_mode="HTML")
    except Exception:
        await update.message.reply_text("<b>❌ Invalid Amount!</b>", parse_mode="HTML")
    return ConversationHandler.END

async def admin_del_stock_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("🗑️ <b>Send Stock ID to DELETE:</b>", parse_mode="HTML")
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
        await update.message.reply_text(f"<b>🎉 Added ₹{amt} to ALL USERS!</b>", parse_mode="HTML")
    except Exception:
        await update.message.reply_text("❌ Invalid Amount!")
    return ConversationHandler.END

async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
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
    if not is_admin(update.effective_user.id): return
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
    if not is_admin(update.effective_user.id): return
    try:
        uid, amt = update.message.text.replace("/addbal", "").strip().split("|")
        update_balance_db(int(uid.strip()), float(amt.strip()), "Admin Added")
        await update.message.reply_text(f"✅ Added ₹{amt.strip()} to <code>{uid.strip()}</code>", parse_mode="HTML")
    except Exception:
        await update.message.reply_text("Format: <code>/addbal UserID | Amount</code>", parse_mode="HTML")

async def cmd_cutbal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        uid, amt = update.message.text.replace("/cutbal", "").strip().split("|")
        update_balance_db(int(uid.strip()), -float(amt.strip()), "Admin Cut")
        await update.message.reply_text(f"✂️ Deducted ₹{amt.strip()} from <code>{uid.strip()}</code>", parse_mode="HTML")
    except Exception:
        await update.message.reply_text("Format: <code>/cutbal UserID | Amount</code>", parse_mode="HTML")

async def cmd_viewstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, category, age, price, phone FROM stock WHERE is_sold = 0")
    items = c.fetchall()
    conn.close()

    txt = "<b>📊 INVENTORY:</b>\n" + ("\n".join([f"• ID: {i['id']} [{i['category'].upper()}] | {i['age']} - ₹{i['price']} | <code>{i['phone']}</code>" for i in items]) if items else "Stock Empty.")
    await update.effective_message.reply_text(txt, parse_mode="HTML")

# --- DIRECT /ADD COMMAND HANDLER ---
async def cmd_add_stock_direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    try:
        text_data = update.message.text.replace("/add", "").strip()
        parts = [p.strip() for p in text_data.split("|")]
        if len(parts) < 5:
            await update.message.reply_text(
                "<b>❌ Invalid Format!</b>\n\n"
                "<b>Use format:</b>\n"
                "<code>/add category | age | price | phone | session</code>\n\n"
                "<b>Example:</b>\n"
                "<code>/add normal | 1 Year | 50 | 919876543210 | 1BwW...session...</code>",
                parse_mode="HTML"
            )
            return

        cat, age, price_str, phone, session_str = parts[0].lower(), parts[1], parts[2], parts[3], parts[4]
        price = float(price_str)

        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO stock (category, age, price, phone, session) VALUES (?, ?, ?, ?, ?)", (cat, age, price, phone, session_str))
        conn.commit()
        conn.close()

        await update.message.reply_text(f"<b>✅ STOCK ADDED SUCCESSFULLY! [{cat.upper()}]</b>", parse_mode="HTML")
    except Exception as e:
        await update.message.reply_text(f"<b>❌ Error:</b> <code>{str(e)}</code>", parse_mode="HTML")

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

# --- STOCK ADDING WIZARD (BUTTON CLICK) ---
async def add_stock_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[InlineKeyboardButton("🔹 Normal", callback_data="addcat_normal")], [InlineKeyboardButton("⭐ Premium", callback_data="addcat_premium")], [InlineKeyboardButton("🛠️ Maked", callback_data="addcat_maked")]]
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text("<b>[Step 1/5] Select Category:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    else:
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
    await update.message.reply_text("<b>[Step 3/5]</b> Enter Price (₹):", parse_mode="HTML")
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

    await update.message.reply_text("<b>✅ STOCK ADDED SUCCESSFULLY!</b>", parse_mode="HTML")
    return ConversationHandler.END

async def cancel_wizard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.")
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

    # Deposit Approval Routes
    app.add_handler(CallbackQueryHandler(admin_handle_deposit_approval, pattern="^dep_(appr|rej)_"))

    # Admin Direct Commands
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("admingive", cmd_admingive))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("addbal", cmd_addbal))
    app.add_handler(CommandHandler("cutbal", cmd_cutbal))
    app.add_handler(CommandHandler("viewstock", cmd_viewstock))
    app.add_handler(CommandHandler("add", cmd_add_stock_direct)) # Direct /add command support

    # Admin Callbacks
    app.add_handler(CallbackQueryHandler(cmd_admin, pattern="^(adm_panel_close|btn_admin_menu)$"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^adm_stats$"))
    app.add_handler(CallbackQueryHandler(cmd_viewstock, pattern="^adm_panel_view$"))

    # Deposit Screenshot Upload Wizard
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(upload_ss_start, pattern="^btn_upload_ss$")],
        states={
            WAITING_PROOF_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, upload_ss_amt)],
            WAITING_PROOF_SS: [MessageHandler(filters.PHOTO, upload_ss_finish)]
        },
        fallbacks=[CommandHandler("cancel", cancel_wizard)],
    ))

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

    # Button Wizard for Adding Stock (Optional fallback)
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(add_stock_start, pattern="^adm_panel_add$")],
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
