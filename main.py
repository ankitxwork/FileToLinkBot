import os
import logging
from pyrogram import Client, filters
from flask import Flask
import threading

# -------------------- LOGGING --------------------
logging.basicConfig(
    format="%(asctime)s - %(message)s",
    level=logging.INFO
)

# -------------------- ENV VARIABLES --------------------
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))  # storage channel

# -------------------- FLASK KEEP ALIVE --------------------
app_web = Flask(__name__)

@app_web.route("/")
def index():
    return "Bot is running!"

def run_flask():
    app_web.run(host="0.0.0.0", port=8080)

def keep_alive():
    thread = threading.Thread(target=run_flask)
    thread.start()

# -------------------- TELEGRAM BOT --------------------
app = Client(
    "bot_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# Convert bytes → MB
def size_in_mb(size):
    return round(size / (1024 * 1024), 2)


# -------------------- HANDLER --------------------
@app.on_message(filters.private & (filters.video | filters.document | filters.audio))
async def media_handler(bot, message):
    try:
        logging.info("Media received... forwarding to storage channel")

        # Forward to your storage channel
        forwarded = await message.forward(CHANNEL_ID)

        file = forwarded.video or forwarded.document or forwarded.audio

        file_id = file.file_id
        file_name = file.file_name or "Unknown"
        file_size = size_in_mb(file.file_size)

        # Direct Telegram CDN link
        stream_link = await bot.get_file_url(file_id)

        # Direct download link
        file_info = await bot.get_file(file_id)
        download_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"

        # Send formatted message
        reply_text = f"""
🎬 **File Name:** {file_name}
📦 **Size:** {file_size} MB

▶ **Streaming Link:**  
{stream_link}

⬇ **Download Link:**  
{download_link}
        """

        await message.reply_text(reply_text, disable_web_page_preview=True)

    except Exception as e:
        logging.error(f"Error: {e}")
        await message.reply_text("❌ Error occurred while processing this file.")


# -------------------- START --------------------
if __name__ == "__main__":
    keep_alive()
    logging.info("Bot Started Successfully!")
    app.run()