from __future__ import annotations

import html

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import Settings
from database import Database, TrackedChat

router = Router(name="admin")


@router.message(Command("start"))
async def start(message: Message, settings: Settings) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None, settings):
        return

    await message.answer(
        "Bot is running. Add it to groups, then use /chats here to allow or block media copying."
    )


@router.message(Command("chats"))
async def list_chats(message: Message, db: Database, settings: Settings) -> None:
    if not _is_admin(message.from_user.id if message.from_user else None, settings):
        return

    chats = await db.list_tracked_chats()
    await message.answer(_menu_text(chats), reply_markup=_chats_keyboard(chats), parse_mode="HTML")


@router.callback_query(F.data.startswith("toggle_chat:"))
async def toggle_chat(callback: CallbackQuery, db: Database, settings: Settings) -> None:
    if not _is_admin(callback.from_user.id, settings):
        await callback.answer("Not allowed.", show_alert=True)
        return

    try:
        chat_id = int(callback.data.split(":", 1)[1]) if callback.data else 0
    except ValueError:
        await callback.answer("Invalid chat id.", show_alert=True)
        return

    updated = await db.toggle_whitelist(chat_id)
    if updated is None:
        await callback.answer("Chat is no longer tracked.", show_alert=True)
    else:
        status = "allowed" if updated.is_whitelisted else "blocked"
        await callback.answer(f"{updated.chat_title} is now {status}.")

    chats = await db.list_tracked_chats()
    if callback.message:
        await callback.message.edit_text(
            _menu_text(chats),
            reply_markup=_chats_keyboard(chats),
            parse_mode="HTML",
        )


def _is_admin(user_id: int | None, settings: Settings) -> bool:
    return user_id == settings.admin_id


def _menu_text(chats: list[TrackedChat]) -> str:
    if not chats:
        return (
            "<b>Tracked chats</b>\n\n"
            "No groups are tracked yet. Add the bot to a group, then open /chats again."
        )

    return (
        "<b>Tracked chats</b>\n\n"
        "Tap a chat to toggle whether media from it is copied to the target channel."
    )


def _chats_keyboard(chats: list[TrackedChat]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for chat in chats:
        status = "✅ Allowed" if chat.is_whitelisted else "❌ Blocked"
        title = _truncate_button_text(chat.chat_title)
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{status} · {title}",
                    callback_data=f"toggle_chat:{chat.chat_id}",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _truncate_button_text(text: str, limit: int = 42) -> str:
    unescaped = html.unescape(text).strip() or "Untitled chat"
    if len(unescaped) <= limit:
        return unescaped
    return f"{unescaped[: limit - 1]}…"
