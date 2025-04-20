import os
import re
import asyncio
from threading import Thread

from pyrogram import Client, filters, enums
from pyrogram.types import Message
from flask import Flask

# ——— Config ———
API_ID    = int(os.getenv("API_ID", "0"))
API_HASH  = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

bot = Client("file_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Health check
app = Flask(__name__)
@app.route("/")
def health(): 
    return "OK", 200

Thread(target=lambda: app.run(host="0.0.0.0", port=8000), daemon=True).start()

# ——— Persistent numbering ———
STATE_FILE = "numbering_state.txt"
_lock = asyncio.Lock()

def load_number() -> int:
    if os.path.exists(STATE_FILE):
        try:
            return int(open(STATE_FILE).read().strip())
        except:
            pass
    return 1

def save_number(n: int):
    with open(STATE_FILE, "w") as f:
        f.write(str(n))

current_number = load_number()

# ——— Font conversion ———
def to_math_sans_plain(text: str) -> str:
    out = []
    for ch in text:
        if 'A' <= ch <= 'Z':
            out.append(chr(ord(ch) + 0x1D5A0 - ord('A')))
        elif 'a' <= ch <= 'z':
            out.append(chr(ord(ch) + 0x1D5BA - ord('a')))
        elif '0' <= ch <= '9':
            out.append(chr(ord(ch) + 0x1D7E2 - ord('0')))
        else:
            out.append(ch)
    return "".join(out)

def blockquote(txt: str) -> str:
    return f"<blockquote>{txt}</blockquote>"

# ——— Caption processing ———
def process_caption(raw: str, num: int) -> str:
    """
    1) If contains "//", expects Title//Class[//Extra]:
       – clean Title & Class to alphanum + spaces
       – produce two blockquotes: [NNN] Title  and  [NNN] Class
       – append any Extra text (untouched) on new line
    2) Else (“other”):
       – strip everything up through first digits (incl.)
       – strip from 'ᒪᑭᖇᑭᗪᐯ' onward (incl.)
    """
    n_str = str(num).zfill(3)
    n_fmt = to_math_sans_plain(n_str)
    
    parts = [p.strip() for p in raw.split("//")]
    if len(parts) >= 2:
        # clean function: remove bullets & non‑alnum except spaces
        def clean(txt):
            t = re.sub(r'\b\d+\.\s*', "", txt)
            t = re.sub(r'[^A-Za-z0-9\s]', "", t)
            return " ".join(t.split())
        
        title = clean(parts[0])
        cls   = clean(parts[1])
        extra = "//".join(parts[2:]).strip() if len(parts) > 2 else ""
        
        out = []
        out.append(blockquote(f"[{n_fmt}] {to_math_sans_plain(title)}"))
        out.append(blockquote(f"[{n_fmt}] {to_math_sans_plain(cls)}"))
        if extra:
            out.append(extra)
        return "\n".join(out)
    else:
        # “other” caption
        txt = raw
        # remove up through first digits
        txt = re.sub(r'^.*?\d+\s*', "", txt)
        # cut off at the marker ᒪᑭᖇᑭᗪᐯ
        txt = re.sub(r'ᒪᑭᖇᑭᗪᐯ.*', "", txt)
        return txt.strip()

# ——— Handlers ———
@bot.on_message(filters.media)
async def on_media(_, message: Message):
    global current_number
    # PDF: clear caption
    if message.document and message.document.mime_type == "application/pdf":
        try:
            await message.edit_caption("")
        except:
            pass
        return

    # Only modify videos & photos/docs
    if message.video or message.photo or message.document:
        async with _lock:
            num = current_number
            current_number += 1
            save_number(current_number)

        new_cap = process_caption(message.caption or "", num)
        try:
            await message.edit_caption(new_cap, parse_mode=enums.ParseMode.HTML)
        except Exception:
            # fallback: repost same media with new caption
            if message.video:
                await message.reply_video(
                    message.video.file_id,
                    caption=new_cap,
                    parse_mode=enums.ParseMode.HTML
                )
            elif message.photo:
                await message.reply_photo(
                    message.photo.file_id,
                    caption=new_cap,
                    parse_mode=enums.ParseMode.HTML
                )
            elif message.document:
                await message.reply_document(
                    message.document.file_id,
                    caption=new_cap,
                    parse_mode=enums.ParseMode.HTML
                )

@bot.on_message(filters.command("start"))
async def start(_, msg: Message):
    await msg.reply(
        "📚 <b>Caption Formatter Bot</b>\n\n"
        "Send media with captions formatted as:\n"
        "<code>Title // Class // Optional extra</code>\n\n"
        "• Title → numbered blockquote\n"
        "• Class → same numbering blockquote\n"
        "• Extra → appended as-is\n"
        "• Other captions: strips up to first #, cuts at ᒪᑭᖇᑭᗪᐯ",
        parse_mode=enums.ParseMode.HTML
    )

@bot.on_message(filters.command(["reset", "set"]))
async def set_number(_, msg: Message):
    global current_number
    async with _lock:
        cmd, *rest = msg.command
        if cmd == "reset":
            current_number = 1
        elif cmd == "set" and rest:
            try:
                current_number = max(1, int(rest[0]))
            except:
                pass
        save_number(current_number)
        z = to_math_sans_plain(str(current_number).zfill(3))
        await msg.reply(f"🔢 Current number set to: {z}", parse_mode=enums.ParseMode.HTML)

if __name__ == "__main__":
    bot.run()
