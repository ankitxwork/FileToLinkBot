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

# ⬅ IMPORTANT: persistent session stored in /app/data
app = Client(
    "data/HLSBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

server = Flask(__name__)

@server.route("/")
def home():
    return "Bot Running Successfully!"


@app.on_message(filters.command("start"))
async def start_msg(_, msg):
    await msg.reply(
        "**Send any *VIDEO* and I will convert it into:**\n\n"
        "🎥 HLS Streaming (.m3u8)\n"
        "⚡ Fast CDN Stream\n"
        "⬇ Direct Download Link\n"
        "💾 Saved securely in private channel\n\n"
        "Upload a video to begin…"
    )


@app.on_message(filters.private & (filters.video | filters.document))
async def convert_hls(client, message):

    status = await message.reply("Processing… 🔄")

    media = message.video or message.document
    file_name = media.file_name or "video.mp4"
    file_size = media.file_size

    # -------- DOWNLOAD --------
    await status.edit("Downloading… ⬇")
    download_path = await client.download_media(message)

    # Unique HLS output folder
    output_id = str(uuid.uuid4())
    out_folder = f"data/hls_{output_id}"
    os.makedirs(out_folder, exist_ok=True)

    m3u8_file = f"{out_folder}/index.m3u8"

    # -------- HLS CONVERSION --------
    await status.edit("Converting to HLS… 🎞")

    cmd = [
        "ffmpeg",
        "-i", download_path,
        "-codec", "copy",
        "-start_number", "0",
        "-hls_time", "4",
        "-hls_list_size", "0",
        "-f", "hls",
        m3u8_file
    ]

    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # -------- UPLOAD M3U8 --------
    await status.edit("Uploading HLS playlist… ☁")

    uploaded_m3u8 = await client.send_document(
        CHANNEL_ID,
        m3u8_file,
        caption=f"HLS Playlist for {file_name}"
    )

    # -------- UPLOAD TS FILES --------
    await status.edit("Uploading video segments… ⏳")

    for ts_file in sorted(os.listdir(out_folder)):
        if ts_file.endswith(".ts"):
            await client.send_document(CHANNEL_ID, f"{out_folder}/{ts_file}")

    # Cleanup downloaded video
    try:
        os.remove(download_path)
    except:
        pass

    # -------- TELEGRAM CDN LINK --------
    file_msg = await client.get_messages(CHANNEL_ID, uploaded_m3u8.id)
    file_info = await client.get_file(file_msg.document.file_id)

    cdn_path = file_info.file_path

    streaming_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{cdn_path}"

    # -------- RESULT MESSAGE --------
    result = f"""
**HLS Conversion Complete! 🚀**

🎥 **File:** `{file_name}`
📦 **Size:** `{round(file_size / (1024*1024), 2)} MB`

📺 **HLS Playlist (.m3u8):**
`{streaming_link}`

▶ Works in VLC, MX Player, Video.js, JWPlayer, ExoPlayer.
"""

    await status.edit(result)


if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=8080)).start()
    app.run()