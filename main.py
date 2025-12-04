import os
import logging
from pyrogram import Client, filters
from flask import Flask

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])

app = Client(
    "CDNFileBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=16,
    in_memory=True
)

server = Flask(__name__)

@server.route("/")
def home():
    return "Bot Running Successfully!"


@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply(
        "**Send me any file and I will give you:**\n\n"
        "✔ Telegram Streaming Link (HLS .m3u8)\n"
        "✔ Direct CDN Link\n"
        "✔ File Name & Size\n"
        "✔ 100% Private & Secure\n"
    )

@app.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_file(client, message):

    status = await message.reply("Processing… 🔄")

    media = message.document or message.video or message.audio
    file_name = media.file_name or "file"
    file_size = round((media.file_size or 0) / (1024*1024), 2)

    # ---- Download File ----
    file_path = await client.download_media(message)

    # ---- Upload To Private Storage Channel ----
    uploaded = await client.send_document(
        chat_id=CHANNEL_ID,
        document=file_path,
        caption=file_name
    )

    # ---- Remove Local File ----
    try:
        os.remove(file_path)
    except:
        pass

    # ---- Get Telegram CDN Path ----
    file_obj = uploaded.document
    file_id = file_obj.file_id
    file_info = await client.get_file(file_id)
    cdn_path = file_info.file_path

    # ---- Final Links ----
    cdn_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{cdn_path}"
    hls_link = cdn_link.replace(".mp4", "/index.m3u8")

    text = f"""
**✔ File Processed Successfully!**

📄 **Name:** `{file_name}`
📦 **Size:** `{file_size} MB`

🎥 **Streaming (HLS .m3u8):**
{hls_link}

⬇️ **Direct Download (CDN):**
{cdn_link}

🔐 *Stored privately inside your storage channel.*
"""

    await status.edit(text)


if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=8080)).start()
    app.run()