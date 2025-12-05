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

    os.makedirs("downloads", exist_ok=True)

    # ---------------- DOWNLOAD ----------------
    await status.edit("Downloading… ⬇")

    try:
        download_path = await client.download_media(
            message,
            file_name=f"downloads/{file_name}"
        )
    except Exception as e:
        return await status.edit(f"❌ Download error:\n`{e}`")

    # ---------------- HLS CONVERSION ----------------
    await status.edit("Converting to HLS… 🎞")

    output_id = str(uuid.uuid4())
    out_folder = f"hls_{output_id}"
    os.makedirs(out_folder, exist_ok=True)

    m3u8_file = f"{out_folder}/index.m3u8"

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

    # ---------------- UPLOAD ----------------
    await status.edit("Uploading files to channel… ☁")

    try:
        uploaded_m3u8 = await client.send_document(
            CHANNEL_ID,
            m3u8_file,
            caption=f"HLS Playlist for {file_name}"
        )
    except Exception as e:
        return await status.edit(f"❌ ERROR: Cannot upload to channel.\n`{e}`\n\n"
                                 "➡ Make sure bot is ADMIN in your channel.")

    for ts in sorted(os.listdir(out_folder)):
        if ts.endswith(".ts"):
            await client.send_document(CHANNEL_ID, f"{out_folder}/{ts}")

    # ---------------- GET TELEGRAM CDN LINK ----------------
    try:
        file_info = await client.get_file(uploaded_m3u8.document.file_id)
    except Exception as e:
        return await status.edit(f"❌ Error generating link:\n`{e}`")

    cdn_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"

    await status.edit(
        f"**HLS Conversion Complete! 🚀**\n\n"
        f"📺 **Playlist (.m3u8):**\n`{cdn_link}`"
    )


if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=8080)).start()
    app.run()