import os
import logging
import uuid
import tempfile
import subprocess
from flask import Flask
from pyrogram import Client, filters
from pyrogram.errors import RPCError

logging.basicConfig(level=logging.INFO)

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])

app = Client(
    "session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

server = Flask(__name__)

@server.route("/")
def home():
    return "Bot Active"

def convert_to_hls(input_file, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    m3u8_file = os.path.join(out_dir, "index.m3u8")

    cmd = [
        "ffmpeg", "-y",
        "-i", input_file,
        "-c", "copy",
        "-start_number", "0",
        "-hls_time", "4",
        "-hls_list_size", "0",
        "-hls_segment_filename", os.path.join(out_dir, "seg_%03d.ts"),
        "-f", "hls",
        m3u8_file
    ]

    result = subprocess.run(cmd, stderr=subprocess.PIPE)
    return result.returncode == 0, m3u8_file

@app.on_message(filters.command("start"))
async def start_msg(_, message):
    await message.reply("Send a *video file* to convert into **HLS (.m3u8)**")

@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    status = await message.reply("Processing… 🔄")

    try:
        # 1) Download
        await status.edit("Downloading… ⬇️")
        tmp = tempfile.mkdtemp()
        in_path = await client.download_media(message, file_name=os.path.join(tmp, "input.mp4"))

        # 2) HLS Convert
        out_dir = os.path.join(tmp, "hls")
        await status.edit("Converting to HLS… 🎞️")
        ok, m3u8_path = convert_to_hls(in_path, out_dir)

        if not ok:
            await status.edit("❌ Conversion Failed")
            return

        # 3) Upload playlist first
        await status.edit("Uploading HLS playlist… ☁️")
        m3u8_msg = await client.send_document(CHANNEL_ID, m3u8_path)

        # 4) Upload TS segments
        await status.edit("Uploading segments… 📦")

        for f in sorted(os.listdir(out_dir)):
            if f.endswith(".ts"):
                await client.send_document(CHANNEL_ID, os.path.join(out_dir, f))

        # 5) Generate CDN link for playlist
        file_info = await client.get_file(m3u8_msg.document.file_id)
        hls_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"

        await status.edit(f"✅ HLS Ready!\n\n📺 **Playlist:**\n{hls_url}")

    except RPCError as e:
        await status.edit(f"❌ Telegram Error: {e}")
    except Exception as e:
        await status.edit(f"❌ Error: {e}")

if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=8080)).start()
    app.run()