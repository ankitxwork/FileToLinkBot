import os
import logging
from pyrogram import Client, filters
from flask import Flask
import subprocess
import uuid
import shutil

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
        "**Send a VIDEO and I will convert it to:**\n\n"
        "🎬 HLS Streaming (.m3u8)\n"
        "⚡ Fast CDN stream link\n"
        "⬇ Direct download link\n"
        "💾 Stored privately in your storage channel"
    )


@app.on_message(filters.private & (filters.video | filters.document))
async def convert_hls(client, message):
    status = await message.reply("Processing… 🔄")

    media = message.video or message.document
    file_name = media.file_name or "video.mp4"
    file_size = media.file_size

    # -------- DOWNLOAD --------
    await status.edit("Downloading File… ⬇")
    download_path = await client.download_media(message)

    # HLS OUTPUT FOLDER
    output_id = str(uuid.uuid4())
    out_folder = f"hls_{output_id}"
    os.makedirs(out_folder, exist_ok=True)

    m3u8_file = f"{out_folder}/index.m3u8"

    # -------- RUN FFMPEG --------
    await status.edit("Converting to HLS… 🎞")

    cmd = [
        "ffmpeg",
        "-i", download_path,
        "-c:v", "copy",
        "-c:a", "copy",
        "-hls_time", "4",
        "-hls_list_size", "0",
        "-hls_segment_filename", f"{out_folder}/seg_%04d.ts",
        m3u8_file
    ]

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if proc.returncode != 0:
        await status.edit("❌ FFmpeg failed! Cannot convert file.")
        return

    # -------- UPLOAD M3U8 --------
    await status.edit("Uploading playlist… ☁")

    uploaded_m3u8 = await client.send_document(
        CHANNEL_ID,
        m3u8_file,
        caption=f"HLS Playlist for {file_name}"
    )

    # -------- UPLOAD TS CHUNKS --------
    await status.edit("Uploading video segments… ⏳")

    for chunk in sorted(os.listdir(out_folder)):
        if chunk.endswith(".ts"):
            await client.send_document(
                CHANNEL_ID,
                f"{out_folder}/{chunk}"
            )

    # Cleanup local storage
    try:
        shutil.rmtree(out_folder)
        os.remove(download_path)
    except:
        pass

    # -------- GENERATE CDN LINK --------
    file_details = await client.get_messages(CHANNEL_ID, uploaded_m3u8.id)
    file_info = await client.get_file(file_details.document.file_id)

    cdn_path = file_info.file_path
    cdn_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{cdn_path}"

    # RESPONSE
    final_msg = f"""
**✅ HLS Conversion Complete!**

🎬 **File:** `{file_name}`
📦 **Size:** `{round(file_size / (1024*1024), 2)} MB`

📺 **HLS Stream Link (.m3u8):**