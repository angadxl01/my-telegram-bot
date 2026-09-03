import asyncio
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait
from pyrogram.raw import functions, types
from flask import Flask
import os
import threading
import json
import random
import urllib.request
import urllib.error

# ==================== CONFIGURATION ====================
API_ID = 36645562
API_HASH = "ccad405579d80b82492abbf4a7777907"
BOT_TOKEN = "8822648253:AAGZroIwI4F7udtFlhABotrsqjAXm_qcSq4"
ADMIN_ID = 8895089247

# Upstash Redis Configuration
UPSTASH_URL = "https://mint-hyena-222078.upstash.io"
UPSTASH_TOKEN = "gQAAAAAAA2N-AAIgcDEzZmE1ZWVjODVhYjE0MTgzOTE3ODRhYjQwNDU5MWNjMQ"
# =======================================================

web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is alive and running with Upstash Redis!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

app = Client(
    "dms_forward_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

user_states = {}
temp_login_data = {}
bot_users = set()
saved_channels = []
user_messages = {}
temp_join_data = {}
active_campaigns = {}
vip_users = {}
valid_redeem_codes = {"VIP2026": 30}

# ==================== REDIS HELPER FUNCTIONS ====================
def redis_get(key):
    try:
        req = urllib.request.Request(
            f"{UPSTASH_URL}/get/{key}", 
            headers={"Authorization": f"Bearer {UPSTASH_TOKEN}"}
        )
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode())
            val = res.get("result")
            if val:
                return json.loads(val)
    except Exception as e:
        print(f"Redis Get Error: {e}")
    return []

def redis_set(key, data):
    try:
        payload = json.dumps(["SET", key, json.dumps(data)]).encode("utf-8")
        req = urllib.request.Request(
            UPSTASH_URL, 
            data=payload, 
            headers={
                "Authorization": f"Bearer {UPSTASH_TOKEN}",
                "Content-Type": "application/json"
            }
        )
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"Redis Set Error: {e}")
    return None

def load_accounts():
    return redis_get("saved_accounts")

def save_accounts_data(accounts):
    redis_set("saved_accounts", accounts)

saved_accounts = load_accounts()
# ===============================================================

def get_main_menu(user_id):
    is_vip = user_id in vip_users or user_id == ADMIN_ID
    vip_text = "⭐ VIP Active (Premium)" if is_vip else "⭐ Go VIP Premium"
    
    buttons = [
        [InlineKeyboardButton("🚀 Start Mass DM Campaign", callback_data="start_campaign")],
        [
            InlineKeyboardButton("✍️ Set Message", callback_data="set_message"),
            InlineKeyboardButton("👀 Preview Message", callback_data="preview_message")
        ],
        [
            InlineKeyboardButton("👤 My Account", callback_data="my_account"),
            InlineKeyboardButton(vip_text, callback_data="vip_premium")
        ],
        [
            InlineKeyboardButton("🎁 Redeem Code", callback_data="redeem_code"),
            InlineKeyboardButton("➕ Add Account (Login)", callback_data="add_account")
        ],
        [
            InlineKeyboardButton("❌ Remove Account", callback_data="remove_account"),
            InlineKeyboardButton("📢 My Channels", callback_data="my_channels")
        ],
        [InlineKeyboardButton("🤝 Join Request DM", callback_data="join_request_dm")],
        [
            InlineKeyboardButton("❓ How to Use", callback_data="how_to_use"),
            InlineKeyboardButton("🛠️ Support", callback_data="support")
        ]
    ]
    if user_id == ADMIN_ID:
        buttons.insert(0, [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(buttons)

def get_admin_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 Total Stats", callback_data="admin_stats"),
            InlineKeyboardButton("📢 Broadcast Msg", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton("📂 All Accounts", callback_data="admin_view_accounts"),
            InlineKeyboardButton("🎁 Create Redeem Code", callback_data="admin_create_code")
        ],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
    ])

@app.on_message(filters.command("start"))
async def start_handler(client, message):
    user_id = message.from_user.id
    bot_users.add(user_id)
    user_states.pop(user_id, None)
    await message.reply_text(
        "**🤖 DMS FORWARD BOT MENU**\n\nWelcome! Please choose an option below:",
        reply_markup=get_main_menu(user_id)
    )

@app.on_message(filters.command("admin"))
async def admin_command_handler(client, message):
    user_id = message.from_user.id
    if user_id != ADMIN_ID:
        await message.reply_text("❌ You are not authorized!")
        return
    await message.reply_text("**👑 WELCOME TO ADMIN PANEL**", reply_markup=get_admin_menu())

@app.on_callback_query()
async def callback_handler(client, callback_query):
    data = callback_query.data
    user_id = callback_query.from_user.id
    await callback_query.answer()
    
    if data == "main_menu":
        user_states.pop(user_id, None)
        await callback_query.message.edit_text(
            "**🤖 DMS FORWARD BOT MENU**\n\nWelcome back!",
            reply_markup=get_main_menu(user_id)
        )
    elif data == "admin_panel":
        if user_id == ADMIN_ID:
            await callback_query.message.edit_text("👑 **ADMIN PANEL**", reply_markup=get_admin_menu())
    elif data == "admin_stats":
        if user_id == ADMIN_ID:
            global saved_accounts
            saved_accounts = load_accounts()
            stats_text = (
                f"📊 **STATS:**\nUsers: {len(bot_users)}\n"
                f"Accounts: {len(saved_accounts)}\nVIP Users: {len(vip_users)}\nChannels: {len(saved_channels)}"
            )
            await callback_query.message.edit_text(stats_text, reply_markup=get_admin_menu())
    elif data == "admin_broadcast":
        if user_id == ADMIN_ID:
            user_states[user_id] = "waiting_for_broadcast"
            await callback_query.message.reply_text("📢 Send broadcast message:")
    elif data == "admin_view_accounts":
        if user_id == ADMIN_ID:
            accs = "\n".join([f"• User ID: `{a['user_id']}`" for a in saved_accounts]) or "None"
            await callback_query.message.reply_text(f"📂 **Saved Accounts:**\n{accs}")
    elif data == "admin_create_code":
        if user_id == ADMIN_ID:
            user_states[user_id] = "waiting_for_new_code"
            await callback_query.message.reply_text("🎁 Naya redeem code aur days format mein bhejein (jaise: `PROMO50 15`):")
    elif data == "set_message":
        user_states[user_id] = "waiting_for_message"
        await callback_query.message.reply_text(
            "✍️ **Set Campaign Message**\n\nPlease send the text message you want to send in your campaigns:"
        )
    elif data == "preview_message":
        msg = user_messages.get(user_id, "⚠️ No message set yet! Please use 'Set Message' first.")
        await callback_query.message.reply_text(
            f"👀 **Your Message Preview:**\n\n{msg}",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]])
        )
    elif data == "my_account":
        ac = len([a for a in saved_accounts if a['user_id'] == user_id])
        cc = len([c for c in saved_channels if c['user_id'] == user_id])
        vip_status = "Active 🌟" if user_id in vip_users or user_id == ADMIN_ID else "Free ❌"
        await callback_query.message.reply_text(f"👤 **Your Account Info:**\nLogged-in Accounts: {ac}\nChannels: {cc}\nVIP Status: {vip_status}")
    elif data == "vip_premium":
        await callback_query.message.reply_text(
            "⭐ **VIP Premium Benefits:**\n\n- Unlimited mass DM campaigns\n- Priority message delivery speed",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]])
        )
    elif data == "redeem_code":
        user_states[user_id] = "waiting_for_redeem_code"
        await callback_query.message.reply_text(
            "🎁 **Redeem VIP Code**\n\nEnter your VIP redeem code below:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]])
        )
    elif data == "add_account":
        user_states[user_id] = "waiting_for_phone"
        temp_login_data[user_id] = {}
        await callback_query.message.reply_text(
            "📱 **Add Telegram Account**\n\nPlease enter your phone number with country code (e.g., `+919876543210`):",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]])
        )
    elif data == "remove_account":
        global saved_accounts
        saved_accounts = load_accounts()
        user_accs = [a for a in saved_accounts if a['user_id'] == user_id]
        if not user_accs:
            await callback_query.message.reply_text("⚠️ Aapka koi account saved nahi hai!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]))
            return
        buttons = []
        for index, acc in enumerate(saved_accounts):
            if acc['user_id'] == user_id:
                buttons.append([InlineKeyboardButton(f"🗑️ Remove Account #{index+1}", callback_data=f"del_acc_{index}")])
        buttons.append([InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")])
        await callback_query.message.reply_text("❌ **Remove Account**", reply_markup=InlineKeyboardMarkup(buttons))
    elif data.startswith("del_acc_"):
        try:
            acc_index = int(data.split("_")[2])
            saved_accounts = load_accounts()
            if acc_index < len(saved_accounts) and saved_accounts[acc_index]['user_id'] == user_id:
                saved_accounts.pop(acc_index)
                save_accounts_data(saved_accounts)
                await callback_query.message.edit_text("✅ Account successfully removed!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]))
            else:
                await callback_query.message.edit_text("⚠️ Invalid account.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]))
        except Exception as e:
            await callback_query.message.edit_text(f"❌ Error: {str(e)}")
    elif data == "join_request_dm":
        user_states[user_id] = "waiting_for_join_channel"
        await callback_query.message.reply_text(
            "🤝 **JOIN REQUEST DM**\n\nSend DMs directly to users who have pending join requests on your channel.\n\n"
            "📢 **Send your channel link, username or ID:**\n• Public/Private Link: `t.me/...` or `t.me/+...`\n• Username: `@MyChannel`\n• ID: `-100xxxxxxxxxx`",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="main_menu")]])
        )
    elif data.startswith("stop_camp_"):
        c_id = data.split("_")[2]
        if c_id in active_campaigns:
            active_campaigns[c_id] = False
            await callback_query.answer("Stopping campaign...", show_alert=True)
    elif data == "how_to_use":
        await callback_query.message.reply_text("❓ Guide on how to use the bot.")
    elif data == "support":
        await callback_query.message.reply_text("🛠️ Support contact link.")

@app.on_message(filters.text & ~filters.command(["start", "admin"]))
async def handle_text_messages(client, message):
    user_id = message.from_user.id
    text = message.text.strip()
    state = user_states.get(user_id)
    bot_users.add(user_id)
    
    if state == "waiting_for_broadcast" and user_id == ADMIN_ID:
        user_states.pop(user_id, None)
        await message.reply_text("⏳ Broadcasting...")
        for u_id in list(bot_users):
            try: await client.send_message(u_id, f"📢 **Broadcast:**\n{text}")
            except: pass
        await message.reply_text("✅ Broadcast completed!")

    elif state == "waiting_for_new_code" and user_id == ADMIN_ID:
        try:
            parts = text.split()
            code = parts[0]
            days = int(parts[1])
            valid_redeem_codes[code] = days
            user_states.pop(user_id, None)
            await message.reply_text(f"✅ Code created: `{code}` for {days} days", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]))
        except:
            await message.reply_text("⚠️ Invalid format! Use: `CODE DAYS`")

    elif state == "waiting_for_redeem_code":
        user_states.pop(user_id, None)
        if text in valid_redeem_codes:
            days = valid_redeem_codes.pop(text)
            vip_users[user_id] = days
            await message.reply_text(f"🎉 VIP Premium activated for `{days}` days!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]))
        else:
            await message.reply_text("❌ Invalid or Expired Code!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]))
        
    elif state == "waiting_for_message":
        user_messages[user_id] = text
        user_states.pop(user_id, None)
        await message.reply_text("✅ **Message Saved Successfully!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]))

    elif state == "waiting_for_phone":
        phone_number = text
        temp_login_data[user_id]["phone"] = phone_number
        status_msg = await message.reply_text("⏳ Connecting to Telegram and sending OTP...")
        try:
            temp_client = Client(f"temp_{user_id}", api_id=API_ID, api_hash=API_HASH, in_memory=True)
            await temp_client.connect()
            sent_code = await temp_client.send_code(phone_number)
            temp_login_data[user_id]["client"] = temp_client
            temp_login_data[user_id]["phone_code_hash"] = sent_code.phone_code_hash
            user_states[user_id] = "waiting_for_otp"
            await status_msg.edit_text("✅ OTP sent to your Telegram app!\n\nPlease send the OTP code with spaces (e.g., `1 2 3 4 5`):")
        except Exception as e:
            await status_msg.edit_text(f"❌ Error: `{str(e)}`")
            user_states.pop(user_id, None)
            temp_login_data.pop(user_id, None)

    elif state == "waiting_for_otp":
        otp_code = text.replace(" ", "")
        login_data = temp_login_data.get(user_id, {})
        temp_client = login_data.get("client")
        phone = login_data.get("phone")
        phone_code_hash = login_data.get("phone_code_hash")
        status_msg = await message.reply_text("⏳ Verifying OTP...")
        try:
            await temp_client.sign_in(phone, phone_code_hash, otp_code)
            session_string = await temp_client.export_session_string()
            await temp_client.disconnect()
            
            global saved_accounts
            saved_accounts = load_accounts()
            saved_accounts.append({"user_id": user_id, "session": session_string})
            save_accounts_data(saved_accounts)
            
            user_states.pop(user_id, None)
            temp_login_data.pop(user_id, None)
            await status_msg.edit_text("✅ **Account Login Successful & Saved to Redis!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]))
        except Exception as e:
            if "SESSION_PASSWORD_NEEDED" in str(e) or "Password" in str(e):
                user_states[user_id] = "waiting_for_2fa"
                await status_msg.edit_text("🔐 Two-Step Verification (2FA) is enabled.\n\nPlease send your account password:")
            else:
                await status_msg.edit_text(f"❌ Login Failed: `{str(e)}`")
                try: await temp_client.disconnect()
                except: pass
                user_states.pop(user_id, None)
                temp_login_data.pop(user_id, None)

    elif state == "waiting_for_2fa":
        password = text
        login_data = temp_login_data.get(user_id, {})
        temp_client = login_data.get("client")
        status_msg = await message.reply_text("⏳ Verifying Password...")
        try:
            await temp_client.check_password(password)
            session_string = await temp_client.export_session_string()
            await temp_client.disconnect()
            
            global saved_accounts
            saved_accounts = load_accounts()
            saved_accounts.append({"user_id": user_id, "session": session_string})
            save_accounts_data(saved_accounts)
            
            user_states.pop(user_id, None)
            temp_login_data.pop(user_id, None)
            await status_msg.edit_text("✅ **Account Login Successful with 2FA & Saved to Redis!**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]))
        except Exception as e:
            await status_msg.edit_text(f"❌ Invalid Password: `{str(e)}`")
            try: await temp_client.disconnect()
            except: pass
            user_states.pop(user_id, None)
            temp_login_data.pop(user_id, None)

    elif state == "waiting_for_join_channel":
        global saved_accounts
        saved_accounts = load_accounts()
        user_accs = [a for a in saved_accounts if a['user_id'] == user_id]
        if not user_accs:
            await message.reply_text("⚠️ Pehle 'Add Account (Login)' se account add karein!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]))
            user_states.pop(user_id, None)
            return

        status_msg = await message.reply_text("⏳ Fetching pending join requests...")
        session_str = user_accs[0]["session"]
        try:
            sender_client = Client(f"join_fetch_{user_id}_{random.randint(1000,9999)}", api_id=API_ID, api_hash=API_HASH, session_string=session_str, in_memory=True)
            await sender_client.start()
            
            channel_input = text.strip()
            chat_obj = None
            
            if "+" in channel_input or "joinchat" in channel_input or ("t.me/" in channel_input and not channel_input.split("t.me/")[-1].startswith("@") and not channel_input.split("t.me/")[-1].replace("-", "").isdigit()):
                try:
                    chat_obj = await sender_client.join_chat(channel_input)
                except Exception:
                    chat_obj = await sender_client.get_chat(channel_input)
            else:
                if "t.me/" in channel_input:
                    channel_input = channel_input.split("t.me/")[-1].strip("/")
                
                if channel_input.startswith("-100") or (channel_input.isdigit() and len(channel_input) > 5) or (channel_input.startswith("-") and channel_input[1:].isdigit()):
                    chat_target = int(channel_input)
                elif channel_input.startswith("@"):
                    chat_target = channel_input
                else:
                    chat_target = "@" + channel_input

                chat_obj = await sender_client.get_chat(chat_target)
            
            pending_users = []
            async for req in sender_client.get_chat_join_requests(chat_obj.id):
                if req.user:
                    if not req.user.is_deleted and not req.u
