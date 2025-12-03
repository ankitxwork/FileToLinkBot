#!/usr/bin/env python3
"""
FileToLinkBot - robust rewrite of main.py

Features:
- Removes old Pyrogram session files at start to avoid stale sessions
- Loads env vars robustly and logs masked debug info
- Verifies bot is admin in target storage channel (or supergroup) at startup
- Forwards files to the configured storage chat and returns:
    - Telegram "t.me/c/..." link (works for supergroups)
    - Optional: HLS (.m3u8) streaming pipeline + upload to Cloudflare R2 if R2_* env vars provided
- Safe error handling and editable progress messages
- Limits (max file size, concurrency) and cleanup
- Helpful debug logs for Railway
Requirements:
- pyrogram, tgcrypto, boto3 (if using R2), aiofiles
- FFmpeg binary available in PATH for HLS conversion (optional)
Environment variables (Railway -> Variables):
- API_ID (int)
- API_HASH (str)
- BOT_TOKEN (str; bot token)
- CHANNEL_ID (int)   -> The storage chat ID (supergroup or private channel). Example: -1003420562724
Optional R2 variables (enable HLS+upload if you fill these):
- R2_BUCKET
- R2_ENDPOINT     (e.g. https://<accountid>.r2.cloudflarestorage.com)
- R2_ACCESS_KEY
- R2_SECRET_KEY
- R2_PUBLIC_URL   (public base URL for served files, e.g. https://pub-xxxxx.r2.dev)
Optional:
- MAX_FILE_SIZE_MB (int) default 300
- HLS_ENABLED (1 to enable processing) default 0

NOTE: If you enable HLS, ensure ffmpeg is present in runtime.
"""

import os
import sys
import shutil
import logging
import asyncio
import tempfile
import uuid
import subprocess
from pathlib import Path
from typing import Optional

# Optional imports
try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
    HAS_BOTO3 = True
except Exception:
    HAS_BOTO3 = False

from pyrogram import Client, filters
from pyrogram.errors import RPCError

# ---------------------------
# Basic setup & session reset
# ---------------------------
# Remove old .session files to avoid stale peer storage problems on Railway after switching channels
for f in ("FileToLinkBot.session", "FileToLinkBot.session-journal"):
    if os.path.exists(f):
        try:
            os.remove(f)
            print(f"DEBUG: Removed old session file: {f}")
        except Exception as e:
            print(f"DEBUG: Could not remove {f}: {e}")

# Configure logging to stdout (Railway shows stdout)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("filetolink")

# ---------------------------
# Load env vars safely
# ---------------------------
def get_env(name: str, required: bool = True, default: Optional[str] = None):
    v = os.environ.get(name, default)
    if required and (v is None):
        log.critical(f"Missing required environment variable: {name}")
        raise SystemExit(1)
    return v

try:
    API_ID = int(get_env("API_ID"))
    API_HASH = get_env("API_HASH")
    BOT_TOKEN = get_env("BOT_TOKEN")
    CHANNEL_ID = int(get_env("CHANNEL_ID"))  # target storage chat (supergroup/channel)
except Exception as e:
    log.critical("Failed loading required environment variables: %s", e)
    raise

# Optional settings
MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", "300"))  # default 300MB
HLS_ENABLED = os.environ.get("HLS_ENABLED", "0") == "1"

# R2 config (optional)
R2_BUCKET = os.environ.get("R2_BUCKET")
R2_ENDPOINT = os.environ.get("R2_ENDPOINT")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY")
R2_SECRET_KEY = os.environ.get("R2_SECRET_KEY")
R2_PUBLIC_URL = os.environ.get("R2_PUBLIC_URL")  # public base URL for constructed links

USE_R2 = all([R2_BUCKET, R2_ENDPOINT, R2_ACCESS_KEY, R2_SECRET_KEY, R2_PUBLIC_URL]) and HAS_BOTO3

if HLS_ENABLED and not shutil.which("ffmpeg"):
    log.warning("HLS_ENABLED is true but ffmpeg binary not found in PATH. HLS will be disabled.")
    HLS_ENABLED = False

if HLS_ENABLED and not USE_R2:
    log.warning("HLS_ENABLED true but R2 credentials not fully provided or boto3 missing. HLS will be disabled.")
    HLS_ENABLED = False

log.info("DEBUG: API_ID loaded: %s", API_ID)
log.info("DEBUG: API_HASH loaded")
log.info("DEBUG: BOT_TOKEN loaded: %s...", BOT_TOKEN[:10])
log.info("DEBUG: CHANNEL_ID loaded: %s", CHANNEL_ID)
log.info("HLS_ENABLED=%s, USE_R2=%s, MAX_FILE_SIZE_MB=%s", HLS_ENABLED, USE_R2, MAX_FILE_SIZE_MB)

# Instantiate Pyrogram client
app = Client(
    "FileToLinkBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir="."
)

# R2 S3 client (if enabled)
s3_client = None
if USE_R2:
    try:
        s3_client = boto3.client(
            "s3",
            region_name="auto",
            endpoint_url=R2_ENDPOINT,
            aws_access_key_id=R2_ACCESS_KEY,
            aws_secret_access_key=R2_SECRET_KEY,
        )
        log.info("DEBUG: R2 client initialized")
    except Exception as e:
        log.exception("Failed to init R2 client: %s", e)
        s3_client = None
        USE_R2 = False

# Concurrency lock to avoid multiple heavy conversions at once
hls_lock = asyncio.Lock()

# ---------------------------
# Utility functions
# ---------------------------
def make_tme_c_link(chat_id: int, message_id: int) -> str:
    """
    Turn a Telegram internal chat id (-100xxxxxxxx) into the t.me/c/<id_without_-100>/<msgid> format.
    Works for private supergroups.
    """
    s = str(chat_id)
    if s.startswith("-100"):
        return f"https://t.me/c/{s[4:]}/{message_id}"
    # fallback, for non -100 ids, return a tg:// or https://t.me/username link is not possible here
    return f"https://t.me/c/{s}/{message_id}"

async def verify_bot_admin_in_chat(client: Client, chat_id: int) -> bool:
    """
    Ensure the bot is present and has admin rights in the target chat.
    Return True if admin/creator, else False.
    """
    try:
        me = await client.get_me()
        member = await client.get_chat_member(chat_id, me.id)
        status = member.status  # "creator", "administrator", "member", etc.
        log.info("DEBUG: Bot membership status in %s = %s", chat_id, status)
        return status in ("administrator", "creator")
    except RPCError as e:
        log.warning("Could not verify bot admin status: %s", e)
        return False
    except Exception as e:
        log.exception("Unexpected error during admin verification: %s", e)
        return False

def human_size(bytesize: int) -> str:
    for unit in ["B","KB","MB","GB"]:
        if bytesize < 1024:
            return f"{bytesize:.2f}{unit}"
        bytesize /= 1024
    return f"{bytesize:.2f}TB"

# ---------------------------
# HLS conversion and R2 upload
# ---------------------------
async def convert_to_hls_and_upload(local_path: str, filename_prefix: str) -> Optional[str]:
    """
    Convert input video into HLS (index.m3u8 + segments) in a temp folder,
    upload to R2 under prefix filename_prefix/, and return the public index.m3u8 url.
    Requires ffmpeg and USE_R2 = True.
    """
    if not HLS_ENABLED or not USE_R2 or s3_client is None:
        return None

    tmpdir = tempfile.mkdtemp(prefix="hls_")
    log.info("DEBUG: HLS temp dir: %s", tmpdir)
    # output pattern and index
    out_index = os.path.join(tmpdir, "index.m3u8")
    segment_pattern = os.path.join(tmpdir, "seg%03d.ts")

    # Build ffmpeg command (re-encode to H.264/AAC for broad compatibility)
    # Adjust quality parameters as needed
    cmd = [
        "ffmpeg", "-y", "-i", local_path,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-vf", "scale=-2:720",
        "-hls_time", "6",
        "-hls_playlist_type", "vod",
        "-hls_segment_filename", segment_pattern,
        out_index
    ]

    log.info("DEBUG: Running ffmpeg for HLS (may take time)...")
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            log.error("FFmpeg failed. rc=%s stderr=%s", proc.returncode, stderr.decode(errors="ignore"))
            shutil.rmtree(tmpdir, ignore_errors=True)
            return None
        log.info("DEBUG: FFmpeg finished, upload to R2 starting...")
    except Exception as e:
        log.exception("FFmpeg execution failed: %s", e)
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None

    # Upload files to R2 under prefix
    prefix = filename_prefix.strip("/")

    try:
        # upload all files in tmpdir
        for p in Path(tmpdir).iterdir():
            if p.is_file():
                key = f"{prefix}/{p.name}"
                log.info("DEBUG: Uploading %s -> s3://%s/%s", p.name, R2_BUCKET, key)
                s3_client.upload_file(str(p), R2_BUCKET, key)
        # Construct public URL
        public_url = f"{R2_PUBLIC_URL.rstrip('/')}/{prefix}/index.m3u8"
        log.info("DEBUG: File uploaded. Public URL: %s", public_url)
        return public_url
    except (BotoCoreError, ClientError) as e:
        log.exception("R2 upload failed: %s", e)
        return None
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

# ---------------------------
# Message handler
# ---------------------------
@app.on_message(filters.private & (filters.video | filters.document))
async def handle_media(client: Client, message):
    """
    Main handler: forwards the incoming media to storage chat, builds t.me link,
    optionally converts to HLS and uploads to R2 and replies final streaming link.
    """
    # Basic info
    uid = message.from_user.id if message.from_user else None
    log.info("Incoming media from user=%s message_id=%s", uid, message.message_id)

    processing = await message.reply("🔄 Uploading to secure storage…")
    try:
        # Quick size check (if available)
        size = None
        if message.document:
            size = message.document.file_size
        elif message.video:
            size = message.video.file_size
        if size:
            size_mb = size / (1024*1024)
            if size_mb > MAX_FILE_SIZE_MB:
                await processing.edit(f"❌ File is too large ({size_mb:.1f}MB). Max allowed is {MAX_FILE_SIZE_MB}MB.")
                return

        # Try forwarding to storage chat
        try:
            uploaded = await message.forward(int(CHANNEL_ID))
        except Exception as e:
            # Provide a helpful error message
            log.exception("Forward failed: %s", e)
            await processing.edit(f"❌ Forward failed: `{str(e)}`\nMake sure the bot is admin in the storage channel and CHANNEL_ID is correct.")
            return

        # Build telegram link
        chat_id = uploaded.chat.id
        msg_id = uploaded.id
        tg_link = make_tme_c_link(chat_id, msg_id)

        # Start preparing reply text
        reply_text = f"🎬 **Streaming Link (Telegram):**\n`{tg_link}`\n"

        # If HLS + R2 enabled and media is video/document, attempt to download + process
        final_hls_url = None
        if HLS_ENABLED and USE_R2:
            # Acquire lock so only one HLS job runs at a time (optional)
            async with hls_lock:
                # Download forwarded media locally
                tmpdir = tempfile.mkdtemp(prefix="dl_")
                try:
                    local_path = await client.download_media(uploaded, file_name=os.path.join(tmpdir, "input"))
                    log.info("DEBUG: downloaded forwarded file to %s", local_path)
                    # Unique prefix on R2 to avoid collisions
                    prefix = f"{uuid.uuid4().hex}"
                    final_hls_url = await convert_to_hls_and_upload(local_path, prefix)
                    if final_hls_url:
                        reply_text = f"🎬 **Streaming Link (.m3u8):**\n{final_hls_url}\n\n(Original Telegram link below)\n`{tg_link}`"
                    else:
                        reply_text += "\n⚠️ HLS conversion/upload failed — delivered Telegram link instead."
                except Exception as e:
                    log.exception("Download/convert/upload error: %s", e)
                    reply_text += f"\n⚠️ HLS pipeline failed: `{e}`"
                finally:
                    shutil.rmtree(tmpdir, ignore_errors=True)

        # Edit processing message with final link
        await processing.edit(reply_text)
        log.info("Replied to user %s with link(s).", uid)
    except Exception as e:
        log.exception("Unhandled error in handler: %s", e)
        try:
            await processing.edit(f"❌ Unexpected error: `{e}`")
        except Exception:
            pass

# ---------------------------
# Startup checks
# ---------------------------
@app.on_message(filters.command(["start", "help"]) & filters.private)
async def start_cmd(client, message):
    await message.reply("👋 Send me any video or file in private chat and I'll create a streaming link for you.")

# Run verification on startup
async def on_startup(client: Client):
    log.info("DEBUG: Running startup checks...")
    ok = await verify_bot_admin_in_chat(client, CHANNEL_ID)
    if not ok:
        log.critical("Bot is NOT admin in CHANNEL_ID=%s. Please add the bot as an administrator in the storage channel.", CHANNEL_ID)
        # We keep running but future forwards will fail; better to stop to avoid user confusion.
        # If you prefer to crash here uncomment the next line:
        # raise SystemExit("Bot must be admin in storage channel.")
    else:
        log.info("Bot is admin in storage chat. Good to go.")

# Hook startup
@app.on_connect()
def _on_connect(client: Client, *args, **kwargs):
    # on_connect is sync; schedule the async startup check
    asyncio.get_event_loop().create_task(on_startup(client))

# ---------------------------
# Start app
# ---------------------------
if __name__ == "__main__":
    log.info("DEBUG: Starting bot (app.run())")
    app.run()