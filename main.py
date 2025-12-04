import os
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from math import ceil

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])

app = Client(
    "FileToLinkBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Convert bytes to human readable format
def human_readable_size(size):
    power = 1024
    n = 0
    units = ["B", "KB", "MB", "GB", "TB"]
    while size > power and n < 4:
        size /= power
        n += 1
    return f"{round(size, 2)} {units[n]}"

@app.on_message(filters.private & (filters.video | filters.document))
async def media_handler(client: Client, message: Message):
    processing = await message.reply("🔄 Uploading… Please wait.")

    # Forward to your private channel
    forwarded_msg = await message.forward(CHANNEL_ID)

    # Extract file info
    media = forwarded_msg.video or forwarded_msg.document
    file_name = media.file_name
    file_size = human_readable_size(media.file_size)

    # Generate Telegram CDN link
    file_path = await client.get_file(media.file_id)
    cdn_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path.file_path}"

    # Reply with full info
    await processing.edit(
        f"🎬 **File Processed Successfully!**\n\n"
        f"📝 **File Name:** `{file_name}`\n"
        f"📦 **File Size:** `{file_size}`\n\n"
        f"▶ **Streaming Link:**\n{cdn_url}\n\n"
        f"⬇ **Direct Download:**\n{cdn_url}\n\n"
        "✔ File stored safely in private channel."
    )


@app.on_message(filters.command(["start", "help"]))
async def start(_, message):
    await message.reply(
        "👋 **Welcome!**\n\n"
        "Send any **video/file** and I will give you:\n"
        "• File Name\n"
        "• File Size\n"
        "• Direct Streaming Link (Telegram CDN)\n"
        "• Direct Download Link\n\n"
        "100% Free • Unlimited Storage • No Cloudflare needed."
    )

import threading
from flask import Flask

flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

threading.Thread(target=run_flask).start()

app.run()