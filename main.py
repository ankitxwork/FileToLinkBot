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
    bot_token=BOT_TOKEN
)

server = Flask(__name__)

@server.route("/")
def home():
    return "Bot Running Successfully!"


@app.on_message(filters.command("start"))
async def start(_, message):
    await message.reply(
        "**Send any file and I'll give you CDN Streaming Link + Direct Download Link.**\n\n"
        "💠 Works even for 2GB files.\n"
        "💠 No Cloudflare, No Storage Needed."
    )


@app.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_file(client, message):

    status = await message.reply("Processing… 🔄")

    media = message.document or message.video or message.audio
    file_name = media.file_name or "file"
    file_size = media.file_size or 0

    # ❌ DO NOT DOWNLOAD THE FILE
    # We upload directly using file_id → FASTEST & SAFE

    sent = await client.send_document(
        chat_id=CHANNEL_ID,
        document=media.file_id,
        caption=file_name
    )

    # Get uploaded file info
    file = await client.get_messages(CHANNEL_ID, sent.id)
    file_info = await client.get_file(file.document.file_id)

    cdn_path = file_info.file_path

    download_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{cdn_path}"
    streaming_link = download_link  # Works in any video player

    text = f"""
**✔ File Ready!**

📌 **Name:** `{file_name}`
📦 **Size:** `{round(file_size / (1024*1024), 2)} MB`

🔗 **Streaming Link (CDN)**  
{streaming_link}

⬇️ **Direct Download:**  
{download_link}

_No storage used. File stays permanently on Telegram CDN._
"""

    await status.edit(text)


# ---- TEST COMMANDS -----

@app.on_message(filters.command("test"))
async def test(client, message):
    try:
        await client.send_message(CHANNEL_ID, "TEST MESSAGE ✔")
        await message.reply("Bot can SEND messages ✔")
    except Exception as e:
        await message.reply(str(e))


@app.on_message(filters.command("id"))
async def get_id(_, message):
    await message.reply(message.chat.id)


if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=8080)).start()
    app.run()