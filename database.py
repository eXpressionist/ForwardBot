from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

import aiosqlite


@dataclass(frozen=True)
class TrackedChat:
    chat_id: int
    chat_title: str
    is_whitelisted: bool
    updated_at: str


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        directory = os.path.dirname(self.path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tracked_chats (
                chat_id INTEGER PRIMARY KEY,
                chat_title TEXT NOT NULL,
                is_whitelisted INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
            """
        )
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database is not connected")
        return self._conn

    async def upsert_tracked_chat(self, chat_id: int, chat_title: str) -> None:
        await self.conn.execute(
            """
            INSERT INTO tracked_chats (chat_id, chat_title, is_whitelisted, updated_at)
            VALUES (?, ?, 0, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                chat_title = excluded.chat_title,
                updated_at = excluded.updated_at
            """,
            (chat_id, chat_title, _now_iso()),
        )
        await self.conn.commit()

    async def remove_tracked_chat(self, chat_id: int) -> None:
        await self.conn.execute("DELETE FROM tracked_chats WHERE chat_id = ?", (chat_id,))
        await self.conn.commit()

    async def list_tracked_chats(self) -> list[TrackedChat]:
        cursor = await self.conn.execute(
            """
            SELECT chat_id, chat_title, is_whitelisted, updated_at
            FROM tracked_chats
            ORDER BY is_whitelisted DESC, chat_title COLLATE NOCASE ASC
            """
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [_row_to_chat(row) for row in rows]

    async def get_tracked_chat(self, chat_id: int) -> TrackedChat | None:
        cursor = await self.conn.execute(
            """
            SELECT chat_id, chat_title, is_whitelisted, updated_at
            FROM tracked_chats
            WHERE chat_id = ?
            """,
            (chat_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        return _row_to_chat(row) if row else None

    async def is_chat_whitelisted(self, chat_id: int) -> bool:
        cursor = await self.conn.execute(
            "SELECT is_whitelisted FROM tracked_chats WHERE chat_id = ?",
            (chat_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        return bool(row and row["is_whitelisted"])

    async def toggle_whitelist(self, chat_id: int) -> TrackedChat | None:
        chat = await self.get_tracked_chat(chat_id)
        if chat is None:
            return None

        new_value = 0 if chat.is_whitelisted else 1
        await self.conn.execute(
            """
            UPDATE tracked_chats
            SET is_whitelisted = ?, updated_at = ?
            WHERE chat_id = ?
            """,
            (new_value, _now_iso(), chat_id),
        )
        await self.conn.commit()
        return await self.get_tracked_chat(chat_id)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _row_to_chat(row: aiosqlite.Row) -> TrackedChat:
    return TrackedChat(
        chat_id=row["chat_id"],
        chat_title=row["chat_title"],
        is_whitelisted=bool(row["is_whitelisted"]),
        updated_at=row["updated_at"],
    )
