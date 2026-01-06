import os
import logging
import asyncio
import subprocess
import glob
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from main import TencentMeetingDownloader
import config

# --- LOGGING ---
logger = logging.getLogger("TencentBotMode")
current_cookie = config.DEFAULT_COOKIE

async def split_video(filename, chunk_size_mb=49):
    """
    Splits the video into chunks using ffmpeg.
    """
    logger.info(f"Splitting {filename} into ~{chunk_size_mb}MB chunks...")
    base, ext = os.path.splitext(filename)
    output_pattern = f"{base}_part%03d{ext}"
    cmd = [
        "ffmpeg", "-i", filename, "-c", "copy", "-map", "0",
        "-segment_time", "00:10:00", "-f", "segment", "-reset_timestamps", "1",
        output_pattern
    ]
    subprocess.run(cmd, check=True)
    chunks = sorted(glob.glob(f"{base}_part*{ext}"))
    return chunks

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot Mode Active!\n\n"
        "Send me a Tencent Meeting URL. If it's >50MB, I will split it for you automatically."
    )

async def set_cookie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global current_cookie
    if not context.args:
        await update.message.reply_text("Usage: /set_cookie <cookie_string>")
        return
    current_cookie = " ".join(context.args)
    await update.message.reply_text("✅ Cookie updated!")

async def list_recordings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List available recordings without downloading."""
    if not context.args:
        await update.message.reply_text("Usage: /list <URL>")
        return

    url = context.args[0]
    status_msg = await update.message.reply_text("🔍 Fetching recording list...")

    try:
        downloader = TencentMeetingDownloader(current_cookie)
        loop = asyncio.get_event_loop()
        recordings = await loop.run_in_executor(None, downloader.get_recording_list, url)

        if not recordings:
            await status_msg.edit_text("❌ No recordings found.")
            return

        msg = f"📋 Found {len(recordings)} recording(s):\n\n"
        for rec in recordings:
            msg += f"{rec['index']}. {rec['name']}\n"
            if rec['duration']:
                msg += f"   ⏱️ {rec['duration']/1000/60:.1f} min\n"
            if rec['size']:
                msg += f"   📦 {rec['size']/1024/1024:.1f} MB\n"

        msg += "\n💡 Send the URL to download first recording, or use /download_all <URL>"
        await status_msg.edit_text(msg)

    except Exception as e:
        logger.exception("Error listing recordings")
        await status_msg.edit_text(f"❌ Error: {str(e)}")

async def download_all_recordings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Download all recordings from a URL."""
    if not context.args:
        await update.message.reply_text("Usage: /download_all <URL>")
        return

    url = context.args[0]
    await _process_download(update, url, download_all=True)

async def _send_video_file(update, local_filename, status_msg):
    """Send a video file, splitting if necessary."""
    file_size_mb = os.path.getsize(local_filename) / (1024 * 1024)

    if file_size_mb > 50:
        await status_msg.edit_text(f"📦 Large file ({file_size_mb:.1f}MB). Splitting...")
        chunks = await split_video(local_filename)

        for i, chunk in enumerate(chunks):
            with open(chunk, 'rb') as video:
                await update.message.reply_video(
                    video=video,
                    caption=f"✅ {local_filename} (Part {i+1}/{len(chunks)})",
                    supports_streaming=True
                )
            os.remove(chunk)
    else:
        with open(local_filename, 'rb') as video:
            await update.message.reply_video(
                video=video,
                caption=f"✅ {local_filename}",
                supports_streaming=True
            )

    os.remove(local_filename)

async def _process_download(update, url, download_all=False):
    """Process download for a URL."""
    status_msg = await update.message.reply_text("🔍 Analyzing (Bot Mode)...")

    try:
        downloader = TencentMeetingDownloader(current_cookie)
        loop = asyncio.get_event_loop()

        if download_all:
            await status_msg.edit_text("⏳ Downloading all recordings...")
            filenames = await loop.run_in_executor(None, downloader.download_all, url)

            if filenames:
                await status_msg.edit_text(f"📤 Uploading {len(filenames)} file(s)...")
                for filename in filenames:
                    if os.path.exists(filename):
                        await _send_video_file(update, filename, status_msg)
                await status_msg.delete()
            else:
                await status_msg.edit_text("❌ No files downloaded.")
        else:
            await status_msg.edit_text("⏳ Downloading...")
            local_filename = await loop.run_in_executor(None, downloader.start_download, url)

            if local_filename and os.path.exists(local_filename):
                await _send_video_file(update, local_filename, status_msg)
                await status_msg.delete()
            else:
                await status_msg.edit_text("❌ Download failed.")

    except Exception as e:
        logger.exception("Error in Bot Mode")
        await status_msg.edit_text(f"❌ Error: {str(e)}")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "meeting.tencent.com" not in url:
        return

    await _process_download(update, url, download_all=False)

def run():
    if not config.TELEGRAM_TOKEN:
        print("ERROR: No TELEGRAM_TOKEN found in config.py")
        return

    app = ApplicationBuilder().token(config.TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("set_cookie", set_cookie))
    app.add_handler(CommandHandler("list", list_recordings))
    app.add_handler(CommandHandler("download_all", download_all_recordings))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_url))

    print("Bot Mode is starting...")
    app.run_polling()
