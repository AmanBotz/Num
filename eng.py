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

bot = Client("geo_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
health_app = Flask(__name__)

NUMBERING_FILE = "geo_number.txt"
current_number = 1
number_lock = asyncio.Lock()

def convert_to_math_sans(text):
    sans_map = {
        **{chr(i): chr(0x1D5A0 + i - 65) for i in range(65, 91)},
        **{chr(i): chr(0x1D5BA + i - 97) for i in range(97, 123)},
        **{chr(i): chr(0x1D7E2 + i - 48) for i in range(48, 58)}
    }
    return ''.join(sans_map.get(c, c) for c in text)

def process_content(original):
    marker = "ᒪᑭᖇᑭᗪᐯ"
    content_part = original.split(marker, 1)[0].strip()
    
    reas_pos = content_part.find("Reas")
    if reas_pos != -1:
        return content_part[reas_pos+4:].strip()
    
    numbers = list(re.finditer(r'\d+', content_part))
    if len(numbers) >= 2:
        return content_part[numbers[1].end():].strip()
    
    return content_part.strip()

@health_app.route('/')
def health_check():
    return "OK", 200

def load_number():
    try:
        with open(NUMBERING_FILE, 'r') as f:
            return int(f.read().strip())
    except:
        return 1

def save_number(number):
    with open(NUMBERING_FILE, 'w') as f:
        f.write(str(number))

current_number = load_number()

@bot.on_message(filters.command("start"))
async def start_handler(_, m):
    await m.reply("Send media with captions for processing")

@bot.on_message(filters.media)
async def media_handler(_, m):
    global current_number
    async with number_lock:
        num = current_number
        if m.video:
            current_number += 1
            save_number(current_number)

    if m.video or (m.document and m.document.mime_type == "application/pdf"):
        new_caption = ""
        if m.video:
            base = convert_to_math_sans(f"Class [{num:03}]")
            processed = process_content(m.caption or "")
            new_caption = f"<blockquote>{base}</blockquote>\n{processed}"

        try:
            await m.edit_caption(new_caption, parse_mode=enums.ParseMode.HTML)
        except:
            if m.video:
                await m.reply_video(m.video.file_id, caption=new_caption, parse_mode=enums.ParseMode.HTML)
            else:
                await m.reply_document(m.document.file_id, caption=new_caption, parse_mode=enums.ParseMode.HTML)

@bot.on_message(filters.command("set"))
async def set_number(_, m):
    try:
        new_num = int(m.command[1])
        async with number_lock:
            global current_number
            current_number = new_num
            save_number(current_number)
        await m.reply(convert_to_math_sans(f"Number set → {new_num:03}"))
    except:
        await m.reply("Invalid number format")

@bot.on_message(filters.command("reset"))
async def reset_number(_, m):
    async with number_lock:
        global current_number
        current_number = 1
        save_number(current_number)
    await m.reply(convert_to_math_sans("Reset → 001"))

def run_flask():
    health_app.run(host='0.0.0.0', port=8000)

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    bot.run()
