from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import ChatMemberUpdated

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
