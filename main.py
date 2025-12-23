import os
import sys
import json
import re
import requests
import time
import random
import string
import logging
from downloader import download_file, download_hls

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TencentDownloader")

class TencentMeetingDownloader:
    def __init__(self, cookie_str=None):
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        self.session.headers.update(self.headers)
        
        if cookie_str:
            self.set_cookies(cookie_str)
        
        self.collection_uuid = None
        self.record_mappings = {}
        self.recording_info = None

    def set_cookies(self, cookie_str):
        if not cookie_str:
            return
        if cookie_str.startswith("Cookie: "):
            cookie_str = cookie_str[8:]
        for item in cookie_str.split(';'):
            if '=' in item:
                k, v = item.strip().split('=', 1)
                self.session.cookies.set(k, v)
        logger.info("Cookies updated.")

    def extract_short_id(self, url):
        match = re.search(r'/(?:crm|cw|v2)/([A-Za-z0-9_-]+)', url)
        if not match:
            raise ValueError("Invalid Tencent Meeting recording URL")
        return match.group(1)

    def generate_nonce(self, length=9):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    def generate_trace_id(self):
        return ''.join(random.choices("0123456789abcdef", k=32))

    def resolve_ids(self, short_id):
        logger.info(f"Resolving IDs for short_id: {short_id}")
        page_url = f"https://meeting.tencent.com/cw/{short_id}"
        self.session.headers.update({"Referer": "https://meeting.tencent.com/"})
        
        response = self.session.get(page_url)
        if response.status_code != 200:
            logger.warning(f"Failed to load landing page (Status: {response.status_code})")
        
        # 1. Collection UUID
        match = re.search(r'id=([a-f0-9-]{36})', response.text)
        if not match:
            match = re.search(r'"id"\s*:\s*"([a-f0-9-]{36})"', response.text)
        
        if match:
            self.collection_uuid = match.group(1)
            logger.info(f"Collection UUID: {self.collection_uuid}")
        else:
            self.collection_uuid = short_id
            logger.warning("Could not find Collection UUID, falling back to Short ID.")

        # 2. Record-specific UUIDs
        self.record_mappings = {}
        id_pattern = r'(?:\\"|")sharing_id(?:\\"|")\s*:\s*(?:\\"|")([a-f0-9-]{36})(?:\\"|")(?:(?!sharing_id).)*?(?:\\"|")id(?:\\"|")\s*:\s*(?:\\"|")?(\d+)(?:\\"|")?'
        rev_id_pattern = r'(?:\\"|")id(?:\\"|")\s*:\s*(?:\\"|")?(\d+)(?:\\"|")?(?:(?!id(?:\\"|")\s*:).)*?(?:\\"|")sharing_id(?:\\"|")\s*:\s*(?:\\"|")([a-f0-9-]{36})(?:\\"|")'
        
        for p in [id_pattern, rev_id_pattern]:
            for match in re.finditer(p, response.text, re.DOTALL):
                g1, g2 = match.groups()
                if "-" in g1: # Pattern 1: g1=UUID, g2=NumID
                    self.record_mappings[str(g2)] = g1
                else: # Pattern 2: g1=NumID, g2=UUID
                    self.record_mappings[str(g1)] = g2
        
        logger.info(f"Found {len(self.record_mappings)} record mappings.")
        return self.collection_uuid

    def fetch_recording_info(self):
        nonce = self.generate_nonce()
        timestamp = int(time.time() * 1000)
        trace_id = self.generate_trace_id()
        
        api_url = "https://meeting.tencent.com/wemeet-tapi/v2/meetlog/public/record-detail/get-multi-record-info"
        params = {
            "c_os_model": "web", "c_os": "web", "c_timestamp": timestamp,
            "c_nonce": nonce, "c_instance_id": "5", "rnds": nonce,
            "platform": "Web", "auth_share_id": self.collection_uuid,
            "uni_record_share_id": self.collection_uuid, "c_lang": "zh-CN",
            "trace-id": trace_id
        }
        
        response = self.session.get(api_url, params=params)
        data = response.json()
        
        if data.get('code') != 0:
            logger.error(f"Error fetching record info: {data.get('message', 'Unknown error')}")
            return None
        
        self.recording_info = data.get('data', {})
        return self.recording_info

    def fetch_sign_urls(self, record_uuid):
        nonce = self.generate_nonce()
        timestamp = int(time.time() * 1000)
        trace_id = self.generate_trace_id()
        
        api_url = "https://meeting.tencent.com/wemeet-cloudrecording-webapi/v1/sign"
        params = {
            "c_os_model": "web", "c_os": "web", "c_timestamp": timestamp,
            "c_nonce": nonce, "c_instance_id": "5", "rnds": nonce,
            "platform": "Web", "id": record_uuid,
            "sharing_id": self.collection_uuid,
            "need_multi_stream": 1, "source": "shares", "enter_from": "share",
            "c_lang": "zh-CN", "trace-id": trace_id
        }
        
        response = self.session.get(api_url, params=params)
        data = response.json()
        if data.get('code') != 0:
            logger.error(f"Sign API Status: Code={data.get('code')}, Msg={data.get('message')}")
        return data

    def start_download(self, url, progress_callback=None):
        """
        Main entry point for bot. Returns the local filename if successful.
        Automatically selects Screen Share stream.
        """
        try:
            short_id = self.extract_short_id(url)
            self.resolve_ids(short_id)
            info = self.fetch_recording_info()
            
            if not info:
                raise Exception("Could not fetch recording info. Cookie might be invalid.")

            base_infos = info.get('base_infos') or info.get('record_info_list')
            if not base_infos:
                raise Exception("No recording files found. Check if the link requires special permissions.")
            
            # Select first record and preferred stream (Screen Share = 1)
            record = base_infos[0]
            rec_id = record.get('recording_id') or record.get('record_id') or record.get('id')
            topic = record.get('name') or record.get('meeting_topic', 'Recording')
            
            record_uuid = self.record_mappings.get(str(rec_id), rec_id)
            sign_data = self.fetch_sign_urls(record_uuid)
            
            if sign_data.get('code') != 0:
                raise Exception(f"Failed to sign URL: {sign_data.get('message')}")
            
            streams = sign_data.get('data', {}).get('multi_stream_recordings', [])
            if not streams:
                raise Exception("No streams available for this recording.")
            
            # Prefer Screen Share (type 1)
            selected_stream = next((s for s in streams if s.get('stream_type') == 1), streams[0])
            stream_url = selected_stream.get('sign_url')
            
            stype = selected_stream.get('stream_type')
            label = "ScreenShare" if stype == 1 else "Speaker" if stype == 2 else "Audio"
            
            safe_topic = "".join([c for c in topic if c.isalnum() or c in (' ', '_', '-')]).strip()
            filename = f"{safe_topic}_{label}.mp4"
            
            logger.info(f"Starting download: {filename}")
            if ".m3u8" in stream_url:
                success = download_hls(stream_url, filename, headers=dict(self.session.headers))
            else:
                success = download_file(stream_url, filename, headers=dict(self.session.headers))
            
            if success:
                return filename
            else:
                raise Exception("Download failed in downloader module.")

        except Exception as e:
            logger.exception("Error during download process")
            raise e

if __name__ == "__main__":
    # Compatibility with old CLI if needed
    if len(sys.argv) < 2:
        print("Usage: python main.py <URL> [COOKIE]")
    else:
        dl = TencentMeetingDownloader(sys.argv[2] if len(sys.argv) > 2 else None)
        try:
            path = dl.start_download(sys.argv[1])
            print(f"Downloaded to: {path}")
        except Exception as e:
            print(f"Error: {e}")
