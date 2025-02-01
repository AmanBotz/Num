import os
import asyncio
from threading import Thread
from pyrogram import Client, filters
from pyrogram.types import Message
from flask import Flask

# ------------------------------------------------------------------------------
# Load configuration from environment variables
# ------------------------------------------------------------------------------
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise ValueError("❌ API_ID, API_HASH, or BOT_TOKEN is missing! Set them in your environment variables.")

# ------------------------------------------------------------------------------
# Initialize the Pyrogram bot client
# ------------------------------------------------------------------------------
bot = Client("file_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# ------------------------------------------------------------------------------
# Initialize Flask for the Koyeb health check endpoint
# ------------------------------------------------------------------------------
health_app = Flask(__name__)

@health_app.route('/health')
def health_check():
    return "OK", 200

def run_flask():
    health_app.run(port=8000, host="0.0.0.0")

flask_thread = Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

# ------------------------------------------------------------------------------
# Persistent numbering state
# ------------------------------------------------------------------------------
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
number_lock = asyncio.Lock()

# ------------------------------------------------------------------------------
# /start command: provides instructions
# ------------------------------------------------------------------------------
@bot.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply(
        "👋 **Welcome!**\n"
        "This bot automatically adds numbering to file captions.\n\n"
        "🔹 **Commands:**\n"
        "• `/reset` - Reset numbering to `001)`\n"
        "• `/set <number>` - Set numbering starting from a custom number (e.g. `/set 051)`)\n"
        "• Send any file and its caption will be updated with a sequential number!"
    )

# ------------------------------------------------------------------------------
# /reset command: resets numbering to 001)
# ------------------------------------------------------------------------------
@bot.on_message(filters.command("reset"))
async def reset(client, message: Message):
    global current_number
    async with number_lock:
        current_number = 1
        save_number(current_number)
    await message.reply("✅ Numbering has been reset to `001)`.")

# ------------------------------------------------------------------------------
# /set command: sets numbering to a custom value
# ------------------------------------------------------------------------------
@bot.on_message(filters.command("set"))
async def set_number(client, message: Message):
    global current_number
    try:
        parts = message.text.split()
        if len(parts) < 2:
            raise ValueError
        new_number = int(parts[1])
        if new_number < 1:
            raise ValueError
        async with number_lock:
            current_number = new_number
            save_number(current_number)
        await message.reply(f"✅ Numbering set to `{str(current_number).zfill(3)})`.")
    except Exception:
        await message.reply("❌ **Usage:** `/set <number>`\nExample: `/set 051)`")

# ------------------------------------------------------------------------------
# Handler for all media messages (documents, photos, videos, audio)
# ------------------------------------------------------------------------------
@bot.on_message(filters.media)
async def handle_media(client, message: Message):
    global current_number
    # Use the lock to guarantee each message gets a unique sequential number
    async with number_lock:
        num = current_number
        current_number += 1
        save_number(current_number)
    # Build the new caption with the format "001) <original caption>"
    new_caption = f"{str(num).zfill(3)}) " + (message.caption or "")

    # If the message is in a channel, try to edit the caption (do not resend file)
    if message.chat.type == "channel":
        try:
            await message.edit_caption(caption=new_caption)
        except Exception as e:
            print(f"❌ Error editing caption in channel for message {message.message_id}: {e}")
    else:
        # For private chats or groups, try to edit the caption; if that fails, reply with the media
        try:
            await message.edit_caption(caption=new_caption)
        except Exception as e:
            print(f"❌ Error editing caption for message {message.message_id}: {e}")
            if message.document:
                await message.reply_document(document=message.document.file_id, caption=new_caption)
            elif message.photo:
                await message.reply_photo(photo=message.photo.file_id, caption=new_caption)
            elif message.video:
                await message.reply_video(video=message.video.file_id, caption=new_caption)
            elif message.audio:
                await message.reply_audio(audio=message.audio.file_id, caption=new_caption)

bot.run()
