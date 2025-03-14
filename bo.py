import os
import re
import asyncio
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
# Convert text to Mathematical Sans‑Serif Plain (non bold, non italic) for numbering
# ------------------------------------------------------------------------------
def to_math_sans_plain(text: str) -> str:
    result = []
    for ch in text:
        if 'A' <= ch <= 'Z':
            result.append(chr(ord(ch) - ord('A') + 0x1D5A0))
        elif 'a' <= ch <= 'z':
            result.append(chr(ord(ch) - ord('a') + 0x1D5BA))
        elif '0' <= ch <= '9':
            result.append(chr(ord(ch) - ord('0') + 0x1D7E2))
        else:
            result.append(ch)
    return ''.join(result)

def format_number(num: int) -> str:
    num_str = str(num).zfill(3)
    return to_math_sans_plain(num_str)

def blockquote(text: str) -> str:
    return f"<blockquote>{text}</blockquote>"

# ------------------------------------------------------------------------------
# Clean extracted text:
# - Remove unwanted phrases "ATM Batch" and "Atm Maths" (case-insensitive)
# - Remove any non-alphabet characters (keeping spaces)
# - Normalize whitespace.
# ------------------------------------------------------------------------------
def clean_extracted_text(text: str) -> str:
    text = re.sub(r"(?i)\bATM Batch\b", "", text)
    text = re.sub(r"(?i)\bAtm Maths\b", "", text)
    cleaned = re.sub(r"[^A-Za-z\s]", "", text)
    return " ".join(cleaned.split())

# ------------------------------------------------------------------------------
# Process caption for the new format:
#
# - Find "Title:" (case-insensitive)
# - Then find the first closing parenthesis ")" after "Title:".
# - Then find the delimiter "||" after the ")".
# - Then find the final marker "➸ᴹᴿ°ℂr‌𝕒c‌k‌єr࿐⁰³" after "||".
#
# The blockquoted part is the cleaned text between ")" and "||" (excluding both).
# The non-blockquoted part is the text from after "||" up to the final marker.
# ------------------------------------------------------------------------------
def process_caption(text: str, numbering: str) -> str:
    lower_text = text.lower()
    idx_title = lower_text.find("title:")
    if idx_title == -1:
        return blockquote(f"[{numbering}]") + "\n" + text.strip()
    idx_closeParen = text.find(")", idx_title)
    if idx_closeParen == -1:
        return blockquote(f"[{numbering}]") + "\n" + text.strip()
    idx_delim = text.find("||", idx_closeParen)
    if idx_delim == -1:
        return blockquote(f"[{numbering}]") + "\n" + text.strip()
    idx_marker = text.find("➸ᴹᴿ°ℂr‌𝕒c‌k‌єr࿐⁰³", idx_delim)
    if idx_marker == -1:
        return blockquote(f"[{numbering}]") + "\n" + text.strip()
    
    # Extract text between ")" and "||" for blockquoting.
    block_text = text[idx_closeParen + 1: idx_delim].strip()
    cleaned_text = clean_extracted_text(block_text)
    
    # Extract text from after "||" up to the final marker.
    non_block_text = text[idx_delim + len("||"): idx_marker].strip()
    
    return blockquote(f"[{numbering}] {cleaned_text}") + "\n" + non_block_text

# ------------------------------------------------------------------------------
# Handler for media messages:
# - Process caption for video files.
# - For PDF files, remove the caption entirely.
# ------------------------------------------------------------------------------
@bot.on_message(filters.media)
async def handle_media(client, message: Message):
    global current_number
    if message.video:
        async with number_lock:
            num = current_number
            current_number += 1
            save_number(current_number)
        orig_caption = message.caption or ""
        numbering = format_number(num)
        new_caption = process_caption(orig_caption, numbering)
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
        pass

# ------------------------------------------------------------------------------
# /start command: provides instructions to the user
# ------------------------------------------------------------------------------
@bot.on_message(filters.command("start"))
async def start(client, message: Message):
    instructions = (
        "<b>Welcome!</b>\n"
        "This bot processes captions with the following structure:\n"
        "• The caption contains a 'Title:' line. After 'Title:', there is a closing parenthesis \")\".\n"
        "• Following the \")\", the text up to the delimiter '||' is extracted, cleaned (removing non-alphabet characters and the phrases 'ATM Batch' and 'Atm Maths'), and used for blockquoting with numbering.\n"
        "• The text from after '||' up to the marker '➸ᴹᴿ°ℂr‌𝕒c‌k‌єr࿐⁰³' is appended as plain text.\n"
        "Send a video file with a caption in this format to see the processing in action."
    )
    await message.reply(instructions, parse_mode=enums.ParseMode.HTML)

@bot.on_message(filters.command("reset"))
async def reset(client, message: Message):
    global current_number
    async with number_lock:
        current_number = 1
        save_number(current_number)
    await message.reply("✅ Numbering has been reset to " + format_number(current_number), parse_mode=enums.ParseMode.HTML)

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
# Start the bot
# ------------------------------------------------------------------------------
bot.run()