import os
import asyncio
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
# Mathematical Sans-Serif Plain conversion function (non bold, non italic)
# ------------------------------------------------------------------------------
def to_math_sans_plain(text: str) -> str:
    result = []
    for ch in text:
        if 'A' <= ch <= 'Z':
            # Mathematical Sans-Serif Uppercase: U+1D5A0 to U+1D5B9
            result.append(chr(ord(ch) - ord('A') + 0x1D5A0))
        elif 'a' <= ch <= 'z':
            # Mathematical Sans-Serif Lowercase: U+1D5BA to U+1D5D3
            result.append(chr(ord(ch) - ord('a') + 0x1D5BA))
        elif '0' <= ch <= '9':
            # Mathematical Sans-Serif Digits: U+1D7E2 to U+1D7EB
            result.append(chr(ord(ch) - ord('0') + 0x1D7E2))
        else:
            result.append(ch)
    return ''.join(result)

# ------------------------------------------------------------------------------
# (Optional) Format number for numbering using the same style
# ------------------------------------------------------------------------------
def format_number(num: int) -> str:
    num_str = str(num).zfill(3)
    return to_math_sans_plain(num_str)

# ------------------------------------------------------------------------------
# Helper: Wrap text in an HTML blockquote
# ------------------------------------------------------------------------------
def blockquote(text: str) -> str:
    return f"<blockquote>{text}</blockquote>"

# ------------------------------------------------------------------------------
# Remove unwanted sentences (fixed phrases and numeric markers) from caption
# ------------------------------------------------------------------------------
def remove_unwanted_sentences(text: str) -> str:
    unwanted_phrases = [
        "Batch » Maths Spl-30 (Pre+Mains)",
        "»Download By➵➵ᴹᴿ°ຮ𝖆𝖈𝖍𝖎𝖓࿐²⁴⁷",
        "»Download By➵ᴹᴿ°ຮ𝖆𝖈𝖍𝖎𝖓࿐²⁴⁷"
    ]
    for phrase in unwanted_phrases:
        text = text.replace(phrase, "")
    # Remove markers like "001).", "002).", ... up to "300)."
    text = re.sub(r'\b(?:0\d{2}|[1-2]\d{2}|300)\)\.', '', text)
    return text.strip()

# ------------------------------------------------------------------------------
# Custom function to process text starting from "Class Date"
# ------------------------------------------------------------------------------
def apply_custom_quote_formatting(text: str, numbering: str) -> str:
    keyword = "class date"
    lower_text = text.lower()
    idx = lower_text.find(keyword)
    if idx != -1:
        # Extract text from "Class Date" onward
        block_text = text[idx:].strip()
        # Remove any newline characters to force a single line
        block_text = ' '.join(block_text.split())
        # Convert the block text to Mathematical Sans-Serif Plain style
        block_text_converted = to_math_sans_plain(block_text)
        # Prepend the numbering inside the blockquote before "Class Date"
        block_text_final = numbering + " " + block_text_converted
        # Wrap in blockquote tags
        blockquoted = blockquote(block_text_final)
        # Get any text before "Class Date" (if present)
        prefix = text[:idx].strip()
        if prefix:
            return prefix + " " + blockquoted
        else:
            return blockquoted
    else:
        # If keyword not found, simply return the cleaned text (optionally converted)
        return to_math_sans_plain(text)

# ------------------------------------------------------------------------------
# /start command: provides instructions to the user
# ------------------------------------------------------------------------------
@bot.on_message(filters.command("start"))
async def start(client, message: Message):
    instructions = (
        "<b>Welcome!</b>\n"
        "This bot automatically numbers file captions and applies custom blockquote formatting for the portion of the caption starting from the keyword \"Class Date\".\n\n"
        "<b>Commands:</b>\n"
        "• <code>/reset</code> - Reset numbering to " + format_number(1) + "\n"
        "• <code>/set &lt;number&gt;</code> - Set numbering starting from a custom number (e.g. <code>/set 051</code>)\n"
        "• Send any file with a caption that contains \"Class Date\". The bot will take the text from \"Class Date\" onward, convert it into non-bold, non-italic Unicode (Mathematical Sans‑Serif Plain), prepend numbering to it, and wrap it in a blockquote on a single line."
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
    await message.reply("✅ Numbering has been reset to " + format_number(current_number), parse_mode=enums.ParseMode.HTML)

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
        await message.reply("✅ Numbering set to " + format_number(current_number), parse_mode=enums.ParseMode.HTML)
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

    # Get the original caption and clean it.
    orig_caption = message.caption or ""
    cleaned_caption = remove_unwanted_sentences(orig_caption)
    # Get numbering in Mathematical Sans-Serif Plain style.
    numbering = format_number(num)
    # Apply custom quote formatting on the text starting from "Class Date"
    new_caption = apply_custom_quote_formatting(cleaned_caption, numbering)

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
