import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN")

# OpenAI API Key для агента-учителя (опционально)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Paths
#DATA_PATH = "data/"
#MEDIA_PATH = "media/"
#AUDIO_PATH = "media/audio/"
#IMAGES_PATH = "media/images/"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, 'data')
MEDIA_PATH = os.path.join(BASE_DIR, 'media') # Ошибка: MEDIA_PATH уже определен как os.path.join(BASE_DIR, 'media')
AUDIO_PATH = os.path.join(MEDIA_PATH, 'audio')
IMAGES_PATH = os.path.join(MEDIA_PATH, 'images')

CURRENT_LESSON_ID = "introduction_to_it_english"

os.makedirs(DATA_PATH, exist_ok=True)
os.makedirs(AUDIO_PATH, exist_ok=True)
os.makedirs(IMAGES_PATH, exist_ok=True)
# Messages
MESSAGES = {
    "welcome": "Привет! Давай изучать английский язык! 🇬🇧",
    "start_lesson": "Начинаем урок! 📚",
    "terms_intro": "Давай изучим следующие термины!\n\nЯ буду отправлять тебе термин на английском, картинку, транскрипцию и голосовое сообщение с произношением.\nИспользуй кнопку ниже для навигации.",
    "terms_complete": "Ты молодец! Все термины изучены! Двигаемся дальше!",
    "pronunciation_intro": "Я буду тебе произносить слово, а твоя задача постараться повторить за мной. Если никак не получается, просто жми кнопку 'Пропустить'. Если диктор говорит слишком быстро для тебя, используй кнопку 'Сказать медленнее'",
    "pronunciation_complete": "Супер, ты справился с произношением! Давай теперь запомним значения слов",
    "pronunciation_correct": "Слово произнесено верно! 👍",
    "pronunciation_incorrect": "Я не смог различить, попробуй ещё раз 🤔",
    "pronunciation_instruction": "Теперь жми кнопку 'Записать произношение'",
    "lexical_intro": "Выбери корректный перевод слова",
    "lexical_en_ru_complete": "Каждое новое слово — шаг вперёд! Теперь немного изменим задачу",
    "lexical_ru_en_complete": "Главное — прогресс, а не совершенство. Ты растёшь!",
    "grammar_intro": "А теперь самое время познакомиться с грамматикой",
    "grammar_understood": "Всё понятно ✅",
    "grammar_questions": "Есть вопросики ❓",
    "grammar_ask_question": "Задай свой вопрос по грамматике, отправив текстовое сообщение:",
    "grammar_now_understood": "Теперь всё понятно ✅",
    "grammar_still_questions": "Остались вопросы ❓",
    "grammar_complete": "Отлично! Грамматический блок пройден 📚",
    "teacher_thinking": "🤔 Подумаю над твоим вопросом...",
    # Лексико-грамматические упражнения
    "verb_exercise_intro": "Напечатай пропущенный глагол в нужной временной форме",
    "verb_exercise_complete": "🚀 С каждым шагом ты становишься увереннее — продолжай!",
    "mchoice_intro": "Выберите правильный вариант ответа",
    "mchoice_complete": "Ещё одно упражнение — и ты ближе к цели!",
    "missing_word_intro": "Вставь подходящее по смыслу пропущенное слово. Отправь текстовое сообщение",
    "missing_word_complete": "Английский открывает двери — и ты их уже делаешь!",
    "negative_intro": "Переделай предложение в отрицательную форму. Отправь текстовое сообщение",
    "negative_complete": "Твой мозг обожает такую тренировку!",
    "question_intro": "Переделай предложение в вопросительную форму. Отправь текстовое сообщение. Не забывай ставить ? в конце предложения",
    "question_complete": "Маленькие шаги приводят к большим результатам!",
    # Блок аудирования
    "listening_true_false_intro": "Прослушай голосовое сообщение столько раз, сколько тебе нужно для его понимания. Выбери корректный вариант ответа True «верно» или False «неверно»",
    "listening_choice_intro": "Прослушай голосовое сообщение 2 раза. Выбери корректный вариант ответа",
    "listening_phrases_intro": "Прослушай голосовое сообщение 2 раза, повтори фразу за спикером. Для продолжения, или если никак не получается, смело жми клавишу 'Дальше'",
    "listening_true_false_complete": "Еще один этап пройден! Продолжим в том же духе!",
    "listening_choice_complete": "Я знаю, что это было не так просто, но это часть пути",
    "listening_phrases_complete": "Сложные задачи делают тебя сильнее — и ты только что стал сильнее",
    "listening_correct": "Фраза произнесена верно! 👍",
    "listening_incorrect": "Я не смог различить, попробуй ещё раз 🤔",
    "true_answer": "Верно",
    "false_answer": "Неверно",
    # Блок письменной речи
    "writing_sentences_intro": "Составь предложение с предлагаемым словом и напиши его, отправив текстовое сообщение",
    "writing_translation_intro": "Напиши перевод предложения на английский язык",
    "writing_sentences_complete": "Отлично! Переходим к переводу предложений",
    "writing_translation_complete": "🎉 Блок письменной речи завершен!",
    "writing_word_prompt": "Составь предложение со словом:",
    "writing_translate_prompt": "Переведи на английский:",
    "continue_writing": "Продолжить урок",
    # Блок говорения
    "speaking_intro": "Подумай над предложенной ситуацией и запиши голосовое сообщение с твоими размышлениями. \n📌 Длина — любая, столько, сколько сможешь сказать.\n Нажми кнопку «Записать мысли» и начни говорить",
    "speaking_situation": "Ситуация для обсуждения:",
    "speaking_instruction": "Запиши голосовое сообщение с твоими мыслями по этой теме:",
    "speaking_analyzing": "🔄 Анализирую твое высказывание...",
    "speaking_complete": "🎉 Поздравляем! Урок завершен!",
    "speaking_final": "Мозг, конечно, подпотел... но даже английский немного в шоке. Переходим к следующему уроку?",
    "record_speaking": "Записать мысли 🎤",
    "correct_answer": "✅ Правильно!",
    "wrong_answer": "❌ Упс, ошибка! Правильный ответ: ",
    "next_button": "Дальше ➡️",
    "skip_button": "Пропустить ⏭️"
}




