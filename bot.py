import os
import logging
import threading
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Config
BOT_TOKEN = "8794925442:AAFIHaUAJM8ZXt2guEN7Lq2kKyTTKzECWqw"
ADMIN_ID = 8895089247
SUPPORT_USERNAME = "tgprimesoul"

# Minimum Deposit Limit
MIN_DEPOSIT = 25

# Global System Settings & Database
payment_settings = {
    "upi": "tgprimesoul@upi",
    "qr_url": "https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=upi://pay?pa=tgprimesoul@upi",  # Live dynamic UPI QR
    "crypto": "USDT (TRC20): TYourUSDTWalletAddressHere",
    "note": "Minimum Deposit is ₹25 / $0.30. Payment karne ke baad screenshot Support Admin ko bhejin."
}

users = {}
items = []
item_counter = 1
admin_wizard = {}

# Web Server
web_app = Flask('')

@web_app.route('/')
def home():
    return "Heart Store Engine Active"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

def get_user(uid):
    if uid not in users:
        users[uid] = {"balance": 0.0, "orders": 0}
    return users[uid]

def clean_html(text):
    if not text:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

# --- USER MENU ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    u_data = get_user(u.id)
    name = clean_html(u.first_name)

    kb = [
        [InlineKeyboardButton("🛍️ Browse Categories", callback_data="btn_categories")],
        [InlineKeyboardButton("👤 Profile", callback_data="btn_profile"), InlineKeyboardButton("💳 Add Money", callback_data="btn_add_bal")],
        [InlineKeyboardButton("👨‍💻 Support", callback_data="btn_support")]
    ]
    
    txt = (
        f"<b>❤️ Welcome to TG Store! 👋</b>\n\n"
        f"👤 <b>User:</b> {name}\n"
        f"🆔 <b>ID:</b> <code>{u.id}</code>\n"
        f"💰 <b>Balance:</b> ₹{u_data['balance']:.2f}\n\n"
        f"<i>Select an option below to buy Accounts/Stock:</i>"
    )

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
    await q.message.edit_text("<b>📂 Select Account Category:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def category_stock_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    cat_type = q.data.replace("cat_", "").lower()
    cat_names = {"normal": "Normal Acc", "premium": "Premium Acc", "maked": "Maked Acc"}
    cat_title = cat_names.get(cat_type, "Accounts")

    filtered_items = [i for i in items if i.get("category", "").lower() == cat_type]

    if not filtered_items:
        kb = [[InlineKeyboardButton("🔙 Back to Categories", callback_data="btn_categories")]]
        await q.message.edit_text(f"❌ <b>No stock available in {cat_title}!</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    kb = []
    for i in filtered_items:
        kb.append([InlineKeyboardButton(f"{i['age']} ({i['category'].capitalize()}) — ₹{i['price']:.2f}", callback_data=f"buy_{i['id']}")])
    kb.append([InlineKeyboardButton("🔙 Back to Categories", callback_data="btn_categories")])

    await q.message.edit_text(f"<b>🛍️ Available in {cat_title}:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def buy_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    item_id = int(q.data.split("_")[1])
    item = next((i for i in items if i["id"] == item_id), None)

    if not item:
        await q.message.edit_text("❌ Sold out!")
        return

    u_data = get_user(q.from_user.id)
    kb = [
        [InlineKeyboardButton("⚡ Confirm & Buy", callback_data=f"pay_{item['id']}")],
        [InlineKeyboardButton("🔙 Back", callback_data="btn_categories")]
    ]
    txt = (
        f"<b>📦 Account Type:</b> {clean_html(item['category'].capitalize())} Acc\n"
        f"<b>⏳ Account Age:</b> {clean_html(item['age'])}\n"
        f"<b>💵 Price:</b> ₹{item['price']:.2f}\n\n"
        f"<b>Your Wallet Balance:</b> ₹{u_data['balance']:.2f}"
    )
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def pay_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    item_id = int(q.data.split("_")[1])
    item = next((i for i in items if i["id"] == item_id), None)

    if not item:
        await q.message.edit_text("❌ Item already sold.")
        return

    u_data = get_user(uid)

    if u_data["balance"] < item["price"]:
        kb = [[InlineKeyboardButton("💳 Add Balance", callback_data="btn_add_bal")], [InlineKeyboardButton("🔙 Back", callback_data="btn_categories")]]
        await q.message.edit_text(f"❌ <b>Insufficient Balance!</b>\nPrice: ₹{item['price']:.2f}\nYour Balance: ₹{u_data['balance']:.2f}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    u_data["balance"] -= item["price"]
    u_data["orders"] += 1
    items.remove(item)

    await q.message.edit_text(
        f"🎉 <b>Purchase Successful!</b>\n\n"
        f"<b>Category:</b> {clean_html(item['category'].capitalize())} Acc\n"
        f"<b>Age:</b> {clean_html(item['age'])}\n"
        f"<b>Price Paid:</b> ₹{item['price']:.2f}\n\n"
        f"🔑 <b>Your Account Data:</b>\n<code>{clean_html(item['data'])}</code>",
        parse_mode="HTML"
    )

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🛍️ <b>Auto Sale Alert!</b>\nUser: @{q.from_user.username} (<code>{uid}</code>)\nCategory: {clean_html(item['category'].capitalize())}\nAge: {clean_html(item['age'])}",
        parse_mode="HTML"
    )

async def user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    u = q.from_user
    u_data = get_user(u.id)

    txt = f"<b>👤 PROFILE INFO</b>\n\n• Name: {clean_html(u.first_name)}\n• User ID: <code>{u.id}</code>\n• Balance: ₹{u_data['balance']:.2f}\n• Total Orders: {u_data['orders']}"
    kb = [[InlineKeyboardButton("💳 Deposit Money", callback_data="btn_add_bal")], [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]]
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

# --- SMART DEPOSIT SYSTEM ---

async def deposit_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    txt = (
        f"<b>💳 DEPOSIT / ADD MONEY</b>\n\n"
        f"⚠️ <b>Minimum Deposit Amount:</b> ₹{MIN_DEPOSIT}\n\n"
        f"Choose your preferred payment method below:"
    )
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
        txt = (
            f"<b>🖼️ SCAN UPI QR CODE</b>\n\n"
            f"⚠️ <b>Minimum Deposit:</b> ₹{MIN_DEPOSIT}\n\n"
            f"👉 QR Link: {payment_settings['qr_url']}\n"
            f"👉 Or Pay on UPI ID: <code>{payment_settings['upi']}</code>\n\n"
            f"<i>Payment ke baad screenshot aur User ID Admin <b>@{SUPPORT_USERNAME}</b> ko bhejeyin.</i>"
        )
    elif method == "dep_upi":
        txt = (
            f"<b>📱 UPI PAYMENT</b>\n\n"
            f"⚠️ <b>Minimum Deposit:</b> ₹{MIN_DEPOSIT}\n\n"
            f"<b>UPI ID:</b> <code>{payment_settings['upi']}</code>\n\n"
            f"<i>Payment karne ke baad proof Admin <b>@{SUPPORT_USERNAME}</b> ko bhejeyin.</i>"
        )
    elif method == "dep_crypto":
        txt = (
            f"<b>🌐 CRYPTO PAYMENT</b>\n\n"
            f"<b>Details:</b> <code>{payment_settings['crypto']}</code>\n\n"
            f"<i>Payment TXID screenshot Admin <b>@{SUPPORT_USERNAME}</b> ko bhejeyin.</i>"
        )

    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def support_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    txt = (
        f"<b>👨‍💻 CUSTOMER SUPPORT</b>\n\n"
        f"Need help with order, stock, or payments? Contact our admin:\n\n"
        f"👤 <b>Support Admin:</b> @{SUPPORT_USERNAME}"
    )
    kb = [
        [InlineKeyboardButton("📩 Contact @tgprimesoul", url=f"https://t.me/{SUPPORT_USERNAME}")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]
    ]
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

# --- ADMIN PANEL & CONTROL ---

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    kb = [
        [InlineKeyboardButton("➕ Add Stock", callback_data="adm_panel_add"), InlineKeyboardButton("📊 View Stock", callback_data="adm_panel_view")],
        [InlineKeyboardButton("⚙️ Payment Settings", callback_data="adm_panel_pay"), InlineKeyboardButton("📢 Broadcast", callback_data="adm_panel_bc")],
        [InlineKeyboardButton("❌ Close Panel", callback_data="adm_panel_close")]
    ]
    txt = (
        f"<b>⚡ ADMIN CONTROL PANEL</b>\n\n"
        f"👥 <b>Total Users:</b> {len(users)}\n"
        f"📦 <b>Available Items:</b> {len(items)}\n\n"
        f"<b>Quick Commands:</b>\n"
        f"• <code>/add</code> - Add Stock\n"
        f"• <code>/addbal UserID | Amount</code> - Add Balance\n"
        f"• <code>/viewstock</code> - Check Store Items"
    )
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
        await q.message.edit_text(
            f"<b>⚙️ UPDATE PAYMENT METHODS</b>\n\n"
            f"Current UPI: <code>{payment_settings['upi']}</code>\n"
            f"Current Crypto: <code>{payment_settings['crypto']}</code>\n\n"
            f"<b>Step 1:</b> Send NEW <b>UPI ID</b> (or send <code>skip</code> to keep same):",
            parse_mode="HTML"
        )
    elif data == "adm_panel_bc":
        admin_wizard[ADMIN_ID] = {"step": "WAITING_BROADCAST"}
        await q.message.edit_text("<b>📢 BROADCAST MESSAGE</b>\n\nSend message text to send to ALL registered users:", parse_mode="HTML")
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
    
    txt = "<b>➕ Select Account Type to Add:</b>"
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

    await q.message.edit_text(f"Selected: <b>{acc_type.capitalize()} Acc</b>\n\n<b>Step 2:</b> Send <b>Account Age</b> (e.g. <code>Fresh</code>, <code>2022 Aged</code>):", parse_mode="HTML")

async def handle_admin_wizard_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ADMIN_ID or uid not in admin_wizard:
        return

    state = admin_wizard[uid]
    step = state.get("step")
    text = update.message.text.strip()

    # BROADCAST
    if step == "WAITING_BROADCAST":
        count = 0
        for u_id in users.keys():
            try:
                await context.bot.send_message(chat_id=u_id, text=f"<b>📢 Announcement:</b>\n\n{clean_html(text)}", parse_mode="HTML")
                count += 1
            except Exception:
                pass
        del admin_wizard[uid]
        await update.message.reply_text(f"✅ Broadcast sent to <b>{count} users</b>!", parse_mode="HTML")

    # PAYMENT EDIT
    elif step == "EDIT_UPI":
        if text.lower() != "skip":
            payment_settings["upi"] = text
            payment_settings["qr_url"] = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=upi://pay?pa={text}"
        state["step"] = "EDIT_CRYPTO"
        await update.message.reply_text("<b>Step 2:</b> Send NEW <b>Crypto Address/Details</b> (or send <code>skip</code> to keep same):", parse_mode="HTML")

    elif step == "EDIT_CRYPTO":
        if text.lower() != "skip":
            payment_settings["crypto"] = text
        del admin_wizard[uid]
        await update.message.reply_text("✅ <b>Payment Details Updated Successfully!</b>", parse_mode="HTML")

    # STOCK ADD
    elif step == "WAITING_AGE":
        state["age"] = text
        state["step"] = "WAITING_PRICE"
        await update.message.reply_text("<b>Step 3:</b> Enter <b>Price</b> in INR ₹ (e.g. <code>50</code> or <code>100</code>):", parse_mode="HTML")

    elif step == "WAITING_PRICE":
        try:
            state["price"] = float(text)
            state["step"] = "WAITING_DATA"
            await update.message.reply_text("<b>Step 4:</b> Send <b>Account Data / Stock String</b>:", parse_mode="HTML")
        except ValueError:
            await update.message.reply_text("❌ Enter a valid number for price (e.g. <code>50</code>):", parse_mode="HTML")

    elif step == "WAITING_DATA":
        global item_counter
        state["data"] = text
        
        items.append({
            "id": item_counter,
            "category": state["category"],
            "age": state["age"],
            "price": state["price"],
            "data": state["data"]
        })
        item_counter += 1
        del admin_wizard[uid]

        txt = (
            f"✅ <b>Stock Added Successfully!</b>\n\n"
            f"• <b>Type:</b> {state['category'].capitalize()} Acc\n"
            f"• <b>Age:</b> {state['age']}\n"
            f"• <b>Price:</b> ₹{state['price']:.2f}\n"
            f"• <b>Data:</b> <code>{clean_html(state['data'])}</code>"
        )
        await update.message.reply_text(txt, parse_mode="HTML")

async def cmd_addbal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        raw_text = update.message.text.replace("/addbal", "").strip()
        uid, amt = raw_text.split("|")
        uid = int(uid.strip())
        amt = float(amt.strip())

        u_data = get_user(uid)
        u_data["balance"] += amt
        await update.message.reply_text(f"✅ Added ₹{amt:.2f} to <code>{uid}</code>", parse_mode="HTML")
        await context.bot.send_message(chat_id=uid, text=f"🎉 <b>₹{amt:.2f} Credited to your Wallet!</b>", parse_mode="HTML")
    except Exception:
        await update.message.reply_text("❌ <b>Wrong Format!</b>\nUse: <code>/addbal UserID | Amount</code>", parse_mode="HTML")

async def cmd_viewstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not items:
        txt = "Store is currently empty."
    else:
        txt = "<b>📊 CURRENT STOCK IN STORE:</b>\n\n"
        for i in items:
            txt += f"• ID: {i['id']} [{i['category'].upper()}] | Age: {clean_html(i['age'])} — ₹{i['price']}\n  Data: <code>{clean_html(i['data'])}</code>\n\n"
    
    if update.callback_query:
        await update.callback_query.message.reply_text(txt, parse_mode="HTML")
    else:
        await update.message.reply_text(txt, parse_mode="HTML")

def main():
    threading.Thread(target=run_flask, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    # User Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start, pattern="^btn_main$"))
    app.add_handler(CallbackQueryHandler(show_categories, pattern="^btn_categories$"))
    app.add_handler(CallbackQueryHandler(category_stock_list, pattern="^cat_"))
    app.add_handler(CallbackQueryHandler(buy_confirm, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(pay_item, pattern="^pay_"))
    app.add_handler(CallbackQueryHandler(user_profile, pattern="^btn_profile$"))
    app.add_handler(CallbackQueryHandler(deposit_info, pattern="^btn_add_bal$"))
    app.add_handler(CallbackQueryHandler(deposit_method_handler, pattern="^dep_"))
    app.add_handler(CallbackQueryHandler(support_info, pattern="^btn_support$"))

    # Admin Commands
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
