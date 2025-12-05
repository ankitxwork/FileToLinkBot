# main.py
import os
import logging
import tempfile
import uuid
import subprocess
from pyrogram import Client, filters
from pyrogram.errors import RPCError
from flask import Flask

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- ENV ---
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])  # -100XXXXXXXXX

# --- PYROGRAM CLIENT ---
# use a file-backed session (not in_memory) so pyrogram persists some state while the container runs
app = Client("hlsbot_session", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- FLASK (health) ---
server = Flask(__name__)
@server.route("/")
def home():
    return "HLS Bot Running"

# --- HELPERS ---
async def ensure_channel_and_admin(client, chat_id):
    """Ensure the channel exists and the bot is an admin there."""
    try:
        chat = await client.get_chat(chat_id)
    except RPCError as e:
        return False, f"Cannot access channel: {e}"
    try:
        me = await client.get_chat_member(chat_id, "me")
        if me.status not in ("administrator", "creator"):
            return False, "Bot is not an admin in the channel. Give the bot admin rights (post messages + add media)."
    except RPCError:
        # On some accounts get_chat_member may not be available, ignore
        pass
    return True, chat

def ffmpeg_to_hls(input_path, out_dir, segment_time=4):
    """Run ffmpeg to create HLS with .m3u8 and .ts segments in out_dir."""
    os.makedirs(out_dir, exist_ok=True)
    seg_pattern = os.path.join(out_dir, "segment%03d.ts")
    m3u8_path = os.path.join(out_dir, "index.m3u8")

    cmd = [
        "ffmpeg",
        "-y",              # overwrite
        "-i", input_path,
        "-c", "copy",      # copy codecs (fast). If fails, remove "-c copy" to re-encode
        "-start_number", "0",
        "-hls_time", str(segment_time),
        "-hls_list_size", "0",
        "-hls_segment_filename", seg_pattern,
        "-f", "hls",
        m3u8_path
    ]

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    success = proc.returncode == 0
    return success, proc.stdout.decode(errors="ignore") + proc.stderr.decode(errors="ignore"), m3u8_path

# --- COMMANDS ---
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    await message.reply_text(
        "**Send any VIDEO (or file) — I'll convert to HLS (.m3u8) and upload to your private storage channel.**\n\n"
        "• Make sure the bot is added to the channel and granted admin rights (Post messages + add media)."
    )

# Accept video or document (video file)
@app.on_message(filters.private & (filters.video | filters.document))
async def handle_convert(client, message):
    status = await message.reply_text("Processing… 🔄")

    # Validate channel / permissions first
    ok, info = await ensure_channel_and_admin(client, CHANNEL_ID)
    if not ok:
        await status.edit(f"❌ Channel issue: {info}")
        return

    media = message.video or message.document
    file_name = getattr(media, "file_name", None) or f"file_{uuid.uuid4().hex}.mp4"
    file_size = getattr(media, "file_size", 0)

    # size check (optional, adjust if you want)
    max_mb = 500  # safety limit
    if file_size and (file_size / (1024*1024) > max_mb):
        await status.edit(f"❌ File too large (> {max_mb} MB). Please send a smaller file.")
        return

    # 1) download to a temporary directory
    await status.edit("Downloading… ⬇️")
    try:
        tmpdir = tempfile.TemporaryDirectory()
        dl_path = await client.download_media(message, file_name=os.path.join(tmpdir.name, file_name))
    except Exception as e:
        tmpdir.cleanup()
        await status.edit(f"❌ Download failed: {e}")
        return

    # 2) convert to HLS inside temporary dir
    await status.edit("Converting to HLS… 🎞️")
    out_folder = os.path.join(tmpdir.name, "hls_out")
    success, ff_out, m3u8_path = ffmpeg_to_hls(dl_path, out_folder, segment_time=4)
    if not success:
        # try a fallback re-encode (slower) if copy failed
        await status.edit("Conversion with codec copy failed — trying a re-encode fallback (slower)… 🔁")
        cmd = [
            "ffmpeg", "-y", "-i", dl_path,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
            "-c:a", "aac", "-b:a", "128k",
            "-start_number", "0",
            "-hls_time", "4",
            "-hls_list_size", "0",
            "-hls_segment_filename", os.path.join(out_folder, "segment%03d.ts"),
            "-f", "hls", m3u8_path
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        success = proc.returncode == 0
        ff_out += "\nFALLBACK:\n" + proc.stdout.decode(errors="ignore") + proc.stderr.decode(errors="ignore")

    if not success:
        tmpdir.cleanup()
        await status.edit(f"❌ HLS conversion failed.\n\nffmpeg output:\n```\n{ff_out[:1000]}\n```")
        return

    # 3) Upload playlist first, then segments
    await status.edit("Uploading HLS playlist… ☁️")
    try:
        # upload m3u8
        sent_m3u8 = await client.send_document(CHANNEL_ID, m3u8_path, caption=f"HLS: {file_name}")
    except Exception as e:
        tmpdir.cleanup()
        await status.edit(f"❌ Upload playlist failed: {e}")
        return

    # upload segments
    await status.edit("Uploading segments (.ts)… This may take a moment depending on number of chunks.")
    ts_count = 0
    uploaded_segments = []
    for fname in sorted(os.listdir(out_folder)):
        if fname.endswith(".ts"):
            ts_count += 1
            local_ts = os.path.join(out_folder, fname)
            try:
                msg = await client.send_document(CHANNEL_ID, local_ts)
                uploaded_segments.append(msg)
            except Exception as e:
                # continue uploading others but log error
                logging.exception("Failed uploading segment %s: %s", local_ts, e)

    # 4) generate CDN link for playlist
    try:
        # fetch the message we just sent to get its document.file_id and file_path
        m = await client.get_messages(CHANNEL_ID, sent_m3u8.id)
        file_info = await client.get_file(m.document.file_id)
        file_path = file_info.file_path  # remote path on telegram CDN
        cdn_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    except Exception as e:
        tmpdir.cleanup()
        await status.edit(f"⚠️ Uploaded but failed to get CDN link: {e}")
        return

    # cleanup local files
    try:
        tmpdir.cleanup()
    except:
        pass

    # 5) final result
    text = (
        "**HLS Conversion Complete! 🚀**\n\n"
        f"🎥 **Original:** `{file_name}`\n"
        f"📦 **Size:** `{round((file_size or 0) / (1024*1024), 2)} MB`\n\n"
        f"📺 **Playlist (.m3u8):**\n{cdn_link}\n\n"
        f"🔢 **Segments uploaded:** {ts_count}\n\n"
        "_Play the playlist URL with any HLS player (VLC, Video.js, ExoPlayer)._"
    )

    await status.edit(text)

# --- RUN ---
if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))).start()
    app.run()