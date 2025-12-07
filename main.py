import os
import uuid
import asyncio
import subprocess
from pyrogram import Client, filters
from flask import Flask

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL = os.environ["CHANNEL_ID"]  # use @username

bot = Client(
    "filetolink",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is Alive ✅"


@bot.on_message(filters.command("start"))
async def start(_, m):
    await m.reply(
        "🎥 Send me a video\n\n"
        "I will generate:\n"
        "• Streaming link\n"
        "• Download link\n"
        "• File details"
    )


@bot.on_message(filters.private & (filters.video | filters.document))
async def handle_file(client, message):
    status = await message.reply("⬇ Downloading...")

    media = message.video or message.document
    name = media.file_name or "video.mp4"
    size_mb = round(media.file_size / (1024 * 1024), 2)

    os.makedirs("tmp", exist_ok=True)
    path = await client.download_media(message, file_name=f"tmp/{name}")

    await status.edit("☁ Uploading to channel...")

    sent = await client.send_document(
        CHANNEL,
        path,
        caption=f"📂 {name}\n📦 {size_mb} MB"
    )

    file_id = sent.document.file_id
    file = await client.get_file(file_id)

    download = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
    stream = download  # Telegram direct stream

    await status.edit(
        f"✅ **Done!**\n\n"