import os
import logging
from pyrogram import Client, filters
from flask import Flask
import threading

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])

logging.info("🚀 Bot Started Successfully!")

# -------------------------------
# PYROGRAM BOT
# -------------------------------
app = Client(
    "CDNFileBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# -------------------------------
# FLASK KEEP-ALIVE SERVER
# -------------------------------
server = Flask(__name__)

@server.route("/")
def home():
    return "Bot is running!"

# -------------------------------
# START COMMAND
# -------------------------------
@app.on_message(filters.command("start"))
async def start_cmd(client, message):
    await message.reply(
        "**Send any video/document/audio and I will give you:**\n"
        "✔ Telegram CDN Streaming Link\n"
        "✔ Direct Download Link\n"
        "✔ File Name & Size\n"
        "\n⚡ Powered by Pyrogram"
    )

# -------------------------------
# MEDIA HANDLER
# -------------------------------
@app.on_message(filters.private & (filters.video | filters.document | filters.audio))
async def handle_media(client, message):

    status = await message.reply("Saving securely… 📦")

    # Extract file info
    media = message.document or message.video or message.audio

    file_name = media.file_name if media.file_name else "file"
    file_size = media.file_size

    # STEP 1: Forward file to storage channel
    forwarded = await client.send_cached_media(
        chat_id=CHANNEL_ID,
        file_id=media.file_id     # 100× faster than message.forward()
    )

    # STEP 2: Fetch message again to get CDN URL
    channel_msg = await client.get_messages(CHANNEL_ID, forwarded.id)

    # STEP 3: Get CDN URL
    cdn_url = await client.get_file_url(channel_msg)

    text = f"""
**🎬 File Processed Successfully**

📌 **File:** `{file_name}`
📦 **Size:** `{round(file_size / (1024*1024), 2)} MB`

🔗 **Streaming Link (Telegram CDN):**
{cdn_url}

⬇️ **Direct Download Link:**
{cdn_url}

🗂 Saved securely in storage 📦
"""

    await status.edit(text)


# -------------------------------
# RUN BOTH FLASK + BOT
# -------------------------------
def start_flask():
    server.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    threading.Thread(target=start_flask).start()
    app.run()