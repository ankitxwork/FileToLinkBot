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

    output_id = str(uuid.uuid4())
    out_folder = f"hls_{output_id}"
    os.makedirs(out_folder, exist_ok=True)

    playlist_path = f"{out_folder}/index.m3u8"

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
        playlist_path
    ]

    subprocess.run(cmd)

    # -------- UPLOAD --------
    await status.edit("Uploading to channel… ☁")

    try:
        uploaded = await client.send_document(
            CHANNEL_ID,
            playlist_path,
            caption=f"HLS Playlist for {file_name}"
        )
    except Exception as e:
        await status.edit(f"❌ Upload failed:\n`{str(e)}`\n\n"
                          "➡ Your bot is NOT admin in the channel.\n"
                          "➡ Fix this by adding bot to channel manually.")
        return

    # Upload .ts files
    ts_files = sorted([f for f in os.listdir(out_folder) if f.endswith(".ts")])
    for ts in ts_files:
        await client.send_document(CHANNEL_ID, f"{out_folder}/{ts}")

    # -------- PUBLIC LINK --------
    file_info = await client.get_messages(CHANNEL_ID, uploaded.id)
    file = await client.get_file(file_info.document.file_id)
    cdn = file.file_path

    link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{cdn}"

    await status.edit(
        f"**HLS Ready! 🚀**\n\n"
        f"🎥 File: `{file_name}`\n"
        f"📦 Size: `{round(file_size/1024/1024,2)} MB`\n\n"
        f"📺 **HLS Playlist:**\n`{link}`"
    )

    shutil.rmtree(out_folder)
    os.remove(download_path)


if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=8080)).start()
    app.run()