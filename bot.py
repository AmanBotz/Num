import os
import asyncio
from threading import Thread
from pyrogram import Client, filters
from pyrogram.types import Message
from flask import Flask

# Load configuration from environment variables
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise ValueError("❌ API_ID, API_HASH, or BOT_TOKEN is missing! Set them in environment variables.")

# Initialize the Pyrogram bot client
bot = Client("file_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# Initialize Flask for the Koyeb health check endpoint
health_app = Flask(__name__)

@health_app.route('/health')
def health_check():
    return "OK", 200

def run_flask():
    health_app.run(port=8000, host="0.0.0.0")

flask_thread = Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

# Global numbering state (persistent)
NUMBERING_FILE = "numbering_state.txt"

def load_number():
    if os.path.exists(NUMBERING_FILE):
        try:
            with open(NUMBERING_FILE, "r") as f:
                return int(f.read().strip())
        except Exception:
            return 1
    return 1

def save_number(number):
    with open(NUMBERING_FILE, "w") as f:
        f.write(str(number))

current_number = load_number()

# Process bulk forwarded messages
async def process_bulk_messages(messages):
    global current_number
    messages.sort(key=lambda m: m.message_id)  # Keep order consistent
    for msg in messages:
        original_caption = msg.caption or ""
        new_caption = f"{str(current_number).zfill(3)}) {original_caption}"
        try:
            await msg.edit_caption(caption=new_caption)
        except Exception as e:
            print(f"❌ Error editing caption in bulk forwarding: {e}")
        current_number += 1
    save_number(current_number)

# Command: /start
@bot.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply(
        "👋 **Welcome!**\n"
        "This bot automatically adds numbering to file captions.\n\n"
        "🔹 **Commands:**\n"
        "✅ `/reset` - Reset numbering to `001)`\n"
        "✅ `/set <number>` - Start numbering from any number (e.g., `/set 051)`)\n"
        "✅ Forward multiple files, and their captions will be numbered sequentially!"
    )

# Command: /reset (Reset numbering to 001)
@bot.on_message(filters.command("reset"))
async def reset(client, message: Message):
    global current_number
    current_number = 1
    save_number(current_number)
    await message.reply("✅ Numbering reset to `001)`.")

# Command: /set <number> (Set numbering to a custom number)
@bot.on_message(filters.command("set"))
async def set_number(client, message: Message):
    global current_number
    try:
        parts = message.text.split()
        if len(parts) < 2:
            raise ValueError
        number = int(parts[1])
        if number < 1:
            raise ValueError
        current_number = number
        save_number(current_number)
        await message.reply(f"✅ Numbering set to `{str(current_number).zfill(3)})`.")
    except (IndexError, ValueError):
        await message.reply("❌ **Usage:** `/set <number>`\nExample: `/set 051)`")

# Handling forwarded files (Documents, Photos, Videos, Audio)
@bot.on_message(filters.forwarded & (filters.document | filters.photo | filters.audio | filters.video))
async def handle_forwarded_files(client, message: Message):
    global current_number

    # If multiple files are forwarded at once, process them as a batch
    if message.chat.type == "channel":
        # Bulk forwarded messages from another channel
        chat_id = message.chat.id
        messages = await client.get_chat_history(chat_id, limit=10)  # Fetch last 10 messages to detect bulk forwarding
        forwarded_messages = [msg for msg in messages if msg.forward_date and msg.message_id >= message.message_id - 9]
        await process_bulk_messages(forwarded_messages)
    else:
        # Single forwarded file
        original_caption = message.caption or ""
        new_caption = f"{str(current_number).zfill(3)}) {original_caption}"
        try:
            await message.edit_caption(caption=new_caption)
        except Exception as e:
            print(f"❌ Error editing caption for forwarded file: {e}")
        current_number += 1
        save_number(current_number)

# Start the bot
bot.run()
