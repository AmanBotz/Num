import os
import asyncio
import re
from threading import Thread
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from flask import Flask

# ----------------------------------------------------------------------------
# Load configuration from environment variables
# ----------------------------------------------------------------------------
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise ValueError("❌ API_ID, API_HASH, or BOT_TOKEN is missing! Set them in your environment variables.")

# ----------------------------------------------------------------------------
# Initialize the Pyrogram bot client
# ----------------------------------------------------------------------------
bot = Client("file_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# ----------------------------------------------------------------------------
# Initialize Flask for the health check endpoint
# ----------------------------------------------------------------------------
health_app = Flask(__name__)

@health_app.route('/health')
def health_check():
    return "OK", 200

def run_flask():
    health_app.run(port=8000, host="0.0.0.0")

flask_thread = Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

# ----------------------------------------------------------------------------
# Persistent numbering state
# ----------------------------------------------------------------------------
NUMBERING_FILE = "numbering_state.txt"

async def load_number():
    if os.path.exists(NUMBERING_FILE):
        try:
            with open(NUMBERING_FILE, "r") as f:
                return int(f.read().strip())
        except Exception:
            return 1
    return 1

async def save_number(number):
    with open(NUMBERING_FILE, "w") as f:
        f.write(str(number))

current_number = asyncio.get_event_loop().run_until_complete(load_number())
number_lock = asyncio.Lock()

# ----------------------------------------------------------------------------
# Format numbering (e.g., state 33 becomes "033" converted to Unicode)
# ----------------------------------------------------------------------------
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

# ----------------------------------------------------------------------------
# Blockquote helper
# ----------------------------------------------------------------------------
def blockquote(text: str) -> str:
    return f"<blockquote>{text}</blockquote>"

# ----------------------------------------------------------------------------
# New caption processing: blockquote only numbering [NNN],
# then extract text from 2nd ':' (excluding 2nd ':') to include '.mkv'
# Additionally remove "VIDEO" and any [bracketed] text except [NNN]
# ----------------------------------------------------------------------------
def process_caption(text: str, numbering: str) -> str:
    quote = blockquote(f"[{numbering}]")

    try:
        colon_positions = [m.start() for m in re.finditer(r":", text)]
        start_idx = colon_positions[1] + 1 if len(colon_positions) >= 2 else 0
        lower = text.lower()
        end_pos = lower.find('.mkv')
        end_idx = end_pos + len('.mkv') if end_pos != -1 else len(text)
        snippet = text[start_idx:end_idx].strip()
    except Exception:
        snippet = text

    # Remove the word "VIDEO" and any words inside brackets [] excluding [NNN]
    snippet = re.sub(r"\bVIDEO\b", "", snippet, flags=re.IGNORECASE)
    snippet = re.sub(r"\[[^\[\]\d]{1,}\]", "", snippet).strip()

    return f"{quote}\n{snippet}"

# ----------------------------------------------------------------------------
# Handler for media messages:
# ----------------------------------------------------------------------------
@bot.on_message(filters.media)
async def handle_media(client, message: Message):
    global current_number

    if message.video:
        async with number_lock:
            num = current_number
            current_number += 1
            await save_number(current_number)
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

# ----------------------------------------------------------------------------
# Start the bot
# ----------------------------------------------------------------------------
bot.run()
