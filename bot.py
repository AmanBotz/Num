import os
import re
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from aiohttp import web

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

# Initialize counter globally
counter = 1

app = Client("caption_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
pattern = re.compile(r'^\d{3}\)')
web_app = web.Application()

async def health_check(request):
    return web.Response(text="OK", status=200)

web_app.router.add_get("/", health_check)

@app.on_message(filters.channel & (filters.document | filters.video | filters.audio | filters.photo))
async def process_caption(client: Client, message: Message):
    global counter  # Declare global counter before using it
    if not message.caption or not pattern.search(message.caption):
        new_caption = f"{counter:03d}) {message.caption or ''}".strip()
        try:
            await client.edit_message_caption(
                chat_id=message.chat.id,
                message_id=message.id,
                caption=new_caption
            )
            counter += 1  # Increment the counter
        except Exception as e:
            print(f"Error updating caption: {e}")

async def run_server():
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8000)
    await site.start()
    print("Health check server running on port 8000")

async def main():
    await app.start()
    await run_server()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
