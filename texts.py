"""Тексты интерфейса MaksiShpi."""

from datetime import datetime, timedelta, timezone
from html import escape

from words import (
    ADULT_TOPICS,
    ALL_PREMIUM,
    CATEGORY_TITLES,
    CELEBRITIES,
    DRINKS,
    PLACES,
    PROFESSIONS,
)


PREMIUM_PRICE_STARS = 50
SUPPORT_URL = "https://t.me/MaksiGamesBots"
MOSCOW_TZ = timezone(timedelta(hours=3))
FOREVER_THRESHOLD = 4_000_000_000


def format_premium_date(expires_at: int) -> str:
    if not expires_at:
        return "не активен"
    if int(expires_at) >= FOREVER_THRESHOLD:
        return "без ограничения срока"
    value = datetime.fromtimestamp(int(expires_at), tz=MOSCOW_TZ)
    return value.strftime("%d.%m.%Y в %H:%M МСК")


def welcome_text(premium_active: bool, expires_at: int = 0) -> str:
    if premium_active:
        premium_block = (
            "\n\n💎 <b>PREMIUM активен</b>\n"
            f"Доступ: {format_premium_date(expires_at)}"
        )
    else:
        premium_block = (
            "\n\n💎 <b>Хотите больше слов?</b>\n"
            "В PREMIUM открыты профессии, взрослые темы и общий расширенный набор."
        )

    return (
        "<b>🕵️ MaksiShpi — «Кто шпион?»</b>\n\n"
        "Соберите компанию и передавайте один телефон по кругу. "
        "Мирные увидят одинаковое секретное слово, а шпион — только свою роль.\n\n"
        "🤝 <b>Мирные:</b> задавайте вопросы и найдите шпиона.\n"
        "🎭 <b>Шпион:</b> не выдавайте себя и попробуйте угадать слово.\n\n"
        "Экран с ролью должен видеть только текущий игрок."
        f"{premium_block}"
    )


RULES = """
<b>📖 Как играть</b>

1️⃣ Выберите количество игроков и шпионов.
2️⃣ Выберите категорию секретных слов.
3️⃣ Введите имена участников.
4️⃣ Передавайте телефон каждому игроку по очереди.
5️⃣ Игрок открывает роль, запоминает её и скрывает экран.
6️⃣ После раздачи задавайте друг другу вопросы по теме слова.
7️⃣ Проведите голосование и нажмите «Завершить раунд».

<b>Как задавать вопросы</b>
Лучше спрашивать не напрямую: «Здесь шумно?», «Я бывал здесь раньше?», «Это дорого?». Слишком точный вопрос может сразу подсказать слово шпиону.

<b>Главное правило:</b> не показывайте свою роль другим игрокам.
""".strip()


def player_count_text(value: int) -> str:
    return (
        "<b>👥 Шаг 1 из 4 — игроки</b>\n\n"
        f"Сейчас играет: <b>{value}</b>\n\n"
        "Выберите от 3 до 20 участников. Имена введём на последнем шаге."
    )


def spy_count_text(value: int, maximum: int) -> str:
    return (
        "<b>🕵️ Шаг 2 из 4 — шпионы</b>\n\n"
        f"Количество шпионов: <b>{value}</b>\n"
        f"Доступный максимум: <b>{maximum}</b>\n\n"
        "В каждом раунде останется минимум два мирных игрока."
    )


def category_text(premium_active: bool) -> str:
    free_total = len(CELEBRITIES) + len(PLACES) + len(DRINKS)
    premium_state = (
        "✅ <b>PREMIUM активен — все категории доступны.</b>"
        if premium_active
        else "🔒 Премиум-категории откроются после оформления подписки."
    )
    return (
        "<b>🗂 Шаг 3 из 4 — категория</b>\n\n"
        "Выберите набор, из которого бот возьмёт секретное слово.\n\n"
        f"🎲 <b>Все категории</b> — {free_total} слов\n"
        f"🌟 <b>Знаменитости</b> — {len(CELEBRITIES)} имён\n"
        f"📍 <b>Локации</b> — {len(PLACES)} локаций\n"
        f"🥤 <b>Напитки</b> — {len(DRINKS)} напитков\n\n"
        f"💎 <b>Все слова PREMIUM</b> — {len(ALL_PREMIUM)} слов\n"
        f"🔞 <b>Взрослые темы PREMIUM</b> — {len(ADULT_TOPICS)} слов\n"
        f"👷 <b>Профессии PREMIUM</b> — {len(PROFESSIONS)} профессий\n\n"
        f"{premium_state}"
    )


def name_prompt(index: int, total: int) -> str:
    return (
        "<b>✍️ Шаг 4 из 4 — имена игроков</b>\n\n"
        f"Сейчас вводим игрока <b>{index + 1} из {total}</b>.\n"
        "Отправьте его имя одним сообщением.\n\n"
        "Так в конце раунда будет понятно, кто оказался шпионом."
    )


def settings_summary(session: dict) -> str:
    players = session.get("players", [])
    names = "\n".join(f"  {index + 1}. {escape(name)}" for index, name in enumerate(players))
    category = CATEGORY_TITLES.get(session.get("category", "all"), CATEGORY_TITLES["all"])
    return (
        "<b>⚙️ Всё готово к игре</b>\n\n"
        f"👥 Игроков: <b>{len(players)}</b>\n"
        f"🕵️ Шпионов: <b>{session.get('spy_count', 1)}</b>\n"
        f"🗂 Категория: <b>{category}</b>\n\n"
        f"<b>Участники:</b>\n{names}\n\n"
        "Проверьте настройки и нажмите «Раздать роли»."
    )


def roster_text(players: list[str]) -> str:
    names = "\n".join(f"  {index + 1}. {escape(name)}" for index, name in enumerate(players))
    return (
        "<b>👥 Состав игроков</b>\n\n"
        f"{names}\n\n"
        "Здесь можно добавить участника, удалить его или изменить имя."
    )


def handoff_text(player_name: str, index: int, total: int) -> str:
    return (
        "<b>📱 Передайте телефон</b>\n\n"
        f"Следующий игрок: <b>{escape(player_name)}</b>\n"
        f"Очередь: <b>{index + 1} из {total}</b>\n\n"
        "Убедитесь, что остальные не видят экран, и только потом откройте роль."
    )


def role_text(is_spy: bool, word: str) -> str:
    if is_spy:
        return (
            "<b>🕵️ ВЫ — ШПИОН</b>\n\n"
            "Секретное слово вам неизвестно. Слушайте ответы остальных, "
            "говорите осторожно и постарайтесь понять общую тему.\n\n"
            "Запомните роль и скройте экран."
        )
    return (
        "<b>🎭 ВЫ — МИРНЫЙ ИГРОК</b>\n\n"
        "Ваше секретное слово:\n"
        f"<tg-spoiler><b>✨ {escape(word)} ✨</b></tg-spoiler>\n\n"
        "Не называйте его напрямую и не показывайте экран другим.\n\n"
        "Запомните слово и скройте экран."
    )


def all_roles_ready_text(round_no: int) -> str:
    return (
        f"<b>✅ Роли раунда №{round_no} розданы</b>\n\n"
        "Все участники узнали свою роль. Уберите телефон, чтобы никто случайно "
        "не увидел переписку.\n\n"
        "Когда компания готова, начинайте обсуждение."
    )


def round_active_text(round_no: int, starter: str) -> str:
    return (
        f"<b>🔥 Раунд №{round_no} начался</b>\n\n"
        f"Первый вопрос задаёт: <b>{escape(starter)}</b>\n\n"
        "Задавайте вопросы по очереди, слушайте ответы и отмечайте подозрительное. "
        "Время не ограничено.\n\n"
        "После голосования нажмите кнопку ниже."
    )


def round_result_text(session: dict) -> str:
    players = session["players"]
    spies = [players[index] for index in session["spy_indexes"]]
    spy_lines = "\n".join(f"🕵️ <b>{escape(name)}</b>" for name in spies)
    return (
        f"<b>🏁 Итоги раунда №{session['round_no']}</b>\n\n"
        f"Секретное слово: <tg-spoiler><b>{escape(session['word'])}</b></tg-spoiler>\n\n"
        f"<b>Шпион{'ы' if len(spies) > 1 else ''}:</b>\n{spy_lines}\n\n"
        "Состав, число шпионов и категория сохранены. Можно сразу начать следующий раунд "
        "или изменить настройки."
    )


def premium_info_text(active: bool, expires_at: int = 0) -> str:
    if active:
        return (
            "<b>💎 MaksiShpi PREMIUM</b>\n\n"
            "✅ Подписка активна.\n"
            f"📅 Доступ: <b>{format_premium_date(expires_at)}</b>\n\n"
            "Вам доступны:\n"
            "• все слова PREMIUM;\n"
            "• взрослые темы 18+;\n"
            "• профессии;\n"
            "• новые премиум-категории после их добавления.\n\n"
            "Платная подписка продлевается автоматически каждые 30 дней, пока вы её не отмените в Telegram."
        )
    return (
        "<b>💎 MaksiShpi PREMIUM</b>\n\n"
        "Больше категорий для компаний, которые уже сыграли базовые наборы.\n\n"
        "<b>В подписке:</b>\n"
        "💎 Все слова PREMIUM\n"
        "🔞 Взрослые темы PREMIUM\n"
        "👷 Профессии PREMIUM\n"
        "➕ будущие премиум-категории\n\n"
        f"Стоимость: <b>{PREMIUM_PRICE_STARS} ⭐ за 30 дней</b>\n"
        "Продление — автоматически каждые 30 дней.\n\n"
        "Категории 18+ предназначены только для совершеннолетних пользователей."
    )


PREMIUM_LOCKED = (
    "<b>🔒 Нужен PREMIUM</b>\n\n"
    "Эта категория входит в подписку MaksiShpi PREMIUM.\n\n"
    f"Стоимость: <b>{PREMIUM_PRICE_STARS} ⭐ за 30 дней</b>\n"
    "После оплаты доступ откроется сразу."
)


def premium_success_text(expires_at: int, first_payment: bool) -> str:
    title = "Подписка оформлена" if first_payment else "Подписка продлена"
    return (
        f"<b>💎 {title}</b>\n\n"
        "Все премиум-категории уже открыты.\n"
        f"📅 Доступ: <b>{format_premium_date(expires_at)}</b>\n\n"
        "Можно вернуться к выбору категории и начать игру."
    )


def adult_confirmation_text(category: str) -> str:
    if category == "all_premium":
        name = "«Все слова PREMIUM»"
        detail = "В этот набор входят слова из взрослой категории."
    else:
        name = "«Взрослые темы PREMIUM»"
        detail = "В наборе присутствуют откровенные слова сексуального характера."
    return (
        "<b>🔞 Подтвердите возраст</b>\n\n"
        f"Вы выбрали {name}.\n{detail}\n\n"
        "Продолжая, вы подтверждаете, что вам уже исполнилось 18 лет."
    )


PAY_SUPPORT = (
    "<b>⭐ Поддержка по оплате</b>\n\n"
    "По вопросам подписки, списаний или доступа напишите через официальный канал:\n"
    f"{SUPPORT_URL}\n\n"
    "Не передавайте никому коды подтверждения, токен бота и данные аккаунта."
)


TERMS = (
    "<b>📜 Условия MaksiShpi PREMIUM</b>\n\n"
    f"• Стоимость — {PREMIUM_PRICE_STARS} Telegram Stars.\n"
    "• Один оплаченный период — 30 дней.\n"
    "• Подписка автоматически продлевается каждые 30 дней.\n"
    "• Автопродление можно отменить в настройках подписок Telegram.\n"
    "• После отмены доступ работает до конца оплаченного периода.\n"
    "• PREMIUM привязан к Telegram-аккаунту покупателя.\n"
    "• Возвраты и вопросы по оплате рассматриваются через /paysupport."
)


# ─────────────────────────── Админ-панель ───────────────────────────


def admin_panel_text(admin_id: int) -> str:
    return (
        "<b>🛠 Админ-панель MaksiShpi</b>\n\n"
        "Здесь можно посмотреть статистику, отправить сообщение пользователям "
        "и управлять PREMIUM-доступом.\n\n"
        f"Ваш ID: <code>{admin_id}</code>\n"
        "Все действия доступны только администраторам из ADMIN_IDS."
    )


def admin_statistics_text(stats: dict[str, int]) -> str:
    return (
        "<b>📊 Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
        f"📬 Доступны для рассылки: <b>{stats['reachable_users']}</b>\n"
        f"🟢 Активны за 24 часа: <b>{stats['active_24h']}</b>\n"
        f"📅 Активны за 7 дней: <b>{stats['active_7d']}</b>\n\n"
        f"💎 PREMIUM активен: <b>{stats['premium_active']}</b>\n"
        f"⭐ Платных подписок: <b>{stats['premium_paid']}</b>\n"
        f"🎁 Выдано вручную: <b>{stats['premium_manual']}</b>\n"
        f"🧾 Успешных платежей: <b>{stats['payments_count']}</b>\n"
        f"⭐ Получено Stars: <b>{stats['stars_received']}</b>\n\n"
        f"🎮 Сыграно раундов: <b>{stats['rounds_played']}</b>\n"
        f"📢 Проведено рассылок: <b>{stats['broadcasts_count']}</b>"
    )


ADMIN_BROADCAST_PROMPT = (
    "<b>📢 Новая рассылка</b>\n\n"
    "Отправьте следующее сообщение в том виде, в котором его должны получить пользователи.\n\n"
    "Поддерживаются текст, фото, видео, документ, аудио, голосовое сообщение, GIF и стикер. "
    "Бот сначала покажет предпросмотр и только потом попросит подтверждение."
)


def admin_broadcast_preview_text(recipients: int) -> str:
    return (
        "<b>📢 Предпросмотр готов</b>\n\n"
        f"Получателей в базе: <b>{recipients}</b>\n\n"
        "Проверьте сообщение выше. После запуска рассылку уже нельзя будет остановить из интерфейса."
    )


def admin_broadcast_result_text(total: int, delivered: int, blocked: int, failed: int) -> str:
    return (
        "<b>✅ Рассылка завершена</b>\n\n"
        f"Всего получателей: <b>{total}</b>\n"
        f"Доставлено: <b>{delivered}</b>\n"
        f"Заблокировали бота: <b>{blocked}</b>\n"
        f"Других ошибок: <b>{failed}</b>"
    )


ADMIN_GRANT_PROMPT = (
    "<b>💎 Выдать PREMIUM</b>\n\n"
    "Отправьте Telegram ID пользователя одним сообщением.\n\n"
    "Пользователь может узнать его командой /myid."
)


ADMIN_REVOKE_PROMPT = (
    "<b>🛑 Забрать PREMIUM</b>\n\n"
    "Отправьте Telegram ID пользователя, у которого нужно отключить доступ."
)


ADMIN_FIND_PROMPT = (
    "<b>👤 Найти пользователя</b>\n\n"
    "Отправьте его Telegram ID одним сообщением."
)


def admin_user_text(user: dict, premium_active: bool) -> str:
    username = f"@{escape(user['username'])}" if user.get("username") else "не указан"
    full_name = " ".join(
        part for part in (user.get("first_name", ""), user.get("last_name", "")) if part
    ) or "не указано"
    premium = (
        f"✅ Активен до: <b>{format_premium_date(int(user.get('expires_at', 0)))}</b>"
        if premium_active
        else "❌ Не активен"
    )
    reachable = "да" if user.get("is_active") else "нет — бот заблокирован или недоступен"
    return (
        "<b>👤 Пользователь</b>\n\n"
        f"ID: <code>{user['user_id']}</code>\n"
        f"Имя: <b>{escape(full_name)}</b>\n"
        f"Username: <b>{username}</b>\n"
        f"Язык Telegram: <b>{escape(user.get('language_code') or 'не указан')}</b>\n"
        f"Доступен боту: <b>{reachable}</b>\n"
        f"Первый запуск: <b>{escape(user.get('first_seen_at') or 'неизвестно')}</b>\n"
        f"Последняя активность: <b>{escape(user.get('last_seen_at') or 'неизвестно')}</b>\n\n"
        f"💎 PREMIUM: {premium}"
    )


def admin_grant_result_text(user_id: int, days: int, expires_at: int) -> str:
    period = "без ограничения срока" if days >= 36500 else f"{days} дней"
    return (
        "<b>✅ PREMIUM выдан</b>\n\n"
        f"Пользователь: <code>{user_id}</code>\n"
        f"Срок: <b>{period}</b>\n"
        f"Доступ: <b>{format_premium_date(expires_at)}</b>\n\n"
        "Telegram Stars не списывались."
    )


def admin_revoke_confirm_text(user_id: int, expires_at: int) -> str:
    return (
        "<b>🛑 Отключить PREMIUM?</b>\n\n"
        f"Пользователь: <code>{user_id}</code>\n"
        f"Текущий доступ: <b>{format_premium_date(expires_at)}</b>\n\n"
        "Ручное отключение не отменяет автоматическое продление платной подписки в Telegram."
    )
