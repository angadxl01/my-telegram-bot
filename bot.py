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
SUPPORT_USERNAME = "tgprimesoul"  # Admin Support Handle

# Web Server
web_app = Flask('')

@web_app.route('/')
def home():
    return "Heart Store Engine Active"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

# Store Database
users = {}
items = []
item_counter = 1
admin_wizard = {}  # Store temporary steps for stock addition

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
        f"💰 <b>Balance:</b> ${u_data['balance']:.2f}\n\n"
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
        kb.append([InlineKeyboardButton(f"{i['age']} ({i['category'].capitalize()}) — ${i['price']:.2f}", callback_data=f"buy_{i['id']}")])
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
        f"<b>💵 Price:</b> ${item['price']:.2f}\n\n"
        f"<b>Your Wallet Balance:</b> ${u_data['balance']:.2f}"
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
        await q.message.edit_text(f"❌ <b>Insufficient Balance!</b>\nPrice: ${item['price']:.2f}\nYour Balance: ${u_data['balance']:.2f}", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    u_data["balance"] -= item["price"]
    u_data["orders"] += 1
    items.remove(item)

    await q.message.edit_text(
        f"🎉 <b>Purchase Successful!</b>\n\n"
        f"<b>Category:</b> {clean_html(item['category'].capitalize())} Acc\n"
        f"<b>Age:</b> {clean_html(item['age'])}\n"
        f"<b>Price Paid:</b> ${item['price']:.2f}\n\n"
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

    txt = f"<b>👤 PROFILE INFO</b>\n\n• Name: {clean_html(u.first_name)}\n• User ID: <code>{u.id}</code>\n• Balance: ${u_data['balance']:.2f}\n• Orders: {u_data['orders']}"
    kb = [[InlineKeyboardButton("💳 Deposit", callback_data="btn_add_bal")], [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]]
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def deposit_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    txt = (
        f"<b>💳 ADD MONEY TO WALLET</b>\n\n"
        f"Contact Support Admin to add balance via UPI / Crypto / Bank Transfer.\n\n"
        f"📩 <b>Support Admin:</b> @{SUPPORT_USERNAME}"
    )
    kb = [
        [InlineKeyboardButton("💬 Message Supporter", url=f"https://t.me/{SUPPORT_USERNAME}")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]
    ]
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def support_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    txt = (
        f"<b>👨‍💻 CUSTOMER SUPPORT</b>\n\n"
        f"Need help with an order or balance? Click below to chat directly with our support team:\n\n"
        f"👤 <b>Supporter User:</b> @{SUPPORT_USERNAME}"
    )
    kb = [
        [InlineKeyboardButton("📩 Contact @tgprimesoul", url=f"https://t.me/{SUPPORT_USERNAME}")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]
    ]
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

# --- INTERACTIVE /add ADMIN WIZARD ---

async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    kb = [
        [InlineKeyboardButton("🔹 Normal Acc", callback_data="adm_type_normal")],
        [InlineKeyboardButton("⭐ Premium Acc", callback_data="adm_type_premium")],
        [InlineKeyboardButton("🛠️ Maked Acc", callback_data="adm_type_maked")]
    ]
    admin_wizard[ADMIN_ID] = {"step": "SELECT_TYPE"}
    await update.message.reply_text("<b>➕ Select Account Type to Add:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def admin_wizard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        return
    await q.answer()

    acc_type = q.data.replace("adm_type_", "")
    admin_wizard[ADMIN_ID] = {"step": "WAITING_AGE", "category": acc_type}

    await q.message.edit_text(f"Selected: <b>{acc_type.capitalize()} Acc</b>\n\n<b>Step 2:</b> Send <b>Account Age</b> (e.g. <code>Fresh</code>, <code>2022 Aged</code>, <code>6 Months Old</code>):", parse_mode="HTML")

async def handle_admin_wizard_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ADMIN_ID or uid not in admin_wizard:
        return

    state = admin_wizard[uid]
    step = state.get("step")

    if step == "WAITING_AGE":
        state["age"] = update.message.text.strip()
        state["step"] = "WAITING_PRICE"
        await update.message.reply_text("<b>Step 3:</b> Enter <b>Price</b> in USD (e.g. <code>4.5</code> or <code>10</code>):", parse_mode="HTML")

    elif step == "WAITING_PRICE":
        try:
            state["price"] = float(update.message.text.strip())
            state["step"] = "WAITING_DATA"
            await update.message.reply_text("<b>Step 4:</b> Send <b>Account Details / Stock Data</b> (Session, OTP Link, Phone, etc.):", parse_mode="HTML")
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number for price (e.g. <code>5.0</code>):", parse_mode="HTML")

    elif step == "WAITING_DATA":
        global item_counter
        state["data"] = update.message.text.strip()
        
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
            f"• <b>Price:</b> ${state['price']:.2f}\n"
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
        await update.message.reply_text(f"✅ Added ${amt:.2f} to <code>{uid}</code>", parse_mode="HTML")
        await context.bot.send_message(chat_id=uid, text=f"🎉 <b>${amt:.2f} Credited to your Wallet!</b>", parse_mode="HTML")
    except Exception:
        await update.message.reply_text("❌ <b>Wrong Format!</b>\nUse: <code>/addbal UserID | Amount</code>", parse_mode="HTML")

async def cmd_viewstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not items:
        await update.message.reply_text("Store is currently empty.")
        return
    txt = "<b>📊 CURRENT STOCK IN STORE:</b>\n\n"
    for i in items:
        txt += f"• ID: {i['id']} [{i['category'].upper()}] | Age: {clean_html(i['age'])} — ${i['price']}\n  Data: <code>{clean_html(i['data'])}</code>\n\n"
    await update.message.reply_text(txt, parse_mode="HTML")

def main():
    threading.Thread(target=run_flask, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    # User Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start, pattern="^btn_main$"))
    app.add_handler(CallbackQueryHandler(show_categories, pattern="^btn_categories$"))
    app.add_handler(CallbackQueryHandler(category_stock_list, pattern="^cat_"))
    app.add_handler(CallbackQueryHandler(buy_confirm, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(pay_item, pattern="^pay_"))
    app.add_handler(CallbackQueryHandler(user_profile, pattern="^btn_profile$"))
    app.add_handler(CallbackQueryHandler(deposit_info, pattern="^btn_add_bal$"))
    app.add_handler(CallbackQueryHandler(support_info, pattern="^btn_support$"))

    # Admin Commands
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CallbackQueryHandler(admin_wizard_callback, pattern="^adm_type_"))
    app.add_handler(CommandHandler("addbal", cmd_addbal))
    app.add_handler(CommandHandler("viewstock", cmd_viewstock))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_wizard_input))

    app.run_polling()

if __name__ == "__main__":
    main()
