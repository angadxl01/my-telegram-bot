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

# --- CONFIGURATION ---
BOT_TOKEN = "8906190418:AAEsPFEkD8OHqsMgwKFUKNR8IJcZmJI_3mc"
ADMIN_ID = 8895089247

# --- RENDER FLASK WEBSERVER ---
web_app = Flask('')

@web_app.route('/')
def home():
    return "Nova TG Store Bot is 24/7 Active!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

# --- DATABASE (In-Memory) ---
users_db = {}  # {user_id: {"balance": 0.00, "orders": 0}}
categories_db = ["🇺🇸 USA Accounts", "🇬🇧 UK Accounts", "⭐️ Telegram Premium", "💎 Username Stock"]
stock_db = [
    {"id": 1, "category": "🇺🇸 USA Accounts", "name": "USA Aged Account (2022)", "price": 4.50, "data": "Phone: +1... | Session Key: xyz"},
    {"id": 2, "category": "🇬🇧 UK Accounts", "name": "UK Fresh OTP Account", "price": 3.00, "data": "Phone: +44... | OTP Link: abc"},
]
item_counter = 3
admin_states = {}

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- HELPER FUNCTIONS ---
def get_user_data(user_id):
    if user_id not in users_db:
        users_db[user_id] = {"balance": 0.00, "orders": 0}
    return users_db[user_id]

# --- USER INTERFACE HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    u_data = get_user_data(user.id)

    keyboard = [
        [InlineKeyboardButton("🛍️ Browse Categories", callback_data="categories")],
        [InlineKeyboardButton("👤 My Profile", callback_data="profile"), InlineKeyboardButton("💵 Add Balance", callback_data="add_balance")],
        [InlineKeyboardButton("📢 Channel", url="https://t.me/telegram"), InlineKeyboardButton("👨‍💻 Support", callback_data="support")]
    ]
    
    welcome_text = (
        f"<b>Welcome to Nova TG Store! ⚡️</b>\n\n"
        f"👤 <b>User:</b> {user.first_name}\n"
        f"🆔 <b>ID:</b> <code>{user.id}</code>\n"
        f"💰 <b>Balance:</b> ${u_data['balance']:.2f}\n\n"
        f"<i>Select an option below to buy Telegram Accounts, Premium & Stock instantly!</i>"
    )
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = query.from_user
    u_data = get_user_data(user.id)

    text = (
        f"<b>👤 YOUR PROFILE</b>\n\n"
        f"• <b>Name:</b> {user.first_name}\n"
        f"• <b>User ID:</b> <code>{user.id}</code>\n"
        f"• <b>Balance:</b> ${u_data['balance']:.2f}\n"
        f"• <b>Total Orders Completed:</b> {u_data['orders']}\n"
    )
    keyboard = [[InlineKeyboardButton("💳 Deposit Funds", callback_data="add_balance")], [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    keyboard = []
    for cat in categories_db:
        keyboard.append([InlineKeyboardButton(cat, callback_data=f"cat_{cat}")])
    keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])

    await query.message.edit_text("<b>📂 Choose a Category:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def show_category_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    category_name = query.data.replace("cat_", "")

    items = [item for item in stock_db if item["category"] == category_name]

    if not items:
        keyboard = [[InlineKeyboardButton("🔙 Back to Categories", callback_data="categories")]]
        await query.message.edit_text(f"❌ No stock available in <b>{category_name}</b> right now.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return

    keyboard = []
    for item in items:
        keyboard.append([InlineKeyboardButton(f"{item['name']} — ${item['price']:.2f}", callback_data=f"buy_item_{item['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 Back to Categories", callback_data="categories")])

    await query.message.edit_text(f"<b>📦 Stock in {category_name}:</b>\nSelect an item to purchase:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def item_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    item_id = int(query.data.split("_")[2])
    item = next((i for i in stock_db if i["id"] == item_id), None)

    if not item:
        await query.message.edit_text("Item sold out.")
        return

    u_data = get_user_data(query.from_user.id)

    keyboard = [
        [InlineKeyboardButton("⚡ Buy Now (Instant Delivery)", callback_data=f"confirm_buy_{item['id']}")],
        [InlineKeyboardButton("🔙 Back", callback_data="categories")]
    ]
    msg = (
        f"<b>🛒 Item Details:</b>\n\n"
        f"• <b>Name:</b> {item['name']}\n"
        f"• <b>Category:</b> {item['category']}\n"
        f"• <b>Price:</b> ${item['price']:.2f}\n\n"
        f"💳 <b>Your Balance:</b> ${u_data['balance']:.2f}"
    )
    await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def confirm_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    item_id = int(query.data.split("_")[2])
    item = next((i for i in stock_db if i["id"] == item_id), None)

    if not item:
        await query.message.edit_text("❌ Item no longer available.")
        return

    u_data = get_user_data(user_id)

    # Check Balance System
    if u_data["balance"] < item["price"]:
        keyboard = [
            [InlineKeyboardButton("💳 Deposit Balance", callback_data="add_balance")],
            [InlineKeyboardButton("🔙 Back", callback_data="categories")]
        ]
        await query.message.edit_text(
            f"❌ <b>Insufficient Funds!</b>\n\nItem Price: ${item['price']:.2f}\nYour Balance: ${u_data['balance']:.2f}\n\nPlease add funds to your wallet.",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML"
        )
        return

    # Auto Deduct & Deliver Stock
    u_data["balance"] -= item["price"]
    u_data["orders"] += 1
    stock_db.remove(item)

    await query.message.edit_text(
        f"🎉 <b>PURCHASE SUCCESSFUL!</b>\n\n"
        f"<b>Item:</b> {item['name']}\n"
        f"<b>Price Paid:</b> ${item['price']:.2f}\n\n"
        f"🔑 <b>Your Account Data / Stock:</b>\n<code>{item['data']}</code>\n\n"
        f"<i>Thank you for buying from Nova TG Store!</i>",
        parse_mode="HTML"
    )

    # Admin Alert
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🛍️ <b>Auto Sale Alert!</b>\nUser: @{query.from_user.username} (<code>{user_id}</code>)\nItem: {item['name']}\nPrice: ${item['price']:.2f}",
        parse_mode="HTML"
    )

async def add_balance_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    msg = (
        "<b>💳 ADD BALANCE / DEPOSIT</b>\n\n"
        "Send payment to Admin:\n"
        "• <b>USDT TRC20:</b> <code>YOUR_WALLET_ADDRESS</code>\n"
        "• <b>UPI ID:</b> <code>yourupi@upi</code>\n\n"
        "<i>After sending payment, contact Admin with screenshot to credit balance instantly!</i>"
    )
    keyboard = [[InlineKeyboardButton("👨‍💻 Send Payment Receipt", url="https://t.me/telegram")], [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]
    await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# --- ADMIN PANEL HANDLERS ---

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized Access!")
        return

    keyboard = [
        [InlineKeyboardButton("➕ Add Stock", callback_data="admin_add_stock")],
        [InlineKeyboardButton("💳 Add User Balance", callback_data="admin_add_bal")],
        [InlineKeyboardButton("📊 View Stock Stats", callback_data="admin_stats")]
    ]
    msg = "<b>⚡️ Nova Store Admin Dashboard</b>\nSelect action:"
    if update.message:
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await update.callback_query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        return
    await query.answer()
    data = query.data

    if data == "admin_stats":
        text = f"<b>📊 STORE STATISTICS</b>\n\nTotal In-Stock Items: {len(stock_db)}\nTotal Users Registered: {len(users_db)}"
        keyboard = [[InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_home")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "admin_add_bal":
        admin_states[ADMIN_ID] = "WAITING_ADD_BAL"
        await query.message.edit_text("<b>Send User ID and Amount to Add:</b>\n\nFormat: <code>USER_ID | AMOUNT</code>\nExample: <code>8895089247 | 10.0</code>", parse_mode="HTML")

    elif data == "admin_add_stock":
        admin_states[ADMIN_ID] = "WAITING_STOCK"
        cats = ", ".join(categories_db)
        await query.message.edit_text(
            f"<b>➕ Add New Stock</b>\n\nAvailable Categories:\n<i>{cats}</i>\n\n"
            f"Send details in format:\n<code>Category | Item Name | Price | Stock Data</code>\n\n"
            f"Example:\n<code>🇺🇸 USA Accounts | USA Aged 2021 | 5.00 | Phone: +123 Pass: xyz</code>",
            parse_mode="HTML"
        )

    elif data == "admin_home":
        await admin_panel(update, context)

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return

    state = admin_states.get(user_id)

    if state == "WAITING_ADD_BAL":
        try:
            target_id, amount = update.message.text.split("|")
            target_id = int(target_id.strip())
            amount = float(amount.strip())

            u_data = get_user_data(target_id)
            u_data["balance"] += amount
            admin_states[user_id] = None

            await update.message.reply_text(f"✅ Added ${amount:.2f} to User <code>{target_id}</code>. New Balance: ${u_data['balance']:.2f}", parse_mode="HTML")
            await context.bot.send_message(chat_id=target_id, text=f"🎉 <b>Balance Credited!</b>\n\n${amount:.2f} added to your wallet. Balance: ${u_data['balance']:.2f}", parse_mode="HTML")
        except Exception:
            await update.message.reply_text("❌ Invalid Format! Use: `USER_ID | AMOUNT`")

    elif state == "WAITING_STOCK":
        global item_counter
        try:
            cat, name, price, data = update.message.text.split("|")
            stock_db.append({
                "id": item_counter,
                "category": cat.strip(),
                "name": name.strip(),
                "price": float(price.strip()),
                "data": data.strip()
            })
            item_counter += 1
            admin_states[user_id] = None
            await update.message.reply_text("✅ Stock Added Successfully!")
        except Exception:
            await update.message.reply_text("❌ Invalid Format! Use: `Category | Name | Price | Data`")

def main():
    threading.Thread(target=run_flask, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))

    app.add_handler(CallbackQueryHandler(start, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(show_categories, pattern="^categories$"))
    app.add_handler(CallbackQueryHandler(show_category_items, pattern="^cat_"))
    app.add_handler(CallbackQueryHandler(item_details, pattern="^buy_item_"))
    app.add_handler(CallbackQueryHandler(confirm_purchase, pattern="^confirm_buy_"))
    app.add_handler(CallbackQueryHandler(user_profile, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(add_balance_info, pattern="^add_balance$"))

    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))

    app.run_polling()

if __name__ == "__main__":
    main()
