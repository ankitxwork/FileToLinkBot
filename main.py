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

# IMPORTANT: No session file (Railway ephemeral), so use bot mode only
app = Client(
    name="bot-session",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH
)

server = Flask(__name__)

@server.route("/")
def home():
    return "HLS Bot Running Successfully!"

@app.on_message(filters.command("start"))
async def start_msg(_, msg):
    await msg.reply(
        "**🎥 Send any *VIDEO* and I will convert it into:**\n"
        "• HLS Streaming (.m3u8)\n"
        "• Fast CDN Stream Link\n"
        "• Direct Download Link\n"
        "• Saved in Private Channel\n\n"
        "⚡ Supports MP4, MKV, WebM"
    )


@app.on_message(filters.private & (filters.video | filters.document))
async def convert_hls(client, message):
    status = await message.reply("Processing… 🔄")

    media = message.video or message.document
    file_name = media.file_name or "video.mp4"
    file_size = media.file_size

    # STEP 1 — DOWNLOAD
    await status.edit("⬇ Downloading file…")
    try:
        download_path = await client.download_media(message)
    except Exception as e:
        await status.edit(f"❌ Download failed:\n`{e}`")
        return

    # Unique folder for HLS
    output_id = uuid.uuid4().hex
    out_folder = f"hls_{output_id}"
    os.makedirs(out_folder, exist_ok=True)

    m3u8_file = f"{out_folder}/index.m3u8"

    # STEP 2 — Convert to HLS
    await status.edit("🎞 Converting video to HLS…")

    cmd = [
        "ffmpeg",
        "-i", download_path,
        "-preset", "veryfast",
        "-hls_time", "4",
        "-hls_list_size", "0",
        "-hls_segment_filename", f"{out_folder}/seg_%03d.ts",
        "-f", "hls",
        m3u8_file
    ]

    process = subprocess.run(cmd, stderr=subprocess.PIPE)
    if process.returncode != 0:
        await status.edit("❌ FFmpeg failed to convert file.")
        return

    # STEP 3 — Upload .m3u8 file
    await status.edit("☁ Uploading playlist…")

    try:
        uploaded_m3u8 = await client.send_document(
            CHANNEL_ID,
            m3u8_file,
            caption=f"HLS Playlist for {file_name}"
        )
    except Exception as e:
        await status.edit(f"❌ Upload failed:\n`{e}`")
        return

    # STEP 4 — Upload TS chunks
    await status.edit("☁ Uploading video segments…")

    ts_uploaded = []
    for ts in sorted(os.listdir(out_folder)):
        if ts.endswith(".ts"):
            path = f"{out_folder}/{ts}"
            msg_ts = await client.send_document(CHANNEL_ID, path)
            ts_uploaded.append(msg_ts)

    # Cleanup temp files
    try:
        os.remove(download_path)
        shutil.rmtree(out_folder)
    except:
        pass

    # STEP 5 — Generate File Link
    file_info = await client.get_messages(CHANNEL_ID, uploaded_m3u8.id)
    file_meta = await client.get_file(file_info.document.file_id)
    cdn_path = file_meta.file_path

    stream_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{cdn_path}"

    await status.edit(
        f"✅ **HLS Conversion Complete!**\n\n"
        f"📌 **File:** `{file_name}`\n"
        f"📦 **Size:** `{round(file_size / (1024*1024), 2)} MB`\n\n"
        f"🎥 **HLS Playlist (.m3u8):**\n`{stream_link}`\n\n"
        f"⚠️ Use a player that supports `.m3u8` (VLC, MX Player, Video.js)"
    )


if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=8080)).start()
    app.run()