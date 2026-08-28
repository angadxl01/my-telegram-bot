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

PREMIUM_STICKER_ID = "CAACAgIAAxkBAAE_YOUR_STICKER_FILE_ID_HERE"

MIN_DEPOSIT = 25
REFERRAL_BONUS = 0.1
# ================================================================

WAITING_CAT, WAITING_AGE, WAITING_PRICE, WAITING_PHONE, WAITING_SESSION = range(5)
WAITING_BROADCAST_MSG, WAITING_DEL_ID, WAITING_GIVEALL_AMT = range(10, 13)

# --- HELPER FUNCTION FOR STICKERS ---
async def send_premium_sticker(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        if PREMIUM_STICKER_ID and "YOUR_STICKER" not in PREMIUM_STICKER_ID:
            await context.bot.send_sticker(chat_id=chat_id, sticker=PREMIUM_STICKER_ID)
    except Exception:
        pass

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
    conn.commit()
    conn.close()

init_db()

def get_user_db(uid, ref_id=0):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT balance, orders, referred_by, is_banned FROM users WHERE uid = ?", (uid,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO users (uid, balance, orders, referred_by, is_banned) VALUES (?, 0.0, 0, ?, 0)", (uid, ref_id))
        conn.commit()
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

# --- WEB SERVER ---
web_app = Flask('')
@web_app.route('/')
def home():
    return "Store Engine Online"

def run_flask():
    web_app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- START & REFERRAL LOGIC ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    u_data = get_user_db(u.id)

    if u_data["is_banned"] == 1:
        await update.effective_message.reply_text("🚫 <b>You are BANNED from using this bot!</b>", parse_mode="HTML")
        return

    # Referral Check
    if context.args and len(context.args) > 0:
        try:
            ref_id = int(context.args[0])
            if ref_id != u.id and u_data["referred_by"] == 0:
                update_balance_db(ref_id, REFERRAL_BONUS, "Referral Bonus")
                await context.bot.send_message(chat_id=ref_id, text=f"🎉 <b>New Referral!</b> User <code>{u.id}</code> joined via your link.\n💰 ₹{REFERRAL_BONUS} added!", parse_mode="HTML")
        except Exception:
            pass

    kb = [
        [InlineKeyboardButton("🛍️ Browse Categories", callback_data="btn_categories")],
        [InlineKeyboardButton("👤 Profile & History", callback_data="btn_profile"), InlineKeyboardButton("💳 Add Money", callback_data="btn_add_bal")],
        [InlineKeyboardButton("🎁 Refer & Earn", callback_data="btn_refer"), InlineKeyboardButton("👨‍💻 Support", callback_data="btn_support")]
    ]
    txt = f"<b>❤️ Welcome to TG Store! 👋</b>\n\n🆔 <b>ID:</b> <code>{u.id}</code>\n💰 <b>Balance:</b> ₹{u_data['balance']:.2f}"

    await send_premium_sticker(u.id, context)
    if update.message:
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    else:
        await update.callback_query.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

# --- USER CATEGORIES & BUYING ---
async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user_db(q.from_user.id)["is_banned"]: return

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
    cat_type = q.data.replace("cat_", "").lower()

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, age, price FROM stock WHERE category = ? AND is_sold = 0", (cat_type,))
    filtered_items = c.fetchall()
    conn.close()

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
        await q.message.reply_text("❌ Item already sold.")
        conn.close()
        return

    price, phone, session_str, category = item["price"], item["phone"], item["session"], item["category"]
    u_data = get_user_db(uid)

    if u_data["balance"] < price:
        needed = price - u_data["balance"]
        conn.close()
        kb = [[InlineKeyboardButton("💳 Add Money", callback_data="btn_add_bal")], [InlineKeyboardButton("🔙 Back", callback_data="btn_categories")]]
        await q.message.reply_text(f"❌ <b>Insufficient Balance!</b>\nNeed ₹{needed:.2f} more.", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    c.execute("UPDATE users SET balance = balance - ?, orders = orders + 1 WHERE uid = ?", (price, uid))
    c.execute("UPDATE stock SET is_sold = 1 WHERE id = ?", (item_id,))
    c.execute("INSERT INTO purchases (uid, item_id, phone, session, price) VALUES (?, ?, ?, ?, ?)", (uid, item_id, phone, session_str, price))
    c.execute("INSERT INTO transactions (uid, amount, type) VALUES (?, ?, ?)", (uid, -price, f"Bought {category.capitalize()} Acc"))
    conn.commit()

    # Low Stock Check
    c.execute("SELECT COUNT(*) as cnt FROM stock WHERE category = ? AND is_sold = 0", (category,))
    rem_stock = c.fetchone()["cnt"]
    conn.close()

    if rem_stock == 0:
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ <b>STOCK ALERT!</b> Category <b>{category.upper()}</b> is OUT OF STOCK!", parse_mode="HTML")
        except Exception: pass

    kb = [[InlineKeyboardButton("📩 GET OTP NOW", callback_data=f"get_otp_{item_id}")]]
    txt = f"🎉 <b>Purchase Successful!</b>\n\n📱 <b>Phone:</b> <code>{phone}</code>\n\n<i>Enter number in Telegram, then click GET OTP NOW below.</i>"
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

    session_str = purchase["session"]
    msg_status = await q.message.reply_text("🔄 <b>Checking Telegram System (777000)...</b>", parse_mode="HTML")

    try:
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            await msg_status.edit_text("❌ <b>Session Expired / Logged Out!</b>")
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

        if otp_found:
            kb = [[InlineKeyboardButton("📩 GET OTP AGAIN", callback_data=f"get_otp_{item_id}")]]
            await msg_status.edit_text(f"🔑 <b>YOUR LOGIN OTP:</b> <code>{otp_found}</code>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        else:
            kb = [[InlineKeyboardButton("🔄 TRY AGAIN", callback_data=f"get_otp_{item_id}")]]
            await msg_status.edit_text("❌ <b>OTP Not Received Yet!</b> Request code in app first.", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

    except Exception as e:
        await msg_status.edit_text(f"⚠️ <b>Error:</b> <code>{str(e)}</code>")

# --- PROFILE & HISTORY ---
async def user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    u = q.from_user
    u_data = get_user_db(u.id)

    txt = f"<b>👤 PROFILE INFO</b>\n\n• Name: {clean_html(u.first_name)}\n• User ID: <code>{u.id}</code>\n• Balance: ₹{u_data['balance']:.2f}\n• Purchases: {u_data['orders']}"
    kb = [
        [InlineKeyboardButton("📜 My Orders", callback_data="btn_history_orders"), InlineKeyboardButton("💸 Txns", callback_data="btn_history_txns")],
        [InlineKeyboardButton("💳 Add Money", callback_data="btn_add_bal")],
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

    txt = "<b>🛍️ LAST 5 ORDERS:</b>\n\n" + ("\n".join([f"• <code>{r['phone']}</code> | ₹{r['price']} | {r['date']}" for r in rows]) if rows else "No orders yet.")
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Profile", callback_data="btn_profile")]]), parse_mode="HTML")

async def view_history_txns(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT amount, type, date FROM transactions WHERE uid = ? ORDER BY id DESC LIMIT 5", (q.from_user.id,))
    rows = c.fetchall()
    conn.close()

    txt = "<b>💸 LAST 5 TRANSACTIONS:</b>\n\n" + ("\n".join([f"• ₹{r['amount']} ({r['type']}) - {r['date']}" for r in rows]) if rows else "No transactions yet.")
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Profile", callback_data="btn_profile")]]), parse_mode="HTML")

async def refer_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    bot_obj = await context.bot.get_me()
    txt = f"<b>🎁 REFER & EARN</b>\n\nEarn <b>₹{REFERRAL_BONUS:.2f}</b> per referral!\n\n🔗 <code>https://t.me/{bot_obj.username}?start={q.from_user.id}</code>"
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]), parse_mode="HTML")

async def deposit_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    txt = f"<b>💳 ADD MONEY</b>\n\n• UPI ID: <code>tgprimesoul@upi</code>\n• Min Deposit: ₹{MIN_DEPOSIT}\n\n<i>Payment ke baad Admin @{SUPPORT_USERNAME} ko proof bhejein.</i>"
    kb = [[InlineKeyboardButton("📤 Send Proof", url=f"https://t.me/{SUPPORT_USERNAME}")], [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]]
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def support_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(f"<b>👨‍💻 SUPPORT:</b> @{SUPPORT_USERNAME}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]), parse_mode="HTML")

# --- POWERFUL ADMIN CONTROL PANEL ---
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return

    kb = [
        [InlineKeyboardButton("📊 Dashboard Stats", callback_data="adm_stats"), InlineKeyboardButton("➕ Add Stock", callback_data="adm_panel_add")],
        [InlineKeyboardButton("📦 View Stock", callback_data="adm_panel_view"), InlineKeyboardButton("🗑️ Delete Stock", callback_data="adm_del_stock")],
        [InlineKeyboardButton("📢 Broadcast Msg", callback_data="adm_panel_broadcast"), InlineKeyboardButton("🎁 Mass Giveaway", callback_data="adm_giveall")],
        [InlineKeyboardButton("❌ Close Panel", callback_data="adm_panel_close")]
    ]
    txt = (
        "<b>⚡ ADMIN CONTROL PANEL ⚡</b>\n\n"
        "<b>Available Admin Commands:</b>\n"
        "• <code>/addbal UserID | Amt</code> - Add balance\n"
        "• <code>/cutbal UserID | Amt</code> - Cut balance\n"
        "• <code>/ban UserID</code> - Block user\n"
        "• <code>/unban UserID</code> - Unblock user"
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
        f"<b>📊 STORE LIVE STATS</b>\n\n"
        f"👥 <b>Total Users:</b> {tot_users}\n"
        f"🛒 <b>Total Orders:</b> {tot_orders}\n"
        f"💰 <b>Total Revenue:</b> ₹{revenue:.2f}\n"
        f"📦 <b>Available Stock:</b> {active_stock} items"
    )
    await q.message.reply_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Admin", callback_data="btn_admin_menu")]), parse_mode="HTML")

# --- ADMIN DELETION & GIVEAWAY WIZARDS ---
async def admin_del_stock_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("🗑️ <b>Send the Stock ID you want to DELETE:</b>\n(Check ID from View Stock)", parse_mode="HTML")
    return WAITING_DEL_ID

async def admin_del_stock_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sid = int(update.message.text.strip())
        conn = get_db()
        c = conn.cursor()
        c.execute("DELETE FROM stock WHERE id = ?", (sid,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"✅ Stock ID <code>{sid}</code> deleted successfully!", parse_mode="HTML")
    except Exception:
        await update.message.reply_text("❌ Invalid Stock ID!")
    return ConversationHandler.END

async def admin_giveall_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("🎁 <b>Enter amount to give to ALL USERS (e.g. 10):</b>", parse_mode="HTML")
    return WAITING_GIVEALL_AMT

async def admin_giveall_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amt = float(update.message.text.strip())
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET balance = balance + ?", (amt,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"🎉 <b>Successfully added ₹{amt} bonus to ALL USERS!</b>", parse_mode="HTML")
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
        await update.message.reply_text(f"🚫 User <code>{uid}</code> has been BANNED!", parse_mode="HTML")
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

    txt = "<b>📊 AVAILABLE STOCK:</b>\n\n" + ("\n".join([f"• ID: {i['id']} [{i['category'].upper()}] | {i['age']} - ₹{i['price']} | <code>{i['phone']}</code>" for i in items]) if items else "Empty stock.")
    await update.effective_message.reply_text(txt, parse_mode="HTML")

# --- BROADCAST WIZARD ---
async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("📢 <b>Send message to BROADCAST:</b>", parse_mode="HTML")
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

    await update.message.reply_text(f"✅ Broadcast Sent to {sent} users!", parse_mode="HTML")
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

    await update.message.reply_text("✅ <b>STOCK ADDED!</b>", parse_mode="HTML")
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
    app.add_handler(CallbackQueryHandler(user_profile, pattern="^btn_profile$"))
    app.add_handler(CallbackQueryHandler(view_history_orders, pattern="^btn_history_orders$"))
    app.add_handler(CallbackQueryHandler(view_history_txns, pattern="^btn_history_txns$"))
    app.add_handler(CallbackQueryHandler(refer_info, pattern="^btn_refer$"))
    app.add_handler(CallbackQueryHandler(deposit_info, pattern="^btn_add_bal$"))
    app.add_handler(CallbackQueryHandler(support_info, pattern="^btn_support$"))

    # Admin Direct Commands
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

    # Wizards
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
