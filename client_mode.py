import os
import logging
import asyncio
import time
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from main import TencentMeetingDownloader
import config

# --- LOGGING ---
logger = logging.getLogger("TencentClientMode")
current_cookie = config.DEFAULT_COOKIE

def is_allowed_chat(event):
    """Check if the event is from an allowed chat."""
    if not config.TG_ALLOWED_CHATS:
        # No restriction - allow all chats
        return True
    return event.chat_id in config.TG_ALLOWED_CHATS

async def run_client():
    # Use StringSession if TG_SESSION_STRING is set (for containerized environments)
    # Otherwise, fall back to file-based session
    if config.TG_SESSION_STRING:
        logger.info("Using StringSession from TG_SESSION_STRING environment variable")
        session = StringSession(config.TG_SESSION_STRING)
    else:
        # Use sessions directory for Docker volume mount compatibility
        session_dir = os.path.join(os.path.dirname(__file__), 'sessions')
        os.makedirs(session_dir, exist_ok=True)
        session = os.path.join(session_dir, 'tencent_session')
        logger.info(f"Using file-based session at {session}")

    client = TelegramClient(session, config.API_ID, config.API_HASH)

    @client.on(events.NewMessage(pattern='/start'))
    async def start(event):
        if not is_allowed_chat(event):
            return
        await event.respond(
            "👤 Client Mode (Telethon) Active!\n\n"
            "Send a Tencent URL to download (up to 2GB supported).\n\n"
            "Commands:\n"
            "/list <URL> - List available recordings\n"
            "/download_all <URL> - Download all recordings"
        )

    @client.on(events.NewMessage(pattern='/set_cookie'))
    async def set_cookie(event):
        if not is_allowed_chat(event):
            return
        global current_cookie
        new_cookie = event.text.split(' ', 1)
        if len(new_cookie) < 2:
            await event.respond("Usage: /set_cookie <string>")
            return
        current_cookie = new_cookie[1].strip()
        await event.respond("✅ Cookie updated!")

    @client.on(events.NewMessage(pattern='/list'))
    async def list_recordings(event):
        if not is_allowed_chat(event):
            return
        parts = event.text.split(' ', 1)
        if len(parts) < 2:
            await event.respond("Usage: /list <URL>")
            return

        url = parts[1].strip()
        status_msg = await event.respond("🔍 Fetching recording list...")

        try:
            downloader = TencentMeetingDownloader(current_cookie)
            loop = asyncio.get_event_loop()
            recordings = await loop.run_in_executor(None, downloader.get_recording_list, url)

            if not recordings:
                await status_msg.edit("❌ No recordings found.")
                return

            msg = f"📋 Found {len(recordings)} recording(s):\n\n"
            for rec in recordings:
                msg += f"{rec['index']}. {rec['name']}\n"
                if rec['duration']:
                    msg += f"   ⏱️ {rec['duration']/1000/60:.1f} min\n"
                if rec['size']:
                    msg += f"   📦 {rec['size']/1024/1024:.1f} MB\n"

            msg += "\n💡 Send the URL to download first, or use /download_all <URL>"
            await status_msg.edit(msg)

        except Exception as e:
            logger.exception("Error listing recordings")
            await status_msg.edit(f"❌ Error: {str(e)}")

    @client.on(events.NewMessage(pattern='/download_all'))
    async def download_all_recordings(event):
        if not is_allowed_chat(event):
            return
        parts = event.text.split(' ', 1)
        if len(parts) < 2:
            await event.respond("Usage: /download_all <URL>")
            return

        url = parts[1].strip()
        await _process_download(client, event, url, download_all=True)

    @client.on(events.NewMessage)
    async def handle_url(event):
        if not is_allowed_chat(event):
            return
        if event.text.startswith('/'): return
        url = event.text
        if "meeting.tencent.com" not in url: return

        await _process_download(client, event, url, download_all=False)

    async def _process_download(client, event, url, download_all=False):
        status_msg = await event.respond("🔍 Analyzing (Client Mode)...")

        try:
            downloader = TencentMeetingDownloader(current_cookie)
            loop = asyncio.get_event_loop()

            if download_all:
                await status_msg.edit("⏳ Downloading all recordings...")
                filenames = await loop.run_in_executor(None, downloader.download_all, url)

                if filenames:
                    for i, filename in enumerate(filenames):
                        if os.path.exists(filename):
                            await _upload_file(client, event, filename, status_msg, i+1, len(filenames))
                    await status_msg.delete()
                else:
                    await status_msg.edit("❌ No files downloaded.")
            else:
                await status_msg.edit("⏳ Downloading...")
                local_filename = await loop.run_in_executor(None, downloader.start_download, url)

                if local_filename and os.path.exists(local_filename):
                    await _upload_file(client, event, local_filename, status_msg, 1, 1)
                    await status_msg.delete()
                else:
                    await status_msg.edit("❌ Download failed.")

        except Exception as e:
            logger.exception("Error in Client Mode")
            await status_msg.edit(f"❌ Error: {str(e)}")

    async def _upload_file(client, event, local_filename, status_msg, current_idx, total):
        total_size = os.path.getsize(local_filename)
        file_size_mb = total_size / (1024 * 1024)

        progress_prefix = f"[{current_idx}/{total}] " if total > 1 else ""
        await status_msg.edit(f"🚀 {progress_prefix}Uploading ({file_size_mb:.1f}MB)...")

        last_edit_time = 0
        async def progress_callback(current, total):
            nonlocal last_edit_time
            now = time.time()
            if now - last_edit_time > 3:
                percentage = (current / total) * 100
                try:
                    await status_msg.edit(
                        f"🚀 {progress_prefix}Uploading: {percentage:.1f}% "
                        f"({current/(1024*1024):.1f}MB / {file_size_mb:.1f}MB)"
                    )
                    last_edit_time = now
                except: pass

        await client.send_file(
            event.chat_id,
            local_filename,
            caption=f"✅ {local_filename}",
            supports_streaming=True,
            progress_callback=progress_callback
        )

        os.remove(local_filename)

    print("Client Mode is starting...")
    await client.start()
    await client.run_until_disconnected()

def run():
    if not config.API_ID or not config.API_HASH:
        print("ERROR: API_ID or API_HASH missing in config.py")
        return
    asyncio.run(run_client())
