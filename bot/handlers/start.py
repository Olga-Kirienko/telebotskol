import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from bot.keyboards import get_start_keyboard, get_main_menu_keyboard, get_block_menu_keyboard
from bot.states import LessonStates
from config import MESSAGES

router = Router()


@router.message(CommandStart())
@router.message(Command("help"))
async def start_command(message: Message, state: FSMContext):
    """Обработчик команды /start и /help"""
    await message.answer(
        f"{MESSAGES['welcome']}\n\n"
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
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )


@router.message(Command("lesson"))
async def lesson_command(message: Message, state: FSMContext):
    """Команда для начала урока"""
    await message.answer(MESSAGES["start_lesson"])
    await state.set_state(LessonStates.TERMS_START)
    
    from bot.handlers.lesson import start_terms_block
    await start_terms_block(message, state)


@router.message(Command("restart"))
async def restart_command(message: Message, state: FSMContext):
    """Команда перезапуска урока"""
    await state.clear()
    from bot.utils import user_progress
    user_progress.reset_progress(message.from_user.id)
    
    await message.answer(
        "🔄 Урок перезапущен!\n\nВыберите действие:",
        reply_markup=get_main_menu_keyboard()
    )


@router.message(Command("listening"))
async def listening_command(message: Message, state: FSMContext):
    """Команда для блока аудирования"""
    await message.answer("🎧 Запускаем блок аудирования...")
    from bot.handlers.lesson import start_listening_true_false
    await start_listening_true_false(message, state)


@router.message(Command("terms"))
async def terms_command(message: Message, state: FSMContext):
    """Команда для блока терминов"""
    await message.answer("📖 Запускаем блок изучения терминов...")
    from bot.handlers.lesson import start_terms_block
    await start_terms_block(message, state)


@router.callback_query(F.data == "start_lesson")
async def start_lesson(callback: CallbackQuery, state: FSMContext):
    """Начало урока"""
    await callback.message.edit_text(
        MESSAGES["start_lesson"]
    )
    
    # Переходим к блоку терминов
    await state.set_state(LessonStates.TERMS_START)
    
    # Импортируем и вызываем обработчик терминов
    from bot.handlers.lesson import start_terms_block
    await start_terms_block(callback.message, state)
    
    await callback.answer()


@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery, state: FSMContext):
    """Показать главное меню"""
    await callback.message.edit_text(
        f"{MESSAGES['welcome']}\n\n"
        "🎯 **Специализация:** Английский для программистов, Data Science и нейросетей\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "restart_lesson")
async def restart_lesson(callback: CallbackQuery, state: FSMContext):
    # Сбрасываем состояние и прогресс
    await state.clear()
    from bot.utils import user_progress
    user_progress.reset_progress(callback.from_user.id)
    
    try:
        await callback.message.edit_text(
            "🔄 Урок перезапущен! Начинаем заново.\n\nВыберите действие:",
            reply_markup=get_main_menu_keyboard()
        )
    except Exception:
        # Если не удалось изменить сообщение, отправляем новое
        await callback.message.answer(
            "🔄 Урок перезапущен! Начинаем заново.\n\nВыберите действие:",
            reply_markup=get_main_menu_keyboard()
        )
    
    await callback.answer()


@router.callback_query(F.data == "continue_lesson")
async def continue_lesson(callback: CallbackQuery, state: FSMContext):
    """Продолжить урок с текущего места"""
    from bot.utils import user_progress
    
    progress = user_progress.get_progress(callback.from_user.id)
    current_block = progress.get('current_block', 'terms')
    
    if current_block == 'terms':
        await callback.message.edit_text("📖 Продолжаем изучение терминов...")
        from bot.handlers.lesson import start_terms_block
        await start_terms_block(callback.message, state)
        
    elif current_block == 'pronunciation':
        await callback.message.edit_text("🗣️ Продолжаем блок произношения...")
        from bot.handlers.lesson import start_pronunciation_block
        await start_pronunciation_block(callback.message, state)
        
    elif current_block == 'lexical':
        await callback.message.edit_text("📝 Продолжаем лексические упражнения...")
        from bot.handlers.lesson import start_lexical_en_to_ru_block
        await start_lexical_en_to_ru_block(callback.message, state)
        
    elif current_block == 'grammar':
        await callback.message.edit_text("📚 Продолжаем изучение грамматики...")
        from bot.handlers.lesson import start_grammar_block
        await start_grammar_block(callback.message, state)
        
    elif current_block == 'lexico_grammar':
        await callback.message.edit_text("✏️ Продолжаем практические упражнения...")
        from bot.handlers.lesson import start_verb_exercise
        await start_verb_exercise(callback.message, state)
        
    elif current_block == 'listening':
        await callback.message.edit_text("🎧 Продолжаем блок аудирования...")
        from bot.handlers.lesson import start_listening_true_false
        await start_listening_true_false(callback.message, state)
        
    elif current_block == 'writing':
        await callback.message.edit_text("✍️ Продолжаем блок письменной речи...")
        from bot.handlers.lesson import start_writing_sentences
        await start_writing_sentences(callback.message, state)
        
    else:
        await callback.message.edit_text(
            "🎉 Все доступные блоки пройдены!\n\n"
            "Остальные блоки (говорение) в разработке.",
            reply_markup=get_main_menu_keyboard()
        )
    
    await callback.answer()


@router.message(Command("writing"))
async def writing_command(message: Message, state: FSMContext):
    """Команда для блока письма"""
    await message.answer("✍️ Запускаем блок письменной речи...")
    from bot.handlers.lesson import start_writing_sentences
    await start_writing_sentences(message, state)


@router.callback_query(F.data.startswith("menu_"))
async def handle_menu_navigation(callback: CallbackQuery, state: FSMContext):
    """Обработка навигации по меню"""
    menu_type = callback.data.replace("menu_", "")
    
    if menu_type == "terms":
        await callback.message.edit_text(
            "📖 **Блок: Изучение терминов**\n\n"
            "В этом блоке вы изучите ключевые термины программирования и Data Science с переводом, транскрипцией и произношением.",
            parse_mode="Markdown",
            reply_markup=get_block_menu_keyboard()
        )
        # Можно сразу запустить блок терминов
        from bot.handlers.lesson import start_terms_block
        await start_terms_block(callback.message, state)
        
    elif menu_type == "pronunciation":
        await callback.message.edit_text(
            "🗣️ **Блок: Произношение**\n\n"
            "Тренировка произношения IT терминов с голосовыми упражнениями.",
            parse_mode="Markdown", 
            reply_markup=get_block_menu_keyboard()
        )
        # Запускаем блок произношения
        from bot.handlers.lesson import start_pronunciation_block
        await start_pronunciation_block(callback.message, state)
        
    elif menu_type == "speaking":
        await callback.message.edit_text(
            "💬 **Блок: Говорение**\n\n"
            "Финальный блок курса - развитие навыков устной речи на IT темы.",
            parse_mode="Markdown"
        )
        # Запускаем блок говорения
        from bot.handlers.lesson import start_speaking_block
        await start_speaking_block(callback.message, state)
        
    elif menu_type == "lexical":
        await callback.message.edit_text(
            "📝 **Блок: Лексические упражнения**\n\n"
            "Упражнения на перевод технических терминов в обе стороны.",
            parse_mode="Markdown",
            reply_markup=get_block_menu_keyboard()
        )
        # Запускаем лексический блок
        from bot.handlers.lesson import start_lexical_en_to_ru_block
        await start_lexical_en_to_ru_block(callback.message, state)
        
    elif menu_type == "grammar":
        await callback.message.edit_text(
            "📚 **Блок: Грамматика**\n\n"
            "Изучение грамматических правил с примерами из мира программирования.",
            parse_mode="Markdown",
            reply_markup=get_block_menu_keyboard()
        )
        # Запускаем блок грамматики
        from bot.handlers.lesson import start_grammar_block
        await start_grammar_block(callback.message, state)
        
    elif menu_type == "exercises":
        await callback.message.edit_text(
            "✏️ **Блок: Практические упражнения**\n\n"
            "Лексико-грамматические упражнения на IT тематику.",
            parse_mode="Markdown",
            reply_markup=get_block_menu_keyboard()
        )
        # Запускаем блок упражнений
        from bot.handlers.lesson import start_verb_exercise
        await start_verb_exercise(callback.message, state)
    
    elif menu_type == "listening":
        await callback.message.edit_text(
            "🎧 **Блок: Аудирование**\n\n"
            "Упражнения на понимание речи на слух с IT терминологией.",
            parse_mode="Markdown"
        )
        # Запускаем блок аудирования
        from bot.handlers.lesson import start_listening_true_false
        await start_listening_true_false(callback.message, state)
        
    elif menu_type == "writing":
        await callback.message.edit_text(
            "✍️ **Блок: Письменная речь**\n\n"
            "Упражнения на составление предложений и перевод с IT терминологией.",
            parse_mode="Markdown"
        )
        # Запускаем блок письма
        from bot.handlers.lesson import start_writing_sentences
        await start_writing_sentences(callback.message, state)
   
    await callback.answer()