import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from bot.keyboards import (get_next_keyboard, get_pronunciation_keyboard, get_pronunciation_result_keyboard, 
                         get_choice_keyboard, get_continue_keyboard, get_grammar_keyboard, get_grammar_qa_keyboard,
                         get_mchoice_keyboard, get_text_exercise_keyboard, get_true_false_keyboard, 
                         get_listening_choice_keyboard, get_listening_phrases_keyboard, get_phrase_result_keyboard,
                         get_main_menu_keyboard, get_continue_writing_keyboard, get_writing_skip_keyboard,
                         get_speaking_keyboard, get_speaking_result_keyboard, get_final_keyboard, get_word_build_keyboard)
from bot.states import LessonStates
from bot.utils import (load_json_data, generate_audio, user_progress, simple_pronunciation_check, 
                      get_teacher_response, check_writing_with_ai, analyze_speaking_with_ai, transcribe_audio_simple)
from config import MESSAGES, IMAGES_PATH
from config import OPENAI_API_KEY 
from bot.utils import convert_ogg_to_wav

router = Router()



def get_keyboard_with_menu(original_keyboard):
    """Добавляет кнопки меню к любой клавиатуре"""
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    # Создаем новую клавиатуру на основе оригинальной
    keyboard = InlineKeyboardBuilder()
    
    # Добавляем кнопки из оригинальной клавиатуры
    if hasattr(original_keyboard, 'inline_keyboard'):
        for row in original_keyboard.inline_keyboard:
            for button in row:
                keyboard.button(text=button.text, callback_data=button.callback_data)
    
    # Добавляем кнопки меню
    # keyboard.button(text="🏠 Главное меню", callback_data="main_menu")
    # keyboard.button(text="🔄 Перезапуск", callback_data="restart_lesson")
    
    # Настраиваем расположение кнопок
    keyboard.adjust(1, 1, 2)  # Основные кнопки в столбец, меню в строку
    return keyboard.as_markup()


# Обработчики меню - они должны работать из любого состояния
@router.callback_query(F.data == "main_menu")
async def handle_main_menu(callback: CallbackQuery, state: FSMContext):
    """Переход в главное меню из любого состояния"""
    await callback.message.edit_text(
        "🏠 **Главное меню**\n\n"
        "🎯 **Специализация:** Английский для программистов, Data Science и нейросетей\n\n"
        "Выберите действие:",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "restart_lesson")
async def handle_restart_lesson(callback: CallbackQuery, state: FSMContext):
    """Перезапуск урока из любого состояния"""
    # Сбрасываем состояние и прогресс
    await state.clear()
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
    
async def start_terms_block(message: Message, state: FSMContext):
    """Начало блока изучения терминов"""
    # Загружаем данные терминов
    terms_data = await load_json_data("1_terms.json")
    if not terms_data or "terms" not in terms_data:
        await message.answer("Ошибка загрузки данных терминов")
        return
    
    # Сохраняем данные в состояние
    await state.update_data(terms=terms_data["terms"], current_term=0)
    
    # Отправляем инструкцию
    await message.answer(MESSAGES["terms_intro"])
    
    # Показываем первый термин
    await show_current_term(message, state)


async def show_current_term(message: Message, state: FSMContext):
    """Показать текущий термин (поэтапно)"""
    data = await state.get_data()
    terms = data.get("terms", [])
    current_index = data.get("current_term", 0)
    
    if current_index >= len(terms):
        # Все термины изучены
        await message.answer(
            MESSAGES["terms_complete"],
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        await state.set_state(LessonStates.TERMS_COMPLETE)
        return
    
    current_term = terms[current_index]
    
    # Этап 1: Показываем английский термин
    await message.answer(
        f"📝 **Термин:** {current_term['english']}",
        parse_mode="Markdown"
    )
    
    # Этап 2: Показываем перевод
    await message.answer(
        f"🇷🇺 **Перевод:** {current_term['russian']}",
        parse_mode="Markdown"
    )
    
    # Этап 3: Показываем транскрипцию
    await message.answer(
        f"🔤 **Транскрипция:** {current_term['transcription']}",
        parse_mode="Markdown"
    )
    
    # Этап 4: Показываем картинку (если есть)
    image_path = os.path.join(IMAGES_PATH, current_term.get("image", ""))
    if os.path.exists(image_path):
        try:
            photo = FSInputFile(image_path)
            await message.answer_photo(photo)
        except Exception as e:
            print(f"Ошибка отправки изображения: {e}")
            await message.answer("изображение недоступно")
    else:
        await message.answer("изображение недоступно")
    
    # Этап 5: Генерируем и отправляем аудио
    audio_filename = f"term_{current_index}_{current_term['english'].replace(' ', '_')}"
    audio_path = await generate_audio(current_term['english'], audio_filename, 'en')
    
    if audio_path and os.path.exists(audio_path):
        try:
            audio = FSInputFile(audio_path)
            await message.answer_audio(
                audio, 
                caption="🔊 **Произношение**",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Ошибка отправки аудио: {e}")
            await message.answer("🔊 **Произношение:** (аудио недоступно)")
    else:
        await message.answer("🔊 **Произношение:** (аудио недоступно)")
    
    # Кнопка "Дальше" с меню
    await message.answer(
        "Нажмите кнопку «Дальше» для продолжения",
        reply_markup=get_keyboard_with_menu(get_next_keyboard())
    )
    
    await state.set_state(LessonStates.TERMS_SHOW_AUDIO)


@router.callback_query(F.data == "next", LessonStates.TERMS_SHOW_AUDIO)
async def next_term(callback: CallbackQuery, state: FSMContext):
    """Переход к следующему термину"""
    data = await state.get_data()
    current_index = data.get("current_term", 0)
    
    # Увеличиваем индекс текущего термина
    await state.update_data(current_term=current_index + 1)
    
    # Обновляем прогресс пользователя
    user_progress.update_progress(
        callback.from_user.id, 
        current_item=current_index + 1
    )
    
    # Показываем следующий термин
    await show_current_term(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "next", LessonStates.TERMS_COMPLETE)
async def terms_complete_next(callback: CallbackQuery, state: FSMContext):
    """Завершение блока терминов и переход к произношению"""
    await callback.message.edit_text(
        "🎉 Блок терминов завершен!\n\n"
        "Переходим к блоку произношения..."
    )
    
    # Обновляем прогресс
    user_progress.update_progress(
        callback.from_user.id,
        current_block="pronunciation",
        current_item=0
    )
    
    # Запускаем блок произношения
    await start_pronunciation_block(callback.message, state)
    await callback.answer()

async def start_pronunciation_block(message: Message, state: FSMContext):
    """Начало блока произношения"""
    # Загружаем данные для произношения
    pronunciation_data = await load_json_data("2_pronouncing_words.json")
    if not pronunciation_data or "words" not in pronunciation_data:
        await message.answer("Ошибка загрузки данных для произношения")
        return
    
    # Сохраняем данные в состояние
    await state.update_data(
        pronunciation_words=pronunciation_data["words"], 
        current_pronunciation_word=0
    )
    
    # Отправляем инструкцию
    await message.answer(MESSAGES["pronunciation_intro"])
    
    # Показываем первое слово для произношения
    await show_pronunciation_word(message, state)


async def show_pronunciation_word(message: Message, state: FSMContext):
    """Показать текущее слово для произношения"""
    data = await state.get_data()
    words = data.get("pronunciation_words", [])
    current_index = data.get("current_pronunciation_word", 0)
    
    if current_index >= len(words):
        # Все слова произнесены
        await message.answer(
            MESSAGES["pronunciation_complete"],
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        await state.set_state(LessonStates.PRONUNCIATION_COMPLETE)
        return
    
    current_word = words[current_index]
    
    # Показываем информацию о слове
    await message.answer(
        f"📝 **Слово:** {current_word['english']}\n"
        f"🇷🇺 **Перевод:** {current_word['russian']}\n"
        f"🔤 **Транскрипция:** {current_word['transcription']}",
        parse_mode="Markdown"
    )
    
    # Генерируем и отправляем аудио произношения
    audio_filename = f"pronunciation_{current_index}_{current_word['english'].replace(' ', '_')}"
    audio_path = await generate_audio(current_word['english'], audio_filename, 'en')
    
    if audio_path and os.path.exists(audio_path):
        try:
            audio = FSInputFile(audio_path)
            await message.answer_audio(
                audio, 
                caption="🔊 **Послушайте произношение**",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Ошибка отправки аудио: {e}")
    
    # Инструкция и клавиатура с меню
    await message.answer(
        MESSAGES["pronunciation_instruction"],
        reply_markup=get_keyboard_with_menu(get_pronunciation_keyboard())
    )
    
    await state.set_state(LessonStates.PRONUNCIATION_LISTEN)


@router.callback_query(F.data == "record_pronunciation", LessonStates.PRONUNCIATION_LISTEN)
async def request_pronunciation_recording(callback: CallbackQuery, state: FSMContext):
    """Запрос записи произношения"""
    await callback.message.edit_text(
        "🎤 Запишите голосовое сообщение с произношением слова.\n\n"
        "Для записи голосового сообщения нажмите на микрофон в Telegram и произнесите слово.",
        reply_markup=get_keyboard_with_menu(get_pronunciation_keyboard())
    )
    
    await state.set_state(LessonStates.PRONUNCIATION_RECORD)
    await callback.answer()


@router.message(F.voice, LessonStates.PRONUNCIATION_RECORD)
async def process_pronunciation_recording(message: Message, state: FSMContext):
    """Обработка записи произношения"""
    data = await state.get_data()
    words = data.get("pronunciation_words", [])
    current_index = data.get("current_pronunciation_word", 0)

    if current_index >= len(words):
        return

    current_word = words[current_index]
    processing_msg = await message.answer("🔄 Анализирую ваше произношение...")

    try:
        # Скачиваем голосовое сообщение
        voice_file = await message.bot.get_file(message.voice.file_id)
        voice_path_ogg = f"media/audio/voice_{message.from_user.id}_{current_index}.ogg"
        voice_path_wav = voice_path_ogg.replace(".ogg", ".wav")

        await message.bot.download_file(voice_file.file_path, voice_path_ogg)

        # Конвертируем в .wav 16kHz
        if not await convert_ogg_to_wav(voice_path_ogg, voice_path_wav):
            await processing_msg.delete()
            await message.answer("⚠️ Не удалось обработать аудио.")
            return

        # Проверяем произношение
        accuracy = await simple_pronunciation_check(current_word['english'], voice_path_wav)

        # Удаляем временные файлы
        os.remove(voice_path_ogg)
        if os.path.exists(voice_path_wav):
            os.remove(voice_path_wav)

        await processing_msg.delete()

        # Формируем обратную связь
        if accuracy >= 80:
            feedback = "🎉 Отличное произношение!"
        elif accuracy >= 50:
            feedback = "👍 Хорошо, но можно лучше."
        else:
            feedback = "⚠️ Требуется больше практики."

        await message.answer(
            f"{feedback}\n\n🎯 Точность: {accuracy:.1f}%",
            reply_markup=get_keyboard_with_menu(get_pronunciation_result_keyboard())
        )

    except Exception as e:
        await processing_msg.delete()
        await message.answer("Произошла ошибка при обработке голосового сообщения.")
        print(f"Ошибка: {e}")


@router.callback_query(F.data == "skip_pronunciation", LessonStates.PRONUNCIATION_LISTEN)
@router.callback_query(F.data == "skip_pronunciation", LessonStates.PRONUNCIATION_RECORD)
@router.callback_query(F.data == "next_pronunciation")
async def next_pronunciation_word(callback: CallbackQuery, state: FSMContext):
    """Переход к следующему слову для произношения"""
    data = await state.get_data()
    current_index = data.get("current_pronunciation_word", 0)
    
    # Увеличиваем индекс
    await state.update_data(current_pronunciation_word=current_index + 1)
    
    # Обновляем прогресс пользователя
    user_progress.update_progress(
        callback.from_user.id, 
        current_item=current_index + 1
    )
    
    # Показываем следующее слово
    await show_pronunciation_word(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "retry_pronunciation")
async def retry_pronunciation(callback: CallbackQuery, state: FSMContext):
    """Повторить попытку произношения"""
    await callback.message.edit_text(
        "🎤 Попробуйте ещё раз! Запишите голосовое сообщение с произношением слова.",
        reply_markup=get_keyboard_with_menu(get_pronunciation_keyboard())
    )
    
    await state.set_state(LessonStates.PRONUNCIATION_RECORD)
    await callback.answer()


@router.callback_query(F.data == "next", LessonStates.PRONUNCIATION_COMPLETE)
async def pronunciation_complete_next(callback: CallbackQuery, state: FSMContext):
    """Завершение блока произношения и переход к лексике"""
    await callback.message.edit_text(
        "🎉 Блок произношения завершен!\n\n"
        "Переходим к лексическим упражнениям..."
    )
    
    # Обновляем прогресс
    user_progress.update_progress(
        callback.from_user.id,
        current_block="lexical",
        current_item=0
    )
    
    # Запускаем лексический блок (английский -> русский)
    await start_lexical_en_to_ru_block(callback.message, state)
    await callback.answer()

async def start_lexical_en_to_ru_block(message: Message, state: FSMContext):
    """Начало лексического блока: английский -> русский"""
    # Загружаем данные
    lexical_data = await load_json_data("translation_questions.json")
    if not lexical_data:
        await message.answer("Ошибка загрузки лексических данных")
        return
    
    # Преобразуем данные в список
    questions = []
    for word, data in lexical_data.items():
        questions.append({
            "word": word,
            "correct": data["correct"],
            "options": data["options"]
        })
    
    # Сохраняем данные в состояние
    await state.update_data(
        lexical_en_ru=questions,
        current_lexical_en=0,
        lexical_score=0
    )
    
    # Отправляем инструкцию
    await message.answer(MESSAGES["lexical_intro"])
    
    # Показываем первый вопрос
    await show_lexical_en_question(message, state)


async def show_lexical_en_question(message: Message, state: FSMContext):
    """Показать вопрос английский -> русский"""
    data = await state.get_data()
    questions = data.get("lexical_en_ru", [])
    current_index = data.get("current_lexical_en", 0)
    
    if current_index >= len(questions):
        # Все вопросы пройдены
        score = data.get("lexical_score", 0)
        await message.answer(
            f"{MESSAGES['lexical_en_ru_complete']}\n\n"
            f"Ваш результат: {score}/{len(questions)} ✨",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        await state.set_state(LessonStates.LEXICAL_EN_COMPLETE)
        return
    
    current_question = questions[current_index]
    
    # Отправляем вопрос
    question_text = f"📝 **Переведите слово ({current_index + 1}/{len(questions)}):**\n\n**{current_question['word']}**"
    
    await message.answer(
        question_text,
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_choice_keyboard(current_question['options'], str(current_index)))
    )
    
    await state.set_state(LessonStates.LEXICAL_EN_TO_RU)


@router.callback_query(F.data.startswith("lexical_"), LessonStates.LEXICAL_EN_TO_RU)
async def process_lexical_en_answer(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа на английский -> русский"""
    data = await state.get_data()
    questions = data.get("lexical_en_ru", [])
    current_index = data.get("current_lexical_en", 0)
    score = data.get("lexical_score", 0)
    
    if current_index >= len(questions):
        return
    
    current_question = questions[current_index]
    
    # Извлекаем выбранный ответ из callback_data
    callback_parts = callback.data.split("_", 2)
    if len(callback_parts) >= 3:
        selected_answer = callback_parts[2]
    else:
        selected_answer = ""
    
    correct_answer = current_question["correct"]
    
    # Проверяем ответ
    if selected_answer == correct_answer:
        response_text = MESSAGES["correct_answer"]
        score += 1
        await state.update_data(lexical_score=score)
    else:
        response_text = f"{MESSAGES['wrong_answer']}{correct_answer}"
    
    # Отправляем результат
    await callback.message.edit_text(
        f"**{current_question['word']}** → **{correct_answer}**\n\n{response_text}",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_continue_keyboard())
    )
    
    await callback.answer()


@router.callback_query(F.data == "continue_lexical", LessonStates.LEXICAL_EN_TO_RU)
async def continue_lexical_en_to_ru(callback: CallbackQuery, state: FSMContext):
    """Продолжить лексический блок английский -> русский"""
    
    # 🔍 DEBUG: Сообщаем, что функция начала работу
    print("[DEBUG] Запущен обработчик continue_lexical_en_to_ru")
    
    # Получаем данные из состояния
    data = await state.get_data()
    
    # 🔍 DEBUG: Выводим текущие данные из состояния
    print("[DEBUG] Текущие данные из state:", data)
    
    current_index = data.get("current_lexical_en", 0)
    
    # 🔍 DEBUG: Выводим текущий индекс
    print(f"[DEBUG] Текущий индекс вопроса: {current_index}")
    
    # Обновляем индекс
    new_index = current_index + 1
    await state.update_data(current_lexical_en=new_index)
    
    # 🔍 DEBUG: Подтверждаем обновление индекса
    print(f"[DEBUG] Индекс увеличен. Новый индекс: {new_index}")
    
    # Показываем следующий вопрос
    try:
        await show_lexical_en_question(callback.message, state)
        print("[DEBUG] Функция show_lexical_en_question успешно вызвана")
    except Exception as e:
        print(f"[ERROR] Ошибка при вызове show_lexical_en_question: {e}")
    
    # Отвечаем на callback
    await callback.answer()


@router.callback_query(F.data == "next", LessonStates.LEXICAL_EN_COMPLETE)
async def lexical_en_complete_next(callback: CallbackQuery, state: FSMContext):
    """Завершение блока английский -> русский, переход к русский -> английский"""
    await callback.message.edit_text(
        "Отлично! Теперь попробуем в обратную сторону..."
    )
    
    # Запускаем блок русский -> английский
    await start_lexical_ru_to_en_block(callback.message, state)
    await callback.answer()

async def start_lexical_ru_to_en_block(message: Message, state: FSMContext):
    """Начало лексического блока: русский -> английский"""
    # Загружаем данные
    lexical_data = await load_json_data("translation_questions_russian.json")
    if not lexical_data:
        await message.answer("Ошибка загрузки лексических данных (русский)")
        return
    
    # Преобразуем данные в список
    questions = []
    for word, data in lexical_data.items():
        questions.append({
            "word": word,
            "correct": data["correct"],
            "options": data["options"]
        })
    
    # Сохраняем данные в состояние
    await state.update_data(
        lexical_ru_en=questions,
        current_lexical_ru=0,
        lexical_ru_score=0
    )
    
    # Отправляем инструкцию
    await message.answer(MESSAGES["lexical_intro"])
    
    # Показываем первый вопрос
    await show_lexical_ru_question(message, state)


async def show_lexical_ru_question(message: Message, state: FSMContext):
    """Показать вопрос русский -> английский"""
    data = await state.get_data()
    questions = data.get("lexical_ru_en", [])
    current_index = data.get("current_lexical_ru", 0)
    
    if current_index >= len(questions):
        # Все вопросы пройдены
        score = data.get("lexical_ru_score", 0)
        await message.answer(
            f"{MESSAGES['lexical_ru_en_complete']}\n\n"
            f"Ваш результат: {score}/{len(questions)} ✨",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        await state.set_state(LessonStates.LEXICAL_RU_COMPLETE)
        return
    
    current_question = questions[current_index]
    
    # Отправляем вопрос
    question_text = f"📝 **Переведите слово ({current_index + 1}/{len(questions)}):**\n\n**{current_question['word']}**"
    
    await message.answer(
        question_text,
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_choice_keyboard(current_question['options'], f"ru_{current_index}"))
    )
    
    await state.set_state(LessonStates.LEXICAL_RU_TO_EN)


@router.callback_query(F.data.startswith("lexical_"), LessonStates.LEXICAL_RU_TO_EN)
async def process_lexical_ru_answer(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа на русский -> английский"""
    data = await state.get_data()
    questions = data.get("lexical_ru_en", [])
    current_index = data.get("current_lexical_ru", 0)
    score = data.get("lexical_ru_score", 0)
    
    if current_index >= len(questions):
        return
    
    current_question = questions[current_index]
    
 # Извлекаем выбранный ответ из callback_data
    callback_parts = callback.data.split("_")
    if len(callback_parts) >= 4:
        selected_answer = callback_parts[-1]  # Берем последний элемент - это вариант ответа
    else:
        selected_answer = ""
        
    correct_answer = current_question["correct"]
    
    # Проверяем ответ
    if selected_answer == correct_answer:
        response_text = MESSAGES["correct_answer"]
        score += 1
        await state.update_data(lexical_ru_score=score)
    else:
        response_text = f"{MESSAGES['wrong_answer']}{correct_answer}"
    
    # Отправляем результат
    await callback.message.edit_text(
        f"**{current_question['word']}** → **{correct_answer}**\n\n{response_text}",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_continue_keyboard())
    )
    
    await callback.answer()


@router.callback_query(F.data == "continue_lexical", LessonStates.LEXICAL_RU_TO_EN)
async def continue_lexical_ru_to_en(callback: CallbackQuery, state: FSMContext):
    """Продолжить русский -> английский"""
    data = await state.get_data()
    current_index = data.get("current_lexical_ru", 0)
    await state.update_data(current_lexical_ru=current_index + 1)
    
    await show_lexical_ru_question(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "next", LessonStates.LEXICAL_RU_COMPLETE)
async def lexical_complete_next(callback: CallbackQuery, state: FSMContext):
    """Упражнение-игра (геймификация)"""
    await callback.message.edit_text(
        "🎉 Еще одно упражнение завершено!\n\n"
        "Теперь попробуйте собрать слова из частей."
    )
    
    # Обновляем прогресс
    user_progress.update_progress(
        callback.from_user.id,
        current_block="lexical",
        current_item=0
    )
    
    # Запускаем упражнение на сборку слов
    await start_word_build(callback, state)
    
    await callback.answer()


# --- Упражнение: Сборка слова из частей ---

async def start_word_build(callback: CallbackQuery, state: FSMContext):
    """Начало упражнения на сборку слов"""
    data = await load_json_data("word_build.json")
    if not data:
        await callback.message.answer("Ошибка загрузки данных")
        return

    words = list(data.keys())
    await state.update_data(
        word_build_data=data,
        word_build_words=words,
        current_word_index=0,
        word_build_collected="",
        word_build_score=0
    )

    await show_word_build_exercise(callback.message, state)
    await callback.answer()


async def show_word_build_exercise(message: Message, state: FSMContext):
    data = await state.get_data()
    words = data.get("word_build_words", [])
    index = data.get("current_word_index", 0)
    all_data = data.get("word_build_data", {})

    if index >= len(words):
        await finish_word_build(message, state)
        return

    word = words[index]
    parts = all_data[word]["scrambled_parts"]
    collected = data.get("word_build_collected", "")

    placeholder = " ".join(["_" * len(part) for part in all_data[word]["parts"]])
    user_input = " + ".join(collected.split("+")) if collected else ""

    text = (
        f"🔤 Собери слово из частей:\n\n"
        f"{placeholder}\n\n"
        f"Ты собрал: {user_input or 'ничего'}\n\n"
        f"Выбери части:"
    )

    await message.edit_text(text, reply_markup=get_word_build_keyboard(parts, collected))
    await state.set_state(LessonStates.LEXICAL_WORD_BUILD)


async def finish_word_build(message: Message, state: FSMContext):
    data = await state.get_data()
    total = len(data.get("word_build_words", []))
    score = data.get("word_build_score", 0)

    result_text = (
        f"🎉 Упражнение завершено!\n"
        f"Вы правильно собрали {score} из {total} слов."
    )

    await message.edit_text(result_text, reply_markup=get_keyboard_with_menu(get_next_keyboard()))
    await state.set_state(LessonStates.LEXICAL_WORD_COMPLETE)


@router.callback_query(F.data.startswith("wb_part_"))
async def handle_word_part(callback: CallbackQuery, state: FSMContext):
    part = callback.data.replace("wb_part_", "")
    data = await state.get_data()
    collected = data.get("word_build_collected", "")
    collected += "+" + part if collected else part
    await state.update_data(word_build_collected=collected)
    await show_word_build_exercise(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "wb_check")
async def check_word_build(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    words = data.get("word_build_words", [])
    index = data.get("current_word_index", 0)
    all_data = data.get("word_build_data", {})
    collected = data.get("word_build_collected", "")

    word = words[index]
    correct_parts = all_data[word]["parts"]
    user_parts = collected.split("+")

    if user_parts == correct_parts:
        score = data.get("word_build_score", 0) + 1
        await state.update_data(word_build_score=score)

        # Показываем результат и кнопку "Далее"
        await callback.message.edit_text(
            f"✅ Правильный ответ!\n\n"
            f"Вы собрали: {' + '.join(correct_parts)}\n\n"
            f"Нажмите «➡️ Далее», чтобы продолжить.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➡️ Далее", callback_data="wb_next")]
            ])
        )
    else:
        correct = " + ".join(correct_parts)
        await callback.message.edit_text(
            f"❌ Неправильно.\nПравильный ответ: {correct}\n\n"
            f"Нажмите «➡️ Далее».",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➡️ Далее", callback_data="wb_next")]
            ])
        )


@router.callback_query(F.data == "wb_next")
async def next_word_after_check(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index = data.get("current_word_index", 0)

    await state.update_data(
        current_word_index=index + 1,
        word_build_collected=""
    )

    await show_word_build_exercise_new(callback.message, state)
    await callback.answer()
    
@router.callback_query(F.data == "wb_skip")
async def skip_word_build(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    index = data.get("current_word_index", 0)

    await state.update_data(
        current_word_index=index + 1,
        word_build_collected=""
    )

    await show_word_build_exercise_new(callback.message, state)
    await callback.answer()

async def show_word_build_exercise_new(message: Message, state: FSMContext):
    data = await state.get_data()
    words = data.get("word_build_words", [])
    index = data.get("current_word_index", 0)
    all_data = data.get("word_build_data", {})

    if index >= len(words):
        await finish_word_build(message, state)
        return

    word = words[index]
    parts = all_data[word]["scrambled_parts"]
    collected = data.get("word_build_collected", "")

    placeholder = " ".join(["_" * len(part) for part in all_data[word]["parts"]])
    user_input = " + ".join(collected.split("+")) if collected else ""

    text = (
        f"🔤 Собери слово из частей:\n\n"
        f"{placeholder}\n\n"
        f"Ты собрал: {user_input or 'ничего'}\n\n"
        f"Выбери части:"
    )
    
    await message.answer(text, reply_markup=get_word_build_keyboard(parts, collected))

@router.callback_query(F.data == "next", LessonStates.LEXICAL_WORD_COMPLETE)
async def word_build_complete_next(callback: CallbackQuery, state: FSMContext):
    # Отправляем новое сообщение (не меняем старое!)
    await callback.message.answer("🔤 Слово собрано правильно!\n\n"
                                  "🎉 Отличная работа!\n"
                                  "Переходим к изучению грамматики.")
    
    # Переход к грамматике
    await start_grammar_block(callback.message, state)
    
    await callback.answer()

# --- Конец упражнения: Сборка слова ---

async def start_grammar_block(message: Message, state: FSMContext):
    """Начало грамматического блока"""
    # Отправляем инструкцию
    await message.answer(MESSAGES["grammar_intro"])
    
    # Загружаем грамматическое правило
    grammar_data = await load_json_data("present_simple.json")
    if not grammar_data or "rule" not in grammar_data:
        await message.answer("Ошибка загрузки грамматических правил")
        return
    
    # Сохраняем данные в состояние
    await state.update_data(grammar_rule=grammar_data["rule"])
    
    # Отправляем правило
    await message.answer(
        f"📚 **Грамматическое правило:**\n\n{grammar_data['rule']}",
        parse_mode="Markdown"
    )
    
    # Показываем клавиатуру выбора с меню
    await message.answer(
        "Как дела с пониманием?",
        reply_markup=get_keyboard_with_menu(get_grammar_keyboard())
    )
    
    await state.set_state(LessonStates.GRAMMAR_CHOICE)


@router.callback_query(F.data == "grammar_understood", LessonStates.GRAMMAR_CHOICE)
async def grammar_understood(callback: CallbackQuery, state: FSMContext):
    """Пользователь понял грамматику"""
    await callback.message.edit_text(
        "🎉 Отлично! Вы поняли грамматическое правило!\n\n"
        "Переходим к следующему блоку...",
        reply_markup=get_keyboard_with_menu(get_next_keyboard())
    )
    
    await state.set_state(LessonStates.GRAMMAR_COMPLETE)
    await callback.answer()


@router.callback_query(F.data == "grammar_questions", LessonStates.GRAMMAR_CHOICE)
async def grammar_questions(callback: CallbackQuery, state: FSMContext):
    """Пользователь хочет задать вопросы"""
    await callback.message.edit_text(
        MESSAGES["grammar_ask_question"],
        reply_markup=get_keyboard_with_menu(get_grammar_qa_keyboard())
    )
    
    await state.set_state(LessonStates.GRAMMAR_QA)
    await callback.answer()


@router.message(F.text, LessonStates.GRAMMAR_QA)
async def process_grammar_question(message: Message, state: FSMContext):
    """Обработка вопроса по грамматике"""
    user_question = message.text
    
    # Показываем, что обрабатываем вопрос
    thinking_msg = await message.answer(MESSAGES["teacher_thinking"])
    
    try:
        # Получаем ответ от AI агента-учителя
        teacher_response = await get_teacher_response(user_question)
        
        # Удаляем сообщение "думаю"
        await thinking_msg.delete()
        
        # Отправляем ответ учителя
        await message.answer(
            teacher_response,
            reply_markup=get_keyboard_with_menu(get_grammar_qa_keyboard())
        )
        
    except Exception as e:
        await thinking_msg.delete()
        await message.answer(
            "Извините, произошла ошибка при обработке вашего вопроса. "
            "Попробуйте переформулировать вопрос.",
            reply_markup=get_keyboard_with_menu(get_grammar_qa_keyboard())
        )
        print(f"Ошибка в обработке вопроса: {e}")


@router.callback_query(F.data == "grammar_now_understood", LessonStates.GRAMMAR_QA)
async def grammar_now_understood(callback: CallbackQuery, state: FSMContext):
    """Пользователь понял после объяснения"""
    await callback.message.edit_text(
        "🎉 Превосходно! Теперь вы понимаете грамматическое правило!\n\n"
        "Переходим к следующему блоку...",
        reply_markup=get_keyboard_with_menu(get_next_keyboard())
    )
    
    await state.set_state(LessonStates.GRAMMAR_COMPLETE)
    await callback.answer()


@router.callback_query(F.data == "grammar_still_questions", LessonStates.GRAMMAR_QA)
async def grammar_still_questions(callback: CallbackQuery, state: FSMContext):
    """У пользователя остались вопросы"""
    await callback.message.edit_text(
        "Задайте следующий вопрос по грамматике:",
        reply_markup=get_keyboard_with_menu(get_grammar_qa_keyboard())
    )
    
    # Остаемся в состоянии GRAMMAR_QA для продолжения диалога
    await callback.answer()


@router.callback_query(F.data == "next", LessonStates.GRAMMAR_COMPLETE)
async def grammar_complete_next(callback: CallbackQuery, state: FSMContext):
    """Завершение грамматического блока и переход к лексико-грамматическим упражнениям"""
    await callback.message.edit_text(
        "🎉 Грамматический блок завершен!\n\n"
        "Переходим к практическим упражнениям..."
    )
    
    # Обновляем прогресс
    user_progress.update_progress(
        callback.from_user.id,
        current_block="lexico_grammar",
        current_item=0
    )
    
    # Запускаем упражнения с глаголами
    await start_verb_exercise(callback.message, state)
    await callback.answer()

async def start_verb_exercise(message: Message, state: FSMContext):
    """Начало упражнений с глаголами"""
    # Загружаем данные
    verb_data = await load_json_data("verb_it.json")
    print(f"DEBUG: verb_data = {verb_data}") 
    if not verb_data:
        await message.answer("Ошибка загрузки данных упражнений")
        return
        
    print(f"DEBUG: verb_data length = {len(verb_data)}")  
    
    # Сохраняем данные в состояние
    await state.update_data(
        verb_exercises=verb_data,
        current_verb=0,
        verb_score=0
    )
    
    # Отправляем инструкцию
    await message.answer(MESSAGES["verb_exercise_intro"])
    
    # Показываем первое упражнение
    await show_verb_exercise(message, state)


async def show_verb_exercise(message: Message, state: FSMContext):
    """Показать упражнение с глаголами"""
    data = await state.get_data()
    exercises = data.get("verb_exercises", [])
    current_index = data.get("current_verb", 0)
    
    if current_index >= len(exercises):
        # Все упражнения выполнены
        score = data.get("verb_score", 0)
        await message.answer(
            f"{MESSAGES['verb_exercise_complete']}\n\n"
            f"Ваш результат: {score}/{len(exercises)} ✨",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        await state.set_state(LessonStates.VERB_COMPLETE)
        return
    
    current_exercise = exercises[current_index]
    
    # Отправляем упражнение
    await message.answer(
        f"💻 **Упражнение {current_index + 1}/{len(exercises)}:**\n\n{current_exercise['text']}",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_text_exercise_keyboard())
    )
    
    await state.set_state(LessonStates.VERB_EXERCISE)


@router.message(F.text, LessonStates.VERB_EXERCISE)
async def process_verb_answer(message: Message, state: FSMContext):
    """Обработка ответа на упражнение с глаголами"""
    data = await state.get_data()
    exercises = data.get("verb_exercises", [])
    current_index = data.get("current_verb", 0)
    score = data.get("verb_score", 0)
    
    if current_index >= len(exercises):
        return
    
    current_exercise = exercises[current_index]
    user_answer = message.text.strip().lower()
    correct_answer = current_exercise["answer"].lower()
    
    # Проверяем ответ
    if user_answer == correct_answer:
        response_text = MESSAGES["correct_answer"]
        score += 1
        await state.update_data(verb_score=score)
    else:
        response_text = f"{MESSAGES['wrong_answer']}{current_exercise['answer']}"
    
    # Отправляем результат
    await message.answer(
        f"**Правильный ответ:** {current_exercise['answer']}\n\n{response_text}",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_continue_keyboard())
    )


@router.callback_query(F.data == "skip_text_exercise", LessonStates.VERB_EXERCISE)
async def skip_verb_exercise(callback: CallbackQuery, state: FSMContext):
    """Пропустить упражнение с глаголами"""
    data = await state.get_data()
    current_index = data.get("current_verb", 0)
    await state.update_data(current_verb=current_index + 1)
    
    await show_verb_exercise(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "continue_exercise", LessonStates.VERB_EXERCISE)
async def continue_verb_exercise_specific(callback: CallbackQuery, state: FSMContext):
    """Продолжить упражнения с глаголами"""
    data = await state.get_data()
    current_index = data.get("current_verb", 0)
    await state.update_data(current_verb=current_index + 1)
    
    await show_verb_exercise(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "next", LessonStates.VERB_COMPLETE)
async def verb_complete_next(callback: CallbackQuery, state: FSMContext):
    """Завершение упражнений с глаголами, переход к множественному выбору"""
    await callback.message.edit_text("Отлично! Переходим к следующему типу упражнений...")
    
    await start_mchoice_exercise(callback.message, state)
    await callback.answer()

async def start_mchoice_exercise(message: Message, state: FSMContext):
    """Начало упражнений с множественным выбором"""
    # Загружаем данные
    mchoice_data = await load_json_data("mchoice_it.json")
    if not mchoice_data:
        await message.answer("Ошибка загрузки данных упражнений с выбором")
        return
    
    # Сохраняем данные в состояние
    await state.update_data(
        mchoice_exercises=mchoice_data,
        current_mchoice=0,
        mchoice_score=0
    )
    
    # Отправляем инструкцию
    await message.answer(MESSAGES["mchoice_intro"])
    
    # Показываем первое упражнение
    await show_mchoice_exercise(message, state)


async def show_mchoice_exercise(message: Message, state: FSMContext):
    """Показать упражнение с множественным выбором"""
    data = await state.get_data()
    exercises = data.get("mchoice_exercises", [])
    current_index = data.get("current_mchoice", 0)
    
    if current_index >= len(exercises):
        # Все упражнения выполнены
        score = data.get("mchoice_score", 0)
        await message.answer(
            f"{MESSAGES['mchoice_complete']}\n\n"
            f"Ваш результат: {score}/{len(exercises)} ✨",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        await state.set_state(LessonStates.MCHOICE_COMPLETE)
        return
    
    current_exercise = exercises[current_index]
    
    # Отправляем упражнение
    await message.answer(
        f"💻 **Выберите правильный вариант ({current_index + 1}/{len(exercises)}):**\n\n{current_exercise['sentence']}",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_mchoice_keyboard(current_exercise['options'], current_index))
    )
    
    await state.set_state(LessonStates.MCHOICE_EXERCISE)


@router.callback_query(F.data.startswith("mchoice_"), LessonStates.MCHOICE_EXERCISE)
async def process_mchoice_answer(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа на упражнение с множественным выбором"""
    data = await state.get_data()
    exercises = data.get("mchoice_exercises", [])
    current_index = data.get("current_mchoice", 0)
    score = data.get("mchoice_score", 0)
    
    if current_index >= len(exercises):
        return
    
    current_exercise = exercises[current_index]
    
    # Извлекаем выбранный ответ
    parts = callback.data.split("_")
    if len(parts) >= 4:
        selected_answer = parts[3]
    else:
        selected_answer = ""
    
    correct_answer = current_exercise["answer"]
    
    # Проверяем ответ
    if selected_answer == correct_answer:
        response_text = MESSAGES["correct_answer"]
        score += 1
        await state.update_data(mchoice_score=score)
    else:
        response_text = f"{MESSAGES['wrong_answer']}{correct_answer}"
    
    # Отправляем результат
    await callback.message.edit_text(
        f"**Вопрос:** {current_exercise['sentence']}\n"
        f"**Правильный ответ:** {correct_answer}\n\n{response_text}",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_continue_keyboard())
    )
    
    await callback.answer()


@router.callback_query(F.data == "continue_exercise", LessonStates.MCHOICE_EXERCISE)
async def continue_mchoice_exercise_specific(callback: CallbackQuery, state: FSMContext):
    """Продолжить упражнения с множественным выбором"""
    data = await state.get_data()
    current_index = data.get("current_mchoice", 0)
    await state.update_data(current_mchoice=current_index + 1)
    
    await show_mchoice_exercise(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "next", LessonStates.MCHOICE_COMPLETE)
async def mchoice_complete_next(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Отлично! Теперь попробуем строить отрицательные предложения.")

    # Один раз запускаем упражнение
    await start_negative_exercise(callback.message, state)

    # Обновляем прогресс
    user_progress.update_progress(
        callback.from_user.id,
        current_block="lexico_grammar",
        current_item=0
    )

    await callback.answer()
    
async def start_negative_exercise(message: Message, state: FSMContext):
    """Начало упражнений на преобразование предложений в отрицательную форму"""
    negative_data = await load_json_data("negative_it.json")
    if not negative_data:
        await message.answer("Ошибка загрузки данных для упражнений на отрицательные предложения")
        return

    await state.update_data(
        negative_exercises=negative_data,
        current_negative=0,
        negative_score=0
    )

    await message.answer("✍️ **Инструкция:** Преобразуйте предложение в отрицательную форму и отправьте исправленный вариант.")
 
    await show_negative_exercise(message, state)
    
async def show_negative_exercise(message: Message, state: FSMContext):
    data = await state.get_data()
    exercises = data.get("negative_exercises", [])
    current_index = data.get("current_negative", 0)

    if current_index >= len(exercises):
        score = data.get("negative_score", 0)
        await message.answer(
            f"🎉 Вы успешно выполнили все упражнения!\nВаш результат: {score}/{len(exercises)} ✨",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        await state.set_state(LessonStates.NEGATIVE_COMPLETE)
        return

    current_exercise = exercises[current_index]
    await message.answer(
        f"💻 **Упражнение {current_index + 1}/{len(exercises)}:**\n"
        f"{current_exercise['text']}",
        parse_mode="Markdown"
    )
    await state.set_state(LessonStates.NEGATIVE_EXERCISE)  # ← Установка состояния


@router.message(F.text, LessonStates.NEGATIVE_EXERCISE)
async def process_negative_answer(message: Message, state: FSMContext):
    user_answer = message.text.strip().lower()
    data = await state.get_data()
    exercises = data.get("negative_exercises", [])
    current_index = data.get("current_negative", 0)
    score = data.get("negative_score", 0)

    if current_index >= len(exercises):
        return

    current_exercise = exercises[current_index]
    correct_answers = [ans.lower() for ans in current_exercise["answer"]]

    if any(user_answer == ans for ans in correct_answers):
        response_text = "✅ Правильно!"
        score += 1
        await state.update_data(negative_score=score)
    else:
        examples = "\n".join([f"- {ans}" for ans in current_exercise["answer"]])
        response_text = f"❌ Неправильно.\nПравильные варианты:\n{examples}"

    await message.answer(f"{response_text}\n\nПереходим к следующему упражнению...")
    await state.update_data(current_negative=current_index + 1)
    await show_negative_exercise(message, state)

    
@router.callback_query(F.data == "next", LessonStates.NEGATIVE_COMPLETE)
async def negative_complete_next(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Отлично! Переходим к следующему типу упражнений...")
    await start_question_exercise(callback.message, state)  # ← Заменено
    await callback.answer()
    
async def start_question_exercise(message: Message, state: FSMContext):
    """Начало упражнения на преобразование предложений в вопросительную форму"""
    question_data = await load_json_data("question_it.json")
    if not question_data:
        await message.answer("Ошибка загрузки данных для упражнений на вопросительные предложения")
        return

    await state.update_data(
        question_exercises=question_data,
        current_question=0,
        question_score=0
    )

    await message.answer(
        "❓ **Инструкция:** Преобразуйте предложение в вопросительную форму и отправьте исправленный вариант."
    )
    await show_question_exercise(message, state)


async def show_question_exercise(message: Message, state: FSMContext):
    data = await state.get_data()
    exercises = data.get("question_exercises", [])
    current_index = data.get("current_question", 0)

    if current_index >= len(exercises):
        score = data.get("question_score", 0)
        await message.answer(
            f"🎉 Вы успешно выполнили все упражнения на вопросительные формы!\n"
            f"Ваш результат: {score}/{len(exercises)} ✨",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        await state.set_state(LessonStates.QUESTION_COMPLETE)
        return

    current_exercise = exercises[current_index]
    await message.answer(
        f"💻 **Упражнение {current_index + 1}/{len(exercises)}:**\n"
        f"{current_exercise['text']}",
        parse_mode="Markdown"
    )
    await state.set_state(LessonStates.QUESTION_EXERCISE)


@router.message(F.text, LessonStates.QUESTION_EXERCISE)
async def process_question_answer(message: Message, state: FSMContext):
    user_answer = message.text.strip().lower()
    data = await state.get_data()
    exercises = data.get("question_exercises", [])
    current_index = data.get("current_question", 0)
    score = data.get("question_score", 0)

    if current_index >= len(exercises):
        return

    current_exercise = exercises[current_index]
    correct_answer = current_exercise["answer"].lower()

    if user_answer == correct_answer:
        response_text = "✅ Правильно!"
        score += 1
        await state.update_data(question_score=score)
    else:
        response_text = (
            f"❌ Неправильно.\nПравильный вариант:\n- {current_exercise['answer']}"
        )

    await message.answer(
        f"{response_text}\n\nПереходим к следующему упражнению...",
        parse_mode="Markdown"
    )

    await state.update_data(current_question=current_index + 1)
    await show_question_exercise(message, state)
    
@router.callback_query(F.data == "next", LessonStates.QUESTION_COMPLETE)
async def question_complete_next(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Отлично! Переходим к аудированию...")
    await start_missing_word(callback.message, state)
    await callback.answer()
    
async def start_missing_word(message: Message, state: FSMContext):
    """Начало упражнения 'Вставить пропущенное слово'"""
    missing_data = await load_json_data("missing_word_it.json")
    if not missing_data:
        await message.answer("Ошибка загрузки данных для упражнения 'Пропущенное слово'")
        return

    await state.update_data(
        missing_words=missing_data,
        current_missing=0,
        missing_score=0
    )

    await message.answer(
        "🔤 **Инструкция:** Вставьте пропущенное слово в предложении и отправьте свой вариант."
    )
    await show_missing_word_exercise(message, state)


async def show_missing_word_exercise(message: Message, state: FSMContext):
    data = await state.get_data()
    exercises = data.get("missing_words", [])
    current_index = data.get("current_missing", 0)

    if current_index >= len(exercises):
        score = data.get("missing_score", 0)
        await message.answer(
            f"🎉 Вы успешно выполнили все упражнения на восстановление пропущенных слов!\n"
            f"Ваш результат: {score}/{len(exercises)} ✨",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        await state.set_state(LessonStates.MISSING_WORD_COMPLETE)
        return

    current_exercise = exercises[current_index]

    # Экранируем подчёркивания для корректного отображения в Markdown
    escaped_statement = current_exercise["statement"].replace("_", r"\_")

    await message.answer(
        f"💻 **Упражнение {current_index + 1}/{len(exercises)}:**\n"
        f"{escaped_statement}",
        parse_mode="Markdown"
    )
    await state.set_state(LessonStates.MISSING_WORD_EXERCISE)


@router.message(F.text, LessonStates.MISSING_WORD_EXERCISE)
async def process_missing_word_answer(message: Message, state: FSMContext):
    user_answer = message.text.strip().lower()
    data = await state.get_data()
    exercises = data.get("missing_words", [])
    current_index = data.get("current_missing", 0)
    score = data.get("missing_score", 0)

    if current_index >= len(exercises):
        return

    current_exercise = exercises[current_index]
    correct_answers = [ans.lower() for ans in current_exercise["answers"]]

    if user_answer in correct_answers:
        response_text = "✅ Правильно!"
        score += 1
        await state.update_data(missing_score=score)
    else:
        examples = "\n".join([f"- {ans}" for ans in current_exercise["answers"]])
        response_text = f"❌ Неправильно.\nПравильные варианты:\n{examples}"

    await message.answer(
        f"{response_text}\n\nПереходим к следующему упражнению...",
        parse_mode="Markdown"
    )

    await state.update_data(current_missing=current_index + 1)
    await show_missing_word_exercise(message, state)
    
@router.callback_query(F.data == "next", LessonStates.MISSING_WORD_COMPLETE)
async def missing_word_complete_next(callback: CallbackQuery, state: FSMContext):
    """Завершение упражнения 'Пропущенное слово', переход к  аудированию"""
    await callback.message.edit_text("Отлично! Переходим к аудированию...")
    await start_listening_true_false(callback.message, state)
    await callback.answer()

async def start_listening_true_false(message: Message, state: FSMContext):
    """Начало упражнений True/False для аудирования"""
    # Загружаем данные
    listening_data = await load_json_data("listening_tasks_it.json")
    if not listening_data:
        await message.answer("Ошибка загрузки данных аудирования")
        return
    
    # Сохраняем данные в состояние
    await state.update_data(
        listening_true_false=listening_data,
        current_listening_tf=0,
        listening_tf_score=0
    )
    
    # Отправляем инструкцию
    await message.answer(MESSAGES["listening_true_false_intro"])
    
    # Показываем первое упражнение
    await show_listening_true_false(message, state)


async def show_listening_true_false(message: Message, state: FSMContext):
    """Показать упражнение True/False для аудирования"""
    data = await state.get_data()
    exercises = data.get("listening_true_false", [])
    current_index = data.get("current_listening_tf", 0)
    
    if current_index >= len(exercises):
        # Все упражнения выполнены
        score = data.get("listening_tf_score", 0)
        await message.answer(
            f"{MESSAGES['listening_true_false_complete']}\n\n"
            f"Ваш результат: {score}/{len(exercises)} ✨",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        await state.set_state(LessonStates.LISTENING_TRUE_FALSE_COMPLETE)
        return
    
    current_exercise = exercises[current_index]
    
    # Генерируем аудио для фразы
    audio_filename = f"listening_tf_{current_index}_{current_exercise['phrase'][:20].replace(' ', '_')}"
    audio_path = await generate_audio(current_exercise['phrase'], audio_filename, 'en')
    
    # Отправляем аудио
    if audio_path and os.path.exists(audio_path):
        try:
            audio = FSInputFile(audio_path)
            await message.answer_audio(
                audio,
                caption="🎧 **Прослушайте фразу**",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Ошибка отправки аудио: {e}")
            await message.answer("🎧 **Аудио недоступно**")
    
    # Отправляем утверждение для проверки
    await message.answer(
        f"📝 **Утверждение ({current_index + 1}/{len(exercises)}):**\n\n{current_exercise['statement']}",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_true_false_keyboard())
    )
    
    await state.set_state(LessonStates.LISTENING_TRUE_FALSE)


@router.callback_query(F.data.startswith("listening_"), LessonStates.LISTENING_TRUE_FALSE)
async def process_listening_true_false_answer(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа True/False для аудирования"""
    data = await state.get_data()
    exercises = data.get("listening_true_false", [])
    current_index = data.get("current_listening_tf", 0)
    score = data.get("listening_tf_score", 0)
    
    if current_index >= len(exercises):
        return
    
    current_exercise = exercises[current_index]
    
    # Определяем выбранный ответ
    if callback.data == "listening_true":
        selected_answer = "True"
    else:
        selected_answer = "False"
    
    correct_answer = current_exercise["correct_answer"]
    
    # Проверяем ответ
    if selected_answer == correct_answer:
        response_text = MESSAGES["correct_answer"]
        score += 1
        await state.update_data(listening_tf_score=score)
    else:
        response_text = f"{MESSAGES['wrong_answer']}{correct_answer}"
    
    # Отправляем результат
    await callback.message.edit_text(
        f"**Фраза:** {current_exercise['phrase']}\n"
        f"**Утверждение:** {current_exercise['statement']}\n"
        f"**Правильный ответ:** {correct_answer}\n\n{response_text}",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_continue_keyboard())
    )
    
    await callback.answer()


@router.callback_query(F.data == "continue_exercise", LessonStates.LISTENING_TRUE_FALSE)
async def continue_listening_tf_specific(callback: CallbackQuery, state: FSMContext):
    """Продолжить True/False аудирование"""
    data = await state.get_data()
    current_index = data.get("current_listening_tf", 0)
    await state.update_data(current_listening_tf=current_index + 1)
    
    await show_listening_true_false(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "next", LessonStates.LISTENING_TRUE_FALSE_COMPLETE)
async def listening_tf_complete_next(callback: CallbackQuery, state: FSMContext):
    """Завершение True/False, переход к множественному выбору"""
    await callback.message.edit_text("Отлично! Переходим к следующему типу аудирования...")
    
    await start_listening_choice(callback.message, state)
    await callback.answer()

async def start_listening_choice(message: Message, state: FSMContext):
    """Начало упражнений с множественным выбором для аудирования"""
    # Загружаем данные
    listening_data = await load_json_data("listening_choice_it.json")
    if not listening_data:
        await message.answer("Ошибка загрузки данных аудирования (выбор)")
        return
    
    # Сохраняем данные в состояние
    await state.update_data(
        listening_choice=listening_data,
        current_listening_choice=0,
        listening_choice_score=0
    )
    
    # Отправляем инструкцию
    await message.answer(MESSAGES["listening_choice_intro"])
    
    # Показываем первое упражнение
    await show_listening_choice(message, state)


async def show_listening_choice(message: Message, state: FSMContext):
    """Показать упражнение с множественным выбором для аудирования"""
    data = await state.get_data()
    exercises = data.get("listening_choice", [])
    current_index = data.get("current_listening_choice", 0)
    
    if current_index >= len(exercises):
        # Все упражнения выполнены
        score = data.get("listening_choice_score", 0)
        await message.answer(
            f"{MESSAGES['listening_choice_complete']}\n\n"
            f"Ваш результат: {score}/{len(exercises)} ✨",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        await state.set_state(LessonStates.LISTENING_CHOICE_COMPLETE)
        return
    
    current_exercise = exercises[current_index]
    
    # Генерируем аудио для фразы
    audio_filename = f"listening_choice_{current_index}_{current_exercise['phrase'][:20].replace(' ', '_')}"
    audio_path = await generate_audio(current_exercise['phrase'], audio_filename, 'en')
    
    # Отправляем аудио
    if audio_path and os.path.exists(audio_path):
        try:
            audio = FSInputFile(audio_path)
            await message.answer_audio(
                audio,
                caption="🎧 **Прослушайте фразу 2 раза**",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Ошибка отправки аудио: {e}")
            await message.answer("🎧 **Аудио недоступно**")
    
    # Отправляем вопрос и варианты ответов
    await message.answer(
        f"❓ **{current_exercise['question']} ({current_index + 1}/{len(exercises)})**",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_listening_choice_keyboard(current_exercise['options'], current_index))
    )
    
    await state.set_state(LessonStates.LISTENING_CHOICE)


@router.callback_query(F.data.startswith("listening_choice_"), LessonStates.LISTENING_CHOICE)
async def process_listening_choice_answer(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа множественного выбора для аудирования"""
    data = await state.get_data()
    exercises = data.get("listening_choice", [])
    current_index = data.get("current_listening_choice", 0)
    score = data.get("listening_choice_score", 0)
    
    if current_index >= len(exercises):
        return
    
    current_exercise = exercises[current_index]
    
    # Извлекаем выбранный ответ
    parts = callback.data.split("_")
    if len(parts) >= 5:
        selected_answer = "_".join(parts[4:])  # Берем все части после четвертого _
    else:
        selected_answer = ""
    
    correct_answer = current_exercise["correct_answer"]
    
    # Проверяем ответ
    if selected_answer == correct_answer:
        response_text = MESSAGES["correct_answer"]
        score += 1
        await state.update_data(listening_choice_score=score)
    else:
        response_text = f"{MESSAGES['wrong_answer']}{correct_answer}"
    
    # Отправляем результат
    await callback.message.edit_text(
        f"**Фраза:** {current_exercise['phrase']}\n"
        f"**Вопрос:** {current_exercise['question']}\n"
        f"**Правильный ответ:** {correct_answer}\n\n{response_text}",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_continue_keyboard())
    )
    
    await callback.answer()


@router.callback_query(F.data == "continue_exercise", LessonStates.LISTENING_CHOICE)
async def continue_listening_choice_specific(callback: CallbackQuery, state: FSMContext):
    """Продолжить множественный выбор аудирование"""
    data = await state.get_data()
    current_index = data.get("current_listening_choice", 0)
    await state.update_data(current_listening_choice=current_index + 1)
    
    await show_listening_choice(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "next", LessonStates.LISTENING_CHOICE_COMPLETE)
async def listening_choice_complete_next(callback: CallbackQuery, state: FSMContext):
    """Завершение множественного выбора, переход к повторению фраз"""
    await callback.message.edit_text("Отлично! Переходим к повторению фраз...")
    
    await start_listening_phrases(callback.message, state)
    await callback.answer()

async def start_listening_phrases(message: Message, state: FSMContext):
    """Начало упражнений с повторением фраз"""
    # Загружаем данные
    phrases_data = await load_json_data("listening_phrases_it.json")
    if not phrases_data:
        await message.answer("Ошибка загрузки данных фраз")
        return
    
    # Сохраняем данные в состояние
    await state.update_data(
        listening_phrases=phrases_data,
        current_listening_phrase=0,
        listening_phrases_score=0
    )
    
    # Отправляем инструкцию
    await message.answer(MESSAGES["listening_phrases_intro"])
    
    # Показываем первое упражнение
    await show_listening_phrase(message, state)


async def show_listening_phrase(message: Message, state: FSMContext):
    """Показать упражнение с повторением фразы"""
    data = await state.get_data()
    exercises = data.get("listening_phrases", [])
    current_index = data.get("current_listening_phrase", 0)
    
    if current_index >= len(exercises):
        # Все упражнения выполнены
        score = data.get("listening_phrases_score", 0)
        await message.answer(
            f"{MESSAGES['listening_phrases_complete']}\n\n"
            f"Ваш результат: {score}/{len(exercises)} ✨",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        await state.set_state(LessonStates.LISTENING_PHRASES_COMPLETE)
        return
    
    current_exercise = exercises[current_index]
    
    # Генерируем аудио для фразы
    audio_filename = f"listening_phrase_{current_index}_{current_exercise['phrase'][:20].replace(' ', '_')}"
    audio_path = await generate_audio(current_exercise['phrase'], audio_filename, 'en')
    
    # Отправляем аудио
    if audio_path and os.path.exists(audio_path):
        try:
            audio = FSInputFile(audio_path)
            await message.answer_audio(
                audio,
                caption="🎧 **Прослушайте фразу 2 раза**",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Ошибка отправки аудио: {e}")
            await message.answer("🎧 **Аудио недоступно**")
    
    # Показываем транскрипцию и инструкцию
    await message.answer(
        f"🔤 **Транскрипция ({current_index + 1}/{len(exercises)}):** {current_exercise.get('transcription', 'Недоступно')}\n\n"
        "Нажмите кнопку 'Записать фразу' и Повторите фразу за спикером, отправив голосове сообщение:",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_listening_phrases_keyboard())
    )
    
    await state.set_state(LessonStates.LISTENING_PHRASES)


@router.callback_query(F.data == "record_phrase", LessonStates.LISTENING_PHRASES)
async def request_phrase_recording(callback: CallbackQuery, state: FSMContext):
    """Запрос записи произношения фразы"""
    # await callback.message.answer(  # Изменить edit_text на answer
       # "🎤 Запишите голосовое сообщение с произношением фразы.\n\n"
       # "Для записи голосового сообщения нажмите на микрофон в Telegram и произнесите фразу.",
       # reply_markup=get_keyboard_with_menu(get_listening_phrases_keyboard())
    # )
    
    await state.set_state(LessonStates.LISTENING_PHRASES_RECORD)
    await callback.answer()


@router.message(F.voice, LessonStates.LISTENING_PHRASES_RECORD)
async def process_phrase_recording(message: Message, state: FSMContext):
    """Обработка записи произношения фразы"""
    data = await state.get_data()
    exercises = data.get("listening_phrases", [])
    current_index = data.get("current_listening_phrase", 0)
    
    if current_index >= len(exercises):
        return
    
    current_exercise = exercises[current_index]
    
    # Показываем, что обрабатываем
    processing_msg = await message.answer("🔄 Анализирую ваше произношение...")
    
    try:
        # Скачиваем голосовое сообщение
        voice_file = await message.bot.get_file(message.voice.file_id)
        voice_path = f"media/audio/phrase_{message.from_user.id}_{current_index}.ogg"
        
        await message.bot.download_file(voice_file.file_path, voice_path)
        
        # Простая проверка произношения (заглушка)
        is_correct = await simple_pronunciation_check(current_exercise['phrase'], voice_path)
        
        # Удаляем временный файл
        if os.path.exists(voice_path):
            os.remove(voice_path)
        
        # Удаляем сообщение об обработке
        await processing_msg.delete()
        
        # Отправляем результат
        if is_correct:
            await message.answer(
                MESSAGES["listening_correct"],
                reply_markup=get_keyboard_with_menu(get_phrase_result_keyboard())
            )
            # Увеличиваем счет
            score = data.get("listening_phrases_score", 0)
            await state.update_data(listening_phrases_score=score + 1)
        else:
            await message.answer(
                MESSAGES["listening_incorrect"],
                reply_markup=get_keyboard_with_menu(get_phrase_result_keyboard())
            )
    
    except Exception as e:
        await processing_msg.delete()
        await message.answer(
            "Произошла ошибка при обработке голосового сообщения.",
            reply_markup=get_keyboard_with_menu(get_phrase_result_keyboard())
        )
        print(f"Ошибка обработки голосового сообщения: {e}")


@router.callback_query(F.data == "skip_phrase", LessonStates.LISTENING_PHRASES)
@router.callback_query(F.data == "skip_phrase", LessonStates.LISTENING_PHRASES_RECORD)
@router.callback_query(F.data == "next_phrase")
async def next_listening_phrase(callback: CallbackQuery, state: FSMContext):
    """Переход к следующей фразе для повторения"""
    data = await state.get_data()
    current_index = data.get("current_listening_phrase", 0)
    
    # Увеличиваем индекс
    await state.update_data(current_listening_phrase=current_index + 1)
    
    # Обновляем прогресс пользователя
    user_progress.update_progress(
        callback.from_user.id, 
        current_item=current_index + 1
    )
    
    # Показываем следующую фразу
    await show_listening_phrase(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "retry_phrase")
async def retry_phrase(callback: CallbackQuery, state: FSMContext):
    """Повторить попытку произношения фразы"""
    await callback.message.edit_text(
        "🎤 Попробуйте ещё раз! Запишите голосовое сообщение с произношением фразы.",
        reply_markup=get_keyboard_with_menu(get_listening_phrases_keyboard())
    )
    
    await state.set_state(LessonStates.LISTENING_PHRASES_RECORD)
    await callback.answer()


@router.callback_query(F.data == "next", LessonStates.LISTENING_PHRASES_COMPLETE)
async def listening_phrases_complete_next(callback: CallbackQuery, state: FSMContext):
    """Завершение блока аудирования и переход к письму"""
    await callback.message.edit_text(
        "🎉 Блок аудирования завершен!\n\n"
        "Переходим к блоку письменной речи..."
    )
    
    # Обновляем прогресс
    user_progress.update_progress(
        callback.from_user.id,
        current_block="writing",
        current_item=0
    )
    
    # Запускаем блок письма
    await start_writing_sentences(callback.message, state)
    await callback.answer()

async def start_writing_sentences(message: Message, state: FSMContext):
    """Начало упражнений на составление предложений"""
    # Загружаем данные
    words_data = await load_json_data("words_written.json")
    if not words_data or "words" not in words_data:
        await message.answer("Ошибка загрузки данных для письма")
        return
    
    # Сохраняем данные в состояние
    await state.update_data(
        writing_words=words_data["words"],
        current_writing_word=0,
        writing_sentences_complete_count=0
    )
    
    # Отправляем инструкцию
    await message.answer(MESSAGES["writing_sentences_intro"])
    
    # Показываем первое упражнение
    await show_writing_sentence_task(message, state)

async def show_writing_sentence_task(message: Message, state: FSMContext):
    """Показать задание на составление предложения"""
    data = await state.get_data()
    words = data.get("writing_words", [])
    current_index = data.get("current_writing_word", 0)
    
    if current_index >= len(words):
        # Все слова пройдены
        completed = data.get("writing_sentences_complete_count", 0)
        await message.answer(
            f"{MESSAGES['writing_sentences_complete']}\n\n"
            f"Предложений составлено: {completed}/{len(words)} ✨",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        await state.set_state(LessonStates.WRITING_SENTENCES_COMPLETE)
        return
    
    current_word = words[current_index]
    
    # Отправляем задание
    await message.answer(
        f"✍️ **{MESSAGES['writing_word_prompt']} ({current_index + 1}/{len(words)})**\n\n"
        f"**{current_word}**",
        # "Напишите предложение с этим словом и отправьте его текстовым сообщением:",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_writing_skip_keyboard())
    )
    
    await state.set_state(LessonStates.WRITING_SENTENCES)

@router.message(F.text, LessonStates.WRITING_SENTENCES)
async def process_writing_sentence(message: Message, state: FSMContext):
    """Обработка составленного предложения"""
    user_sentence = message.text.strip()
    
    # Показываем, что проверяем
    checking_msg = await message.answer("🔄 Проверяю ваше предложение...")
    
    try:
        # Проверяем с помощью AI
        feedback = await check_writing_with_ai(user_sentence, "sentence")
        
        # Удаляем сообщение о проверке
        await checking_msg.delete()
        
        # Отправляем обратную связь
        await message.answer(
            f"**Ваше предложение:** {user_sentence}\n\n{feedback}",
            parse_mode="Markdown",
            reply_markup=get_keyboard_with_menu(get_continue_writing_keyboard())
        )
        
        # Увеличиваем счетчик выполненных
        data = await state.get_data()
        completed = data.get("writing_sentences_complete_count", 0)
        await state.update_data(writing_sentences_complete_count=completed + 1)
        
    except Exception as e:
        await checking_msg.delete()
        await message.answer(
            "Произошла ошибка при проверке предложения.",
            reply_markup=get_keyboard_with_menu(get_continue_writing_keyboard())
        )
        print(f"Ошибка проверки предложения: {e}")


@router.callback_query(F.data == "skip_writing", LessonStates.WRITING_SENTENCES)
@router.callback_query(F.data == "continue_writing", LessonStates.WRITING_SENTENCES)
async def continue_writing_sentences(callback: CallbackQuery, state: FSMContext):
    """Продолжить упражнения на составление предложений"""
    data = await state.get_data()
    current_index = data.get("current_writing_word", 0)
    await state.update_data(current_writing_word=current_index + 1)
    
    await show_writing_sentence_task(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "next", LessonStates.WRITING_SENTENCES_COMPLETE)
async def writing_sentences_complete_next(callback: CallbackQuery, state: FSMContext):
    """Завершение составления предложений, переход к переводу"""
    await callback.message.edit_text("Отлично! Теперь попробуем перевести предложения...")
    
    await start_writing_translation(callback.message, state)
    await callback.answer()


async def start_writing_translation(message: Message, state: FSMContext):
    """Начало упражнений на перевод предложений"""
    # Загружаем данные
    translation_data = await load_json_data("sentence_translation_it.json")
    if not translation_data or "phrases" not in translation_data:
        await message.answer("Ошибка загрузки данных для перевода")
        return
    
    # Сохраняем данные в состояние
    await state.update_data(
        translation_phrases=translation_data["phrases"],
        current_translation=0,
        translation_complete_count=0
    )
    
    # Отправляем инструкцию
    await message.answer(MESSAGES["writing_translation_intro"])
    
    # Показываем первое упражнение
    await show_writing_translation_task(message, state)


async def show_writing_translation_task(message: Message, state: FSMContext):
    """Показать задание на перевод предложения"""
    data = await state.get_data()
    phrases = data.get("translation_phrases", [])
    current_index = data.get("current_translation", 0)
    
    if current_index >= len(phrases):
        # Все фразы переведены
        completed = data.get("translation_complete_count", 0)
        await message.answer(
            f"{MESSAGES['writing_translation_complete']}\n\n"
            f"Предложений переведено: {completed}/{len(phrases)} ✨",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        await state.set_state(LessonStates.WRITING_TRANSLATION_COMPLETE)
        return
    
    current_phrase = phrases[current_index]
    
    # Отправляем задание
    await message.answer(
        f"🌐 **{MESSAGES['writing_translate_prompt']} ({current_index + 1}/{len(phrases)})**\n\n"
        f"**{current_phrase}**\n\n"
        "Напишите перевод на английский и отправьте текстовым сообщением:",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_writing_skip_keyboard())
    )
    
    await state.set_state(LessonStates.WRITING_TRANSLATION)


@router.message(F.text, LessonStates.WRITING_TRANSLATION)
async def process_writing_translation(message: Message, state: FSMContext):
    """Обработка перевода предложения"""
    user_translation = message.text.strip()
    
    # Показываем, что проверяем
    checking_msg = await message.answer("🔄 Проверяю ваш перевод...")
    
    try:
        # Проверяем с помощью AI
        feedback = await check_writing_with_ai(user_translation, "translation")
        
        # Удаляем сообщение о проверке
        await checking_msg.delete()
        
        # Отправляем обратную связь
        await message.answer(
            f"**Ваш перевод:** {user_translation}\n\n{feedback}",
            parse_mode="Markdown",
            reply_markup=get_keyboard_with_menu(get_continue_writing_keyboard())
        )
        
        # Увеличиваем счетчик выполненных
        data = await state.get_data()
        completed = data.get("translation_complete_count", 0)
        await state.update_data(translation_complete_count=completed + 1)
        
    except Exception as e:
        await checking_msg.delete()
        await message.answer(
            "Произошла ошибка при проверке перевода.",
            reply_markup=get_keyboard_with_menu(get_continue_writing_keyboard())
        )
        print(f"Ошибка проверки перевода: {e}")


@router.callback_query(F.data == "skip_writing", LessonStates.WRITING_TRANSLATION)
@router.callback_query(F.data == "continue_writing", LessonStates.WRITING_TRANSLATION)
async def continue_writing_translation(callback: CallbackQuery, state: FSMContext):
    """Продолжить упражнения на перевод"""
    data = await state.get_data()
    current_index = data.get("current_translation", 0)
    await state.update_data(current_translation=current_index + 1)
    
    await show_writing_translation_task(callback.message, state)
    await callback.answer()

# Обновить завершение блока письма:
@router.callback_query(F.data == "next", LessonStates.WRITING_TRANSLATION_COMPLETE)
async def writing_translation_complete_next(callback: CallbackQuery, state: FSMContext):
    """Завершение блока письменной речи и переход к говорению"""
    await callback.message.edit_text(
        "🎉 Блок письменной речи завершен!\n\n"
        "Переходим к финальному блоку - говорение..."
    )
    
    # Обновляем прогресс
    user_progress.update_progress(
        callback.from_user.id,
        current_block="speaking",
        current_item=0
    )
    
    # Запускаем блок говорения
    await start_speaking_block(callback.message, state)
    await callback.answer()


async def start_speaking_block(message: Message, state: FSMContext):
    """Начало блока говорения"""
    # Загружаем темы для обсуждения
    speaking_data = await load_json_data("speaking_it.json")
    if not speaking_data or "topics" not in speaking_data:
        await message.answer("Ошибка загрузки тем для говорения")
        return
    
    # Сохраняем данные в состояние
    await state.update_data(
        speaking_topics=speaking_data["topics"],
        current_speaking_topic=0,
        speaking_complete_count=0
    )
    
    # Отправляем инструкцию
    await message.answer(MESSAGES["speaking_intro"])
    
    # Показываем первую тему
    await show_speaking_topic(message, state)


async def show_speaking_topic(message: Message, state: FSMContext):
    """Показать тему для говорения"""
    data = await state.get_data()
    topics = data.get("speaking_topics", [])
    current_index = data.get("current_speaking_topic", 0)
    
    if current_index >= len(topics):
        # Все темы пройдены - курс завершен!
        completed = data.get("speaking_complete_count", 0)
        
        await message.answer(
            f"{MESSAGES['speaking_complete']}\n\n"
            f"Тем обсуждено: {completed}/{len(topics)} 🎯\n\n"
            f"{MESSAGES['speaking_final']}",
            reply_markup=get_keyboard_with_menu(get_final_keyboard())
        )
        await state.set_state(LessonStates.SPEAKING_COMPLETE)
        return
    
    current_topic = topics[current_index]
    
    # Отправляем тему для обсуждения
    await message.answer(
        f"🎙️ **{MESSAGES['speaking_situation']} ({current_index + 1}/{len(topics)})**\n\n"
        f"*{current_topic}*\n\n",
        # f"{MESSAGES['speaking_instruction']}",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_speaking_keyboard())
    )
    
    await state.set_state(LessonStates.SPEAKING)


@router.callback_query(F.data == "record_speaking", LessonStates.SPEAKING)
async def request_speaking_recording(callback: CallbackQuery, state: FSMContext):
    """Запрос записи высказывания"""
    await callback.message.edit_text(
        "🎤 **Запишите голосовое сообщение с вашими мыслями по теме.**\n\n"
        "💡 Говорите свободно на английском языке. Можете рассказать о своем опыте, "
        "привести примеры из работы или поделиться мнением.\n\n"
        "Для записи нажмите на микрофон в Telegram и начните говорить.",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_speaking_keyboard())
    )
    
    await state.set_state(LessonStates.SPEAKING_RECORD)
    await callback.answer()


@router.message(F.voice, LessonStates.SPEAKING_RECORD)
async def process_speaking_recording(message: Message, state: FSMContext):
    """Обработка записи говорения"""
    data = await state.get_data()
    topics = data.get("speaking_topics", [])
    current_index = data.get("current_speaking_topic", 0)
    
    if current_index >= len(topics):
        return
    
    current_topic = topics[current_index]
    
    # Показываем, что анализируем
    analyzing_msg = await message.answer(MESSAGES["speaking_analyzing"])
    
    try:
        # Скачиваем голосовое сообщение
        voice_file = await message.bot.get_file(message.voice.file_id)
        voice_path = f"media/audio/speaking_{message.from_user.id}_{current_index}.ogg"
        
        await message.bot.download_file(voice_file.file_path, voice_path)
        
        # Простая транскрипция (в реальности - Whisper API)
        transcribed_text = await transcribe_audio_simple(voice_path)
        
        # Анализируем с помощью AI
        analysis = await analyze_speaking_with_ai(transcribed_text, current_topic)
        
        # Удаляем временный файл
        if os.path.exists(voice_path):
            os.remove(voice_path)
        
        # Удаляем сообщение об анализе
        await analyzing_msg.delete()
        
        # Отправляем анализ
        await message.answer(
            f"**Ваша тема:** {current_topic}\n\n{analysis}",
            parse_mode="Markdown",
            reply_markup=get_keyboard_with_menu(get_speaking_result_keyboard())
        )
        
        # Увеличиваем счетчик выполненных
        completed = data.get("speaking_complete_count", 0)
        await state.update_data(speaking_complete_count=completed + 1)
        
    except Exception as e:
        await analyzing_msg.delete()
        await message.answer(
            "Произошла ошибка при анализе вашего высказывания.",
            reply_markup=get_keyboard_with_menu(get_speaking_result_keyboard())
        )
        print(f"Ошибка анализа речи: {e}")


@router.callback_query(F.data == "skip_speaking", LessonStates.SPEAKING)
@router.callback_query(F.data == "skip_speaking", LessonStates.SPEAKING_RECORD)
@router.callback_query(F.data == "next_speaking")
async def next_speaking_topic(callback: CallbackQuery, state: FSMContext):
    """Переход к следующей теме для говорения"""
    data = await state.get_data()
    current_index = data.get("current_speaking_topic", 0)
    
    # Увеличиваем индекс
    await state.update_data(current_speaking_topic=current_index + 1)
    
    # Обновляем прогресс пользователя
    user_progress.update_progress(
        callback.from_user.id, 
        current_item=current_index + 1
    )
    
    # Показываем следующую тему
    await show_speaking_topic(callback.message, state)
    await callback.answer()


@router.callback_query(F.data == "retry_speaking")
async def retry_speaking(callback: CallbackQuery, state: FSMContext):
    """Повторить запись по той же теме"""
    await callback.message.edit_text(
        "🎤 Попробуйте ещё раз! Запишите голосовое сообщение с вашими мыслями по теме.",
        reply_markup=get_keyboard_with_menu(get_speaking_keyboard())
    )
    
    await state.set_state(LessonStates.SPEAKING_RECORD)
    await callback.answer()
# Финальные обработчики завершения курса
@router.callback_query(F.data == "main_menu", LessonStates.SPEAKING_COMPLETE)
@router.callback_query(F.data == "restart_lesson", LessonStates.SPEAKING_COMPLETE)
async def course_complete_actions(callback: CallbackQuery, state: FSMContext):
    """Действия после завершения полного курса"""
    if callback.data == "restart_lesson":
        # Сбрасываем прогресс для нового прохождения
        await state.clear()
        user_progress.reset_progress(callback.from_user.id)
        
        await callback.message.edit_text(
            "🔄 Курс перезапущен! Готовы пройти его заново?\n\n"
            "Это отличная практика для закрепления знаний!",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        # Возврат в главное меню
        await callback.message.edit_text(
            "🏠 **Добро пожаловать обратно в главное меню!**\n\n"
            "Вы можете повторить любой блок или пройти весь курс заново.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )
    
    await callback.answer()


# Обработчик завершения всего курса
@router.callback_query(F.data == "next", LessonStates.SPEAKING_COMPLETE)
async def final_course_completion(callback: CallbackQuery, state: FSMContext):
    """Финальное завершение курса"""
    await callback.message.edit_text(
        "🎓 **ПОЗДРАВЛЯЕМ С ЗАВЕРШЕНИЕМ КУРСА!** 🎓\n\n"
        "Вы успешно прошли все 8 блоков английского языка для программистов:\n"
        "✅ Изучение терминов\n"
        "✅ Произношение\n"
        "✅ Лексические упражнения\n"
        "✅ Грамматика с AI-учителем\n"
        "✅ Практические упражнения\n"
        "✅ Аудирование\n"
        "✅ Письменная речь\n"
        "✅ Говорение\n\n"
        "🚀 Теперь вы готовы к общению на английском в IT среде!",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_final_keyboard())
    )
    
    await state.set_state(LessonStates.LESSON_COMPLETE)
    await callback.answer()

@router.callback_query(F.data == "continue_exercise")
async def continue_exercise_handler(callback: CallbackQuery, state: FSMContext):
    """Универсальный обработчик продолжения упражнений - fallback"""
    current_state = await state.get_state()
         
    # Логируем для отладки
    print(f"Универсальный обработчик: состояние {current_state}")
    
    # ДОБАВЛЯЕМ ОБРАБОТКУ ЛЕКСИЧЕСКИХ СОСТОЯНИЙ
    if current_state == LessonStates.LEXICAL_EN_TO_RU:
        print("[DEBUG] Обрабатываем LEXICAL_EN_TO_RU в универсальном обработчике")
        # Переходим к следующему вопросу английский -> русский
        data = await state.get_data()
        current_index = data.get("current_lexical_en", 0)
        new_index = current_index + 1
        await state.update_data(current_lexical_en=new_index)
        
        print(f"[DEBUG] Увеличили индекс с {current_index} до {new_index}")
        
        try:
            await show_lexical_en_question(callback.message, state)
            print("[DEBUG] show_lexical_en_question успешно вызвана")
        except Exception as e:
            print(f"[ERROR] Ошибка в show_lexical_en_question: {e}")
            await callback.message.edit_text(
                "Произошла ошибка при загрузке следующего вопроса.",
                reply_markup=get_keyboard_with_menu(get_main_menu_keyboard())
            )
        
        await callback.answer()
        return
        
    elif current_state == LessonStates.LEXICAL_RU_TO_EN:
        print("[DEBUG] Обрабатываем LEXICAL_RU_TO_EN в универсальном обработчике")
        # Переходим к следующему вопросу русский -> английский
        data = await state.get_data()
        current_index = data.get("current_lexical_ru", 0)
        new_index = current_index + 1
        await state.update_data(current_lexical_ru=new_index)
        
        print(f"[DEBUG] Увеличили индекс с {current_index} до {new_index}")
        
        try:
            await show_lexical_ru_question(callback.message, state)
            print("[DEBUG] show_lexical_ru_question успешно вызвана")
        except Exception as e:
            print(f"[ERROR] Ошибка в show_lexical_ru_question: {e}")
            await callback.message.edit_text(
                "Произошла ошибка при загрузке следующего вопроса.",
                reply_markup=get_keyboard_with_menu(get_main_menu_keyboard())
            )
        
        await callback.answer()
        return
         
    # Если дошли до сюда, значит не сработал специфичный обработчик
    await callback.message.edit_text(
        "⚠️ Произошла ошибка при продолжении упражнения.\n\n"
        "Попробуйте использовать меню для навигации.",
        reply_markup=get_keyboard_with_menu(get_main_menu_keyboard())
    )
    await callback.answer()


# Обработчики для специфичных типов продолжения лексических упражнений
@router.callback_query(F.data == "continue_lexical")
async def continue_lexical_exercise_fallback(callback: CallbackQuery, state: FSMContext):
    """Fallback обработчик для лексических упражнений"""
    current_state = await state.get_state()
    
    print(f"[DEBUG] FALLBACK сработал для состояния: {current_state}")
    
    if current_state == LessonStates.LEXICAL_EN_TO_RU:
        print("[DEBUG] Обрабатываем EN->RU в fallback")
        
        # Переходим к следующему вопросу английский -> русский
        data = await state.get_data()
        current_index = data.get("current_lexical_en", 0)
        await state.update_data(current_lexical_en=current_index + 1)
        
        await show_lexical_en_question(callback.message, state)
        
    elif current_state == LessonStates.LEXICAL_RU_TO_EN:
        # Переходим к следующему вопросу русский -> английский
        data = await state.get_data()
        current_index = data.get("current_lexical_ru", 0)
        await state.update_data(current_lexical_ru=current_index + 1)
        
        await show_lexical_ru_question(callback.message, state)
    
    else:
        # Если состояние не подходит
        await callback.message.edit_text(
            "⚠️ Неожиданное состояние в лексических упражнениях.\n\n"
            "Воспользуйтесь меню для навигации.",
            reply_markup=get_keyboard_with_menu(get_main_menu_keyboard())
        )
    
    await callback.answer()


# Дополнительные обработчики для улучшения пользовательского опыта
@router.callback_query(F.data.startswith("lexical_"))
async def handle_lexical_fallback(callback: CallbackQuery, state: FSMContext):
    """Fallback обработчик для лексических callback'ов"""
    current_state = await state.get_state()
    
    # Если callback пришел, но состояние неподходящее
    if current_state not in [LessonStates.LEXICAL_EN_TO_RU, LessonStates.LEXICAL_RU_TO_EN]:
        await callback.message.edit_text(
            "⚠️ Это упражнение уже завершено или недоступно.\n\n"
            "Воспользуйтесь меню для навигации по урокам.",
            reply_markup=get_keyboard_with_menu(get_main_menu_keyboard())
        )
        await callback.answer()
        return
    
    # Логируем для отладки
    print(f"Необработанный lexical callback: {callback.data} в состоянии {current_state}")
    await callback.answer("Нажмите кнопку еще раз")


@router.callback_query(F.data.startswith("mchoice_"))
async def handle_mchoice_fallback(callback: CallbackQuery, state: FSMContext):
    """Fallback обработчик для mchoice callback'ов"""
    current_state = await state.get_state()
    
    # Если callback пришел, но состояние неподходящее
    if current_state not in [LessonStates.MCHOICE_EXERCISE, LessonStates.LISTENING_CHOICE]:
        await callback.message.edit_text(
            "⚠️ Это упражнение уже завершено или недоступно.\n\n"
            "Воспользуйтесь меню для навигации по урокам.",
            reply_markup=get_keyboard_with_menu(get_main_menu_keyboard())
        )
        await callback.answer()
        return
    
    # Логируем для отладки
    print(f"Необработанный mchoice callback: {callback.data} в состоянии {current_state}")
    await callback.answer("Нажмите кнопку еще раз")


@router.callback_query(F.data.startswith("listening_"))
async def handle_listening_fallback(callback: CallbackQuery, state: FSMContext):
    """Fallback обработчик для listening callback'ов"""
    current_state = await state.get_state()
    
    # Если callback пришел, но состояние неподходящее
    if current_state not in [LessonStates.LISTENING_TRUE_FALSE, LessonStates.LISTENING_CHOICE]:
        await callback.message.edit_text(
            "⚠️ Это упражнение уже завершено или недоступно.\n\n"
            "Воспользуйтесь меню для навигации по урокам.",
            reply_markup=get_keyboard_with_menu(get_main_menu_keyboard())
        )
        await callback.answer()
        return
    
    # Логируем для отладки
    print(f"Необработанный listening callback: {callback.data} в состоянии {current_state}")
    await callback.answer("Нажмите кнопку еще раз")


# Fallback обработчик для всех неопознанных callback'ов
@router.callback_query()
async def handle_unknown_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик для всех неопознанных callback'ов"""
    print(f"Неопознанный callback: {callback.data}")
    
    # Просто подтверждаем callback без действий
    await callback.answer("Команда не распознана. Используйте доступные кнопки.")


# Fallback обработчик для текстовых сообщений в неподходящих состояниях
@router.message(F.text)
async def handle_unexpected_text(message: Message, state: FSMContext):
    current_state = await state.get_state()

    if current_state not in [
        LessonStates.VERB_EXERCISE,
        LessonStates.GRAMMAR_QA,
        LessonStates.NEGATIVE_EXERCISE,
        LessonStates.QUESTION_EXERCISE,
        LessonStates.MISSING_WORD_EXERCISE # ← Добавлено
    ]:
        await message.answer(
            "🤔 Сейчас не время для текстового ввода.\n\n"
            "Используйте кнопки для навигации или вернитесь в главное меню.",
            reply_markup=get_keyboard_with_menu(get_main_menu_keyboard())
        )

# Fallback обработчик для голосовых сообщений в неподходящих состояниях
@router.message(F.voice)
async def handle_unexpected_voice(message: Message, state: FSMContext):
    """Обработчик для неожиданных голосовых сообщений"""
    current_state = await state.get_state()
    
    # Если голосовое сообщение пришло в состоянии, где его не ждут
    if current_state not in [LessonStates.PRONUNCIATION_RECORD, LessonStates.LISTENING_PHRASES_RECORD]:
        await message.answer(
            "🎤 Сейчас не время для голосовых сообщений.\n\n"
            "Дождитесь соответствующего упражнения или вернитесь в главное меню.",
            reply_markup=get_keyboard_with_menu(get_main_menu_keyboard())
        )


# Обработчик для всех остальных типов сообщений
@router.message()
async def handle_unexpected_message(message: Message, state: FSMContext):
    """Обработчик для всех остальных типов сообщений"""
    current_state = await state.get_state()
    
    await message.answer(
        f"🤷‍♂️ Не понимаю этот тип сообщения.\n\n"
        f"Текущее состояние: {current_state or 'не определено'}\n\n"
        "Используйте доступные кнопки для навигации.",
        reply_markup=get_keyboard_with_menu(get_main_menu_keyboard())
    )

