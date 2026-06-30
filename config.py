from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_id: int
    target_channel_id: str | int
    database_path: str
    log_level: str


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable {name} is required")
    return value


def _parse_chat_id(value: str) -> str | int:
    if value.lstrip("-").isdigit():
        return int(value)
    return value


def load_settings() -> Settings:
    load_dotenv()

    try:
        admin_id = int(_required("ADMIN_ID"))
    except ValueError as exc:
        raise RuntimeError("ADMIN_ID must be an integer Telegram user ID") from exc

    return Settings(
        bot_token=_required("BOT_TOKEN"),
        admin_id=admin_id,
        target_channel_id=_parse_chat_id(_required("TARGET_CHANNEL_ID")),
        database_path=os.getenv("DATABASE_PATH", "data/bot.sqlite3"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
