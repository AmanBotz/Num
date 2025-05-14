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
# New caption processing:
# - Blockquote only numbering [NNN]
# - Extract text after the 2nd ':' up to '.mkv'
# - Cleanup: remove 'VIDEO', all other bracketed text, the '.mkv' extension,
#   leading colons, stray dashes, and collapse whitespace.
# ----------------------------------------------------------------------------
def process_caption(text: str, numbering: str) -> str:
    # 1. Blockquote numbering
    quote = blockquote(f"[{numbering}]")

    # 2. Extract snippet between after 2nd colon to .mkv
    snippet = text
    try:
        cols = [m.start() for m in re.finditer(r":", text)]
        start = cols[1] + 1 if len(cols) >= 2 else 0
        end_mkv = text.lower().find('.mkv')
        end = end_mkv if end_mkv != -1 else len(text)
        snippet = text[start:end]
    except Exception:
        snippet = text

    # 3. Remove 'VIDEO' keyword (case-insensitive)
    snippet = re.sub(r"\bVIDEO\b", "", snippet, flags=re.IGNORECASE)

    # 4. Remove bracketed content [ ... ]
    snippet = re.sub(r"\[[^\]]*\]", "", snippet)

    # 5. Remove leading colons and whitespace
    snippet = re.sub(r"^[:]+", "", snippet).strip()

    # 6. Remove stray dashes (e.g. leftover separators)
    snippet = re.sub(r"\s*-+\s*", " ", snippet)

    # 7. Collapse multiple spaces
    snippet = ' '.join(snippet.split())

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
