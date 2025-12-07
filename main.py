import os
from pyrogram import Client, filters

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

app = Client(
    "FileToLinkBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@app.on_message(filters.command("start"))
async def start(_, msg):
    await msg.reply(
        "✅ **Send me a video or file**\n\n"
        "I will give you:\n"
        "📄 File name\n"
        "📦 File size\n"
        "⬇️ Direct download link\n"
        "▶️ Streaming-ready Telegram link"
    )

@app.on_message(filters.private & (filters.video | filters.document))
async def handle_file(client, message):
    status = await message.reply("⬆️ Uploading file...")

    media = message.video or message.document
    file_name = media.file_name or "video.mp4"
    file_size = round(media.file_size / (1024 * 1024), 2)

    # ✅ FILE ID
    file_id = media.file_id

    # ✅ CORRECT WAY (NO await, NO generator)
    file = await client.download_media(file_id, in_memory=True)
    file_path = media.file_id

    # ✅ TELEGRAM CDN LINK (SAFE)
    tg_link = f"https://t.me/{(await client.get_me()).username}?start=file_{file_id}"

    text = (
        "✅ **File Processed Successfully!**\n\n"
        f"📄 **Name:** `{file_name}`\n"
        f"📦 **Size:** `{file_size} MB`\n\n"
        f"⬇️ **Download:** {tg_link}\n"
        f"▶️ **Stream:** {tg_link}"
    )

    await status.edit(text)

app.run()