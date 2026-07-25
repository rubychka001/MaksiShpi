"""MaksiShpi — Telegram-бот для игры «Кто шпион?»."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import suppress
from html import escape
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import random
import time
from typing import Any

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from config import Config, load_config
from database import Database
from game import (
    MAX_PLAYERS,
    MIN_PLAYERS,
    choose_spy_indexes,
    choose_word,
    clamp_spies,
    clean_name,
    default_session,
    max_spies,
    merge_session,
    validate_name,
)
import keyboards as kb
import texts
from words import (
    CATEGORY_TITLES,
    contains_adult_content,
    is_premium_category,
)


PREMIUM_PRICE_STARS = texts.PREMIUM_PRICE_STARS
PREMIUM_PERIOD_SECONDS = 30 * 24 * 60 * 60
PREMIUM_PAYLOAD = "maksishpi_premium_monthly_v1"
PREMIUM_INVOICE_SETTING = "premium_invoice_link_v1"

router = Router(name=__name__)
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)

DB: Database
CONFIG: Config
CHAT_LOCKS: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
WAITING_FOR_STICKER_ID: set[int] = set()
logger = logging.getLogger("MaksiShpi")


async def get_session(chat_id: int) -> dict[str, Any]:
    return merge_session(await DB.get_session(chat_id))


async def save_session(chat_id: int, session: dict[str, Any]) -> None:
    await DB.save_session(chat_id, session)


async def answer_callback(
    callback: CallbackQuery, text: str | None = None, *, show_alert: bool = False
) -> None:
    """Не даёт устаревшему callback-запросу сломать игровой сценарий."""
    with suppress(TelegramBadRequest):
        await callback.answer(text=text, show_alert=show_alert)


async def cleanup_active_message(bot: Bot, chat_id: int, session: dict[str, Any]) -> None:
    message_id = session.get("active_message_id")
    if isinstance(message_id, int):
        with suppress(TelegramBadRequest, TelegramForbiddenError):
            await bot.delete_message(chat_id=chat_id, message_id=message_id)
    session["active_message_id"] = None


async def safe_edit(
    message: Message,
    text: str,
    reply_markup=None,
) -> None:
    try:
        await message.edit_text(text=text, reply_markup=reply_markup)
    except TelegramBadRequest as error:
        if "message is not modified" not in str(error).lower():
            raise


async def safe_delete(message: Message | None) -> None:
    if message is None:
        return
    with suppress(TelegramBadRequest, TelegramForbiddenError):
        await message.delete()


async def send_optional_sticker(bot: Bot, chat_id: int, sticker_id: str | None) -> None:
    if not sticker_id:
        return
    with suppress(TelegramBadRequest, TelegramForbiddenError):
        await bot.send_sticker(chat_id=chat_id, sticker=sticker_id)


async def show_home(message: Message, session: dict[str, Any], *, edit: bool = False) -> None:
    session["state"] = "home"
    session["role_visible"] = False
    session["word"] = ""
    session["spy_indexes"] = []
    session["current_index"] = 0
    session["active_message_id"] = None
    session["pending_category"] = None
    await save_session(message.chat.id, session)

    premium = await DB.get_premium_status(message.chat.id)
    markup = kb.welcome_keyboard(bool(session.get("players")), premium["active"])
    text = texts.welcome_text(premium["active"], premium["expires_at"])
    if edit:
        await safe_edit(message, text, markup)
    else:
        await message.answer(text, reply_markup=markup)


async def show_player_count(message: Message, session: dict[str, Any]) -> None:
    value = int(session.get("player_count", 4))
    await safe_edit(message, texts.player_count_text(value), kb.player_count_keyboard(value))


async def show_spy_count(message: Message, session: dict[str, Any]) -> None:
    count = int(session["spy_count"])
    maximum = max_spies(int(session["player_count"]))
    await safe_edit(message, texts.spy_count_text(count, maximum), kb.spy_count_keyboard(count))


async def show_category(message: Message) -> None:
    premium_active = await DB.is_premium_active(message.chat.id)
    await safe_edit(
        message,
        texts.category_text(premium_active),
        kb.category_keyboard(premium_active),
    )


async def show_summary(message: Message, session: dict[str, Any], *, edit: bool = True) -> None:
    if is_premium_category(str(session.get("category", "all"))):
        if not await DB.is_premium_active(message.chat.id):
            session["category"] = "all"
            session["pending_category"] = None

    session["state"] = "setup_review"
    session["player_count"] = len(session["players"])
    session["spy_count"] = clamp_spies(int(session["spy_count"]), len(session["players"]))
    session["return_to"] = None
    session["edit_index"] = None
    await save_session(message.chat.id, session)
    if edit:
        await safe_edit(message, texts.settings_summary(session), kb.setup_summary_keyboard())
    else:
        await message.answer(texts.settings_summary(session), reply_markup=kb.setup_summary_keyboard())


async def show_roster(message: Message, session: dict[str, Any], *, edit: bool = True) -> None:
    session["state"] = "roster"
    session["edit_index"] = None
    await save_session(message.chat.id, session)
    if edit:
        await safe_edit(message, texts.roster_text(session["players"]), kb.roster_keyboard())
    else:
        await message.answer(texts.roster_text(session["players"]), reply_markup=kb.roster_keyboard())


async def get_premium_invoice_link(bot: Bot) -> str:
    saved = await DB.get_setting(PREMIUM_INVOICE_SETTING)
    if saved:
        return saved

    link = await bot.create_invoice_link(
        title="MaksiShpi PREMIUM",
        description=(
            "Все PREMIUM-категории на 30 дней. "
            "Автоматическое продление каждые 30 дней за 50 Telegram Stars."
        ),
        payload=PREMIUM_PAYLOAD,
        currency="XTR",
        prices=[LabeledPrice(label="PREMIUM — 30 дней", amount=PREMIUM_PRICE_STARS)],
        provider_token="",
        subscription_period=PREMIUM_PERIOD_SECONDS,
    )
    await DB.set_setting(PREMIUM_INVOICE_SETTING, link)
    return link


def enum_value(value: Any) -> str:
    return str(getattr(value, "value", value or ""))


async def sync_recent_premium_transactions(bot: Bot) -> None:
    """Восстанавливает активные подписки из истории Stars после потери локальной БД."""
    now = int(time.time())
    incoming: list[Any] = []
    refunded_ids: set[str] = set()
    offset = 0

    try:
        for _ in range(10):
            result = await bot.get_star_transactions(offset=offset, limit=100)
            transactions = list(getattr(result, "transactions", []) or [])
            if not transactions:
                break

            for transaction in transactions:
                transaction_id = str(getattr(transaction, "id", "") or "")
                if getattr(transaction, "receiver", None) is not None and transaction_id:
                    refunded_ids.add(transaction_id)
                if getattr(transaction, "source", None) is not None:
                    incoming.append(transaction)

            if len(transactions) < 100:
                break
            offset += len(transactions)
    except Exception as error:
        logger.warning("Не удалось синхронизировать историю Telegram Stars: %s", error)
        return

    restored = 0
    for transaction in incoming:
        source = getattr(transaction, "source", None)
        if source is None:
            continue
        if enum_value(getattr(source, "type", "")) != "user":
            continue
        if enum_value(getattr(source, "transaction_type", "")) != "invoice_payment":
            continue
        if getattr(source, "invoice_payload", None) != PREMIUM_PAYLOAD:
            continue
        if int(getattr(source, "subscription_period", 0) or 0) != PREMIUM_PERIOD_SECONDS:
            continue

        transaction_id = str(getattr(transaction, "id", "") or "")
        if not transaction_id or transaction_id in refunded_ids:
            continue

        user = getattr(source, "user", None)
        user_id = getattr(user, "id", None)
        created_at = int(getattr(transaction, "date", 0) or 0)
        amount = int(getattr(transaction, "amount", 0) or 0)
        expires_at = created_at + PREMIUM_PERIOD_SECONDS

        if not isinstance(user_id, int):
            continue
        if amount != PREMIUM_PRICE_STARS or expires_at <= now:
            continue

        is_new = await DB.record_premium_payment(
            user_id=user_id,
            amount=amount,
            currency="XTR",
            invoice_payload=PREMIUM_PAYLOAD,
            expires_at=expires_at,
            telegram_payment_charge_id=transaction_id,
            created_at=created_at,
            is_recurring=True,
        )
        restored += int(is_new)

    if restored:
        logger.info("Из истории Telegram Stars восстановлено PREMIUM-платежей: %s", restored)


async def finish_category_selection(
    message: Message,
    session: dict[str, Any],
    category: str,
) -> None:
    previous_state = session["state"]
    session["category"] = category
    session["pending_category"] = None

    if previous_state == "edit_category":
        await show_summary(message, session)
        return

    session["state"] = "setup_names"
    session["draft_names"] = []
    session["name_index"] = 0
    session["players"] = []
    await save_session(message.chat.id, session)
    await safe_edit(
        message,
        texts.name_prompt(0, session["player_count"]),
        kb.name_input_keyboard(0),
    )


@router.message(CommandStart())
async def command_start(message: Message, bot: Bot) -> None:
    async with CHAT_LOCKS[message.chat.id]:
        session = await get_session(message.chat.id)
        await cleanup_active_message(bot, message.chat.id, session)
        await send_optional_sticker(bot, message.chat.id, CONFIG.welcome_sticker_id)
        await show_home(message, session)


@router.message(Command("help"))
async def command_help(message: Message) -> None:
    await message.answer(texts.RULES, reply_markup=kb.back_home_keyboard())


@router.message(Command("premium"))
async def command_premium(message: Message) -> None:
    premium = await DB.get_premium_status(message.from_user.id)
    await message.answer(
        texts.premium_info_text(premium["active"], premium["expires_at"]),
        reply_markup=kb.premium_main_keyboard(premium["active"]),
    )


@router.message(Command("paysupport"))
async def command_paysupport(message: Message) -> None:
    await message.answer(texts.PAY_SUPPORT, reply_markup=kb.back_home_keyboard())


@router.message(Command("terms"))
async def command_terms(message: Message) -> None:
    await message.answer(texts.TERMS, reply_markup=kb.back_home_keyboard())


@router.message(Command("cancel"))
async def command_cancel(message: Message, bot: Bot) -> None:
    async with CHAT_LOCKS[message.chat.id]:
        session = await get_session(message.chat.id)
        await cleanup_active_message(bot, message.chat.id, session)
        session["word"] = ""
        session["spy_indexes"] = []
        session["current_index"] = 0
        await show_home(message, session)


@router.message(Command("stickerid"))
async def command_sticker_id(message: Message) -> None:
    WAITING_FOR_STICKER_ID.add(message.chat.id)
    await message.answer(
        "Отправьте мне нужный стикер следующим сообщением. "
        "Я покажу его <code>file_id</code> для файла .env."
    )


@router.message(F.sticker)
async def receive_sticker_id(message: Message) -> None:
    if message.chat.id not in WAITING_FOR_STICKER_ID:
        return
    WAITING_FOR_STICKER_ID.discard(message.chat.id)
    await message.answer(
        "Скопируйте значение ниже в <code>WELCOME_STICKER_ID</code> "
        "или <code>RESULT_STICKER_ID</code>:\n\n"
        f"<code>{message.sticker.file_id}</code>"
    )


@router.pre_checkout_query()
async def process_pre_checkout(query: PreCheckoutQuery) -> None:
    valid = (
        query.invoice_payload == PREMIUM_PAYLOAD
        and query.currency == "XTR"
        and query.total_amount == PREMIUM_PRICE_STARS
    )
    if valid:
        await query.answer(ok=True)
    else:
        await query.answer(
            ok=False,
            error_message=(
                "Не удалось проверить параметры подписки. "
                "Закройте оплату и попробуйте оформить PREMIUM заново."
            ),
        )


@router.message(F.successful_payment)
async def process_successful_payment(message: Message) -> None:
    payment = message.successful_payment
    if payment is None:
        return
    if (
        payment.invoice_payload != PREMIUM_PAYLOAD
        or payment.currency != "XTR"
        or payment.total_amount != PREMIUM_PRICE_STARS
    ):
        logger.error("Получен платёж с неожиданными параметрами: %r", payment)
        await message.answer(texts.PAY_SUPPORT)
        return

    now = int(time.time())
    expires_at = int(
        payment.subscription_expiration_date
        or (now + PREMIUM_PERIOD_SECONDS)
    )
    user_id = message.from_user.id if message.from_user else message.chat.id
    first_payment = bool(payment.is_first_recurring)

    is_new = await DB.record_premium_payment(
        user_id=user_id,
        amount=payment.total_amount,
        currency=payment.currency,
        invoice_payload=payment.invoice_payload,
        expires_at=expires_at,
        telegram_payment_charge_id=payment.telegram_payment_charge_id,
        provider_payment_charge_id=payment.provider_payment_charge_id or "",
        created_at=now,
        is_recurring=bool(payment.is_recurring),
        is_first_recurring=first_payment,
    )
    if not is_new:
        return

    await message.answer(
        texts.premium_success_text(expires_at, first_payment),
        reply_markup=kb.premium_success_keyboard(),
    )


@router.message(F.refunded_payment)
async def process_refunded_payment(message: Message) -> None:
    refunded = message.refunded_payment
    if refunded is None or refunded.invoice_payload != PREMIUM_PAYLOAD:
        return
    await DB.mark_refunded(refunded.telegram_payment_charge_id)
    await message.answer(
        "<b>↩️ Платёж возвращён</b>\n\n"
        "Доступ 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 по этому платежу отключён. "
        "По вопросам возврата используйте /paysupport."
    )


@router.message(F.bot_subscription_updated)
async def process_subscription_update(message: Message) -> None:
    update = message.bot_subscription_updated
    if update is None or update.invoice_payload != PREMIUM_PAYLOAD:
        return
    state = enum_value(update.state)
    if state == "canceled":
        premium = await DB.get_premium_status(update.user.id)
        await message.answer(
            "<b>ℹ️ Автопродление PREMIUM отменено</b>\n\n"
            f"Доступ сохранится до <b>{texts.format_premium_date(premium['expires_at'])}</b>."
        )
    elif state == "failed":
        await message.answer(
            "<b>⚠️ Не удалось продлить PREMIUM</b>\n\n"
            "Проверьте баланс Telegram Stars. До окончания уже оплаченного периода "
            "доступ продолжит работать."
        )
    elif state == "active":
        await message.answer(
            "<b>✅ Автопродление PREMIUM снова включено</b>"
        )


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery) -> None:
    await answer_callback(callback)


@router.callback_query(F.data == "rules")
async def callback_rules(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    await safe_edit(callback.message, texts.RULES, kb.back_home_keyboard())


@router.callback_query(F.data == "terms")
async def callback_terms(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    await safe_edit(callback.message, texts.TERMS, kb.back_home_keyboard())


@router.callback_query(F.data == "home")
async def callback_home(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        await show_home(callback.message, session, edit=True)


@router.callback_query(F.data == "premium")
async def callback_premium(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    premium = await DB.get_premium_status(callback.from_user.id)
    await safe_edit(
        callback.message,
        texts.premium_info_text(premium["active"], premium["expires_at"]),
        kb.premium_main_keyboard(premium["active"]),
    )


@router.callback_query(F.data == "premium:buy")
async def callback_premium_buy(callback: CallbackQuery, bot: Bot) -> None:
    await answer_callback(callback)
    premium = await DB.get_premium_status(callback.from_user.id)
    if premium["active"]:
        await safe_edit(
            callback.message,
            texts.premium_info_text(True, premium["expires_at"]),
            kb.premium_main_keyboard(True),
        )
        return

    try:
        invoice_url = await get_premium_invoice_link(bot)
    except TelegramBadRequest as error:
        logger.exception("Ошибка создания ссылки подписки")
        await answer_callback(
            callback,
            f"Не удалось создать счёт: {error}",
            show_alert=True,
        )
        return

    await safe_edit(
        callback.message,
        texts.PREMIUM_LOCKED,
        kb.premium_purchase_keyboard(invoice_url),
    )


@router.callback_query(F.data == "premium:check")
async def callback_premium_check(callback: CallbackQuery) -> None:
    premium = await DB.get_premium_status(callback.from_user.id)
    if premium["active"]:
        await answer_callback(callback, "PREMIUM активен")
        await safe_edit(
            callback.message,
            texts.premium_info_text(True, premium["expires_at"]),
            kb.premium_main_keyboard(True),
        )
    else:
        await answer_callback(
            callback,
            "Оплата пока не найдена. Если звёзды уже списались — откройте /paysupport.",
            show_alert=True,
        )


@router.callback_query(F.data == "premium:back_categories")
async def callback_premium_back_categories(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    await show_category(callback.message)


@router.callback_query(F.data == "premium:categories")
async def callback_premium_categories(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        if len(session.get("players", [])) >= MIN_PLAYERS:
            session["state"] = "edit_category"
            await save_session(callback.message.chat.id, session)
            await show_category(callback.message)
            return

        session["state"] = "setup_player_count"
        session["return_to"] = "initial"
        await save_session(callback.message.chat.id, session)
        await show_player_count(callback.message, session)


@router.callback_query(F.data == "reset")
async def callback_reset(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    await safe_edit(
        callback.message,
        "<b>🧹 Сбросить игру?</b>\n\n"
        "Будут удалены сохранённые игроки, настройки и текущий раунд. "
        "Подписка PREMIUM сохранится.",
        kb.confirm_reset_keyboard(),
    )


@router.callback_query(F.data == "reset_yes")
async def callback_reset_yes(callback: CallbackQuery) -> None:
    await answer_callback(callback, "Настройки игры удалены")
    async with CHAT_LOCKS[callback.message.chat.id]:
        await DB.delete_session(callback.message.chat.id)
        session = default_session()
        await show_home(callback.message, session, edit=True)


@router.callback_query(F.data == "start_game")
async def callback_start_game(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        if len(session.get("players", [])) >= MIN_PLAYERS:
            await show_summary(callback.message, session)
            return
        session["state"] = "setup_player_count"
        session["player_count"] = max(MIN_PLAYERS, int(session.get("player_count", 4)))
        session["spy_count"] = clamp_spies(int(session.get("spy_count", 1)), session["player_count"])
        session["return_to"] = "initial"
        await save_session(callback.message.chat.id, session)
        await show_player_count(callback.message, session)


@router.callback_query(F.data == "full_setup")
async def callback_full_setup(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        old = await get_session(callback.message.chat.id)
        session = default_session()
        session["round_no"] = old.get("round_no", 0)
        session["last_word"] = old.get("last_word", "")
        session["state"] = "setup_player_count"
        session["return_to"] = "initial"
        await save_session(callback.message.chat.id, session)
        await show_player_count(callback.message, session)


@router.callback_query(F.data.startswith("pc:"))
async def callback_player_count(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        if session["state"] != "setup_player_count":
            await answer_callback(callback, "Этот экран уже неактуален", show_alert=True)
            return
        action = callback.data.split(":", 1)[1]
        value = int(session["player_count"])
        if action == "minus":
            value = max(MIN_PLAYERS, value - 1)
        elif action == "plus":
            value = min(MAX_PLAYERS, value + 1)
        elif action == "ok":
            session["player_count"] = value
            session["spy_count"] = clamp_spies(int(session["spy_count"]), value)
            session["state"] = "setup_spy_count"
            await save_session(callback.message.chat.id, session)
            await show_spy_count(callback.message, session)
            return
        session["player_count"] = value
        session["spy_count"] = clamp_spies(int(session["spy_count"]), value)
        await save_session(callback.message.chat.id, session)
        await show_player_count(callback.message, session)


@router.callback_query(F.data.startswith("sc:"))
async def callback_spy_count(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        if session["state"] not in {"setup_spy_count", "edit_spy_count"}:
            await answer_callback(callback, "Этот экран уже неактуален", show_alert=True)
            return
        action = callback.data.split(":", 1)[1]
        current = int(session["spy_count"])
        maximum = max_spies(int(session["player_count"]))
        if action == "minus":
            current = max(1, current - 1)
        elif action == "plus":
            current = min(maximum, current + 1)
        elif action == "back":
            if session["state"] == "edit_spy_count":
                await show_summary(callback.message, session)
            else:
                session["state"] = "setup_player_count"
                await save_session(callback.message.chat.id, session)
                await show_player_count(callback.message, session)
            return
        elif action == "ok":
            session["spy_count"] = current
            if session["state"] == "edit_spy_count":
                await show_summary(callback.message, session)
            else:
                session["state"] = "setup_category"
                await save_session(callback.message.chat.id, session)
                await show_category(callback.message)
            return
        session["spy_count"] = current
        await save_session(callback.message.chat.id, session)
        await show_spy_count(callback.message, session)


@router.callback_query(F.data == "edit_spies")
async def callback_edit_spies(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        session["state"] = "edit_spy_count"
        session["player_count"] = len(session["players"])
        session["spy_count"] = clamp_spies(session["spy_count"], session["player_count"])
        await save_session(callback.message.chat.id, session)
        await show_spy_count(callback.message, session)


@router.callback_query(F.data == "edit_category")
async def callback_edit_category(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        session["state"] = "edit_category"
        session["pending_category"] = None
        await save_session(callback.message.chat.id, session)
        await show_category(callback.message)


@router.callback_query(F.data.startswith("cat:"))
async def callback_category(callback: CallbackQuery, bot: Bot) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        if session["state"] not in {"setup_category", "edit_category"}:
            await answer_callback(callback, "Этот экран уже неактуален", show_alert=True)
            return

        action = callback.data.split(":", 1)[1]
        if action == "back":
            if session["state"] == "edit_category":
                await show_summary(callback.message, session)
            else:
                session["state"] = "setup_spy_count"
                await save_session(callback.message.chat.id, session)
                await show_spy_count(callback.message, session)
            return
        if action not in CATEGORY_TITLES:
            return

        if is_premium_category(action):
            premium_active = await DB.is_premium_active(callback.from_user.id)
            if not premium_active:
                try:
                    invoice_url = await get_premium_invoice_link(bot)
                except TelegramBadRequest:
                    logger.exception("Ошибка создания ссылки подписки")
                    await answer_callback(
                        callback,
                        "Не удалось создать счёт. Попробуйте позже.",
                        show_alert=True,
                    )
                    return
                await safe_edit(
                    callback.message,
                    texts.PREMIUM_LOCKED,
                    kb.premium_purchase_keyboard(
                        invoice_url,
                        back_callback="premium:back_categories",
                        back_text="⬅️ К категориям",
                    ),
                )
                return

        if contains_adult_content(action):
            session["pending_category"] = action
            await save_session(callback.message.chat.id, session)
            await safe_edit(
                callback.message,
                texts.adult_confirmation_text(action),
                kb.adult_confirmation_keyboard(),
            )
            return

        await finish_category_selection(callback.message, session, action)


@router.callback_query(F.data == "adult:back")
async def callback_adult_back(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        session["pending_category"] = None
        await save_session(callback.message.chat.id, session)
        await show_category(callback.message)


@router.callback_query(F.data == "adult:confirm")
async def callback_adult_confirm(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        category = session.get("pending_category")
        if not isinstance(category, str) or not contains_adult_content(category):
            await answer_callback(callback, "Выбор категории устарел", show_alert=True)
            return
        if not await DB.is_premium_active(callback.from_user.id):
            session["pending_category"] = None
            await save_session(callback.message.chat.id, session)
            await answer_callback(callback, "Подписка PREMIUM не активна", show_alert=True)
            await show_category(callback.message)
            return
        await finish_category_selection(callback.message, session, category)


async def accept_draft_name(message: Message, name: str, session: dict[str, Any]) -> None:
    draft = list(session.get("draft_names", []))
    error = validate_name(name, draft)
    if error:
        await message.answer(f"⚠️ {error}")
        return
    draft.append(clean_name(name))
    session["draft_names"] = draft
    session["name_index"] = len(draft)
    if len(draft) >= int(session["player_count"]):
        session["players"] = draft
        session["draft_names"] = []
        session["state"] = "setup_review"
        await save_session(message.chat.id, session)
        await show_summary(message, session, edit=False)
        return
    await save_session(message.chat.id, session)
    await message.answer(
        texts.name_prompt(len(draft), int(session["player_count"])),
        reply_markup=kb.name_input_keyboard(len(draft)),
    )


@router.callback_query(F.data.startswith("name:default:"))
async def callback_default_name(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        if session["state"] != "setup_names":
            return
        index = len(session.get("draft_names", []))
        try:
            expected_index = int(callback.data.rsplit(":", 1)[1])
        except ValueError:
            return
        if expected_index != index:
            await answer_callback(callback, "Этот экран уже неактуален", show_alert=True)
            return
        await safe_delete(callback.message)
        await accept_draft_name(callback.message, f"Игрок {index + 1}", session)


@router.message(F.text)
async def receive_text(message: Message) -> None:
    if message.text.startswith("/"):
        return
    async with CHAT_LOCKS[message.chat.id]:
        session = await get_session(message.chat.id)
        state = session["state"]
        if state == "setup_names":
            await accept_draft_name(message, message.text, session)
            return
        if state == "roster_add":
            error = validate_name(message.text, session["players"])
            if error:
                await message.answer(f"⚠️ {error}", reply_markup=kb.cancel_roster_input_keyboard())
                return
            if len(session["players"]) >= MAX_PLAYERS:
                await message.answer(f"Достигнут максимум: {MAX_PLAYERS} игроков.")
                return
            session["players"].append(clean_name(message.text))
            session["player_count"] = len(session["players"])
            session["spy_count"] = clamp_spies(session["spy_count"], session["player_count"])
            await save_session(message.chat.id, session)
            await show_roster(message, session, edit=False)
            return
        if state == "roster_rename":
            index = session.get("edit_index")
            if not isinstance(index, int) or not 0 <= index < len(session["players"]):
                await message.answer("Не удалось определить игрока. Вернитесь в меню состава.")
                return
            error = validate_name(message.text, session["players"], ignored_index=index)
            if error:
                await message.answer(f"⚠️ {error}", reply_markup=kb.cancel_roster_input_keyboard())
                return
            session["players"][index] = clean_name(message.text)
            await save_session(message.chat.id, session)
            await show_roster(message, session, edit=False)
            return
        await message.answer(
            "Используйте кнопки под сообщением. Для возврата в начало отправьте /start."
        )


@router.callback_query(F.data == "summary")
async def callback_summary(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        if len(session["players"]) < MIN_PLAYERS:
            await answer_callback(callback, f"Нужно минимум {MIN_PLAYERS} игрока", show_alert=True)
            return
        await show_summary(callback.message, session)


@router.callback_query(F.data == "roster")
async def callback_roster(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        await show_roster(callback.message, session)


@router.callback_query(F.data == "roster:add")
async def callback_roster_add(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        if len(session["players"]) >= MAX_PLAYERS:
            await answer_callback(callback, f"Максимум {MAX_PLAYERS} игроков", show_alert=True)
            return
        session["state"] = "roster_add"
        await save_session(callback.message.chat.id, session)
        await safe_edit(
            callback.message,
            "<b>➕ Новый игрок</b>\n\nОтправьте его имя одним сообщением.",
            kb.cancel_roster_input_keyboard(),
        )


@router.callback_query(F.data == "roster:remove_menu")
async def callback_remove_menu(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        if len(session["players"]) <= MIN_PLAYERS:
            await answer_callback(
                callback,
                f"В игре должно остаться минимум {MIN_PLAYERS} игрока",
                show_alert=True,
            )
            return
        await safe_edit(
            callback.message,
            "<b>➖ Кого удалить?</b>\n\nНажмите на имя игрока.",
            kb.indexed_players_keyboard(session["players"], "remove"),
        )


@router.callback_query(F.data.startswith("roster:remove:"))
async def callback_remove_player(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        if len(session["players"]) <= MIN_PLAYERS:
            await answer_callback(callback, f"Минимум {MIN_PLAYERS} игрока", show_alert=True)
            return
        with suppress(ValueError):
            index = int(callback.data.rsplit(":", 1)[1])
            if 0 <= index < len(session["players"]):
                removed = session["players"].pop(index)
                session["player_count"] = len(session["players"])
                session["spy_count"] = clamp_spies(session["spy_count"], session["player_count"])
                await save_session(callback.message.chat.id, session)
                await answer_callback(callback, f"Удалён: {removed}")
        await show_roster(callback.message, session)


@router.callback_query(F.data == "roster:rename_menu")
async def callback_rename_menu(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        await safe_edit(
            callback.message,
            "<b>✏️ Кого переименовать?</b>\n\nНажмите на имя игрока.",
            kb.indexed_players_keyboard(session["players"], "rename"),
        )


@router.callback_query(F.data.startswith("roster:rename:"))
async def callback_rename_player(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        try:
            index = int(callback.data.rsplit(":", 1)[1])
        except ValueError:
            return
        if not 0 <= index < len(session["players"]):
            return
        session["state"] = "roster_rename"
        session["edit_index"] = index
        await save_session(callback.message.chat.id, session)
        await safe_edit(
            callback.message,
            f"<b>✏️ Новое имя</b>\n\n"
            f"Сейчас: <b>{escape(session['players'][index])}</b>\n"
            "Отправьте новое имя одним сообщением.",
            kb.cancel_roster_input_keyboard(),
        )


@router.callback_query(F.data == "deal")
async def callback_deal(callback: CallbackQuery, bot: Bot) -> None:
    await answer_callback(callback)
    chat_id = callback.message.chat.id
    async with CHAT_LOCKS[chat_id]:
        session = await get_session(chat_id)
        players = session.get("players", [])
        if len(players) < MIN_PLAYERS:
            await answer_callback(callback, f"Нужно минимум {MIN_PLAYERS} игрока", show_alert=True)
            return

        category = str(session.get("category", "all"))
        if is_premium_category(category) and not await DB.is_premium_active(callback.from_user.id):
            session["category"] = "all"
            session["state"] = "edit_category"
            session["pending_category"] = None
            await save_session(chat_id, session)
            await safe_edit(
                callback.message,
                texts.category_text(False)
                + "\n\n⚠️ <b>Срок PREMIUM закончился.</b> Выберите бесплатную категорию "
                  "или оформите подписку заново.",
                kb.category_keyboard(False),
            )
            return

        session["player_count"] = len(players)
        session["spy_count"] = clamp_spies(int(session["spy_count"]), len(players))
        session["word"] = choose_word(category, session.get("last_word", ""))
        session["last_word"] = session["word"]
        session["spy_indexes"] = choose_spy_indexes(len(players), session["spy_count"])
        session["current_index"] = 0
        session["role_visible"] = False
        session["round_no"] = int(session.get("round_no", 0)) + 1
        session["state"] = "reveal_hidden"
        await save_session(chat_id, session)
        await safe_delete(callback.message)
        sent = await bot.send_message(
            chat_id,
            texts.handoff_text(players[0], 0, len(players)),
            reply_markup=kb.reveal_hidden_keyboard(),
        )
        session["active_message_id"] = sent.message_id
        await save_session(chat_id, session)


@router.callback_query(F.data == "role:show")
async def callback_show_role(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    chat_id = callback.message.chat.id
    async with CHAT_LOCKS[chat_id]:
        session = await get_session(chat_id)
        if session["state"] != "reveal_hidden" or session.get("role_visible"):
            await answer_callback(
                callback,
                "Роль уже была открыта или экран устарел",
                show_alert=True,
            )
            return
        index = int(session["current_index"])
        if not 0 <= index < len(session["players"]):
            await answer_callback(
                callback,
                "Ошибка очереди игроков. Начните раздачу заново.",
                show_alert=True,
            )
            return
        is_spy = index in session["spy_indexes"]
        session["role_visible"] = True
        session["state"] = "reveal_visible"
        await save_session(chat_id, session)
        await safe_edit(
            callback.message,
            texts.role_text(is_spy, session["word"]),
            kb.reveal_visible_keyboard(),
        )


@router.callback_query(F.data == "role:seen")
async def callback_role_seen(callback: CallbackQuery, bot: Bot) -> None:
    await answer_callback(callback)
    chat_id = callback.message.chat.id
    async with CHAT_LOCKS[chat_id]:
        session = await get_session(chat_id)
        if session["state"] != "reveal_visible" or not session.get("role_visible"):
            await answer_callback(callback, "Этот экран уже неактуален", show_alert=True)
            return
        await safe_delete(callback.message)
        next_index = int(session["current_index"]) + 1
        session["current_index"] = next_index
        session["role_visible"] = False
        if next_index < len(session["players"]):
            session["state"] = "reveal_hidden"
            sent = await bot.send_message(
                chat_id,
                texts.handoff_text(
                    session["players"][next_index],
                    next_index,
                    len(session["players"]),
                ),
                reply_markup=kb.reveal_hidden_keyboard(),
            )
            session["active_message_id"] = sent.message_id
        else:
            session["state"] = "ready_to_start"
            sent = await bot.send_message(
                chat_id,
                texts.all_roles_ready_text(session["round_no"]),
                reply_markup=kb.ready_round_keyboard(),
            )
            session["active_message_id"] = sent.message_id
        await save_session(chat_id, session)


@router.callback_query(F.data == "round:start")
async def callback_round_start(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        if session["state"] != "ready_to_start":
            await answer_callback(
                callback,
                "Раунд уже запущен или экран устарел",
                show_alert=True,
            )
            return
        session["state"] = "round_active"
        starter = random.choice(session["players"])
        await save_session(callback.message.chat.id, session)
        await safe_edit(
            callback.message,
            texts.round_active_text(session["round_no"], starter),
            kb.active_round_keyboard(),
        )


@router.callback_query(F.data == "round:end")
async def callback_round_end(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        if session["state"] != "round_active":
            return
        session["state"] = "round_end_confirm"
        await save_session(callback.message.chat.id, session)
        await safe_edit(
            callback.message,
            "<b>🏁 Точно завершить раунд?</b>\n\n"
            "После подтверждения бот раскроет секретное слово и имена шпионов.",
            kb.end_round_confirm_keyboard(),
        )


@router.callback_query(F.data == "round:continue")
async def callback_round_continue(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        if session["state"] != "round_end_confirm":
            return
        session["state"] = "round_active"
        await save_session(callback.message.chat.id, session)
        await safe_edit(
            callback.message,
            f"<b>🔥 Раунд №{session['round_no']} продолжается</b>\n\n"
            "Обсуждайте и голосуйте. Когда закончите — нажмите кнопку ниже.",
            kb.active_round_keyboard(),
        )


@router.callback_query(F.data == "round:finish")
async def callback_round_finish(callback: CallbackQuery, bot: Bot) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        if session["state"] != "round_end_confirm":
            await answer_callback(callback, "Итоги уже показаны", show_alert=True)
            return
        session["state"] = "round_finished"
        await save_session(callback.message.chat.id, session)
        await send_optional_sticker(bot, callback.message.chat.id, CONFIG.result_sticker_id)
        await safe_edit(callback.message, texts.round_result_text(session), kb.result_keyboard())


@router.callback_query(F.data == "next_round")
async def callback_next_round(callback: CallbackQuery) -> None:
    await answer_callback(callback)
    async with CHAT_LOCKS[callback.message.chat.id]:
        session = await get_session(callback.message.chat.id)
        session["word"] = ""
        session["spy_indexes"] = []
        session["current_index"] = 0
        session["role_visible"] = False
        await show_summary(callback.message, session)


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="premium", description="Подписка PREMIUM"),
            BotCommand(command="help", description="Правила игры"),
            BotCommand(command="terms", description="Условия подписки"),
            BotCommand(command="paysupport", description="Поддержка по оплате"),
            BotCommand(command="cancel", description="Отменить текущий экран"),
            BotCommand(command="stickerid", description="Узнать ID стикера"),
        ]
    )


def configure_logging(level: str) -> None:
    logs_dir = Path(__file__).resolve().parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        logs_dir / "bot.log",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        handlers=[file_handler, console_handler],
    )


async def main() -> None:
    global DB, CONFIG
    CONFIG = load_config()
    configure_logging(CONFIG.log_level)
    DB = Database(CONFIG.database_path)
    await DB.connect()

    bot = Bot(
        token=CONFIG.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher.include_router(router)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await set_commands(bot)
        await sync_recent_premium_transactions(bot)
        me = await bot.get_me()
        logger.info("Бот @%s запущен", me.username)
        await dispatcher.start_polling(
            bot,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        await DB.close()
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
