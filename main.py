import os
import logging
from pyrogram import Client, filters
from flask import Flask
import subprocess
import uuid
import asyncio

logging.basicConfig(level=logging.INFO)

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])

bot = Client(
    "FileToLinkBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running ✅"

@bot.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply(
        "✅ **Send any video**\n\n"
        "I will:\n"
        "• Save it privately\n"
        "• Give Telegram streaming link\n"
        "• Give direct download link"
    )

@bot.on_message(filters.private & (filters.video | filters.document))
async def handle_video(client, message):
    status = await message.reply("📥 Downloading...")

    os.makedirs("downloads", exist_ok=True)

    try:
        file_path = await client.download_media(
            message,
            file_name=f"downloads/{uuid.uuid4()}"
        )
    except Exception as e:
        await status.edit(f"❌ Download failed:\n`{e}`")
        return

    await status.edit("☁ Uploading to secure storage...")

    try:
        uploaded = await client.send_document(
            CHANNEL_ID,
            file_path,
            caption=f"Saved via bot\nUser: {message.from_user.id}"
        )
    except Exception as e:
        await status.edit(f"❌ Upload failed:\n`{e}`")
        return

    # ✅ TELEGRAM NATIVE STREAM LINK
    stream_link = f"https://t.me/c/{str(CHANNEL_ID)[4:]}/{uploaded.id}"

    result = f"""
✅ **File Saved Successfully**

▶ **Telegram Stream Link**
{stream_link}

⬇ **Download**
Open link → Save As

🔒 Stored in private channel
"""

    await status.edit(result)

    try:
        os.remove(file_path)
    except:
        pass

if __name__ == "__main__":
    import threading
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=8080),
        daemon=True
    ).start()

    bot.run()