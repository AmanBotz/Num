import os
from pyrogram import Client, filters
from flask import Flask

# Ensure you have these environment variables set
API_ID = int(os.getenv("API_ID"))  # Convert to integer
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Debugging: Print the values (remove this in production)
print(f"API_ID: {API_ID}, API_HASH: {API_HASH}, BOT_TOKEN: {BOT_TOKEN}")

app = Flask(__name__)

bot = Client("my_bot", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

@bot.on_message(filters.channel & filters.document)
async def update_caption(client, message):
    current_caption = message.caption or ""
    
    if current_caption:
        parts = current_caption.split(' ')
        if parts and parts[0].isdigit():
            number = int(parts[0]) + 1
        else:
            number = 1
    else:
        number = 1

    new_caption = f"{number:03d} {current_caption}"
    
    await message.edit_caption(new_caption)

@app.route('/health', methods=['GET'])
def health_check():
    return "OK", 200

if __name__ == "__main__":
    bot.start()
    app.run(host='0.0.0.0', port=8000)
