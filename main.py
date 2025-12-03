#!/usr/bin/env python3
import os
import sys
import logging

from pyrogram import Client, filters

# ---------------------------
# Logging
# ---------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("bot")

# ---------------------------
# ENV VARS
# ---------------------------
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))

log.info("DEBUG: API_ID loaded: %s", API_ID)
log.info("DEBUG: API_HASH loaded")
log.info("DEBUG: BOT_TOKEN loaded: %s...", BOT_TOKEN[:10])
log.info("DEBUG: CHANNEL_ID loaded: %s", CHANNEL_ID)

# ---------------------------
# Client
# ---------------------------
app = Client(
    "FileToLinkBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ---------------------------
# HELPER
# ---------------------------
def tme_c_link(chat_id, msg_id):
    s = str(chat_id)
    if s.startswith("-100"):
        return f"https://t.me/c/{s[4:]}/{msg_id}"
    return f"https://t.me/c/{s}/{msg_id}"

# ---------------------------
# Commands
# ---------------------------
@app.on_message(filters.private & filters.command(["start", "help"]))
async def start(_, message):
    await message.reply("Send me any video/file and I will create a streaming link!")

# ---------------------------
# File Handler
# ---------------------------
@app.on_message(filters.private & (filters.video | filters.document))
async def handle_media(client, message):
    status = await message.reply("🔄 Uploading to secure storage…")

    try:
        forwarded = await message.forward(CHANNEL_ID)
    except Exception as e:
        return await status.edit(f"❌ Forward failed:\n`{e}`")

    link = tme_c_link(forwarded.chat.id, forwarded.id)

    await status.edit(
        f"🎬 **Streaming Link:**\n`{link}`\n\nSaved securely in storage 📦"
    )

# ---------------------------
# Run bot
# ---------------------------
if __name__ == "__main__":
    log.info("DEBUG: Starting bot...")
    app.run()