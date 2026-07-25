"""Постоянное хранилище игровых сессий и PREMIUM-подписок в SQLite."""

from __future__ import annotations

import json
from pathlib import Path
import time
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
        await self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS premium_subscriptions (
                user_id INTEGER PRIMARY KEY,
                expires_at INTEGER NOT NULL DEFAULT 0,
                telegram_payment_charge_id TEXT NOT NULL DEFAULT '',
                provider_payment_charge_id TEXT NOT NULL DEFAULT '',
                last_amount INTEGER NOT NULL DEFAULT 0,
                currency TEXT NOT NULL DEFAULT 'XTR',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS premium_payments (
                telegram_payment_charge_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT NOT NULL,
                invoice_payload TEXT NOT NULL,
                expires_at INTEGER NOT NULL,
                created_at INTEGER NOT NULL,
                is_recurring INTEGER NOT NULL DEFAULT 0,
                is_first_recurring INTEGER NOT NULL DEFAULT 0,
                refunded INTEGER NOT NULL DEFAULT 0,
                recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
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
        """Удаляет только игровую сессию. PREMIUM при сбросе игры сохраняется."""
        connection = self._require_connection()
        await connection.execute("DELETE FROM sessions WHERE chat_id = ?", (chat_id,))
        await connection.commit()

    async def get_premium_status(self, user_id: int, now_ts: int | None = None) -> dict[str, Any]:
        connection = self._require_connection()
        async with connection.execute(
            """
            SELECT expires_at, telegram_payment_charge_id,
                   provider_payment_charge_id, last_amount, currency
            FROM premium_subscriptions
            WHERE user_id = ?
            """,
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()

        current = int(now_ts if now_ts is not None else time.time())
        if row is None:
            return {
                "active": False,
                "expires_at": 0,
                "telegram_payment_charge_id": "",
                "provider_payment_charge_id": "",
                "last_amount": 0,
                "currency": "XTR",
            }

        expires_at = int(row[0] or 0)
        return {
            "active": expires_at > current,
            "expires_at": expires_at,
            "telegram_payment_charge_id": row[1] or "",
            "provider_payment_charge_id": row[2] or "",
            "last_amount": int(row[3] or 0),
            "currency": row[4] or "XTR",
        }

    async def is_premium_active(self, user_id: int, now_ts: int | None = None) -> bool:
        return bool((await self.get_premium_status(user_id, now_ts))["active"])

    async def record_premium_payment(
        self,
        *,
        user_id: int,
        amount: int,
        currency: str,
        invoice_payload: str,
        expires_at: int,
        telegram_payment_charge_id: str,
        provider_payment_charge_id: str = "",
        created_at: int | None = None,
        is_recurring: bool = False,
        is_first_recurring: bool = False,
    ) -> bool:
        """Сохраняет платёж и продлевает PREMIUM. Возвращает True для нового платежа."""
        connection = self._require_connection()
        created = int(created_at if created_at is not None else time.time())

        cursor = await connection.execute(
            """
            INSERT OR IGNORE INTO premium_payments (
                telegram_payment_charge_id, user_id, amount, currency,
                invoice_payload, expires_at, created_at,
                is_recurring, is_first_recurring
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                telegram_payment_charge_id,
                user_id,
                amount,
                currency,
                invoice_payload,
                int(expires_at),
                created,
                int(bool(is_recurring)),
                int(bool(is_first_recurring)),
            ),
        )
        is_new = cursor.rowcount > 0

        await connection.execute(
            """
            INSERT INTO premium_subscriptions (
                user_id, expires_at, telegram_payment_charge_id,
                provider_payment_charge_id, last_amount, currency, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                expires_at = CASE
                    WHEN excluded.expires_at > premium_subscriptions.expires_at
                    THEN excluded.expires_at
                    ELSE premium_subscriptions.expires_at
                END,
                telegram_payment_charge_id = CASE
                    WHEN excluded.expires_at >= premium_subscriptions.expires_at
                    THEN excluded.telegram_payment_charge_id
                    ELSE premium_subscriptions.telegram_payment_charge_id
                END,
                provider_payment_charge_id = CASE
                    WHEN excluded.expires_at >= premium_subscriptions.expires_at
                    THEN excluded.provider_payment_charge_id
                    ELSE premium_subscriptions.provider_payment_charge_id
                END,
                last_amount = excluded.last_amount,
                currency = excluded.currency,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                int(expires_at),
                telegram_payment_charge_id,
                provider_payment_charge_id,
                amount,
                currency,
            ),
        )
        await connection.commit()
        return is_new

    async def mark_refunded(self, telegram_payment_charge_id: str) -> None:
        connection = self._require_connection()
        await connection.execute(
            """
            UPDATE premium_payments
            SET refunded = 1
            WHERE telegram_payment_charge_id = ?
            """,
            (telegram_payment_charge_id,),
        )
        await connection.execute(
            """
            UPDATE premium_subscriptions
            SET expires_at = 0, updated_at = CURRENT_TIMESTAMP
            WHERE telegram_payment_charge_id = ?
            """,
            (telegram_payment_charge_id,),
        )
        await connection.commit()

    async def get_setting(self, key: str) -> str | None:
        connection = self._require_connection()
        async with connection.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
        return None if row is None else str(row[0])

    async def set_setting(self, key: str, value: str) -> None:
        connection = self._require_connection()
        await connection.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value),
        )
        await connection.commit()
