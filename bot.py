import os
import asyncio
from threading import Thread
from pyrogram import Client, filters, enums  # Import enums
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
# Initialize Flask for the health check endpoint
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
# Bold Unicode digits mapping and formatting function
# ------------------------------------------------------------------------------
def format_bold_number(num: int) -> str:
    num_str = str(num).zfill(3)
    bold_digits = {
        "0": "𝟶", "1": "𝟷", "2": "𝟸", "3": "𝟹", "4": "𝟺",
        "5": "𝟻", "6": "𝟼", "7": "𝟽", "8": "𝟾", "9": "𝟿"
    }
    return "[" + "".join(bold_digits[digit] for digit in num_str) + "]"

# ------------------------------------------------------------------------------
# Helper: Simulated blockquote formatting in HTML.
# We simply wrap the text in <blockquote> tags.
# ------------------------------------------------------------------------------
def blockquote(text: str) -> str:
    return f"<blockquote>{text}</blockquote>"

# ------------------------------------------------------------------------------
# Apply quote formatting from the "Class Date" keyword onward.
# If "Class Date" is found (case-insensitive) in the caption,
# then everything from that keyword onward is wrapped in a blockquote.
# ------------------------------------------------------------------------------
def apply_quote_formatting(text: str, keyword: str = "Class Date") -> str:
    lower_text = text.lower()
    keyword_lower = keyword.lower()
    idx = lower_text.find(keyword_lower)
    if idx != -1:
        before = text[:idx].strip()
        after = text[idx:].strip()
        quoted = blockquote(after)
        if before:
            return before + "\n" + quoted
        else:
            return quoted
    return text

# ------------------------------------------------------------------------------
# /start command: provides instructions to the user
# ------------------------------------------------------------------------------
@bot.on_message(filters.command("start"))
async def start(client, message: Message):
    instructions = (
        "<b>Welcome!</b>\n"
        "This bot automatically numbers file captions and applies quote formatting for the portion of the caption starting from the keyword \"Class Date\".\n\n"
        "<b>Commands:</b>\n"
        "• <code>/reset</code> - Reset numbering to " + format_bold_number(1) + "\n"
        "• <code>/set &lt;number&gt;</code> - Set numbering starting from a custom number (e.g. <code>/set 051</code>)\n"
        "• Send any file with a caption that contains \"Class Date\" and everything from that keyword onward will be formatted as a quote."
    )
    await message.reply(instructions, parse_mode=enums.ParseMode.HTML)

# ------------------------------------------------------------------------------
# /reset command: resets numbering to 1
# ------------------------------------------------------------------------------
@bot.on_message(filters.command("reset"))
async def reset(client, message: Message):
    global current_number
    async with number_lock:
        current_number = 1
        save_number(current_number)
    await message.reply("✅ Numbering has been reset to " + format_bold_number(current_number), parse_mode=enums.ParseMode.HTML)

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
        await message.reply("✅ Numbering set to " + format_bold_number(current_number), parse_mode=enums.ParseMode.HTML)
    except Exception:
        await message.reply("❌ <b>Usage:</b> <code>/set &lt;number&gt;</code>\nExample: <code>/set 051</code>", parse_mode=enums.ParseMode.HTML)

# ------------------------------------------------------------------------------
# Handler for all media messages (documents, photos, videos, audio)
# ------------------------------------------------------------------------------
@bot.on_message(filters.media)
async def handle_media(client, message: Message):
    global current_number

    async with number_lock:
        num = current_number
        current_number += 1
        save_number(current_number)

    orig_caption = message.caption or ""
    numbering = format_bold_number(num)
    # Apply quote formatting from "Class Date" onward.
    formatted_caption_body = apply_quote_formatting(orig_caption)
    new_caption = f"{numbering} {formatted_caption_body}"

    try:
        await message.edit_caption(new_caption, parse_mode=enums.ParseMode.HTML)
    except Exception as e:
        print(f"Error editing caption: {e}")
        # Fallback: resend the media with the new caption.
        if message.document:
            await message.reply_document(message.document.file_id, caption=new_caption, parse_mode=enums.ParseMode.HTML)
        elif message.photo:
            await message.reply_photo(message.photo.file_id, caption=new_caption, parse_mode=enums.ParseMode.HTML)
        elif message.video:
            await message.reply_video(message.video.file_id, caption=new_caption, parse_mode=enums.ParseMode.HTML)
        elif message.audio:
            await message.reply_audio(message.audio.file_id, caption=new_caption, parse_mode=enums.ParseMode.HTML)

# ------------------------------------------------------------------------------
# Start the bot
# ------------------------------------------------------------------------------
bot.run()
