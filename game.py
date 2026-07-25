"""Чистая игровая логика без Telegram API."""

from __future__ import annotations

import random
from typing import Any, Sequence

from words import CATEGORIES


MIN_PLAYERS = 3
MAX_PLAYERS = 20
MAX_SPIES_LIMIT = 5
MAX_NAME_LENGTH = 24


def default_session() -> dict[str, Any]:
    return {
        "state": "home",
        "player_count": 4,
        "spy_count": 1,
        "category": "all",
        "pending_category": None,
        "players": [],
        "draft_names": [],
        "name_index": 0,
        "return_to": None,
        "edit_index": None,
        "current_index": 0,
        "role_visible": False,
        "word": "",
        "spy_indexes": [],
        "round_no": 0,
        "last_word": "",
        "active_message_id": None,
    }


def merge_session(raw: dict[str, Any] | None) -> dict[str, Any]:
    session = default_session()
    if raw:
        session.update(raw)
    if session.get("category") not in CATEGORIES:
        session["category"] = "all"
    if session.get("pending_category") not in CATEGORIES:
        session["pending_category"] = None
    return session


def max_spies(player_count: int) -> int:
    """Оставляем минимум двух мирных игроков."""
    return max(1, min(MAX_SPIES_LIMIT, player_count - 2))


def clamp_spies(spy_count: int, player_count: int) -> int:
    return max(1, min(spy_count, max_spies(player_count)))


def clean_name(value: str) -> str:
    return " ".join(value.strip().split())


def validate_name(value: str, existing: Sequence[str], ignored_index: int | None = None) -> str | None:
    name = clean_name(value)
    if not name:
        return "Имя не может быть пустым."
    if len(name) > MAX_NAME_LENGTH:
        return f"Имя слишком длинное. Максимум {MAX_NAME_LENGTH} символа."
    lowered = name.casefold()
    for index, current in enumerate(existing):
        if ignored_index is not None and index == ignored_index:
            continue
        if current.casefold() == lowered:
            return "Такое имя уже есть в списке."
    return None


def choose_word(category: str, previous_word: str = "", rng: random.Random | None = None) -> str:
    generator = rng or random
    words = CATEGORIES.get(category, CATEGORIES["all"])
    if len(words) > 1 and previous_word:
        candidates = [word for word in words if word != previous_word]
        return generator.choice(candidates)
    return generator.choice(words)


def choose_spy_indexes(
    player_count: int, spy_count: int, rng: random.Random | None = None
) -> list[int]:
    if player_count < MIN_PLAYERS:
        raise ValueError(f"Минимум игроков: {MIN_PLAYERS}")
    allowed = max_spies(player_count)
    if not 1 <= spy_count <= allowed:
        raise ValueError(f"Для {player_count} игроков допустимо от 1 до {allowed} шпионов")
    generator = rng or random
    return sorted(generator.sample(range(player_count), spy_count))
