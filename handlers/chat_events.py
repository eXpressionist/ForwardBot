from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import ChatMemberUpdated, Message

from config import Settings
from database import Database

router = Router(name="chat_events")
logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {"member", "administrator"}
INACTIVE_STATUSES = {"left", "kicked"}


@router.my_chat_member()
async def track_chat_membership(event: ChatMemberUpdated, db: Database) -> None:
    chat = event.chat
    if chat.type not in {"group", "supergroup"}:
        return

    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status
    title = chat.title or chat.full_name or str(chat.id)

    if new_status in ACTIVE_STATUSES:
        await db.upsert_tracked_chat(chat.id, title)
        logger.info("Tracked chat %s (%s), status changed %s -> %s", title, chat.id, old_status, new_status)
        return

    if new_status in INACTIVE_STATUSES:
        await db.remove_tracked_chat(chat.id)
        logger.info("Removed chat %s (%s), status changed %s -> %s", title, chat.id, old_status, new_status)


@router.message(Command("track"))
async def track_chat_from_command(message: Message, db: Database, settings: Settings) -> None:
    if message.chat.type not in {"group", "supergroup"}:
        return

    title = message.chat.title or message.chat.full_name or str(message.chat.id)
    await db.upsert_tracked_chat(message.chat.id, title)
    logger.info("Tracked chat %s (%s) from /track command", title, message.chat.id)

    if message.from_user and message.from_user.id == settings.admin_id:
        await message.reply("Chat registered. Open /chats in private chat to allow or block it.")
