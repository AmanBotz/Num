import os
from pyrogram import Client, filters
from pyrogram.types import Message
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8000))

file_counts = {}

async def health_check(request):
    return web.Response(text="OK")

app = Client("caption_bot", bot_token=BOT_TOKEN)

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

    if chat_id not in file_counts:
        file_counts[chat_id] = 0

    file_counts[chat_id] += 1
    
    # Format number with leading zeros and closing parenthesis
    number_str = f"{file_counts[chat_id]:03d})"
    new_caption = f"{number_str} {message.caption or ''}"
    
    try:
        await message.edit_caption(new_caption)
    except Exception as e:
        print(f"Error editing caption: {e}")

async def main():
    runner = web.AppRunner(web.Application())
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    print(f"Health check active on port {PORT}")
    await app.start()
    await app.idle()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
