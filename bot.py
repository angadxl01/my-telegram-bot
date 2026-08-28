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

# Configuration
BOT_TOKEN = "8794925442:AAFIHaUAJM8ZXt2guEN7Lq2kKyTTKzECWqw"
ADMIN_ID = 8895089247

# Webserver for Render free hosting
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot status: Running 24/7"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

# Temporary Storage
users = {}  # {user_id: {"balance": 0.0, "orders": 0}}
categories = ["🇺🇸 USA Accounts", "🇬🇧 UK Accounts", "⭐️ TG Premium", "💎 Username Stock"]
items = [
    {"id": 1, "cat": "🇺🇸 USA Accounts", "title": "USA Aged 2022 Account", "price": 4.5, "data": "Session: US_2022_KEY_9921"},
    {"id": 2, "cat": "🇬🇧 UK Accounts", "title": "UK Fresh Account", "price": 3.0, "data": "Session: UK_FRESH_KEY_1092"}
]
item_id_counter = 3
admin_action = {}

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# User Data Helper
def get_user(uid):
    if uid not in users:
        users[uid] = {"balance": 0.0, "orders": 0}
    return users[uid]

# Main Menu
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    u_data = get_user(u.id)

    kb = [
        [InlineKeyboardButton("🛍️ Browse Store", callback_data="btn_cats")],
        [InlineKeyboardButton("👤 My Profile", callback_data="btn_profile"), InlineKeyboardButton("💵 Add Balance", callback_data="btn_add_bal")],
        [InlineKeyboardButton("👨‍💻 Support / Contact", callback_data="btn_support")]
    ]
    txt = (
        f"<b>Welcome to TG Store! 👋</b>\n\n"
        f"👤 <b>User:</b> {u.first_name}\n"
        f"🆔 <b>ID:</b> <code>{u.id}</code>\n"
        f"💰 <b>Wallet Balance:</b> ${u_data['balance']:.2f}\n\n"
        f"Select an option below to start buying stock:"
    )

    if update.message:
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    else:
        await update.callback_query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

# User Profile
async def user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    u = q.from_user
    u_data = get_user(u.id)

    txt = (
        f"<b>👤 PROFILE INFO</b>\n\n"
        f"• <b>Name:</b> {u.first_name}\n"
        f"• <b>User ID:</b> <code>{u.id}</code>\n"
        f"• <b>Balance:</b> ${u_data['balance']:.2f}\n"
        f"• <b>Completed Orders:</b> {u_data['orders']}"
    )
    kb = [
        [InlineKeyboardButton("💵 Deposit Funds", callback_data="btn_add_bal")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data="btn_main")]
    ]
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

# Categories Menu
async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    kb = []
    for c in categories:
        kb.append([InlineKeyboardButton(c, callback_data=f"cat_{c}")])
    kb.append([InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")])

    await q.message.edit_text("<b>📂 Select Category:</b>", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

# Category Items
async def category_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cat_name = q.data.replace("cat_", "")

    cat_items = [i for i in items if i["cat"] == cat_name]

    if not cat_items:
        kb = [[InlineKeyboardButton("🔙 Back", callback_data="btn_cats")]]
        await q.message.edit_text(f"❌ No stock in <b>{cat_name}</b> right now.", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    kb = []
    for i in cat_items:
        kb.append([InlineKeyboardButton(f"{i['title']} - ${i['price']:.2f}", callback_data=f"buy_item_{i['id']}")])
    kb.append([InlineKeyboardButton("🔙 Back", callback_data="btn_cats")])

    await q.message.edit_text(f"<b>📦 Category: {cat_name}</b>\nChoose item to buy:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

# Item View & Auto Purchase
async def item_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    item_id = int(q.data.split("_")[2])
    target_item = next((i for i in items if i["id"] == item_id), None)

    if not target_item:
        await q.message.edit_text("Item unavailable.")
        return

    u_data = get_user(q.from_user.id)
    kb = [
        [InlineKeyboardButton("⚡ Buy Instantly", callback_data=f"purchase_{target_item['id']}")],
        [InlineKeyboardButton("🔙 Back", callback_data="btn_cats")]
    ]
    txt = (
        f"<b>🛒 Item Details:</b>\n\n"
        f"• <b>Name:</b> {target_item['title']}\n"
        f"• <b>Category:</b> {target_item['cat']}\n"
        f"• <b>Price:</b> ${target_item['price']:.2f}\n\n"
        f"<b>Your Wallet:</b> ${u_data['balance']:.2f}"
    )
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def process_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    item_id = int(q.data.split("_")[1])
    target_item = next((i for i in items if i["id"] == item_id), None)

    if not target_item:
        await q.message.edit_text("Item is sold out!")
        return

    u_data = get_user(uid)

    if u_data["balance"] < target_item["price"]:
        kb = [
            [InlineKeyboardButton("💵 Deposit Money", callback_data="btn_add_bal")],
            [InlineKeyboardButton("🔙 Back", callback_data="btn_cats")]
        ]
        await q.message.edit_text(
            f"❌ <b>Insufficient Funds!</b>\n\nPrice: ${target_item['price']:.2f}\nYour Balance: ${u_data['balance']:.2f}",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML"
        )
        return

    # Auto Deduct and Deliver
    u_data["balance"] -= target_item["price"]
    u_data["orders"] += 1
    items.remove(target_item)

    await q.message.edit_text(
        f"✅ <b>PURCHASE SUCCESSFUL!</b>\n\n"
        f"<b>Item:</b> {target_item['title']}\n"
        f"<b>Price:</b> ${target_item['price']:.2f}\n\n"
        f"🔑 <b>Account Data:</b>\n<code>{target_item['data']}</code>",
        parse_mode="HTML"
    )

    # Notify Admin
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🛍️ <b>New Auto Sale!</b>\nUser: @{q.from_user.username} (<code>{uid}</code>)\nItem: {target_item['title']}\nPrice: ${target_item['price']:.2f}",
        parse_mode="HTML"
    )

async def add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    txt = (
        "<b>💳 ADD BALANCE / FUND WALLET</b>\n\n"
        "Send payment to Admin:\n"
        "• <b>USDT (TRC20):</b> <code>YOUR_USDT_ADDRESS</code>\n"
        "• <b>UPI ID:</b> <code>yourupi@upi</code>\n\n"
        "<i>Contact Admin with payment screenshot to credit balance.</i>"
    )
    kb = [[InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]]
    await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kb = [[InlineKeyboardButton("🔙 Main Menu", callback_data="btn_main")]]
    await q.message.edit_text("<b>👨‍💻 Support:</b>\nContact admin for help or custom orders.", reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

# Admin Dashboard
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized access.")
        return

    kb = [
        [InlineKeyboardButton("➕ Add Stock", callback_data="adm_add_stock")],
        [InlineKeyboardButton("💳 Add User Balance", callback_data="adm_add_bal")],
        [InlineKeyboardButton("📊 View Store Stats", callback_data="adm_stats")]
    ]
    txt = "<b>⚙️ ADMIN CONTROL PANEL</b>\nChoose an action:"
    if update.message:
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
    else:
        await update.callback_query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.from_user.id != ADMIN_ID:
        return
    await q.answer()
    data = q.data

    if data == "adm_stats":
        txt = f"<b>📊 STORE STATS</b>\n\nTotal In-Stock Items: {len(items)}\nTotal Registered Users: {len(users)}"
        kb = [[InlineKeyboardButton("🔙 Back to Admin", callback_data="adm_home")]]
        await q.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

    elif data == "adm_add_bal":
        admin_action[ADMIN_ID] = "ADD_BAL"
        await q.message.edit_text("Send User ID & Amount:\nFormat: <code>USER_ID | AMOUNT</code>\nExample: <code>8895089247 | 10.50</code>", parse_mode="HTML")

    elif data == "adm_add_stock":
        admin_action[ADMIN_ID] = "ADD_STOCK"
        cat_str = ", ".join(categories)
        await q.message.edit_text(
            f"Available Categories:\n<i>{cat_str}</i>\n\nSend format:\n<code>Category | Title | Price | Data</code>\n\n"
            f"Example:\n<code>🇺🇸 USA Accounts | USA Aged | 4.5 | Session Data</code>",
            parse_mode="HTML"
        )

    elif data == "adm_home":
        await admin_panel(update, context)

async def admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid != ADMIN_ID:
        return

    act = admin_action.get(uid)

    if act == "ADD_BAL":
        try:
            target_id, amt = update.message.text.split("|")
            target_id = int(target_id.strip())
            amt = float(amt.strip())

            u_data = get_user(target_id)
            u_data["balance"] += amt
            admin_action[uid] = None

            await update.message.reply_text(f"✅ Added ${amt:.2f} to User ID <code>{target_id}</code>.", parse_mode="HTML")
            await context.bot.send_message(chat_id=target_id, text=f"🎉 <b>Balance Added!</b>\n\n${amt:.2f} credited to your account.", parse_mode="HTML")
        except Exception:
            await update.message.reply_text("❌ Wrong Format! Use: `USER_ID | AMOUNT`")

    elif act == "ADD_STOCK":
        global item_id_counter
        try:
            cat, title, price, data = update.message.text.split("|")
            items.append({
                "id": item_id_counter,
                "cat": cat.strip(),
                "title": title.strip(),
                "price": float(price.strip()),
                "data": data.strip()
            })
            item_id_counter += 1
            admin_action[uid] = None
            await update.message.reply_text("✅ Stock Added Successfully!")
        except Exception:
            await update.message.reply_text("❌ Wrong Format! Use: `Category | Title | Price | Data`")

def main():
    threading.Thread(target=run_flask, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))

    app.add_handler(CallbackQueryHandler(start, pattern="^btn_main$"))
    app.add_handler(CallbackQueryHandler(show_categories, pattern="^btn_cats$"))
    app.add_handler(CallbackQueryHandler(user_profile, pattern="^btn_profile$"))
    app.add_handler(CallbackQueryHandler(add_balance, pattern="^btn_add_bal$"))
    app.add_handler(CallbackQueryHandler(support, pattern="^btn_support$"))

    app.add_handler(CallbackQueryHandler(category_items, pattern="^cat_"))
    app.add_handler(CallbackQueryHandler(item_view, pattern="^buy_item_"))
    app.add_handler(CallbackQueryHandler(process_purchase, pattern="^purchase_"))

    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^adm_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text))

    app.run_polling()

if __name__ == "__main__":
    main()
