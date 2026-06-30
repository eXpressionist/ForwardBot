from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from aiogram import Bot, Router
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import InputMediaDocument, InputMediaPhoto, InputMediaVideo, Message

from config import Settings
from database import Database

router = Router(name="media")
logger = logging.getLogger(__name__)

CAPTION_LIMIT = 1024
ALBUM_DEBOUNCE_SECONDS = 1.2

_albums: dict[str, "AlbumBucket"] = {}
_albums_lock = asyncio.Lock()


@dataclass
class AlbumBucket:
    chat_id: int
    media_group_id: str
    messages: list[Message] = field(default_factory=list)
    task: asyncio.Task[None] | None = None


@router.message()
async def copy_allowed_media(message: Message, db: Database, bot: Bot, settings: Settings) -> None:
    if message.chat.type not in {"group", "supergroup"}:
        return

    if not _has_supported_media(message):
        return

    if not _is_not_repost(message):
        logger.info(
            "Ignored non-original media from chat %s message %s",
            message.chat.id,
            message.message_id,
        )
        return

    await db.upsert_tracked_chat(message.chat.id, _source_title(message))

    if not await db.is_chat_whitelisted(message.chat.id):
        return

    if message.media_group_id:
        await _enqueue_album_message(message, bot, settings)
        return

    await _copy_single_message(message, bot, settings)


async def _enqueue_album_message(message: Message, bot: Bot, settings: Settings) -> None:
    key = f"{message.chat.id}:{message.media_group_id}"
    async with _albums_lock:
        bucket = _albums.get(key)
        if bucket is None:
            bucket = AlbumBucket(chat_id=message.chat.id, media_group_id=message.media_group_id)
            _albums[key] = bucket
        bucket.messages.append(message)

        if bucket.task is not None:
            bucket.task.cancel()
        bucket.task = asyncio.create_task(_flush_album_after_delay(key, bot, settings))


async def _flush_album_after_delay(key: str, bot: Bot, settings: Settings) -> None:
    try:
        await asyncio.sleep(ALBUM_DEBOUNCE_SECONDS)
        async with _albums_lock:
            bucket = _albums.pop(key, None)

        if bucket is None:
            return

        await _copy_album(bucket.messages, bot, settings)
    except asyncio.CancelledError:
        return
    except Exception:
        logger.exception("Failed to copy album %s", key)


async def _copy_album(messages: list[Message], bot: Bot, settings: Settings) -> None:
    supported = [
        message
        for message in messages
        if _has_supported_media(message) and _is_not_repost(message)
    ]
    if not supported:
        return

    supported.sort(key=lambda item: item.message_id)
    caption_message = next((item for item in supported if item.caption), supported[0])
    caption = _caption_with_source(
        caption_message.caption,
        _source_title(caption_message),
        _message_link(supported[0]),
    )

    media = []
    for index, message in enumerate(supported):
        item_caption = caption if index == 0 else None
        media_item = _message_to_input_media(message, item_caption)
        if media_item is not None:
            media.append(media_item)

    if not media:
        return

    try:
        await bot.send_media_group(chat_id=settings.target_channel_id, media=media)
    except TelegramRetryAfter as exc:
        logger.warning("Telegram flood control requested %.2f seconds for album", exc.retry_after)
        await asyncio.sleep(exc.retry_after)
        await bot.send_media_group(chat_id=settings.target_channel_id, media=media)
    except TelegramBadRequest:
        logger.exception("Telegram rejected album copy from chat %s", supported[0].chat.id)
    except Exception:
        logger.exception("Unexpected error while copying album from chat %s", supported[0].chat.id)


async def _copy_single_message(message: Message, bot: Bot, settings: Settings) -> None:
    caption = _caption_with_source(message.caption, _source_title(message), _message_link(message))
    await _copy_with_retry(message, bot, settings, caption=caption)


async def _copy_with_retry(
    message: Message,
    bot: Bot,
    settings: Settings,
    caption: str | None,
) -> None:
    try:
        await bot.copy_message(
            chat_id=settings.target_channel_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            caption=caption,
            parse_mode=None,
        )
    except TelegramRetryAfter as exc:
        logger.warning("Telegram flood control requested %.2f seconds", exc.retry_after)
        await asyncio.sleep(exc.retry_after)
        await bot.copy_message(
            chat_id=settings.target_channel_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            caption=caption,
            parse_mode=None,
        )
    except TelegramBadRequest:
        logger.exception(
            "Telegram rejected media copy from chat %s message %s",
            message.chat.id,
            message.message_id,
        )
    except Exception:
        logger.exception("Unexpected error while copying message %s", message.message_id)


def _has_supported_media(message: Message) -> bool:
    if message.photo or message.video:
        return True

    document = message.document
    if document and document.mime_type:
        return document.mime_type.startswith(("image/", "video/"))

    return False


def _is_not_repost(message: Message) -> bool:
    if getattr(message, "forward_origin", None) is not None:
        return False

    if getattr(message, "forward_date", None) is not None:
        return False

    if getattr(message, "is_automatic_forward", False):
        return False

    return True


def _message_to_input_media(
    message: Message,
    caption: str | None,
) -> InputMediaPhoto | InputMediaVideo | InputMediaDocument | None:
    if message.photo:
        return InputMediaPhoto(media=message.photo[-1].file_id, caption=caption, parse_mode=None)

    if message.video:
        return InputMediaVideo(media=message.video.file_id, caption=caption, parse_mode=None)

    if message.document and message.document.mime_type:
        if message.document.mime_type.startswith(("image/", "video/")):
            return InputMediaDocument(media=message.document.file_id, caption=caption, parse_mode=None)

    return None


def _caption_with_source(caption: str | None, source_title: str, source_url: str | None) -> str:
    source = f"\U0001f4e2 Source: {source_title}"
    if source_url:
        source = f"{source}\n{source_url}"

    suffix = f"\n\n{source}"
    base = (caption or "").strip()
    source_suffix = suffix.strip()

    if not base:
        return source_suffix[:CAPTION_LIMIT]

    available = CAPTION_LIMIT - len(suffix)
    if available <= 0:
        return source_suffix[:CAPTION_LIMIT]

    if len(base) > available:
        if available <= 3:
            base = base[:available].rstrip()
        else:
            base = base[: available - 3].rstrip() + "..."

    return f"{base}{suffix}"


def _source_title(message: Message) -> str:
    return message.chat.title or message.chat.full_name or str(message.chat.id)


def _message_link(message: Message) -> str | None:
    if message.chat.username:
        return f"https://t.me/{message.chat.username}/{message.message_id}"

    chat_id = str(message.chat.id)
    if chat_id.startswith("-100"):
        return f"https://t.me/c/{chat_id[4:]}/{message.message_id}"

    return None
