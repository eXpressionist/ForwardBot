# ForwardBot

A lightweight Telegram bot that tracks groups it has been added to and copies allowed media into a target channel without exposing the original sender.

## Features

- aiogram 3 async bot runtime.
- SQLite storage through `aiosqlite`.
- Dynamic group tracking via Telegram `my_chat_member` updates.
- Admin-only `/chats` menu for toggling which tracked groups are allowed.
- Copies photos, videos, and image/video documents to the target channel.
- Ignores forwarded/reposted media while allowing posts sent by users, anonymous admins, or participants posting as channels.
- Appends source attribution and the original message link to captions while respecting Telegram's 1024 character caption limit.
- Handles albums by preserving the grouped media order and adding source attribution once.

## Setup

1. Create a bot with BotFather and copy its token.
2. Add the bot to your target channel as an administrator with permission to post messages.
3. Copy the environment template:

```bash
cp .env.example .env
```

4. Edit `.env`:

```env
BOT_TOKEN=123456789:your_bot_token
ADMIN_ID=123456789
TARGET_CHANNEL_ID=@your_target_channel
DATABASE_PATH=data/bot.sqlite3
LOG_LEVEL=INFO
```

`TARGET_CHANNEL_ID` can be a channel username such as `@my_channel` or a numeric channel ID.

## Run With Docker

```bash
docker compose up -d --build
```

View logs:

```bash
docker compose logs -f forwardbot
```

## Run Locally

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python main.py
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## Admin Usage

1. Add the bot to a group or supergroup.
2. If the bot was already in the group before this app started, send `/track` in that group once.
3. Open a private chat with the bot from the Telegram account whose ID is set in `ADMIN_ID`.
4. Send `/chats`.
5. Tap a listed chat to switch it between `❌ Blocked` and `✅ Allowed`.

Only media from allowed chats is copied to `TARGET_CHANNEL_ID`.
