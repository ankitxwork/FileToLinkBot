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
        "ffmpeg",
        "-i", download_path,
        "-c", "copy",
        "-start_number", "0",
        "-hls_time", "4",
        "-hls_list_size", "0",
        "-f", "hls",
        m3u8_path
    ], check=True)

    await msg.edit("☁ Uploading files...")

    m3u8_msg = await client.send_document(
        CHANNEL_ID,
        m3u8_path,
        caption=f"🎬 {file_name}"
    )

    for f in sorted(os.listdir(hls_dir)):
        if f.endswith(".ts"):
            await client.send_document(
                CHANNEL_ID,
                f"{hls_dir}/{f}"
            )

    file = await client.get_file(m3u8_msg.document.file_id)
    stream_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"

    result = (
        "✅ **Conversion Completed**\n\n"
        f"📁 **Name:** `{file_name}`\n"
        f"📦 **Size:** `{file_size} MB`\n\n"
        f"▶ **Streaming (.m3u8):**\n{stream_link}\n\n"
        f"⬇ **Download:**\n{stream_link}"
    )

    await msg.edit(result)


app.run()