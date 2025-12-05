# main.py
import os
import shutil
import logging
import subprocess
import asyncio
from pathlib import Path
from math import ceil

from pyrogram import Client, filters
from flask import Flask, send_from_directory, abort

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# Environment variables (make sure these are set in Railway / your deploy)
API_ID = int(os.environ.get("API_ID") or 0)
API_HASH = os.environ.get("API_HASH") or ""
BOT_TOKEN = os.environ.get("BOT_TOKEN") or ""
CHANNEL_ID = int(os.environ.get("CHANNEL_ID") or 0)
PORT = int(os.environ.get("PORT") or 8080)
BASE_STREAM_DIR = Path("streams")

# Create streams directory
BASE_STREAM_DIR.mkdir(exist_ok=True)

logging.info("🚀 Starting CDN HLS bot...")

# Pyrogram client
app = Client(
    "CDNFileBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# Flask server to serve HLS files
server = Flask(__name__, static_folder=None)


@server.route("/streams/<stream_id>/<path:filename>")
def serve_stream_file(stream_id: str, filename: str):
    folder = BASE_STREAM_DIR / stream_id
    if not folder.exists():
        abort(404)
    # Security: only allow files under the folder
    return send_from_directory(folder.resolve(), filename)


@server.route("/streams/<stream_id>/")
def serve_stream_index(stream_id: str):
    # Redirect or show index.m3u8
    folder = BASE_STREAM_DIR / stream_id
    if not folder.exists():
        abort(404)
    return send_from_directory(folder.resolve(), "index.m3u8")


def ffmpeg_available() -> bool:
    """Check if ffmpeg exists in PATH"""
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


async def make_hls(input_file: str, out_dir: Path, playlist_name: str = "index.m3u8"):
    """
    Convert input_file to HLS in out_dir using ffmpeg.
    Returns path to index.m3u8 on success.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    # Make sure output files are deterministic and isolated
    playlist_path = out_dir / playlist_name
    segment_pattern = str(out_dir / "seg_%05d.ts")

    # Basic HLS command (VOD)
    cmd = [
        "ffmpeg", "-y",
        "-i", input_file,
        "-c:v", "copy",
        "-c:a", "copy",
        "-hls_time", "6",
        "-hls_playlist_type", "vod",
        "-hls_segment_filename", segment_pattern,
        str(playlist_path)
    ]

    logging.info("Running ffmpeg for HLS: %s", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        logging.error("ffmpeg failed: rc=%s stderr=%s", proc.returncode, stderr.decode(errors="ignore"))
        raise RuntimeError("ffmpeg conversion failed")
    logging.info("ffmpeg completed, playlist: %s", playlist_path)
    return playlist_path


@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message):
    await message.reply(
        "**Send me any file and I will convert to HLS and store locally**\n\n"
        "✔ Local HLS streaming link (index.m3u8)\n"
        "✔ Telegram direct download link (if upload to storage channel succeeds)\n\n"
        "Requirements: ffmpeg must be available in the container."
    )


@app.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_media(client, message):
    status = await message.reply("Processing… 🔄\nThis may take a few seconds depending on file size.")
    try:
        # Extract media wrapper
        media = message.document or message.video or message.audio
        file_name = getattr(media, "file_name", None) or "file"
        file_size = getattr(media, "file_size", 0)

        # Step 1: download local copy (to /tmp)
        tmp_dir = Path("/tmp") / f"cdnbot_{message.message_id}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        logging.info("Downloading media to %s", tmp_dir)
        file_path = await client.download_media(message, file_name=str(tmp_dir / file_name))
        if not file_path:
            await status.edit("❌ Failed to download media.")
            return

        # Step 2: Convert to HLS (if ffmpeg available)
        stream_id = str(message.message_id)
        out_dir = BASE_STREAM_DIR / stream_id
        # Remove existing dir if present to avoid stale files
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        if ffmpeg_available():
            try:
                playlist = await make_hls(file_path, out_dir, playlist_name="index.m3u8")
                local_stream_url = f"/streams/{stream_id}/index.m3u8"
                # If you're serving externally, Railway URL + local_stream_url will be the full link:
                # e.g. https://<your-app>.railway.app/streams/<id>/index.m3u8
            except Exception as e:
                logging.exception("HLS conversion failed, will continue but no HLS produced.")
                playlist = None
                local_stream_url = None
        else:
            logging.warning("ffmpeg not available. Skipping HLS conversion.")
            playlist = None
            local_stream_url = None

        # Step 3: Upload original file to storage channel (so it's saved)
        telegram_download_link = None
        try:
            sent = await client.send_document(
                chat_id=CHANNEL_ID,
                document=str(file_path),
                caption=file_name
            )
            # Try to get file path via get_file
            try:
                file_info = await client.get_file(sent.document.file_id)
                # HTTP file link for bot to download via Bot API
                file_path_on_telegram = file_info.file_path
                telegram_download_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path_on_telegram}"
            except Exception:
                logging.exception("Could not get file path from Telegram (get_file failed).")
                telegram_download_link = None
        except Exception as exc:
            logging.exception("Upload to storage channel failed.")
            # If peer id invalid (channel not recognized), return clear instructions
            msg = str(exc)
            if "Peer id invalid" in msg or "ID not found" in msg or "USER_PRIVACY" in msg or "CHAT_WRITE_FORBIDDEN" in msg:
                await status.edit(
                    "❌ Upload to storage channel failed (Pyrogram can't resolve the channel).\n\n"
                    "This is normal when the bot session hasn't 'seen' your private channel yet.\n\n"
                    "To fix: temporarily make the channel PUBLIC or send a message AS the bot inside the channel to register it.\n\n"
                    "✅ EASIEST (temporary):\n"
                    " 1. Make channel public (Settings → Channel Type → Public)\n"
                    " 2. Restart the bot\n"
                    " 3. Send a file again\n"
                    " 4. After it works, you can set the channel back to private.\n\n"
                    "ALTERNATIVE (without making public):\n"
                    " 1. In the channel, use the menu to 'Send as' and choose your bot (this forces Telegram to link the bot to the channel session).\n\n"
                    "After you do one of the above, re-run the file upload.\n"
                )
                # clean local tmp but keep HLS so user can re-run
                try:
                    shutil.rmtree(tmp_dir)
                except Exception:
                    pass
                return
            else:
                # other upload error
                await status.edit(f"❌ Upload to storage channel failed: `{msg}`")
                try:
                    shutil.rmtree(tmp_dir)
                except Exception:
                    pass
                return

        # Step 4: Cleanup local upload file
        try:
            os.remove(file_path)
        except Exception:
            pass

        # Compose final message
        lines = []
        lines.append("**🎬 File Processed Successfully!**\n")
        lines.append(f"📌 **File Name:** `{file_name}`")
        lines.append(f"📦 **File Size:** `{round(file_size / (1024*1024), 2)} MB`")

        if local_stream_url:
            # If app is deployed, user must prepend their app domain
            lines.append("\n🔴 **Local HLS Streaming (served by this app):**")
            # we provide both relative and instruction how to build full link
            lines.append(f"`{local_stream_url}`")
            lines.append(
                "_Full URL example: https://<your-app-domain>_/{path} (replace <your-app-domain> with your Railway domain)_".replace(
                    "{path}", local_stream_url.lstrip("/")
                )
            )
        else:
            lines.append("\n⚠️ HLS not available (ffmpeg missing or conversion failed).")

        if telegram_download_link:
            lines.append("\n🔗 **Telegram Download Link:**")
            lines.append(telegram_download_link)

        lines.append("\n_File saved securely in your storage channel (if upload succeeded)._")
        text = "\n".join(lines)

        await status.edit(text)

    except Exception as e:
        logging.exception("Unhandled error in handler")
        try:
            await status.edit("❌ Unexpected error occurred. Check container logs.")
        except Exception:
            pass


if __name__ == "__main__":
    # Start Flask in background thread and then run Pyrogram app
    import threading

    def run_flask():
        server.run(host="0.0.0.0", port=PORT)

    threading.Thread(target=run_flask, daemon=True).start()
    app.run()