# main.py (replace your current file with this)
import os
import logging
import subprocess
import uuid
import shutil
import requests
from pyrogram import Client, filters
from flask import Flask

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# --- ENV ---
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
# You may use -1001234567890 (int) or a @username (string). See notes below.
CHANNEL_ID = os.environ.get("CHANNEL_ID")  # keep as string; we'll try to use int if possible

# --- CLIENT ---
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

# Helper to get a numeric chat id when user provided integer string
def parse_channel_id(raw):
    if raw is None:
        return None
    try:
        return int(raw)
    except:
        return raw  # likely a @username string

def bot_api_get_file_path(file_id: str):
    """Use Bot HTTP API to call getFile and return file_path (or raise)."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile"
    resp = requests.get(url, params={"file_id": file_id}, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Bot API getFile failed: {data}")
    return data["result"]["file_path"]

def cleanup_paths(*paths):
    for p in paths:
        try:
            if os.path.isdir(p):
                shutil.rmtree(p)
            elif os.path.exists(p):
                os.remove(p)
        except Exception:
            pass

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
    file_name = getattr(media, "file_name", None) or "video.mp4"
    file_size = getattr(media, "file_size", 0)

    # ensure folders
    os.makedirs("downloads", exist_ok=True)
    output_id = str(uuid.uuid4())
    out_folder = f"hls_{output_id}"
    os.makedirs(out_folder, exist_ok=True)
    m3u8_file = os.path.join(out_folder, "index.m3u8")

    # Download
    await status.edit("Downloading… ⬇")
    try:
        download_path = await client.download_media(message, file_name=os.path.join("downloads", file_name))
        if not download_path or not os.path.exists(download_path):
            raise RuntimeError("download returned no file")
    except Exception as e:
        await status.edit(f"❌ Error downloading file:\n`{e}`")
        cleanup_paths(out_folder)
        return

    # Convert to HLS
    await status.edit("Converting to HLS… 🎞")
    cmd = [
        "ffmpeg",
        "-y",
        "-i", download_path,
        "-codec", "copy",
        "-start_number", "0",
        "-hls_time", "4",
        "-hls_list_size", "0",
        "-f", "hls",
        m3u8_file
    ]
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
        if p.returncode != 0:
            raise RuntimeError(f"ffmpeg failed (rc={p.returncode}): {p.stderr[:1000]}")
    except Exception as e:
        await status.edit(f"❌ FFmpeg conversion failed:\n`{e}`")
        cleanup_paths(download_path, out_folder)
        return

    # Upload to channel
    await status.edit("Uploading HLS files to channel… ☁")

    chat = parse_channel_id(CHANNEL_ID)
    # first upload index.m3u8
    try:
        uploaded_m3u8 = await client.send_document(chat, m3u8_file, caption=f"HLS Playlist for {file_name}")
    except Exception as e:
        # Give actionable message if peer invalid
        err_text = str(e)
        if "Peer id invalid" in err_text or "ID not found" in err_text or "ChannelPrivate" in err_text:
            await status.edit(
                "❌ Error: Cannot send to the channel with the given CHANNEL_ID.\n\n"
                "Make sure:\n"
                "• the bot is **added as an admin** in the channel (Post messages right enabled),\n"
                "• if the channel is **private**, you added the bot as an admin directly (not via forwarding),\n"
                "• CHANNEL_ID is set correctly (use `-1001234567890` or `@channelusername`).\n\n"
                f"Detailed error: `{err_text}`"
            )
        else:
            await status.edit(f"❌ Error uploading index.m3u8:\n`{err_text}`")
        cleanup_paths(download_path, out_folder)
        return

    # then upload TS segments
    try:
        for ts_file in sorted(os.listdir(out_folder)):
            if ts_file.endswith(".ts"):
                ts_path = os.path.join(out_folder, ts_file)
                await client.send_document(chat, ts_path)
    except Exception as e:
        await status.edit(f"❌ Error uploading segments:\n`{e}`")
        # continue to try to give playlist link anyway

    # Build download link using Bot API getFile (avoids awaiting async generator)
    try:
        file_id = uploaded_m3u8.document.file_id
        file_path = bot_api_get_file_path(file_id)
        download_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    except Exception as e:
        download_link = None
        dl_err = str(e)

    # Final message
    res_lines = [
        "**HLS Conversion Complete! 🚀**",
        "",
        f"🎥 **Original File:** `{file_name}`",
        f"📦 **Size:** `{round(file_size / (1024*1024), 2)} MB`",
        ""
    ]
    if download_link:
        res_lines += ["📺 **HLS Playlist (.m3u8):**", f"`{download_link}`"]
    else:
        res_lines += ["⚠ Could not generate direct download via Bot API.", f"`{dl_err}`"]

    await status.edit("\n".join(res_lines))

    # cleanup
    cleanup_paths(download_path)
    # keep uploaded files in channel; remove local hls folder
    cleanup_paths(out_folder)


if __name__ == "__main__":
    import threading
    # start a small health server for Railway
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))).start()
    app.run()