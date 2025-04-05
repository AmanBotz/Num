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
# - Remove numbers with dots (e.g., "1.", "2.")
# - Remove unwanted phrases "ATM Batch" and "Atm Maths" (case-insensitive)
# - Remove any non-alphabet characters (keeping spaces)
# - Normalize whitespace
# ------------------------------------------------------------------------------
def clean_extracted_text(text: str) -> str:
    # Remove numbered bullets
    text = re.sub(r"\b\d+\.\s*", "", text)
    # Remove specific phrases
    text = re.sub(r"(?i)\bATM Batch\b", "", text)
    text = re.sub(r"(?i)\bAtm Maths\b", "", text)
    # Remove non-alphabet characters
    cleaned = re.sub(r"[^A-Za-z\s]", "", text)
    return " ".join(cleaned.split())

# ------------------------------------------------------------------------------
# Process caption for the new format:
# 1. Split caption at "//" delimiter
# 2. Extract text before "//" for blockquote
# 3. Remove all text starting from "Batch" in the remaining text
# ------------------------------------------------------------------------------
def process_caption(text: str, numbering: str) -> str:
    # Split caption at first "//" occurrence
    parts = text.split("//", 1)
    before_delim = parts[0].strip()
    after_delim = parts[1].strip() if len(parts) > 1 else ""

    # Clean the text before delimiter
    cleaned_before = clean_extracted_text(before_delim)
    blockquote_text = f"[{numbering}] {cleaned_before}" if cleaned_before else f"[{numbering}]"

    # Process text after delimiter
    if after_delim:
        # Remove everything from "Batch" onwards
        after_delim = re.sub(r"(?i)\bBatch.*", "", after_delim).strip()

    return blockquote(blockquote_text) + (f"\n{after_delim}" if after_delim else "")

# ------------------------------------------------------------------------------
# Handler for media messages
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

# ------------------------------------------------------------------------------
# Command handlers
# ------------------------------------------------------------------------------
@bot.on_message(filters.command("start"))
async def start(client, message: Message):
    instructions = (
        "<b>Welcome!</b>\n"
        "This bot processes captions with the following structure:\n"
        "• Use '//' to separate the main title from additional text\n"
        "• Text before '//' will be formatted with automatic numbering\n"
        "• Everything after 'Batch' (case-insensitive) will be removed\n"
        "Example:\n"
        "<i>Problem 1 // Solution details Batch 3</i>\n"
        "Becomes:\n"
        "<blockquote>[𝟘𝟘𝟙] Problem 1</blockquote>\nSolution details"
    )
    await message.reply(instructions, parse_mode=enums.ParseMode.HTML)

@bot.on_message(filters.command("reset"))
async def reset(client, message: Message):
    global current_number
    async with number_lock:
        current_number = 1
        save_number(current_number)
    await message.reply("✅ Numbering reset to " + format_number(current_number), parse_mode=enums.ParseMode.HTML)

@bot.on_message(filters.command("set"))
async def set_number(client, message: Message):
    global current_number
    try:
        new_number = int(message.command[1])
        async with number_lock:
            current_number = new_number
            save_number(current_number)
        await message.reply(f"✅ Numbering set to {format_number(current_number)}", parse_mode=enums.ParseMode.HTML)
    except (IndexError, ValueError):
        await message.reply("❌ Invalid format. Use: /set 123", parse_mode=enums.ParseMode.HTML)

# ------------------------------------------------------------------------------
# Start the bot
# ------------------------------------------------------------------------------
bot.run()
