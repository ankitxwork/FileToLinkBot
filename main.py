import os
print("DEBUG: Starting bot...")

try:
    API_ID = int(os.environ["API_ID"])
    print("DEBUG: API_ID loaded:", API_ID)
except Exception as e:
    print("ERROR loading API_ID:", e)
    raise

try:
    API_HASH = os.environ["API_HASH"]
    print("DEBUG: API_HASH loaded")
except Exception as e:
    print("ERROR loading API_HASH:", e)
    raise

try:
    BOT_TOKEN = os.environ["BOT_TOKEN"]
    print("DEBUG: BOT_TOKEN loaded:", BOT_TOKEN[:10], "...")
except Exception as e:
    print("ERROR loading BOT_TOKEN:", e)
    raise

try:
    CHANNEL_ID = os.environ["CHANNEL_ID"]
    print("DEBUG: CHANNEL_ID loaded:", CHANNEL_ID)
except Exception as e:
    print("ERROR loading CHANNEL_ID:", e)
    raise

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
    uploaded = await message.forward(int(CHANNEL_ID))
    clean_id = CHANNEL_ID.replace("-100", "")
    link = f"https://t.me/c/{clean_id}/{uploaded.id}"
    await processing.edit(f"🎬 Streaming Link:\n`{link}`")

@app.on_message(filters.command(["start", "help"]))
async def start(client, message):
    await message.reply("Send any file to get a streaming link.")

print("DEBUG: Running app...")
app.run()