import os
import re
import asyncio
from threading import Thread
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from flask import Flask

# ---------------------------- Configuration ---------------------------- #
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise ValueError("Missing API credentials!")

# ---------------------------- Bot Initialization ---------------------------- #
bot = Client("caption_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# ---------------------------- Health Check Server ---------------------------- #
health_app = Flask(__name__)

@health_app.route('/health')
def health_check():
    return "OK", 200

flask_thread = Thread(target=lambda: health_app.run(port=8000, host="0.0.0.0"), daemon=True)
flask_thread.start()

# ---------------------------- Numbering System ---------------------------- #
NUMBER_FILE = "number_state.txt"
current_number = 1
number_lock = asyncio.Lock()

def load_number():
    global current_number
    try:
        with open(NUMBER_FILE, "r") as f:
            current_number = int(f.read().strip()) or 1
    except:
        current_number = 1

def save_number():
    with open(NUMBER_FILE, "w") as f:
        f.write(str(current_number))

load_number()

# ---------------------------- Text Formatting ---------------------------- #
def format_number(num: int) -> str:
    """Convert number to Mathematical Sans-Serif"""
    return ''.join([chr(0x1D7E2 + int(d)) for d in f"{num:03d}"])

def blockquote(text: str) -> str:
    return f"<blockquote>{text}</blockquote>"

# ---------------------------- Caption Processing ---------------------------- #
def process_caption(caption: str, numbering: str) -> str:
    # Process Class section
    class_pattern = re.compile(r"(Class:?[\s\S]*?)(?=Title:|$)", re.IGNORECASE)
    class_match = class_pattern.search(caption)
    if class_match:
        class_text = class_match.group(1).strip()
        updated_class = f"{class_text} [{numbering}]"
        caption = caption.replace(class_text, updated_class, 1)

    # Process Title section
    title_pattern = re.compile(r"Title:?([\s\S]*?)(?=➸|$)", re.IGNORECASE)
    title_match = title_pattern.search(caption)
    if title_match:
        title_content = title_match.group(1).strip()
        
        # Remove everything before first number including the number
        title_content = re.sub(r"^.*?(\d+)|(\d+).*?$", "", title_content).strip()
        
        # Remove everything after ᒪᑭᖇᑭᗪᐯ including the marker
        title_content = re.split(r"ᒪᑭᖇᑭᗪᐯ", title_content, 1)[0].strip()
        
        caption = caption.replace(title_match.group(0), f"Title: {title_content}")

    # Add blockquotes to numbering instances
    caption = re.sub(
        r"(\[.*?\])", 
        lambda m: blockquote(m.group(1)), 
        caption
    )

    return caption.strip()

# ---------------------------- Bot Handlers ---------------------------- #
@bot.on_message(filters.media & filters.outgoing)
async def handle_media(client, message: Message):
    global current_number
    
    async with number_lock:
        num = current_number
        current_number += 1
        save_number()

    formatted_number = format_number(num)
    
    if message.caption:
        new_caption = process_caption(message.caption, formatted_number)
        try:
            await message.edit_caption(new_caption, parse_mode=enums.ParseMode.HTML)
        except Exception as e:
            print(f"Caption edit failed: {e}")

@bot.on_message(filters.command(["start", "help"]))
async def send_help(client, message: Message):
    help_text = (
        "<b>Caption Formatting Bot</b>\n\n"
        "Automatically processes captions with:\n"
        "1. Auto-incrementing 3-digit Mathematical numbers\n"
        "2. Class section numbering\n"
        "3. Title section cleaning\n"
        "4. Automatic blockquote formatting\n\n"
        "Just send media with captions containing 'Class' and 'Title' sections!"
    )
    await message.reply_text(help_text, parse_mode=enums.ParseMode.HTML)

@bot.on_message(filters.command("setnum"))
async def set_number(client, message: Message):
    try:
        new_num = int(message.command[1])
        async with number_lock:
            global current_number
            current_number = max(1, new_num)
            save_number()
        await message.reply(f"Number set to {format_number(current_number)}")
    except:
        await message.reply("Usage: /setnum [new_number]")

# ---------------------------- Main Execution ---------------------------- #
bot.run()
