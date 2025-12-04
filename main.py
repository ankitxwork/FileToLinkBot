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

# ----------------------------
# PYROGRAM BOT CLIENT
# ----------------------------
bot = Client(
    "cdn_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ----------------------------
# FLASK SERVER (RAILWAY)
# ----------------------------
server = Flask(__name__)

@server.route("/")
def home():
    return "Bot Running Successfully!"

# ----------------------------
# START COMMAND
# ----------------------------
@bot.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply(
        "**Send me any file and I will give you:**\n\n"
        "✔ Telegram CDN Streaming Link\n"
        "✔ Direct Download Link\n"
        "✔ File Name\n"
        "✔ File Size\n\n"
        "Works with ALL FILES — even forwarded 💯"
    )

# ----------------------------
# FILE HANDLER
# ----------------------------
@bot.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handler(client, message):

    status = await message.reply("Saving securely… 📦")

    # Detect file + size
    media = message.document or message.video or message.audio
    file_name = media.file_name or "file"
    file_size = media.file_size

    # ----------------------------
    # UPLOAD WITHOUT DOWNLOADING
    # This avoids railway storage problems
    # ----------------------------
    try:
        sent = await client.copy_message(
            chat_id=CHANNEL_ID,
            from_chat_id=message.chat.id,
            message_id=message.id
        )
    except Exception as e:
        await status.edit(f"❌ Upload failed.\n\nError: `{e}`")
        return

    # ----------------------------
    # GET CDN DIRECT LINK
    # ----------------------------
    try:
        cdn_link = await client.get_file_url(sent)
    except Exception as e:
        await status.edit(f"❌ Failed generating CDN link.\nError: `{e}`")
        return

    # ----------------------------
    # SEND RESULT
    # ----------------------------
    text = f"""
**🎬 File Ready!**

📌 **File Name:** `{file_name}`
📦 **File Size:** `{round(file_size / (1024*1024), 2)} MB`

🔗 **Streaming Link (Telegram CDN):**  
{cdn_link}

⬇️ **Direct Download Link:**  
{cdn_link}

_File stored safely in your private channel._
"""

    await status.edit(text)

# ----------------------------
# RUN BOTH
# ----------------------------
if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=8080)).start()
    bot.run()