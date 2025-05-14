import os
import asyncio
import re
from threading import Thread
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from flask import Flask

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise ValueError("API_ID, API_HASH, and BOT_TOKEN must be set")

bot = Client("file_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)
health_app = Flask(__name__)

@health_app.route('/health')
def health_check():
    return "OK", 200

Thread(target=lambda: health_app.run(port=8000, host="0.0.0.0"), daemon=True).start()

NUMBERING_FILE = "numbering_state.txt"

async def load_number():
    if os.path.exists(NUMBERING_FILE):
        try:
            with open(NUMBERING_FILE) as f:
                return int(f.read().strip())
        except:
            return 1
    return 1

async def save_number(number):
    with open(NUMBERING_FILE, 'w') as f:
        f.write(str(number))

current_number = asyncio.get_event_loop().run_until_complete(load_number())
number_lock = asyncio.Lock()

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
    return to_math_sans_plain(str(num).zfill(3))

def blockquote(text: str) -> str:
    return f"<blockquote>{text}</blockquote>"

def process_caption(text: str, numbering: str) -> str:
    quote = blockquote(f"[{numbering}]")
    snippet = text
    try:
        cols = [m.start() for m in re.finditer(r":", text)]
        start = cols[1] + 1 if len(cols) >= 2 else 0
        end_mkv = text.lower().find('.mkv')
        end = end_mkv if end_mkv != -1 else len(text)
        snippet = text[start:end]
    except:
        pass
    snippet = re.sub(r"\bVIDEO\b", "", snippet, flags=re.IGNORECASE)
    snippet = re.sub(r"\[[^\]]*\]", "", snippet)
    snippet = re.sub(r"^[:]+", "", snippet).strip()
    snippet = re.sub(r"\s*-+\s*", " ", snippet)
    snippet = ' '.join(snippet.split())
    return f"{quote}\n{snippet}"

@bot.on_message(filters.command("start"))
async def start(client, message: Message):
    await message.reply(
        "Welcome! Use /reset to reset numbering or /set <number> to set a custom start.",
        parse_mode=enums.ParseMode.HTML
    )

@bot.on_message(filters.command("reset"))
async def reset(client, message: Message):
    global current_number
    async with number_lock:
        current_number = 1
        await save_number(current_number)
    await message.reply(format_number(current_number), parse_mode=enums.ParseMode.HTML)

@bot.on_message(filters.command("set"))
async def set_number(client, message: Message):
    global current_number
    parts = message.text.split(maxsplit=1)
    if len(parts) == 2 and parts[1].isdigit():
        num = int(parts[1])
        async with number_lock:
            current_number = num
            await save_number(num)
        await message.reply(format_number(current_number), parse_mode=enums.ParseMode.HTML)
    else:
        await message.reply("Usage: /set <number>", parse_mode=enums.ParseMode.HTML)

@bot.on_message(filters.media)
async def handle_media(client, message: Message):
    global current_number
    if message.video:
        async with number_lock:
            num = current_number
            current_number += 1
            await save_number(current_number)
        orig = message.caption or ""
        new_cap = process_caption(orig, format_number(num))
        try:
            await message.edit_caption(new_cap, parse_mode=enums.ParseMode.HTML)
        except:
            await message.reply_video(message.video.file_id, caption=new_cap, parse_mode=enums.ParseMode.HTML)
    elif message.document and message.document.mime_type == "application/pdf":
        await message.edit_caption("", parse_mode=enums.ParseMode.HTML)

bot.run()
