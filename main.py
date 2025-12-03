#!/usr/bin/env python3
import os
import sys
import shutil
import logging
import asyncio
import tempfile
import uuid
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.errors import RPCError

# ---------------------------
# Remove stale session
# ---------------------------
for f in ("FileToLinkBot.session", "FileToLinkBot.session-journal"):
    if os.path.exists(f):
        try:
            os.remove(f)
            print(f"DEBUG: Removed old session {f}")
        except:
            pass

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
# Helpers
# ---------------------------
def tme_c_link(chat_id, msg_id):
    s = str(chat_id)
    if s.startswith("-100"):
        return f"https://t.me/c/{s[4:]}/{msg_id}"
    return f"https://t.me/c/{s}/{msg_id}"

async def check_admin(client: Client, chat_id: int):
    try:
        me = await client.get_me()
        m = await client.get_chat_member(chat_id, me.id)
        return m.status in ("administrator", "creator")
    except:
        return False

# ---------------------------
# Startup event (Correct for Pyrogram v2)
# ---------------------------
@app.on_start()
async def startup(client):
    log.info("DEBUG: Running startup checks...")
    ok = await check_admin(client, CHANNEL_ID)
    if not ok:
        log.error("❌ Bot is NOT admin in CHANNEL_ID. Forwarding will fail.")
    else:
        log.info("✅ Bot is admin in storage chat.")

# ---------------------------
# Start/help
# ---------------------------
@app.on_message(filters.private & filters.command(["start", "help"]))
async def start(client, message):
    await message.reply("Send me any video/file and I'll create a streaming link!")

# ---------------------------
# File Forward Handler
# ---------------------------
@app.on_message(filters.private & (filters.video | filters.document))
async def handle_media(client: Client, message):
    log.info("Incoming media from %s", message.from_user.id)

    status = await message.reply("🔄 Uploading to secure storage…")

    try:
        forwarded = await message.forward(CHANNEL_ID)
    except Exception as e:
        await status.edit(f"❌ Forward failed: `{e}`")
        return

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