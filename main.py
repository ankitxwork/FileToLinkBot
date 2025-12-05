import os
import uuid
import logging
import subprocess
from pyrogram import Client, filters
from flask import Flask

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
        "**Send any VIDEO and I will convert to:**\n"
        "🎥 HLS Streaming (.m3u8)\n"
        "⚡ Telegram-powered CDN\n"
        "⬇ Direct Download Link\n"
    )


@app.on_message(filters.private & (filters.video | filters.document))
async def convert_hls(client, message):
    status = await message.reply("Processing… 🔄")

    media = message.video or message.document
    file_name = media.file_name or "video.mp4"

    # ---- DOWNLOAD ----
    await status.edit("Downloading… ⬇")
    input_path = await client.download_media(message)

    # ---- MAKE TEMP HLS FOLDER (RAM DISK) ----
    session_id = uuid.uuid4().hex
    hls_dir = f"/tmp/hls_{session_id}"
    os.makedirs(hls_dir, exist_ok=True)

    hls_playlist = f"{hls_dir}/index.m3u8"

    # ---- RUN FFMPEG → CREATE HLS FILES ----
    await status.edit("Converting to HLS… 🎞")

    cmd = [
        "ffmpeg",
        "-i", input_path,
        "-codec:", "copy",
        "-start_number", "0",
        "-hls_time", "4",
        "-hls_list_size", "0",
        "-f", "hls",
        hls_playlist
    ]

    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    await status.edit("Uploading to Telegram… ☁")

    # ---- UPLOAD M3U8 PLAYLIST ----
    uploaded_m3u8 = await client.send_document(
        CHANNEL_ID,
        hls_playlist,
        caption=f"HLS Playlist for {file_name}"
    )

    # ---- UPLOAD .TS CHUNKS ----
    ts_files = sorted([f for f in os.listdir(hls_dir) if f.endswith(".ts")])
    for ts in ts_files:
        ts_path = f"{hls_dir}/{ts}"
        await client.send_document(CHANNEL_ID, ts_path)

    # ---- GENERATE TELEGRAM CDN LINK ----
    details = await client.get_messages(CHANNEL_ID, uploaded_m3u8.id)
    file = await client.get_file(details.document.file_id)
    m3u8_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"

    # ---- DONE ----
    await status.edit(
        f"**HLS Ready! 🚀**\n\n"
        f"🎞 **Playlist:** `{m3u8_link}`\n\n"
        f"Play this link in VLC, MX Player, or any HLS player."
    )


if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=8080)).start()
    app.run()