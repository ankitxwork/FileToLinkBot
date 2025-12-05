# main.py
import os
import logging
import uuid
import shutil
import subprocess
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.errors import PeerIdInvalid, ChatAdminRequired
from flask import Flask

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- env ---
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", 0))
PORT = int(os.environ.get("PORT", 8080))

if not (API_ID and API_HASH and BOT_TOKEN and CHANNEL_ID):
    logging.error("Missing env vars. Make sure API_ID, API_HASH, BOT_TOKEN and CHANNEL_ID are set.")
    raise SystemExit("Missing essential environment variables")

# --- Pyrogram client ---
bot = Client(
    "HLSBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    # don't persist huge local session; this is fine for a bot
)

# --- Flask server (keeps Railway container alive) ---
server = Flask(__name__)

@server.route("/")
def home():
    return "Bot Running Successfully!"

# --- Helpers ---
def run_ffmpeg_to_hls(input_path: str, out_dir: str) -> (bool, str):
    """
    Run ffmpeg to convert a video to HLS (index.m3u8 + .ts segments).
    Returns (success, stderr_text)
    """
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    m3u8 = os.path.join(out_dir, "index.m3u8")
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-c", "copy",
        "-start_number", "0",
        "-hls_time", "4",
        "-hls_list_size", "0",
        "-f", "hls",
        m3u8
    ]
    logging.info("Running ffmpeg: %s", " ".join(cmd))
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return True, proc.stderr
    except subprocess.CalledProcessError as e:
        logging.error("ffmpeg error: %s", e.stderr[:1000])
        return False, e.stderr

def build_bot_file_url(file_path: str) -> str:
    """
    Build bot API download URL for a given file_path returned by get_file.
    """
    return f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

# --- Commands & handlers ---
@bot.on_message(filters.command("start"))
async def start(_, message):
    await message.reply(
        "**Send any VIDEO (or a file) and I'll convert it to HLS (.m3u8) and give you a CDN link.**\n\n"
        "• Works with forwarded files\n"
        "• Bot must be admin in your private storage channel"
    )

@bot.on_message(filters.private & (filters.video | filters.document))
async def handle_convert(client, message):
    status = await message.reply("Processing… 🔄")
    try:
        media = message.video or message.document
        file_name = getattr(media, "file_name", None) or "video.mp4"
        file_size = getattr(media, "file_size", 0)

        await status.edit("Downloading… ⬇️")
        download_path = await client.download_media(message)
        logging.info("Downloaded to %s", download_path)

        # prepare HLS output folder
        uid = uuid.uuid4().hex[:12]
        out_dir = f"/tmp/hls_{uid}"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        await status.edit("Converting to HLS… 🎞")

        ok, ff_err = run_ffmpeg_to_hls(download_path, out_dir)
        if not ok:
            await status.edit("⚠ Conversion failed. Check ffmpeg logs.")
            logging.error("FFMPEG failed: %s", ff_err[:2000])
            return

        # Upload playlist (.m3u8) first
        m3u8_path = os.path.join(out_dir, "index.m3u8")
        await status.edit("Uploading playlist to storage channel… ☁️")
        try:
            uploaded_msg = await client.send_document(
                chat_id=CHANNEL_ID,
                document=m3u8_path,
                caption=f"HLS playlist for {file_name}"
            )
        except PeerIdInvalid:
            await status.edit("❌ Cannot access channel. Make sure the bot is admin in the channel and CHANNEL_ID is correct.")
            logging.exception("PeerIdInvalid while sending playlist. CHANNEL_ID=%s", CHANNEL_ID)
            return
        except ChatAdminRequired:
            await status.edit("❌ Bot must be admin to post files in the storage channel.")
            logging.exception("ChatAdminRequired while sending playlist.")
            return
        except Exception as e:
            await status.edit(f"❌ Failed uploading playlist: {e}")
            logging.exception("Failed upload playlist")
            return

        # Upload all .ts files
        await status.edit("Uploading segment files (.ts)… ⬆️")
        ts_count = 0
        for f in sorted(os.listdir(out_dir)):
            if f.endswith(".ts"):
                ts_path = os.path.join(out_dir, f)
                try:
                    await client.send_document(chat_id=CHANNEL_ID, document=ts_path)
                    ts_count += 1
                except Exception as e:
                    logging.warning("Failed to upload ts file %s: %s", ts_path, e)

        # cleanup local download & hls folder
        try:
            os.remove(download_path)
        except Exception:
            pass

        try:
            shutil.rmtree(out_dir)
        except Exception:
            pass

        # get file_path for the uploaded playlist so we can build CDN url
        try:
            msg = await client.get_messages(CHANNEL_ID, uploaded_msg.id)
            file_obj = msg.document or msg.audio or msg.video or msg.document
            file_id = file_obj.file_id
            file_info = await client.get_file(file_id)
            file_path = file_info.file_path  # path on telegram CDN
            cdn_url = build_bot_file_url(file_path)
        except Exception as e:
            logging.exception("Failed to fetch file_path for CDN link: %s", e)
            cdn_url = "Could not build CDN link (see logs)."

        # final message
        out_text = (
            f"**HLS Conversion Complete! 🚀**\n\n"
            f"🎥 **Original:** `{file_name}`\n"
            f"📦 **Size:** `{round(file_size / (1024*1024), 2)} MB`\n\n"
            f"📺 **HLS Playlist (.m3u8):**\n{cdn_url}\n\n"
            "⚠ To play HLS, use a player that supports .m3u8 (VLC, ExoPlayer, Video.js, etc.)\n"
            "_Playlist & segments saved in your private storage channel._"
        )

        await status.edit(out_text)
    except Exception as e:
        logging.exception("Unexpected error in handler")
        await status.edit(f"❌ Unexpected error: {e}")

# --- run ---
if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=PORT)).start()
    bot.run()