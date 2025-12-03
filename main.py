import os

print("DEBUG: Starting bot...")

API_ID = int(os.environ["API_ID"])
print("DEBUG: API_ID loaded:", API_ID)

API_HASH = os.environ["API_HASH"]
print("DEBUG: API_HASH loaded")

BOT_TOKEN = os.environ["BOT_TOKEN"]
print("DEBUG: BOT_TOKEN loaded:", BOT_TOKEN[:10], "...")

CHANNEL_ID = int(os.environ["CHANNEL_ID"])
print("DEBUG: CHANNEL_ID loaded:", CHANNEL_ID)

from pyrogram import Client, filters

app = Client(
    "FileToLinkBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

@app.on_message(filters.private & (filters.video | filters.document))
async def handle_media(client, message):

    processing = await message.reply("🔄 Uploading to secure storage…")

    # Forward file to private channel
    uploaded = await message.forward(int(CHANNEL_ID))

    # Correct chat and message ID extraction
    chat_id = uploaded.chat.id
    msg_id = uploaded.id

    # Convert chat_id -> t.me/c link format
    link = f"https://t.me/c/{str(chat_id)[4:]}/{msg_id}"

    await processing.edit(
        f"🎬 **Streaming Link:**\n`{link}`\n\nSaved securely in storage 📦"
    )

@app.on_message(filters.command(["start", "help"]))
async def start(client, message):
    await message.reply(
        "👋 **Welcome to FileToLink Bot!**\n\n"
        "Send any *file or video* and I’ll generate a **streaming link** for you."
    )

print("DEBUG: Running app...")
app.run()