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
# StringSession for containerized environments (no interactive login needed)
# Generate using: python generate_session.py
TG_SESSION_STRING = os.getenv("TG_SESSION_STRING", "")

# Allowed chat IDs for Client mode (comma-separated)
# Only respond to messages from these chats. Leave empty to respond to all.
# Example: "123456789,987654321" or just "123456789"
# To get chat ID, forward a message from the chat to @userinfobot
_allowed_chats = os.getenv("TG_ALLOWED_CHATS", "")
TG_ALLOWED_CHATS = [int(x.strip()) for x in _allowed_chats.split(",") if x.strip()]

# --- DOWNLOADER CONFIG ---
DEFAULT_COOKIE = os.getenv("DEFAULT_COOKIE", "")
