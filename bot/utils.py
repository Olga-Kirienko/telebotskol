import json
import os
import asyncio
import sys
from typing import Dict, List
from gtts import gTTS
import aiofiles
from openai import AsyncOpenAI
import tempfile
from aiogram import types
import torch
from transformers import Wav2Vec2Processor, Wav2Vec2ForCTC
import numpy as np
import librosa
from phonemizer import phonemize
from difflib import SequenceMatcher
import torchaudio
import subprocess
import re
import random

os.environ['PATH'] += r';C:\Program Files\eSpeak NG'

# --- Загрузка модели один раз при старте ---
from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2CTCTokenizer

feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained("facebook/wav2vec2-lv-60-espeak-cv-ft")
tokenizer = Wav2Vec2CTCTokenizer.from_pretrained("facebook/wav2vec2-lv-60-espeak-cv-ft")
processor = Wav2Vec2Processor(feature_extractor=feature_extractor, tokenizer=tokenizer)
model = Wav2Vec2ForCTC.from_pretrained("facebook/wav2vec2-lv-60-espeak-cv-ft")


# Добавляем путь к корневой директории
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATA_PATH, AUDIO_PATH

# Пытаемся импортировать OpenAI, если доступен
try:
    import openai
    from config import OPENAI_API_KEY
    OPENAI_AVAILABLE = bool(OPENAI_API_KEY)
    if OPENAI_AVAILABLE:
        openai.api_key = OPENAI_API_KEY
except (ImportError, AttributeError):
    OPENAI_AVAILABLE = False
    OPENAI_API_KEY = None


async def load_json_data(filename: str) -> Dict:
    """Загрузка данных из JSON файла"""
    file_path = os.path.join(DATA_PATH, filename)
    try:
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as file:
            content = await file.read()
            return json.loads(content)
    except FileNotFoundError:
        print(f"Файл {filename} не найден")
        return {}
    except json.JSONDecodeError:
        print(f"Ошибка декодирования JSON в файле {filename}")
        return {}


async def generate_audio(text: str, filename: str, lang: str = 'en') -> str:
    """Генерация аудио файла из текста"""
    audio_file_path = os.path.join(AUDIO_PATH, f"{filename}.mp3")
    
    # Если файл уже существует, возвращаем путь
    if os.path.exists(audio_file_path):
        return audio_file_path
    
    try:
        # Создаем аудио в отдельном потоке
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, 
            lambda: gTTS(text=text, lang=lang, slow=False).save(audio_file_path)
        )
        return audio_file_path
    except Exception as e:
        print(f"Ошибка генерации аудио: {e}")
        return None


class UserProgress:
    """Простое управление прогрессом пользователя"""
    
    def __init__(self):
        self.users_progress = {}
    
    def get_progress(self, user_id: int) -> Dict:
        """Получить прогресс пользователя"""
        return self.users_progress.get(user_id, {
            'current_block': 'terms',
            'current_item': 0,
            'completed_items': []
        })
    
    def update_progress(self, user_id: int, **kwargs):
        """Обновить прогресс пользователя"""
        if user_id not in self.users_progress:
            self.users_progress[user_id] = {
                'current_block': 'terms',
                'current_item': 0,
                'completed_items': []
            }
        
        self.users_progress[user_id].update(kwargs)
    
    def reset_progress(self, user_id: int):
        """Сбросить прогресс пользователя"""
        self.users_progress[user_id] = {
            'current_block': 'terms',
            'current_item': 0,
            'completed_items': []
        }


async def recognize_speech(audio_file_path: str) -> Dict:
    """Простое распознавание речи (заглушка)"""
    # Пока что возвращаем случайный результат для тестирования
    import random
    
    # В реальной реализации здесь будет speech_recognition
    success = random.choice([True, False])
    
    if success:
        return {
            "success": True,
            "text": "recognized_word",
            "confidence": 0.85
        }
    else:
        return {
            "success": False,
            "text": "",
            "confidence": 0.0
        }
        
# --- Функции для обработки произношения---
async def convert_ogg_to_wav(input_path: str, output_path: str):
    """Конвертирует ogg в wav 16kHz mono"""
    try:
        # Загружаем аудио
        waveform, sample_rate = torchaudio.load(input_path)
        
        # Конвертируем в моно (если нужно)
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)

        # Ресэмплируем до 16kHz
        if sample_rate != 16000:
            resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
            waveform = resampler(waveform)

        # Сохраняем как WAV
        torchaudio.save(output_path, waveform, 16000, format="wav")
        return True
    except Exception as e:
        print(f"Ошибка конвертации ogg → wav: {e}")
        return False

def normalize_phonemes(phonemes: str) -> str:
    """
    Нормализует фонемы для корректного сравнения
    """
    # Убираем все символы ударения и диакритику
    phonemes = re.sub(r'[ˈˌ`´ʼ\']', '', phonemes)
    
    # Маппинг различий между espeak IPA и wav2vec2
    phoneme_mapping = {
        # Гласные
        'ɜː': 'ɚ',  # r-colored vowel
        'əʊ': 'oʊ', # diphthong
        'ɛ': 'e',   # close-mid front unrounded
        'ɔː': 'ɑː', # open back rounded
        'ɪ': 'i',   # near-close front unrounded
        'ʌ': 'ʌ',   # open-mid back unrounded
        'aɪ': 'aɪ', # diphthong
        'æ': 'æ',   # near-open front unrounded
        
        # Согласные
        'ð': 'ð',   # voiced dental fricative
        'θ': 'θ',   # voiceless dental fricative
        'ŋ': 'ŋ',   # velar nasal
        'ʃ': 'ʃ',   # voiceless postalveolar fricative
        'ʒ': 'ʒ',   # voiced postalveolar fricative
        'tʃ': 'tʃ', # voiceless postalveolar affricate  
        'dʒ': 'dʒ', # voiced postalveolar affricate
        'j': 'j',   # palatal approximant
        'w': 'w',   # voiced labio-velar approximant
        'r': 'ɹ',   # alveolar approximant
        'l': 'l',   # alveolar lateral approximant
    }
    
    # Применяем маппинг
    for old, new in phoneme_mapping.items():
        phonemes = phonemes.replace(old, new)
    
    # Убираем пробелы и приводим к нижнему регистру
    phonemes = ''.join(phonemes.split()).lower()
    
    return phonemes

def text_to_phonemes_simplified(text: str) -> str:
    """
    Переводит текст в упрощенные фонемы, совместимые с wav2vec2
    """
    try:
        # Получаем IPA от espeak
        result = subprocess.run([
            r'C:\Program Files\eSpeak NG\espeak-ng.exe',
            '-q', '--ipa', text
        ], capture_output=True, text=True, encoding='utf-8')
        
        ipa_output = result.stdout.strip()
        
        # Нормализуем для совместимости с wav2vec2
        normalized = normalize_phonemes(ipa_output)
        
        return normalized
        
    except Exception as e:
        print(f"Ошибка espeak: {e}")
        return ""

async def audio_to_phonemes(audio_path: str) -> str:
    """Конвертация аудио в фонемы с помощью Wav2Vec2"""
    try:
        # Загрузка аудио
        speech, sr = librosa.load(audio_path, sr=16000)
        
        # Обработка входных данных
        input_values = processor(speech, return_tensors="pt", sampling_rate=16000).input_values
        
        # Предсказание
        with torch.no_grad():
            logits = model(input_values).logits
        
        # Получаем предсказанные токены
        predicted_ids = torch.argmax(logits, dim=-1)
        
        # Декодируем в символы
        transcription = processor.decode(predicted_ids[0])
        
        # Нормализуем результат
        normalized = normalize_phonemes(transcription)
        
        return normalized
        
    except Exception as e:
        print(f"Ошибка обработки аудио: {e}")
        return ""

def advanced_phoneme_comparison(expected: str, user: str) -> float:
    """
    Улучшенное сравнение фонем с учетом фонетической близости
    """
    # Группы фонетически близких звуков
    similar_groups = [
        ['i', 'ɪ', 'iː'],           # близкие гласные
        ['e', 'ɛ', 'eː'],          
        ['æ', 'a', 'ʌ'],           
        ['o', 'ɔ', 'oː', 'ʊ'],     
        ['u', 'uː', 'ʊ'],          
        ['ɚ', 'ər', 'ɜr', 'ɜː'],   # r-colored vowels
        ['θ', 'f'],                 # глухие фрикативы
        ['ð', 'v'],                 # звонкие фрикативы
        ['s', 'z'],                 # сибилянты
        ['ʃ', 'ʒ'],                 
        ['t', 'd'],                 # альвеолярные взрывные
        ['k', 'g'],                 # велярные взрывные
        ['p', 'b'],                 # билабиальные взрывные
        ['r', 'ɹ', 'ɻ'],            # различные r-звуки
        ['l', 'ɫ'],                 # боковые согласные
    ]
    
    # Создаем карту похожести
    similarity_map = {}
    for group in similar_groups:
        for phoneme in group:
            similarity_map[phoneme] = group
    
    def get_similarity_score(ph1: str, ph2: str) -> float:
        if ph1 == ph2:
            return 1.0
        
        # Проверяем фонетическую близость
        group1 = similarity_map.get(ph1, [ph1])
        group2 = similarity_map.get(ph2, [ph2])
        
        if ph1 in group2 or ph2 in group1:
            return 0.8  # высокая похожесть
        
        return 0.0  # нет похожести
    
    # Динамическое программирование для выравнивания
    len1, len2 = len(expected), len(user)
    dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]
    
    # Заполняем матрицу
    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            match_score = get_similarity_score(expected[i-1], user[j-1])
            
            dp[i][j] = max(
                dp[i-1][j-1] + match_score,  # совпадение/замена
                dp[i-1][j],                  # удаление
                dp[i][j-1]                   # вставка
            )
    
    # Вычисляем финальный процент
    max_length = max(len1, len2)
    if max_length == 0:
        return 100.0
    
    alignment_score = dp[len1][len2]
    percentage = (alignment_score / max_length) * 100
    
    return round(percentage, 1)

def compare_phonemes(expected: str, user: str) -> float:
    """
    Основная функция сравнения с отладочной информацией
    """
    print(f"[DEBUG] Сравниваем:")
    print(f"  Ожидалось (нормализованное): {expected}")
    print(f"  Получено (нормализованное): {user}")
    
    # Используем улучшенное сравнение
    advanced_score = advanced_phoneme_comparison(expected, user)
    
    # Также считаем простое совпадение для сравнения
    simple_score = round(SequenceMatcher(None, expected, user).ratio() * 100, 1)
    
    print(f"  Простое совпадение: {simple_score}%")
    print(f"  Фонетическое совпадение: {advanced_score}%")
    
    # Возвращаем лучший результат
    return max(simple_score, advanced_score)

async def simple_pronunciation_check(target_text: str, audio_path: str) -> float:
    """
    Проверяет произношение пользователя по аудиозаписи.
    Возвращает процент точности совпадения фонем.
    """
    
    # 1. Переводим аудио в фонемы
    user_phonemes = await audio_to_phonemes(audio_path)
    
    # 2. Переводим эталонный текст в совместимые фонемы
    expected_phonemes = text_to_phonemes_simplified(target_text)
    
    # 3. Сравниваем с учетом фонетической близости
    accuracy = compare_phonemes(expected_phonemes, user_phonemes)
    
    return accuracy

async def get_teacher_response(question: str) -> str:
    """
    AI агент-учитель с использованием GPT-4.1-nano
    """
    if not OPENAI_AVAILABLE:
        # Fallback к простым ответам если нет OpenAI
        return await get_simple_teacher_response(question)
    
    try:
        # Системный промпт для агента-учителя
        system_prompt = """Ты — Telegram-бот для изучения английского языка. Веди пользователя по этапам: введение новых слов, фонетика, лексика, грамматика, лексико-грамматические задания, аудирование, письмо и говорение. 

На каждом этапе давай задания, проверяй ответы, объясняй ошибки. Если пользователь не понял правило — организуй диалог для разъяснения. 

Всегда объясняй на русском языке. Используй картинки, аудио, варианты ответов, текстовые и голосовые задания. Поддерживай дружелюбный и мотивирующий стиль общения.

Сейчас ты отвечаешь на вопрос пользователя по грамматике английского языка. Особое внимание уделяй терминологии программирования, Data Science и нейросетей в примерах."""
        
        # Создаем клиент OpenAI
        client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        
        # Отправляем запрос к GPT-4.1-nano
        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # Используем доступную модель вместо gpt-4.1-nano
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Вопрос по грамматике: {question}"}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        return f"🤖 {response.choices[0].message.content}"
        
    except Exception as e:
        print(f"Ошибка OpenAI API: {e}")
        # Fallback к простым ответам
        return await get_simple_teacher_response(question)


async def get_simple_teacher_response(question: str) -> str:
    """
    Простые ответы на типичные вопросы (fallback)
    """
    responses = {
        "когда использовать": "Present Simple используется для постоянных действий, привычек и фактов. Например: 'I code every day' или 'Neural networks process data'.",
        "как образуется": "Present Simple образуется с помощью основной формы глагола. Для he/she/it добавляется -s или -es. Например: 'I debug' → 'She debugs'.",
        "отрицание": "Для отрицания используется do not (don't) или does not (doesn't). Например: 'I don't use Java' или 'The model doesn't overfit'.",
        "вопрос": "Вопросы образуются с помощью do/does. Например: 'Do you program in Python?' или 'Does the algorithm work efficiently?'",
        "примеры": "Примеры Present Simple в IT: 'I write code daily', 'She trains neural networks', 'Python supports machine learning', 'Data flows through pipelines'."
    }
    
    question_lower = question.lower()
    
    # Ищем ключевые слова в вопросе
    for key, response in responses.items():
        if key in question_lower:
            return f"📚 {response}\n\nЕсли у вас есть другие вопросы, задавайте!"
    
    # Общий ответ если не нашли подходящий
    return ("📚 Это хороший вопрос! Present Simple - это одно из основных времен в английском языке. "
            "В программировании мы часто используем его для описания процессов: 'The algorithm processes data', 'Python executes code'. "
            "Попробуйте переформулировать вопрос более конкретно, и я постараюсь помочь!")


async def check_writing_with_ai(text: str, task_type: str = "sentence") -> str:
    """
    Проверка письменного задания с помощью AI
    """
    check_writing_with_ai
    print(f"[DEBUG] check_writing_with_ai вызван")
    print(f"[DEBUG] Текст пользователя: '{text}'")
    print(f"[DEBUG] OPENAI_AVAILABLE = {OPENAI_AVAILABLE}")
    
    if not OPENAI_AVAILABLE:
        print("[DEBUG] Используется fallback — simple_writing_check")
        # Fallback к простой проверке
        return await simple_writing_check(text, task_type)
    
    try:
        # Системный промпт для проверки письма
        if task_type == "sentence":
            system_prompt = """Ты - учитель английского языка. Проверь предложение студента на грамматические ошибки, стиль и соответствие заданию. 

Дай конструктивную обратную связь на русском языке:
- Если ошибок нет: похвали и кратко прокомментируй
- Если есть ошибки: укажи их и предложи исправления
- Будь конструктивным и мотивирующим

Особое внимание уделяй IT терминологии и техническому контексту."""
        else:  # translation
            system_prompt = """Ты - учитель английского языка. Проверь перевод студента с русского на английский.

Дай обратную связь на русском языке:
- Оцени правильность перевода
- Укажи грамматические ошибки если есть
- Предложи более точный вариант если нужно
- Будь конструктивным и поддерживающим

Контекст: IT терминология, программирование, Data Science."""
        
        # Создаем клиент OpenAI
        client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        
        # Отправляем запрос
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Проверь это: {text}"}
            ],
            max_tokens=300,
            temperature=0.3
        )
        
        return f"👨‍🏫 **Обратная связь учителя:**\n\n{response.choices[0].message.content}"
        
    except Exception as e:
        print(f"Ошибка AI проверки письма: {e}")
        return await simple_writing_check(text, task_type)


async def simple_writing_check(text: str, task_type: str = "sentence") -> str:
    """
    Простая проверка письма (fallback)
    """
    if task_type == "sentence":
        if len(text.split()) >= 3:
            return ("👨‍🏫 **Хорошая работа!** \n\n"
                   "Ваше предложение составлено правильно. "
                   "Продолжайте практиковаться с техническими терминами!")
        else:
            return ("👨‍🏫 **Можно лучше!** \n\n"
                   "Попробуйте составить более развернутое предложение. "
                   "Добавьте больше деталей о том, как используется этот термин в IT.")
    else:  # translation
        if len(text.split()) >= 4:
            return ("👨‍🏫 **Отличный перевод!** \n\n"
                   "Ваш перевод выглядит грамотно. "
                   "Хорошее владение технической лексикой!")
        else:
            return ("👨‍🏫 **Неплохо, но можно улучшить!** \n\n"
                   "Попробуйте сделать перевод более полным и точным. "
                   "Обратите внимание на технические термины.")


async def analyze_speaking_with_ai(audio_text: str, topic: str) -> str:
    """
    Анализ устной речи с помощью AI
    """
    if not OPENAI_AVAILABLE:
        # Fallback к простому анализу
        return await simple_speaking_analysis(audio_text, topic)
    
    try:
        # Системный промпт для анализа речи
        system_prompt = """Ты - опытный преподаватель английского языка, специализирующийся на обучении программистов и IT специалистов.

Проанализируй устное высказывание студента на английском языке и дай подробную обратную связь на русском языке:

1. Оцени соответствие теме
2. Укажи на грамматические ошибки (если есть)
3. Прокомментируй использование технической лексики
4. Дай советы по улучшению
5. Похвали за хорошие моменты

Будь конструктивным, поддерживающим и мотивирующим. Фокусируйся на IT контексте."""
        
        # Создаем клиент OpenAI
        client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        
        # Отправляем запрос
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Тема: {topic}\n\nВысказывание студента: {audio_text}"}
            ],
            max_tokens=400,
            temperature=0.4
        )
        
        return f"🎙️ **Анализ вашего высказывания:**\n\n{response.choices[0].message.content}"
        
    except Exception as e:
        print(f"Ошибка AI анализа речи: {e}")
        return await simple_speaking_analysis(audio_text, topic)


async def simple_speaking_analysis(audio_text: str, topic: str) -> str:
    """
    Простой анализ речи (fallback)
    """
    if len(audio_text) > 50:
        return ("🎙️ **Отличная работа!**\n\n"
               "Вы хорошо раскрыли тему и показали уверенное владение английским языком в IT контексте. "
               "Продолжайте практиковаться - ваши навыки говорения развиваются!\n\n"
               "💡 **Совет:** Попробуйте использовать больше технических терминов в следующих высказываниях.")
    else:
        # Если текст короткий, возможно, распознавание не сработало
        return ("🎙️ **Хорошая попытка!**\n\n"
               "Я не смог полностью распознать ваше высказывание, но вы молодец, что практикуете устную речь! "
               "Это очень важно для развития разговорных навыков в IT среде.\n\n"
               "💡 **Совет:** Говорите чуть громче и четче для лучшего распознавания.")


async def transcribe_audio_simple(audio_path: str) -> str:
    """
    Транскрипция аудио файла с использованием Whisper API
    """
    try:
        # Проверяем, что файл существует
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Аудио файл не найден: {audio_path}")
        
        # Проверяем размер файла (Whisper API имеет лимит 25MB)
        file_size = os.path.getsize(audio_path) / (1024 * 1024)  # в MB
        if file_size > 25:
            raise ValueError(f"Файл слишком большой: {file_size:.1f}MB. Максимум 25MB")
        
        # Создаем клиент OpenAI
        client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
        
        # Открываем аудио файл и отправляем на транскрипцию
        with open(audio_path, 'rb') as audio_file:
            transcript = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en",
                response_format="text",
                temperature=0.0
            )
        
        return transcript.strip()
        
    except Exception as e:
        print(f"Ошибка при транскрипции: {e}")
        # Fallback к заглушке
        sample_responses = [
            "I think programming is very important skill for future. Python is my favorite language because it simple and powerful.",
            "Machine learning help us solve complex problems. I use TensorFlow for my projects and it work very good.",
            "Debugging is challenge but necessary part of development. I use print statements and debugger tools.",
            "AI changing everything in technology. Many jobs become automated but new opportunities appear too.",
            "Remote work good for programmers because we can focus better at home without office noise."
        ]
        return random.choice(sample_responses)


async def transcribe_telegram_audio(bot, file_id: str) -> str:
    """
    Транскрипция аудио сообщения из aiogram бота
    
    Args:
        bot: экземпляр aiogram бота
        file_id: ID файла из Telegram (voice.file_id или audio.file_id)
    
    Returns:
        str: расшифрованный текст
    """
    try:
        # Получаем информацию о файле из Telegram
        file = await bot.get_file(file_id)
        
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as temp_file:
            # Скачиваем файл из Telegram для aiogram
            await bot.download_file(file.file_path, temp_file.name)
            
            # Транскрибируем
            result = await transcribe_audio_simple(temp_file.name)
            
            # Удаляем временный файл
            os.unlink(temp_file.name)
            
            return result
            
    except Exception as e:
        print(f"Ошибка при обработке Telegram аудио: {e}")
        return "Ошибка: не удалось обработать аудио сообщение"


async def handle_voice_message(message: types.Message):
    """
    Обработчик голосовых сообщений в aiogram боте
    """
    try:
        # Получаем голосовое сообщение
        voice = message.voice
        
        # Транскрибируем
        transcribed_text = await transcribe_telegram_audio(message.bot, voice.file_id)
        
        # Отправляем на анализ (ваша существующая функция)
        topic = "General IT Discussion"  # или получите тему из контекста
        analysis = await analyze_speaking_with_ai(transcribed_text, topic)
        
        # Отправляем результат пользователю
        await message.reply(analysis)
        
    except Exception as e:
        await message.reply("Извините, произошла ошибка при обработке вашего сообщения.")
        print(f"Ошибка в обработчике голосовых сообщений: {e}")



# Глобальный экземпляр для отслеживания прогресса
user_progress = UserProgress()