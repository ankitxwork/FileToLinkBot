import os
import logging
from pyrogram import Client, filters
from flask import Flask
import threading
import asyncio

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
# FLASK SERVER
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
        "**Send any media file, I will give you:**\n"
        "✔ Telegram CDN Streaming Link\n"
        "✔ Direct Download Link\n"
        "✔ File Name & Size\n"
        "\n⚡ Fast & Secure"
    )

# -------------------------------
# HANDLE FILES
# -------------------------------
@app.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def file_handler(client, message):

    status = await message.reply("Saving securely… 📦")

    media = message.document or message.video or message.audio
    file_name = media.file_name or "file"
    file_size = media.file_size

    # STEP 1: Store in channel instantly (cached media)
    forwarded = await client.send_cached_media(
        chat_id=CHANNEL_ID,
        file_id=media.file_id
    )

    # WAIT UNTIL TELEGRAM PROCESSES THE FILE
    await asyncio.sleep(1.5)

    # STEP 2: Read channel message AGAIN
    msg = await client.get_messages(CHANNEL_ID, forwarded.id)

    # WAIT AGAIN TO ENSURE CDN URL EXISTS
    await asyncio.sleep(1.5)

    # STEP 3: Get CDN url
    try:
        cdn_url = await client.get_file_url(msg)
    except:
        # If CDN not ready, wait a bit more
        await asyncio.sleep(1.5)
        cdn_url = await client.get_file_url(msg)

    text = f"""
**🎬 File Saved Successfully**

📌 **Name:** `{file_name}`
📦 **Size:** `{round(file_size / (1024*1024), 2)} MB`

🔗 **Streaming Link (Telegram CDN):**
{cdn_url}

⬇️ **Direct Download Link:**
{cdn_url}

📦 Stored safely in your private channel.
"""

    await status.edit(text)


# -------------------------------
# RUN SERVER + BOT
# -------------------------------
def start_flask():
    server.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    threading.Thread(target=start_flask).start()
    app.run()