from flask import Flask
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from threading import Thread
import os
import time

# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# Counter for numbering
counter = 1

# Default caption format
caption_format = "{numbering}. {original_caption}"

# Initialize Pyrogram Bot
app_bot = Client("renamer_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# Flask app for health check
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

@app_bot.on_message(filters.command("reset") & filters.private)
async def reset_counter(client, message):
    global counter
    counter = 1
    await message.reply_text("Counter has been reset to 1.")

@app_bot.on_message(filters.command("start_numbering") & filters.channel)
async def start_numbering(client, message):
    global counter, caption_format

    chat_id = message.chat.id
    all_messages = []  # To store all messages

    try:
        # Fetch all messages and store them in a list
        async for msg in client.get_chat_history(chat_id, limit=200):
            all_messages.append(msg)

        # Reverse the list to process from oldest to newest
        all_messages.reverse()

        # Iterate through messages and edit captions
        for msg in all_messages:
            if msg.document or msg.video or msg.audio:  # Check if the message contains a file
                original_caption = msg.caption or "No Caption"

                # Format numbering as 3 digits
                formatted_number = f"{counter:03}"

                # Generate the new caption
                new_caption = caption_format.replace("{numbering}", f"{formatted_number}).").replace("{original_caption}", original_caption)

                # Edit the message with the new caption
                try:
                    await client.edit_message_caption(chat_id, msg.id, caption=new_caption)
                    counter += 1
                    time.sleep(1)  # Avoid hitting Telegram's rate limits
                except FloodWait as e:
                    time.sleep(e.x)

    except Exception as e:
        await message.reply_text(f"An error occurred: {str(e)}")
        return

    await message.reply_text("Numbering completed for all files in the channel.")

@app_bot.on_message(filters.command("start") & filters.private)
async def start(client, message):
    await message.reply_text(
        "Hello! Here's how you can use me:\n\n"
        "Commands:\n"
        "`/set_caption {numbering}. Your custom text` - Set custom caption format.\n"
        "`/reset` - Reset the counter to 1.\n"
        "`/start_numbering` - Add numbering to all files in the channel."
    )

if __name__ == "__main__":
    # Start Flask health check server on dynamic port
    flask_port = int(os.getenv("PORT", "8000"))
    Thread(target=lambda: flask_app.run(host="0.0.0.0", port=flask_port)).start()

    # Start Pyrogram bot
    app_bot.run()
