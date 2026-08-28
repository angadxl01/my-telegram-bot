import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

# Set your details here
BOT_TOKEN = "8906190418:AAEsPFEkD8OHqsMgwKFUKNR8IJcZmJI_3mc"
ADMIN_CHAT_ID = 8895089247 

# Simulated stock database
STOCK = [
    {"id": 1, "name": "+1 (USA) Aged Account - 2022", "price": 5.00, "details": "Phone: +1... | Session: app_session_key_data_here"},
    {"id": 2, "name": "+44 (UK) Fresh Account", "price": 3.50, "details": "Phone: +44... | Session: app_session_key_data_here"},
    {"id": 3, "name": "@RareHandle Username", "price": 15.00, "details": "Transfer auth code: 987654"},
]

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message with main menu."""
    keyboard = [
        [InlineKeyboardButton("📦 View Available Stock", callback_data="view_stock")],
        [InlineKeyboardButton("💳 Payment Methods", callback_data="payment_info")],
        [InlineKeyboardButton("👨‍💻 Support / Contact", callback_data="support_info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "<b>Welcome to TG Store! 👋</b>\n\n"
        "Select an option below to browse available Telegram IDs, channels, or stock."
    )
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await update.callback_query.message.edit_text(welcome_text, reply_markup=reply_markup, parse_mode="HTML")

async def stock_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of available stock items."""
    query = update.callback_query
    await query.answer()

    keyboard = []
    for item in STOCK:
        btn_text = f"{item['name']} - ${item['price']:.2f}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"buy_{item['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.message.edit_text("<b>🛍️ Available Stock:</b>\nClick an item to purchase:", reply_markup=reply_markup, parse_mode="HTML")

async def buy_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle item selection for purchase."""
    query = update.callback_query
    await query.answer()
    
    item_id = int(query.data.split("_")[1])
    item = next((i for i in STOCK if i["id"] == item_id), None)
    
    if not item:
        await query.message.edit_text("Item no longer available.")
        return

    keyboard = [
        [InlineKeyboardButton("✅ Confirm & Request Purchase", callback_data=f"confirm_{item['id']}")],
        [InlineKeyboardButton("🔙 Back to Stock", callback_data="view_stock")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    msg = (
        f"<b>Item:</b> {item['name']}\n"
        f"<b>Price:</b> ${item['price']:.2f}\n\n"
        "To buy, click confirm below to notify the admin for manual payment processing."
    )
    await query.message.edit_text(msg, reply_markup=reply_markup, parse_mode="HTML")

async def confirm_purchase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Notify admin of purchase request."""
    query = update.callback_query
    await query.answer()

    item_id = int(query.data.split("_")[1])
    item = next((i for i in STOCK if i["id"] == item_id), None)
    user = query.from_user

    # Notify user
    await query.message.edit_text(
        f"✅ <b>Order Placed!</b>\n\n"
        f"You requested: <b>{item['name']}</b>\n"
        f"Please contact the admin (@YourAdminUsername) to complete payment.",
        parse_mode="HTML"
    )

    # Notify Admin
    admin_msg = (
        f"🚨 <b>New Order Request!</b>\n\n"
        f"<b>User:</b> @{user.username} (ID: <code>{user.id}</code>)\n"
        f"<b>Item:</b> {item['name']}\n"
        f"<b>Price:</b> ${item['price']:.2f}\n"
        f"<b>Item Data:</b> <code>{item['details']}</code>"
    )
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg, parse_mode="HTML")

async def payment_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display payment information."""
    query = update.callback_query
    await query.answer()

    msg = (
        "<b>💳 Accepted Payment Methods:</b>\n\n"
        "• USDT (TRC20): <code>YOUR_USDT_ADDRESS_HERE</code>\n"
        "• BTC: <code>YOUR_BTC_ADDRESS_HERE</code>\n"
        "• UPI / Other: Contact Admin\n\n"
        "After payment, send proof to @YourAdminUsername to receive your account details."
    )
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]]
    await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

async def support_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display support contact info."""
    query = update.callback_query
    await query.answer()

    msg = "<b>👨‍💻 Support:</b>\n\nFor any inquiries or issues, contact @YourAdminUsername."
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]]
    await query.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(start, pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(stock_menu, pattern="^view_stock$"))
    app.add_handler(CallbackQueryHandler(payment_info, pattern="^payment_info$"))
    app.add_handler(CallbackQueryHandler(support_info, pattern="^support_info$"))
    app.add_handler(CallbackQueryHandler(buy_item, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(confirm_purchase, pattern="^confirm_"))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
