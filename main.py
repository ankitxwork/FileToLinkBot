import os
from pyrogram import Client, filters
from flask import Flask
import threading

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))  # must be PUBLIC channel

bot = Client(
    "FileToLinkBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running ✅"


@bot.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply(
        "✅ **Send me any video or file**\n\n"
        "I will give you:\n"
        "📁 File name\n"
        "📦 File size\n"
        "▶ Streaming link\n"
        "⬇ Direct download link"
    )


@bot.on_message(filters.private & (filters.video | filters.document))
async def handle_file(client, message):
    status = await message.reply("⬆ Uploading file...")

    try:
        media = message.video or message.document

        sent = await client.send_document(
            chat_id=CHANNEL_ID,
            document=media.file_id,
            caption=f"📁 {media.file_name}"
        )

        file = sent.document
        file_name = file.file_name
        file_size = round(file.file_size / (1024 * 1024), 2)

        # ✅ Telegram auto-generates this path
        file_path = file.file_id
        download_link = f"https://t.me/{os.getenv('PUBLIC_CHANNEL_USERNAME')}/{sent.id}"

        result = (
            "✅ **File Uploaded Successfully**\n\n"
            f"📁 **Name:** `{file_name}`\n"
            f"📦 **Size:** `{file_size} MB`\n\n"
            f"▶ **Streaming Link:**\n{download_link}\n\n"
            f"⬇ **Download Link:**\n{download_link}"
        )

        await status.edit(result)

    except Exception as e:
        await status.edit(f"❌ Error:\n`{e}`")


def run_flask():
    app.run(host="0.0.0.0", port=8080)


if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.run()