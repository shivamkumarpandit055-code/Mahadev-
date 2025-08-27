# main.py

import os
import sys
import time
import asyncio
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.handlers import MessageHandler
from pyrogram.errors import FloodWait
import logging

import ug as helper  # आपका ug.py जिसमें डाउनलोडिंग और डीक्रिप्शन की लाजिक है
from vars import *   # आपकी environment variables
from db import db    # आपकी db क्लास/इंस्टेंस
from clean import register_clean_handler
from utils import progress_bar
from apixug import SecureAPIClient

# Initialize variables and client
watermark = "UG"
timeout_duration = 300  # 5 minutes

client = SecureAPIClient()
apis = client.get_apis()

bot = Client(
    "ugx",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=300,
    sleep_threshold=60,
    in_memory=True,
)

# Register your clean command handler
register_clean_handler(bot)

# DRM downloader command implementation
@bot.on_message(filters.command("drm") & filters.create(
    lambda _, __, msg: db.is_user_authorized(msg.from_user.id, bot.me.username) if msg.from_user else False
))
async def drm_handler(bot: Client, message: Message):
    # Authorization check for channel or user
    bot_username = (await bot.get_me()).username
    if message.chat.type == "channel":
        if not db.is_channel_authorized(message.chat.id, bot_username):
            return
    else:
        if not db.is_user_authorized(message.from_user.id, bot_username):
            await message.reply_text("❌ You are not authorized to use this command.")
            return

    await message.reply_text(
        "__Hello! Send me a text file containing lines in the format:\n"
        "Name: URL\n\nExample:\nPhysics Lecture 1: https://example.com/video1\nMath Lecture 2: https://example.com/video2\n__"
    )

    file_msg = await bot.listen(message.chat.id)
    if not file_msg.document:
        await message.reply_text("❌ Please send a valid text file document.")
        return

    input_file_path = await file_msg.download()
    try:
        with open(input_file_path, "r") as f:
            lines = f.readlines()
    except Exception as e:
        await message.reply_text(f"Failed to read file: {str(e)}")
        return
    os.remove(input_file_path)

    entries = []
    for line in lines:
        if ':' in line:
            name, url = line.split(':', 1)
            entries.append((name.strip(), url.strip()))

    if not entries:
        await message.reply_text("❌ No valid entries found in the file.")
        return

    # Request optional DRM token/password
    await message.reply_text("Send DRM token/password for special URLs or /skip to continue without it.")
    try:
        token_msg = await bot.listen(message.chat.id, timeout=60)
        drm_token = token_msg.text if token_msg.text != "/skip" else None
        if token_msg.text:
            await token_msg.delete()
    except asyncio.TimeoutError:
        drm_token = None

    # Request target channel ID or default to current chat
    await message.reply_text("Send target channel ID to upload videos or /skip to upload here.")
    try:
        ch_msg = await bot.listen(message.chat.id, timeout=60)
        if ch_msg.text != "/skip":
            target_channel_id = int(ch_msg.text)
        else:
            target_channel_id = message.chat.id
        if ch_msg.text:
            await ch_msg.delete()
    except Exception:
        target_channel_id = message.chat.id

    success_count = 0
    failed = []

    for idx, (name, url) in enumerate(entries, 1):
        try:
            await message.reply_text(f"Processing {name}...")

            # DRM URL handling
            if "classplus" in url or "drm" in url or "encrypted.m" in url or "drmcdni" in url:
                # Prepare DRM keys or signed URL using your helper and APIs
                keys_string = ""
                if "classplusapp.com/drm" in url:
                    api_url = apis.get("API_DRM", "")
                    if api_url:
                        try:
                            full_api_url = api_url + url
                            mpd, keys = helper.get_mps_and_keys(full_api_url)
                            if mpd and keys:
                                url = mpd
                                keys_string = " ".join([f"--key {k}" for k in keys])
                        except Exception as e:
                            await message.reply_text(f"Failed to fetch DRM keys: {str(e)}")

                # Decrypt and merge DRM video
                show_msg = await message.reply_text(f"Downloading DRM video: {name}")
                downloaded_file = await helper.decrypt_and_merge_video(url, keys_string, "downloads", name)
                await show_msg.delete(True)
                if downloaded_file:
                    await helper.send_vid(bot, message, f"Uploaded: {name}", downloaded_file, None, name, None, target_channel_id, watermark=watermark)
                    success_count += 1
                else:
                    raise Exception("Failed DRM decryption/download")
            else:
                # Normal video download with yt-dlp
                cmd = f'yt-dlp -o "{name}.mp4" "{url}"'
                show_msg = await message.reply_text(f"Downloading video: {name}")
                downloaded_file = await helper.download_video(url, cmd, name)
                await show_msg.delete(True)
                if downloaded_file:
                    await helper.send_vid(bot, message, f"Uploaded: {name}", downloaded_file, None, name, None, target_channel_id, watermark=watermark)
                    success_count += 1
                else:
                    raise Exception("Download failed")

        except Exception as err:
            failed.append((name, str(err)))
            await message.reply_text(f"Failed {name}: {str(err)}")

    summary = f"✅ Successfully processed {success_count} videos."
    if failed:
        summary += "\n⚠️ Failed downloads:\n"
        for fn, err in failed:
            summary += f"- {fn}: {err}\n"

    await message.reply_text(summary)


# Other existing commands and handlers (like /start, /setlog, /getlog, etc.) go here
# ...

# Start the bot
if __name__ == "__main__":
    print("Starting UGDEV DRM Uploader Bot...")
    bot.run()
