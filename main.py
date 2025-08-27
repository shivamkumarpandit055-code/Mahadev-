import os
import re
import sys
import time
import json
import asyncio
import aiohttp
import aiofiles
import requests
import cloudscraper
import yt_dlp
import ffmpeg
import m3u8
import tgcrypto
import subprocess
from datetime import datetime, timedelta
from urllib.parse import urljoin

from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait

from vars import *
from utils import progress_bar
import auth
import ug as helper
from ug import *
from apixug import SecureAPIClient
from clean import register_clean_handler
from db import db

# Initialize Secure API client and APIs dictionary
client = SecureAPIClient()
apis = client.get_apis()

# Global default values
watermark = "UG"
timeout_duration = 300  # seconds
count = 0

# Initialize Telegram bot client
bot = Client(
    "ugx",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=300,
    sleep_threshold=60,
    in_memory=True,
)

register_clean_handler(bot)  # Registers the /clean command handler

# Inline Keyboards
BUTTONSCONTACT = InlineKeyboardMarkup([[InlineKeyboardButton(text="📞 Contact", url="https://t.me/ItsUGxBot")]])
HELP_KEYBOARD = InlineKeyboardMarkup([[InlineKeyboardButton(text="🛠️ Help", url="https://t.me/ItsUGBot")]])

# /setlog command to set the log channel
@bot.on_message(filters.command("setlog") & filters.private)
async def set_log_channel_cmd(client: Client, message: Message):
    if not db.is_admin(message.from_user.id):
        await message.reply_text("⚠️ You are not authorized to use this command.")
        return
    args = message.text.strip().split()
    if len(args) != 2:
        await message.reply_text("❌ Invalid format!\nUse: /setlog channel_id\nExample: /setlog -100123456789")
        return
    try:
        channel_id = int(args[1])
    except ValueError:
        await message.reply_text("❌ Invalid channel ID. Please provide a valid number.")
        return
    if db.set_log_channel(client.me.username, channel_id):
        await message.reply_text(f"✅ Log channel set successfully!\nChannel ID: {channel_id}")
    else:
        await message.reply_text("❌ Failed to set log channel. Please try again.")

# /getlog command to get current log channel info
@bot.on_message(filters.command("getlog") & filters.private)
async def get_log_channel_cmd(client: Client, message: Message):
    if not db.is_admin(message.from_user.id):
        await message.reply_text("⚠️ You are not authorized to use this command.")
        return
    channel_id = db.get_log_channel(client.me.username)
    if channel_id:
        try:
            channel = await client.get_chat(channel_id)
            info = f"📢 Channel Name: {channel.title}\n"
        except Exception:
            info = ""
        await message.reply_text(
            f"**📋 Log Channel Info**\n\n🤖 Bot: @{client.me.username}\n{info}🆔 Channel ID: `{channel_id}`\n\nUse /setlog to change the log channel."
        )
    else:
        await message.reply_text(
            f"**📋 Log Channel Info**\n\n🤖 Bot: @{client.me.username}\n❌ No log channel set\n\nUse /setlog to set a log channel."
        )

# /cookies command for uploading cookies file
@bot.on_message(filters.command("cookies") & filters.private)
async def cookies_handler(client: Client, message: Message):
    await message.reply_text("Please upload the cookies file (.txt format).", quote=True)
    try:
        input_message = await client.listen(message.chat.id)
        if not input_message.document or not input_message.document.file_name.endswith(".txt"):
            await message.reply_text("Invalid file type. Please upload a .txt file.")
            return
        downloaded_path = await input_message.download()
        async with aiofiles.open(downloaded_path, "r") as f:
            cookies_content = await f.read()
        cookies_file_path = os.getenv("cookies_file_path", "youtube_cookies.txt")
        async with aiofiles.open(cookies_file_path, "w") as f:
            await f.write(cookies_content)
        await input_message.reply_text("✅ Cookies updated successfully and saved.")
    except Exception as e:
        await message.reply_text(f"⚠️ An error occurred: {str(e)}")

# /getcookies command to send cookies file to user
@bot.on_message(filters.command("getcookies") & filters.private)
async def getcookies_handler(client: Client, message: Message):
    try:
        cookies_file_path = os.getenv("cookies_file_path", "youtube_cookies.txt")
        await client.send_document(chat_id=message.chat.id, document=cookies_file_path, caption="Here is the `youtube_cookies.txt` file.")
    except Exception as e:
        await message.reply_text(f"⚠️ An error occurred: {str(e)}")

# /t2t command: text to text file converter
@bot.on_message(filters.command("t2t") & filters.private)
async def text_to_txt(client: Client, message: Message):
    editable = await message.reply_text("Welcome to Text to .txt Converter! Send the text you want to convert.")
    input_message = await bot.listen(message.chat.id)
    if not input_message.text:
        await message.reply_text("**Send valid text data**")
        return
    text_data = input_message.text.strip()
    await input_message.delete()
    await editable.edit("**🔄 Send file name or send /d for default filename**")
    inputn = await bot.listen(message.chat.id)
    raw_textn = inputn.text
    await inputn.delete()
    await editable.delete()
    custom_file_name = "txt_file" if raw_textn == "/d" else raw_textn
    txt_file = os.path.join("downloads", f"{custom_file_name}.txt")
    os.makedirs(os.path.dirname(txt_file), exist_ok=True)
    async with aiofiles.open(txt_file, "w") as f:
        await f.write(text_data)
    await message.reply_document(document=txt_file, caption=f"`{custom_file_name}.txt`\n\nYou can now download your content! 📥")
    os.remove(txt_file)

# /stop command to restart bot
@bot.on_message(filters.command("stop"))
async def restart_handler(client: Client, message: Message):
    await message.reply_text("🚦**STOPPED**", True)
    os.execl(sys.executable, sys.executable, *sys.argv)

# /start command: welcome message and authorization check
@bot.on_message(filters.command("start") & (filters.private | filters.channel))
async def start(bot: Client, message: Message):
    try:
        if message.chat.type == "channel":
            if not db.is_channel_authorized(message.chat.id, bot.me.username):
                return
            await message.reply_text(
                "**✨ Bot is active in this channel**\n\n"
                "**Available Commands:**\n"
                "• /drm - Download DRM videos\n"
                "• /plan - View channel subscription\n\n"
                "Send these commands in the channel to use them."
            )
        else:
            is_authorized = db.is_user_authorized(message.from_user.id, bot.me.username)
            is_admin = db.is_admin(message.from_user.id)
            if not is_authorized:
                await message.reply_photo(
                    photo=photologo,
                    caption="**🔒 Access Required**\n\nContact admin to get access.",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💫 Get Access", url="https://t.me/ItsUGBot")]]),
                )
                return
            commands_list = (
                "**🤖 Available Commands**\n\n• /drm - Start Uploading...\n• /plan - View subscription\n"
            )
            if is_admin:
                commands_list += "\n**👑 Admin Commands**\n• /users - List all users\n"
            await message.reply_photo(
                photo=photologo,
                caption=f"**👋 Welcome {message.from_user.first_name}!**\n\n{commands_list}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📚 Help", url="https://t.me/ItsUGBot")]]),
            )
    except Exception as e:
        print(f"Error in start command: {str(e)}")

# Authorization filter for private users and channels
def auth_check_filter(_, client, message):
    try:
        if message.chat.type == "channel":
            return db.is_channel_authorized(message.chat.id, client.me.username)
        else:
            return db.is_user_authorized(message.from_user.id, client.me.username)
    except Exception:
        return False

auth_filter = filters.create(auth_check_filter)

# Handler for unauthorized commands by users without subscription
@bot.on_message(~auth_filter & filters.private & filters.command)
async def unauthorized_handler(client: Client, message: Message):
    await message.reply(
        "You need to have an active subscription to use this bot.\nPlease contact admin to get premium access.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("💫 Get Premium Access", url="https://t.me/ItsUGBot")]]
        ),
    )

# /id command to get current chat ID
@bot.on_message(filters.command("id"))
async def id_command(client: Client, message: Message):
    chat_id = message.chat.id
    await message.reply_text(f"The ID of this chat is:\n`{chat_id}`")

# /drm command placeholder for DRM-related functionality
@bot.on_message(filters.command("drm") & auth_filter)
async def drm_handler(bot: Client, message: Message):
    await message.reply_text("DRM downloader feature is under development.")

# Register user management commands from auth module
bot.add_handler(MessageHandler(auth.add_user_cmd, filters.command("add") & filters.private))
bot.add_handler(MessageHandler(auth.remove_user_cmd, filters.command("remove") & filters.private))
bot.add_handler(MessageHandler(auth.list_users_cmd, filters.command("users") & filters.private))
bot.add_handler(MessageHandler(auth.my_plan_cmd, filters.command("plan") & filters.private))

# Run the bot
bot.run()
