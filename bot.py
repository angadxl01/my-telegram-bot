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

# --- FLASK WEBSERVER FOR RENDER ---
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot is running 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host='0.0.0.0', port=port)

# --- BOT DATABASE & STATE ---
stock_db = [
    {"id": 1, "name": "+1 (USA) Aged Account", "price": 5.00, "details": "Session: app_session_data_1"},
    {"id": 2, "name": "+44 (UK) Fresh Account", "price": 3.50, "details": "Session: app_session_data_2"}
]
item_counter = 3
admin_states = {}

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- USER HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("📦 View Available Stock", callback_data="view_stock")],
        [InlineKeyboardButton("💳 Payment Methods", callback_data="payment_info")],
        [InlineKeyboardButton("👨‍💻 Support / Contact", callback_data="support_info")]
    ]
    welcome_text = "<b>Welcome to TG Store! 👋</b>\n\nSelect an option below to browse stock:"
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def stock_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if not stock_db:
        keyboard = [[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]
        await query.message.edit_text("❌ Currently Out of Stock! Check back later.", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    keyboard = []
    for item in stock_db:
        keyboard.append([InlineKeyboardButton(f"{item['name']} - ${item['price']:.2f}", callback_data=f"buy_{item['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")])
    await query.message.edit_text("<b>🛍️ Available Stock:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def buy_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    item_id = int(query.data.split("_")[1])
    item = next((i for i in stock_db if i["id"] == item_id), None)
    
    if not item:
        await query.message.edit_text("Item no longer available.")
        return

    keyboard = [
        [InlineKeyboardButton("✅ Confirm & Request Purchase", callback_data=f"confirm_{item['id']}")],
        [InlineKeyboardButton("🔙 Back to Stock", callback_data="view_stock")]
    ]
    msg = f"<b>Item:</b> {item['name']}\n<b>Price:</b> ${item['price']:.2f}\n\nClick below to confirm request."
    await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def confirm_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    item_id = int(query.data.split("_")[1])
    item = next((i for i in stock_db if i["id"] == item_id), None)
    user = query.from_user

    if not item:
        await query.message.edit_text("Item not found.")
        return

    await query.message.edit_text(
        f"✅ <b>Order Placed!</b>\n\nYour request for <b>{item['name']}</b> has been sent to Admin.",
        parse_mode="HTML"
    )

    admin_kb = [
        [InlineKeyboardButton("✅ Deliver Stock to User", callback_data=f"deliver_{user.id}_{item['id']}"),
         InlineKeyboardButton("❌ Reject Order", callback_data=f"reject_{user.id}")]
    ]
    admin_msg = (
        f"🚨 <b>New Buy Request!</b>\n\n"
        f"<b>User:</b> @{user.username} (ID: <code>{user.id}</code>)\n"
        f"<b>Item:</b> {item['name']}\n"
        f"<b>Price:</b> ${item['price']:.2f}\n"
        f"<b>Data:</b> <code>{item['details']}</code>"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_msg, reply_markup=InlineKeyboardMarkup(admin_kb), parse_mode="HTML")

async def payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    msg = "<b>💳 Payment Details:</b>\n\nContact Admin for payment details."
    keyboard = [[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]
    await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def support_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    msg = "<b>👨‍💻 Support:</b>\n\nFor support, contact admin."
    keyboard = [[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]
    await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

# --- ADMIN HANDLERS ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Access Denied!")
        return

    keyboard = [
        [InlineKeyboardButton("➕ Add New Stock", callback_data="admin_add")],
        [InlineKeyboardButton("🗑️ Delete Stock", callback_data="admin_delete_menu")],
        [InlineKeyboardButton("📊 View Total Stock", callback_data="admin_view")]
    ]
    msg = "<b>⚙️ Admin Dashboard</b>"
    if update.message:
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await update.callback_query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query.from_user.id != ADMIN_ID:
        await query.answer("Access Denied", show_alert=True)
        return

    await query.answer()
    data = query.data

    if data == "admin_view":
        text = "<b>📦 Current Stock Database:</b>\n\n"
        for i in stock_db:
            text += f"• <b>ID {i['id']}:</b> {i['name']} - ${i['price']}\n  Data: <code>{i['details']}</code>\n"
        if not stock_db:
            text = "No stock available."
        keyboard = [[InlineKeyboardButton("🔙 Back to Admin", callback_data="admin_home")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data == "admin_add":
        admin_states[query.from_user.id] = "WAITING_STOCK_DATA"
        await query.message.edit_text(
            "<b>➕ Add Stock Item</b>\n\nSend format:\n<code>Name | Price | Details</code>",
            parse_mode="HTML"
        )

    elif data == "admin_delete_menu":
        if not stock_db:
            await query.message.edit_text("No stock to delete.")
            return
        keyboard = []
        for item in stock_db:
            keyboard.append([InlineKeyboardButton(f"❌ Delete ID {item['id']}: {item['name']}", callback_data=f"del_{item['id']}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_home")])
        await query.message.edit_text("<b>Select item:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

    elif data.startswith("del_"):
        item_id = int(data.split("_")[1])
        global stock_db
        stock_db = [i for i in stock_db if i["id"] != item_id]
        await query.message.edit_text(f"✅ Item ID {item_id} deleted.")

    elif data == "admin_home":
        await admin_panel(update, context)

    elif data.startswith("deliver_"):
        _, target_user_id, item_id = data.split("_")
        target_user_id, item_id = int(target_user_id), int(item_id)
        item = next((i for i in stock_db if i["id"] == item_id), None)
        
        if item:
            try:
                await context.bot.send_message(
                    chat_id=target_user_id,
                    text=f"🎉 <b>Item Details:</b>\n\n<b>Item:</b> {item['name']}\n<b>Data:</b>\n<code>{item['details']}</code>",
                    parse_mode="HTML"
                )
                await query.message.edit_text(f"✅ Delivered to User ID: {target_user_id}")
            except Exception as e:
                await query.message.edit_text(f"❌ Delivery Failed: {str(e)}")

    elif data.startswith("reject_"):
        target_user_id = int(data.split("_")[1])
        await context.bot.send_message(chat_id=target_user_id, text="❌ Order request rejected.")
        await query.message.edit_text("Order Rejected.")

async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id == ADMIN_ID and admin_states.get(user_id) == "WAITING_STOCK_DATA":
        global item_counter
        try:
            name, price, details = update.message.text.split("|")
            stock_db.append({
                "id": item_counter,
                "name": name.strip(),
                "price": float(price.strip()),
                "details": details.strip()
            })
            item_counter += 1
            admin_states[user_id] = None
            await update.message.reply_text("✅ Stock added successfully!")
        except Exception:
            await update.message.reply_text("❌ Format error! Use: `Name | Price | Details`")

def main():
    threading.Thread(target=run_flask, daemon=True).start()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    
    app.add_handler(CallbackQueryHandler(start, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(stock_menu, pattern="^view_stock$"))
    app.add_handler(CallbackQueryHandler(payment_info, pattern="^payment_info$"))
    app.add_handler(CallbackQueryHandler(support_info, pattern="^support_info$"))
    app.add_handler(CallbackQueryHandler(buy_item, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(confirm_purchase, pattern="^confirm_"))
    
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_|^del_|^deliver_|^reject_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_text))

    app.run_polling()

if __name__ == "__main__":
    main()
               
