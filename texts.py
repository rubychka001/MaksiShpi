"""Тексты интерфейса."""

from html import escape

from words import CATEGORY_TITLES


WELCOME = """
<b>🕵️ MaksiShpi — игра «Кто шпион?»</b>

Один телефон передаётся по кругу. Мирные игроки получают одинаковое секретное слово, а шпионы видят только свою роль.

Задача мирных — вычислить шпиона. Задача шпиона — не выдать себя и догадаться, какое слово загадано.

<b>Телефон никому не показывайте во время просмотра роли.</b>
""".strip()

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


CATEGORY_TEXT = """
<b>🗂 Шаг 3 из 4 — категория слов</b>

Выберите, откуда бот будет брать секретное слово:

🎲 <b>Все категории</b> — 225 слов
🌟 <b>Знаменитости</b> — 100 имён
📍 <b>Локации</b> — 75 локаций
🥤 <b>Напитки</b> — 50 напитков
""".strip()


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
            "Ты не знаешь секретное слово. Слушай ответы других, отвечай осторожно и попробуй догадаться, о чём идёт речь.\n\n"
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
        "Все игроки получили своё слово или роль шпиона. Уберите телефон так, чтобы никто случайно не открыл переписку.\n\n"
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
        "Для следующего раунда бот сохранит состав, число шпионов и категорию, но сначала снова покажет настройки."
    )
