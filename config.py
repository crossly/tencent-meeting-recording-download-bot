import os
from dotenv import load_dotenv

# Load variables from .env if it exists
load_dotenv()

# --- RUN MODE ---
# "BOT" or "CLIENT"
RUN_MODE = os.getenv("RUN_MODE", "BOT")

# --- TELEGRAM BOT CONFIG (Used if RUN_MODE == "BOT") ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

# --- TELEGRAM CLIENT CONFIG (Used if RUN_MODE == "CLIENT") ---
API_ID = os.getenv("TG_API_ID")
if API_ID:
    API_ID = int(API_ID)
API_HASH = os.getenv("TG_API_HASH", "")

# --- DOWNLOADER CONFIG ---
DEFAULT_COOKIE = os.getenv("DEFAULT_COOKIE", "")
