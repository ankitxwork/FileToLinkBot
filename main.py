import os
import logging
from pyrogram import Client, filters
from flask import Flask
import subprocess
import uuid

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])

app = Client(
    "HLSBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

server = Flask(__name__)

@server.route("/")
def home():
    return "Bot Running Successfully!"


@app.on_message(filters.command("start"))
async def start_msg(_, msg):
    await msg.reply(
        "**Send any *VIDEO FILE* and I will convert it into:**\n\n"
        "🎥 HLS Streaming (.m3u8)\n"
        "⚡ CDN-based Stream Link\n"
        "⬇ Direct Download Link\n"
        "💾 Stored safely in private channel"
    )


@app.on_message(filters.private & (filters.video | filters.document))
async def convert_hls(client, message):

    status = await message.reply("Processing… 🔄")

    # ---------------------------
    # SAFE MEDIA DETECTION FIX
    # ---------------------------
    if message.video:
        media = message.video
    elif message.document and message.document.mime_type.startswith("video"):
        media = message.document
    else:
        await status.edit("❌ Please send a valid *video file*.")
        return

    file_name = media.file_name or "video.mp4"
    file_size = media.file_size

    os.makedirs("downloads", exist_ok=True)

    await status.edit("Downloading video… ⬇")

    try:
        download_path = await client.download_media(
            message,
            file_name=f"downloads/{file_name}"
        )
    except Exception as e:
        await status.edit(f"❌ Download Error:\n`{e}`")
        return

    # ---------------------------
    # HLS CONVERSION
    # ---------------------------

    out_id = uuid.uuid4().hex
    out_folder = f"hls_{out_id}"
    os.makedirs(out_folder, exist_ok=True)

    m3u8_path = f"{out_folder}/index.m3u8"

    await status.edit("Converting to HLS… 🎞")

    cmd = [
        "ffmpeg",
        "-i", download_path,
        "-c:v", "copy",
        "-c:a", "copy",
        "-hls_time", "4",
        "-hls_playlist_type", "vod",
        "-hls_segment_filename", f"{out_folder}/segment_%03d.ts",
        m3u8_path
    ]

    subprocess.run(cmd)

    # ---------------------------
    # UPLOAD
    # ---------------------------
    await status.edit("Uploading HLS files… ☁")

    try:
        playlist_msg = await client.send_document(
            CHANNEL_ID,
            m3u8_path,
            caption=f"HLS Playlist for {file_name}"
        )
    except Exception as e:
        await status.edit(f"❌ Upload Error:\n`{e}`")
        return

    # Upload TS segments
    for ts in sorted(os.listdir(out_folder)):
        if ts.endswith(".ts"):
            await client.send_document(CHANNEL_ID, f"{out_folder}/{ts}")

    # ---------------------------
    # CREATE PUBLIC LINK
    # ---------------------------
    file = await client.get_messages(CHANNEL_ID, playlist_msg.id)
    file_info = await client.get_file(file.document.file_id)

    public_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"

    await status.edit(
        f"✅ **HLS Conversion Done!**\n\n"
        f"🎥 **File:** `{file_name}`\n"
        f"📦 **Size:** {round(file_size/1024/1024, 2)} MB\n\n"
        f"📺 **HLS Playlist:**\n`{public_link}`"
    )


if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=8080)).start()
    app.run()