import os
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

app = Flask(__name__)

# Global counter for numbering
numbering_counter = {"count": 1}

# Telegram bot commands
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! Send me a file, and I'll add numbered captions to it.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    numbering_counter["count"] = 1
    await update.message.reply_text("Numbering reset!")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global numbering_counter
    file = update.message.document or update.message.photo[-1]
    caption = update.message.caption or "No caption provided"
    number = f"{numbering_counter['count']:03d})"
    new_caption = f"{number} {caption}"
    numbering_counter["count"] += 1

    await update.message.reply_document(file, caption=new_caption)

# Flask endpoint for Telegram webhook
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    update = Update.de_json(data, app.bot.bot)
    app.bot.process_update(update)
    return jsonify({"status": "ok"}), 200

# Health check route for Koyeb
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"}), 200

# Main function
def main():
    global app

    # Load bot token and webhook URL from environment variables
    bot_token = os.getenv("BOT_TOKEN")
    webhook_url = os.getenv("WEBHOOK_URL")

    if not bot_token or not webhook_url:
        raise EnvironmentError("BOT_TOKEN and WEBHOOK_URL must be set in the environment variables!")

    # Telegram bot application
    app.bot = Application.builder().token(bot_token).build()
    app.bot.add_handler(CommandHandler("start", start))
    app.bot.add_handler(CommandHandler("reset", reset))
    app.bot.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file))

    # Set webhook
    app.bot.bot.set_webhook(url=webhook_url)

    # Start Flask server
    app.run(host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
