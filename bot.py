import os
import asyncio
from threading import Thread
from pyrogram import Client, filters
from pyrogram.types import Message
from flask import Flask

# ------------------------------------------------------------------------------
# Load configuration from environment variables (set these in Koyeb)
# ------------------------------------------------------------------------------
try:
    API_ID = int(os.getenv("API_ID", "0"))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
except Exception as e:
    raise ValueError("Error reading environment variables: " + str(e))

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise ValueError("Missing one or more required environment variables: API_ID, API_HASH, BOT_TOKEN")

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

# Start the Flask app in a separate thread
flask_thread = Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

# ------------------------------------------------------------------------------
# Global numbering state (persisted to file)
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

# ------------------------------------------------------------------------------
# Global dictionary to hold media groups in channels
# ------------------------------------------------------------------------------
media_groups = {}  # key: media_group_id, value: list of Message objects

# ------------------------------------------------------------------------------
# Asynchronous function to process a media group after a short delay
# ------------------------------------------------------------------------------
async def process_media_group(group_id: str):
    # Wait for additional messages in the same media group
    await asyncio.sleep(2)  # adjust delay as needed
    global current_number
    messages = media_groups.pop(group_id, [])
    # Sort messages by message_id to have a consistent order
    messages.sort(key=lambda m: m.message_id)
    for msg in messages:
        original_caption = msg.caption or ""
        # Build new caption with sequential numbering in the format "001) <original caption>"
        new_caption = f"{str(current_number).zfill(3)}) {original_caption}"
        try:
            await msg.edit_caption(caption=new_caption)
        except Exception as e:
            print(f"Error editing caption for message {msg.message_id} in group {group_id}: {e}")
        current_number += 1
    save_number(current_number)

# ------------------------------------------------------------------------------
# Bot command: /start
# ------------------------------------------------------------------------------
@bot.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply(
        "👋 Welcome! This bot automatically numbers files that you upload.\n\n"
        "🔹 **Commands Available:**\n"
        "✅ /reset - Reset numbering to 001)\n"
        "✅ /set <number> - Start numbering from any number (e.g. /set 051)\n"
        "✅ Just send any file, and it will be numbered!"
    )

# ------------------------------------------------------------------------------
# Bot command: /reset (reset numbering to 001)
# ------------------------------------------------------------------------------
@bot.on_message(filters.command("reset"))
async def reset(client, message: Message):
    global current_number
    current_number = 1
    save_number(current_number)
    await message.reply("✅ Numbering has been reset to 001).")

# ------------------------------------------------------------------------------
# Bot command: /set <number> (set numbering to a custom starting number)
# ------------------------------------------------------------------------------
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
        await message.reply(f"✅ Numbering started from {str(current_number).zfill(3)})")
    except (IndexError, ValueError):
        await message.reply("❌ Usage: /set <number>\nExample: /set 051")

# ------------------------------------------------------------------------------
# Bot handler for file uploads (supports documents, photos, audio, and videos)
# ------------------------------------------------------------------------------
@bot.on_message(filters.document | filters.photo | filters.audio | filters.video)
async def handle_file(client, message: Message):
    global current_number

    # Preserve the original caption if any
    original_caption = message.caption or ""
    # Build the new caption with numbering in the format "001) <original caption>"
    new_caption = f"{str(current_number).zfill(3)}) {original_caption}"

    # Check if the message is in a channel
    if message.chat.type == "channel":
        # Check if this message is part of a media group
        if message.media_group_id:
            group_id = message.media_group_id
            # Add message to the media group list
            if group_id not in media_groups:
                media_groups[group_id] = []
            media_groups[group_id].append(message)
            # If this is the first message in the group, schedule processing
            if len(media_groups[group_id]) == 1:
                asyncio.create_task(process_media_group(group_id))
        else:
            # Single message in channel (not a media group), simply edit its caption
            try:
                await message.edit_caption(caption=new_caption)
            except Exception as e:
                print(f"Error editing caption in channel: {e}")
            current_number += 1
            save_number(current_number)
    else:
        # For private chats or groups, simply reply with the file using the new caption.
        if message.document:
            await message.reply_document(document=message.document.file_id, caption=new_caption)
        elif message.audio:
            await message.reply_audio(audio=message.audio.file_id, caption=new_caption)
        elif message.video:
            await message.reply_video(video=message.video.file_id, caption=new_caption)
        elif message.photo:
            await message.reply_photo(photo=message.photo.file_id, caption=new_caption)
        current_number += 1
        save_number(current_number)

# ------------------------------------------------------------------------------
# Start the bot
# ------------------------------------------------------------------------------
bot.run()
