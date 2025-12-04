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
    "DirectLinkBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# -------------------------------
# FLASK SERVER (FOR RAILWAY/RENDER)
# -------------------------------
server = Flask(__name__)

@server.route("/")
def home():
    return "Bot is running successfully!"

# -------------------------------
# COMMAND: /start
# -------------------------------
@app.on_message(filters.command("start"))
async def start(_, message):
    await message.reply(
        "**Send me any file and I will give you:**\n\n"
        "✔ Permanent Streaming Link\n"
        "✔ Direct Download Link\n"
        "✔ File Name\n"
        "✔ File Size\n\n"
        "No CDN upload • No R2 • 100% Free"
    )

# -------------------------------
# HANDLE ANY MEDIA FILE
# -------------------------------
@app.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_file(client, message):

    status = await message.reply("Saving file securely… 📦")

    # ---- Extract File Info ----
    media = message.document or message.video or message.audio
    file_name = media.file_name or "unnamed"
    file_size = media.file_size

    # ---- Forward to storage channel ----
    uploaded = await message.forward(CHANNEL_ID)

    # ---- GET FILE PATH FROM TELEGRAM ----
    file_obj = await client.get_messages(CHANNEL_ID, uploaded.id)

    file_path = file_obj.document.file_path if file_obj.document else (
                file_obj.video.file_path if file_obj.video else
                file_obj.audio.file_path)

    # ---- FINAL DIRECT LINK (Permanent) ----
    direct_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

    text = f"""
**🎬 File Processed Successfully**

📌 **File Name:** `{file_name}`
📦 **File Size:** `{round(file_size / (1024*1024), 2)} MB`

🎥 **Streaming Link:**
{direct_link}

⬇️ **Direct Download Link:**
{direct_link}

🗂 Saved safely in storage 📦
"""

    await status.edit(text)

# -------------------------------
# RUN BOT + FLASK SERVER
# -------------------------------
if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=8080)).start()
    app.run()