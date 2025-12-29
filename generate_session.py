#!/usr/bin/env python3
"""
Generate a Telegram StringSession for use in containerized environments.

This script authenticates with Telegram and outputs a session string that can
be used as the TG_SESSION_STRING environment variable in Docker/Coolify.

Usage:
    1. Run this script locally: python generate_session.py
    2. Complete the interactive login (phone number + code)
    3. Copy the output session string
    4. Set it as TG_SESSION_STRING in your Coolify environment variables
"""

from telethon.sync import TelegramClient
from telethon.sessions import StringSession


def main():
    print("=" * 50)
    print("Telegram StringSession Generator")
    print("=" * 50)
    print()

    api_id = input("Enter your API_ID: ").strip()
    api_hash = input("Enter your API_HASH: ").strip()

    if not api_id or not api_hash:
        print("❌ API_ID and API_HASH are required!")
        return

    try:
        api_id = int(api_id)
    except ValueError:
        print("❌ API_ID must be a number!")
        return

    print()
    print("Starting authentication...")
    print("You will be prompted for your phone number and verification code.")
    print()

    with TelegramClient(StringSession(), api_id, api_hash) as client:
        session_string = client.session.save()
        print()
        print("=" * 50)
        print("✅ Authentication successful!")
        print("=" * 50)
        print()
        print("Your session string (copy this entire line):")
        print()
        print(session_string)
        print()
        print("=" * 50)
        print("IMPORTANT:")
        print("1. Add this to your Coolify environment variables as TG_SESSION_STRING")
        print("2. Keep this string SECRET - it grants access to your Telegram account")
        print("=" * 50)


if __name__ == "__main__":
    main()
