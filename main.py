import os, logging, subprocess, uuid
from pyrogram import Client, filters
from flask import Flask

logging.basicConfig(level=logging.INFO)

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

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
    await msg.reply("Send a *video* to convert into HLS (.m3u8)")

@app.on_message(filters.private & (filters.video | filters.document))
async def convert_hls(client, message):

    status = await message.reply("Processing… 🔄")

    media = message.video or message.document
    file_name = media.file_name or "video.mp4"
    file_size = media.file_size

    os.makedirs("downloads", exist_ok=True)
    os.makedirs("hls", exist_ok=True)

    await status.edit("Downloading… ⬇")

    try:
        download_path = await client.download_media(
            message, file_name=f"downloads/{file_name}"
        )
    except Exception as e:
        return await status.edit(f"❌ Download error:\n`{e}`")

    folder = f"hls/{uuid.uuid4()}"
    os.makedirs(folder, exist_ok=True)

    m3u8_path = f"{folder}/index.m3u8"

    await status.edit("Converting to HLS… 🎞")

    cmd = [
        "ffmpeg",
        "-i", download_path,
        "-codec", "copy",
        "-start_number", "0",
        "-hls_time", "4",
        "-hls_list_size", "0",
        "-f", "hls",
        m3u8_path
    ]

    subprocess.run(cmd)

    await status.edit("Uploading… ☁")

    # IMPORTANT FIX
    CHANNEL = await client.get_chat(CHANNEL_ID)

    # upload m3u8
    uploaded_m3u8 = await client.send_document(CHANNEL.id, m3u8_path)

    # upload segments
    for ts in sorted(os.listdir(folder)):
        if ts.endswith(".ts"):
            await client.send_document(CHANNEL.id, f"{folder}/{ts}")

    # generate CDN link
    file_details = await client.get_messages(CHANNEL.id, uploaded_m3u8.id)
    file_info = await client.get_file(file_details.document.file_id)

    link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"

    return await status.edit(
        f"**HLS Ready!** 🎉\n\n"
        f"📺 Playlist:\n`{link}`"
    )

if __name__ == "__main__":
    import threading
    threading.Thread(target=lambda: server.run(host="0.0.0.0", port=8080)).start()
    app.run()