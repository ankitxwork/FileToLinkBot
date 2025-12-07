import os
import uuid
import subprocess
import logging
from flask import Flask
from pyrogram import Client, filters

# ---------- LOGGING ----------
logging.basicConfig(level=logging.INFO)

# ---------- ENV ----------
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])
PORT = int(os.environ.get("PORT", 8080))

# ---------- PYROGRAM ----------
bot = Client(
    "filetolink",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# ---------- FLASK ----------
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Bot is Running"

# ---------- COMMAND ----------
@bot.on_message(filters.command("start") & filters.private)
async def start(_, msg):
    await msg.reply(
        "✅ **Send a video file**\n\n"
        "I will convert it to **HLS (.m3u8)** and give you a streaming link."
    )

# ---------- MAIN HANDLER ----------
@bot.on_message(filters.private & (filters.video | filters.document))
async def handler(client, message):
    status = await message.reply("⬇ Downloading...")

    media = message.video or message.document
    filename = media.file_name or "video.mp4"

    os.makedirs("downloads", exist_ok=True)
    os.makedirs("hls", exist_ok=True)

    # ---- DOWNLOAD ----
    input_path = await client.download_media(
        message,
        file_name=f"downloads/{filename}"
    )

    await status.edit("🎞 Converting to HLS...")

    uid = str(uuid.uuid4())
    out_dir = f"hls/{uid}"
    os.makedirs(out_dir, exist_ok=True)

    playlist = f"{out_dir}/index.m3u8"

    # ---- FFMPEG ----
    subprocess.run([
        "ffmpeg", "-y",
        "-i", input_path,
        "-codec", "copy",
        "-start_number", "0",
        "-hls_time", "4",
        "-hls_list_size", "0",
        "-f", "hls",
        playlist
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    await status.edit("☁ Uploading files...")

    # ---- UPLOAD PLAYLIST ----
    sent = await client.send_document(
        chat_id=CHANNEL_ID,
        document=playlist,
        caption=f"HLS playlist for {filename}"
    )

    # ---- UPLOAD SEGMENTS ----
    for file in sorted(os.listdir(out_dir)):
        if file.endswith(".ts"):
            await client.send_document(
                CHANNEL_ID,
                f"{out_dir}/{file}"
            )

    # ✅ DIRECT FILE LINK (NO async generator)
    file_path = sent.document.file_id
    link = f"https://t.me/c/{str(CHANNEL_ID)[4:]}/{sent.id}"

    await status.edit(
        f"✅ **HLS Ready**\n\n"
        f"📺 Playlist Message:\n{link}"
    )

# ---------- START ----------
if __name__ == "__main__":
    from threading import Thread
    Thread(target=lambda: app.run(host="0.0.0.0", port=PORT)).start()
    bot.run()