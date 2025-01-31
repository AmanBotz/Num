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
async def start(client: Client, message: Message):
    await message.reply_text("Bot is running! Send files in channels where I'm admin to get 001)-style numbering.")

@app.on_message(filters.command("reset"))
async def reset(client: Client, message: Message):
    chat_id = message.chat.id
    file_counts[chat_id] = 0
    await message.reply_text("Counter reset to 000)")

@app.on_message(filters.channel & (filters.document | filters.photo | filters.video | filters.audio))
async def handle_channel_file(client: Client, message: Message):
    chat_id = message.chat.id
    file_counts[chat_id] = file_counts.get(chat_id, 0) + 1
    new_caption = f"{file_counts[chat_id]:03d}) {message.caption or ''}"
    await message.edit_caption(new_caption)

async def run_server():
    runner = web.AppRunner(web.Application())
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Health check active on port {PORT}")

async def main():
    await asyncio.gather(
        run_server(),
        app.start(),
    )
    await asyncio.Event().wait()  # Keep running indefinitely

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped!")
