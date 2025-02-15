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
# Convert text to Mathematical Sans‑Serif Plain (non bold, non italic)
# ------------------------------------------------------------------------------
def to_math_sans_plain(text: str) -> str:
    result = []
    for ch in text:
        if 'A' <= ch <= 'Z':
            # Mathematical Sans‑Serif Uppercase: U+1D5A0 to U+1D5B9
            result.append(chr(ord(ch) - ord('A') + 0x1D5A0))
        elif 'a' <= ch <= 'z':
            # Mathematical Sans‑Serif Lowercase: U+1D5BA to U+1D5D3
            result.append(chr(ord(ch) - ord('a') + 0x1D5BA))
        elif '0' <= ch <= '9':
            # Mathematical Sans‑Serif Digits: U+1D7E2 to U+1D7EB
            result.append(chr(ord(ch) - ord('0') + 0x1D7E2))
        else:
            result.append(ch)
    return ''.join(result)

# ------------------------------------------------------------------------------
# Format the numbering (e.g., state 1 becomes "001" converted to Unicode)
# ------------------------------------------------------------------------------
def format_number(num: int) -> str:
    num_str = str(num).zfill(3)
    return to_math_sans_plain(num_str)

# ------------------------------------------------------------------------------
# Wrap text in an HTML blockquote
# ------------------------------------------------------------------------------
def blockquote(text: str) -> str:
    return f"<blockquote>{text}</blockquote>"

# ------------------------------------------------------------------------------
# Remove unwanted sentences and markers from the caption.
# Added "•" to unwanted phrases.
# ------------------------------------------------------------------------------
def remove_unwanted_sentences(text: str) -> str:
    unwanted_phrases = [
        "Batch » Maths Spl-30 (Pre+Mains)",
        "»Download By➵➵ᴹᴿ°ຮ𝖆𝖈𝖍𝖎𝖓࿐²⁴⁷",
        "»Download By➵ᴹᴿ°ຮ𝖆𝖈𝖍𝖎𝖓࿐²⁴⁷",
        "•"  # remove bullet characters
    ]
    for phrase in unwanted_phrases:
        text = text.replace(phrase, "")
    # Remove any leading numbering pattern like "033)." at the start of a line
    text = re.sub(r'^\s*\d+\)\.?\s*', '', text, flags=re.MULTILINE)
    # Remove numeric markers like "001)." anywhere in the text
    text = re.sub(r'\b(?:0\d{2}|[1-2]\d{2}|300)\)\.', '', text)
    return text.strip()

# ------------------------------------------------------------------------------
# Clean prefix: remove any leading numbering from the prefix text.
# ------------------------------------------------------------------------------
def clean_prefix(prefix: str) -> str:
    return re.sub(r'^\s*\d+\)\.?\s*', '', prefix).strip()

# ------------------------------------------------------------------------------
# Process caption:
#   - Split into prefix (before "Class Date") and suffix (from "Class Date" onward).
#   - If "Class Date" found:
#         * Force the suffix to one line.
#         * Convert suffix to Mathematical Sans‑Serif Plain.
#         * Prepend numbering (in square brackets) to suffix.
#         * Wrap suffix in blockquote.
#         * Append the cleaned prefix below.
#   - If "Class Date" not found:
#         * Blockquote only the numbering, then append the full cleaned caption below.
# ------------------------------------------------------------------------------
def process_caption(text: str, numbering: str) -> str:
    cleaned_text = remove_unwanted_sentences(text)
    lower_text = cleaned_text.lower()
    idx = lower_text.find("class date")
    if idx != -1:
        prefix = cleaned_text[:idx].strip()
        suffix = cleaned_text[idx:].strip()
        # Force suffix to one line:
        suffix_one_line = ' '.join(suffix.split())
        # Convert suffix to Mathematical Sans‑Serif Plain
        converted_suffix = to_math_sans_plain(suffix_one_line)
        # Prepend numbering (in square brackets) to suffix
        block_text = f"[{numbering}] {converted_suffix}"
        blockquoted = blockquote(block_text)
        # Clean the prefix and return blockquote on first line, then prefix on next
        clean_pref = clean_prefix(prefix)
        return f"{blockquoted}\n{clean_pref}"
    else:
        # If "Class Date" not found, blockquote only the numbering
        blockquoted = blockquote(f"[{numbering}]")
        return f"{blockquoted}\n{to_math_sans_plain(cleaned_text)}"

# ------------------------------------------------------------------------------
# Handler for media messages:
#   - Process caption for video files only.
#   - If a PDF is sent, remove the caption entirely.
#   - For other file types, leave the caption unchanged.
# ------------------------------------------------------------------------------
@bot.on_message(filters.media)
async def handle_media(client, message: Message):
    global current_number

    # Check if it's a video file
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
            # Fallback: resend the media with the new caption.
            await message.reply_video(message.video.file_id, caption=new_caption, parse_mode=enums.ParseMode.HTML)
    elif message.document and message.document.mime_type == "application/pdf":
        # For PDF files, remove the caption entirely.
        try:
            await message.edit_caption("", parse_mode=enums.ParseMode.HTML)
        except Exception as e:
            print(f"Error editing caption for PDF: {e}")
            await message.reply_document(message.document.file_id, caption="", parse_mode=enums.ParseMode.HTML)
    else:
        # For other file types, do not modify the caption.
        pass

# ------------------------------------------------------------------------------
# /start command: provides instructions to the user
# ------------------------------------------------------------------------------
@bot.on_message(filters.command("start"))
async def start(client, message: Message):
    instructions = (
        "<b>Welcome!</b>\n"
        "This bot automatically numbers file captions and processes the text starting from the keyword \"Class Date\" for video files. "
        "If a caption contains \"Class Date\", the text from that point is forced onto one line, converted into non-bold, non-italic Mathematical Sans‑Serif Plain style, and prepended with a numbering prefix (in square brackets) inside a blockquote. "
        "Any text before \"Class Date\" is appended on a new line. "
        "If \"Class Date\" is not found, only the numbering is blockquoted and the entire caption is converted. "
        "For PDF files, the caption is entirely removed.\n\n"
        "<b>Commands:</b>\n"
        "• <code>/reset</code> - Reset numbering to " + format_number(1) + "\n"
        "• <code>/set &lt;number&gt;</code> - Set numbering starting from a custom number (e.g. <code>/set 051</code>)\n"
        "• Send a video file with a caption containing \"Class Date\" or a PDF file to see the processing in action."
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
# Start the bot
# ------------------------------------------------------------------------------
bot.run()
