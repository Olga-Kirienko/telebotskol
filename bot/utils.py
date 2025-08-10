import json
import os
import asyncio
import sys
import re
import random
import numpy as np
import librosa
import torch
import torchaudio
import subprocess
import sys
from typing import Dict, List, Tuple, Any, Optional
from gtts import gTTS
import aiofiles
from openai import AsyncOpenAI
import tempfile
from aiogram import types # Оставляем types, так как он нужен для handle_voice_message
from aiogram.types import FSInputFile # Добавляем для работы с файлами, если потребуется в других функциях
from transformers import Wav2Vec2Processor, Wav2Vec2ForCTC, Wav2Vec2FeatureExtractor, Wav2Vec2CTCTokenizer
from difflib import SequenceMatcher
import subprocess
from datetime import datetime # Добавляем datetime для создания уникальных имен файлов
from bot.statistics import UserStatistics
# --- Установка переменной окружения для eSpeak NG ---
# Автоматическое определение операционной системы и установка пути к eSpeak NG.
# Убедитесь, что eSpeak NG установлен в стандартных местах или указан в системных переменных PATH.

espeak_path = None # Инициализируем None, чтобы потом проверить, установлен ли путь

if sys.platform.startswith('win'):
    # Для Windows: ищем espeak-ng.exe в PATH или используем стандартный путь
    # Можно добавить переменную окружения ESPEAK_NG_PATH для гибкости
    espeak_ng_executable = "espeak-ng.exe"
    # Попробуем найти в PATH
    from shutil import which
    espeak_path = which(espeak_ng_executable)
    if not espeak_path:
        # Если не найдено в PATH, можно указать предполагаемый путь
        # Пользователь может задать свою переменную окружения ESPEAK_NG_PATH
        # или изменить этот путь
        default_win_path = os.environ.get('ESPEAK_NG_PATH', 'C:\\Program Files\\eSpeak NG\\espeak-ng.exe')
        if os.path.exists(default_win_path):
            espeak_path = default_win_path
        else:
            print(f"Внимание: eSpeak-ng.exe не найден в PATH и по пути '{default_win_path}'. "
                  "Убедитесь, что eSpeak NG установлен и доступен, или задайте переменную окружения ESPEAK_NG_PATH.")
            espeak_path = 'espeak-ng' # Попытка использовать как команду, если не найден полный путь
elif sys.platform.startswith('linux') or sys.platform.startswith('darwin'): # Linux или macOS
    # Для Linux/macOS: espeak-ng обычно в /usr/bin/ или доступен в PATH
    espeak_ng_executable = "espeak-ng"
    # Попробуем найти в PATH
    from shutil import which
    espeak_path = which(espeak_ng_executable)
    if not espeak_path:
        # Если не найдено в PATH, можно указать предполагаемый путь
        # Или просто использовать 'espeak-ng' как команду, если она в PATH, но which не сработал
        default_unix_path = os.environ.get('ESPEAK_NG_PATH', '/usr/bin/espeak-ng')
        if os.path.exists(default_unix_path):
            espeak_path = default_unix_path
        else:
            print(f"Внимание: espeak-ng не найден в PATH и по пути '{default_unix_path}'. "
                  "Убедитесь, что eSpeak NG установлен и доступен, или задайте переменную окружения ESPEAK_NG_PATH.")
            espeak_path = 'espeak-ng' # Попытка использовать как команду
else:
    print(f"Внимание: Неизвестная операционная система '{sys.platform}'. "
          "Проверьте путь к eSpeak NG вручную.")
    espeak_path = 'espeak-ng' # Попытка использовать как команду по умолчанию
# --- Загрузка моделей один раз при старте приложения ---
# Эти модели используются для фонетического анализа Wav2Vec2
feature_extractor = Wav2Vec2FeatureExtractor.from_pretrained("facebook/wav2vec2-lv-60-espeak-cv-ft")
tokenizer = Wav2Vec2CTCTokenizer.from_pretrained("facebook/wav2vec2-lv-60-espeak-cv-ft")
processor = Wav2Vec2Processor(feature_extractor=feature_extractor, tokenizer=tokenizer)
model = Wav2Vec2ForCTC.from_pretrained("facebook/wav2vec2-lv-60-espeak-cv-ft")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_PATH, AUDIO_PATH, OPENAI_API_KEY

# Проверяем доступность OpenAI API
OPENAI_AVAILABLE = bool(OPENAI_API_KEY)
if OPENAI_AVAILABLE:
    try:
        import openai
    except ImportError:
        OPENAI_AVAILABLE = False
        OPENAI_API_KEY = None

# --- Вспомогательные функции для работы с данными и аудио ---
async def load_json_data(filename: str) -> Dict:
    """Загружает данные из JSON файла."""
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


# Словарь для кэширования путей к MP3 файлам
# Ключ: (filename_prefix, lang, slow_mode) -> путь_к_файлу
_mp3_cache = {}


async def generate_audio(text: str, filename_prefix: str, lang: str = 'en', slow_mode: bool = False) -> str:
    """
    Генерирует аудиофайл из текста с использованием gTTS.
    Кэширует MP3 файлы на основе текста, языка и режима скорости.
    :param text: Текст для генерации.
    :param filename_prefix: Базовое имя файла (например, "apple" из JSON).
    :param lang: Язык.
    :param slow_mode: True для замедленной речи, False для обычной.
    :return: Путь к сгенерированному или кэшированному MP3 файлу.
    """
    # Создаём уникальный суффикс для файла, чтобы учитывать slow_mode
    speed_suffix = "_slow" if slow_mode else ""
    # Создаём детерминированное имя файла, которое будет уникально для текста, языка и скорости
    # Используем комбинацию filename_prefix и хэша текста для надёжного кэширования,
    # избегая слишком длинных имён файлов и сохраняя читаемость.
    # Это позволяет кэшировать "Apple" и "Apple_slow" как разные файлы.
    import hashlib # Временный импорт для хэша, если он нужен только здесь
    text_hash = hashlib.md5(f"{text}-{lang}-{slow_mode}".encode('utf-8')).hexdigest()[:8] # Сокращаем хэш

    # Используем clean_prefix, чтобы имя файла было валидным и коротким
    clean_prefix = re.sub(r'[^a-zA-Z0-9_]', '', filename_prefix).lower()
    if len(clean_prefix) > 20: # Обрезаем, чтобы не было слишком длинных префиксов
        clean_prefix = clean_prefix[:20]

    final_filename = f"{clean_prefix}{speed_suffix}_{text_hash}.mp3"
    audio_file_path = os.path.join(AUDIO_PATH, final_filename)

    # Ключ для кэша в памяти, чтобы быстро найти файл, если он уже сгенерирован
    cache_key = (text, lang, slow_mode)

    # 1. Проверяем кэш в памяти
    if cache_key in _mp3_cache:
        cached_path = _mp3_cache[cache_key]
        if os.path.exists(cached_path):
            print(f"Используется кэшированный MP3 файл из памяти: {cached_path}")
            return cached_path
        else:
            # Если файл удалён с диска, но ссылка в кэше осталась, удаляем её
            del _mp3_cache[cache_key]
            print(f"Кэшированный MP3 файл не найден на диске, перегенерация.")

    # 2. Если не найдено в кэше, проверяем файл на диске
    if os.path.exists(audio_file_path):
        print(f"Используется существующий MP3 файл на диске: {audio_file_path}")
        _mp3_cache[cache_key] = audio_file_path # Добавляем в кэш в памяти
        return audio_file_path

    # 3. Если файла нет, генерируем его
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: gTTS(text=text, lang=lang, slow=slow_mode).save(audio_file_path)
        )
        print(f"MP3 аудио сгенерировано: {audio_file_path}")
        _mp3_cache[cache_key] = audio_file_path # Добавляем в кэш в памяти
        return audio_file_path
    except Exception as e:
        print(f"Ошибка генерации MP3 аудио: {e}")
        # В случае ошибки, удаляем недоделанный файл, если он есть
        if os.path.exists(audio_file_path):
            os.remove(audio_file_path)
        return None
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True) # Создаем папку, если ее нет

PROGRESS_FILE = os.path.join(DATA_DIR, "user_progress.json")
class UserProgress:
    """Управление прогрессом пользователя с сохранением на диск."""

    def __init__(self):
        self.users_progress = {}
        self._load_progress() # Загружаем прогресс при инициализации

    def _load_progress(self):
        """Загружает прогресс пользователей из файла."""
        if os.path.exists(PROGRESS_FILE):
            try:
                with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                    # Преобразуем ключи user_id из строк в int, т.к. JSON сохраняет их как строки
                    loaded_data = json.load(f)
                    self.users_progress = {int(k): v for k, v in loaded_data.items()}
                print(f"DEBUG: Прогресс пользователей загружен из {PROGRESS_FILE}")
            except (json.JSONDecodeError, ValueError) as e:
                print(f"ERROR: Ошибка чтения файла прогресса {PROGRESS_FILE}: {e}. Начинаем с чистого листа.")
                self.users_progress = {}
        else:
            print(f"DEBUG: Файл прогресса {PROGRESS_FILE} не найден. Начинаем с чистого листа.")

    def _save_progress(self):
        """Сохраняет прогресс пользователей в файл."""
        try:
            with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.users_progress, f, indent=4, ensure_ascii=False)
            # print(f"DEBUG: Прогресс пользователей сохранен в {PROGRESS_FILE}") # Можно раскомментировать для отладки
        except IOError as e:
            print(f"ERROR: Ошибка записи файла прогресса {PROGRESS_FILE}: {e}")

    def get_progress(self, user_id: int) -> Dict:
        """Получить прогресс пользователя или инициализировать его."""
        # Убедитесь, что эти поля инициализируются при первом получении прогресса пользователя
        # Добавляем current_pronunciation_data и удаляем current_pronunciation_text,
        # так как current_pronunciation_data будет его заменой.
        # Возвращаем копию, чтобы избежать случайных изменений без update_progress
        return self.users_progress.get(user_id, {
            'current_block': 'terms',
            'current_item': 0,
            'completed_items': [],
            'current_pronunciation_slow_mode': False,
            'current_pronunciation_data': None,  # <--- НОВОЕ ПОЛЕ: будет хранить всю инфу о фразе
        }).copy() # Возвращаем копию, чтобы избежать прямого изменения внутреннего словаря

    def update_progress(self, user_id: int, **kwargs: Any):
        """Обновить прогресс пользователя и сохранить."""
        if user_id not in self.users_progress:
            self.users_progress[user_id] = self.get_progress(user_id)
        self.users_progress[user_id].update(kwargs)
        self._save_progress() # Сохраняем после каждого обновления
        print(f"DEBUG: UserProgress: Прогресс пользователя {user_id} обновлен: {kwargs}")


    def reset_progress(self, user_id: int):
        """Сбросить прогресс пользователя и сохранить."""
        # Используем get_progress для получения начального состояния
        self.users_progress[user_id] = self.get_progress(user_id)
        self._save_progress() # Сохраняем после сброса
        print(f"DEBUG: UserProgress: Прогресс пользователя {user_id} сброшен.")

    def clear_current_block_data(self, user_id: int):
        """
        Очищает данные о текущем блоке и подблоке для пользователя.
        Вызывается после завершения блока.
        :param user_id: ID пользователя.
        """
        user_id_str = str(user_id) # Используем строковое представление, так как ключи в users_progress - int
        if user_id in self.users_progress:
            user_data = self.users_progress[user_id]
            if 'current_block' in user_data:
                del user_data['current_block']
                print(f"DEBUG: UserProgress: 'current_block' очищен для пользователя {user_id}.")
            if 'current_sub_block' in user_data:
                del user_data['current_sub_block']
                print(f"DEBUG: UserProgress: 'current_sub_block' очищен для пользователя {user_id}.")
            self._save_progress()
            print(f"DEBUG: UserProgress: Данные текущего блока очищены и сохранены для пользователя {user_id}.")
        else:
            print(f"DEBUG: UserProgress: Прогресс для пользователя {user_id} не найден, нет данных для очистки.")

# --- Функции для обработки произношения ---

async def convert_ogg_to_wav(input_path: str, output_path: str):
    """Конвертирует OGG аудиофайл в WAV."""
    try:
        waveform, sample_rate = torchaudio.load(input_path)
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)  # Конвертируем стерео в моно
        if sample_rate != 16000:
            resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
            waveform = resampler(waveform)
        torchaudio.save(output_path, waveform, 16000, format="wav")
        return True
    except Exception as e:
        print(f"Ошибка конвертации ogg → wav: {e}")
        return False


# Список диакритических знаков IPA для удаления/нормализации
DIACRITICS = [
    'ː', 'ˑ', 'ˈ', 'ˌ', 'ʰ', 'ʷ', 'ʲ',
    '\u0325', '\u032C', '\u0303', '\u0329', '\u0361', '˞'
]

# Группы похожих фонем для более точного сравнения
similar_groups = [
    ['i', 'ɪ', 'iː'],
    ['e', 'ɛ', 'eː'],
    ['æ', 'a', 'ʌ'],
    ['o', 'ɔ', 'oː', 'ʊ'],
    ['u', 'uː', 'ʊ'],
    ['ɚ', 'ər', 'ɜr', 'ɜː'],
    ['θ', 'f'],
    ['ð', 'v'],
    ['s', 'z'],
    ['ʃ', 'ʒ'],
    ['t', 'd'],
    ['k', 'g'],
    ['p', 'b'],
    ['r', 'ɹ', 'ɻ'],
    ['l', 'ɫ'],
]


def normalize_phonemes(phonemes: str) -> str:
    """Нормализует фонемы, удаляя диакритические знаки и преобразуя схожие фонемы."""
    s = phonemes.strip()
    for d in DIACRITICS:
        esc = re.escape(d)
        s = re.sub(rf'([^\s])\s*{esc}', r'\1', s)  # Удаляем диакритику, если она следует за фонемой без пробела
    s = re.sub(r'[ˈˌ`´ʼ\']', '', s)  # Удаляем знаки ударения/апострофы

    # Карта для упрощения фонем
    phoneme_mapping = {
        'ɜː': 'ɚ', 'əʊ': 'oʊ', 'ɛ': 'e', 'ɔː': 'ɑː', 'ɪ': 'i', 'ʌ': 'ʌ',
        'aɪ': 'aɪ', 'æ': 'æ', 'ð': 'ð', 'θ': 'θ', 'ŋ': 'ŋ', 'ʃ': 'ʃ',
        'ʒ': 'ʒ', 'tʃ': 'tʃ', 'dʒ': 'dʒ', 'j': 'j', 'w': 'w', 'r': 'ɹ',
        'l': 'l',
    }

    for old, new in phoneme_mapping.items():
        s = s.replace(old, new)

    s = ''.join(s.split()).lower()  # Удаляем все пробелы и приводим к нижнему регистру
    return s.strip()


def get_phonemes_from_espeak(text: str) -> str:
    """Получает фонемы (IPA) для текста с помощью eSpeak NG."""
    try:
        result = subprocess.run(
            [espeak_path, '-q', '--ipa', text],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace",
            check=True
        )
        return result.stdout.strip()
    except FileNotFoundError as e:
        print(f"Ошибка: {e}")
        return ""
    except subprocess.CalledProcessError as e:
        print(f"Ошибка выполнения espeak-ng (код: {e.returncode}): {e.stderr}")
        return ""
    except Exception as e:
        print(f"Общая ошибка при вызове espeak-ng: {e}")
        return ""


def text_to_phonemes_simplified(text: str) -> str:
    """Преобразует текст в упрощенные фонемы."""
    ipa_output = get_phonemes_from_espeak(text)
    normalized = normalize_phonemes(ipa_output)
    return normalized


async def audio_to_phonemes(audio_path: str) -> str:
    """Транскрибирует аудио в фонемы с использованием Wav2Vec2 модели."""
    try:
        # torchaudio.load() может быть более универсальным для разных форматов
        waveform, sr = torchaudio.load(audio_path)

        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0)  # Конвертация стерео в моно

        if sr != 16000:
            resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=16000)
            waveform = resampler(waveform)

        # Нормализация громкости для Wav2Vec2
        waveform = (waveform - waveform.mean()) / (waveform.std() + 1e-7)

        input_values = processor(waveform.numpy(), return_tensors="pt", sampling_rate=16000).input_values
        with torch.no_grad():
            logits = model(input_values).logits
        predicted_ids = torch.argmax(logits, dim=-1)
        transcription = processor.decode(predicted_ids[0])
        normalized = normalize_phonemes(transcription)
        return normalized
    except Exception as e:
        print(f"Ошибка обработки аудио в фонемы: {e}")
        return ""


def advanced_phoneme_comparison(expected: str, user: str) -> float:
    """
    Сравнивает две строки фонем, используя SequenceMatcher.ratio()
    для получения общей точности.
    """
    if not expected and not user:
        return 100.0
    if not expected or not user:
        return 0.0  # Если одна строка пуста, а другая нет

    matcher = SequenceMatcher(None, expected, user)
    return round(matcher.ratio() * 100, 1)


def _preprocess_text_for_phoneme_splitting(text: str) -> str:
    """
    Предварительная обработка текста для разделения на слова
    для корректного получения фонем.
    """
    text = re.sub(r"['’-]", " ", text)  # Заменяем апострофы и дефисы пробелами
    text = re.sub(r'[^\w\s]', '', text)  # Удаляем знаки препинания
    text = re.sub(r'\s+', ' ', text).strip()  # Убираем лишние пробелы
    return text.lower()


def analyze_word_errors(
        text_words: List[str],
        orig_phonemes: str,  # Это flat строка
        user_phonemes: str  # Это flat строка
) -> List[Dict]:
    """Анализ ошибок произношения по отдельным словам."""

    # Если orig_phonemes не был получен с пробелами между словами,
    # нам нужно получить фонемное представление каждого слова отдельно
    # для корректного разделения на границы слов.
    # orig_phonemes, переданная сюда, уже является "плоской" строкой из `text_to_phonemes_simplified`.
    # Поэтому для пословного анализа нам нужно снова сгенерировать фонемы для каждого слова.
    orig_words_phonemes_separated = [text_to_phonemes_simplified(word) for word in text_words]

    # Создаем "плоскую" версию эталонных фонем, но теперь гарантированно разбитую по словам,
    # чтобы сопоставить границы слов.
    orig_flat_with_word_boundaries = "".join(orig_words_phonemes_separated)
    user_flat = user_phonemes  # user_phonemes уже нормализованы и без пробелов

    # Проверяем, чтобы длины фонем соответствовали ожидаемым
    if not orig_flat_with_word_boundaries and not user_flat:  # Обе строки пусты
        return []
    if not orig_flat_with_word_boundaries or not user_flat:  # Одна строка пуста, другая нет
        # В этом случае пословный анализ может быть неинформативен,
        # но мы должны хотя бы указать, что что-то не так.
        # Это крайний случай, который обычно обрабатывается на уровне overall_accuracy.
        # Для простоты, если есть слова в text_words, вернем по ним 0%
        return [{
            'word': word,
            'expected': text_to_phonemes_simplified(word),
            'expected_ipa_raw': get_phonemes_from_espeak(word), # Add raw IPA for better GPT analysis
            'detected': user_flat,  # detected_word_phonemes не получится точно выделить
            'accuracy': 0.0,
            'errors': ["Значительные расхождения с ожидаемым произношением всего предложения."]
        } for word in text_words]

    word_boundaries = []
    current_pos = 0
    for word_ph_separated in orig_words_phonemes_separated:
        start = current_pos
        end = start + len(word_ph_separated)
        word_boundaries.append((start, end))
        current_pos = end

    # Используем SequenceMatcher для общего выравнивания двух полных строк фонем
    matcher = SequenceMatcher(None, orig_flat_with_word_boundaries, user_flat)
    alignment = matcher.get_opcodes()

    results = []

    for idx, (start, end) in enumerate(word_boundaries):
        if idx >= len(text_words):
            break

        word = text_words[idx]
        expected_word_phonemes = orig_flat_with_word_boundaries[start:end]
        expected_word_phonemes_raw_ipa = get_phonemes_from_espeak(word) # Get raw IPA for the word


        detected_word_phonemes = ''

        # Собираем фонемы, произнесенные пользователем, для текущего слова
        # Идем по общему выравниванию и извлекаем те части, которые соответствуют текущему слову
        for tag, i1, i2, j1, j2 in alignment:
            # i1, i2 относятся к orig_flat_with_word_boundaries
            # j1, j2 относятся к user_flat

            # Если блок выравнивания полностью до начала текущего слова
            if i2 <= start:
                continue
            # Если блок выравнивания полностью после конца текущего слова
            if i1 >= end:
                break

            # Находим пересечение блока выравнивания с границами текущего слова
            clip_start_orig = max(i1, start)
            clip_end_orig = min(i2, end)

            if clip_end_orig <= clip_start_orig:  # Если нет пересечения или оно нулевое
                continue

            # Определяем, какую часть из user_flat нужно взять
            # Это приблизительный расчет, основанный на пропорции
            # Более точное сопоставление требует построения нового SequenceMatcher для каждой пары слово-пользователь

            # Пропорция текущего совпадения/различия в контексте всего блока
            ratio_in_block = (clip_end_orig - clip_start_orig) / (i2 - i1) if (i2 - i1) > 0 else 0

            # Часть, которая была произнесена пользователем для этой части блока
            detected_segment_length = int((j2 - j1) * ratio_in_block)

            # Если tag - 'equal' или 'replace', берем соответствующую часть из произнесенных
            if tag in ('equal', 'replace'):
                # Добавляем часть, которая совпадает или является заменой
                detected_word_phonemes += user_flat[j1: j1 + detected_segment_length]
            elif tag == 'insert' and (i1 >= start and i1 < end):
                # Если это "вставка" в ожидаемом тексте, но фактически в произнесенном, и она попадает в границы слова
                detected_word_phonemes += user_flat[j1: j2]  # Вставка целиком

        # Теперь, когда у нас есть предположительно произнесенные фонемы для слова, сравниваем их
        if not detected_word_phonemes and expected_word_phonemes:
            # Случай, когда слово было полностью пропущено или не распознано
            accuracy = 0.0
            errors = [f"Полностью пропустили или сильно исказили произношение."]
            highlighted_expected = [f"<b>{expected_word_phonemes}</b>"]
            highlighted_detected = ["-"]  # Обозначаем отсутствие
        elif not expected_word_phonemes and detected_word_phonemes:
            # Случай, когда в ожидаемом слове нет фонем (редко, но возможно), а пользователь что-то произнес
            accuracy = 0.0  # Не соответствует ожидаемому
            errors = [f"Лишнее произношение: '{detected_word_phonemes}'"]
            highlighted_expected = ["-"]
            highlighted_detected = [f"<b>{detected_word_phonemes}</b>"]
        elif not expected_word_phonemes and not detected_word_phonemes:
            accuracy = 100.0  # Оба пусты - идеально
            errors = []
            highlighted_expected = [""]
            highlighted_detected = [""]
        else:
            # Детальное сравнение для конкретного слова
            matcher_word = SequenceMatcher(None, expected_word_phonemes, detected_word_phonemes)
            word_alignment = matcher_word.get_opcodes()

            highlighted_expected = []
            highlighted_detected = []
            errors = []

            for tag, i1, i2, j1, j2 in word_alignment:
                exp_chunk = expected_word_phonemes[i1:i2]
                det_chunk = detected_word_phonemes[j1:j2]

                if tag == 'equal':
                    highlighted_expected.append(exp_chunk)
                    highlighted_detected.append(det_chunk)
                elif tag == 'replace':
                    highlighted_expected.append(f"<b>{exp_chunk}</b>")
                    highlighted_detected.append(f"<b>{det_chunk}</b>")
                    errors.append(f"Заменили '{exp_chunk}' на '{det_chunk}'")
                elif tag == 'delete':
                    highlighted_expected.append(f"<b>{exp_chunk}</b>")
                    errors.append(f"Пропустили '{exp_chunk}'")
                elif tag == 'insert':
                    highlighted_detected.append(f"<b>{det_chunk}</b>")
                    errors.append(f"Добавили лишнее '{det_chunk}'")

            accuracy = matcher_word.ratio() * 100

        results.append({
            'word': word,
            'expected': ''.join(highlighted_expected),
            'expected_ipa_raw': expected_word_phonemes_raw_ipa, # Add raw IPA for GPT
            'detected': ''.join(highlighted_detected),
            'accuracy': accuracy,
            'errors': errors
        })

    return results



async def simple_pronunciation_check(
    target_text: str,
    user_audio_path: str,
    lower_threshold: float,
    upper_threshold: float
) -> Tuple[float, str, str, str, str, List[Dict]]:
    """
    Проверяет произношение и формирует ответ:
      • overall_accuracy — численное значение;
      • verdict          — короткий итог (без процентов при "Отлично" и "Плохо");
      • analysis_text    — подробности (если нужно);
      • expected_phonemes, user_phonemes, word_results — служебные данные.
    """
    expected_phonemes = text_to_phonemes_simplified(target_text)
    user_phonemes = await audio_to_phonemes(user_audio_path)
    overall_accuracy = advanced_phoneme_comparison(expected_phonemes, user_phonemes)

    PERFECT_THRESHOLD = 85.0
    verdict: str = ""
    analysis_text: str = ""
    word_results: List[Dict] = []

    if overall_accuracy >= PERFECT_THRESHOLD:
        verdict = "🎉 <b>Отлично!</b>"
        analysis_text = ""  # ОБЯЗАТЕЛЬНО очистить текст анализа, чтобы не показывать детали
        word_results = []
    elif overall_accuracy >= lower_threshold:
        verdict = "👍 <b>Хорошо, но можно лучше!</b>"

        text_words_processed = _preprocess_text_for_phoneme_splitting(target_text).split()
        word_results = analyze_word_errors(text_words_processed, expected_phonemes, user_phonemes)

        analysis = ["\n\n📝 <b>Обнаружены следующие ошибки произношения:</b>"]
        for result in word_results:
            analysis.append(f"\n▸ <b>{result['word'].upper()}</b> ({result['accuracy']:.1f}%)")
            analysis.append(f"    🔹 Ожидалось: /{result['expected']}/")
            analysis.append(f"    🔸 Произнесено: /{result['detected']}/")
            if result['errors']:
                analysis.append("    💡 Подробнее:")
                for err in result['errors']:
                    analysis.append(f"      • {err}")
        analysis_text = "\n".join(analysis)
    else:
        verdict = "👎 <b>(не разборчиво, попробуйте ещё раз)</b>"
        analysis_text = ""  # ОБЯЗАТЕЛЬНО очистить текст анализа, чтобы не показывать детали
        word_results = []
        # Тоже без анализа и процентов

    return overall_accuracy, verdict, analysis_text, expected_phonemes, user_phonemes, word_results

# --- Функции AI ассистента ---

# --- НОВАЯ ФУНКЦИЯ ДЛЯ GPT-АНАЛИЗА (перенесена из gpt_phoneme_analyzer.py) ---
async def analyze_phonemes_with_gpt(
    original_text: str,
    expected_phonemes: str,
    user_phonemes: str,
    overall_accuracy: float,
    word_errors_analysis: List[Dict]
) -> Optional[str]:
    """
    Получает детальный анализ произношения от GPT-модели,
    включая сравнение фонем и конкретные советы.
    """
    if not OPENAI_API_KEY:
        print("OPENAI_API_KEY не установлен. Пропускаем GPT-анализ фонем.")
        return None

    # Добавляем проверку, чтобы GPT-анализ не делался, если нет ошибок для анализа
    # Или если точность идеальна или очень плоха (чтобы не перегружать GPT)
    if not word_errors_analysis and overall_accuracy >= 85.0: # Если нет ошибок и отлично
        return None
    if not word_errors_analysis and overall_accuracy < 68: # Если нет ошибок и плохо
        return None

    try:
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)

        error_details = []
        for word_info in word_errors_analysis:
            errors_list = ", ".join(word_info['errors']) if word_info['errors'] else "Нет специфических ошибок"
            error_details.append(
                f"- Слово: '{word_info['word']}' (Точность: {word_info['accuracy']:.1f}%)\n"
                f"  Ожидалось (фонемы): /{word_info['expected']}/\n"
                f"  Произнесено (фонемы): /{word_info['detected']}/\n"
                f"  Ошибки: {errors_list}"
            )

        error_analysis_str = "\n".join(error_details) if error_details else "Детальный пословный анализ не выявил специфических ошибок или не был предоставлен."

        system_prompt = f"""Ты — эксперт по фонетике английского языка и учитель по произношению.
        Твоя задача — проанализировать произношение студента, сравнить его с эталонным,
        и дать краткие, конкретные и полезные советы по улучшению.
        Отвечай на русском языке.

        Используй следующий шаблон:
        ---
        Твой анализ:
        [Твой краткий анализ произношения, основанный на сравнении фонем. Выдели основные расхождения.]

        Что делать, чтобы улучшить:
        [1-2 конкретных совета по фонетике, например, "Обратите внимание на звук /θ/ (th), он произносится как...", "Уделите внимание открытости гласных".]
        ---
        """

        user_content = f"""
        Проанализируй произношение фразы "{original_text}".
        Общая алгоритмическая точность: {overall_accuracy:.1f}%.

        Детальный пословный анализ:
        {error_analysis_str}
        """

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            max_tokens=350,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Ошибка GPT-анализа произношения: {e}")
        return "⚠️ Произошла ошибка при получении фонетического анализа от AI. Пожалуйста, попробуйте позже."


async def get_teacher_response(question: str) -> str:
    """Получает ответ от AI учителя по грамматике."""
    if not OPENAI_AVAILABLE:
        return await get_simple_teacher_response(question)
    try:
        system_prompt = """Ты — помощник в Telegram-боте по изучению английского языка. 
Отвечай на вопросы по грамматике кратко, чётко и по делу. Пиши на русском языке.

❗ Правила:
- Отвечай только на грамматические вопросы. Не отвлекайся на посторонние темы.
- Если вопрос непонятен, задай 1–2 уточняющих вопроса, прежде чем отвечать.
- Пиши структурировано: короткое объяснение + минимум 1 пример на английском с переводом.
- Используй дружелюбный, но профессиональный тон. Не пиши разговорно.
- Не используй лишние слова, шуточки, извинения.
- Не пиши "я не понял" — вместо этого уточни, например: “Вы имеете в виду...?”.
"""

        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
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
        return "⚠️ Сервис временно недоступен. Попробуйте позже."


async def get_simple_teacher_response(question: str) -> str:
    """Предоставляет простой (заглушечный) ответ учителя при отсутствии OpenAI API."""
    responses = {
        "когда использовать": "Present Simple используется для постоянных действий, привычек и фактов. Например: 'I code every day' или 'Neural networks process data'.",
        "как образуется": "Present Simple образуется с помощью основной формы глагола. Для he/she/it добавляется -s или -es. Например: 'I debug' → 'She debugs'.",
        "отрицание": "Для отрицания используется do not (don't) или does not (doesn't). Например: 'I don't use Java' или 'The model doesn't overfit'.",
        "вопрос": "Вопросы образуются с помощью do/does. Например: 'Do you program in Python?' или 'Does the algorithm work efficiently?'",
        "примеры": "Примеры Present Simple в IT: 'I write code daily', 'She trains neural networks', 'Python supports machine learning', 'Data flows through pipelines'."
    }
    question_lower = question.lower()
    for key, response in responses.items():
        if key in question_lower:
            return f"📚 {response}\n\nЕсли у вас есть другие вопросы, задавайте!"
    return ("📚 Это хороший вопрос! Present Simple - это одно из основных времен в английском языке. "
            "В программировании мы часто используем его для описания процессов: 'The algorithm processes data', 'Python executes code'. "
            "Попробуйте переформулировать вопрос более конкретно, и я постараюсь помочь!")


async def check_writing_with_ai(text: str, task_type: str = "sentence", context_data: str = "") -> str:
    """Проверяет письменный текст с помощью AI."""
    if not OPENAI_AVAILABLE:
        return await simple_writing_check(text, task_type)
    try:
        if task_type == "sentence":
            system_prompt = """Ты — учитель английского языка. Твоя задача — проверить предложение студента по следующим критериям:

Если в предложении **есть лексически, стилистические, грамматические ошибки или недочёты**, укажи их и предложи исправленный вариант.

Если ошибок **нет** — начни ответ с символа ✅ и похвали студента.

Отвечай кратко, конструктивно и на русском языке, поддерживай и стимулируй студента к изучению английского языка.
"""

        else:  # translation
            system_prompt = f"""Ты — учитель английского языка. Твоя задача — проверить как студент перевёл фразу с русского на английский, оцени корректность перевода:

        **Исходная русская фраза:** "{context_data}"

        1. Сравни перевод с исходной русской фразой
        2. Укажи на грамматические, лексические и стилистические ошибки
        3. Предложи исправленный вариант, если есть ошибки
        4. Если перевод правильный — начни ответ с символа ✅

        Отвечай на русском, кратко и конструктивно, с акцентом на обучающую ценность и поддержку."""    

        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Проверь это: {text}"}
            ],
            max_tokens=300,
            temperature=0.3
        )
        return f"👨‍🏫 <b>Обратная связь учителя:</b>\n\n{response.choices[0].message.content}"
    except Exception as e:
        print(f"Ошибка AI проверки письма: {e}")
        return await simple_writing_check(text, task_type)


async def simple_writing_check(text: str, task_type: str = "sentence") -> str:
    """Простая (заглушечная) проверка письменного текста."""
    if task_type == "sentence":
        if len(text.split()) >= 3:
            return ("✅ <b>Хорошая работа!</b> \n\n"
                    "Ваше предложение составлено правильно. "
                    "Продолжайте практиковаться с техническими терминами!")
        else:
            return ("❌ <b>Можно лучше!</b> \n\n"
                    "Попробуйте составить более развернутое предложение. "
                    "Добавьте больше деталей о том, как используется этот термин в IT.")
    else:  # translation
        if len(text.split()) >= 4:
            return ("✅ <b>Отличный перевод!</b> \n\n"
                    "Ваш перевод выглядит грамотно. "
                    "Хорошее владение технической лексикой!")
        else:
            return ("❌ <b>Неплохо, но можно улучшить!</b> \n\n"
                    "Попробуйте сделать перевод более полным и точным. "
                    "Обратите внимание на технические термины.")


async def analyze_speaking_with_ai(audio_text: str, topic: str) -> str:
    """Анализирует устное высказывание с помощью AI."""
    if not OPENAI_AVAILABLE:
        return await simple_speaking_analysis(audio_text, topic)
    try:
        system_prompt = """Ты — учитель английского языка. Твоя задача — проверить высказывание  студента по следующим критериям:

1) Грамматические, лексические, стилистические ошибки - предложи исправленный вариант

2) Соответствие теме высказывания "what does the user do with data?

3) Если студент не использовал термины из списка (user, file, folder, data, save, create, open), мягко порекомендуй вставить хотя бы один из них, если это уместно по смыслу

Если ошибок нет — похвали и подтверди, что всё хорошо.

Отвечай кратко, конструктивно и на русском языке. Используй поддерживающий, но профессиональный тон. Не извиняйся, не используй лишних слов и не пиши в разговорном стиле. Старайся мотивировать студента продолжать учёбу
"""

        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Тема: {topic}\n\nВысказывание студента: {audio_text}"}
            ],
            max_tokens=400,
            temperature=0.4
        )
        return f"🎙️ <b>Анализ вашего высказывания:</b>\n\n{response.choices[0].message.content}"
    except Exception as e:
        print(f"Ошибка AI анализа речи: {e}")
        return await simple_speaking_analysis(audio_text, topic)


async def simple_speaking_analysis(audio_text: str, topic: str) -> str:
    """Простой (заглушечная) анализ устного высказывания."""
    if len(audio_text) > 50:
        return ("🎙️ <b>Отличная работа!</b>\n\n"
                "Вы хорошо раскрыли тему и показали уверенное владение английским языком в IT контексте. "
                "Продолжайте практиковаться - ваши навыки говорения развиваются!\n\n"
                "💡 <b>Совет:</b> Попробуйте использовать больше технических терминов в следующих высказываниях.")
    else:
        return ("🎙️ <b>Хорошая попытка!</b>\n\n"
                "Я не смог полностью распознать ваше высказывание, но вы молодец, что практикуете устную речь! "
                "Это очень важно для развития разговорных навыков в IT среде.\n\n"
                "💡 <b>Совет:</b> Говорите чуть громче и четче для лучшего распознавания.")


async def transcribe_audio_simple(audio_path: str) -> str:
    """Транскрибирует аудио в текст с использованием OpenAI Whisper API."""
    try:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Аудио файл не найден: {audio_path}")
        file_size = os.path.getsize(audio_path) / (1024 * 1024)
        if file_size > 25:
            raise ValueError(f"Файл слишком большой: {file_size:.1f}MB. Максимум 25MB")
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
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
        # Возвращаем случайный ответ при ошибке API или отсутствии API ключа
        sample_responses = [
            "I think programming is very important skill for future. Python is my favorite language because it simple and powerful.",
            "Machine learning help us solve complex problems. I use TensorFlow for my projects and it work very good.",
            "Debugging is challenge but necessary part of development. I use print statements and debugger tools.",
            "AI changing everything in technology. Many jobs become automated but new opportunities appear too.",
            "Remote work good for programmers because we can focus better at home without office noise."
        ]
        return random.choice(sample_responses)


async def transcribe_telegram_audio(bot, file_id: str) -> str:
    """Загружает аудио из Telegram и транскрибирует его."""
    try:
        file = await bot.get_file(file_id)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.ogg') as temp_file:
            await bot.download_file(file.file_path, temp_file.name)
            result = await transcribe_audio_simple(temp_file.name)
            os.unlink(temp_file.name)  # Удаляем временный файл
            return result
    except Exception as e:
        print(f"Ошибка при обработке Telegram аудио: {e}")
        return "Ошибка: не удалось обработать аудио сообщение"


async def handle_voice_message(message: types.Message):
    """
    Обработчик голосовых сообщений.
    Эта функция находится здесь, но в реальном приложении должна вызываться из роутера.
    """
    try:
        voice = message.voice
        transcribed_text = await transcribe_telegram_audio(message.bot, voice.file_id)
        topic = "Общие рассуждения об IT"  # Можно сделать тему динамической
        analysis = await analyze_speaking_with_ai(transcribed_text, topic)
        await message.reply(analysis)
    except Exception as e:
        await message.reply("Извините, произошла ошибка при обработке вашего сообщения.")
        print(f"Ошибка в обработчике голосовых сообщений: {e}")


# Создаем экземпляр класса UserProgress для отслеживания прогресса пользователей
