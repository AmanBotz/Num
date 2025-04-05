import os
import re
import asyncio
from threading import Thread
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from flask import Flask

# Configuration
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Client initialization
bot = Client("file_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# Flask health check
health_app = Flask(__name__)
@health_app.route('/health')
def health_check(): return "OK", 200
Thread(target=lambda: health_app.run(port=8000, host="0.0.0.0"), daemon=True).start()

# Numbering persistence
NUMBERING_FILE = "numbering_state.txt"
current_number = 1
number_lock = asyncio.Lock()

def load_number():
    try:
        with open(NUMBERING_FILE, "r") as f:
            return int(f.read().strip()) if os.path.exists(NUMBERING_FILE) else 1
    except: return 1

def save_number(num):
    with open(NUMBERING_FILE, "w") as f:
        f.write(str(num))

current_number = load_number()

# Font conversion
def to_math_sans_plain(text: str) -> str:
    converted = []
    for char in text:
        if 'A' <= char <= 'Z':
            converted.append(chr(ord(char) + 0x1D5A0 - ord('A')))
        elif 'a' <= char <= 'z':
            converted.append(chr(ord(char) + 0x1D5BA - ord('a')))
        elif '0' <= char <= '9':
            converted.append(chr(ord(char) + 0x1D7E2 - ord('0')))
        else:
            converted.append(char)
    return ''.join(converted)

def blockquote(text: str) -> str:
    return f"<blockquote>{text}</blockquote>"

# Text processing
def clean_extracted_text(text: str) -> str:
    # Remove numbered bullets (e.g., "1.", "2.")
    text = re.sub(r'\b\d+\.\s*', '', text)
    # Remove non-alphanumeric characters except spaces
    text = re.sub(r'[^A-Za-z0-9\s]', '', text)
    return ' '.join(text.split())

def process_caption(text: str, numbering: str) -> str:
    # Split at first "//"
    parts = text.split('//', 1)
    before_delim = clean_extracted_text(parts[0].strip())
    after_delim = parts[1].strip() if len(parts) > 1 else ''

    # Convert both numbering and text to sans-serif
    formatted_number = to_math_sans_plain(numbering.zfill(3))
    formatted_text = to_math_sans_plain(before_delim)
    blockquote_text = f"[{formatted_number}] {formatted_text}"

    # Remove everything after Batch (case-insensitive, multi-line)
    if after_delim:
        after_delim = re.sub(r'(?si)Batch.*', '', after_delim).strip()

    return blockquote(blockquote_text) + (f"\n{after_delim}" if after_delim else '')

# Handlers
@bot.on_message(filters.media)
async def handle_media(client, message: Message):
    global current_number
    if message.video:
        async with number_lock:
            num = current_number
            current_number += 1
            save_number(current_number)
        
        new_caption = process_caption(message.caption or '', str(num))
        try:
            await message.edit_caption(new_caption, parse_mode=enums.ParseMode.HTML)
        except Exception as e:
            print(f"Caption edit failed: {e}")
            await message.reply_video(message.video.file_id, caption=new_caption, parse_mode=enums.ParseMode.HTML)
    elif message.document and message.document.mime_type == "application/pdf":
        try: await message.edit_caption('')
        except: pass

# Command handlers
@bot.on_message(filters.command("start"))
async def start_cmd(_, message):
    await message.reply(
        "📚 <b>Caption Formatter Bot</b>\n\n"
        "Send videos with captions formatted as:\n"
        "<code>Title text // Additional details Batch info</code>\n\n"
        "• Text before // becomes numbered title\n"
        "• Everything after Batch is removed\n"
        "• Automatic sans-serif formatting applied",
        parse_mode=enums.ParseMode.HTML
    )

@bot.on_message(filters.command(["reset", "set"]))
async def number_control(_, message):
    global current_number
    async with number_lock:
        if message.command[0] == "reset":
            current_number = 1
        elif message.command[0] == "set" and len(message.command) > 1:
            try: current_number = max(1, int(message.command[1]))
            except: pass
        save_number(current_number)
        formatted = to_math_sans_plain(str(current_number).zfill(3))
        await message.reply(f"Current numbering: {formatted}")

bot.run()
