import os
import logging
from pyrogram import Client, filters
from flask import Flask

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])   # your storage channel (must be admin)

logging.info("🚀 Bot Started Successfully!")

# -------------------------------
# PYROGRAM CLIENT
# -------------------------------
app = Client(
    "CDNFileBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# -------------------------------
# FLASK SERVER FOR RAILWAY
# -------------------------------
server = Flask(__name__)

@server.route("/")
def home():
    return "Bot Running Successfully!"

# -------------------------------
# /start
# -------------------------------
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply(
        "**Send me any file and I will give you:**\n\n"
        "✔ Telegram CDN Streaming Link\n"
        "✔ Direct Download Link\n"
        "✔ File Name\n"
        "✔ File Size\n\n"
        "Works with ALL FILES (even forwarded)."
    )

# -------------------------------
# FILE HANDLER (ALL MEDIA)
# -------------------------------
@app.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_file(client, message):

    status = await message.reply("Saving securely… 📦")

    # Extract file info
    if message.document:
        file_name = message.document.file_name
        file_size = message.document.file_size
    elif message.video:
        file_name = message.video.file_name or "video.mp4"
        file_size = message.video.file_size
    elif message.audio:
        file_name = message.audio.file_name
        file_size = message.audio.file_size
    else:
        file_name = "file"
        file_size = 0

    # -------------------------------
    # STEP 1: DOWNLOAD FILE LOCALLY
    # -------------------------------
    file_path = await message.download()

    # -------------------------------
    # STEP 2: UPLOAD FRESH TO STORAGE CHANNEL
    # -------------------------------
    uploaded = await client.send_document(
        CHANNEL_ID,
        file_path,
        caption=file_name
    )

    # Delete local file to save space
    try:
        os.remove(file_path)
    except:
        pass

    # -------------------------------
    # STEP 3: GENERATE TELEGRAM CDN LINK
    # -------------------------------
    cdn_link = await client.get_file_url(uploaded)

    # Download link is same CDN link
    download_link = cdn_link

    # -------------------------------
    # FINAL RESULT MESSAGE
    # -------------------------------
    text = f"""
**🎬 File Processed Successfully!**

📌 **File Name:** `{file_name}`
📦 **File Size:** `{round(file_size / (1024*1024), 2)} MB`

🔗 **Streaming Link (Telegram CDN):**
{cdn_link}

⬇️ **Direct Download Link:**
{download_link}

_File saved securely in private storage channel._
"""

    await status.edit(text)

# -------------------------------
# RUN SERVER + BOT
# -------------------------------
if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=8080)).start()
    app.run()