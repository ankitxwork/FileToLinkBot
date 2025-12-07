import os
import uuid
import logging
import subprocess
from pyrogram import Client, filters
from flask import Flask
from threading import Thread

# ───── Logging ─────
logging.basicConfig(level=logging.INFO)

# ───── ENV ─────
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])  # MUST BE PUBLIC CHANNEL USERNAME ID

# ───── Pyrogram Bot ─────
app = Client(
    "filetolink",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# ───── Flask (Railway requirement) ─────
server = Flask(__name__)

@server.route("/")
def home():
    return "Bot is alive ✅"

def run_flask():
    server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# ───── Commands ─────
@app.on_message(filters.command("start"))
async def start(_, m):
    await m.reply("📤 Send a video file to convert into HLS (.m3u8)")

# ───── HLS Logic ─────
@app.on_message(filters.private & (filters.video | filters.document))
async def convert(client, message):
    status = await message.reply("⬇ Downloading...")

    media = message.video or message.document
    filename = media.file_name or "video.mp4"

    os.makedirs("downloads", exist_ok=True)
    os.makedirs("hls", exist_ok=True)

    try:
        input_path = await client.download_media(
            message,
            file_name=f"downloads/{filename}"
        )
    except Exception as e:
        await status.edit(f"❌ Download failed\n`{e}`")
        return

    await status.edit("🎞 Converting to HLS...")

    uid = uuid.uuid4().hex
    out_dir = f"hls/{uid}"
    os.makedirs(out_dir, exist_ok=True)

    m3u8 = f"{out_dir}/index.m3u8"

    subprocess.run([
        "ffmpeg", "-i", input_path,
        "-codec", "copy",
        "-start_number", "0",
        "-hls_time", "4",
        "-hls_list_size", "0",
        "-f", "hls",
        m3u8
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    await status.edit("☁ Uploading...")

    playlist_msg = await client.send_document(
        CHANNEL_ID,
        m3u8,
        caption=f"HLS Playlist\n{filename}"
    )

    for f in sorted(os.listdir(out_dir)):
        if f.endswith(".ts"):
            await client.send_document(CHANNEL_ID, f"{out_dir}/{f}")

    # ✅ CORRECT LINK METHOD
    link = f"https://t.me/{playlist_msg.chat.username}/{playlist_msg.id}"

    await status.edit(
        f"✅ Done!\n\n"
        f"📺 **HLS Playlist:**\n{link}"
    )

# ───── RUN ─────
if __name__ == "__main__":
    Thread(target=run_flask).start()
    app.run()