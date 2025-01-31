from flask import Flask
from pyrogram import Client, filters

# Bot Configuration
import os
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# Counter for numbering
counter = 1

# Default caption format
caption_format = "{numbering}. {original_caption}"

# Initialize Pyrogram Bot
app_bot = Client("renamer_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# Health check endpoint
flask_app = Flask(__name__)

@flask_app.route("/")
def health_check():
    return "Bot is running", 200

@app_bot.on_message(filters.command("set_caption") & filters.private)
async def set_caption(client, message):
    global caption_format
    if len(message.command) > 1:
        caption_format = " ".join(message.command[1:])
        await message.reply_text(f"Caption format updated to:\n`{caption_format}`")
    else:
        await message.reply_text("Usage: `/set_caption {numbering}. Your custom text`")

@app_bot.on_message(filters.document | filters.video | filters.audio & filters.private)
async def rename_caption(client, message):
    global counter, caption_format

    # Get the original caption
    original_caption = message.caption or "No Caption"

    # Generate the new caption
    new_caption = caption_format.replace("{numbering}", str(counter)).replace("{original_caption}", original_caption)

    # Send the file back with the new caption
    if message.document:
        await client.send_document(message.chat.id, message.document.file_id, caption=new_caption)
    elif message.video:
        await client.send_video(message.chat.id, message.video.file_id, caption=new_caption)
    elif message.audio:
        await client.send_audio(message.chat.id, message.audio.file_id, caption=new_caption)

    # Increment the counter
    counter += 1

@app_bot.on_message(filters.command("start") & filters.private)
async def start(client, message):
    await message.reply_text(
        "Hello! Send me a file, and I'll add numbering to its caption.\n\n"
        "To set a custom caption format, use `/set_caption {numbering}. Your custom text`.\n"
        "Use `{numbering}` for the counter and `{original_caption}` for the file's original caption."
    )

if __name__ == "__main__":
    # Run Flask health check and Pyrogram in parallel
    from threading import Thread
    Thread(target=lambda: flask_app.run(host="0.0.0.0", port=8000)).start()
    app_bot.run()
