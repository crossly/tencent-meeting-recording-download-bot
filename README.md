# Tencent Meeting Recording Downloader (Tencent Meeting Downloader)

[中文](README_ZH.md) | English

A powerful, automated tool to download Tencent Meeting recordings. Supports both standard Bot mode (for server-side automation) and User Client mode (for large file support up to 2GB).

## ✨ Key Features

- **Dual Mode Operation**:
  - 🤖 **Bot Mode**: Uses Telegram Bot API. Automatically splits videos >50MB using FFmpeg for seamless delivery.
  - 👤 **Client Mode**: Uses Telethon (MTProto). Supports single-file uploads up to 2GB.
- **Automated Stream Selection**: Intelligent selection of "Screen Share/Main Stream" without manual intervention.
- **Large File Support**: Built-in FFmpeg splitting (Bot mode) or high-speed MTProto upload (Client mode).
- **Session Management**: Easy cookie management and dynamic updates via Telegram commands.
- **One-Click Download**: Just send the recording URL to the bot.

## 🚀 Quick Start

### 1. Requirements

- Python 3.9+
- FFmpeg (for Bot mode splitting)

### 2. Installation

```bash
git clone https://github.com/ricky/tencent-meeting-recording-for-mp4.git
cd tencent-meeting-recording-for-mp4
pip install -r requirements.txt
```

### 3. Configuration

Copy the example environment file and fill in your details:

```bash
cp .env.example .env
```

Edit `.env`:
- `RUN_MODE`: Set to `BOT` or `CLIENT`.
- `TELEGRAM_TOKEN`: Get from [@BotFather](https://t.me/BotFather) (Bot mode).
- `TG_API_ID` / `TG_API_HASH`: Get from [my.telegram.org](https://my.telegram.org) (Client mode).
- `TG_SESSION_STRING`: Session string for containerized environments (see below).
- `DEFAULT_COOKIE`: Your Tencent Meeting session cookie.

### 4. Usage

```bash
python bot.py
```

- Send any Tencent Meeting URL to your bot.
- Use `/set_cookie <new_cookie>` to update your session on the fly.

## 🐳 Container Deployment (Docker/Coolify)

When running **Client mode** in a container environment, interactive login is not possible. You need to pre-generate a Session string.

### Generate Session String

Run locally (one-time setup):

```bash
python generate_session.py
```

You will be prompted for:
1. API_ID and API_HASH
2. Phone number
3. Verification code (or 2FA password)

After completion, a long string will be output.

### Configure Environment Variable

Add the generated string to your Coolify/Docker environment variables:

```
TG_SESSION_STRING=<your_generated_string>
```

> ⚠️ **Security Note**: The session string is equivalent to login credentials. Keep it secret and never share it.

## 🛠️ Technical Details

| Component | Technology |
| :--- | :--- |
| **API Wrapper** | Python Requests |
| **Bot Framework** | python-telegram-bot |
| **User Client** | Telethon (MTProto) |
| **Video Processing** | FFmpeg |

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

MIT License
