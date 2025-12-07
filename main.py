import os
from pyrogram import Client, filters
from pyrogram.types import Message

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

# Channel MUST be public username (NOT numeric ID)
# Example: "@myfileschannel"
CHANNEL_USERNAME = os.environ["CHANNEL_USERNAME"]

app = Client(
    "file_to_link_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@app.on_message(filters.command("start"))
async def start(_, message: Message):
    await message.reply(
        "✅ **File To Link Bot**\n\n"
        "📤 Send me any **video or file**\n"
        "🔗 I will give you:\n"
        "• Streaming Link\n"
        "• Download Link\n"
        "• File Name & Size"
    )

@app.on_message(filters.private & (filters.video | filters.document))
async def handle_file(client: Client, message: Message):
    status = await message.reply("⬆️ Uploading file...")

    try:
        sent = await message.copy(CHANNEL_USERNAME)
    except Exception as e:
        await status.edit(f"❌ Upload failed:\n`{e}`")
        return

    file = sent.video or sent.document
    size_mb = round(file.file_size / (1024 * 1024), 2)

    stream_link = sent.link
    file_id = file.file_id
    tg_download = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{(await client.get_file(file_id)).file_path}"

    await status.edit(
        f"✅ **File Uploaded Successfully!**\n\n"
        f"📄 **Name:** `{file.file_name}`\n"
        f"📦 **Size:** `{size_mb} MB`\n\n"
        f"▶️ **Streaming Link:**\n{stream_link}\n\n"
        f"⬇️ **Direct Download:**\n{tg_download}"
    )

app.run()