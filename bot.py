import os
import asyncio
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from fastapi.responses import JSONResponse

# Initialize FastAPI app
app = FastAPI()

# Global counter for numbering
numbering_counter = {"count": 1}

# Store the bot instance in a global variable
bot_app = None  # This will hold the bot instance

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


# FastAPI endpoint for Telegram webhook
@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, bot_app.bot)  # Use the bot instance here

    # Process the update asynchronously
    await bot_app.bot.process_update(update)

    return JSONResponse({"status": "ok"}, status_code=200)


# Health check route for Koyeb
@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Main function to initialize the bot
async def main():
    global bot_app

    # Load bot token and webhook URL from environment variables
    bot_token = os.getenv("BOT_TOKEN")
    webhook_url = os.getenv("WEBHOOK_URL")

    if not bot_token or not webhook_url:
        raise EnvironmentError("BOT_TOKEN and WEBHOOK_URL must be set in the environment variables!")

    # Initialize the Telegram bot application
    bot_app = Application.builder().token(bot_token).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("reset", reset))
    bot_app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, handle_file))

    # Set webhook
    await bot_app.bot.set_webhook(url=webhook_url)


# Run FastAPI app
if __name__ == "__main__":
    import uvicorn
    import asyncio

    # Start the bot and FastAPI server asynchronously
    loop = asyncio.get_event_loop()
    loop.create_task(main())  # Initialize the bot
    uvicorn.run(app, host="0.0.0.0", port=8000)  # Run FastAPI server
