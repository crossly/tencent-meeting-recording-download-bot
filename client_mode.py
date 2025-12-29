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
        await event.respond("👤 Client Mode (Telethon) Active!\n\nSend a Tencent URL to download (up to 2GB supported).")

    @client.on(events.NewMessage(pattern='/set_cookie'))
    async def set_cookie(event):
        global current_cookie
        new_cookie = event.text.split(' ', 1)
        if len(new_cookie) < 2:
            await event.respond("Usage: /set_cookie <string>")
            return
        current_cookie = new_cookie[1].strip()
        await event.respond("✅ Cookie updated!")

    @client.on(events.NewMessage)
    async def handle_url(event):
        if event.text.startswith('/'): return
        url = event.text
        if "meeting.tencent.com" not in url: return
        
        status_msg = await event.respond("🔍 Analyzing (Client Mode)...")
        
        try:
            downloader = TencentMeetingDownloader(current_cookie)
            await status_msg.edit("⏳ Downloading...")
            
            loop = asyncio.get_event_loop()
            local_filename = await loop.run_in_executor(None, downloader.start_download, url)
            
            if local_filename and os.path.exists(local_filename):
                total_size = os.path.getsize(local_filename)
                file_size_mb = total_size / (1024 * 1024)
                await status_msg.edit(f"🚀 Uploading ({file_size_mb:.1f}MB)...")
                
                last_edit_time = 0
                async def progress_callback(current, total):
                    nonlocal last_edit_time
                    now = time.time()
                    if now - last_edit_time > 3:
                        percentage = (current / total) * 100
                        try:
                            await status_msg.edit(f"🚀 Uploading: {percentage:.1f}% ({current/(1024*1024):.1f}MB / {file_size_mb:.1f}MB)")
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
                await status_msg.delete()
            else:
                await status_msg.edit("❌ Download failed.")
        except Exception as e:
            logger.exception("Error in Client Mode")
            await status_msg.edit(f"❌ Error: {str(e)}")

    print("Client Mode is starting...")
    await client.start()
    await client.run_until_disconnected()

def run():
    if not config.API_ID or not config.API_HASH:
        print("ERROR: API_ID or API_HASH missing in config.py")
        return
    asyncio.run(run_client())
