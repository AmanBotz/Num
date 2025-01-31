# bot.py
import os
from pyrogram import Client, filters
from flask import Flask, request

app = Flask(__name__)

# Replace 'API_ID' and 'API_HASH' with your actual values
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

app = Flask(__name__)

bot = Client("my_bot", bot_token=BOT_TOKEN)

@bot.on_message(filters.channel & filters.document)
async def update_caption(client, message):
    # Get the current caption
    current_caption = message.caption or ""
    
    # Extract the current numbering from the caption
    if current_caption:
        parts = current_caption.split(' ')
        if parts and parts[0].isdigit():
            number = int(parts[0]) + 1
        else:
            number = 1
    else:
        number = 1

    # Create new caption
    new_caption = f"{number:03d} {current_caption}"
    
    # Update the message caption
    await message.edit_caption(new_caption)

@app.route('/health', methods=['GET'])
def health_check():
    return "OK", 200

if __name__ == "__main__":
    bot.start()
    app.run(host='0.0.0.0', port=8000)
