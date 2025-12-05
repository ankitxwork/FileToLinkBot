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
        "**Send any *VIDEO* and I will convert it into:**\n\n"
        "🎥 HLS Streaming (.m3u8)\n"
        "⚡ Fast CDN Stream\n"
        "⬇ Direct Download Link\n"
        "💾 Saved securely in private channel"
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

    # HLS OUTPUT FOLDER
    output_id = str(uuid.uuid4())
    out_folder = f"hls_{output_id}"
    os.makedirs(out_folder, exist_ok=True)

    m3u8_file = f"{out_folder}/index.m3u8"

    # -------- HLS CONVERSION --------
    await status.edit("Converting to HLS… 🎞")

    cmd = [
        "ffmpeg",
        "-i", download_path,
        "-codec:", "copy",
        "-start_number", "0",
        "-hls_time", "4",
        "-hls_list_size", "0",
        "-f", "hls",
        m3u8_file
    ]

    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # -------- UPLOAD TO CHANNEL --------
    await status.edit("Uploading HLS files… ☁")

    uploaded_m3u8 = await client.send_document(
        CHANNEL_ID,
        m3u8_file,
        caption=f"HLS Playlist for {file_name}"
    )

    # Upload .ts chunks
    ts_links = []
    for ts_file in sorted(os.listdir(out_folder)):
        if ts_file.endswith(".ts"):
            ts_path = f"{out_folder}/{ts_file}"
            msg_ts = await client.send_document(CHANNEL_ID, ts_path)
            ts_links.append(msg_ts)

    # Delete local files
    try:
        os.remove(download_path)
    except:
        pass

    # -------- GENERATE PUBLIC LINKS --------
    file_details = await client.get_messages(CHANNEL_ID, uploaded_m3u8.id)
    file_info = await client.get_file(file_details.document.file_id)
    cdn_path = file_info.file_path

    download_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{cdn_path}"

    result = f"""
**HLS Conversion Complete! 🚀**

🎥 **Original File:** `{file_name}`
📦 **Size:** `{round(file_size / (1024*1024), 2)} MB`

📺 **HLS Playlist (.m3u8):**
`{download_link}`

⚠ Important:
To play HLS, use any player that supports `.m3u8`  
(VLC, MX Player, Video.js, ExoPlayer, JWPlayer)
"""

    await status.edit(result)


if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=8080)).start()
    app.run()