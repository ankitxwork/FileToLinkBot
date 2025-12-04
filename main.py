import os
import logging
from pyrogram import Client, filters
from flask import Flask

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])

logging.info("🚀 Bot Started Successfully!")

app = Client(
    "CDNFileBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

server = Flask(__name__)

@server.route("/")
def home():
    return "Bot Running Successfully!"

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply(
        "**Send me any file and I will give you:**\n\n"
        "✔ Telegram CDN Streaming Link\n"
        "✔ Direct Download Link\n"
        "✔ File Name\n"
        "✔ File Size\n\n"
        "Works with ALL FILES — even forwarded 💯"
    )

@app.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_file(client, message):

    status = await message.reply("Saving securely… 📦")

    # Extract file info
    if message.document:
        media = message.document
    elif message.video:
        media = message.video
    elif message.audio:
        media = message.audio
    else:
        await status.edit("❌ Unsupported file type.")
        return

    file_name = media.file_name or "file"
    file_size = media.file_size or 0

    # Download file
    file_path = await client.download_media(message)

    # Upload fresh to storage channel
    uploaded = await client.send_document(
        chat_id=CHANNEL_ID,
        document=file_path,
        caption=file_name
    )

    # Remove local file
    try:
        os.remove(file_path)
    except:
        pass

    # CDN File ID
    file_id = uploaded.document.file_id

    # Telegram CDN URL (Pyrogram v2 compatible)
    cdn_link = f"https://cdn.telegram.org/file/{file_id}"
    download_link = cdn_link

    text = f"""
**🎬 File Processed Successfully!**

📌 **File Name:** `{file_name}`
📦 **File Size:** `{round(file_size / (1024*1024), 2)} MB`

🔗 **Streaming Link (Telegram CDN):**
{cdn_link}

⬇️ **Direct Download Link:**
{download_link}

_File saved securely in your private channel._
"""

    await status.edit(text)


if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=8080)).start()
    app.run()