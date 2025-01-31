import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from aiohttp import web

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8000))

file_counts = {}

async def health_check(request):
    return web.Response(text="OK")

app = Client(
    "caption_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

@app.on_message(filters.command("start"))
async def start(_, message: Message):
    await message.reply("✅ Bot is alive! Add me to a channel as admin with edit permissions.")

@app.on_message(filters.command("reset"))
async def reset(_, message: Message):
    chat_id = message.chat.id
    file_counts[chat_id] = 0
    await message.reply("🔄 Counter reset to 000)")

@app.on_message(filters.channel & (filters.document | filters.photo | filters.video | filters.audio))
async def handle_file(_, message: Message):
    chat_id = message.chat.id
    file_counts[chat_id] = file_counts.get(chat_id, 0) + 1
    new_caption = f"{file_counts[chat_id]:03d}) {message.caption or ''}"
    await message.edit_caption(new_caption)

async def web_server():
    app_web = web.Application()
    app_web.router.add_get("/", health_check)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

async def main():
    await web_server()
    await app.start()
    print("Bot started!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped!")
