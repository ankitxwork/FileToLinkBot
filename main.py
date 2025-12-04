import os
import logging
from pyrogram import Client, filters
from flask import Flask

# -------------------------------
# BASIC LOGGING
# -------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logging.info("🚀 Bot Started Successfully!")

# -------------------------------
# ENV VARIABLES
# -------------------------------
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])   # MUST start with -100XXXXXXXXXX

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
# FLASK SERVER (FOR RENDER PING)
# -------------------------------
server = Flask(__name__)

@server.route("/")
def home():
    return "Bot Running Successfully!"


# -------------------------------
# START COMMAND
# -------------------------------
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply(
        "**👋 Welcome!**\n\n"
        "Send me any file and I will return:\n\n"
        "✔ Streamable Link (Telegram CDN)\n"
        "✔ Direct Download Link\n"
        "✔ File Name\n"
        "✔ File Size\n\n"
        "Works with ALL files — even forwarded 💯"
    )


# -------------------------------
# MAIN FILE HANDLER
# -------------------------------
@app.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_file(client, message):

    status = await message.reply("📦 Saving file securely…")

    # Detect media
    media = message.document or message.video or message.audio
    file_name = media.file_name or "unnamed_file"
    file_size = media.file_size or 0

    # Download to temp folder
    file_path = await client.download_media(message)

    # Upload to private storage channel
    uploaded = await client.send_document(
        chat_id=CHANNEL_ID,
        document=file_path,
        caption=file_name
    )

    # Delete local file
    if os.path.exists(file_path):
        os.remove(file_path)

    # Fetch CDN path
    stored_msg = await client.get_messages(CHANNEL_ID, uploaded.id)
    file_id = stored_msg.document.file_id
    file_info = await client.get_file(file_id)

    # Telegram CDN file path
    cdn_path = file_info.file_path

    # FINAL LINKS
    download_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{cdn_path}"
    streaming_link = download_link  # CDN supports streaming automatically

    # Reply message
    text = f"""
**✅ File Processed Successfully!**

📄 **File Name:** `{file_name}`
📦 **File Size:** `{round(file_size / (1024*1024), 2)} MB`

▶️ **Streaming Link (Telegram CDN):**
{streaming_link}

⬇️ **Direct Download Link:**
{download_link}

🔒 *Stored securely in your private channel.*
"""

    await status.edit(text)


# -------------------------------
# RUN BOTH BOT + FLASK
# -------------------------------
if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=8080)).start()
    app.run()