import sys
import os
import traceback
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from bot.statistics import UserStatistics

from bot.keyboards import (get_next_keyboard, get_pronunciation_keyboard, get_pronunciation_result_keyboard,
                         get_choice_keyboard, get_continue_keyboard, get_grammar_keyboard, get_grammar_qa_keyboard,
                         get_mchoice_keyboard, get_text_exercise_keyboard, get_true_false_keyboard,
                         get_listening_choice_keyboard, get_listening_phrases_keyboard, get_phrase_result_keyboard,
                         get_main_menu_keyboard, get_continue_writing_keyboard, get_writing_skip_keyboard,
                         get_speaking_keyboard, get_speaking_result_keyboard, get_final_keyboard, get_word_build_keyboard)
from bot.states import LessonStates
from bot.utils import (load_json_data, UserProgress, generate_audio, simple_pronunciation_check,
                       get_teacher_response, check_writing_with_ai, analyze_speaking_with_ai,
                       transcribe_audio_simple, analyze_phonemes_with_gpt)

from config import MESSAGES, IMAGES_PATH, CURRENT_LESSON_ID
from config import OPENAI_API_KEY
from bot.utils import convert_ogg_to_wav
from aiogram.exceptions import TelegramBadRequest
from datetime import datetime # Добавьте, если нет
from typing import Callable, Awaitable, Dict, List, Tuple, Any
import shutil
import logging
import os
from bot.utils import UserProgress

# Создаем папку для логов, если её нет
os.makedirs("logs", exist_ok=True)

# Настройка логгера
logging.basicConfig(
    filename="logs/user_interactions.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | [%(filename)s] %(message)s",
    encoding="utf-8",
    force=True
)

# Добавьте эту функцию
def log_user_result(user_id, result_type, result_data):
    print(f"Логгирую: {user_id}")  # для отладки
    logging.info(f"USER_ID: {user_id} | RESULT_TYPE: {result_type} | DATA: {result_data}")

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
        "Выбери действие:",
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "restart_lesson")
async def handle_restart_lesson(callback: CallbackQuery, state: FSMContext, user_progress: UserProgress):
    """Перезапуск урока из любого состояния"""
    # Сбрасываем состояние и прогресс
    await state.clear()
    user_progress.reset_progress(callback.from_user.id)

    try:
        await callback.message.edit_text(
            "🔄 Урок перезапущен! Начинаем заново.\n\nВыбери действие:",
            reply_markup=get_main_menu_keyboard()
        )
    except Exception:
        # Если не удалось изменить сообщение, отправляем новое
        await callback.message.answer(
            "🔄 Урок перезапущен! Начинаем заново.\n\nВыбери действие:",
            reply_markup=get_main_menu_keyboard()
        )

    await callback.answer()


async def start_terms_block(
        user_id: int,
        message: Message,
        state: FSMContext,
        user_statistics: UserStatistics, user_progress: UserProgress
):
    print(f"DEBUG (start_terms_block): Начало выполнения для пользователя {user_id}")

    terms_data = {}  # Инициализируем пустым словарем на случай ошибки загрузки
    try:
        terms_data = await load_json_data("1_terms.json")
        # Дополнительная отладка: выводим тип данных и начало содержимого
        print(
            f"DEBUG (start_terms_block): Данные терминов загружены. Тип: {type(terms_data)}, Содержимое (первые 100 символов): {str(terms_data)[:100]}")
    except Exception as e:
        # Если при загрузке произошла любая ошибка, мы это поймаем
        print(f"ERROR (start_terms_block): Критическая ошибка при загрузке 1_terms.json: {e}")
        await message.answer(
            "Произошла критическая ошибка при загрузке данных урока. Пожалуйста, попробуйте позже или обратитесь к администратору.")
        return  # Останавливаем выполнение функции

    # Проверяем, что terms_data не пуст, является словарем и содержит ключ "terms", который является списком
    if not terms_data or not isinstance(terms_data, dict) or "terms" not in terms_data or not isinstance(
            terms_data["terms"], list):
        await message.answer(
            "Ошибка: данные терминов отсутствуют или имеют неверный формат в файле 1_terms.json. Обратитесь к администратору.")
        print(
            "ERROR (start_terms_block): terms_data пуст, не является словарем, или отсутствует ключ 'terms' (или 'terms' не список).")
        return  # Останавливаем выполнение функции

    # Проверяем, что список терминов не пуст
    if not terms_data["terms"]:
        await message.answer("Ошибка: Список терминов в файле 1_terms.json пуст. Добавьте термины.")
        print("ERROR (start_terms_block): Список терминов в файле 1_terms.json пуст.")
        return  # Останавливаем выполнение функции

    await state.update_data(terms=terms_data["terms"], current_term=0)
    print(f"DEBUG (start_terms_block): Состояние обновлено: current_term=0, всего терминов={len(terms_data['terms'])}")

    # Это сообщение, которое должно идти вторым, но сейчас не появляется
    await message.answer(MESSAGES["terms_intro"])

    await show_current_term(user_id, message, state, user_statistics, user_progress)




async def show_current_term(
    user_id: int,
    message: Message,
    state: FSMContext,
    user_statistics: UserStatistics, user_progress: UserProgress # Убедитесь, что здесь есть user_statistics
):
    print(f"DEBUG (show_current_term): Начало выполнения для пользователя {user_id}")
    data = await state.get_data()
    terms = data.get("terms", [])
    current_index = data.get("current_term", 0)
    print(f"DEBUG (show_current_term): Из состояния: терминов={len(terms)}, текущий индекс={current_index}")

    if current_index >= len(terms):
        print(f"DEBUG (show_current_term): Условие завершения блока выполнено: current_index ({current_index}) >= len(terms) ({len(terms)}).")
        # Все термины изучены
        await message.answer(
            MESSAGES["terms_complete"],
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        await state.set_state(LessonStates.TERMS_COMPLETE)
        # ИЗМЕНЕНИЕ: Передача lesson_id в update_block_status
        user_statistics.update_block_status(user_id, "terms", completed=True, lesson_id=CURRENT_LESSON_ID)
        print(f"DEBUG: Статус блока терминов обновлен как завершенный для пользователя {user_id} (из next_term).")

        return # Выход из функции

    current_term = terms[current_index]
    print(f"DEBUG (show_current_term): Отображаю термин: '{current_term['english']}'")

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

    try:
        if audio_path and os.path.exists(audio_path):
            audio = FSInputFile(audio_path)
            await message.answer_voice(
                voice=audio, # Исправлено: voice=audio вместо voice=FSInputFile(audio_path)
                caption="🔊 **Произношение**",
                parse_mode="Markdown"
            )
            print(f"DEBUG (show_current_term): Аудио файл '{audio_path}' отправлен.")
        else:
            print(f"DEBUG (show_current_term): Аудио файл не найден или не сгенерирован: '{audio_path}'")
            await message.answer("🔊 **Произношение:** (аудио недоступно)")
    except Exception as e:
        print(f"CRITICAL ERROR (show_current_term): Ошибка при отправке аудио: {e}")
        await message.answer("🔊 **Произношение:** (аудио недоступно - критическая ошибка!)")

    # Окончательный блок: Кнопка "Дальше" и установка состояния
    try:
        await message.answer(
            "Нажмите кнопку «Дальше» для продолжения",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        print(f"DEBUG (show_current_term): Сообщение с кнопкой 'Дальше' отправлено.")

        user_progress.update_progress(user_id=user_id, current_block="terms", current_item=current_index + 1)
        print(f"DEBUG (show_current_term): Прогресс пользователя {user_id} обновлен.")

        await state.set_state(LessonStates.TERMS_SHOW_AUDIO)
        print(
            f"DEBUG (show_current_term): Состояние установлено в LessonStates.TERMS_SHOW_AUDIO для пользователя {user_id}")

    except Exception as e:
        print(
            f"CRITICAL ERROR (show_current_term): Ошибка при отправке финального сообщения/кнопки или установке состояния: {e}")
        await message.answer("⚠️ Критическая ошибка! Пожалуйста, перезапустите урок.")

@router.callback_query(F.data == "next", LessonStates.TERMS_SHOW_AUDIO)
async def next_term(

    callback: CallbackQuery,
    state: FSMContext,
    user_progress: UserProgress,
    user_statistics: UserStatistics # Убедитесь, что этот аргумент присутствует
):
    print(f"--- DEBUG: Функция next_term ВЫЗВАНА! Пользователь: {callback.from_user.id} ---")
    user_id = callback.from_user.id
    print(f"DEBUG (next_term): Обработка 'next' для пользователя {user_id} в состоянии TERMS_SHOW_AUDIO.")

    data = await state.get_data()
    terms = data.get("terms", [])
    current_index = data.get("current_term", 0)

    # Увеличиваем индекс для следующего термина
    new_index = current_index + 1
    print(f"DEBUG (next_term): Старый индекс: {current_index}, Новый индекс: {new_index}.")

    if new_index >= len(terms):
        print(f"DEBUG (next_term): Все термины пройдены для пользователя {user_id}. Новый индекс: {new_index}, Всего терминов: {len(terms)}.")

        # 1. Отправляем сообщение о завершении блока терминов и переходе
        await callback.message.edit_text(
            "🎉 Блок терминов завершен!\n\n"
            "Переходим к блоку произношения..."
        )

        # 2. Обновляем статус блока терминов как завершенный в user_statistics
        # ИЗМЕНЕНИЕ: Передача lesson_id в update_block_status
        user_statistics.update_block_status(user_id, "terms", completed=True, lesson_id=CURRENT_LESSON_ID)

        print(f"DEBUG: Статус блока терминов обновлен как завершенный для пользователя {user_id} (из next_term).")

        # 3. Обновляем прогресс пользователя на следующий блок (произношение)
        user_progress.update_progress(
            user_id,
            current_block="pronunciation",
            current_item=0
        )
        print(f"DEBUG: Прогресс пользователя {user_id} обновлен для блока произношения (из next_term).")

        # 4. Устанавливаем состояние бота на начало блока произношения
        await state.set_state(LessonStates.PRONUNCIATION_LISTEN)
        print(f"DEBUG: Состояние бота установлено в LessonStates.PRONUNCIATION_LISTEN (из next_term).")

        # 5. Запускаем блок произношения
        await start_pronunciation_block(user_id, callback.message, state, user_statistics, user_progress)
        print(f"DEBUG: start_pronunciation_block вызван (из next_term).")

    else:
        # ОБНОВЛЯЕМ СОСТОЯНИЕ с новым индексом
        await state.update_data(current_term=new_index)
        print(f"DEBUG (next_term): Состояние обновлено: current_term={new_index}.")
        print(f"DEBUG (next_term): Отображаю следующий термин для пользователя {user_id}. Индекс: {new_index}.")
        # Вызываем show_current_term с обновленным состоянием
        await show_current_term(user_id, callback.message, state, user_statistics, user_progress)

    # Всегда отвечаем на callbackQuery, чтобы кнопка не висела "нажатой"
    await callback.answer()


#    @router.callback_query(F.data == "next", LessonStates.TERMS_COMPLETE)
#    async def terms_complete_next(
#        callback: CallbackQuery,
#        state: FSMContext,
#        user_statistics: UserStatistics, # <--- ДОБАВЬТЕ ЭТОТ АРГУМЕНТ
#        user_progress: UserProgress      # <--- ДОБАВЬТЕ ЭТОТ АРГУМЕНТ
#    ):
#        """Завершение блока терминов и переход к произношению"""
#        await callback.message.edit_text(
#            "🎉 Блок терминов завершен!\n\n"
#            "Переходим к блоку произношения..."
#        )
#
#        user_progress.update_progress(
#            callback.from_user.id,
#            current_block="pronunciation",
#            current_item=0
#        ) # Теперь user_progress доступен
#        print(f"DEBUG: Прогресс пользователя {callback.from_user.id} обновлен для блока произношения.")
#
#        # user_statistics: UserStatistics = router.parent_router["user_statistics"] # <--- УДАЛИТЕ ЭТУ СТРОКУ!
#        # Теперь user_statistics доступен через аргумент
#        if user_statistics.is_terms_block_completed(callback.from_user.id):
#            user_statistics.increment_lessons_completed_count(callback.from_user.id)
#            print(f"DEBUG: Урок завершен для пользователя {callback.from_user.id}. Всего уроков: {user_statistics.get_user_stats(callback.from_user.id)['lessons_completed_count']}")
#        else:
#             print(f"DEBUG: Блок терминов не был помечен как завершенный для пользователя {callback.from_user.id}.")
#
#        # Запускаем блок произношения
#        # Проверьте сигнатуру start_pronunciation_block: если он нуждается в user_statistics/user_progress,
#        # то их нужно будет передать здесь:
#        # await start_pronunciation_block(callback.message, state, user_statistics, user_progress)
#         # Если не нужны, то так
#        await callback.answer()
#        await start_pronunciation_block(callback.message, state, user_statistics, user_progress)



@router.message(F.voice, LessonStates.PRONUNCIATION_RECORD)
async def process_pronunciation_recording(message: Message, state: FSMContext, user_progress: UserProgress,
    user_statistics: UserStatistics):
    data = await state.get_data()
    text_to_check = data.get("current_pronunciation_text")

    if not text_to_check:
        await message.answer("Извини, не могу найти текущее слово для проверки.")
        return

    async def handle_result(overall_accuracy: float, verdict: str, analysis_text: str,
                            expected_phonemes: str, user_phonemes: str, word_results: List[Dict]):
        full_response = f"{verdict}" # Начинаем только с вердикта

        # Если точность не "Отлично" и не "Неразборчиво" (т.е. "Хорошо, но можно лучше!")
        # И есть реальный анализ для отображения
        if overall_accuracy < 85.0 and analysis_text: # Условие для показа точности и обычного анализа
             full_response += f"\n\n🎯 <b>Точность:</b> {overall_accuracy:.1f}%\n{analysis_text}"

        gpt_analysis_output = None
        # Вызов GPT-анализа только если verdict не "Отлично" и не "Неразборчиво",
        # и если есть word_results для анализа
        # (это означает, что overall_accuracy находится между порогами)
        if word_results and analysis_text: # Проверяем, что есть ошибки, для которых делался анализ
            gpt_analysis_output = await analyze_phonemes_with_gpt(
                original_text=text_to_check,
                expected_phonemes=expected_phonemes,
                user_phonemes=user_phonemes,
                overall_accuracy=overall_accuracy,
                word_errors_analysis=word_results
            )

        if gpt_analysis_output:
            full_response += f"\n\n---\n🤖 <b>Советы от AI:</b>\n{gpt_analysis_output}"

        # Сохраняем детальные данные произношения
        user_statistics.save_pronunciation_data(
            user_id=message.from_user.id,
            word=text_to_check,
            user_phonemes=user_phonemes,
            expected_phonemes=expected_phonemes,
            accuracy=overall_accuracy
        )

        # Логируем результат
        log_user_result(
            user_id=str(message.from_user.id),
            result_type="pronunciation_check",
            result_data={
                "text": text_to_check,
                "accuracy": overall_accuracy,
                "verdict": verdict,
                "analysis": analysis_text,
                "gpt_analysis": gpt_analysis_output,
                "user_phonemes": user_phonemes
            }
        )

        # ИЗМЕНЕНИЕ: Добавляем каждую попытку произношения в статистику (lesson_id по умолчанию)
        user_statistics.add_pronunciation_attempt(
            user_id=message.from_user.id,
            word=text_to_check,
            score=overall_accuracy
        )

        await message.answer(
            full_response,
            reply_markup=get_keyboard_with_menu(get_pronunciation_result_keyboard()),
            parse_mode='HTML'
        )
        await state.set_state(LessonStates.PRONUNCIATION_LISTEN)

    await analyze_pronunciation(
        message=message,
        text_to_check=text_to_check,
        callback=handle_result,
        state=state
    )

async def analyze_pronunciation(
    message: Message,
    text_to_check: str,
    callback: Callable[[float, str, str, str, str, List[Dict]], Awaitable[None]],
    state: FSMContext
):
    """Общая функция для анализа произношения (может использоваться в разных блоках)"""
    processing_msg = await message.answer("🔄 Анализирую твоё произношение...")

    # Настройка порогов
    base_lower_threshold = 68.0
    base_upper_threshold = 84.0
    sensitivity_factor = -1.0
    num_words = len(text_to_check.split())

    adjusted_lower_threshold = base_lower_threshold
    adjusted_upper_threshold = base_upper_threshold

    if num_words <= 2:
        adjusted_lower_threshold += 3.0 * sensitivity_factor
    elif num_words >= 5:
        adjusted_lower_threshold += -3.0 * sensitivity_factor

    adjusted_lower_threshold = max(0.0, min(100.0, adjusted_lower_threshold))
    adjusted_upper_threshold = max(0.0, min(100.0, adjusted_upper_threshold))

    timestamp_str = datetime.now().strftime("%Y%m%d%H%M%S%f")
    voice_path_ogg = os.path.join("media", "audio", f"voice_{message.from_user.id}_{timestamp_str}.ogg")
    voice_path_wav = voice_path_ogg.replace(".ogg", ".wav")

    try:
        voice_file = await message.bot.get_file(message.voice.file_id)
        os.makedirs(os.path.dirname(voice_path_ogg), exist_ok=True)
        await message.bot.download_file(voice_file.file_path, voice_path_ogg)

        if not await convert_ogg_to_wav(voice_path_ogg, voice_path_wav):
            if processing_msg:
                try:
                    await processing_msg.delete()
                except TelegramBadRequest as e:
                    print(f"Ошибка удаления сообщения при неудачной конвертации: {e}")
            await message.answer("⚠️ Не удалось обработать аудио. Пожалуйста, попробуйте еще раз.")
            return

        # ⬇️ Основной анализ
        overall_accuracy, verdict, analysis_text, expected_phonemes, user_phonemes, word_results = await simple_pronunciation_check(
            text_to_check,
            voice_path_wav,
            adjusted_lower_threshold,
            adjusted_upper_threshold
        )

        # ⬇️ Вызываем callback для UI
        await callback(overall_accuracy, verdict, analysis_text, expected_phonemes, user_phonemes, word_results)

        # ⬇️ Архивация голоса
        save_dir = os.path.join("media", "archived_voices")
        os.makedirs(save_dir, exist_ok=True)
        unique_name = f"{message.from_user.id}_acc_{round(overall_accuracy)}_%_{_sanitize_filename(text_to_check)[:20]}.ogg" # ИЗМЕНЕНИЕ: Используем _sanitize_filename
        shutil.copyfile(voice_path_ogg, os.path.join(save_dir, unique_name))

    except Exception as e:
        await message.answer("Произошла ошибка при обработке вашего голосового сообщения.")
        print(f"Ошибка: {e}")

    finally:
        if voice_path_ogg and os.path.exists(voice_path_ogg):
            os.remove(voice_path_ogg)
        if voice_path_wav and os.path.exists(voice_path_wav):
            os.remove(voice_path_wav)

        if processing_msg:
            try:
                await processing_msg.delete()
            except TelegramBadRequest as e:
                print(f"Ошибка удаления сообщения об анализе: {e}")
            except Exception as e:
                print(f"Ошибка удаления сообщения об анализе (непредвиденная): {e}")


# --- start_pronunciation_block - ВЕРНУЛ К ИСХОДНОМУ СОСТОЯНИЮ ---
# ИЗМЕНЕНИЕ: Добавляем user_statistics и user_progress в сигнатуру
async def start_pronunciation_block(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Начало блока произношения"""
    # Загружаем данные для произношения
    pronunciation_data = await load_json_data("2_pronouncing_words.json")
    print(f"DEBUG: pronunciation_data loaded: {pronunciation_data}")
    if not pronunciation_data or "words" not in pronunciation_data:
        await message.answer("Ошибка загрузки данных для произношения")
        return
    print(f"DEBUG: Number of words for pronunciation: {len(pronunciation_data['words'])}")

    # Сохраняем данные в состояние
    await state.update_data(
        pronunciation_words=pronunciation_data["words"],
        current_pronunciation_word=0
    )

    # Отправляем инструкцию
    await message.answer(MESSAGES["pronunciation_intro"])

    # Показываем первое слово для произношения
    await show_pronunciation_word(user_id, message, state, user_statistics, user_progress) # ИСПРАВЛЕНО: передаем user_id

# --- КОНЕЦ start_pronunciation_block ---


@router.callback_query(F.data == "start_pronunciation_lesson")
async def start_pronunciation_lesson_from_callback(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress): # user_id убран из сигнатуры, так как он доступен через callback.from_user.id
    """
    Обработчик кнопки "Начать урок произношения".
    Вызывает start_pronunciation_block для инициализации и старта.
    """
    await start_pronunciation_block(callback.from_user.id, callback.message, state, user_statistics, user_progress)
    await callback.answer()

def _sanitize_filename(text: str, max_length: int = 50) -> str:
    """
    Очищает строку для использования в качестве части имени файла.
    Удаляет недопустимые символы и обрезает строку до max_length.
    """
    sanitized = re.sub(r'[^\w\s-]', '', text).strip()
    sanitized = re.sub(r'\s+', '_', sanitized)
    sanitized = re.sub(r'__+', '_', sanitized)
    sanitized = sanitized.strip('_')
    return sanitized[:max_length]

async def show_pronunciation_word(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress): # ИСПРАВЛЕНО: Добавлен user_id
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

    # --- ИЗМЕНЕНИЕ: Сохраняем все необходимые параметры слова в состоянии ---
    await state.update_data(
        current_pronunciation_word_data=current_word, # Сохраняем весь словарь слова для удобства
        current_pronunciation_text=current_word['english'], # Отдельно 'english' для прямой проверки
        current_pronunciation_translation=current_word['russian'],
        current_pronunciation_transcription=current_word['transcription'],
        current_pronunciation_slow_mode=False # Сбрасываем режим замедления при показе нового слова
    )
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    user_progress.update_progress(
        user_id, # ИСПРАВЛЕНО: Используем переданный user_id
        current_pronunciation_text=current_word['english'],
        current_pronunciation_slow_mode=False
    )

    # Показываем информацию о слове
    await message.answer(
        f"📝 **Слово:** {current_word['english']}\n"
        f"🇷🇺 **Перевод:** {current_word['russian']}\n"
        f"🔤 **Транскрипция:** {current_word['transcription']}",
        parse_mode="Markdown"
    )

    # Генерируем и отправляем аудио произношения (всегда в обычном режиме при первом показе)
    sanitized_english_word = _sanitize_filename(current_word['english'])
    audio_filename = f"pronunciation_{current_index}_{sanitized_english_word}"
    audio_path = await generate_audio(current_word['english'], audio_filename, 'en', slow_mode=False)

    if audio_path and os.path.exists(audio_path):
        try:
            audio = FSInputFile(audio_path)
            await message.answer_voice(
                voice=audio,
                caption="🔊 **Послушай произношение**",
                parse_mode="Markdown"
            )
            if os.path.exists(audio_path):
                 os.remove(audio_path)
        except Exception as e:
            print(f"Ошибка отправки аудио: {e}")
            await message.answer("🔊 **Послушай произношение:** (аудио недоступно)")
    else:
        await message.answer("🔊 **Послушай произношение:** (аудио недоступно)")

    # Инструкция и клавиатура с меню
    await message.answer(
        MESSAGES["pronunciation_instruction"],
        reply_markup=get_keyboard_with_menu(get_pronunciation_keyboard())
    )

    await state.set_state(LessonStates.PRONUNCIATION_LISTEN)


# --- ИЗМЕНЕНИЕ: slow_down_pronunciation_handler для повторного вывода текста и замедленного аудио ---
@router.callback_query(
    F.data == "slow_down_pronunciation",
    LessonStates.PRONUNCIATION_LISTEN
)
@router.callback_query(F.data == "slow_down_pronunciation", LessonStates.PRONUNCIATION_RECORD)
async def slow_down_pronunciation_handler(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    data = await state.get_data()
    # Получаем данные о текущем слове из состояния
    text = data.get("current_pronunciation_text")
    translation = data.get("current_pronunciation_translation")
    transcription = data.get("current_pronunciation_transcription")

    if not text:
        await callback.answer("Извини, не могу найти текст для замедленного произношения.", show_alert=True)
        return

    # Помечаем, что сейчас slow mode
    await state.update_data(current_pronunciation_slow_mode=True)

    # 1) Повторно выводим текст фразы
    await callback.message.answer(
        f"📝 **Слово:** {text}\n"
        f"🇷🇺 **Перевод:** {translation}\n"
        f"🔤 **Транскрипция:** {transcription}",
        parse_mode="Markdown"
    )

    # 2) Генерируем и отправляем замедленное аудио
    sanitized_text = _sanitize_filename(text)
    filename = f"slow_{callback.from_user.id}_{sanitized_text}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    audio_path = await generate_audio(text, filename, lang='en', slow_mode=True)
    if not audio_path or not os.path.exists(audio_path):
        await callback.answer("Не удалось сгенерировать замедленное аудио.", show_alert=True)
        return

    await callback.message.answer_voice(
        voice=FSInputFile(audio_path),
        caption=f"🐢 Замедленное произношение: **{text}**",
        parse_mode="Markdown"
    )
    os.remove(audio_path) # Удаляем временный файл

    # 3) Отправляем приглашение с кнопками
    await callback.message.answer(
        MESSAGES["pronunciation_instruction"],
        reply_markup=get_keyboard_with_menu(get_pronunciation_keyboard())
    )
    await callback.answer() # Закрываем "часики" на кнопке
# --- КОНЕЦ ИЗМЕНЕНИЯ slow_down_pronunciation_handler ---


@router.callback_query(
    F.data == "repeat_pronunciation",
    LessonStates.PRONUNCIATION_LISTEN
)
@router.callback_query(F.data == "repeat_pronunciation", LessonStates.PRONUNCIATION_RECORD)
async def repeat_pronunciation_handler(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    data = await state.get_data()

    # Используем current_pronunciation_text из состояния
    text = data.get("current_pronunciation_text")
    slow_mode = data.get("current_pronunciation_slow_mode", False)
    if not text:
        await callback.answer("Извини, не могу найти текст для повторного произношения.", show_alert=True)
        return

    sanitized_text = _sanitize_filename(text)
    filename = f"rep_{callback.from_user.id}_{sanitized_text}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    audio_path = await generate_audio(text, filename, lang='en', slow_mode=slow_mode)
    if not audio_path or not os.path.exists(audio_path):
        await callback.answer("Не удалось сгенерировать аудио.", show_alert=True)
        return

    await callback.message.answer_voice(
        voice=FSInputFile(audio_path),
        caption=f"{'🐢 ' if slow_mode else ''}Повторяю: **{text}**",
        parse_mode="Markdown"
    )
    os.remove(audio_path)
    await callback.message.answer(
        MESSAGES["pronunciation_instruction"],
        reply_markup=get_keyboard_with_menu(get_pronunciation_keyboard())
    )
    await callback.answer()


@router.callback_query(F.data == "record_pronunciation", LessonStates.PRONUNCIATION_LISTEN)
async def request_pronunciation_recording(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Запрос записи произношения"""
    # Здесь edit_text уместен, так как мы меняем сообщение с инструкцией
    await callback.message.edit_text(
        "🎤  Нажми на значок микрофона в правом нижнем углу в Telegram и произнеси слово",
        reply_markup=get_keyboard_with_menu(get_pronunciation_keyboard())
    )
    await state.set_state(LessonStates.PRONUNCIATION_RECORD)
    await callback.answer()


@router.callback_query(F.data == "skip_pronunciation", LessonStates.PRONUNCIATION_LISTEN)
@router.callback_query(F.data == "skip_pronunciation", LessonStates.PRONUNCIATION_RECORD)
@router.callback_query(F.data == "next_pronunciation")
async def next_pronunciation_word(callback: CallbackQuery, state: FSMContext, user_progress: UserProgress, user_statistics: UserStatistics):
    """Переход к следующему слову для произношения"""
    user_id = callback.from_user.id
    data = await state.get_data()
    words = data.get("pronunciation_words", []) # Получаем список слов
    current_index = data.get("current_pronunciation_word", 0)

    # Увеличиваем индекс
    await state.update_data(current_pronunciation_word=current_index + 1)

    # Обновляем прогресс пользователя
    user_progress.update_progress(
        user_id,
        current_item=current_index + 1,
        current_pronunciation_slow_mode=False
    )

    # Показываем следующее слово. user_progress уже передан, передаем user_statistics.
    await show_pronunciation_word(user_id, callback.message, state, user_statistics, user_progress) # ИСПРАВЛЕНО: передаем user_id
    await callback.answer()


@router.callback_query(F.data == "next", LessonStates.PRONUNCIATION_COMPLETE)
async def pronunciation_complete_next(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Завершение блока произношения и переход к лексике"""

    user_id = callback.from_user.id
    # ИЗМЕНЕНИЕ: Используем новый метод для расчета среднего балла произношения
    average_score = user_statistics.calculate_average_pronunciation_score_for_block(user_id, lesson_id=CURRENT_LESSON_ID)

    completion_message = (
        "🎉 Блок произношения завершен!\n\n"
        f"🗣️ **Ваш средний процент произношения по этому блоку:** {average_score:.1f}%\n\n"
        "Переходим к лексическим упражнениям..."
    )

    await callback.message.edit_text(
        completion_message
    )

    # Обновляем прогресс
    user_progress.update_progress(
        user_id,
        current_block="pronunciation",
        current_item=0
    )
    # ИЗМЕНЕНИЕ: Обновляем статус блока в user_statistics
    user_statistics.update_block_status(user_id, "pronunciation", completed=True, average_score=average_score, lesson_id=CURRENT_LESSON_ID)

    # ИЗМЕНЕНИЕ: Проверяем завершение урока и отмечаем его, если все обязательные блоки пройдены
    # Предполагаем, что для завершения урока нужны блоки "terms" и "pronunciation".
    # Если у вас есть другие обязательные блоки, добавьте их в эту проверку.
    if user_statistics.is_block_completed(user_id, "terms", lesson_id=CURRENT_LESSON_ID) and \
       user_statistics.is_block_completed(user_id, "pronunciation", lesson_id=CURRENT_LESSON_ID):
        user_statistics.mark_lesson_completed(user_id, lesson_id=CURRENT_LESSON_ID)
        print(f"DEBUG: Урок '{CURRENT_LESSON_ID}' отмечен как завершенный для пользователя {user_id}.")


    # Предполагается, что эта функция start_lexical_en_to_ru_block существует и принимает user_statistics и user_progress
    try:
        from bot.handlers.lesson import start_lexical_en_to_ru_block # Добавляем импорт
        await start_lexical_en_to_ru_block(user_id, callback.message, state, user_statistics, user_progress)
    except NameError:
        await callback.message.answer("Функция для лексического блока (start_lexical_en_to_ru_block) еще не реализована или не импортирована.")
    await callback.answer()


#+++++++++++ НАЧАЛО ЛЕКСИЧЕСКОГО БЛОКА ++++++++++++++++++
async def start_lexical_en_to_ru_block(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Начало лексического блока: английский -> русский"""

    lexical_data = await load_json_data("translation_questions.json")
    if not lexical_data:
        await message.answer("Ошибка загрузки лексических данных")
        return

    questions = []
    for word, data in lexical_data.items():
        questions.append({
            "word": word,
            "correct": data["correct"],
            "options": data["options"]
        })

    await state.update_data(
        lexical_en_ru=questions,
        current_lexical_en=0,
        lexical_score_en_ru=0 # Отдельный счет для этого подблока
    )

    # Обновляем прогресс пользователя
    user_progress.update_progress(user_id, current_block="lexical_en_to_ru", current_item=0)
    print(f"DEBUG: Прогресс пользователя {user_id} обновлен для блока lexical_en_to_ru.")

    await message.answer(MESSAGES["lexical_intro"])

    await show_lexical_en_question(user_id, message, state, user_statistics, user_progress)


async def show_lexical_en_question(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Показать вопрос английский -> русский"""

    data = await state.get_data()
    questions = data.get("lexical_en_ru", [])
    current_index = data.get("current_lexical_en", 0)

    if current_index >= len(questions):
        score = data.get("lexical_score_en_ru", 0) # Используем отдельный счет
        total_questions = len(questions)
        score_percentage = (score / total_questions) * 100 if total_questions > 0 else 0

        await message.answer(
            f"{MESSAGES['lexical_en_ru_complete']}\n\n"
            f"Ваш результат: {score}/{total_questions} ( {score_percentage:.1f}%) ✨",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        await state.set_state(LessonStates.LEXICAL_EN_COMPLETE)

        # Обновляем статус подблока в UserStatistics
        user_statistics.update_block_status(user_id, "lexical_en_to_ru", completed=True, average_score=score_percentage, lesson_id=CURRENT_LESSON_ID)
        print(f"DEBUG: Статус подблока lexical_en_to_ru обновлен как завершенный для пользователя {user_id}.")

        return

    current_question = questions[current_index]

    # Обновляем прогресс пользователя на текущий вопрос
    user_progress.update_progress(user_id, current_block="lexical_en_to_ru", current_item=current_index + 1)

    question_text = f"📝 **Переведи слово ({current_index + 1}/{len(questions)}):**\n\n**{current_question['word']}**"

    await message.answer(
        question_text,
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_choice_keyboard(current_question['options'], f"en_{current_index}")) # Добавляем префикс "en_"
    )

    await state.set_state(LessonStates.LEXICAL_EN_TO_RU)


@router.callback_query(F.data.startswith("lexical_en_"), LessonStates.LEXICAL_EN_TO_RU) # Обновлен префикс для фильтрации
async def process_lexical_en_answer(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Обработка ответа на английский -> русский"""
    user_id = callback.from_user.id
    data = await state.get_data()
    questions = data.get("lexical_en_ru", [])
    current_index = data.get("current_lexical_en", 0)
    score = data.get("lexical_score_en_ru", 0) # Используем отдельный счет

    if current_index >= len(questions):
        return

    current_question = questions[current_index]

    callback_parts = callback.data.split("_")
    # selected_answer = "_".join(callback_parts[2:]) # Если ответ может содержать нижнее подчеркивание
    selected_answer = callback_parts[-1] # Теперь просто последний элемент

    correct_answer = current_question["correct"]
    is_correct = False

    if selected_answer == correct_answer:
        response_text = MESSAGES["correct_answer"]
        score += 1
        is_correct = True
        await state.update_data(lexical_score_en_ru=score)
    else:
        response_text = f"❌ Упс, ошибка!\nТвой ответ: {selected_answer}\nПравильный ответ: {correct_answer}"
        is_correct = False

    # Добавляем попытку в статистику
    user_statistics.add_lexical_attempt(user_id, "en_to_ru", current_question['word'], is_correct, CURRENT_LESSON_ID, selected_answer)

    await callback.message.edit_text(
        f"**{current_question['word']}**\n\n{response_text}",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_continue_keyboard())
    )
    await callback.answer()


@router.callback_query(F.data == "continue_exercise", LessonStates.LEXICAL_EN_TO_RU)
async def continue_lexical_en_to_ru(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Продолжить лексический блок английский -> русский"""
    user_id = callback.from_user.id

    print("[DEBUG] Запущен обработчик continue_lexical_en_to_ru")
    data = await state.get_data()
    print("[DEBUG] Текущие данные из state:", data)
    current_index = data.get("current_lexical_en", 0)
    print(f"[DEBUG] Текущий индекс вопроса: {current_index}")
    new_index = current_index + 1
    await state.update_data(current_lexical_en=new_index)
    print(f"[DEBUG] Индекс увеличен. Новый индекс: {new_index}")

    # Обновляем прогресс пользователя перед показом следующего вопроса
    user_progress.update_progress(user_id, current_block="lexical_en_to_ru", current_item=new_index + 1)

    try:
        await show_lexical_en_question(user_id, callback.message, state, user_statistics, user_progress)
        print("[DEBUG] Функция show_lexical_en_question успешно вызвана")
    except Exception as e:
        print(f"[ERROR] Ошибка при вызове show_lexical_en_question: {e}")

    await callback.answer()


@router.callback_query(F.data == "next", LessonStates.LEXICAL_EN_COMPLETE)
async def lexical_en_complete_next(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Завершение блока английский -> русский, переход к русский -> английский"""
    user_id = callback.from_user.id
    await callback.message.edit_text(
        "Отлично! Теперь попробуем в обратную сторону..."
    )

    # Обновляем прогресс пользователя для перехода к следующему подблоку
    user_progress.update_progress(user_id, current_block="lexical_ru_to_en", current_item=0)

    # Запускаем блок русский -> английский
    await start_lexical_ru_to_en_block(user_id, callback.message, state, user_statistics, user_progress)
    await callback.answer()

async def start_lexical_ru_to_en_block(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Начало лексического блока: русский -> английский"""

    lexical_data = await load_json_data("translation_questions_russian.json")
    if not lexical_data:
        await message.answer("Ошибка загрузки лексических данных (русский)")
        return

    questions = []
    for word, data in lexical_data.items():
        questions.append({
            "word": word,
            "correct": data["correct"],
            "options": data["options"]
        })

    await state.update_data(
        lexical_ru_en=questions,
        current_lexical_ru=0,
        lexical_score_ru_en=0 # Отдельный счет для этого подблока
    )

    # Обновляем прогресс пользователя
    user_progress.update_progress(user_id, current_block="lexical_ru_to_en", current_item=0)
    print(f"DEBUG: Прогресс пользователя {user_id} обновлен для блока lexical_ru_to_en.")

    await message.answer(MESSAGES["lexical_intro"])

    await show_lexical_ru_question(user_id, message, state, user_statistics, user_progress)


async def show_lexical_ru_question(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Показать вопрос русский -> английский"""

    data = await state.get_data()
    questions = data.get("lexical_ru_en", [])
    current_index = data.get("current_lexical_ru", 0)

    if current_index >= len(questions):
        score = data.get("lexical_score_ru_en", 0) # Используем отдельный счет
        total_questions = len(questions)
        score_percentage = (score / total_questions) * 100 if total_questions > 0 else 0

        await message.answer(
            f"{MESSAGES['lexical_ru_en_complete']}\n\n"
            f"Ваш результат: {score}/{total_questions} ( {score_percentage:.1f}%) ✨",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        await state.set_state(LessonStates.LEXICAL_RU_COMPLETE)

        # Обновляем статус подблока в UserStatistics
        user_statistics.update_block_status(user_id, "lexical_ru_to_en", completed=True, average_score=score_percentage, lesson_id=CURRENT_LESSON_ID)
        print(f"DEBUG: Статус подблока lexical_ru_to_en обновлен как завершенный для пользователя {user_id}.")

        return

    current_question = questions[current_index]

    # Обновляем прогресс пользователя на текущий вопрос
    user_progress.update_progress(user_id, current_block="lexical_ru_to_en", current_item=current_index + 1)

    question_text = f"📝 **Переведи слово ({current_index + 1}/{len(questions)}):**\n\n**{current_question['word']}**"

    await message.answer(
        question_text,
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_choice_keyboard(current_question['options'], f"ru_{current_index}")) # Добавляем префикс "ru_"
    )

    await state.set_state(LessonStates.LEXICAL_RU_TO_EN)


@router.callback_query(F.data.startswith("lexical_ru_"), LessonStates.LEXICAL_RU_TO_EN)
async def process_lexical_ru_answer(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Обработка ответа на русский -> английский"""
    user_id = callback.from_user.id
    data = await state.get_data()
    questions = data.get("lexical_ru_en", [])
    current_index = data.get("current_lexical_ru", 0)
    score = data.get("lexical_score_ru_en", 0) # Используем отдельный счет

    if current_index >= len(questions):
        return

    current_question = questions[current_index]

    callback_parts = callback.data.split("_")
    selected_answer = callback_parts[-1]

    correct_answer = current_question["correct"]
    is_correct = False

    if selected_answer == correct_answer:
        response_text = MESSAGES["correct_answer"]
        score += 1
        is_correct = True
        await state.update_data(lexical_score_ru_en=score) # <-- ИСПРАВЛЕНО: Изменено с lexical_ru_score на lexical_score_ru_en
    else:
        response_text = f"❌ Упс, ошибка!\nТвой ответ: {selected_answer}\nПравильный ответ: {correct_answer}"
        is_correct = False

    # Добавляем попытку в статистику
    user_statistics.add_lexical_attempt(user_id, "ru_to_en", current_question['word'], is_correct, CURRENT_LESSON_ID, selected_answer)

    await callback.message.edit_text(
        f"**{current_question['word']}**\n\n{response_text}",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_continue_keyboard())
    )
    await callback.answer()


@router.callback_query(F.data == "continue_exercise", LessonStates.LEXICAL_RU_TO_EN)
async def continue_lexical_ru_to_en(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Продолжить русский -> английский"""
    user_id = callback.from_user.id
    data = await state.get_data()
    current_index = data.get("current_lexical_ru", 0)
    new_index = current_index + 1
    await state.update_data(current_lexical_ru=new_index)

    # Обновляем прогресс пользователя перед показом следующего вопроса
    user_progress.update_progress(user_id, current_block="lexical_ru_to_en", current_item=new_index + 1)

    await show_lexical_ru_question(user_id, callback.message, state, user_statistics, user_progress)
    await callback.answer()


@router.callback_query(F.data == "next", LessonStates.LEXICAL_RU_COMPLETE)
async def lexical_complete_next(callback: CallbackQuery, state: FSMContext, user_progress: UserProgress,
                                user_statistics: UserStatistics):
    """
    Завершение блока русский -> английский, переход к блоку сборки слов (word_build).
    ВАЖНО: Общий лексический блок будет отмечен как завершенный после прохождения word_build.
    """
    user_id = callback.from_user.id
    lesson_id = CURRENT_LESSON_ID

    # 1. Отмечаем текущий подблок lexical_ru_to_en как завершенный (если это не было сделано ранее)
    # Это должно было произойти в show_lexical_ru_question, но для надежности оставим здесь.
    user_statistics.update_block_status(user_id, "lexical_ru_to_en", completed=True, lesson_id=lesson_id)
    print(f"DEBUG: Подблок lexical_ru_to_en отмечен как завершенный для пользователя {user_id}.")


    await callback.message.edit_text(
        "🎉 Лексические упражнения (перевод) завершены!\n\n" # Обновленное сообщение
        "Теперь переходим к **Сборке слов**."
    )

    # 2. Обновляем прогресс для перехода к новому подблоку word_build
    user_progress.update_progress(
        user_id,
        current_block="lexical_word_build", # Указываем конкретный подблок
        current_item=0
    )
    print(f"DEBUG: Прогресс пользователя {user_id} обновлен для блока lexical_word_build.")

    # 3. Запускаем блок сборки слов
    try:
        # Теперь start_word_build принимает callback, state, user_statistics, user_progress
        await start_word_build(callback, state, user_statistics, user_progress)
        print(f"DEBUG: Пользователь {user_id} перешел к блоку Word Build.")

    except NameError:
        await callback.message.answer(
            "Функция для блока 'Собери слово' (start_word_build) еще не реализована или не импортирована.")

    await callback.answer()

# --- Упражнение: Сборка слова из частей (Word Build) ---

async def start_word_build(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Начало упражнения на сборку слов"""
    user_id = callback.from_user.id # Получаем user_id напрямую
    lesson_id = CURRENT_LESSON_ID

    data = await load_json_data("word_build.json")
    if not data:
        await callback.message.answer("Ошибка загрузки данных для сборки слов.")
        return

    words = list(data.keys())
    await state.update_data(
        word_build_data=data,
        word_build_words=words,
        current_word_index=0,
        word_build_collected="",
        word_build_score=0
    )

    # Инициализация статистики для подблока 'lexical_word_build'
    user_statistics.init_lesson_block_data(user_id, lesson_id, 'lexical', 'word_build')
    user_progress.update_progress(user_id, current_block="lexical_word_build", current_item=0) # Обновляем прогресс
    print(f"DEBUG: Пользователь {user_id} начал блок Word Build.")

    await show_word_build_exercise(user_id, callback.message, state, user_statistics, user_progress) # Передаем user_id
    await callback.answer()


async def show_word_build_exercise(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress): # Добавлены user_id, user_statistics, user_progress
    data = await state.get_data()
    words = data.get("word_build_words", [])
    index = data.get("current_word_index", 0)
    all_data = data.get("word_build_data", {})

    if index >= len(words):
        await finish_word_build(user_id, message, state, user_statistics, user_progress) # Передаем user_id
        return

    word = words[index]
    parts = all_data[word]["scrambled_parts"]
    collected = data.get("word_build_collected", "")

    placeholder = " ".join(["_" * len(part) for part in all_data[word]["parts"]])
    user_input = " + ".join(collected.split("+")) if collected else ""

    text = (
        f"🔤 Собери слово из частей ({index + 1}/{len(words)}):\n\n" # Добавил счетчик
        f"{placeholder}\n\n"
        f"Ты собрал: {user_input or 'ничего'}\n\n"
        f"Выбери части:"
    )

    # Обновляем прогресс пользователя на текущий вопрос
    user_progress.update_progress(user_id, current_block="lexical_word_build", current_item=index + 1)

    await message.edit_text(text, reply_markup=get_word_build_keyboard(parts, collected))
    await state.set_state(LessonStates.LEXICAL_WORD_BUILD)
    print(f"DEBUG: Пользователь {user_id} отображает слово для сборки: {word} (индекс {index}).")


async def finish_word_build(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    print(f"DEBUG: Начало функции finish_word_build для пользователя {user_id}.")
    lesson_id = CURRENT_LESSON_ID
    data = await state.get_data()
    words = data.get("word_build_words", [])
    total = len(words)
    score = data.get("word_build_score", 0)

    print(f"DEBUG: finish_word_build: total_words={total}, score={score}.")

    try:
        # Сохранение статистики для подблока "lexical_word_build"
        user_statistics.update_block_score(user_id, lesson_id, 'lexical', 'word_build', score, total)
        user_statistics.mark_block_completed(user_id, lesson_id, 'lexical', 'word_build', True)
        print(f"DEBUG: Подблок lexical_word_build отмечен как завершенный для пользователя {user_id}. Счет: {score}/{total}.")

        # Проверяем и отмечаем весь урок как завершенный, если это применимо
        user_statistics._check_and_mark_lesson_completed(user_id, lesson_id)
        print(f"DEBUG: finish_word_build: Проверена и обновлена статистика урока. (Продолжение выполнения после _check_and_mark_lesson_completed)") # НОВОЕ отладочное сообщение

        user_progress.clear_current_block_data(user_id) # Очищаем текущий прогресс после завершения блока
        print(f"DEBUG: finish_word_build: Прогресс пользователя очищен.")

        # Пересчитываем overall_lexical_score для вывода
        overall_lexical_score_for_display = user_statistics.get_overall_lexical_score(user_id, lesson_id=lesson_id)
        print(f"DEBUG: finish_word_build: Общий балл по лексике для отображения: {overall_lexical_score_for_display:.1f}%")

        result_text = (
            f"🎉 Упражнение **Собери слово** завершено!\n"
            f"Вы правильно собрали {score} из {total} слов.\n\n"
            f"Ваш общий результат по лексике: {overall_lexical_score_for_display:.1f}%"
        )

        # Отправляем новое сообщение с результатом
        print(f"DEBUG: finish_word_build: Попытка отправить сообщение о завершении.")
        await message.answer(result_text, parse_mode="Markdown") # Добавил parse_mode="Markdown"
        print(f"DEBUG: finish_word_build: Сообщение о завершении упражнения отправлено.")

        # Сразу переходим к следующему блоку: Грамматика
        from bot.handlers.lesson import start_grammar_block # Убедитесь, что импорт корректен
        print(f"DEBUG: finish_word_build: Попытка вызвать start_grammar_block.")
        await start_grammar_block(user_id, message, state, user_statistics, user_progress)
        print(f"DEBUG: finish_word_build: Вызвана start_grammar_block для пользователя {user_id}.")

        print(f"DEBUG: finish_word_build: Завершение функции для пользователя {user_id}. Автоматический переход к Грамматике.")

    except Exception as e:
        print(f"ERROR: Ошибка в finish_word_build для пользователя {user_id}: {e}")
        traceback.print_exc() # Выводим полный traceback для отладки
        await message.answer("Произошла ошибка при завершении упражнения. Пожалуйста, попробуйте еще раз или обратитесь в поддержку.")
        # Опционально, сброс состояния или возврат в главное меню
        await state.clear()
        # Убедитесь, что get_keyboard_with_menu и get_main_menu_keyboard импортированы
        from bot.keyboards import get_keyboard_with_menu, get_main_menu_keyboard
        await message.answer("Возвращаемся в главное меню.", reply_markup=get_keyboard_with_menu(get_main_menu_keyboard()))


@router.callback_query(F.data.startswith("wb_part_"), LessonStates.LEXICAL_WORD_BUILD)
async def handle_word_part(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    user_id = callback.from_user.id
    part = callback.data.replace("wb_part_", "")
    data = await state.get_data()
    collected = data.get("word_build_collected", "")
    collected += "+" + part if collected else part
    await state.update_data(word_build_collected=collected)
    await show_word_build_exercise(user_id, callback.message, state, user_statistics, user_progress) # Передаем user_id
    await callback.answer()


@router.callback_query(F.data == "wb_check", LessonStates.LEXICAL_WORD_BUILD)
async def check_word_build(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    user_id = callback.from_user.id
    data = await state.get_data()
    words = data.get("word_build_words", [])
    index = data.get("current_word_index", 0)
    all_data = data.get("word_build_data", {})
    collected = data.get("word_build_collected", "")

    word = words[index]
    correct_parts = all_data[word]["parts"]
    user_parts = collected.split("+")

    is_correct = (user_parts == correct_parts) # Определяем правильность ответа

    if is_correct:
        score = data.get("word_build_score", 0) + 1
        await state.update_data(word_build_score=score)

        await callback.message.edit_text(
            f"✅ Правильный ответ!\n\n"
            f"Вы собрали: {' + '.join(correct_parts)}\n\n"
            f"Нажми «➡️ Далее», чтобы продолжить.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➡️ Далее", callback_data="wb_next")]
            ])
        )
    else:
        correct = " + ".join(correct_parts)
        await callback.message.edit_text(
            f"❌ Неправильно.\nТвой ответ: {' + '.join(user_parts)}\nПравильный ответ: {correct}\n\n"
            f"Нажми «➡️ Далее».",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➡️ Далее", callback_data="wb_next")]
            ])
        )
    # Добавляем попытку в статистику (можно добавить, если нужно отслеживать каждую попытку)
    # user_statistics.add_lexical_attempt(user_id, "word_build", word, is_correct, CURRENT_LESSON_ID)
    await callback.answer()


@router.callback_query(F.data == "wb_next", LessonStates.LEXICAL_WORD_BUILD)
async def next_word_after_check(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    user_id = callback.from_user.id
    print(f"DEBUG: next_word_after_check: Callback 'wb_next' получен для пользователя {user_id} в состоянии {await state.get_state()}.")

    data = await state.get_data()
    current_index = data.get("current_word_index", 0)
    words = data.get("word_build_words", [])
    total_words = len(words)

    # Увеличиваем индекс для СЛЕДУЮЩЕГО слова
    new_index = current_index + 1

    await state.update_data(
        current_word_index=new_index,
        word_build_collected=""
    )
    print(f"DEBUG: next_word_after_check: Пользователь {user_id}, текущий индекс={current_index}, новый индекс={new_index}, всего слов={total_words}.")

    if new_index >= total_words:
        # Все слова обработаны (или пропущены), завершаем блок
        print(f"DEBUG: next_word_after_check: Все слова обработаны. Вызов finish_word_build для пользователя {user_id}.")
        await finish_word_build(user_id, callback.message, state, user_statistics, user_progress)
    else:
        # Есть еще слова, показываем следующее упражнение
        print(f"DEBUG: next_word_after_check: Отображение следующего слова (индекс {new_index}) для пользователя {user_id}.")
        await show_word_build_exercise(user_id, callback.message, state, user_statistics, user_progress)

    await callback.answer() # Всегда отвечаем на callback-запрос


@router.callback_query(F.data == "wb_skip", LessonStates.LEXICAL_WORD_BUILD)
async def skip_word_build(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    user_id = callback.from_user.id
    data = await state.get_data()
    index = data.get("current_word_index", 0)

    await state.update_data(
        current_word_index=index + 1,
        word_build_collected=""
    )

    await show_word_build_exercise(user_id, callback.message, state, user_statistics, user_progress) # Передаем user_id
    await callback.answer()


@router.callback_query(F.data == "next", LessonStates.LEXICAL_WORD_COMPLETE)
async def word_build_complete_next(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    user_id = callback.from_user.id
    lesson_id = CURRENT_LESSON_ID

    # Отправляем новое сообщение (не меняем старое!)
    await callback.message.answer("🎉 Отличная работа!\n"
                                  "Блок **Сборка слов** завершен.\n\n"
                                  "Переходим к следующему этапу: **Грамматика**.")

    # Переход к грамматике
    from bot.handlers.lesson import start_grammar_block # Убедитесь, что start_grammar_block импортируется здесь
    await start_grammar_block(user_id, callback.message, state, user_statistics, user_progress) # Передаем user_id

    await callback.answer()

# --- Конец упражнения: Сборка слова ---
async def start_grammar_block(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Начало грамматического блока"""
    print(f"DEBUG: Начало функции start_grammar_block для пользователя {user_id}.") # Добавлено отладочное сообщение
    lesson_id = CURRENT_LESSON_ID

    # Инициализация статистики для блока 'grammar'
    user_statistics.init_lesson_block_data(user_id, lesson_id, 'grammar', None) # Инициализируем основной блок 'grammar'
    user_progress.update_progress(user_id, current_block="grammar", current_item=0) # Обновляем прогресс
    print(f"DEBUG: Пользователь {user_id} начал блок Грамматика.")

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
    print(f"DEBUG: Пользователь {user_id} перешел в состояние GRAMMAR_CHOICE.")


@router.callback_query(F.data == "grammar_understood", LessonStates.GRAMMAR_CHOICE)
async def grammar_understood(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics,
                             user_progress: UserProgress):
    """Пользователь понял грамматику"""
    await callback.answer()
    user_id = callback.from_user.id
    lesson_id = CURRENT_LESSON_ID

    try:
        user_statistics.mark_block_completed(user_id, lesson_id, "grammar", completed=True)
        print(f"DEBUG: Блок грамматики отмечен как завершенный для пользователя {user_id}.")

        print(f"DEBUG: Попытка проверить и отметить урок как завершенный для пользователя {user_id}.")
        user_statistics._check_and_mark_lesson_completed(user_id, lesson_id)

        print(
            f"DEBUG: Вызов user_statistics.save_data() из grammar_understood для пользователя {user_id}.")  # НОВОЕ ОТЛАДОЧНОЕ СООБЩЕНИЕ
        user_statistics.save_data()
        print(
            f"DEBUG: Данные статистики сохранены после grammar_understood для пользователя {user_id}.")  # НОВОЕ ОТЛАДОЧНОЕ СООБЩЕНИЕ
    except Exception as stat_e:
        print(f"ERROR: Ошибка при работе со статистикой в grammar_understood для пользователя {user_id}: {stat_e}")
        print(traceback.format_exc())

    print(f"DEBUG: Попытка изменить сообщение в grammar_understood для пользователя {user_id} (перед edit_text).")
    try:
        await callback.message.edit_text(
            "🎉 Отлично! Вы поняли грамматическое правило!\n\n"
            "Переходим к следующему блоку...",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        print(f"DEBUG: Сообщение успешно изменено для пользователя {user_id}.")
    except Exception as e:
        print(f"ERROR: Ошибка при изменении сообщения в grammar_understood для пользователя {user_id}: {e}")
        print(traceback.format_exc())
        await callback.message.answer(
            "🎉 Отлично! Вы поняли грамматическое правило!\n\n"
            "Переходим к следующему блоку...",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
    finally:
        print(f"DEBUG: Завершение обработки grammar_understood для пользователя {user_id} (после try-except).")

    await state.set_state(LessonStates.GRAMMAR_COMPLETE)
    user_progress.clear_current_block_data(user_id)
    print(f"DEBUG: Пользователь {user_id} перешел в состояние GRAMMAR_COMPLETE.")


@router.callback_query(F.data == "grammar_questions", LessonStates.GRAMMAR_CHOICE)
async def grammar_questions(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Пользователь хочет задать вопросы"""
    user_id = callback.from_user.id
    await callback.message.edit_text(
        MESSAGES["grammar_ask_question"],
        reply_markup=get_keyboard_with_menu(get_grammar_qa_keyboard())
    )

    await state.set_state(LessonStates.GRAMMAR_QA)
    print(f"DEBUG: Пользователь {user_id} перешел в состояние GRAMMAR_QA.")
    await callback.answer()


@router.message(F.text, LessonStates.GRAMMAR_QA)
async def process_grammar_question(message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Обработка вопроса по грамматике"""
    user_id = message.from_user.id
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
        print(f"DEBUG: Пользователь {user_id} получил ответ на вопрос по грамматике.")

    except Exception as e:
        await thinking_msg.delete()
        await message.answer(
            "Извини, произошла ошибка при обработке твоего вопроса. "
            "Попробуй переформулировать вопрос.",
            reply_markup=get_keyboard_with_menu(get_grammar_qa_keyboard())
        )
        print(f"ERROR: Ошибка в обработке вопроса по грамматике для пользователя {user_id}: {e}")


@router.callback_query(F.data == "grammar_now_understood", LessonStates.GRAMMAR_QA)
async def grammar_now_understood(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics,
                                 user_progress: UserProgress):
    """Пользователь понял после объяснения"""
    await callback.answer()
    user_id = callback.from_user.id
    lesson_id = CURRENT_LESSON_ID

    try:
        user_statistics.mark_block_completed(user_id, lesson_id, "grammar", completed=True)
        print(f"DEBUG: Блок грамматики отмечен как завершенный для пользователя {user_id} (после вопросов).")

        print(f"DEBUG: Попытка проверить и отметить урок как завершенный для пользователя {user_id} (после вопросов).")
        user_statistics._check_and_mark_lesson_completed(user_id, lesson_id)

        print(
            f"DEBUG: Вызов user_statistics.save_data() из grammar_now_understood для пользователя {user_id}.")  # НОВОЕ ОТЛАДОЧНОЕ СООБЩЕНИЕ
        user_statistics.save_data()
        print(
            f"DEBUG: Данные статистики сохранены после grammar_now_understood для пользователя {user_id}.")  # НОВОЕ ОТЛАДОЧНОЕ СООБЩЕНИЕ
    except Exception as stat_e:
        print(f"ERROR: Ошибка при работе со статистикой в grammar_now_understood для пользователя {user_id}: {stat_e}")
        print(traceback.format_exc())

    print(f"DEBUG: Попытка изменить сообщение в grammar_now_understood для пользователя {user_id} (перед edit_text).")
    try:
        await callback.message.edit_text(
            "🎉 Превосходно! Теперь ты понимаешь грамматическое правило!\n\n"
            "Переходим к следующему блоку...",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        print(f"DEBUG: Сообщение успешно изменено для пользователя {user_id}.")
    except Exception as e:
        print(f"ERROR: Ошибка при изменении сообщения в grammar_now_understood для пользователя {user_id}: {e}")
        print(traceback.format_exc())
        await callback.message.answer(
            "🎉 Превосходно! Теперь ты понимаешь грамматическое правило!\n\n"
            "Переходим к следующему блоку...",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
    finally:
        print(f"DEBUG: Завершение обработки grammar_now_understood для пользователя {user_id} (после try-except).")

    await state.set_state(LessonStates.GRAMMAR_COMPLETE)
    user_progress.clear_current_block_data(user_id)
    print(f"DEBUG: Пользователь {user_id} перешел в состояние GRAMMAR_COMPLETE (после вопросов).")


@router.callback_query(F.data == "grammar_still_questions", LessonStates.GRAMMAR_QA)
async def grammar_still_questions(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """У пользователя остались вопросы"""
    user_id = callback.from_user.id
    await callback.message.edit_text(
        "Задай следующий вопрос по грамматике:",
        reply_markup=get_keyboard_with_menu(get_grammar_qa_keyboard())
    )

    # Остаемся в состоянии GRAMMAR_QA для продолжения диалога
    print(f"DEBUG: Пользователь {user_id} остался в состоянии GRAMMAR_QA для новых вопросов.")
    await callback.answer()

@router.callback_query(F.data == "next", LessonStates.GRAMMAR_COMPLETE)
async def grammar_complete_next(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Завершение грамматического блока и переход к лексико-грамматическим упражнениям"""
    user_id = callback.from_user.id
    lesson_id = CURRENT_LESSON_ID

    # Обновляем прогресс пользователя на следующий блок (практические упражнения)
    user_progress.update_progress(
        user_id,
        current_block="lexico_grammar", # Основной блок для всех упражнений
        current_item=0
    )
    print(f"DEBUG: Прогресс пользователя {user_id} обновлен для блока lexico_grammar.")

    await callback.message.edit_text(
        "🎉 Грамматический блок завершен!\n\n"
        "Переходим к практическим упражнениям..."
    )

    # Запускаем упражнения с глаголами
    await start_verb_exercise(user_id, callback.message, state, user_statistics, user_progress)

    await callback.answer()

# --- Подблок: Упражнения с глаголами (VERB_EXERCISE) ---

async def start_verb_exercise(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Начало упражнений с глаголами"""
    verb_data = await load_json_data("verb_it.json")
    print(f"DEBUG: verb_data = {verb_data}")
    if not verb_data:
        await message.answer("Ошибка загрузки данных упражнений")
        return

    print(f"DEBUG: verb_data length = {len(verb_data)}")

    await state.update_data(
        verb_exercises=verb_data,
        current_verb=0,
        verb_score=0
    )

    await message.answer(MESSAGES["verb_exercise_intro"])
    await show_verb_exercise(user_id, message, state, user_statistics, user_progress)


async def show_verb_exercise(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Показать упражнение с глаголами"""
    data = await state.get_data()
    exercises = data.get("verb_exercises", [])
    current_index = data.get("current_verb", 0)

    if current_index >= len(exercises):
        score = data.get("verb_score", 0)
        await message.answer(
            f"{MESSAGES['verb_exercise_complete']}\n\n"
            f"Ваш результат: {score}/{len(exercises)} ✨",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        user_statistics.update_block_score(user_id, CURRENT_LESSON_ID, "lexico_grammar", "verb", score, len(exercises))
        print(f"DEBUG: Setting state to VERB_COMPLETE for user {user_id}") # ADDED DEBUG
        await state.set_state(LessonStates.VERB_COMPLETE)
        return

    current_exercise = exercises[current_index]

    await message.answer(
        f"💻 **Упражнение {current_index + 1}/{len(exercises)}:**\n\n{current_exercise['text']}",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_text_exercise_keyboard())
    )

    await state.set_state(LessonStates.VERB_EXERCISE)


@router.message(F.text, LessonStates.VERB_EXERCISE)
async def process_verb_answer(message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Обработка ответа на упражнение с глаголами"""
    user_id = message.from_user.id
    data = await state.get_data()
    exercises = data.get("verb_exercises", [])
    current_index = data.get("current_verb", 0)
    score = data.get("verb_score", 0)

    if current_index >= len(exercises):
        return

    current_exercise = exercises[current_index]
    user_answer = message.text.strip().lower()
    correct_answer = current_exercise["answer"].lower()

    is_correct = (user_answer == correct_answer) # Для статистики
    user_statistics.add_lexical_attempt(user_id, "verb", current_exercise["text"], is_correct, CURRENT_LESSON_ID, user_message=user_answer) # Сохраняем попытку

    if is_correct:
        response_text = MESSAGES["correct_answer"]
        score += 1
        await state.update_data(verb_score=score)
    else:
        explanation = current_exercise.get('explanation', '')
        response_text = f"{MESSAGES['wrong_answer']}{current_exercise['answer']}\n\n💡 {explanation}" if explanation else f"{MESSAGES['wrong_answer']}{current_exercise['answer']}"

    await message.answer(
        response_text,
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_continue_keyboard())
    )


@router.callback_query(F.data == "skip_text_exercise", LessonStates.VERB_EXERCISE)
async def skip_verb_exercise(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Пропустить упражнение с глаголами"""
    user_id = callback.from_user.id
    data = await state.get_data()
    current_index = data.get("current_verb", 0)
    # Отмечаем как неправильный ответ для статистики, если нужно
    exercises = data.get("verb_exercises", [])
    if current_index < len(exercises):
        current_exercise = exercises[current_index]
        user_statistics.add_lexical_attempt(user_id, "verb", current_exercise["text"], False, CURRENT_LESSON_ID, user_message="Пропущено")

    await state.update_data(current_verb=current_index + 1)
    await show_verb_exercise(user_id, callback.message, state, user_statistics, user_progress)
    await callback.answer()


@router.callback_query(F.data == "continue_exercise", LessonStates.VERB_EXERCISE)
async def continue_verb_exercise_specific(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Продолжить упражнения с глаголами"""
    user_id = callback.from_user.id
    data = await state.get_data()
    current_index = data.get("current_verb", 0)
    await state.update_data(current_verb=current_index + 1)

    await show_verb_exercise(user_id, callback.message, state, user_statistics, user_progress)
    await callback.answer()


@router.callback_query(F.data == "next", LessonStates.VERB_COMPLETE)
async def verb_complete_next(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Завершение упражнений с глаголами, переход к множественному выбору"""
    print(f"DEBUG: Entering verb_complete_next handler for user {callback.from_user.id}") # ADDED DEBUG LINE
    user_id = callback.from_user.id
    await callback.message.edit_text("Отлично! Переходим к следующему типу упражнений...")
    print('DEBUG: 1')
    user_statistics.mark_block_completed(user_id, CURRENT_LESSON_ID, "lexico_grammar", "verb") # Отмечаем подблок как завершенный
    print('DEBUG: 2')
    # Обновляем общий статус блока lexico_grammar, если все подблоки завершены
    # (Эта логика может быть в UserStatistics._check_and_mark_lesson_completed или здесь)
    try:
        # ИСПРАВЛЕНО: Передача аргументов в update_progress как именованные
        user_progress.update_progress(user_id, current_block="lexico_grammar", current_item=1)
        print('DEBUG: 3 - user_progress.update_progress completed')
    except Exception as e:
        print(f"ERROR: Failed to update user_progress: {e}")
        traceback.print_exc()
        await callback.message.answer("Произошла ошибка при обновлении прогресса. Пожалуйста, попробуйте снова.")
        await callback.answer()
        return

    try:
        await start_mchoice_exercise(user_id, callback.message, state, user_statistics, user_progress)
        print('DEBUG: 4 - start_mchoice_exercise called')
    except Exception as e:
        print(f"ERROR: Failed to start mchoice exercise: {e}")
        traceback.print_exc()
        await callback.message.answer("Произошла ошибка при запуске следующего упражнения. Пожалуйста, попробуйте снова.")
        await callback.answer()
        return

    await callback.answer()

async def start_mchoice_exercise(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Начало упражнений с множественным выбором"""
    mchoice_data = await load_json_data("mchoice_it.json")
    if not mchoice_data:
        await message.answer("Ошибка загрузки данных упражнений с выбором")
        return

    await state.update_data(
        mchoice_exercises=mchoice_data,
        current_mchoice=0,
        mchoice_score=0
    )

    await message.answer(MESSAGES["mchoice_intro"])
    await show_mchoice_exercise(user_id, message, state, user_statistics, user_progress)


async def show_mchoice_exercise(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Показать упражнение с множественным выбором"""
    data = await state.get_data()
    exercises = data.get("mchoice_exercises", [])
    current_index = data.get("current_mchoice", 0)

    if current_index >= len(exercises):
        score = data.get("mchoice_score", 0)
        await message.answer(
            f"{MESSAGES['mchoice_complete']}\n\n"
            f"Ваш результат: {score}/{len(exercises)} ✨",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        user_statistics.update_block_score(user_id, CURRENT_LESSON_ID, "lexico_grammar", "mchoice", score, len(exercises))
        await state.set_state(LessonStates.MCHOICE_COMPLETE)
        return

    current_exercise = exercises[current_index]

    await message.answer(
        f"💻 **Выбери правильный вариант ({current_index + 1}/{len(exercises)}):**\n\n{current_exercise['sentence']}",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_mchoice_keyboard(current_exercise['options'], current_index))
    )

    await state.set_state(LessonStates.MCHOICE_EXERCISE)


@router.callback_query(F.data.startswith("mchoice_"), LessonStates.MCHOICE_EXERCISE)
async def process_mchoice_answer(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Обработка ответа на упражнение с множественным выбором"""
    user_id = callback.from_user.id
    data = await state.get_data()
    exercises = data.get("mchoice_exercises", [])
    current_index = data.get("current_mchoice", 0)
    score = data.get("mchoice_score", 0)

    if current_index >= len(exercises):
        return

    current_exercise = exercises[current_index]

    parts = callback.data.split("_")
    if len(parts) >= 4:
        selected_answer = parts[3]
    else:
        selected_answer = ""

    correct_answer = current_exercise["answer"]

    is_correct = (selected_answer == correct_answer) # Для статистики
    user_statistics.add_lexical_attempt(user_id, "mchoice", current_exercise["sentence"], is_correct, CURRENT_LESSON_ID, user_message=selected_answer) # Сохраняем попытку

    if is_correct:
        response_text = MESSAGES["correct_answer"]
        score += 1
        await state.update_data(mchoice_score=score)
    else:
        explanation = current_exercise.get('explanation', '')
        response_text = f"{MESSAGES['wrong_answer']}{correct_answer}\n\n💡 {explanation}" if explanation else f"{MESSAGES['wrong_answer']}{correct_answer}"

    await callback.message.edit_text(
        f"**Вопрос:** {current_exercise['sentence']}\n**Твой ответ:** {selected_answer}\n\n{response_text}",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_continue_keyboard())
    )

    await callback.answer()


@router.callback_query(F.data == "continue_exercise", LessonStates.MCHOICE_EXERCISE)
async def continue_mchoice_exercise_specific(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Продолжить упражнения с множественным выбором"""
    user_id = callback.from_user.id
    data = await state.get_data()
    current_index = data.get("current_mchoice", 0)
    await state.update_data(current_mchoice=current_index + 1)

    await show_mchoice_exercise(user_id, callback.message, state, user_statistics, user_progress)
    await callback.answer()


@router.callback_query(F.data == "next", LessonStates.MCHOICE_COMPLETE)
async def mchoice_complete_next(callback: CallbackQuery, state: FSMContext, user_progress: UserProgress, user_statistics: UserStatistics):
    user_id = callback.from_user.id
    await callback.message.edit_text("Отлично! Теперь попробуем строить отрицательные предложения.")

    user_statistics.mark_block_completed(user_id, CURRENT_LESSON_ID, "lexico_grammar", "mchoice") # Отмечаем подблок как завершенный
    user_progress.update_progress(user_id, current_block="lexico_grammar", current_item=2) # Переход к следующему подблоку

    await start_negative_exercise(user_id, callback.message, state, user_statistics, user_progress)
    await callback.answer()

async def start_negative_exercise(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
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

    await message.answer("✍️ **Инструкция:** Преобразуй предложение в отрицательную форму и отправь исправленный вариант.")

    await show_negative_exercise(user_id, message, state, user_statistics, user_progress)

async def show_negative_exercise(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    data = await state.get_data()
    exercises = data.get("negative_exercises", [])
    current_index = data.get("current_negative", 0)

    if current_index >= len(exercises):
        score = data.get("negative_score", 0)
        await message.answer(
            f"🎉 Вы успешно выполнили все упражнения!\nВаш результат: {score}/{len(exercises)} ✨",
            reply_markup=get_keyboard_with_menu(get_next_keyboard())
        )
        user_statistics.update_block_score(user_id, CURRENT_LESSON_ID, "lexico_grammar", "negative", score, len(exercises))
        await state.set_state(LessonStates.NEGATIVE_COMPLETE)
        return

    current_exercise = exercises[current_index]
    await message.answer(
        f"💻 **Упражнение {current_index + 1}/{len(exercises)}:**\n"
        f"{current_exercise['text']}",
        parse_mode="Markdown"
    )
    await state.set_state(LessonStates.NEGATIVE_EXERCISE)


@router.message(F.text, LessonStates.NEGATIVE_EXERCISE)
async def process_negative_answer(message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    user_id = message.from_user.id
    user_answer = message.text.strip().lower()
    data = await state.get_data()
    exercises = data.get("negative_exercises", [])
    current_index = data.get("current_negative", 0)
    score = data.get("negative_score", 0)

    if current_index >= len(exercises):
        return

    current_exercise = exercises[current_index]
    correct_answers = [ans.lower() for ans in current_exercise["answer"]]

    is_correct = any(user_answer == ans for ans in correct_answers) # Для статистики
    user_statistics.add_lexical_attempt(user_id, "negative", current_exercise["text"], is_correct, CURRENT_LESSON_ID, user_message=user_answer) # Сохраняем попытку

    if is_correct:
        response_text = "✅ Правильно!"
        score += 1
        await state.update_data(negative_score=score)
    else:
        examples = "\n".join([f"- {ans}" for ans in current_exercise["answer"]])
        response_text = f"❌ Неправильно.\nПравильные варианты:\n{examples}"

    await message.answer(f"{response_text}\n\nПереходим к следующему упражнению...")
    await state.update_data(current_negative=current_index + 1)
    await show_negative_exercise(user_id, message, state, user_statistics, user_progress)


@router.callback_query(F.data == "next", LessonStates.NEGATIVE_COMPLETE)
async def negative_complete_next(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    user_id = callback.from_user.id
    await callback.message.edit_text("Отлично! Переходим к следующему типу упражнений...")
    user_statistics.mark_block_completed(user_id, CURRENT_LESSON_ID, "lexico_grammar", "negative") # Отмечаем подблок как завершенный
    user_progress.update_progress(user_id, current_block="lexico_grammar", current_item=3) # Переход к следующему подблоку
    await start_question_exercise(user_id, callback.message, state, user_statistics, user_progress)
    await callback.answer()

async def start_question_exercise(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
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
        "❓ **Инструкция:** Преобразуй предложение в вопросительную форму и отправь исправленный вариант."
    )
    await show_question_exercise(user_id, message, state, user_statistics, user_progress)


async def show_question_exercise(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
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
        user_statistics.update_block_score(user_id, CURRENT_LESSON_ID, "lexico_grammar", "question", score, len(exercises))
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
async def process_question_answer(message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    user_id = message.from_user.id
    user_answer = message.text.strip().lower()
    data = await state.get_data()
    exercises = data.get("question_exercises", [])
    current_index = data.get("current_question", 0)
    score = data.get("question_score", 0)

    if current_index >= len(exercises):
        return

    current_exercise = exercises[current_index]
    correct_answer = current_exercise["answer"].lower()

    is_correct = (user_answer == correct_answer) # Для статистики
    user_statistics.add_lexical_attempt(user_id, "question", current_exercise["text"], is_correct, CURRENT_LESSON_ID, user_message=user_answer) # Сохраняем попытку

    if is_correct:
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
    await show_question_exercise(user_id, message, state, user_statistics, user_progress)

@router.callback_query(F.data == "next", LessonStates.QUESTION_COMPLETE)
async def question_complete_next(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    user_id = callback.from_user.id
    await callback.message.edit_text("Отлично! Идем дальше...")
    user_statistics.mark_block_completed(user_id, CURRENT_LESSON_ID, "lexico_grammar", "question") # Отмечаем подблок как завершенный
    user_progress.update_progress(user_id, current_block="lexico_grammar", current_item=4) # Переход к следующему подблоку
    await start_missing_word(user_id, callback.message, state, user_statistics, user_progress)
    await callback.answer()

async def start_missing_word(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
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
        "🔤 **Инструкция:** Вставь пропущенное слово в предложении и отправь свой вариант."
    )
    await show_missing_word_exercise(user_id, message, state, user_statistics, user_progress)


async def show_missing_word_exercise(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
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
        user_statistics.update_block_score(user_id, CURRENT_LESSON_ID, "lexico_grammar", "missing_word", score, len(exercises))
        await state.set_state(LessonStates.MISSING_WORD_COMPLETE)
        return

    current_exercise = exercises[current_index]

    escaped_statement = current_exercise["statement"].replace("_", r"\_")

    await message.answer(
        f"💻 **Упражнение {current_index + 1}/{len(exercises)}:**\n"
        f"{escaped_statement}",
        parse_mode="Markdown"
    )
    await state.set_state(LessonStates.MISSING_WORD_EXERCISE)


@router.message(F.text, LessonStates.MISSING_WORD_EXERCISE)
async def process_missing_word_answer(message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    user_id = message.from_user.id
    user_answer = message.text.strip().lower()
    data = await state.get_data()
    exercises = data.get("missing_words", [])
    current_index = data.get("current_missing", 0)
    score = data.get("missing_score", 0)

    if current_index >= len(exercises):
        return

    current_exercise = exercises[current_index]
    correct_answers = [ans.lower() for ans in current_exercise["answers"]]

    is_correct = (user_answer in correct_answers) # Для статистики
    user_statistics.add_lexical_attempt(user_id, "missing_word", current_exercise["statement"], is_correct, CURRENT_LESSON_ID, user_message=user_answer) # Сохраняем попытку

    if is_correct:
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
    await show_missing_word_exercise(user_id, message, state, user_statistics, user_progress)

@router.callback_query(F.data == "next", LessonStates.MISSING_WORD_COMPLETE)
async def missing_word_complete_next(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Завершение упражнения 'Пропущенное слово', переход к  аудированию"""
    user_id = callback.from_user.id
    await callback.message.edit_text("Отлично! Переходим к аудированию...")
    user_statistics.mark_block_completed(user_id, CURRENT_LESSON_ID, "lexico_grammar", "missing_word") # Отмечаем подблок как завершенный
    # Здесь можно также проверить, завершен ли весь блок "lexico_grammar"
    # user_statistics.mark_block_completed(user_id, CURRENT_LESSON_ID, "lexico_grammar", completed=True) # Если все подблоки завершены

    user_progress.update_progress(user_id, current_block="listening", current_item=0) # Переход к началу блока аудирования
    await start_listening_true_false(user_id, callback.message, state, user_statistics, user_progress)
    await callback.answer()



async def start_listening_true_false(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Начало упражнений True/False для аудирования"""
    listening_data = await load_json_data("listening_tasks_it.json")
    if not listening_data:
        await message.answer("Ошибка загрузки данных аудирования")
        return

    await state.update_data(
        listening_true_false=listening_data,
        current_listening_tf=0,
        listening_tf_score=0
    )

    await message.answer(MESSAGES["listening_true_false_intro"])
    # ИСПРАВЛЕНО: Передача user_id, user_statistics, user_progress в show_listening_true_false
    await show_listening_true_false(user_id, message, state, user_statistics, user_progress)


async def show_listening_true_false(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
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
        # ИСПРАВЛЕНО: Обновление статистики для подблока
        user_statistics.update_block_score(user_id, CURRENT_LESSON_ID, "listening", "true_false", score, len(exercises))
        # ИСПРАВЛЕНО: Отметка подблока как завершенного
        user_statistics.mark_block_completed(user_id, CURRENT_LESSON_ID, "listening", "true_false")
        # ИСПРАВЛЕНО: Проверка и отметка общего блока аудирования
        user_statistics._check_and_mark_lesson_completed(user_id, CURRENT_LESSON_ID)
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
            await message.answer_voice(
                audio,
                caption="🎧 **Прослушай фразу**",
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


@router.callback_query(
    F.data.in_(["listening_true", "listening_false"]),
    LessonStates.LISTENING_TRUE_FALSE
)
async def process_listening_true_false_answer(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics):
    """Обработка ответа True/False для аудирования"""
    user_id = callback.from_user.id
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

    is_correct = (selected_answer == correct_answer)
    # ИСПРАВЛЕНО: Запись статистики для True/False упражнения
    user_statistics.add_listening_attempt(
        user_id,
        "true_false",
        f"{current_exercise['phrase']} | {current_exercise['statement']}", # Уникальный ID для вопроса
        is_correct,
        CURRENT_LESSON_ID,
        user_message=selected_answer
    )

    # Проверяем ответ
    if is_correct:
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
async def continue_listening_tf_specific(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Продолжить True/False аудирование"""
    user_id = callback.from_user.id
    data = await state.get_data()
    current_index = data.get("current_listening_tf", 0)
    await state.update_data(current_listening_tf=current_index + 1)

    # ИСПРАВЛЕНО: Обновление прогресса пользователя
    user_progress.update_progress(user_id, current_item=current_index + 1)

    await show_listening_true_false(user_id, callback.message, state, user_statistics, user_progress)
    await callback.answer()


@router.callback_query(F.data == "next", LessonStates.LISTENING_TRUE_FALSE_COMPLETE)
async def listening_tf_complete_next(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Завершение True/False, переход к множественному выбору"""
    user_id = callback.from_user.id
    await callback.message.edit_text("Отлично! Переходим к следующему типу аудирования...")

    # ИСПРАВЛЕНО: Обновление прогресса для следующего подблока
    user_progress.update_progress(user_id, current_block="listening", current_item=0)
    await start_listening_choice(user_id, callback.message, state, user_statistics, user_progress)
    await callback.answer()

async def start_listening_choice(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
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
    # ИСПРАВЛЕНО: Передача user_id, user_statistics, user_progress в show_listening_choice
    await show_listening_choice(user_id, message, state, user_statistics, user_progress)


async def show_listening_choice(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
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
        # ИСПРАВЛЕНО: Обновление статистики для подблока
        user_statistics.update_block_score(user_id, CURRENT_LESSON_ID, "listening", "choice", score, len(exercises))
        # ИСПРАВЛЕНО: Отметка подблока как завершенного
        user_statistics.mark_block_completed(user_id, CURRENT_LESSON_ID, "listening", "choice")
        # ИСПРАВЛЕНО: Проверка и отметка общего блока аудирования
        user_statistics._check_and_mark_lesson_completed(user_id, CURRENT_LESSON_ID)
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
            await message.answer_voice(
                audio,
                caption="🎧 **Прослушай фразу 2 раза**",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Ошибка отправки аудио: {e}")
            await message.answer("🎧 **Аудио недоступно**")

    # Отправляем вопрос и варианты ответов
    await message.answer(
        f"❓ **{current_index + 1}/{len(exercises)}:**\n\n{current_exercise['question']}",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_listening_choice_keyboard(current_exercise['options'], current_index))
    )

    await state.set_state(LessonStates.LISTENING_CHOICE)


@router.callback_query(F.data == "listening_slow_down", LessonStates.LISTENING_TRUE_FALSE)
async def slow_down_true_false(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Обработка кнопки 'Сказать медленнее' для True/False"""
    user_id = callback.from_user.id
    data = await state.get_data()
    exercises = data.get("listening_true_false", [])
    current_index = data.get("current_listening_tf", 0)

    if current_index >= len(exercises):
        return

    current_exercise = exercises[current_index]

    # Генерируем замедленное аудио
    audio_filename = f"listening_tf_slow_{current_index}_{current_exercise['phrase'][:20].replace(' ', '_')}"
    audio_path = await generate_audio(current_exercise['phrase'], audio_filename, 'en', slow_mode=True)

    # Удаляем предыдущее сообщение с утверждением
    await callback.message.delete()

    # Отправляем замедленное аудио
    if audio_path and os.path.exists(audio_path):
        try:
            audio = FSInputFile(audio_path)
            await callback.message.answer_voice(
                audio,
                caption="🎧 **Прослушай фразу (медленно)**",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Ошибка отправки аудио: {e}")
            await callback.message.answer("🎧 **Аудио недоступно**")
    else:
        await callback.message.answer("🎧 **Аудио недоступно**")

    # Отправляем утверждение заново
    await callback.message.answer(
        f"📝 **Утверждение ({current_index + 1}/{len(exercises)}):**\n\n{current_exercise['statement']}",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_true_false_keyboard())
    )

    await callback.answer()

@router.callback_query(F.data == "listening_choice_slow_down", LessonStates.LISTENING_CHOICE)
async def slow_down_listening_choice(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
        """Обработка кнопки 'Сказать медленнее' для множественного выбора"""
        user_id = callback.from_user.id
        data = await state.get_data()
        exercises = data.get("listening_choice", [])
        current_index = data.get("current_listening_choice", 0)

        if current_index >= len(exercises):
            return

        current_exercise = exercises[current_index]

        # Удаляем все сообщения, связанные с текущим упражнением
        try:
            # Определяем количество сообщений для удаления (аудио + вопрос)
            messages_to_delete = 2

            # Удаляем последние messages_to_delete сообщений
            for i in range(messages_to_delete):
                await callback.message.bot.delete_message(
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id - i
                )
        except Exception as e:
            print(f"Ошибка при удалении сообщений: {e}")
            # Если не удалось удалить, просто продолжаем

        # Генерируем замедленное аудио
        audio_filename = f"listening_choice_slow_{current_index}_{current_exercise['phrase'][:20].replace(' ', '_')}"
        audio_path = await generate_audio(current_exercise['phrase'], audio_filename, 'en', slow_mode=True)

        # Отправляем замедленное аудио
        if audio_path and os.path.exists(audio_path):
            try:
                audio = FSInputFile(audio_path)
                audio_msg = await callback.message.answer_voice(
                    audio,
                    caption="🎧 **Прослушай фразу 2 раза (медленно)**",
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Ошибка отправки аудио: {e}")
                await callback.message.answer("🎧 **Аудио недоступно**")
        else:
            await callback.message.answer("🎧 **Аудио недоступно**")

        # Отправляем вопрос заново с теми же вариантами
        question_msg = await callback.message.answer(
            f"❓ **{current_index + 1}/{len(exercises)}:**\n\n{current_exercise['question']}",
            parse_mode="Markdown",
            reply_markup=get_keyboard_with_menu(
                get_listening_choice_keyboard(current_exercise['options'], current_index))
        )

        await callback.answer()


@router.callback_query(F.data == "listening_phrases_slow_down", LessonStates.LISTENING_PHRASES)
async def slow_down_listening_phrases(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Обработка кнопки 'Сказать медленнее' для повторения фраз"""
    user_id = callback.from_user.id
    data = await state.get_data()
    exercises = data.get("listening_phrases", [])
    current_index = data.get("current_listening_phrase", 0)

    if current_index >= len(exercises):
        return

    current_exercise = exercises[current_index]

    # Удаляем все сообщения, связанные с текущим упражнением
    try:
        # Определяем количество сообщений для удаления (аудио + инструкция)
        messages_to_delete = 2

        # Удаляем последние messages_to_delete сообщений
        for i in range(messages_to_delete):
            await callback.message.bot.delete_message(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id - i
            )
    except Exception as e:
        print(f"Ошибка при удалении сообщений: {e}")
        # Если не удалось удалить, просто продолжаем

    # Генерируем замедленное аудио
    audio_filename = f"listening_phrase_slow_{current_index}_{current_exercise['phrase'][:20].replace(' ', '_')}"
    audio_path = await generate_audio(current_exercise['phrase'], audio_filename, 'en', slow_mode=True)

    # Отправляем замедленное аудио
    if audio_path and os.path.exists(audio_path):
        try:
            audio = FSInputFile(audio_path)
            audio_msg = await callback.message.answer_voice(
                audio,
                caption="🎧 **Прослушай фразу 2 раза (медленно)**",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Ошибка отправки аудио: {e}")
            await callback.message.answer("🎧 **Аудио недоступно**")
    else:
        await callback.message.answer("🎧 **Аудио недоступно**")

    # Показываем транскрипцию и инструкцию заново
    await callback.message.answer(
        f"🔤 **Транскрипция ({current_index + 1}/{len(exercises)}):** {current_exercise.get('transcription', 'Недоступно')}\n\n"
        "Нажми кнопку 'Записать фразу' и Повтори фразу за спикером, отправив голосове сообщение:",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_listening_phrases_keyboard())
    )

    await callback.answer()

@router.callback_query(
    F.data.startswith("listening_choice_") & ~F.data.contains("slow_down"),
    LessonStates.LISTENING_CHOICE
)
async def process_listening_choice_answer(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics):
    """Обработка ответа множественного выбора для аудирования"""
    user_id = callback.from_user.id
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

    is_correct = (selected_answer == correct_answer)
    # ИСПРАВЛЕНО: Запись статистики для множественного выбора
    user_statistics.add_listening_attempt(
        user_id,
        "choice",
        f"{current_exercise['phrase']} | {current_exercise['question']}", # Уникальный ID для вопроса
        is_correct,
        CURRENT_LESSON_ID,
        user_message=selected_answer
    )

    # Проверяем ответ
    if is_correct:
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
async def continue_listening_choice_specific(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Продолжить множественный выбор аудирование"""
    user_id = callback.from_user.id
    data = await state.get_data()
    current_index = data.get("current_listening_choice", 0)
    await state.update_data(current_listening_choice=current_index + 1)

    # ИСПРАВЛЕНО: Обновление прогресса пользователя
    user_progress.update_progress(user_id, current_item=current_index + 1)

    await show_listening_choice(user_id, callback.message, state, user_statistics, user_progress)
    await callback.answer()


@router.callback_query(F.data == "next", LessonStates.LISTENING_CHOICE_COMPLETE)
async def listening_choice_complete_next(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Завершение множественного выбора, переход к повторению фраз"""
    user_id = callback.from_user.id
    await callback.message.edit_text("Отлично! Переходим к повторению фраз...")

    # ИСПРАВЛЕНО: Обновление прогресса для следующего подблока
    user_progress.update_progress(user_id, current_block="listening", current_item=0)
    await start_listening_phrases(user_id, callback.message, state, user_statistics, user_progress)
    await callback.answer()

async def start_listening_phrases(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
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
    # ИСПРАВЛЕНО: Передача user_id, user_statistics, user_progress в show_listening_phrase
    await show_listening_phrase(user_id, message, state, user_statistics, user_progress)


async def show_listening_phrase(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
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
        # ИСПРАВЛЕНО: Обновление статистики для подблока - используем реальные данные из попыток
        correct_count, total_count = user_statistics.get_listening_phrases_score(user_id, CURRENT_LESSON_ID)
        user_statistics.update_block_score(user_id, CURRENT_LESSON_ID, "listening", "phrases", correct_count, total_count)
        # ИСПРАВЛЕНО: Отметка подблока как завершенного
        user_statistics.mark_block_completed(user_id, CURRENT_LESSON_ID, "listening", "phrases")
        # ИСПРАВЛЕНО: Проверка и отметка общего блока аудирования
        user_statistics._check_and_mark_lesson_completed(user_id, CURRENT_LESSON_ID)
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
            await message.answer_voice(
                audio,
                caption="🎧 **Прослушай фразу 2 раза**",
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Ошибка отправки аудио: {e}")
            await message.answer("🎧 **Аудио недоступно**")

    # Показываем транскрипцию и инструкцию
    await message.answer(
        f"🔤 **Транскрипция ({current_index + 1}/{len(exercises)}):** {current_exercise.get('transcription', 'Недоступно')}\n\n"
        "Нажми кнопку 'Записать фразу' и Повтори фразу за спикером, отправив голосове сообщение:",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_listening_phrases_keyboard())
    )

    await state.set_state(LessonStates.LISTENING_PHRASES)


@router.callback_query(F.data == "record_phrase", LessonStates.LISTENING_PHRASES)
async def request_phrase_recording(callback: CallbackQuery, state: FSMContext):
    """Запрос записи произношения фразы"""
    await state.set_state(LessonStates.LISTENING_PHRASES_RECORD)
    await callback.answer()


@router.message(F.voice, LessonStates.LISTENING_PHRASES_RECORD)
async def process_phrase_recording(message: Message, state: FSMContext, user_statistics: UserStatistics):
    """Обработка записи произношения фразы в блоке аудирования"""
    user_id = message.from_user.id
    data = await state.get_data()
    exercises = data.get("listening_phrases", [])
    current_index = data.get("current_listening_phrase", 0)

    if current_index >= len(exercises):
        return

    current_exercise = exercises[current_index]
    text_to_check = current_exercise['phrase']

    # Определяем callback-функцию для обработки результатов
    async def handle_result(accuracy: float, verdict: str, analysis_text: str,
                            expected_phonemes: str, user_phonemes: str, word_results: List[Dict]):
        
        # Сохраняем детальные данные произношения фразы в блок listening_phrases
        # НЕ сохраняем в pronunciation, так как это отдельный блок

        # Логгируем результат
        log_user_result(
            user_id=str(message.from_user.id),
            result_type="phrase_pronunciation",
            result_data={
                "phrase": text_to_check,
                "accuracy": accuracy,
                "verdict": verdict,
                "passed": accuracy >= 68.0,
                "user_phonemes": user_phonemes
            }
        )

        full_response = f"{verdict}\n\n🎯 <b>Точность:</b> {accuracy:.1f}%"
        if analysis_text:
            full_response += analysis_text

        # Отправляем результат
        await message.answer(
            full_response,
            reply_markup=get_keyboard_with_menu(get_phrase_result_keyboard()),
            parse_mode='HTML'
        )

        # ИСПРАВЛЕНО: Запись статистики для произношения фраз
        user_statistics.add_listening_attempt(
            user_id,
            "phrases",
            text_to_check, # Уникальный ID для фразы
            accuracy >= 68.0, # is_correct
            CURRENT_LESSON_ID,
            score=accuracy, # Точность произношения
            user_message=f"Произношение с точностью {accuracy:.1f}%"
        )

        # Увеличиваем счет, если произношение удовлетворительное
        if accuracy >= 68.0:  # Или любой другой порог
            score = data.get("listening_phrases_score", 0)
            await state.update_data(listening_phrases_score=score + 1)

    # Используем общую функцию анализа
    await analyze_pronunciation(
        message=message,
        text_to_check=text_to_check,
        callback=handle_result,
        state=state
    )

    await state.set_state(LessonStates.LISTENING_PHRASES)


@router.callback_query(F.data == "skip_phrase", LessonStates.LISTENING_PHRASES)
@router.callback_query(F.data == "skip_phrase", LessonStates.LISTENING_PHRASES_RECORD)
@router.callback_query(F.data == "next_phrase")
async def next_listening_phrase(callback: CallbackQuery, state: FSMContext, user_progress: UserProgress, user_statistics: UserStatistics):
    """Переход к следующей фразе для повторения"""
    user_id = callback.from_user.id
    data = await state.get_data()
    current_index = data.get("current_listening_phrase", 0)

    # Проверяем, была ли уже записана попытка для текущей фразы
    exercises = data.get("listening_phrases", [])
    if current_index < len(exercises):
        current_exercise = exercises[current_index]
        current_phrase = current_exercise['phrase']
        
        # Проверяем, есть ли уже запись для этой фразы
        lesson_stats = user_statistics.get_lesson_stats(user_id, CURRENT_LESSON_ID)
        listening_phrases_data = lesson_stats.get("blocks", {}).get("listening_phrases", {})
        attempts = listening_phrases_data.get("attempts", [])
        
        # Ищем существующую запись для этой фразы
        existing_attempt = None
        for attempt in attempts:
            if attempt.get("item_id") == current_phrase:
                existing_attempt = attempt
                break
        
        # Если записи еще нет, значит фраза была пропущена
        if not existing_attempt:
            user_statistics.add_listening_attempt(
                user_id,
                "phrases",
                current_phrase, # Используем фразу как уникальный ID элемента
                False, # Неправильно, так как пропущено
                CURRENT_LESSON_ID,
                score=0.0, # Счет 0 для пропущенного задания
                user_message="Пропущено"
            )

    # Увеличиваем индекс
    await state.update_data(current_listening_phrase=current_index + 1)

    # Обновляем прогресс пользователя
    user_progress.update_progress(
        user_id,
        current_item=current_index + 1
    )

    # Показываем следующую фразу
    await show_listening_phrase(user_id, callback.message, state, user_statistics, user_progress)
    await callback.answer()


@router.callback_query(F.data == "retry_phrase")
async def retry_phrase(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Повторить попытку произношения фразы"""
    user_id = callback.from_user.id
    await callback.message.edit_text(
        "🎤 Попробуй ещё раз! Запиши голосовое сообщение с произношением фразы.",
        reply_markup=get_keyboard_with_menu(get_listening_phrases_keyboard())
    )

    await state.set_state(LessonStates.LISTENING_PHRASES_RECORD)
    await callback.answer()


@router.callback_query(F.data == "next", LessonStates.LISTENING_PHRASES_COMPLETE)
async def listening_phrases_complete_next(callback: CallbackQuery, state: FSMContext, user_progress: UserProgress, user_statistics: UserStatistics):
    """Завершение блока аудирования и переход к письму"""
    user_id = callback.from_user.id
    await callback.message.edit_text(
        "🎉 Блок аудирования завершен!\n\n"
        "Переходим к блоку письменной речи..."
    )
    # ИСПРАВЛЕНО: Обновление прогресса
    user_progress.update_progress(
        user_id,
        current_block="writing",
        current_item=0
    )
    # ИСПРАВЛЕНО: Отметка общего блока аудирования как завершенного
    user_statistics.mark_block_completed(user_id, CURRENT_LESSON_ID, "listening", completed=True)
    user_statistics._check_and_mark_lesson_completed(user_id, CURRENT_LESSON_ID)

    # Запускаем блок письма
    await start_writing_sentences(user_id, callback.message, state, user_statistics, user_progress)
    await callback.answer()

async def start_writing_sentences(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
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
    await show_writing_sentence_task(user_id, message, state, user_statistics, user_progress)

async def show_writing_sentence_task(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
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
        user_statistics.update_block_score(user_id, CURRENT_LESSON_ID, "writing", "sentences", completed, len(words))
        user_statistics.mark_block_completed(user_id, CURRENT_LESSON_ID, "writing", "sentences")
        await state.set_state(LessonStates.WRITING_SENTENCES_COMPLETE)
        return

    current_word = words[current_index]

    # Отправляем задание
    await message.answer(
        f"✍️ **{MESSAGES['writing_word_prompt']} ({current_index + 1}/{len(words)})**\n\n"
        f"**{current_word}**",
        # "Напиши предложение с этим словом и отправь его текстовым сообщением:",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_writing_skip_keyboard())
    )

    await state.set_state(LessonStates.WRITING_SENTENCES)

@router.message(F.text, LessonStates.WRITING_SENTENCES)
async def process_writing_sentence(message: Message, state: FSMContext, user_statistics: UserStatistics):
    """Обработка составленного предложения"""
    user_id = message.from_user.id
    user_sentence = message.text.strip()
    data = await state.get_data()
    current_word = data.get("writing_words", [])[data.get("current_writing_word", 0)]

    # Показываем, что проверяем
    checking_msg = await message.answer("🔄 Проверяю твое предложение...")

    try:
        # Проверяем с помощью AI
        feedback = await check_writing_with_ai(user_sentence, "sentence")
        is_correct = "✅" in feedback # Простая эвристика для определения корректности

        # Логгируем результат
        log_user_result(
            user_id=str(user_id),
            result_type="writing_sentence",
            result_data={
                "word": current_word,
                "user_input": user_sentence,
                "ai_feedback": feedback,
                "is_correct": is_correct
            }
        )
        user_statistics.add_writing_attempt(user_id, "sentences", current_word, is_correct, CURRENT_LESSON_ID, user_message=user_sentence)

        # Удаляем сообщение о проверке
        await checking_msg.delete()

        # Отправляем обратную связь
        await message.answer(
            f"**Твое предложение:** {user_sentence}\n\n{feedback}",
            parse_mode="Markdown",
            reply_markup=get_keyboard_with_menu(get_continue_writing_keyboard())
        )

        # Увеличиваем счетчик выполненных, если ответ правильный
        if is_correct:
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
async def continue_writing_sentences(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Продолжить упражнения на составление предложений"""
    user_id = callback.from_user.id
    data = await state.get_data()
    current_index = data.get("current_writing_word", 0)
    words = data.get("writing_words", [])

    if callback.data == "skip_writing" and current_index < len(words):
        current_word = words[current_index]
        user_statistics.add_writing_attempt(user_id, "sentences", current_word, False, CURRENT_LESSON_ID, user_message="Пропущено") # Пропущено = неверно

    await state.update_data(current_writing_word=current_index + 1)
    user_progress.update_progress(user_id, current_item=current_index + 1)

    await show_writing_sentence_task(user_id, callback.message, state, user_statistics, user_progress)
    await callback.answer()


@router.callback_query(F.data == "next", LessonStates.WRITING_SENTENCES_COMPLETE)
async def writing_sentences_complete_next(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Завершение составления предложений, переход к переводу"""
    user_id = callback.from_user.id
    await callback.message.edit_text("Отлично! Теперь попробуем перевести предложения...")
    user_statistics.mark_block_completed(user_id, CURRENT_LESSON_ID, "writing", "sentences")
    user_progress.update_progress(user_id, current_block="writing", current_item=1) # Обновляем прогресс

    await start_writing_translation(user_id, callback.message, state, user_statistics, user_progress)
    await callback.answer()


async def start_writing_translation(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
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
    await show_writing_translation_task(user_id, message, state, user_statistics, user_progress)


async def show_writing_translation_task(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
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
        user_statistics.update_block_score(user_id, CURRENT_LESSON_ID, "writing", "translation", completed, len(phrases))
        user_statistics.mark_block_completed(user_id, CURRENT_LESSON_ID, "writing", "translation")
        await state.set_state(LessonStates.WRITING_TRANSLATION_COMPLETE)
        return

    current_phrase = phrases[current_index]

    await state.update_data(current_translation_phrase=current_phrase)

    # Отправляем задание
    await message.answer(
        f"🌐 **{MESSAGES['writing_translate_prompt']} ({current_index + 1}/{len(phrases)})**\n\n"
        f"**{current_phrase}**\n\n"
        "Напиши перевод на английский и отправь текстовым сообщением:",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_writing_skip_keyboard())
    )

    await state.set_state(LessonStates.WRITING_TRANSLATION)


@router.message(F.text, LessonStates.WRITING_TRANSLATION)
async def process_writing_translation(message: Message, state: FSMContext, user_statistics: UserStatistics):
    """Обработка перевода предложения"""
    user_id = message.from_user.id
    user_translation = message.text.strip()

    # Показываем, что проверяем
    checking_msg = await message.answer("🔄 Проверяю ваш перевод...")

    try:
        # Получаем исходную фразу
        data = await state.get_data()
        original_phrase = data.get("current_translation_phrase", "")

        # Передаем исходную фразу в функцию
        feedback = await check_writing_with_ai(user_translation, "translation", original_phrase)
        is_correct = "✅" in feedback # Простая эвристика для определения корректности

        # Логгируем результат
        log_user_result(
            user_id=str(user_id),
            result_type="writing_translation",
            result_data={
                "original_phrase": original_phrase,
                "user_translation": user_translation,
                "ai_feedback": feedback,
                "is_correct": is_correct
            }
        )
        user_statistics.add_writing_attempt(user_id, "translation", original_phrase, is_correct, CURRENT_LESSON_ID, user_message=user_translation)

        # Удаляем сообщение о проверке
        await checking_msg.delete()

        # В ответе показать обе фразы
        await message.answer(
            f"**Исходная фраза:** {original_phrase}\n"
            f"**Ваш перевод:** {user_translation}\n\n{feedback}",
            parse_mode="Markdown",
            reply_markup=get_keyboard_with_menu(get_continue_writing_keyboard())
        )

        # Увеличиваем счетчик выполненных, если ответ правильный
        if is_correct:
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
async def continue_writing_translation(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Продолжить упражнения на перевод"""
    user_id = callback.from_user.id
    data = await state.get_data()
    current_index = data.get("current_translation", 0)
    phrases = data.get("translation_phrases", [])

    if callback.data == "skip_writing" and current_index < len(phrases):
        original_phrase = phrases[current_index]
        user_statistics.add_writing_attempt(user_id, "translation", original_phrase, False, CURRENT_LESSON_ID, user_message="Пропущено") # Пропущено = неверно

    await state.update_data(current_translation=current_index + 1)
    user_progress.update_progress(user_id, current_item=current_index + 1)

    await show_writing_translation_task(user_id, callback.message, state, user_statistics, user_progress)
    await callback.answer()

# Обновить завершение блока письма:
@router.callback_query(F.data == "next", LessonStates.WRITING_TRANSLATION_COMPLETE)
async def writing_translation_complete_next(callback: CallbackQuery, state: FSMContext, user_progress: UserProgress, user_statistics: UserStatistics):
    """Завершение блока письменной речи и переход к говорению"""
    user_id = callback.from_user.id
    await callback.message.edit_text(
        "🎉 Блок письменной речи завершен!\n\n"
        "Переходим к финальному блоку - говорение..."
    )
    user_statistics.mark_block_completed(user_id, CURRENT_LESSON_ID, "writing", completed=True) # Отмечаем общий блок письма
    user_statistics._check_and_mark_lesson_completed(user_id, CURRENT_LESSON_ID) # Проверяем завершение урока

    # Обновляем прогресс
    user_progress.update_progress(
        user_id,
        current_block="speaking",
        current_item=0
    )

    # Запускаем блок говорения
    await start_speaking_block(user_id, callback.message, state, user_statistics, user_progress)
    await callback.answer()


async def start_speaking_block(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
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
    await show_speaking_topic(user_id, message, state, user_statistics, user_progress)


async def show_speaking_topic(user_id: int, message: Message, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Показать тему для говорения"""
    data = await state.get_data()
    topics = data.get("speaking_topics", [])
    current_index = data.get("current_speaking_topic", 0)

    if current_index >= len(topics):
        # Все темы пройдены - курс завершен!
        # ИСПРАВЛЕНО: Получаем актуальный счет из статистики
        correctly_completed_topics_count, total_topics_count = user_statistics.get_speaking_block_score(user_id, "topics", CURRENT_LESSON_ID)

        await message.answer(
            f"{MESSAGES['speaking_complete']}\n\n"
            f"Тем обсуждено: {total_topics_count}/{total_topics_count} 🎯\n\n" # ИСПРАВЛЕНО: Используем total_topics_count для отображения
            f"{MESSAGES['speaking_final']}",
            reply_markup=get_keyboard_with_menu(get_final_keyboard())
        )
        # ИСПРАВЛЕНО: Обновляем статистику для общего блока "speaking" с использованием correctly_completed_topics_count
        user_statistics.update_block_score(user_id, CURRENT_LESSON_ID, "speaking", "topics", correctly_completed_topics_count, total_topics_count)
        user_statistics.mark_block_completed(user_id, CURRENT_LESSON_ID, "speaking", completed=True) # Помечаем родительский блок как завершенный
        user_statistics._check_and_mark_lesson_completed(user_id, CURRENT_LESSON_ID)
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
    await callback.message.answer(
        "🎤 **Запиши голосовое сообщение со своми мыслыми по теме.**\n\n"
        "💡 Говори свободно на английском языке. Можешь рассказать о своем опыте, "
        "привести примеры из работы или поделиться мнением.\n\n"
        "Для записи нажми на микрофон в нижнем правом углу  в Telegram и начни говорить.",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_speaking_keyboard())
    )

    await state.set_state(LessonStates.SPEAKING_RECORD)
    await callback.answer()


@router.message(F.voice, LessonStates.SPEAKING_RECORD)
async def process_speaking_recording(message: Message, state: FSMContext, user_statistics: UserStatistics):
    """Обработка записи говорения"""
    user_id = message.from_user.id
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
        # Простая эвристика для определения корректности (например, если AI дал положительный отзыв)
        is_correct = "✅" in analysis or "хорошо" in analysis.lower() or "отлично" in analysis.lower()

        # Создаем уникальный ID диалога для группировки сообщений
        dialogue_id = f"speaking_{user_id}_{current_index}"
        
        # Сохраняем диалог говорения
        user_statistics.save_speaking_dialogue(
            user_id=user_id,
            user_message=transcribed_text,
            gpt_response=analysis,
            topic=current_topic,
            dialogue_id=dialogue_id
        )

        # Логгируем результат
        log_user_result(
            user_id=str(user_id),
            result_type="speaking_exercise",
            result_data={
                "topic": current_topic,
                "user_speech": transcribed_text,
                "ai_analysis": analysis,
                "is_correct": is_correct
            }
        )
        user_statistics.add_speaking_attempt(user_id, "topics", current_topic, is_correct, CURRENT_LESSON_ID)

        # Удаляем временный файл
        if os.path.exists(voice_path):
            os.remove(voice_path)

        # Удаляем сообщение об анализе
        await analyzing_msg.delete()

        # Отправляем анализ
        await message.answer(
            f"**Твоя тема:** {current_topic}\n\n"
            f"**Твое высказывание** {transcribed_text}\n\n"
            f"{analysis}",
            parse_mode="Markdown",
            reply_markup=get_keyboard_with_menu(get_speaking_result_keyboard())
)

        # Увеличиваем счетчик выполненных, если ответ правильный
        if is_correct:
            completed = data.get("speaking_complete_count", 0)
            await state.update_data(speaking_complete_count=completed + 1)

    except Exception as e:
        await analyzing_msg.delete()
        await message.answer(
            "Произошла ошибка при анализе высказывания.",
            reply_markup=get_keyboard_with_menu(get_speaking_result_keyboard())
        )
        print(f"Ошибка анализа речи: {e}")


@router.callback_query(F.data == "skip_speaking", LessonStates.SPEAKING)
@router.callback_query(F.data == "skip_speaking", LessonStates.SPEAKING_RECORD)
@router.callback_query(F.data == "next_speaking")
async def next_speaking_topic(callback: CallbackQuery, state: FSMContext, user_progress: UserProgress, user_statistics: UserStatistics):
    """Переход к следующей теме для говорения"""
    user_id = callback.from_user.id
    data = await state.get_data()
    current_index = data.get("current_speaking_topic", 0)
    topics = data.get("speaking_topics", [])

    if callback.data == "skip_speaking" and current_index < len(topics):
        current_topic = topics[current_index]
        user_statistics.add_speaking_attempt(user_id, "topics", current_topic, False, CURRENT_LESSON_ID) # Пропущено = неверно

    # Увеличиваем индекс
    await state.update_data(current_speaking_topic=current_index + 1)

    # Обновляем прогресс пользователя
    user_progress.update_progress(
        user_id,
        current_item=current_index + 1
    )

    # Показываем следующую тему
    await show_speaking_topic(user_id, callback.message, state, user_statistics, user_progress)
    await callback.answer()


@router.callback_query(F.data == "retry_speaking")
async def retry_speaking(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Повторить запись по той же теме"""
    user_id = callback.from_user.id
    await callback.message.edit_text(
        "🎤 Попробуй ещё раз! Запиши голосовое сообщение с вашими мыслями по теме.",
        reply_markup=get_keyboard_with_menu(get_speaking_keyboard())
    )

    await state.set_state(LessonStates.SPEAKING_RECORD)
    await callback.answer()
# Финальные обработчики завершения курса
@router.callback_query(F.data == "main_menu", LessonStates.SPEAKING_COMPLETE)
@router.callback_query(F.data == "restart_lesson", LessonStates.SPEAKING_COMPLETE)
async def course_complete_actions(callback: CallbackQuery, state: FSMContext, user_progress: UserProgress):
    """Действия после завершения полного курса"""
    if callback.data == "restart_lesson":
        # Сбрасываем прогресс для нового прохождения
        await state.clear()
        user_progress.reset_progress(callback.from_user.id)

        await callback.message.edit_text(
            "🔄 Курс перезапущен! Есть желание пройти его заново?\n\n"
            "Это отличная практика для закрепления знаний!",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        # Возврат в главное меню
        await callback.message.edit_text(
            "🏠 **Добро пожаловать обратно в главное меню!**\n\n"
            "ты можешь повторить любой блок или пройти весь курс заново.",
            parse_mode="Markdown",
            reply_markup=get_main_menu_keyboard()
        )

    await callback.answer()


# Обработчик завершения всего курса
@router.callback_query(F.data == "next", LessonStates.SPEAKING_COMPLETE)
async def final_course_completion(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics):
    """Финальное завершение курса"""
    user_id = callback.from_user.id
    await callback.message.edit_text(
        "🎓 **ПОЗДРАВЛЯЕМ С ЗАВЕРШЕНИЕМ КУРСА!** 🎓\n\n"
        "Все 8 блоков английского языка для программистов пройдены:\n"
        "✅ Изучение терминов\n"
        "✅ Произношение\n"
        "✅ Лексические упражнения\n"
        "✅ Грамматика с AI-учителем\n"
        "✅ Практические упражнения\n"
        "✅ Аудирование\n"
        "✅ Письменная речь\n"
        "✅ Говорение\n\n"
        "🚀 Теперь можешь увереннее общаться на английском в IT среде!",
        parse_mode="Markdown",
        reply_markup=get_keyboard_with_menu(get_final_keyboard())
    )
    user_statistics.mark_lesson_completed(user_id, CURRENT_LESSON_ID) # Отмечаем весь урок как завершенный
    await state.set_state(LessonStates.LESSON_COMPLETE)
    await callback.answer()

@router.callback_query(F.data == "continue_exercise")
async def continue_exercise_handler(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress):
    """Универсальный обработчик продолжения упражнений - fallback"""
    current_state = await state.get_state()
    user_id = callback.from_user.id
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
            await show_lexical_en_question(user_id, callback.message, state, user_statistics, user_progress)
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
            await show_lexical_ru_question(callback.message, state, user_statistics, user_progress)
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
        "Попробуй использовать меню для навигации.",
        reply_markup=get_keyboard_with_menu(get_main_menu_keyboard())
    )
    await callback.answer()


# Обработчики для специфичных типов продолжения лексических упражнений
@router.callback_query(F.data == "continue_exercise")
async def continue_lexical_exercise_fallback(callback: CallbackQuery, state: FSMContext, user_statistics: UserStatistics, user_progress: UserProgress ):
    """Fallback обработчик для лексических упражнений"""
    current_state = await state.get_state()
    user_id = callback.from_user.id
    print(f"[DEBUG] FALLBACK сработал для состояния: {current_state}")

    if current_state == LessonStates.LEXICAL_EN_TO_RU:
        print("[DEBUG] Обрабатываем EN->RU в fallback")

        # Переходим к следующему вопросу английский -> русский
        data = await state.get_data()
        current_index = data.get("current_lexical_en", 0)
        await state.update_data(current_lexical_en=current_index + 1)

        await show_lexical_en_question(user_id, callback.message, state, user_statistics, user_progress)

    elif current_state == LessonStates.LEXICAL_RU_TO_EN:
        # Переходим к следующему вопросу русский -> английский
        data = await state.get_data()
        current_index = data.get("current_lexical_ru", 0)
        await state.update_data(current_lexical_ru=current_index + 1)

        await show_lexical_ru_question(callback.message, state, user_statistics, user_progress)

    else:
        # Если состояние не подходит
        await callback.message.edit_text(
            "⚠️ Неожиданное состояние в лексических упражнениях.\n\n"
            "Воспользуйся меню для навигации.",
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
            "Воспользуйся меню для навигации по урокам.",
            reply_markup=get_keyboard_with_menu(get_main_menu_keyboard())
        )
        await callback.answer()
        return

    # Логируем для отладки
    print(f"Необработанный lexical callback: {callback.data} в состоянии {current_state}")
    await callback.answer("Нажми кнопку еще раз")


@router.callback_query(F.data.startswith("mchoice_"))
async def handle_mchoice_fallback(callback: CallbackQuery, state: FSMContext):
    """Fallback обработчик для mchoice callback'ов"""
    current_state = await state.get_state()

    # Если callback пришел, но состояние неподходящее
    if current_state not in [LessonStates.MCHOICE_EXERCISE, LessonStates.LISTENING_CHOICE]:
        await callback.message.edit_text(
            "⚠️ Это упражнение уже завершено или недоступно.\n\n"
            "Воспользуйся меню для навигации по урокам.",
            reply_markup=get_keyboard_with_menu(get_main_menu_keyboard())
        )
        await callback.answer()
        return

    # Логируем для отладки
    print(f"Необработанный mchoice callback: {callback.data} в состоянии {current_state}")
    await callback.answer("Нажми кнопку еще раз")


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
    await callback.answer("Нажми кнопку еще раз")


# Fallback обработчик для всех неопознанных callback'ов
@router.callback_query()
async def handle_unknown_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик для всех неопознанных callback'ов"""
    print(f"Неопознанный callback: {callback.data}")

    # Просто подтверждаем callback без действий
    await callback.answer("Команда не распознана. Используй доступные кнопки.")


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
            "Используй кнопки для навигации или вернись в главное меню.",
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
            "Дождись соответствующего упражнения или вернись в главное меню.",
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
        "Используй доступные кнопки для навигации.",
        reply_markup=get_keyboard_with_menu(get_main_menu_keyboard())
    )

@router.callback_query()
async def debug_all_callback_queries(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    # Используем sys.stderr.write для гарантированного вывода в консоль
    sys.stderr.write(f"--- DEBUG (Fallback Callback Handler): Неопознанный callback_data='{callback.data}' в состоянии '{current_state}' для пользователя {callback.from_user.id} ---\n")
    sys.stderr.flush() # Убедиться, что запись происходит немедленно
    await callback.answer() # Обязательно отвечаем на callback

