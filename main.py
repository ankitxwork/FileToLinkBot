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
    "TelegramFileCDN",
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
# /start COMMAND
# -------------------------------
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply(
        "**Send me any file and I will give you:**\n\n"
        "✔ Permanent Streaming Link\n"
        "✔ Direct Download Link\n"
        "✔ File Name\n"
        "✔ File Size\n\n"
        "No CDN wait • No Cloudflare • Fully Free 🚀"
    )

# -------------------------------
# HANDLE FILE UPLOAD
# -------------------------------
@app.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_file(client, message):

    status = await message.reply("Saving securely… 📦")

    # Extract file details
    media = message.document or message.video or message.audio
    file_name = media.file_name or "file"
    file_size = media.file_size

    # Forward file to storage channel
    forwarded = await message.forward(CHANNEL_ID)

    # Fetch full file info
    file = await client.get_messages(CHANNEL_ID, forwarded.id)
    file_id = file.document or file.video or file.audio

    # Extract file_path from Telegram
    file_path = file_id.file_path

    # Build direct link (Permanent)
    direct_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

    # Streaming link = same direct link (works on all players)
    streaming_link = direct_link

    text = f"""
**📁 File Saved Successfully**

**📌 File Name:** `{file_name}`
**📦 File Size:** `{round(file_size / (1024*1024), 2)} MB`

🎬 **Streaming Link:**  
{streaming_link}

⬇️ **Direct Download Link:**  
{direct_link}

🔒 Stored safely in your private storage channel.
"""

    await status.edit(text)

# -------------------------------
# RUN FLASK + PYROGRAM
# -------------------------------
if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=8080)).start()
    app.run()