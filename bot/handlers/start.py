import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from bot.keyboards import get_start_keyboard, get_main_menu_keyboard, get_block_menu_keyboard
from bot.states import LessonStates
from config import MESSAGES, CURRENT_LESSON_ID
from bot.statistics import UserStatistics
from bot.utils import UserProgress
router = Router()


@router.message(CommandStart())
@router.message(Command("help"))
async def start_command(message: Message, state: FSMContext):
    """Обработчик команды /start и /help"""
    from bot.database import db_manager
    
    # Проверяем, авторизован ли пользователь
    user_id = message.from_user.id
    user = db_manager.get_user_by_telegram_id(user_id)
    
    if user:
        # Пользователь авторизован
        await message.answer(
            f"{MESSAGES['welcome']}\n\n"
            f"👤 <b>Добро пожаловать, {user['username']}!</b>\n\n"
            "🎯 **Специализация:** Английский для программистов, Data Science и нейросетей\n\n"
            "**Структура урока:**\n"
            "1. 📖 Изучение терминов\n"
            "2. 🗣️ Произношение\n"
            "3. 📝 Лексические упражнения\n"
            "4. 📚 Грамматика с AI-учителем\n"
            "5. ✏️ Практические упражнения\n"
            "6. 🎧 Аудирование\n"
            "7. ✍️ Письмо\n"
            "8. 💬 Говорение\n\n"
            "Выберите действие:",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        # Пользователь не авторизован - предлагаем авторизацию
        await message.answer(
            f"{MESSAGES['welcome']}\n\n"
            "🔐 <b>Для использования бота необходимо авторизоваться</b>\n\n"
            "🎯 **Специализация:** Английский для программистов, Data Science и нейросетей\n\n"
            "**Структура урока:**\n"
            "1. 📖 Изучение терминов\n"
            "2. 🗣️ Произношение\n"
            "3. 📝 Лексические упражнения\n"
            "4. 📚 Грамматика с AI-учителем\n"
            "5. ✏️ Практические упражнения\n"
            "6. 🎧 Аудирование\n"
            "7. ✍️ Письмо\n"
            "8. 💬 Говорение\n\n"
            "Выберите действие:",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard()
        )


@router.message(Command("lesson"))
async def lesson_command(message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Команда для начала урока"""
    await message.answer(MESSAGES["start_lesson"])
    await state.set_state(LessonStates.TERMS_START)

    from bot.handlers.lesson import start_terms_block
    await start_terms_block(message.from_user.id, message, state, user_statistics, user_progress)


@router.message(Command("restart"))
async def restart_command(message: Message, state: FSMContext, user_progress: UserProgress):
    """Команда перезапуска урока"""
    await state.clear()

    user_progress.reset_progress(message.from_user.id)

    await message.answer(
        "🔄 Урок перезапущен!\\n\\nВыберите действие:",
        reply_markup=get_main_menu_keyboard()
    )


@router.message(Command("listening"))
async def listening_command(message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Команда для блока аудирования"""
    await message.answer("🎧 Запускаем блок аудирования...")
    from bot.handlers.lesson import start_listening_true_false
    await start_listening_true_false(message.from_user.id, message, state, user_statistics, user_progress)


@router.message(Command("terms"))
async def terms_command(message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Команда для блока терминов"""
    await message.answer("📖 Запускаем блок изучения терминов...")
    from bot.handlers.lesson import start_terms_block
    await start_terms_block(message.from_user.id, message, state, user_statistics, user_progress)


@router.callback_query(F.data == "start_lesson")
async def start_lesson(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress ):
    """Начало урока"""
    await callback.message.edit_text(
        MESSAGES["start_lesson"]
    )

    # Переходим к блоку терминов
    await state.set_state(LessonStates.TERMS_START)

    # Импортируем и вызываем обработчик терминов
    from bot.handlers.lesson import start_terms_block

    print(f"DEBUG (start_lesson): Вызываю start_terms_block для пользователя {callback.from_user.id}")

    await start_terms_block(callback.from_user.id, callback.message, state, user_statistics, user_progress)

    await callback.answer()

@router.message(Command("progress"))
@router.callback_query(F.data == "show_statistics")
async def show_user_statistics(
    update: Message | CallbackQuery,
    user_statistics: UserStatistics
):
    print("DEBUG: Handler show_user_statistics called!")

    try:
        if isinstance(update, Message):
            user_id = update.from_user.id
            message = update
        else: # CallbackQuery
            user_id = update.from_user.id
            message = update.message
            await update.answer()

        stats = user_statistics.get_user_stats(user_id)

        print(f"DEBUG: User ID: {user_id}, Stats: {stats}")

        # Получаем общий процент по уроку
        overall_percentage = user_statistics.get_lesson_overall_percentage(user_id, CURRENT_LESSON_ID)
        
        progress_message = "<b>📊 Ваша статистика:</b>\n\n"
        progress_message += f"<b>Пройдено уроков:</b> {stats['total_lessons_completed']}\n\n"
        progress_message += f"<b>Урок:</b> {CURRENT_LESSON_ID}\n"
        progress_message += f"<b>Общий процент по уроку:</b> {overall_percentage}%\n\n"

        # Обновляем отображение статусов блоков для соответствия новой структуре
        block_display_names = {
            "terms": "📖 Изучение терминов",
            "pronunciation": "🗣️ Произношение",
            "lexical": "📝 Лексика (Общий)",
            "lexical_en_to_ru": "📝 Лексика (Англ->Рус)",
            "lexical_ru_to_en": "📝 Лексика (Рус->Англ)",
            "lexical_word_build": "🔤 Сборка слов",
            "grammar": "📚 Грамматика (Правило)",
            "lexico_grammar": "✏️ Лексико-грамматика (Общий)",
            "lexico_grammar_verb": "✏️ Глаголы",
            "lexico_grammar_mchoice": "✏️ Множественный выбор",
            "lexico_grammar_negative": "✏️ Отрицательные",
            "lexico_grammar_question": "✏️ Вопросительные",
            "lexico_grammar_missing_word": "✏️ Пропущенные слова",
            "listening": "🎧 Аудирование (Общий)",
            "listening_true_false": "🎧 Аудирование (True/False)",
            "listening_choice": "🎧 Аудирование (Выбор)",
            "listening_phrases": "🎧 Аудирование (Фразы)",
            "writing": "✍️ Письмо (Общий)",
            "writing_sentences": "✍️ Письмо (Предложения)",
            "writing_translation": "✍️ Письмо (Перевод)",
            "speaking": "💬 Говорение (Общий)",
            "speaking_topics": "💬 Говорение (Темы)",
        }

        progress_message += "<b>Статус блоков:</b>\n"
        current_lesson_blocks = stats['lessons'].get(CURRENT_LESSON_ID, {}).get('blocks', {})

        for block_name, display_name in block_display_names.items():
            block_stats = current_lesson_blocks.get(block_name, {})
            
            # Определяем статус завершения с учетом процентов
            is_completed = block_stats.get("completed", False)
            
            # Получаем процент для всех блоков
            percentage = user_statistics.get_block_percentage(user_id, block_name, CURRENT_LESSON_ID)
            
            # Для блоков с подблоками проверяем процент прохождения
            if block_name not in ["terms", "speaking"] and percentage >= 100.0:
                is_completed = True
            
            completed_status = "✅ Пройден" if is_completed else "⏳ Не пройден"

            # Добавляем проценты для всех блоков, кроме исключенных
            score_info = ""
            if block_name not in ["terms", "speaking"] and percentage > 0:
                score_info = f" ({percentage}%)"

            progress_message += f"- {display_name}: {completed_status}{score_info}\n"

        print(f"DEBUG: Progress Message:\n{progress_message}")

        await message.answer(progress_message, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        print("DEBUG: Message sent successfully!")
    except Exception as e:
        print(f"CRITICAL ERROR IN HANDLER show_user_statistics: {e}")
        import traceback
        print(traceback.format_exc())

        if 'message' in locals() and message is not None:
            try:
                await message.answer("Произошла внутренняя ошибка при получении статистики. Попробуйте позже.")
            except Exception as answer_e:
                print(f"ERROR: Could not send fallback error message to user: {answer_e}")


@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery, state: FSMContext):
    """Показать главное меню"""
    await callback.message.edit_text(
        f"{MESSAGES['welcome']}\\n\\n"
        "🎯 **Специализация:** Английский для программистов, Data Science и нейросетей\\n\\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "restart_lesson")
async def restart_lesson(callback: CallbackQuery, state: FSMContext, user_progress: UserProgress):
    # Сбрасываем состояние и прогресс
    await state.clear()

    user_progress.reset_progress(callback.from_user.id)

    try:
        await callback.message.edit_text(
            "🔄 Урок перезапущен! Начинаем заново.\\n\\nВыберите действие:",
            reply_markup=get_main_menu_keyboard()
        )
    except Exception:
        # Если не удалось изменить сообщение, отправляем новое
        await callback.message.answer(
            "🔄 Урок перезапущен! Начинаем заново.\\n\\nВыберите действие:",
            reply_markup=get_main_menu_keyboard()
        )

    await callback.answer()


@router.callback_query(F.data == "continue_lesson")
async def continue_lesson(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Продолжить урок с текущего места"""


    progress = user_progress.get_progress(callback.from_user.id)
    current_block = progress.get('current_block', 'terms')

    if current_block == 'terms':
        await callback.message.edit_text("📖 Продолжаем изучение терминов...")
        from bot.handlers.lesson import start_terms_block
        await start_terms_block(callback.from_user.id, callback.message, state, user_statistics, user_progress)

    elif current_block == 'pronunciation':
        await callback.message.edit_text("🗣️ Продолжаем блок произношения...")
        from bot.handlers.lesson import start_pronunciation_block
        await start_pronunciation_block(callback.from_user.id, callback.message, state, user_statistics, user_progress)

    elif current_block == 'lexical': # Это общий лексический блок, который включает подблоки
        await callback.message.edit_text("📝 Продолжаем лексические упражнения...")
        from bot.handlers.lesson import start_lexical_en_to_ru_block
        await start_lexical_en_to_ru_block(callback.from_user.id, callback.message, state, user_statistics, user_progress)

    elif current_block == 'lexical_word_build': # Добавлено для продолжения word_build
        await callback.message.edit_text("🔤 Продолжаем сборку слов...")
        from bot.handlers.lesson import start_word_build
        await start_word_build(callback, state, user_statistics, user_progress) # start_word_build принимает callback

    elif current_block == 'grammar':
        await callback.message.edit_text("📚 Продолжаем изучение грамматики...")
        from bot.handlers.lesson import start_grammar_block
        await start_grammar_block(callback.from_user.id, callback.message, state, user_statistics, user_progress) # user_id добавлен

    elif current_block == 'lexico_grammar': # Общий блок для практических упражнений
        await callback.message.edit_text("✏️ Продолжаем практические упражнения...")
        # Определяем, какой именно подблок нужно продолжить
        current_sub_block = progress.get('current_sub_block_name', 'verb') # Предполагаем 'verb' как первый
        if current_sub_block == 'verb':
            from bot.handlers.lesson import start_verb_exercise
            await start_verb_exercise(callback.from_user.id, callback.message, state, user_statistics, user_progress)
        elif current_sub_block == 'mchoice':
            from bot.handlers.lesson import start_mchoice_exercise
            await start_mchoice_exercise(callback.from_user.id, callback.message, state, user_statistics, user_progress)
        elif current_sub_block == 'negative':
            from bot.handlers.lesson import start_negative_exercise
            await start_negative_exercise(callback.from_user.id, callback.message, state, user_statistics, user_progress)
        elif current_sub_block == 'question':
            from bot.handlers.lesson import start_question_exercise
            await start_question_exercise(callback.from_user.id, callback.message, state, user_statistics, user_progress)
        elif current_sub_block == 'missing_word':
            from bot.handlers.lesson import start_missing_word
            await start_missing_word(callback.from_user.id, callback.message, state, user_statistics, user_progress)

    elif current_block == 'listening':
        await callback.message.edit_text("🎧 Продолжаем блок аудирования...")
        from bot.handlers.lesson import start_listening_true_false
        await start_listening_true_false(callback.from_user.id, callback.message, state, user_statistics, user_progress)

    elif current_block == 'writing':
        await callback.message.edit_text("✍️ Продолжаем блок письменной речи...")
        from bot.handlers.lesson import start_writing_sentences
        await start_writing_sentences(callback.from_user.id, callback.message, state, user_statistics, user_progress)

    else:
        await callback.message.edit_text(
            "🎉 Все доступные блоки пройдены!\\n\\n"
            "Остальные блоки (говорение) в разработке.",
            reply_markup=get_main_menu_keyboard()
        )

    await callback.answer()


@router.message(Command("writing"))
async def writing_command(message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Команда для блока письма"""
    await message.answer("✍️ Запускаем блок письменной речи...")
    from bot.handlers.lesson import start_writing_sentences
    await start_writing_sentences(message.from_user.id, message, state, user_statistics, user_progress)


@router.callback_query(F.data.startswith("menu_"))
async def handle_menu_navigation(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Обработка навигации по меню"""
    menu_type = callback.data.replace("menu_", "")
    user_id = callback.from_user.id # Получаем user_id здесь

    if menu_type == "terms":
        await callback.message.edit_text(
            "📖 **Блок: Изучение терминов**\\n\\n"
            "В этом блоке вы изучите ключевые термины программирования и Data Science с переводом, транскрипцией и произношением.",
            parse_mode="Markdown",
            reply_markup=get_block_menu_keyboard()
        )
        # Можно сразу запустить блок терминов
        from bot.handlers.lesson import start_terms_block
        await start_terms_block(user_id, callback.message, state, user_statistics, user_progress)

    elif menu_type == "pronunciation":
        await callback.message.edit_text(
            "🗣️ **Блок: Произношение**\\n\\n"
            "Тренировка произношения IT терминов с голосовыми упражнениями.",
            parse_mode="Markdown",
            reply_markup=get_block_menu_keyboard()
        )
        # Запускаем блок произношения
        from bot.handlers.lesson import start_pronunciation_block
        await start_pronunciation_block(user_id, callback.message, state, user_statistics, user_progress)

    elif menu_type == "speaking":
        await callback.message.edit_text(
            "💬 **Блок: Говорение**\\n\\n"
            "Финальный блок курса - развитие навыков устной речи на IT темы.",
            parse_mode="Markdown"
        )
        # Запускаем блок говорения
        from bot.handlers.lesson import start_speaking_block
        await start_speaking_block(user_id, callback.message, state, user_statistics, user_progress) # user_id добавлен

    elif menu_type == "lexical":
        await callback.message.edit_text(
            "📝 **Блок: Лексические упражнения**\\n\\n"
            "Упражнения на перевод технических терминов в обе стороны.",
            parse_mode="Markdown",
            reply_markup=get_block_menu_keyboard()
        )
        # Запускаем лексический блок
        from bot.handlers.lesson import start_lexical_en_to_ru_block
        await start_lexical_en_to_ru_block(user_id, callback.message, state, user_statistics, user_progress)

    elif menu_type == "grammar":
        await callback.message.edit_text(
            "📚 **Блок: Грамматика**\\n\\n"
            "Изучение грамматических правил с примерами из мира программирования.",
            parse_mode="Markdown",
            reply_markup=get_block_menu_keyboard()
        )
        # Запускаем блок грамматики
        from bot.handlers.lesson import start_grammar_block
        await start_grammar_block(user_id, callback.message, state, user_statistics, user_progress) # user_id добавлен

    elif menu_type == "exercises": # Это будет общий блок для lexico_grammar
        await callback.message.edit_text(
            "✏️ **Блок: Практические упражнения**\\n\\n"
            "Лексико-грамматические упражнения на IT тематику.",
            parse_mode="Markdown",
            reply_markup=get_block_menu_keyboard()
        )
        # Запускаем первый подблок лексико-грамматических упражнений
        from bot.handlers.lesson import start_verb_exercise
        await start_verb_exercise(user_id, callback.message, state, user_statistics, user_progress) # user_id добавлен

    elif menu_type == "listening":
        await callback.message.edit_text(
            "🎧 **Блок: Аудирование**\\n\\n"
            "Упражнения на понимание речи на слух с IT терминологией.",
            parse_mode="Markdown"
        )
        # Запускаем блок аудирования
        from bot.handlers.lesson import start_listening_true_false
        await start_listening_true_false(user_id, callback.message, state, user_statistics, user_progress) # user_id добавлен

    elif menu_type == "writing":
        await callback.message.edit_text(
            "✍️ **Блок: Письменная речь**\\n\\n"
            "Упражнения на составление предложений и перевод с IT терминологией.",
            parse_mode="Markdown"
        )
        # Запускаем блок письма
        from bot.handlers.lesson import start_writing_sentences
        await start_writing_sentences(user_id, callback.message, state, user_statistics, user_progress) # user_id добавлен

    await callback.answer()
