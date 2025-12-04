import os
import logging
from pyrogram import Client, filters
from flask import Flask

# LOGGING
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logging.info("🚀 Bot Started Successfully!")

# ENV VARS
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])

# TELEGRAM BOT
app = Client(
    "CDNFileBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# FLASK SERVER (for Render/Keep Alive)
server = Flask(__name__)

@server.route("/")
def home():
    return "Bot Running Successfully!"


# ---------------------- BOT HANDLERS -----------------------

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply(
        "**Send me any file and I will give you:**\n\n"
        "✔ Streamable Link (CDN)\n"
        "✔ Direct Download Link\n"
        "✔ File Name\n"
        "✔ File Size\n\n"
        "Works with ALL FILES — even forwarded 💯"
    )


@app.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_file(client, message):

    status = await message.reply("Saving securely… 📦")

    media = message.document or message.video or message.audio
    file_name = media.file_name or "file"
    file_size = media.file_size or 0

    # DOWNLOAD FILE
    file_path = await client.download_media(message)

    # UPLOAD TO STORAGE CHANNEL
    uploaded = await client.send_document(
        chat_id=CHANNEL_ID,
        document=file_path,
        caption=file_name
    )

    # REMOVE LOCAL FILE
    try:
        os.remove(file_path)
    except:
        pass

    # GET FILE PATH DIRECTLY
    file_info = await client.get_file(uploaded.document.file_id)
    cdn_path = file_info.file_path

    download_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{cdn_path}"
    streaming_link = download_link

    text = f"""
**🎬 File Processed Successfully!**

📌 **File Name:** `{file_name}`
📦 **File Size:** `{round(file_size / (1024*1024), 2)} MB`

🔗 **Streaming Link (Telegram CDN):**
{streaming_link}

⬇️ **Direct Download Link:**
{download_link}

_File saved securely in your private storage channel._
"""

    await status.edit(text)

@app.on_message(filters.command("test"))
async def test(client, message):
    try:
        sent = await client.send_message(CHANNEL_ID, "TEST MESSAGE ✔")
        await message.reply("Bot can SEND messages ✔")
    except Exception as e:
        await message.reply(f"❌ ERROR:\n`{e}`")


# ------------------ RUN BOTH BOT + FLASK --------------------

if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=8080)).start()
    app.run()