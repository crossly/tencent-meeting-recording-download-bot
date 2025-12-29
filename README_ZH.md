# 腾讯会议录像下载器 (Tencent Meeting Downloader)

[English](README.md) | 中文

一个强大且自动化的腾讯会议录像下载工具。支持标准 Bot 模式（适合服务器自动化）与用户客户端模式（支持最高 2GB 大文件上传）。

## ✨ 功能特性

- **双模式运行**：
  - 🤖 **Bot 模式**：使用 Telegram Bot API。自动调用 FFmpeg 将大于 50MB 的视频切分，确保无缝发送。
  - 👤 **客户端模式**：使用 Telethon (MTProto)。支持最高 2GB 的单文件直接上传。
- **自动选流**：智能优选“屏幕共享/主画面”，无需人工干预。
- **大文件优化**：内置 FFmpeg 切分逻辑（Bot 模式）或高速 MTProto 上传（客户端模式）。
- **会话管理**：通过 Telegram 命令轻松管理 Cookie 并支持动态更新。
- **一键下载**：只需将录像链接发送给 Bot，即可自动完成解析与传送。

## 🚀 快速开始

### 1. 环境依赖

- Python 3.9+
- FFmpeg (Bot 模式分段功能需要)

### 2. 安装

```bash
git clone https://github.com/ricky/tencent-meeting-recording-for-mp4.git
cd tencent-meeting-recording-for-mp4
pip install -r requirements.txt
```

### 3. 配置

复制环境变量模板并填写相应的参数：

```bash
cp .env.example .env
```

编辑 `.env` 文件：
- `RUN_MODE`: 设置为 `BOT` 或 `CLIENT`。
- `TELEGRAM_TOKEN`: 从 [@BotFather](https://t.me/BotFather) 获取（Bot 模式）。
- `TG_API_ID` / `TG_API_HASH`: 从 [my.telegram.org](https://my.telegram.org) 获取（客户端模式）。
- `TG_SESSION_STRING`: 用于容器环境的会话字符串（见下方说明）。
- `DEFAULT_COOKIE`: 你的腾讯会议会话 Cookie。

### 4. 启动

```bash
python bot.py
```

- 发送腾讯会议链接至你的 Bot 即可开始下载。
- 在对话框中使用 `/set_cookie <新Cookie>` 可随时在线更新。

## 🐳 容器部署（Docker/Coolify）

在容器环境中运行**客户端模式**时，由于无法进行交互式登录，需要预先生成 Session 字符串。

### 生成 Session 字符串

在本地执行（仅需一次）：

```bash
python generate_session.py
```

按提示输入：
1. API_ID 和 API_HASH
2. 手机号码
3. 验证码（或两步验证密码）

完成后会输出一长串字符串。

### 配置环境变量

将生成的字符串添加到 Coolify/Docker 的环境变量中：

```
TG_SESSION_STRING=<你生成的字符串>
```

> ⚠️ **安全提示**：Session 字符串等同于登录凭证，请妥善保管，切勿泄露。

## 🛠️ 技术栈

| 组件 | 技术 |
| :--- | :--- |
| **API 封装** | Python Requests |
| **Bot 框架** | python-telegram-bot |
| **用户客户端** | Telethon (MTProto) |
| **视频处理** | FFmpeg |

## 🤝 贡献说明

欢迎提交 Pull Request 来改进本项目！

## 📄 开源协议

MIT License
