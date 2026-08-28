import os
import re
import sqlite3
import logging
import threading
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
    filters,
)

# --- CONFIGURATION ---
BOT_TOKEN = "8794925442:AAFIHaUAJM8ZXt2guEN7Lq2kKyTTKzECWqw"
ADMIN_ID = 8895089247
SUPPORT_USERNAME = "tgprimesoul"

# 👉 YAHAN APNA my.telegram.org SE MILA DETAILS ENTER KAREIN
API_ID = 36645562          # Change to your real API_ID (e.g. 2847593)
API_HASH = "ccad405579d80b82492abbf4a7777907" # Change to your real API_HASH

MIN_DEPOSIT = 25

payment_settings = {
    "upi": "tgprimesoul@upi",
    "qr_url": "https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=upi://pay?pa=tgprimesoul@upi",
    "crypto": "USDT (TRC20): TYourUSDTWalletAddressHere",
    "note": "Minimum Deposit ₹25. Payment ke baad screenshot Admin ko bhejeyin."
}

admin_wizard = {}

# --- DATABASE ENGINE ---
def init_db():
    conn = sqlite3.connect("store.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (uid INTEGER PRIMARY KEY, balance REAL DEFAULT 0.0, orders INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS stock (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, age TEXT, price REAL, phone TEXT, session TEXT, is_sold INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS purchases (id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, item_id INTEGER, phone TEXT, session TEXT)""")
    conn.commit()
    conn.close()

init_db()

def get_user_db(uid):
    conn = sqlite3.connect("store.db")
    c = conn.cursor()
    c.execute("SELECT balance, orders FROM users WHERE uid = ?", (uid,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO users (uid, balance, orders) VALUES (?, 0.0, 0)", (uid,))
        conn.commit()
        balance, orders = 0.0, 0
    else:
        balance, orders = row[0], row[1]
    conn.close()
    return {"balance": balance, "orders": orders}

def update_balance_db(uid, amt):
    conn = sqlite3.connect("store.db")
    c = conn.cursor()
    c.execute("INSERT INTO users (uid, balance, orders) VALUES (?, ?, 0) ON CONFLICT(uid) DO UPDATE SET balance = balance + ?", (uid, amt, amt))
    conn.commit()
    conn.close()

def clean_html(text):
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

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
    u_data = get_user_db(u.id)

    kb = [
        [InlineKeyboardButton("🛍️ Browse Categories", callback_data="btn_categories")],
        [InlineKeyboardButton("👤 Profile", callback_data="btn_profile"), InlineKeyboardButton("💳 Add Money", callback_data="btn_add_bal")],
        [InlineKeyboardButton("👨‍💻 Support", callback_data="btn_support")]
    ]
    txt = f"<b>❤️ Welcome to TG Store! 👋</b>\n\n🆔 <b>ID:</b> <code>{u.id}</code>\n💰 <b>Balance:</b> ₹{u_data['balance']:.2f}"

    if update.message:
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    else:
        await update.callback_query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kb = [
        [InlineKeyboardButton("🔹 Normal Acc", callback_data="cat_normal")],
        [InlineKeyboardButton("⭐ Premium Acc", callback_data="cat_premium")],
        [InlineKeyboardButton("🛠️ Maked Acc", callback_data="cat_maked")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]
    ]
    await q.message.edit_text("<b>📂 Select Category:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def category_stock_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cat_type = q.data.replace("cat_", "").lower()

    conn = sqlite3.connect("store.db")
    c = conn.cursor()
    c.execute("SELECT id, age, price FROM stock WHERE category = ? AND is_sold = 0", (cat_type,))
    filtered_items = c.fetchall()
    conn.close()

    if not filtered_items:
        kb = [[InlineKeyboardButton("🔙 Back", callback_data="btn_categories")]]
        await q.message.edit_text("❌ <b>Out of Stock!</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    kb = []
    for item in filtered_items:
        kb.append([InlineKeyboardButton(f"{item[1]} — ₹{item[2]:.2f}", callback_data=f"buy_{item[0]}")])
    kb.append([InlineKeyboardButton("🔙 Back", callback_data="btn_categories")])

    await q.message.edit_text("<b>🛍️ Available Accounts:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def buy_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    item_id = int(q.data.split("_")[1])

    conn = sqlite3.connect("store.db")
    c = conn.cursor()
    c.execute("SELECT id, category, age, price FROM stock WHERE id = ? AND is_sold = 0", (item_id,))
    item = c.fetchone()
    conn.close()

    if not item:
        await q.message.edit_text("❌ Account already sold!")
        return

    u_data = get_user_db(q.from_user.id)
    kb = [
        [InlineKeyboardButton("⚡ Confirm & Buy", callback_data=f"pay_{item[0]}")],
        [InlineKeyboardButton("🔙 Back", callback_data="btn_categories")]
    ]
    txt = f"<b>📦 Category:</b> {item[1].capitalize()} Acc\n<b>⏳ Age:</b> {item[2]}\n<b>💵 Price:</b> ₹{item[3]:.2f}\n\n<b>Your Balance:</b> ₹{u_data['balance']:.2f}"
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def pay_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    item_id = int(q.data.split("_")[1])

    conn = sqlite3.connect("store.db")
    c = conn.cursor()
    c.execute("SELECT id, price, phone, session FROM stock WHERE id = ? AND is_sold = 0", (item_id,))
    item = c.fetchone()

    if not item:
        await q.message.edit_text("❌ Item already sold.")
        conn.close()
        return

    price, phone, session_str = item[1], item[2], item[3]
    u_data = get_user_db(uid)

    if u_data["balance"] < price:
        conn.close()
        kb = [[InlineKeyboardButton("💳 Deposit", callback_data="btn_add_bal")], [InlineKeyboardButton("🔙 Back", callback_data="btn_categories")]]
        await q.message.edit_text(f"❌ <b>Insufficient Balance!</b>\nPrice: ₹{price:.2f}\nYour Balance: ₹{u_data['balance']:.2f}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
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
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def fetch_live_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    item_id = int(q.data.replace("get_otp_", ""))

    conn = sqlite3.connect("store.db")
    c = conn.cursor()
    c.execute("SELECT session, phone FROM purchases WHERE item_id = ?", (item_id,))
    purchase = c.fetchone()
    conn.close()

    if not purchase:
        await q.message.reply_text("❌ Purchase record not found.")
        return

    session_str, phone = purchase[0], purchase[1]
    await q.message.reply_text("🔄 <b>Checking OTP from Telegram... Please wait 5 seconds.</b>", parse_mode="HTML")

    try:
        client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            await q.message.reply_text("❌ Session expired or account logged out.")
            await client.disconnect()
            return

        messages = await client.get_messages(777000, limit=3)
        otp_found = None

        for msg in messages:
            if msg.text:
                match = re.search(r'\b\d{5}\b', msg.text)
                if match:
                    otp_found = match.group(0)
                    break

        await client.disconnect()

        if otp_found:
            kb = [[InlineKeyboardButton("📩 GET OTP AGAIN", callback_data=f"get_otp_{item_id}")]]
            await q.message.reply_text(f"🔑 <b>YOUR LOGIN OTP:</b> <code>{otp_found}</code>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        else:
            kb = [[InlineKeyboardButton("🔄 TRY AGAIN", callback_data=f"get_otp_{item_id}")]]
            await q.message.reply_text("❌ <b>OTP Code not received yet.</b> Please request code on app first.", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

    except Exception as e:
        await q.message.reply_text(f"⚠️ Error reading OTP: {str(e)}")

async def user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    u = q.from_user
    u_data = get_user_db(u.id)

    txt = f"<b>👤 PROFILE INFO</b>\n\n• Name: {clean_html(u.first_name)}\n• User ID: <code>{u.id}</code>\n• Balance: ₹{u_data['balance']:.2f}\n• Orders: {u_data['orders']}"
    kb = [[InlineKeyboardButton("💳 Deposit Money", callback_data="btn_add_bal")], [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]]
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def deposit_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    txt = f"<b>💳 DEPOSIT / ADD MONEY</b>\n\n⚠️ <b>Minimum Deposit:</b> ₹{MIN_DEPOSIT}\n\nSelect Payment Method:"
    kb = [
        [InlineKeyboardButton("🖼️ UPI QR Code", callback_data="dep_qr"), InlineKeyboardButton("📱 UPI ID", callback_data="dep_upi")],
        [InlineKeyboardButton("🌐 Crypto (USDT)", callback_data="dep_crypto")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]
    ]
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

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

    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def support_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    txt = f"<b>👨‍💻 CUSTOMER SUPPORT</b>\n\nContact support for help:\n\n👤 <b>Admin:</b> @{SUPPORT_USERNAME}"
    kb = [[InlineKeyboardButton("📩 Contact @tgprimesoul", url=f"https://t.me/{SUPPORT_USERNAME}")], [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]]
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

# --- ADMIN CONTROL PANEL ---

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    kb = [
        [InlineKeyboardButton("➕ Add Stock", callback_data="adm_panel_add"), InlineKeyboardButton("📊 View Stock", callback_data="adm_panel_view")],
        [InlineKeyboardButton("⚙️ Payment Settings", callback_data="adm_panel_pay")],
        [InlineKeyboardButton("❌ Close", callback_data="adm_panel_close")]
    ]
    txt = "<b>⚡ ADMIN CONTROL PANEL</b>\n\nManage stock and settings below."
    if update.message:
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    else:
        await update.callback_query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def admin_panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        return
    await q.answer()

    data = q.data
    if data == "adm_panel_add":
        await cmd_add(update, context)
    elif data == "adm_panel_view":
        await cmd_viewstock(update, context)
    elif data == "adm_panel_pay":
        admin_wizard[ADMIN_ID] = {"step": "EDIT_UPI"}
        await q.message.edit_text(f"Current UPI: <code>{payment_settings['upi']}</code>\n\nSend NEW <b>UPI ID</b> (or <code>skip</code>):", parse_mode="HTML")
    elif data == "adm_panel_close":
        await q.message.delete()

async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    kb = [
        [InlineKeyboardButton("🔹 Normal Acc", callback_data="adm_type_normal")],
        [InlineKeyboardButton("⭐ Premium Acc", callback_data="adm_type_premium")],
        [InlineKeyboardButton("🛠️ Maked Acc", callback_data="adm_type_maked")]
    ]
    admin_wizard[ADMIN_ID] = {"step": "SELECT_TYPE"}
    txt = "<b>➕ Select Account Category:</b>"
    if update.callback_query:
        await update.callback_query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    else:
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def admin_wizard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        return
    await q.answer()

    acc_type = q.data.replace("adm_type_", "")
    admin_wizard[ADMIN_ID] = {"step": "WAITING_AGE", "category": acc_type}
    await q.message.edit_text(f"Selected: <b>{acc_type.capitalize()}</b>\n\n<b>Step 2:</b> Send Account Age (e.g. <code>2023 Aged</code>):", parse_mode="HTML")

async def handle_admin_wizard_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ADMIN_ID or uid not in admin_wizard:
        return

    state = admin_wizard[uid]
    step = state.get("step")
    text = update.message.text.strip()

    if step == "EDIT_UPI":
        if text.lower() != "skip":
            payment_settings["upi"] = text
            payment_settings["qr_url"] = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=upi://pay?pa={text}"
        state["step"] = "EDIT_CRYPTO"
        await update.message.reply_text("Send NEW <b>Crypto Address</b> (or <code>skip</code>):", parse_mode="HTML")

    elif step == "EDIT_CRYPTO":
        if text.lower() != "skip":
            payment_settings["crypto"] = text
        del admin_wizard[uid]
        await update.message.reply_text("✅ Payment Details Updated!", parse_mode="HTML")

    elif step == "WAITING_AGE":
        state["age"] = text
        state["step"] = "WAITING_PRICE"
        await update.message.reply_text("<b>Step 3:</b> Enter Price (₹):", parse_mode="HTML")

    elif step == "WAITING_PRICE":
        try:
            state["price"] = float(text)
            state["step"] = "WAITING_PHONE"
            await update.message.reply_text("<b>Step 4:</b> Send Phone Number (e.g. <code>+919876543210</code>):", parse_mode="HTML")
        except ValueError:
            await update.message.reply_text("❌ Enter valid price number:", parse_mode="HTML")

    elif step == "WAITING_PHONE":
        state["phone"] = text
        state["step"] = "WAITING_SESSION"
        await update.message.reply_text("<b>Step 5:</b> Paste <b>Telethon Session String</b>:", parse_mode="HTML")

    elif step == "WAITING_SESSION":
        state["session"] = text
        
        conn = sqlite3.connect("store.db")
        c = conn.cursor()
        c.execute("INSERT INTO stock (category, age, price, phone, session) VALUES (?, ?, ?, ?, ?)",
                  (state["category"], state["age"], state["price"], state["phone"], state["session"]))
        conn.commit()
        conn.close()

        del admin_wizard[uid]
        await update.message.reply_text(f"✅ <b>Stock Added!</b>\nPhone: <code>{state['phone']}</code>", parse_mode="HTML")

async def cmd_addbal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        raw_text = update.message.text.replace("/addbal", "").strip()
        uid, amt = raw_text.split("|")
        update_balance_db(int(uid.strip()), float(amt.strip()))
        await update.message.reply_text(f"✅ Added ₹{amt.strip()} to <code>{uid.strip()}</code>", parse_mode="HTML")
    except Exception:
        await update.message.reply_text("Format: <code>/addbal UserID | Amount</code>", parse_mode="HTML")

async def cmd_viewstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    conn = sqlite3.connect("store.db")
    c = conn.cursor()
    c.execute("SELECT id, category, age, price, phone FROM stock WHERE is_sold = 0")
    items = c.fetchall()
    conn.close()

    if not items:
        txt = "Store is currently empty."
    else:
        txt = "<b>📊 AVAILABLE STOCK:</b>\n\n"
        for i in items:
            txt += f"• ID: {i[0]} [{i[1].upper()}] | Age: {i[2]} — ₹{i[3]}\n  Phone: <code>{i[4]}</code>\n\n"
    
    if update.callback_query:
        await update.callback_query.message.reply_text(txt, parse_mode="HTML")
    else:
        await update.message.reply_text(txt, parse_mode="HTML")

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

    # Admin Routes
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CallbackQueryHandler(admin_panel_callback, pattern="^adm_panel_"))
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CallbackQueryHandler(admin_wizard_callback, pattern="^adm_type_"))
    app.add_handler(CommandHandler("addbal", cmd_addbal))
    app.add_handler(CommandHandler("viewstock", cmd_viewstock))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_wizard_input))

    app.run_polling()

if __name__ == "__main__":
    main()
