from pyrogram import Client, filters
import os

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])  # Your private channel ID

app = Client(
    "FileToLinkBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@app.on_message(filters.private & (filters.video | filters.document))
async def handle_media(client, message):

    processing = await message.reply("🔄 Uploading to secure storage…")

    # Forward file to your private channel
    uploaded = await message.forward(CHANNEL_ID)

    # Convert channel ID to t.me/c format
    link = f"https://t.me/c/{str(CHANNEL_ID)[4:]}/{uploaded.id}"

    # Reply with streaming link
    await processing.edit(
        f"🎬 **Your Streaming Link is Ready:**\n\n"
        f"🔗 `{link}`\n\n"
        "File saved in private channel safely ✔"
    )


@app.on_message(filters.command(["start", "help"]))
async def start(client, message):
    await message.reply(
        "👋 **Welcome to FileToLink Bot!**\n\n"
        "Send me any video or file and I will generate a 📺 streaming link for you."
    )

app.run()
