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


def format_premium_date(expires_at: int) -> str:
    if not expires_at:
        return "не указано"
    value = datetime.fromtimestamp(int(expires_at), tz=MOSCOW_TZ)
    return value.strftime("%d.%m.%Y в %H:%M МСК")


def welcome_text(premium_active: bool, expires_at: int = 0) -> str:
    premium_line = (
        f"\n\n💎 <b>𝗣𝗥𝗘𝗠𝗜𝗨𝗠 активен</b> до {format_premium_date(expires_at)}."
        if premium_active
        else "\n\n💎 Дополнительные категории доступны с подпиской <b>𝗣𝗥𝗘𝗠𝗜𝗨𝗠</b>."
    )
    return (
        "<b>🕵️ MaksiShpi — игра «Кто шпион?»</b>\n\n"
        "Один телефон передаётся по кругу. Мирные игроки получают одинаковое "
        "секретное слово, а шпионы видят только свою роль.\n\n"
        "Задача мирных — вычислить шпиона. Задача шпиона — не выдать себя "
        "и догадаться, какое слово загадано.\n\n"
        "<b>Телефон никому не показывайте во время просмотра роли.</b>"
        f"{premium_line}"
    )


RULES = """
<b>📖 Как проходит игра</b>

1️⃣ Выберите число игроков и шпионов.
2️⃣ Выберите категорию слов.
3️⃣ Введите имена всех участников.
4️⃣ Передавайте телефон строго по очереди.
5️⃣ Каждый нажимает «Показать мою роль», запоминает её и нажимает «Я увидел».
6️⃣ После раздачи обсуждайте слово, задавая друг другу вопросы.
7️⃣ Когда закончите, нажмите «Завершить раунд» — бот покажет шпиона и секретное слово.

<b>Совет:</b> не задавайте слишком прямые вопросы, иначе шпион быстро поймёт слово.
""".strip()


def player_count_text(value: int) -> str:
    return (
        "<b>👥 Шаг 1 из 4 — количество игроков</b>\n\n"
        f"Сейчас участвует: <b>{value}</b>\n\n"
        "Допустимо от 3 до 20 игроков."
    )


def spy_count_text(value: int, maximum: int) -> str:
    return (
        "<b>🕵️ Шаг 2 из 4 — количество шпионов</b>\n\n"
        f"Выбрано шпионов: <b>{value}</b>\n"
        f"Максимум для этого состава: <b>{maximum}</b>\n\n"
        "В игре всегда остаётся минимум два мирных игрока."
    )


def category_text(premium_active: bool) -> str:
    premium_state = (
        "✅ <b>𝗣𝗥𝗘𝗠𝗜𝗨𝗠 активен — все категории открыты.</b>"
        if premium_active
        else "🔒 Категории 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 откроются после оформления подписки."
    )
    return (
        "<b>🗂 Шаг 3 из 4 — категория слов</b>\n\n"
        "Выберите, откуда бот будет брать секретное слово:\n\n"
        f"🎲 <b>Все категории</b> — {len(CELEBRITIES) + len(PLACES) + len(DRINKS)} слов\n"
        f"🌟 <b>Знаменитости</b> — {len(CELEBRITIES)} имён\n"
        f"📍 <b>Локации</b> — {len(PLACES)} локаций\n"
        f"🥤 <b>Напитки</b> — {len(DRINKS)} напитков\n\n"
        f"💎 <b>Все слова 𝗣𝗥𝗘𝗠𝗜𝗨𝗠</b> — {len(ALL_PREMIUM)} слов\n"
        f"🔞 <b>Взрослые темы 𝗣𝗥𝗘𝗠𝗜𝗨𝗠</b> — {len(ADULT_TOPICS)} слов\n"
        f"👷 <b>Профессии 𝗣𝗥𝗘𝗠𝗜𝗨𝗠</b> — {len(PROFESSIONS)} профессий\n\n"
        f"{premium_state}"
    )


def name_prompt(index: int, total: int) -> str:
    return (
        "<b>✍️ Шаг 4 из 4 — имена игроков</b>\n\n"
        f"Введите имя игрока <b>{index + 1} из {total}</b>.\n"
        "Имя нужно, чтобы в конце раунда было понятно, кто оказался шпионом."
    )


def settings_summary(session: dict) -> str:
    players = session.get("players", [])
    names = "\n".join(f"  {index + 1}. {escape(name)}" for index, name in enumerate(players))
    category = CATEGORY_TITLES.get(session.get("category", "all"), CATEGORY_TITLES["all"])
    return (
        "<b>⚙️ Настройки следующего раунда</b>\n\n"
        f"👥 Игроков: <b>{len(players)}</b>\n"
        f"🕵️ Шпионов: <b>{session.get('spy_count', 1)}</b>\n"
        f"🗂 Категория: <b>{category}</b>\n\n"
        f"<b>Состав:</b>\n{names}\n\n"
        "Проверьте всё перед раздачей ролей."
    )


def roster_text(players: list[str]) -> str:
    names = "\n".join(f"  {index + 1}. {escape(name)}" for index, name in enumerate(players))
    return (
        "<b>👥 Состав игроков</b>\n\n"
        f"{names}\n\n"
        "Можно добавить нового игрока, удалить участника или изменить имя."
    )


def handoff_text(player_name: str, index: int, total: int) -> str:
    return (
        "<b>📱 Передайте телефон</b>\n\n"
        f"Сейчас смотрит: <b>{escape(player_name)}</b>\n"
        f"Игрок <b>{index + 1} из {total}</b>\n\n"
        "Убедитесь, что экран видит только этот игрок, затем нажмите кнопку."
    )


def role_text(is_spy: bool, word: str) -> str:
    if is_spy:
        return (
            "<b>🕵️ ТЫ — ШПИОН</b>\n\n"
            "Ты не знаешь секретное слово. Слушай ответы других, отвечай осторожно "
            "и попробуй догадаться, о чём идёт речь.\n\n"
            "Запомнил роль? Нажми «Я увидел»."
        )
    return (
        "<b>🎭 ТЫ — МИРНЫЙ ИГРОК</b>\n\n"
        "Секретное слово:\n"
        f"<tg-spoiler><b>✨ {escape(word)} ✨</b></tg-spoiler>\n\n"
        "Не называй слово напрямую и не показывай экран другим.\n\n"
        "Запомнил слово? Нажми «Я увидел»."
    )


def all_roles_ready_text(round_no: int) -> str:
    return (
        f"<b>✅ Роли раунда №{round_no} розданы</b>\n\n"
        "Все игроки получили своё слово или роль шпиона. Уберите телефон так, "
        "чтобы никто случайно не открыл переписку.\n\n"
        "Когда все готовы, запускайте обсуждение."
    )


def round_active_text(round_no: int, starter: str) -> str:
    return (
        f"<b>🔥 Раунд №{round_no} начался!</b>\n\n"
        f"Первым задаёт вопрос: <b>{escape(starter)}</b>\n\n"
        "Обсуждайте, подозревайте и голосуйте между собой. Бот не ограничивает время.\n\n"
        "Когда закончите голосование, нажмите «Завершить раунд»."
    )


def round_result_text(session: dict) -> str:
    players = session["players"]
    spies = [players[index] for index in session["spy_indexes"]]
    spy_lines = "\n".join(f"🕵️ <b>{escape(name)}</b>" for name in spies)
    return (
        f"<b>🏁 Итоги раунда №{session['round_no']}</b>\n\n"
        f"Секретное слово: <tg-spoiler><b>{escape(session['word'])}</b></tg-spoiler>\n\n"
        f"<b>Шпион{'ы' if len(spies) > 1 else ''}:</b>\n{spy_lines}\n\n"
        "Для следующего раунда бот сохранит состав, число шпионов и категорию, "
        "но сначала снова покажет настройки."
    )


def premium_info_text(active: bool, expires_at: int = 0) -> str:
    if active:
        return (
            "<b>💎 MaksiShpi 𝗣𝗥𝗘𝗠𝗜𝗨𝗠</b>\n\n"
            "✅ Подписка активна.\n"
            f"📅 Доступ до: <b>{format_premium_date(expires_at)}</b>\n\n"
            "Открыты категории:\n"
            "💎 Все слова 𝗣𝗥𝗘𝗠𝗜𝗨𝗠\n"
            "🔞 Взрослые темы 𝗣𝗥𝗘𝗠𝗜𝗨𝗠\n"
            "👷 Профессии 𝗣𝗥𝗘𝗠𝗜𝗨𝗠\n\n"
            "Подписка продлевается автоматически каждые 30 дней, пока её не отменят "
            "в настройках подписок Telegram."
        )
    return (
        "<b>💎 MaksiShpi 𝗣𝗥𝗘𝗠𝗜𝗨𝗠</b>\n\n"
        "Откройте все текущие и будущие премиум-категории.\n\n"
        "В подписку входят:\n"
        "💎 Все слова 𝗣𝗥𝗘𝗠𝗜𝗨𝗠\n"
        "🔞 Взрослые темы 𝗣𝗥𝗘𝗠𝗜𝗨𝗠\n"
        "👷 Профессии 𝗣𝗥𝗘𝗠𝗜𝗨𝗠\n\n"
        f"Стоимость: <b>{PREMIUM_PRICE_STARS} ⭐ за 30 дней</b>\n"
        "Продление происходит автоматически каждые 30 дней.\n\n"
        "Категории 18+ предназначены только для совершеннолетних пользователей."
    )


PREMIUM_LOCKED = (
    "<b>🔒 Нужен 𝗣𝗥𝗘𝗠𝗜𝗨𝗠</b>\n\n"
    "Эта категория доступна по подписке MaksiShpi 𝗣𝗥𝗘𝗠𝗜𝗨𝗠.\n\n"
    f"Стоимость: <b>{PREMIUM_PRICE_STARS} ⭐ за 30 дней</b>\n"
    "После оплаты доступ откроется сразу."
)


def premium_success_text(expires_at: int, first_payment: bool) -> str:
    title = "Подписка оформлена" if first_payment else "Подписка продлена"
    return (
        f"<b>💎 {title}!</b>\n\n"
        "Все премиум-категории открыты.\n"
        f"📅 Доступ до: <b>{format_premium_date(expires_at)}</b>\n\n"
        "Вернитесь к выбору категории или начните новую игру."
    )


def adult_confirmation_text(category: str) -> str:
    if category == "all_premium":
        name = "«Все слова 𝗣𝗥𝗘𝗠𝗜𝗨𝗠»"
        detail = "В общий набор входят слова из категории «Взрослые темы»."
    else:
        name = "«Взрослые темы 𝗣𝗥𝗘𝗠𝗜𝗨𝗠»"
        detail = "В категории присутствуют откровенные слова сексуального характера."
    return (
        "<b>🔞 Подтверждение возраста</b>\n\n"
        f"Вы выбрали категорию {name}.\n"
        f"{detail}\n\n"
        "Продолжая, вы подтверждаете, что вам исполнилось 18 лет."
    )


PAY_SUPPORT = (
    "<b>⭐ Поддержка по оплате</b>\n\n"
    "По вопросам подписки, списаний или доступа обратитесь в официальный канал:\n"
    f"{SUPPORT_URL}\n\n"
    "Не отправляйте никому токены, коды подтверждения и данные своего аккаунта."
)


TERMS = (
    "<b>📜 Условия подписки MaksiShpi 𝗣𝗥𝗘𝗠𝗜𝗨𝗠</b>\n\n"
    f"• Стоимость — {PREMIUM_PRICE_STARS} Telegram Stars.\n"
    "• Один период подписки — 30 дней.\n"
    "• После оплаты подписка продлевается автоматически каждые 30 дней.\n"
    "• Отменить автопродление можно в настройках подписок Telegram.\n"
    "• После отмены доступ сохраняется до конца уже оплаченного периода.\n"
    "• PREMIUM привязан к Telegram-аккаунту покупателя.\n"
    "• Категории 18+ предназначены только для совершеннолетних.\n\n"
    f"Поддержка: {SUPPORT_URL}"
)
