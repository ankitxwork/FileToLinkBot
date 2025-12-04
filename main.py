@app.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_file(client, message):

    status = await message.reply("Saving securely… 📦")

    media = message.document or message.video or message.audio

    try:
        file_path = await client.download_media(message)
    except Exception as e:
        return await status.edit(f"❌ Download failed:\n`{e}`")

    try:
        uploaded = await client.send_document(
            chat_id=CHANNEL_ID,
            document=file_path,
            caption=media.file_name or "file"
        )
    except Exception as e:
        return await status.edit(f"❌ Upload failed:\n`{e}`")

    try:
        f = await client.get_messages(CHANNEL_ID, uploaded.id)
        file_info = await client.get_file(f.document.file_id)
        cdn_path = file_info.file_path
    except Exception as e:
        return await status.edit(f"❌ CDN Error:\n`{e}`")

    download_link = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{cdn_path}"

    await status.edit(
        f"**🎉 File Ready!**\n\n"
        f"**Download:** {download_link}"
    )