"""Все inline-клавиатуры MaksiShpi."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from words import CATEGORY_TITLES, FREE_CATEGORY_KEYS, PREMIUM_CATEGORY_KEYS


def welcome_keyboard(has_saved_players: bool, premium_active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    title = "▶️ Продолжить с настройками" if has_saved_players else "🎮 Начать игру"
    builder.button(text=title, callback_data="start_game")
    premium_title = "💎 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 активен" if premium_active else "💎 Открыть 𝗣𝗥𝗘𝗠𝗜𝗨𝗠"
    builder.button(text=premium_title, callback_data="premium")
    builder.button(text="📖 Как играть", callback_data="rules")
    if has_saved_players:
        builder.button(text="🧹 Сбросить всё", callback_data="reset")
    builder.adjust(1)
    return builder.as_markup()


def back_home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="home")]]
    )


def confirm_reset_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Да, сбросить", callback_data="reset_yes")],
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="home")],
        ]
    )


def player_count_keyboard(value: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➖", callback_data="pc:minus"),
                InlineKeyboardButton(text=f"👥 {value}", callback_data="noop"),
                InlineKeyboardButton(text="➕", callback_data="pc:plus"),
            ],
            [InlineKeyboardButton(text="Далее ➡️", callback_data="pc:ok")],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="home")],
        ]
    )


def spy_count_keyboard(value: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➖", callback_data="sc:minus"),
                InlineKeyboardButton(text=f"🕵️ {value}", callback_data="noop"),
                InlineKeyboardButton(text="➕", callback_data="sc:plus"),
            ],
            [InlineKeyboardButton(text="Готово ✅", callback_data="sc:ok")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="sc:back")],
        ]
    )


def category_keyboard(premium_active: bool, back_callback: str = "cat:back") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for key in FREE_CATEGORY_KEYS:
        builder.button(text=CATEGORY_TITLES[key], callback_data=f"cat:{key}")

    for key in ("all_premium", "adult", "professions"):
        title = CATEGORY_TITLES[key]
        if not premium_active:
            title = f"🔒 {title}"
        builder.button(text=title, callback_data=f"cat:{key}")

    builder.button(text="💎 𝗣𝗥𝗘𝗠𝗜𝗨𝗠", callback_data="premium")
    builder.button(text="⬅️ Назад", callback_data=back_callback)
    builder.adjust(1)
    return builder.as_markup()


def premium_main_keyboard(active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if active:
        builder.button(text="🗂 Открыть категории", callback_data="premium:categories")
    else:
        builder.button(text="⭐ Оформить за 50 ⭐", callback_data="premium:buy")
    builder.button(text="📜 Условия подписки", callback_data="terms")
    builder.button(text="⬅️ Главное меню", callback_data="home")
    builder.adjust(1)
    return builder.as_markup()


def premium_purchase_keyboard(
    invoice_url: str,
    *,
    back_callback: str = "home",
    back_text: str = "⬅️ Главное меню",
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐ Оплатить 50 ⭐", url=invoice_url)],
            [InlineKeyboardButton(text="🔄 Проверить доступ", callback_data="premium:check")],
            [InlineKeyboardButton(text="📜 Условия подписки", callback_data="terms")],
            [InlineKeyboardButton(text=back_text, callback_data=back_callback)],
        ]
    )


def premium_success_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗂 К выбору категории", callback_data="premium:categories")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")],
        ]
    )


def adult_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔞 Мне есть 18 лет — продолжить", callback_data="adult:confirm")],
            [InlineKeyboardButton(text="⬅️ Назад к категориям", callback_data="adult:back")],
        ]
    )


def name_input_keyboard(index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Оставить «Игрок {index + 1}»", callback_data=f"name:default:{index}"
                )
            ],
            [InlineKeyboardButton(text="❌ Отменить настройку", callback_data="home")],
        ]
    )


def setup_summary_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🎭 Раздать роли", callback_data="deal")
    builder.button(text="👥 Состав игроков", callback_data="roster")
    builder.button(text="🕵️ Количество шпионов", callback_data="edit_spies")
    builder.button(text="🗂 Категория", callback_data="edit_category")
    builder.button(text="💎 𝗣𝗥𝗘𝗠𝗜𝗨𝗠", callback_data="premium")
    builder.button(text="🔄 Настроить заново", callback_data="full_setup")
    builder.button(text="🏠 Главное меню", callback_data="home")
    builder.adjust(1, 2, 1, 1, 1)
    return builder.as_markup()


def roster_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Добавить", callback_data="roster:add"),
                InlineKeyboardButton(text="➖ Удалить", callback_data="roster:remove_menu"),
            ],
            [InlineKeyboardButton(text="✏️ Переименовать", callback_data="roster:rename_menu")],
            [InlineKeyboardButton(text="✅ Готово", callback_data="summary")],
        ]
    )


def indexed_players_keyboard(players: list[str], action: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, name in enumerate(players):
        builder.button(text=f"{index + 1}. {name}", callback_data=f"roster:{action}:{index}")
    builder.button(text="⬅️ Назад к составу", callback_data="roster")
    builder.adjust(1)
    return builder.as_markup()


def cancel_roster_input_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Отмена", callback_data="roster")]]
    )


def reveal_hidden_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👁 Показать мою роль", callback_data="role:show")]
        ]
    )


def reveal_visible_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я увидел", callback_data="role:seen")]
        ]
    )


def ready_round_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Начать раунд", callback_data="round:start")]
        ]
    )


def active_round_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏁 Завершить раунд", callback_data="round:end")]
        ]
    )


def end_round_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, показать итог", callback_data="round:finish")],
            [InlineKeyboardButton(text="↩️ Продолжить игру", callback_data="round:continue")],
        ]
    )


def result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔁 Следующий раунд", callback_data="next_round")],
            [InlineKeyboardButton(text="⚙️ Проверить настройки", callback_data="summary")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="home")],
        ]
    )
