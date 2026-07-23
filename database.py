"""Простое постоянное хранилище игровых сессий в SQLite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = await aiosqlite.connect(self.path)
        await self.connection.execute("PRAGMA journal_mode=WAL;")
        await self.connection.execute("PRAGMA synchronous=NORMAL;")
        await self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                chat_id INTEGER PRIMARY KEY,
                data_json TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await self.connection.commit()

    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.close()
            self.connection = None

    def _require_connection(self) -> aiosqlite.Connection:
        if self.connection is None:
            raise RuntimeError("Database.connect() должен быть вызван до работы с БД")
        return self.connection

    async def get_session(self, chat_id: int) -> dict[str, Any] | None:
        connection = self._require_connection()
        async with connection.execute(
            "SELECT data_json FROM sessions WHERE chat_id = ?", (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    async def save_session(self, chat_id: int, data: dict[str, Any]) -> None:
        connection = self._require_connection()
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        await connection.execute(
            """
            INSERT INTO sessions (chat_id, data_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id) DO UPDATE SET
                data_json = excluded.data_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (chat_id, payload),
        )
        await connection.commit()

    async def delete_session(self, chat_id: int) -> None:
        connection = self._require_connection()
        await connection.execute("DELETE FROM sessions WHERE chat_id = ?", (chat_id,))
        await connection.commit()
