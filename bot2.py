import os
import re
from threading import Thread
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from flask import Flask

# ------------------------------------------------------------------------------
# Load configuration from environment variables
# ------------------------------------------------------------------------------
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN2 = os.getenv("BOT_TOKEN2", "")

if not API_ID or not API_HASH or not BOT_TOKEN2:
    raise ValueError("❌ API_ID, API_HASH, or BOT_TOKEN2 is missing! Set them in your environment variables.")

# ------------------------------------------------------------------------------
# Initialize the Pyrogram bot client for bot2
# ------------------------------------------------------------------------------
bot2 = Client("file_bot2", bot_token=BOT_TOKEN2, api_id=API_ID, api_hash=API_HASH)

# ------------------------------------------------------------------------------
# Initialize Flask for the health check endpoint (on a separate port)
# ------------------------------------------------------------------------------
health_app = Flask(__name__)

@health_app.route('/health2')
def health_check():
    return "OK", 200

def run_flask():
    # Run on port 8001 to avoid conflict with bot.py
    health_app.run(port=8001, host="0.0.0.0")

flask_thread = Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

# ------------------------------------------------------------------------------
# Process caption: remove the unwanted text but preserve all HTML formatting.
# If a blockquote becomes empty, insert a non‑breaking space.
# ------------------------------------------------------------------------------
def process_caption(text: str) -> str:
    # Remove the unwanted text globally.
    new_text = text.replace("𝖢𝗅𝖺𝗌𝗌 𝖣𝖺𝗍𝖾 »", "")
    # Replace any blockquote that is empty (or only whitespace) with one containing a non-breaking space.
    new_text = re.sub(r"(?i)(<blockquote>\s*</blockquote>)", "<blockquote>&nbsp;</blockquote>", new_text)
    return new_text

# ------------------------------------------------------------------------------
# Handler for media messages
# ------------------------------------------------------------------------------
@bot2.on_message(filters.media)
async def handle_media(client, message: Message):
    if message.video:
        orig_caption = message.caption or ""
        new_caption = process_caption(orig_caption)
        try:
            await message.edit_caption(new_caption, parse_mode=enums.ParseMode.HTML)
        except Exception as e:
            print(f"Error editing caption: {e}")
            await message.reply_video(message.video.file_id, caption=new_caption, parse_mode=enums.ParseMode.HTML)
    elif message.document and message.document.mime_type == "application/pdf":
        try:
            await message.edit_caption("", parse_mode=enums.ParseMode.HTML)
        except Exception as e:
            print(f"Error editing caption for PDF: {e}")
            await message.reply_document(message.document.file_id, caption="", parse_mode=enums.ParseMode.HTML)
    else:
        # For other file types, leave the caption unchanged.
        pass

# ------------------------------------------------------------------------------
# /start command: provides instructions to the user
# ------------------------------------------------------------------------------
@bot2.on_message(filters.command("start"))
async def start(client, message: Message):
    instructions = (
        "<b>Welcome to Bot2!</b>\n"
        "This bot automatically removes the text \"𝖢𝗅𝖺𝗌𝗌 𝖣𝖺𝗍𝖾 »\" from video file captions while preserving all formatting, including blockquotes.\n\n"
        "Simply send a video file with a caption containing the unwanted text to see the processing in action."
    )
    await message.reply(instructions, parse_mode=enums.ParseMode.HTML)

# ------------------------------------------------------------------------------
# Start bot2
# ------------------------------------------------------------------------------
bot2.run()
