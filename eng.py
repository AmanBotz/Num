import os
import asyncio
from threading import Thread
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from flask import Flask

------------------------------------------------------------------------------

Load configuration from environment variables

------------------------------------------------------------------------------

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
raise ValueError("❌ API_ID, API_HASH, or BOT_TOKEN is missing! Set them in your environment variables.")

------------------------------------------------------------------------------

Initialize the Pyrogram bot client

------------------------------------------------------------------------------

bot = Client("indian_geography_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

------------------------------------------------------------------------------

Initialize Flask for the health check endpoint

------------------------------------------------------------------------------

health_app = Flask(name)

@health_app.route('/')
def health_check():
return "OK", 200

def run_flask():
health_app.run(port=8000, host="0.0.0.0")

flask_thread = Thread(target=run_flask)
flask_thread.daemon = True
flask_thread.start()

------------------------------------------------------------------------------

Persistent numbering state

------------------------------------------------------------------------------

NUMBERING_FILE = "numbering_state_indian_geography.txt"

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

------------------------------------------------------------------------------

Convert text to Mathematical Sans-Serif Plain (for numbering)

------------------------------------------------------------------------------

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

------------------------------------------------------------------------------

Process caption for modified requirements:

- Blockquote only "Class [NNN]" where NNN is the current counter.

- Skip all text up to the second colon, then keep content up to the marker.

- Marker for truncation: 'ᒪᑭᖇᑭᗪᐯ'.

------------------------------------------------------------------------------

def process_caption(text: str, numbering: str) -> str:
import re
# 1. Blockquote "Class [NNN]"
class_block = f"Class [{numbering}]"
quote = blockquote(class_block)

# 2. Truncate at marker if present  
marker = '— ᴹᴿ°𝐀ѕρ𝒾𝚛åηƚ𝓈࿐'  
truncated = text.split(marker, 1)[0]  

# 3. Find all colon positions  
colon_positions = [m.start() for m in re.finditer(r":", truncated)]  
if len(colon_positions) >= 2:  
    # Keep content after the second colon  
    start_idx = colon_positions[1] + 1  
    cleaned = truncated[start_idx:]  
elif colon_positions:  
    # Fallback: after first colon  
    cleaned = truncated[colon_positions[0] + 1:]  
else:  
    # No colons: keep entire truncated text  
    cleaned = truncated  

# Strip whitespace  
cleaned = cleaned.strip()  

# Combine blockquote and cleaned content  
if cleaned:  
    return f"{quote}\n{cleaned}"  
else:  
    return quote

------------------------------------------------------------------------------

Handler for media messages:

- Process caption for video files using updated logic.

- For PDF files, remove the caption entirely.

------------------------------------------------------------------------------

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

------------------------------------------------------------------------------

/start, /reset, /set commands remain unchanged

------------------------------------------------------------------------------

@bot.on_message(filters.command("start"))
async def start(client, message: Message):
instructions = (
"<b>Welcome to the Indian Geography Caption Bot!</b>\n"
"This bot now uses an updated caption logic:\n"
"  • Blockquotes only the text 'Class [NNN]'.\n"
"  • Skips everything up to the 2nd colon, then keeps text before the marker 'ᒪᑭᖇᑭᗪᐯ'.\n"
"Send a video with a caption containing at least two colons and the marker to see it in action."
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
await message.reply("❌ <b>Usage:</b> <code>/set <number></code>\nExample: <code>/set 051</code>", parse_mode=enums.ParseMode.HTML)

------------------------------------------------------------------------------

Start the bot

------------------------------------------------------------------------------

bot.run()

