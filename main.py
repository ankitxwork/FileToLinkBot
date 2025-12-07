import os
import uuid
import asyncio
import subprocess
from pyrogram import Client, filters
from pyrogram.types import Message

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])

app = Client(
    "filetolink",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


@app.on_message(filters.command("start"))
async def start(_, m: Message):
    await m.reply(
        "✅ **File To Link Bot**\n\n"
        "Send me a video and I will provide:\n"
        "• Streaming (.m3u8)\n"
        "• Direct Download Link"
    )


@app.on_message(filters.private & (filters.video | filters.document))
async def handle_video(client: Client, m: Message):
    msg = await m.reply("⬇ Downloading...")

    media = m.video or m.document
    file_name = media.file_name or "video.mp4"
    file_size = round(media.file_size / (1024 * 1024), 2)

    os.makedirs("downloads", exist_ok=True)
    os.makedirs("hls", exist_ok=True)

    download_path = await client.download_media(
        m,
        file_name=f"downloads/{uuid.uuid4()}_{file_name}"
    )

    hls_id = uuid.uuid4().hex
    hls_dir = f"hls/{hls_id}"
    os.makedirs(hls_dir, exist_ok=True)

    m3u8_path = f"{hls_dir}/index.m3u8"

    await msg.edit("🎞 Converting to streaming format...")

    subprocess.run([