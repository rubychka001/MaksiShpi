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
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL DEFAULT '',
                first_name TEXT NOT NULL DEFAULT '',
                last_name TEXT NOT NULL DEFAULT '',
                language_code TEXT NOT NULL DEFAULT '',
                is_bot INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER NOT NULL,
                source_chat_id INTEGER NOT NULL,
                source_message_id INTEGER NOT NULL,
                total INTEGER NOT NULL DEFAULT 0,
                delivered INTEGER NOT NULL DEFAULT 0,
                blocked INTEGER NOT NULL DEFAULT 0,
                failed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
            CREATE TABLE IF NOT EXISTS premium_manual_grants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                granted_by INTEGER NOT NULL,
                action TEXT NOT NULL,
                days INTEGER NOT NULL DEFAULT 0,
                previous_expires_at INTEGER NOT NULL DEFAULT 0,
                new_expires_at INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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

    async def grant_premium(
        self,
        *,
        user_id: int,
        days: int,
        granted_by: int,
        now_ts: int | None = None,
    ) -> dict[str, int]:
        """Вручную добавляет дни PREMIUM без списания Telegram Stars."""
        if user_id <= 0:
            raise ValueError("user_id должен быть положительным")
        if not 1 <= days <= 36500:
            raise ValueError("days должен быть от 1 до 36500")

        connection = self._require_connection()
        current_time = int(now_ts if now_ts is not None else time.time())
        status = await self.get_premium_status(user_id, current_time)
        previous_expires_at = int(status["expires_at"])
        base_expires_at = max(current_time, previous_expires_at)
        new_expires_at = base_expires_at + days * 24 * 60 * 60

        await connection.execute(
            """
            INSERT INTO premium_subscriptions (
                user_id, expires_at, telegram_payment_charge_id,
                provider_payment_charge_id, last_amount, currency, updated_at
            )
            VALUES (?, ?, '', '', 0, 'MANUAL', CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                expires_at = excluded.expires_at,
                telegram_payment_charge_id = '',
                provider_payment_charge_id = '',
                last_amount = 0,
                currency = 'MANUAL',
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, new_expires_at),
        )
        await connection.execute(
            """
            INSERT INTO premium_manual_grants (
                user_id, granted_by, action, days,
                previous_expires_at, new_expires_at
            )
            VALUES (?, ?, 'grant', ?, ?, ?)
            """,
            (user_id, granted_by, days, previous_expires_at, new_expires_at),
        )
        await connection.commit()
        return {
            "previous_expires_at": previous_expires_at,
            "expires_at": new_expires_at,
        }

    async def revoke_premium(
        self,
        *,
        user_id: int,
        revoked_by: int,
    ) -> dict[str, int]:
        """Вручную отключает локальный PREMIUM-доступ пользователя."""
        if user_id <= 0:
            raise ValueError("user_id должен быть положительным")

        connection = self._require_connection()
        status = await self.get_premium_status(user_id)
        previous_expires_at = int(status["expires_at"])

        await connection.execute(
            """
            INSERT INTO premium_subscriptions (
                user_id, expires_at, telegram_payment_charge_id,
                provider_payment_charge_id, last_amount, currency, updated_at
            )
            VALUES (?, 0, '', '', 0, 'MANUAL', CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                expires_at = 0,
                telegram_payment_charge_id = '',
                provider_payment_charge_id = '',
                last_amount = 0,
                currency = 'MANUAL',
                updated_at = CURRENT_TIMESTAMP
            """,
            (user_id,),
        )
        await connection.execute(
            """
            INSERT INTO premium_manual_grants (
                user_id, granted_by, action, days,
                previous_expires_at, new_expires_at
            )
            VALUES (?, ?, 'revoke', 0, ?, 0)
            """,
            (user_id, revoked_by, previous_expires_at),
        )
        await connection.commit()
        return {
            "previous_expires_at": previous_expires_at,
            "expires_at": 0,
        }

    async def migrate_session_users(self) -> None:
        """Добавляет в список рассылки старые chat_id из игровых сессий."""
        connection = self._require_connection()
        await connection.execute(
            """
            INSERT OR IGNORE INTO users (user_id, is_active, first_seen_at, last_seen_at)
            SELECT chat_id, 1, updated_at, updated_at
            FROM sessions
            WHERE chat_id > 0
            """
        )
        await connection.commit()

    async def upsert_user(
        self,
        *,
        user_id: int,
        username: str = "",
        first_name: str = "",
        last_name: str = "",
        language_code: str = "",
        is_bot: bool = False,
    ) -> None:
        """Создаёт пользователя или обновляет его публичные данные и активность."""
        if user_id <= 0:
            return
        connection = self._require_connection()
        await connection.execute(
            """
            INSERT INTO users (
                user_id, username, first_name, last_name, language_code,
                is_bot, is_active, first_seen_at, last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                language_code = excluded.language_code,
                is_bot = excluded.is_bot,
                is_active = 1,
                last_seen_at = CURRENT_TIMESTAMP
            """,
            (
                user_id,
                username or "",
                first_name or "",
                last_name or "",
                language_code or "",
                int(bool(is_bot)),
            ),
        )
        await connection.commit()

    async def mark_user_inactive(self, user_id: int) -> None:
        connection = self._require_connection()
        await connection.execute(
            "UPDATE users SET is_active = 0 WHERE user_id = ?",
            (user_id,),
        )
        await connection.commit()

    async def get_user(self, user_id: int) -> dict[str, Any] | None:
        connection = self._require_connection()
        async with connection.execute(
            """
            SELECT
                u.user_id, u.username, u.first_name, u.last_name,
                u.language_code, u.is_active, u.first_seen_at, u.last_seen_at,
                COALESCE(p.expires_at, 0), COALESCE(p.last_amount, 0),
                COALESCE(p.currency, '')
            FROM users AS u
            LEFT JOIN premium_subscriptions AS p ON p.user_id = u.user_id
            WHERE u.user_id = ?
            """,
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return {
            "user_id": int(row[0]),
            "username": row[1] or "",
            "first_name": row[2] or "",
            "last_name": row[3] or "",
            "language_code": row[4] or "",
            "is_active": bool(row[5]),
            "first_seen_at": row[6] or "",
            "last_seen_at": row[7] or "",
            "expires_at": int(row[8] or 0),
            "last_amount": int(row[9] or 0),
            "premium_currency": row[10] or "",
        }

    async def get_broadcast_user_ids(self) -> list[int]:
        connection = self._require_connection()
        async with connection.execute(
            """
            SELECT user_id
            FROM users
            WHERE is_active = 1 AND is_bot = 0
            ORDER BY user_id
            """
        ) as cursor:
            rows = await cursor.fetchall()
        return [int(row[0]) for row in rows]

    async def get_admin_statistics(self, now_ts: int | None = None) -> dict[str, int]:
        connection = self._require_connection()
        current = int(now_ts if now_ts is not None else time.time())

        async def scalar(query: str, params: tuple[Any, ...] = ()) -> int:
            async with connection.execute(query, params) as cursor:
                row = await cursor.fetchone()
            return int((row[0] if row else 0) or 0)

        total_users = await scalar("SELECT COUNT(*) FROM users WHERE is_bot = 0")
        reachable_users = await scalar(
            "SELECT COUNT(*) FROM users WHERE is_bot = 0 AND is_active = 1"
        )
        active_24h = await scalar(
            """
            SELECT COUNT(*) FROM users
            WHERE is_bot = 0 AND last_seen_at >= datetime('now', '-1 day')
            """
        )
        active_7d = await scalar(
            """
            SELECT COUNT(*) FROM users
            WHERE is_bot = 0 AND last_seen_at >= datetime('now', '-7 day')
            """
        )
        premium_active = await scalar(
            "SELECT COUNT(*) FROM premium_subscriptions WHERE expires_at > ?",
            (current,),
        )
        premium_paid = await scalar(
            """
            SELECT COUNT(*) FROM premium_subscriptions
            WHERE expires_at > ? AND currency = 'XTR' AND last_amount > 0
            """,
            (current,),
        )
        premium_manual = await scalar(
            """
            SELECT COUNT(*) FROM premium_subscriptions
            WHERE expires_at > ? AND currency = 'MANUAL'
            """,
            (current,),
        )
        payments_count = await scalar(
            "SELECT COUNT(*) FROM premium_payments WHERE refunded = 0"
        )
        stars_received = await scalar(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM premium_payments
            WHERE refunded = 0 AND currency = 'XTR'
            """
        )
        broadcasts_count = await scalar("SELECT COUNT(*) FROM broadcasts")

        rounds_played = 0
        async with connection.execute("SELECT data_json FROM sessions") as cursor:
            rows = await cursor.fetchall()
        for row in rows:
            try:
                rounds_played += int(json.loads(row[0]).get("round_no", 0) or 0)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue

        return {
            "total_users": total_users,
            "reachable_users": reachable_users,
            "active_24h": active_24h,
            "active_7d": active_7d,
            "premium_active": premium_active,
            "premium_paid": premium_paid,
            "premium_manual": premium_manual,
            "payments_count": payments_count,
            "stars_received": stars_received,
            "rounds_played": rounds_played,
            "broadcasts_count": broadcasts_count,
        }

    async def record_broadcast(
        self,
        *,
        admin_id: int,
        source_chat_id: int,
        source_message_id: int,
        total: int,
        delivered: int,
        blocked: int,
        failed: int,
    ) -> None:
        connection = self._require_connection()
        await connection.execute(
            """
            INSERT INTO broadcasts (
                admin_id, source_chat_id, source_message_id,
                total, delivered, blocked, failed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                admin_id, source_chat_id, source_message_id,
                total, delivered, blocked, failed,
            ),
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
