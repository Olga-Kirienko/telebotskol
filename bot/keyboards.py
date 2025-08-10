import os
import sys

# Добавляем путь к корневой директории
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_start_keyboard():
    """Стартовая клавиатура"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Начать урок 📚", callback_data="start_lesson")
    return keyboard.as_markup()


def get_next_keyboard():
    """Кнопка 'Дальше'"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Дальше ➡️", callback_data="next")
    return keyboard.as_markup()


def get_skip_next_keyboard():
    """Кнопки 'Пропустить' и 'Дальше'"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Пропустить ⏭️", callback_data="skip")
    keyboard.button(text="Дальше ➡️", callback_data="next")
    keyboard.adjust(2)
    return keyboard.as_markup()


def get_pronunciation_keyboard():
    """Клавиатура для блока произношения"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Записать произношение 🎤", callback_data="record_pronunciation")
    # Новая кнопка: сказать медленнее
    keyboard.button(text="Сказать медленнее 🐢", callback_data="slow_down_pronunciation")
    keyboard.button(text="Пропустить ⏭️", callback_data="skip_pronunciation")
    keyboard.adjust(1)
    return keyboard.as_markup()


def get_pronunciation_result_keyboard():
    """Клавиатура после проверки произношения"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Дальше ➡️", callback_data="next_pronunciation")
    keyboard.button(text="Пропустить ⏭️", callback_data="skip_pronunciation")
    # Новая кнопка: повторить слово/фразу
    keyboard.button(text="Повторить 🔁", callback_data="repeat_pronunciation")
    keyboard.adjust(
        2)  # adjust(2) оставит "Повторить" на отдельной строке, если хотите все 3 в ряд, используйте adjust(3)
    return keyboard.as_markup()


def get_choice_keyboard(options: list, word: str = ""):
    """Клавиатура с вариантами ответов для лексических упражнений"""
    keyboard = InlineKeyboardBuilder()
    for i, option in enumerate(options):
        # Используем word для создания уникального callback_data
        callback_data = f"lexical_{word}_{option}"[:64]  # Ограничиваем длину
        keyboard.button(text=option, callback_data=callback_data)
    keyboard.adjust(1)
    return keyboard.as_markup()


def get_grammar_keyboard():
    """Клавиатура после объяснения грамматики"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Всё понятно ✅", callback_data="grammar_understood")
    keyboard.button(text="Есть вопросики ❓", callback_data="grammar_questions")
    keyboard.adjust(1)
    return keyboard.as_markup()


def get_grammar_qa_keyboard():
    """Клавиатура в режиме вопросов-ответов"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Теперь всё понятно ✅", callback_data="grammar_now_understood")
    keyboard.button(text="Остались вопросы ❓", callback_data="grammar_still_questions")
    keyboard.adjust(1)
    return keyboard.as_markup()


def get_main_menu_keyboard():
    """Главное меню бота"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📚 Начать урок", callback_data="start_lesson")
    keyboard.button(text="📖 Термины", callback_data="menu_terms")
    keyboard.button(text="🗣️ Произношение", callback_data="menu_pronunciation")
    keyboard.button(text="📝 Лексика", callback_data="menu_lexical")
    keyboard.button(text="📚 Грамматика", callback_data="menu_grammar")
    keyboard.button(text="✏️ Упражнения", callback_data="menu_exercises")
    keyboard.button(text="🎧 Аудирование", callback_data="menu_listening")
    keyboard.button(text="✍️ Письмо", callback_data="menu_writing")
    keyboard.button(text="💬 Говорение", callback_data="menu_speaking")
    keyboard.button(text="🔄 Перезапуск", callback_data="restart_lesson")
    keyboard.button(text="📊 Моя статистика", callback_data="show_statistics")
    keyboard.button(text="🔐 Авторизация / Регистрация", callback_data="auth_menu")
    keyboard.adjust(1, 2, 2, 2, 2, 2, 1, 1, 1)
    return keyboard.as_markup()


def get_block_menu_keyboard():
    """Меню навигации по блокам"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🏠 Главное меню", callback_data="main_menu")
    keyboard.button(text="📚 Продолжить урок", callback_data="continue_lesson")
    keyboard.adjust(2)
    return keyboard.as_markup()


def get_mchoice_keyboard(options: list, question_index: int = 0):
    """Клавиатура для множественного выбора"""
    keyboard = InlineKeyboardBuilder()
    for i, option in enumerate(options):
        callback_data = f"mchoice_{question_index}_{i}_{option}"[:64]
        keyboard.button(text=option, callback_data=callback_data)
    keyboard.adjust(1)
    return keyboard.as_markup()


def get_text_exercise_keyboard():
    """Клавиатура для текстовых упражнений"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Пропустить ⏭️", callback_data="skip_text_exercise")
    return keyboard.as_markup()


def get_true_false_keyboard():
    """Клавиатура True/False для аудирования"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="True ✅", callback_data="listening_true")
    keyboard.button(text="False ❌", callback_data="listening_false")
    keyboard.button(text="Сказать медленнее 🐢", callback_data="listening_slow_down")
    keyboard.adjust(2,1)
    return keyboard.as_markup()


def get_listening_choice_keyboard(options: list, question_index: int = 0):
    keyboard = InlineKeyboardBuilder()
    for i, option in enumerate(options):
        callback_data = f"listening_choice_{question_index}_{i}_{option}"[:64]
        keyboard.button(text=option, callback_data=callback_data)

    # Добавляем кнопку замедления с уникальным callback_data
    keyboard.button(text="Сказать медленнее 🐢", callback_data="listening_choice_slow_down")
    keyboard.adjust(1, repeat=True)
    return keyboard.as_markup()


def get_listening_phrases_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Записать фразу 🎤", callback_data="record_phrase")
    keyboard.button(text="Пропустить фразу ⏭️", callback_data="skip_phrase")
    keyboard.button(text="Сказать медленнее 🐢", callback_data="listening_phrases_slow_down")
    keyboard.adjust(1, 2)
    return keyboard.as_markup()


def get_phrase_result_keyboard():
    """Клавиатура после проверки произношения"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Дальше ➡️", callback_data="next_phrase")
    return keyboard.as_markup()


def get_continue_writing_keyboard():
    """Кнопка 'Продолжить урок' для письменных упражнений"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Продолжить урок ➡️", callback_data="continue_writing")
    return keyboard.as_markup()


def get_writing_skip_keyboard():
    """Клавиатура для пропуска письменных упражнений"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Пропустить ⏭️", callback_data="skip_writing")
    return keyboard.as_markup()


def get_speaking_keyboard():
    """Клавиатура для блока говорения"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Записать мысли 🎤", callback_data="record_speaking")
    keyboard.button(text="Пропустить ⏭️", callback_data="skip_speaking")
    return keyboard.as_markup()


def get_speaking_result_keyboard():
    """Клавиатура после анализа говорения"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Следующая тема ➡️", callback_data="next_speaking")
    keyboard.button(text="Записать еще раз 🔄", callback_data="retry_speaking")
    keyboard.adjust(1)
    return keyboard.as_markup()


def get_word_build_keyboard(parts: list, collected: str = ""):
    """
    Клавиатура с частями слова для упражнения на сборку.

    :param parts: список частей слова (например, ["pix", "el"])
    :param collected: уже собранные части (для отображения)
    :return: InlineKeyboardMarkup
    """
    kb = InlineKeyboardBuilder()

    for part in parts:
        kb.button(text=part, callback_data=f"wb_part_{part}")

    kb.button(text="✅ Проверить", callback_data="wb_check")
    kb.button(text="⏩ Пропустить", callback_data="wb_skip")
    kb.adjust(2)  # Делаем по 2 кнопки в ряд

    return kb.as_markup()


def get_final_keyboard():
    """Финальная клавиатура курса"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🏠 Главное меню", callback_data="main_menu")
    keyboard.button(text="🔄 Начать заново", callback_data="restart_lesson")
    keyboard.adjust(2)
    return keyboard.as_markup()


def get_continue_keyboard():
    """Кнопка 'Продолжить' после ответа"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Продолжить ➡️", callback_data="continue_exercise")
    return keyboard.as_markup()


def get_keyboard_with_menu(current_keyboard: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
    """
    Добавляет кнопку '🏠 Главное меню' к существующей клавиатуре.

    :param current_keyboard: Текущая InlineKeyboardMarkup, к которой нужно добавить кнопку.
    :return: Модифицированная InlineKeyboardMarkup с добавленной кнопкой 'Главное меню'.
    """
    # Создаем новый InlineKeyboardBuilder из существующей клавиатуры
    builder = InlineKeyboardBuilder()
    builder.attach(InlineKeyboardBuilder.from_markup(current_keyboard))

    # Добавляем кнопку "Главное меню"
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu"))

    return builder.as_markup()


# Клавиатуры для авторизации
def get_auth_choice_keyboard():
    """Клавиатура выбора между регистрацией и авторизацией"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📝 Регистрация", callback_data="auth_register")
    keyboard.button(text="🔑 Авторизация", callback_data="auth_login")
    keyboard.button(text="🔙 Назад", callback_data="main_menu")
    keyboard.adjust(2, 1)
    return keyboard.as_markup()


def get_register_confirm_keyboard():
    """Клавиатура подтверждения регистрации"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="✅ Подтвердить", callback_data="register_confirm")
    keyboard.button(text="🔄 Начать заново", callback_data="auth_register")
    keyboard.button(text="🔙 Отмена", callback_data="auth_menu")
    keyboard.adjust(2, 1)
    return keyboard.as_markup()


def get_auth_cancel_keyboard():
    """Клавиатура отмены авторизации"""
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Отмена", callback_data="auth_menu")
    return keyboard.as_markup()