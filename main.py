import os
import uuid
import logging
import subprocess
from pyrogram import Client, filters
from flask import Flask

# ---------------- CONFIG ----------------
logging.basicConfig(level=logging.INFO)

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])
PORT = int(os.environ.get("PORT", 8080))

# ---------------- PYROGRAM ----------------
app = Client(
    name="FileToLinkBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# ---------------- FLASK (Railway keep-alive) ----------------
web = Flask(__name__)

@web.route("/")
def home():
    return "✅ FileToLink Bot is running"

# ---------------- START ----------------
@app.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply(
        "Send a *video file* and I will convert it to:\n\n"
        "🎥 HLS (.m3u8)\n"
        "⚡ Streaming link\n"
        "☁ Stored in your channel"
    )

# ---------------- CONVERTER ----------------
@app.on_message(filters.private & (filters.video | filters.document))
async def convert(client, message):
    status = await message.reply("Processing… 🔄")

    media = message.video or message.document
    filename = media.file_name or "video.mp4"

    os.makedirs("downloads", exist_ok=True)

    try:
        await status.edit("Downloading… ⬇")
        input_path = await client.download_media(
            message, file_name=f"downloads/{filename}"
        )

        await status.edit("Converting to HLS… 🎞")

        out_id = str(uuid.uuid4())
        out_dir = f"hls_{out_id}"
        os.makedirs(out_dir, exist_ok=True)

        m3u8_path = f"{out_dir}/index.m3u8"

        subprocess.run([
            "ffmpeg",
            "-i", input_path,
            "-codec", "copy",
            "-start_number", "0",
            "-hls_time", "4",
            "-hls_list_size", "0",
            "-f", "hls",
            m3u8_path
        ], check=True)

        # ✅ IMPORTANT: resolve peer once
        await client.get_chat(CHANNEL_ID)

        await status.edit("Uploading HLS files… ☁")

        playlist_msg = await client.send_document(
            CHANNEL_ID,
            m3u8_path,
            caption=f"HLS Playlist — {filename}"
        )

        for file in sorted(os.listdir(out_dir)):
            if file.endswith(".ts"):
                await client.send_document(
                    CHANNEL_ID,
                    f"{out_dir}/{file}"
                )

        # ✅ DIRECT TELEGRAM FILE LINK (NO get_messages)
        file_path = playlist_msg.document.file_id
        file = await client.get_file(file_path)

        link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"

        await status.edit(
            f"✅ *HLS Ready*\n\n"
            f"🎥 `{filename}`\n\n"
            f"📺 `.m3u8` link:\n{link}"
        )

    except Exception as e:
        logging.exception(e)
        await status.edit(f"❌ Error:\n`{e}`")

# ---------------- MAIN ----------------
if __name__ == "__main__":
    from threading import Thread
    Thread(target=lambda: web.run(host="0.0.0.0", port=PORT)).start()
    app.run()