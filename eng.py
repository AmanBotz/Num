import os
import asyncio
import re
from threading import Thread
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from flask import Flask

# ==============================================================================
# Configuration
# ==============================================================================

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise ValueError("❌ Missing API credentials! Set API_ID, API_HASH, and BOT_TOKEN.")

# ==============================================================================
# Pyrogram Client Setup
# ==============================================================================

bot = Client(
    "indian_geo_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ==============================================================================
# Flask Health Check
# ==============================================================================

health_app = Flask(__name__)

@health_app.route('/')
def health_check():
    return "OK", 200

def run_flask():
    health_app.run(host='0.0.0.0', port=8000)

flask_thread = Thread(target=run_flask, daemon=True)
flask_thread.start()

# ==============================================================================
# Numbering System
# ==============================================================================

NUMBERING_FILE = "geo_number_state.txt"

def load_number():
    try:
        with open(NUMBERING_FILE, 'r') as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 1

def save_number(number):
    with open(NUMBERING_FILE, 'w') as f:
        f.write(str(number))

current_number = load_number()
number_lock = asyncio.Lock()

# ==============================================================================
# Text Formatting Utilities
# ==============================================================================

def to_math_sans(num: int) -> str:
    return ''.join([chr(0x1D7E2 + int(d)) for d in f"{num:03d}"])

def blockquote(text: str) -> str:
    return f"<blockquote>{text}</blockquote>"

# ==============================================================================
# Caption Processing Logic
# ==============================================================================

def process_caption(text: str, number: int) -> str:
    # Format number block
    formatted_num = f"Class [{to_math_sans(number)}]"
    numbered_block = blockquote(formatted_num)

    # Find first two number sequences
    matches = list(re.finditer(r'\d+', text))
    if len(matches) >= 2:
        # Truncate after second number
        truncated = text[matches[1].end():].strip()
    else:
        # If less than two numbers, use full text
        truncated = text.strip()

    # Clean remaining numbers and whitespace
    cleaned = re.sub(r'\d+', '', truncated).strip()
    
    return f"{numbered_block}\n{cleaned}" if cleaned else numbered_block

# ==============================================================================
# Message Handlers
# ==============================================================================

@bot.on_message(filters.command("start"))
async def start_handler(_, message: Message):
    help_text = (
        "🌍 Indian Geography Bot\n\n"
        "Automatically processes media captions:\n"
        "• Adds numbered Class header\n"
        "• Removes text before second number sequence\n"
        "• Strips all remaining numbers\n\n"
        "Just send any video/document with caption!"
    )
    await message.reply(help_text)

@bot.on_message(filters.media)
async def media_handler(_, message: Message):
    global current_number
    
    async with number_lock:
        current_num = current_number
        if message.video:  # Only increment for videos
            current_number += 1
            save_number(current_number)

    if message.video or (message.document and message.document.mime_type == "application/pdf"):
        new_caption = ""
        if message.video:
            original = message.caption or ""
            new_caption = process_caption(original, current_num)

        try:
            await message.edit_caption(
                caption=new_caption,
                parse_mode=enums.ParseMode.HTML
            )
        except Exception as e:
            print(f"Caption edit failed: {e}")
            # Fallback: send as new message
            if message.video:
                await message.reply_video(
                    message.video.file_id,
                    caption=new_caption,
                    parse_mode=enums.ParseMode.HTML
                )
            else:
                await message.reply_document(
                    message.document.file_id,
                    caption=new_caption,
                    parse_mode=enums.ParseMode.HTML
                )

@bot.on_message(filters.command("set"))
async def set_number(_, message: Message):
    try:
        new_num = int(message.command[1])
        if new_num < 1:
            raise ValueError
        
        async with number_lock:
            global current_number
            current_number = new_num
            save_number(current_number)
            
        await message.reply(f"✅ Number set to {to_math_sans(new_num)}")
    except (IndexError, ValueError):
        await message.reply("❌ Invalid format! Use: /set [3-digit number]")

@bot.on_message(filters.command("reset"))
async def reset_number(_, message: Message):
    async with number_lock:
        global current_number
        current_number = 1
        save_number(current_number)
    await message.reply(f"✅ Reset complete! Current number: {to_math_sans(1)}")

# ==============================================================================
# Main Execution
# ==============================================================================

if __name__ == "__main__":
    print("Bot starting...")
    bot.run()
