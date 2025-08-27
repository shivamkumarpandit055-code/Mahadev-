import os
import asyncio
import time
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait
import ug as helper  # आपकी ug.py - इसमें DRM लाइव डाउनलोड/डिक्रिप्ट फंक्शन हैं
from vars import *
from db import db
from clean import register_clean_handler
from utils import progress_bar
from apixug import SecureAPIClient

watermark = "UG"
timeout_duration = 300  # 5 मिनट

bot = Client(
    "ugx",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=300,
    sleep_threshold=60,
    in_memory=True,
)

register_clean_handler(bot)
client = SecureAPIClient()
apis = client.get_apis()


def auth_check_filter(_, __, message):
    try:
        if message.chat.type == "channel":
            return db.is_channel_authorized(message.chat.id, bot.me.username)
        else:
            return db.is_user_authorized(message.from_user.id, bot.me.username)
    except Exception:
        return False


auth_filter = filters.create(auth_check_filter)


@bot.on_message(filters.command("drm") & auth_filter)
async def drm_command_handler(bot: Client, message: Message):
    try:
        bot_username = (await bot.get_me()).username

        # Channel में अनुमति जांचें
        if message.chat.type == "channel" and not db.is_channel_authorized(message.chat.id, bot_username):
            return
        # प्राइवेट यूजर जांच
        if message.chat.type != "channel" and not db.is_user_authorized(message.from_user.id, bot_username):
            await message.reply_text("❌ आप इस कमांड को इस्तेमाल करने के लिए अधिकृत नहीं हैं।")
            return

        await message.reply_text(
            "**👋 Send a text file containing Name and URL lines in this format:**\n\n"
            "`Name: URL`\n\n"
            "Example:\nPhysics Lecture 1: https://example.com/drm_video_link\nMath Class: https://example.com/normal_video\n\n"
            "_Send the file within 60 seconds._"
        )

        input_file_msg = await bot.listen(message.chat.id, timeout=60)
        if not input_file_msg.document:
            await message.reply_text("❌ कृपया एक वैध टेक्स्ट (.txt) फ़ाइल भेजें।")
            return

        input_file_path = await input_file_msg.download()
        with open(input_file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        os.remove(input_file_path)

        entries = []
        for line in lines:
            if ':' in line:
                name, url = line.split(':', 1)
                name = name.strip()
                url = url.strip()
                if url:
                    entries.append((name, url))

        if not entries:
            await message.reply_text("❌ फाइल में उपयुक्त नाम:URL लाइनें नहीं मिलीं।")
            return

        await message.reply_text("✅ फ़ाइल प्राप्त। अब वीडियो डाउनलोडिंग शुरू हो रही है...")

        success_count, failed_list = 0, []

        for idx, (name, url) in enumerate(entries, start=1):
            try:
                await message.reply_text(f"▶️ डाउनलोड कर रहा हूँ: {name}")
                # DRM लिंक के लिए विशेष हैंडलिंग
                if any(x in url for x in ["classplusapp.com/drm", "encrypted.m", "drmcdni", "drm/wv"]):
                    api_drm_url = apis.get("API_DRM", "")
                    keys_string = ""
                    if api_drm_url:
                        # DRM कुंजी प्राप्त करें
                        try:
                            full_api_url = api_drm_url + url
                            mpd, keys = helper.get_mps_and_keys(full_api_url)
                            if mpd and keys:
                                url = mpd
                                keys_string = " ".join([f"--key {k}" for k in keys])
                        except Exception as e:
                            await message.reply_text(f"DRM कुंजी प्राप्त करने में विफल: {str(e)}")

                    download_progress_msg = await message.reply_text(f"🔐 DRM वीडियो डाउनलोड कर रहा हूँ: {name}")
                    file_path = await helper.decrypt_and_merge_video(url, keys_string, "downloads", name)
                    await download_progress_msg.delete()

                    if file_path:
                        await helper.send_vid(bot, message, f"🎬 {name} अपलोड हो गया है।", file_path, None, name, None, message.chat.id, watermark=watermark)
                        success_count += 1
                    else:
                        raise Exception("डिक्रिप्शन या डाउनलोड फेल")

                else:
                    # सामान्य वीडियो डाउनलोडिंग
                    download_progress_msg = await message.reply_text(f"⬇️ वीडियो डाउनलोड कर रहा हूँ: {name}")
                    cmd = f'yt-dlp -o "{name}.mp4" "{url}"'
                    file_path = await helper.download_video(url, cmd, name)
                    await download_progress_msg.delete()

                    if file_path:
                        await helper.send_vid(bot, message, f"🎬 {name} अपलोड हो गया है।", file_path, None, name, None, message.chat.id, watermark=watermark)
                        success_count += 1
                    else:
                        raise Exception("डाउनलोड विफल")

            except Exception as e:
                failed_list.append((name, str(e)))
                await message.reply_text(f"❌ फेल हुआ: {name}\nकारण: {str(e)}")

        result_msg = f"✅ कुल सफल वीडियो: {success_count}\n"
        if failed_list:
            result_msg += "⚠️ फेल वीडियो:\n" + "\n".join([f"- {n}: {m}" for n, m in failed_list])

        await message.reply_text(result_msg)

    except Exception as e:
        await message.reply_text(f"⚠️ कोई त्रुटि हुई: {str(e)}")


if __name__ == "__main__":
    print("Bot Starting...")
    bot.run()
                
