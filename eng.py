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
_number_lock = asyncio.Lock()

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
    Handles two styles:
    1) If caption contains '//', treat parts[0] as Title and parts[1] as Class:
       – Title: clean out bullets and non-alphanumerics
       – Class: strip everything before literal 'Class', remove after marker 'ᒪᑭᖇᑭᗪᐯ'
       – Wrap each in a blockquote with [NNN] prefix in math-sans-serif
       – Append extras as plain text if present
    2) Otherwise, remove up through first digits, then drop from 'ᒪᑭᖇᑭᗪᐯ' onward
    """
    n_str = str(num).zfill(3)
    n_fmt = to_math_sans_plain(n_str)
    parts = [p.strip() for p in raw.split("//")]

    # Case 1: Title/Class style
    if len(parts) >= 2:
        # Clean Title
        title_raw = parts[0]
        title_clean = re.sub(r"\b\d+\.\s*", "", title_raw)
        title_clean = re.sub(r"[^A-Za-z0-9\s]", "", title_clean).strip()

        # Extract Class segment
        class_raw = parts[1]
        idx = class_raw.find("Class")
        class_seg = class_raw[idx:] if idx != -1 else class_raw
        class_seg = re.sub(r"ᒪᑭᖇᑭᗪᐯ.*", "", class_seg, flags=re.DOTALL).strip()
        class_clean = re.sub(r"[^A-Za-z0-9\s]", "", class_seg).strip()

        # Convert text to math-sans
        title_fmt = to_math_sans_plain(title_clean)
        class_fmt = to_math_sans_plain(class_clean)

        # Build output
        out_lines = []
        out_lines.append(blockquote(f"[{n_fmt}] {title_fmt}"))
        out_lines.append(blockquote(f"[{n_fmt}] {class_fmt}"))

        # Append any extra parts beyond the first two
        if len(parts) > 2:
            extras = "//".join(parts[2:]).strip()
            if extras:
                out_lines.append(extras)

        return "\n".join(out_lines)

    # Case 2: other captions
    txt = raw
    # Remove everything up to and including the first numeric sequence
    txt = re.sub(r'^.*?\d+\s*', '', txt)
    # Truncate at the special marker
    txt = re.sub(r'ᒪᑭᖇᑭᗪᐯ.*', '', txt, flags=re.DOTALL)
    return txt.strip()

# ——— Handlers ———
@bot.on_message(filters.media)
async def on_media(_, message: Message):
    global current_number
    # Clear PDF captions
    if message.document and message.document.mime_type == "application/pdf":
        try:
            await message.edit_caption("")
        except:
            pass
        return

    # Only process videos, photos, and documents
    if message.video or message.photo or message.document:
        # Grab next number
        async with _number_lock:
            num = current_number
            current_number += 1
            save_number(current_number)

        # Generate new caption
        new_caption = process_caption(message.caption or "", num)
        try:
            await message.edit_caption(new_caption, parse_mode=enums.ParseMode.HTML)
        except Exception:
            # Fallback: repost media with new caption
            media_id = None
            if message.video:
                media_id = message.video.file_id
                await message.reply_video(media_id, caption=new_caption, parse_mode=enums.ParseMode.HTML)
            elif message.photo:
                media_id = message.photo.file_id
                await message.reply_photo(media_id, caption=new_caption, parse_mode=enums.ParseMode.HTML)
            elif message.document:
                media_id = message.document.file_id
                await message.reply_document(media_id, caption=new_caption, parse_mode=enums.ParseMode.HTML)

@bot.on_message(filters.command("start"))
async def start_cmd(_, msg: Message):
    await msg.reply(
        "📚 <b>Caption Formatter Bot</b>\n\n"
        "Send media with captions using `Title // Class // Optional extra`.\n"
        "• Title → numbered blockquote\n"
        "• Class → same numbering blockquote (text after literal 'Class')\n"
        "• Extra → appended as plain text\n"
        "• Other captions: strips up to first number, cuts at ᒪᑭᖇᑭᗪᐯ",
        parse_mode=enums.ParseMode.HTML
    )

@bot.on_message(filters.command(["reset", "set"]))
async def set_number(_, msg: Message):
    global current_number
    async with _number_lock:
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
