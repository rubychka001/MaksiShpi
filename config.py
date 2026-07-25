"""Загрузка настроек из файла .env."""

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _parse_admin_ids(raw_value: str) -> frozenset[int]:
    """Читает ADMIN_IDS в формате: 123456789,987654321."""
    result: set[int] = set()
    normalized = raw_value.replace(";", ",").replace(" ", ",")
    for item in normalized.split(","):
        value = item.strip()
        if not value:
            continue
        try:
            user_id = int(value)
        except ValueError as error:
            raise RuntimeError(
                f"Некорректный Telegram ID в ADMIN_IDS: {value!r}"
            ) from error
        if user_id <= 0:
            raise RuntimeError("ADMIN_IDS должен содержать положительные Telegram ID")
        result.add(user_id)
    return frozenset(result)


@dataclass(frozen=True, slots=True)
class Config:
    bot_token: str
    database_path: Path
    log_level: str
    welcome_sticker_id: str | None
    result_sticker_id: str | None
    admin_ids: frozenset[int]


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token or token == "ВСТАВЬТЕ_ТОКЕН_СЮДА":
        raise RuntimeError(
            "Не найден BOT_TOKEN. Скопируйте .env.example в .env и вставьте токен от BotFather."
        )

    raw_database_path = os.getenv("DATABASE_PATH", "data/maksishpi.db").strip()
    database_path = Path(raw_database_path)
    if not database_path.is_absolute():
        database_path = BASE_DIR / database_path

    return Config(
        bot_token=token,
        database_path=database_path,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        welcome_sticker_id=os.getenv("WELCOME_STICKER_ID", "").strip() or None,
        result_sticker_id=os.getenv("RESULT_STICKER_ID", "").strip() or None,
        admin_ids=_parse_admin_ids(os.getenv("ADMIN_IDS", "")),
    )
