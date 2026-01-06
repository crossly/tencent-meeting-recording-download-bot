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
        self.page_recordings = []  # Recordings extracted from page HTML

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
        """
        Resolve collection UUID and record mappings from the page.
        Also extracts recordings from page serverData as fallback.
        """
        logger.info(f"Resolving IDs for short_id: {short_id}")
        page_url = f"https://meeting.tencent.com/cw/{short_id}"
        self.session.headers.update({"Referer": "https://meeting.tencent.com/"})

        response = self.session.get(page_url)
        if response.status_code != 200:
            logger.warning(f"Failed to load landing page (Status: {response.status_code})")

        page_text = response.text

        # 1. Collection UUID
        match = re.search(r'id=([a-f0-9-]{36})', page_text)
        if not match:
            match = re.search(r'"id"\s*:\s*"([a-f0-9-]{36})"', page_text)

        if match:
            self.collection_uuid = match.group(1)
            logger.info(f"Collection UUID: {self.collection_uuid}")
        else:
            self.collection_uuid = short_id
            logger.warning("Could not find Collection UUID, falling back to Short ID.")

        # 2. Record-specific UUIDs (id -> sharing_id mapping)
        self.record_mappings = {}
        id_pattern = r'(?:\\"|")sharing_id(?:\\"|")\s*:\s*(?:\\"|")([a-f0-9-]{36})(?:\\"|")(?:(?!sharing_id).)*?(?:\\"|")id(?:\\"|")\s*:\s*(?:\\"|")?(\d+)(?:\\"|")?'
        rev_id_pattern = r'(?:\\"|")id(?:\\"|")\s*:\s*(?:\\"|")?(\d+)(?:\\"|")?(?:(?!id(?:\\"|")\s*:).)*?(?:\\"|")sharing_id(?:\\"|")\s*:\s*(?:\\"|")([a-f0-9-]{36})(?:\\"|")'

        for p in [id_pattern, rev_id_pattern]:
            for match in re.finditer(p, page_text, re.DOTALL):
                g1, g2 = match.groups()
                if "-" in g1:  # Pattern 1: g1=UUID, g2=NumID
                    self.record_mappings[str(g2)] = g1
                else:  # Pattern 2: g1=NumID, g2=UUID
                    self.record_mappings[str(g1)] = g2

        logger.info(f"Found {len(self.record_mappings)} record mappings.")

        # 3. Extract recordings from page serverData (fallback for when API returns empty)
        self._extract_page_recordings(page_text)

        return self.collection_uuid

    def _extract_page_recordings(self, page_text):
        """
        Extract recording info directly from page HTML serverData.
        This is a fallback when the API returns empty base_infos.
        """
        self.page_recordings = []

        # Find all unique sharing_ids (these are the recording UUIDs)
        sharing_ids = re.findall(r'sharing_id[\\\"]+:\s*[\\\"]+([a-f0-9-]{36})', page_text)
        unique_sharing_ids = list(dict.fromkeys(sharing_ids))

        # Decode escaped content for parsing
        decoded = page_text.replace('\\\\', '\\').replace('\\"', '"')

        for sharing_id in unique_sharing_ids:
            # Skip collection UUID
            if sharing_id == self.collection_uuid:
                continue

            rec_info = {
                'sharing_id': sharing_id,
                'id': None,
                'name': None,
                'duration': None,
                'size': None,
            }

            # Try to find associated info near this sharing_id
            # Look for the object containing this sharing_id
            pattern = rf'"sharing_id"\s*:\s*"{sharing_id}"[^}}]*'
            match = re.search(pattern, decoded)
            if match:
                context = match.group(0)
                # Extend context to get more fields
                start = match.start()
                end = min(match.end() + 500, len(decoded))
                extended = decoded[start:end]

                id_match = re.search(r'"id"\s*:\s*"?(\d{19})"?', extended)
                if id_match:
                    rec_info['id'] = id_match.group(1)

                name_match = re.search(r'"name"\s*:\s*"([^"]*)"', extended)
                if name_match:
                    rec_info['name'] = name_match.group(1)

                duration_match = re.search(r'"duration"\s*:\s*"?(\d+)"?', extended)
                if duration_match:
                    rec_info['duration'] = int(duration_match.group(1))

                size_match = re.search(r'"size"\s*:\s*"?(\d+)"?', extended)
                if size_match:
                    rec_info['size'] = int(size_match.group(1))

            self.page_recordings.append(rec_info)

        logger.info(f"Extracted {len(self.page_recordings)} recordings from page data.")

    def fetch_recording_info(self):
        """
        Fetch recording info from API.
        Returns API data, or falls back to page_recordings if API returns empty.
        """
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

        # Check if API returned empty, use page_recordings as fallback
        base_infos = self.recording_info.get('base_infos') or self.recording_info.get('record_info_list')
        if not base_infos and self.page_recordings:
            logger.info("API returned empty base_infos, using page_recordings as fallback.")
            # Convert page_recordings to base_infos format
            self.recording_info['base_infos'] = [
                {
                    'sharing_id': rec['sharing_id'],
                    'id': rec['id'],
                    'recording_id': rec['id'],
                    'name': rec['name'] or f"Recording_{i+1}",
                    'duration': rec['duration'],
                    'size': rec['size'],
                }
                for i, rec in enumerate(self.page_recordings)
            ]

        return self.recording_info

    def fetch_sign_urls(self, record_uuid):
        """
        Fetch signed URLs for a recording.
        Returns response with either multi_stream_recordings or signurl.
        """
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

    def _get_download_url_from_sign_data(self, sign_data):
        """
        Extract download URL from sign API response.
        Supports both multi_stream_recordings (multi-stream) and signurl (direct download).

        Returns: (url, stream_type_label)
        """
        if sign_data.get('code') != 0:
            return None, None

        data = sign_data.get('data', {})

        # Mode 1: Multi-stream recordings (has separate screen share, speaker, audio)
        streams = data.get('multi_stream_recordings')
        if streams and len(streams) > 0:
            # Prefer Screen Share (type 1), then Speaker (type 2), then first available
            selected = next((s for s in streams if s.get('stream_type') == 1), None)
            if not selected:
                selected = next((s for s in streams if s.get('stream_type') == 2), None)
            if not selected:
                selected = streams[0]

            stype = selected.get('stream_type')
            label = "ScreenShare" if stype == 1 else "Speaker" if stype == 2 else "Audio"
            return selected.get('sign_url'), label

        # Mode 2: Direct download URL (signurl)
        signurl = sign_data.get('signurl')
        if signurl:
            logger.info("Using direct download mode (signurl)")
            return signurl, "Direct"

        return None, None

    def start_download(self, url, progress_callback=None):
        """
        Main entry point for bot. Returns the local filename if successful.
        Downloads the first recording with preferred stream.
        """
        filenames = self.download_all(url, max_count=1, progress_callback=progress_callback)
        if filenames:
            return filenames[0]
        raise Exception("Download failed - no files downloaded.")

    def download_all(self, url, max_count=None, progress_callback=None):
        """
        Download all (or up to max_count) recordings from the URL.
        Returns list of downloaded filenames.
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

            # Limit number of downloads if specified
            if max_count:
                base_infos = base_infos[:max_count]

            downloaded_files = []

            for idx, record in enumerate(base_infos):
                logger.info(f"Processing recording {idx + 1}/{len(base_infos)}")

                # Get record identifiers
                rec_id = record.get('recording_id') or record.get('record_id') or record.get('id')
                sharing_id = record.get('sharing_id')
                topic = record.get('name') or record.get('meeting_topic') or f'Recording_{idx + 1}'

                # Determine which UUID to use for sign API
                # Priority: sharing_id from record > mapped UUID > rec_id
                if sharing_id:
                    record_uuid = sharing_id
                elif rec_id and str(rec_id) in self.record_mappings:
                    record_uuid = self.record_mappings[str(rec_id)]
                else:
                    record_uuid = rec_id

                if not record_uuid:
                    logger.warning(f"Could not determine UUID for recording {idx + 1}, skipping.")
                    continue

                logger.info(f"Fetching sign URL for: {record_uuid}")
                sign_data = self.fetch_sign_urls(record_uuid)

                if sign_data.get('code') != 0:
                    logger.error(f"Failed to sign URL for recording {idx + 1}: {sign_data.get('message')}")
                    continue

                # Get download URL (supports both modes)
                stream_url, stream_label = self._get_download_url_from_sign_data(sign_data)

                if not stream_url:
                    logger.error(f"No download URL available for recording {idx + 1}")
                    continue

                # Generate filename
                safe_topic = "".join([c for c in topic if c.isalnum() or c in (' ', '_', '-')]).strip()
                if not safe_topic:
                    safe_topic = f"Recording_{idx + 1}"

                # Add index if multiple recordings
                if len(base_infos) > 1:
                    filename = f"{safe_topic}_{idx + 1}_{stream_label}.mp4"
                else:
                    filename = f"{safe_topic}_{stream_label}.mp4"

                logger.info(f"Starting download: {filename}")

                # Download based on URL type
                try:
                    if ".m3u8" in stream_url:
                        success = download_hls(stream_url, filename, headers=dict(self.session.headers))
                    else:
                        success = download_file(stream_url, filename, headers=dict(self.session.headers))

                    if success:
                        downloaded_files.append(filename)
                        logger.info(f"Successfully downloaded: {filename}")
                    else:
                        logger.error(f"Download failed for: {filename}")
                except Exception as e:
                    logger.exception(f"Error downloading {filename}: {e}")

            return downloaded_files

        except Exception as e:
            logger.exception("Error during download process")
            raise e

    def get_recording_list(self, url):
        """
        Get list of recordings without downloading.
        Useful for bot to show available recordings to user.
        """
        short_id = self.extract_short_id(url)
        self.resolve_ids(short_id)
        info = self.fetch_recording_info()

        if not info:
            return []

        base_infos = info.get('base_infos') or info.get('record_info_list') or []

        result = []
        for idx, record in enumerate(base_infos):
            duration = record.get('duration')
            size = record.get('size')
            # Ensure numeric types
            if duration and isinstance(duration, str):
                duration = int(duration)
            if size and isinstance(size, str):
                size = int(size)
            result.append({
                'index': idx + 1,
                'name': record.get('name') or record.get('meeting_topic') or f'Recording_{idx + 1}',
                'duration': duration,
                'size': size,
                'sharing_id': record.get('sharing_id'),
            })

        return result


if __name__ == "__main__":
    # Compatibility with old CLI if needed
    if len(sys.argv) < 2:
        print("Usage: python main.py <URL> [COOKIE]")
        print("       python main.py --all <URL> [COOKIE]  # Download all recordings")
    else:
        download_all = False
        url_idx = 1

        if sys.argv[1] == "--all":
            download_all = True
            url_idx = 2

        if url_idx >= len(sys.argv):
            print("Error: URL is required")
            sys.exit(1)

        url = sys.argv[url_idx]
        cookie = sys.argv[url_idx + 1] if len(sys.argv) > url_idx + 1 else None

        dl = TencentMeetingDownloader(cookie)
        try:
            if download_all:
                paths = dl.download_all(url)
                print(f"Downloaded {len(paths)} files:")
                for p in paths:
                    print(f"  - {p}")
            else:
                path = dl.start_download(url)
                print(f"Downloaded to: {path}")
        except Exception as e:
            print(f"Error: {e}")
