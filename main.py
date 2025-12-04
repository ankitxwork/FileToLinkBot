import os
import logging
from pyrogram import Client, filters
from flask import Flask

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])

logging.info("Bot Started Successfully!")

# -------------------------------
# PYROGRAM BOT CLIENT
# -------------------------------
app = Client(
    "CDNFileBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# -------------------------------
# FLASK SERVER (FOR RAILWAY)
# -------------------------------
server = Flask(__name__)

@server.route("/")
def home():
    return "Bot Running Successfully!"

# -------------------------------
# COMMAND: /start
# -------------------------------
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply(
        "**Send me any file and I will give you:**\n\n"
        "✔ Streaming link (Telegram CDN)\n"
        "✔ Download link\n"
        "✔ File name\n"
        "✔ File size"
    )

# -------------------------------
# HANDLE MEDIA
# -------------------------------
@app.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_file(client, message):

    status = await message.reply("Uploading to Telegram CDN… 🔄")

    # Save file info
    file_name = message.document.file_name if message.document else (
                 message.video.file_name if message.video else (
                 message.audio.file_name if message.audio else "file"))

    file_size = message.document.file_size if message.document else (
                message.video.file_size if message.video else (
                message.audio.file_size if message.audio else 0))

    # Upload to private storage channel
    uploaded = await message.forward(CHANNEL_ID)

    # Get Telegram CDN direct link
    cdn_link = await client.get_file_url(uploaded)

    # Build download link (same as CDN link)
    download_link = cdn_link

    text = f"""
**🎬 File Processed Successfully**

📌 **File Name:** `{file_name}`
📦 **File Size:** `{round(file_size / (1024*1024), 2)} MB`

🔗 **Streaming Link (CDN):**
{cdn_link}

⬇️ **Direct Download Link:**
{download_link}
"""

    await status.edit(text)

# -------------------------------
# RUN BOTH (Flask + Pyrogram)
# -------------------------------
if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=8080)).start()
    app.run()