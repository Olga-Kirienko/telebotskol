import json
import os
from config import DATA_PATH, CURRENT_LESSON_ID
from datetime import datetime
from collections import defaultdict
from typing import Dict, Any, Tuple, List
import traceback

class UserStatistics:
    def __init__(self, data_file="user_statistics.json"):
        self.data_file = os.path.join(DATA_PATH, data_file)
        self._load_data()

    def _load_data(self):
        """Загружает данные статистики из файла. Добавлена базовая миграция."""
        if os.path.exists(self.data_file):
            with open(self.data_file, 'r', encoding='utf-8') as f:
                try:
                    self.data = json.load(f)
                    for user_id_str, user_stats in list(self.data.items()):
                        # Миграция старых данных, если необходимо
                        if "lesson_progress" in user_stats and "lessons" not in user_stats:
                            print(f"DEBUG: Миграция данных для пользователя {user_id_str} из старой структуры.")
                            lessons_data = {
                                CURRENT_LESSON_ID: {
                                    "status": "completed" if user_stats.get("lessons_completed_count",
                                                                            0) > 0 else "in_progress",
                                    "blocks": {
                                        "terms": user_stats["lesson_progress"].get("terms", {"completed": False,
                                                                                             "average_score": None}),
                                        "pronunciation": user_stats["lesson_progress"].get("pronunciation",
                                                                                           {"completed": False,
                                                                                            "average_score": None}),
                                        "pronunciation_attempts": user_stats.get("pronunciation_attempts", [])
                                    }
                                }
                            }
                            user_stats["total_lessons_completed"] = user_stats.pop("lessons_completed_count", 0)
                            user_stats["lessons"] = lessons_data
                            user_stats.pop("lesson_progress", None)
                            user_stats.pop("pronunciation_attempts", None)
                            self._save_data()
                        # Убедимся, что все необходимые блоки и подблоки инициализированы
                        lesson_stats = user_stats["lessons"].get(CURRENT_LESSON_ID)
                        if lesson_stats:
                            # Инициализация всех ожидаемых блоков и подблоков
                            # Это гарантирует, что даже если блок не был пройден, он существует в структуре
                            # с дефолтными значениями, что важно для расчетов общего балла.
                            default_block_data = {"completed": False, "average_score": 0.0} # Изменено None на 0.0 для average_score
                            default_sub_block_data = {"completed": False, "average_score": 0.0, "attempts": []} # Изменено None на 0.0

                            # Основные блоки
                            for block in ["terms", "pronunciation", "lexical", "grammar",
                                         "lexico_grammar", "listening", "writing", "speaking"]:
                                if block not in lesson_stats["blocks"]:
                                    lesson_stats["blocks"][block] = default_block_data.copy()

                            # Подблоки лексики
                            if "lexical_en_to_ru" not in lesson_stats["blocks"]:
                                lesson_stats["blocks"]["lexical_en_to_ru"] = default_sub_block_data.copy()
                            if "lexical_ru_to_en" not in lesson_stats["blocks"]:
                                lesson_stats["blocks"]["lexical_ru_to_en"] = default_sub_block_data.copy()
                            if "lexical_word_build" not in lesson_stats["blocks"]:
                                lesson_stats["blocks"]["lexical_word_build"] = default_sub_block_data.copy()

                            # Подблоки лексико-грамматики
                            if "lexico_grammar_verb" not in lesson_stats["blocks"]:
                                lesson_stats["blocks"]["lexico_grammar_verb"] = default_sub_block_data.copy()
                            if "lexico_grammar_mchoice" not in lesson_stats["blocks"]:
                                lesson_stats["blocks"]["lexico_grammar_mchoice"] = default_sub_block_data.copy()
                            if "lexico_grammar_negative" not in lesson_stats["blocks"]:
                                lesson_stats["blocks"]["lexico_grammar_negative"] = default_sub_block_data.copy()
                            if "lexico_grammar_question" not in lesson_stats["blocks"]:
                                lesson_stats["blocks"]["lexico_grammar_question"] = default_sub_block_data.copy()
                            if "lexico_grammar_missing_word" not in lesson_stats["blocks"]:
                                lesson_stats["blocks"]["lexico_grammar_missing_word"] = default_sub_block_data.copy()

                            # Подблоки аудирования
                            if "listening_true_false" not in lesson_stats["blocks"]:
                                lesson_stats["blocks"]["listening_true_false"] = default_sub_block_data.copy()
                            if "listening_choice" not in lesson_stats["blocks"]:
                                lesson_stats["blocks"]["listening_choice"] = default_sub_block_data.copy()
                            if "listening_phrases" not in lesson_stats["blocks"]:
                                lesson_stats["blocks"]["listening_phrases"] = default_sub_block_data.copy()

                            # Подблоки письма
                            if "writing_sentences" not in lesson_stats["blocks"]:
                                lesson_stats["blocks"]["writing_sentences"] = default_sub_block_data.copy()
                            if "writing_translation" not in lesson_stats["blocks"]:
                                lesson_stats["blocks"]["writing_translation"] = default_sub_block_data.copy()

                            # Подблоки говорения
                            if "speaking_topics" not in lesson_stats["blocks"]:
                                lesson_stats["blocks"]["speaking_topics"] = default_sub_block_data.copy()


                except json.JSONDecodeError:
                    self.data = {}
        else:
            self.data = {}

    def _save_data(self):
        """Сохраняет данные статистики в файл."""
        print(f"DEBUG: Вход в _save_data. Путь файла: {self.data_file}") # НОВОЕ ОТЛАДОЧНОЕ СООБЩЕНИЕ
        try:
            os.makedirs(DATA_PATH, exist_ok=True)
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
            print(f"DEBUG: Данные успешно сохранены в {self.data_file}.") # НОВОЕ ОТЛАДОЧНОЕ СООБЩЕНИЕ
        except IOError as e:
            print(f"ERROR: Ошибка ввода/вывода при сохранении данных: {e}")
            print(traceback.format_exc())
        except Exception as e:
            print(f"ERROR: Неизвестная ошибка при сохранении данных: {e}")
            print(traceback.format_exc())
        print(f"DEBUG: Выход из _save_data.") # НОВОЕ ОТЛАДОЧНОЕ СООБЩЕНИЕ

    def get_user_stats(self, user_id: int):
        """Возвращает статистику для конкретного пользователя, инициализируя если нет."""
        user_id_str = str(user_id)
        if user_id_str not in self.data:
            self.data[user_id_str] = self._get_default_user_data_structure()
            self._save_data()
        return self.data[user_id_str]

    def _get_default_user_data_structure(self):
        """Возвращает структуру по умолчанию для нового пользователя (общая)."""
        return {
            "lessons": {},
            "total_lessons_completed": 0,
            "global_settings": {}
        }

    def _get_default_lesson_structure(self, lesson_id: str):
        """
        Возвращает структуру по умолчанию для нового урока.
        """
        return {
            "status": "in_progress",
            "blocks": {
                "terms": {"completed": False, "average_score": 0.0},
                "pronunciation": {"completed": False, "average_score": 0.0, "attempts": []},
                "lexical": {"completed": False, "average_score": 0.0},  # Общий блок лексики
                "lexical_en_to_ru": {"completed": False, "average_score": 0.0, "attempts": []},
                "lexical_ru_to_en": {"completed": False, "average_score": 0.0, "attempts": []},
                "lexical_word_build": {"completed": False, "average_score": 0.0, "attempts": []},
                "grammar": {"completed": False, "average_score": 0.0},
                # НОВЫЕ БЛОКИ ДЛЯ lexico_grammar
                "lexico_grammar": {"completed": False, "average_score": 0.0},  # Общий блок лексико-грамматики
                "lexico_grammar_verb": {"completed": False, "average_score": 0.0, "attempts": []},
                "lexico_grammar_mchoice": {"completed": False, "average_score": 0.0, "attempts": []},
                "lexico_grammar_negative": {"completed": False, "average_score": 0.0, "attempts": []},
                "lexico_grammar_question": {"completed": False, "average_score": 0.0, "attempts": []},
                "lexico_grammar_missing_word": {"completed": False, "average_score": 0.0, "attempts": []},
                # НОВЫЕ БЛОКИ ДЛЯ listening
                "listening": {"completed": False, "average_score": 0.0}, # Общий блок аудирования
                "listening_true_false": {"completed": False, "average_score": 0.0, "attempts": []},
                "listening_choice": {"completed": False, "average_score": 0.0, "attempts": []},
                "listening_phrases": {"completed": False, "average_score": 0.0, "attempts": []},
                # НОВЫЕ БЛОКИ ДЛЯ writing
                "writing": {"completed": False, "average_score": 0.0}, # Общий блок письменной речи
                "writing_sentences": {"completed": False, "average_score": 0.0, "attempts": []},
                "writing_translation": {"completed": False, "average_score": 0.0, "attempts": []},
                # НОВЫЕ БЛОКИ ДЛЯ speaking
                "speaking": {"completed": False, "average_score": 0.0}, # Общий блок говорения
                "speaking_topics": {"completed": False, "average_score": 0.0, "attempts": []},
            }
        }

    def get_lesson_stats(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID):
        """Получает статистику для конкретного урока пользователя, инициализируя если нет."""
        user_id_str = str(user_id)
        user_data = self.get_user_stats(user_id)
        if lesson_id not in user_data["lessons"]:
            user_data["lessons"][lesson_id] = self._get_default_lesson_structure(lesson_id)
            self._save_data()
        return user_data["lessons"][lesson_id]

    def update_block_status(self, user_id: int, block_name: str, completed: bool, average_score: float = None,
                            lesson_id: str = CURRENT_LESSON_ID):
        """Обновляет статус прохождения блока и его средний балл внутри конкретного урока."""
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)

        if block_name not in lesson_stats["blocks"]:
            # Инициализируем блок, если его нет
            lesson_stats["blocks"][block_name] = {"completed": False, "average_score": 0.0}
            if (block_name.startswith("lexical_") or
                block_name.startswith("lexico_grammar_") or
                block_name.startswith("listening_") or
                block_name.startswith("writing_") or
                block_name.startswith("speaking_")) and "attempts" not in \
                    lesson_stats["blocks"][block_name]:
                lesson_stats["blocks"][block_name]["attempts"] = []

        lesson_stats["blocks"][block_name]["completed"] = completed
        
        # Для блоков terms и grammar: если completed=True, то average_score=100.0
        if block_name in ["terms", "grammar"] and completed:
            lesson_stats["blocks"][block_name]["average_score"] = 100.0
        elif average_score is not None:
            lesson_stats["blocks"][block_name]["average_score"] = average_score
        self._save_data()

        # После обновления статуса подблока, проверяем и обновляем статус родительского блока
        if block_name.startswith("lexico_grammar_"):
            self._update_overall_lexico_grammar_status(user_id, lesson_id)
        elif block_name.startswith("lexical_") and block_name != "lexical": # Избегаем рекурсии для "lexical" общего
            self._update_overall_lexical_status(user_id, lesson_id)
        elif block_name.startswith("listening_") and block_name != "listening":
            self._update_overall_listening_status(user_id, lesson_id)
        elif block_name.startswith("writing_") and block_name != "writing":
            self._update_overall_writing_status(user_id, lesson_id)
        elif block_name.startswith("speaking_") and block_name != "speaking":
            self._update_overall_speaking_status(user_id, lesson_id)


    def add_pronunciation_attempt(self, user_id: int, word: str, score: float, lesson_id: str = CURRENT_LESSON_ID):
        """
        Добавляет/обновляет результат одной попытки произношения для конкретного слова
        в текущем блоке произношения текущего урока.
        """
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        pronunciation_block = lesson_stats["blocks"]["pronunciation"]

        if "attempts" not in pronunciation_block:
            pronunciation_block["attempts"] = []

        found = False
        for attempt in pronunciation_block["attempts"]:
            if attempt["word"] == word:
                attempt["score"] = score
                attempt["timestamp"] = datetime.now().isoformat()
                found = True
                break
        if not found:
            pronunciation_block["attempts"].append({
                "word": word,
                "score": score,
                "timestamp": datetime.now().isoformat()
            })
        self._save_data()

    def get_current_pronunciation_attempts(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID) -> list:
        """Возвращает список всех сохраненных попыток произношения для текущего урока."""
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        return lesson_stats["blocks"].get("pronunciation", {}).get("attempts", [])

    def calculate_average_pronunciation_score_for_block(self, user_id: int,
                                                        lesson_id: str = CURRENT_LESSON_ID) -> float:
        """
        Рассчитывает средний процент произношения для блока,
        учитывая только последний результат для каждого уникального слова.
        """
        attempts = self.get_current_pronunciation_attempts(user_id, lesson_id)

        last_scores = {}
        for attempt in attempts:
            last_scores[attempt["word"]] = attempt["score"]

        if not last_scores:
            return 0.0

        total_score = sum(last_scores.values())
        return total_score / len(last_scores)

    def mark_lesson_completed(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID):
        """Отмечает урок как завершенный и увеличивает общий счетчик."""
        user_data = self.get_user_stats(user_id)
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)

        if lesson_stats["status"] != "completed":
            lesson_stats["status"] = "completed"
            user_data["total_lessons_completed"] += 1
            print(
                f"DEBUG: Пользователь {user_id} завершил урок '{lesson_id}'. Всего уроков: {user_data['total_lessons_completed']}")
            self._save_data()
        else:
            print(f"DEBUG: Урок '{lesson_id}' для пользователя {user_id} уже был отмечен как завершенный.")

    def is_block_completed(self, user_id: int, block_name: str, lesson_id: str = CURRENT_LESSON_ID) -> bool:
        """Проверяет, пройден ли определенный блок для пользователя в конкретном уроке."""
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        # Проверяем, существует ли блок и имеет ли он ключ 'completed'
        if block_name in lesson_stats["blocks"]:
            return lesson_stats["blocks"][block_name].get("completed", False)
        # Если блок не существует, он не может быть завершен
        return False

    # --- Методы для лексического блока ---
    def add_lexical_attempt(self, user_id: int, sub_block_name: str, word: str, is_correct: bool,
                            lesson_id: str = CURRENT_LESSON_ID, user_result: str = None, user_message: str = None):
        """Добавляет попытку для конкретного слова в лексическом подблоке."""
        # Адаптировано для lexico_grammar и других блоков, использующих "attempts"
        block_key_prefix = ""
        if sub_block_name in ["en_to_ru", "ru_to_en", "word_build"]:
            block_key_prefix = "lexical_"
        elif sub_block_name in ["verb", "mchoice", "negative", "question", "missing_word"]:
            block_key_prefix = "lexico_grammar_"
        elif sub_block_name in ["sentences", "translation"]:
            block_key_prefix = "writing_"
        elif sub_block_name in ["topics"]:
            block_key_prefix = "speaking_"

        block_key = f"{block_key_prefix}{sub_block_name}"

        lesson_stats = self.get_lesson_stats(user_id, lesson_id)

        if block_key not in lesson_stats["blocks"]:
            lesson_stats["blocks"][block_key] = {"completed": False, "average_score": 0.0, "attempts": []}
        elif "attempts" not in lesson_stats["blocks"][block_key]:
            lesson_stats["blocks"][block_key]["attempts"] = []

        # Обновляем существующую попытку или добавляем новую
        found = False
        for attempt in lesson_stats["blocks"][block_key]["attempts"]:
            if attempt["word"] == word:
                attempt["is_correct"] = is_correct # Обновляем результат
                attempt["timestamp"] = datetime.now().isoformat()
                if user_result:
                    attempt["user_result"] = user_result
                if user_message:
                    attempt["user_message"] = user_message
                found = True
                break
        if not found:
            attempt_data = {
                "word": word,
                "is_correct": is_correct,
                "timestamp": datetime.now().isoformat()
            }
            if user_result:
                attempt_data["user_result"] = user_result
            if user_message:
                attempt_data["user_message"] = user_message
            lesson_stats["blocks"][block_key]["attempts"].append(attempt_data)
        self._save_data()

    def get_lexical_block_score(self, user_id: int, sub_block_name: str,
                                lesson_id: str = CURRENT_LESSON_ID) -> Tuple[int, int]:
        """
        Возвращает (количество_правильных_уникальных_слов, общее_количество_уникальных_слов)
        для заданного лексического подблока.
        Учитывается только последний результат для каждого уникального слова.
        """
        block_key_prefix = ""
        if sub_block_name in ["en_to_ru", "ru_to_en", "word_build"]:
            block_key_prefix = "lexical_"
        elif sub_block_name in ["verb", "mchoice", "negative", "question", "missing_word"]:
            block_key_prefix = "lexico_grammar_"
        elif sub_block_name in ["sentences", "translation"]:
            block_key_prefix = "writing_"
        elif sub_block_name in ["topics"]:
            block_key_prefix = "speaking_"

        block_key = f"{block_key_prefix}{sub_block_name}"

        lesson_stats = self.get_lesson_stats(user_id, lesson_id)

        lexical_data = lesson_stats["blocks"].get(block_key, {})
        
        # Сначала проверяем, есть ли прямые счетчики
        if "correct_count" in lexical_data and "total_count" in lexical_data:
            return lexical_data["correct_count"], lexical_data["total_count"]
        
        # Если нет прямых счетчиков, используем попытки
        attempts = lexical_data.get("attempts", [])

        unique_correct_words = set()
        unique_total_words = set()

        # Собираем только последние попытки для каждого слова
        latest_attempts = {}
        for attempt in attempts:
            latest_attempts[attempt["word"]] = attempt["is_correct"]

        for word, is_correct in latest_attempts.items():
            unique_total_words.add(word)
            if is_correct:
                unique_correct_words.add(word)

        return len(unique_correct_words), len(unique_total_words)

    def get_overall_lexical_score(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID) -> float:
        """
        Рассчитывает общий средний балл по основным лексическим подблокам (en_to_ru, ru_to_en, word_build).
        """
        sub_blocks = ["en_to_ru", "ru_to_en", "word_build"]

        total_correct_all_lexical = 0
        total_questions_all_lexical = 0

        for sb_name in sub_blocks:
            correct, total = self.get_lexical_block_score(user_id, sb_name, lesson_id)
            total_correct_all_lexical += correct
            total_questions_all_lexical += total

        if total_questions_all_lexical == 0:
            return 0.0
        return (total_correct_all_lexical / total_questions_all_lexical) * 100

    def _update_overall_lexical_status(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID):
        """
        Проверяет, завершены ли все подблоки лексики, и обновляет статус общего блока "lexical".
        Также обновляет средний балл общего блока.
        """
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        sub_blocks = ["lexical_en_to_ru", "lexical_ru_to_en", "lexical_word_build"]

        all_sub_blocks_completed = True
        for sb_name in sub_blocks:
            if not lesson_stats["blocks"].get(sb_name, {}).get("completed", False):
                all_sub_blocks_completed = False
                break

        overall_score = self.get_overall_lexical_score(user_id, lesson_id)
        self.update_block_status(user_id, "lexical", all_sub_blocks_completed, overall_score, lesson_id)
        self._save_data() # Сохраняем после обновления общего блока

    def get_overall_lexico_grammar_score(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID) -> float:
        """
        Рассчитывает общий средний балл по всем подблокам лексико-грамматического блока.
        """
        sub_blocks = ["verb", "mchoice", "negative", "question", "missing_word"]  # Все подблоки lexico_grammar

        total_correct_all_lexico_grammar = 0
        total_questions_all_lexico_grammar = 0

        for sb_name in sub_blocks:
            # Используем get_lexical_block_score, так как она универсальна для подсчета правильных/всего
            correct, total = self.get_lexical_block_score(user_id, sb_name, lesson_id)
            total_correct_all_lexico_grammar += correct
            total_questions_all_lexico_grammar += total

        if total_questions_all_lexico_grammar == 0:
            return 0.0
        return (total_correct_all_lexico_grammar / total_questions_all_lexico_grammar) * 100

    def _update_overall_lexico_grammar_status(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID):
        """
        Проверяет, завершены ли все подблоки лексико-грамматики, и обновляет статус общего блока "lexico_grammar".
        Также обновляет средний балл общего блока.
        """
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        sub_blocks = ["lexico_grammar_verb", "lexico_grammar_mchoice", "lexico_grammar_negative",
                      "lexico_grammar_question", "lexico_grammar_missing_word"]

        all_sub_blocks_completed = True
        for sb_name in sub_blocks:
            if not lesson_stats["blocks"].get(sb_name, {}).get("completed", False):
                all_sub_blocks_completed = False
                break

        overall_score = self.get_overall_lexico_grammar_score(user_id, lesson_id)
        self.update_block_status(user_id, "lexico_grammar", all_sub_blocks_completed, overall_score, lesson_id)
        self._save_data() # Сохраняем после обновления общего блока

    # --- Новые методы для блока аудирования ---
    def add_listening_attempt(self, user_id: int, sub_block_name: str, item_id: str, is_correct: bool,
                              lesson_id: str = CURRENT_LESSON_ID, score: float = None, user_result: str = None, user_message: str = None):
        """
        Добавляет или обновляет попытку для элемента в подблоке аудирования.
        Если item_id уже существует, обновляет его.
        """
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        block_key = f"listening_{sub_block_name}"

        if block_key not in lesson_stats["blocks"]:
            lesson_stats["blocks"][block_key] = {"completed": False, "average_score": 0.0, "attempts": []}
        elif "attempts" not in lesson_stats["blocks"][block_key]:
            lesson_stats["blocks"][block_key]["attempts"] = []

        attempts = lesson_stats["blocks"][block_key]["attempts"]

        found = False
        for attempt in attempts:
            if attempt["item_id"] == item_id:
                attempt["is_correct"] = is_correct
                if score is not None:
                    attempt["score"] = score # Для произношения фраз
                attempt["timestamp"] = datetime.now().isoformat()
                if user_result:
                    attempt["user_result"] = user_result
                if user_message:
                    attempt["user_message"] = user_message
                found = True
                break
        if not found:
            new_attempt = {
                "item_id": item_id,
                "is_correct": is_correct,
                "timestamp": datetime.now().isoformat()
            }
            if score is not None:
                new_attempt["score"] = score
            if user_result:
                new_attempt["user_result"] = user_result
            if user_message:
                new_attempt["user_message"] = user_message
            attempts.append(new_attempt)
        self._save_data()

    def get_listening_block_score(self, user_id: int, sub_block_name: str,
                                  lesson_id: str = CURRENT_LESSON_ID) -> Tuple[int, int]:
        """
        Возвращает (количество_правильных_уникальных_элементов, общее_количество_уникальных_элементов)
        для заданного подблока аудирования.
        Учитывается только последний результат для каждого item_id.
        """
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        block_key = f"listening_{sub_block_name}"

        listening_data = lesson_stats["blocks"].get(block_key, {})
        
        # Сначала проверяем, есть ли прямые счетчики
        if "correct_count" in listening_data and "total_count" in listening_data:
            return listening_data["correct_count"], listening_data["total_count"]
        
        # Если нет прямых счетчиков, используем попытки
        attempts = listening_data.get("attempts", [])

        unique_correct_items = set()
        unique_total_items = set()

        latest_results = {} # Словарь для хранения последних результатов по item_id
        for attempt in attempts:
            latest_results[attempt["item_id"]] = attempt["is_correct"]

        for item_id, is_correct in latest_results.items():
            unique_total_items.add(item_id)
            if is_correct:
                unique_correct_items.add(item_id)

        return len(unique_correct_items), len(unique_total_items)

    def get_listening_phrases_score(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID) -> Tuple[int, int]:
        """
        Возвращает (количество_правильных_уникальных_фраз, общее_количество_уникальных_фраз)
        для подблока listening_phrases, используя поле 'score'.
        """
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        block_key = "listening_phrases"

        listening_data = lesson_stats["blocks"].get(block_key, {})
        attempts = listening_data.get("attempts", [])

        unique_phrases_latest_score = {} # {item_id: score}

        for attempt in attempts:
            if "score" in attempt: # Убедимся, что это попытка с произношением
                unique_phrases_latest_score[attempt["item_id"]] = attempt["score"]

        correct_count = 0
        total_count = len(unique_phrases_latest_score)

        for score in unique_phrases_latest_score.values():
            if score >= 68.0: # Порог успешности произношения
                correct_count += 1

        return correct_count, total_count

    def get_overall_listening_score(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID) -> float:
        """
        Рассчитывает общий средний балл по всем подблокам аудирования.
        """
        sub_blocks = ["true_false", "choice"] # Для этих блоков используем is_correct

        total_correct_all_listening = 0
        total_questions_all_listening = 0

        for sb_name in sub_blocks:
            correct, total = self.get_listening_block_score(user_id, sb_name, lesson_id)
            total_correct_all_listening += correct
            total_questions_all_listening += total

        # Отдельно обрабатываем listening_phrases, так как у него score, а не is_correct
        phrases_correct, phrases_total = self.get_listening_phrases_score(user_id, lesson_id)
        total_correct_all_listening += phrases_correct
        total_questions_all_listening += phrases_total


        if total_questions_all_listening == 0:
            return 0.0
        return (total_correct_all_listening / total_questions_all_listening) * 100

    def _update_overall_listening_status(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID):
        """
        Проверяет, завершены ли все подблоки аудирования, и обновляет статус общего блока "listening".
        Также обновляет средний балл общего блока.
        """
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        sub_blocks = ["listening_true_false", "listening_choice", "listening_phrases"]

        all_sub_blocks_completed = True
        for sb_name in sub_blocks:
            if not lesson_stats["blocks"].get(sb_name, {}).get("completed", False):
                all_sub_blocks_completed = False
                break

        overall_score = self.get_overall_listening_score(user_id, lesson_id)
        self.update_block_status(user_id, "listening", all_sub_blocks_completed, overall_score, lesson_id)
        self._save_data()

    # --- Новые методы для блока письменной речи ---
    def add_writing_attempt(self, user_id: int, sub_block_name: str, item_id: str, is_correct: bool,
                            lesson_id: str = CURRENT_LESSON_ID, user_result: str = None, user_message: str = None):
        """
        Добавляет или обновляет попытку для элемента в подблоке письменной речи.
        """
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        block_key = f"writing_{sub_block_name}"

        if block_key not in lesson_stats["blocks"]:
            lesson_stats["blocks"][block_key] = {"completed": False, "average_score": 0.0, "attempts": []}
        elif "attempts" not in lesson_stats["blocks"][block_key]:
            lesson_stats["blocks"][block_key]["attempts"] = []

        attempts = lesson_stats["blocks"][block_key]["attempts"]

        found = False
        for attempt in attempts:
            if attempt["item_id"] == item_id:
                attempt["is_correct"] = is_correct
                attempt["timestamp"] = datetime.now().isoformat()
                if user_result:
                    attempt["user_result"] = user_result
                if user_message:
                    attempt["user_message"] = user_message
                found = True
                break
        if not found:
            new_attempt = {
                "item_id": item_id,
                "is_correct": is_correct,
                "timestamp": datetime.now().isoformat()
            }
            if user_result:
                new_attempt["user_result"] = user_result
            if user_message:
                new_attempt["user_message"] = user_message
            attempts.append(new_attempt)
        self._save_data()

    def get_writing_block_score(self, user_id: int, sub_block_name: str,
                                lesson_id: str = CURRENT_LESSON_ID) -> Tuple[int, int]:
        """
        Возвращает (количество_правильных_уникальных_элементов, общее_количество_уникальных_элементов)
        для заданного подблока письменной речи.
        """
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        block_key = f"writing_{sub_block_name}"

        writing_data = lesson_stats["blocks"].get(block_key, {})
        
        # Сначала проверяем, есть ли прямые счетчики
        if "correct_count" in writing_data and "total_count" in writing_data:
            return writing_data["correct_count"], writing_data["total_count"]
        
        # Если нет прямых счетчиков, используем попытки
        attempts = writing_data.get("attempts", [])

        unique_correct_items = set()
        unique_total_items = set()

        latest_results = {}
        for attempt in attempts:
            latest_results[attempt["item_id"]] = attempt["is_correct"]

        for item_id, is_correct in latest_results.items():
            unique_total_items.add(item_id)
            if is_correct:
                unique_correct_items.add(item_id)

        return len(unique_correct_items), len(unique_total_items)

    def get_overall_writing_score(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID) -> float:
        """
        Рассчитывает общий средний балл по всем подблокам письменной речи.
        """
        sub_blocks = ["sentences", "translation"]

        total_correct_all_writing = 0
        total_questions_all_writing = 0

        for sb_name in sub_blocks:
            correct, total = self.get_writing_block_score(user_id, sb_name, lesson_id)
            total_correct_all_writing += correct
            total_questions_all_writing += total

        if total_questions_all_writing == 0:
            return 0.0
        return (total_correct_all_writing / total_questions_all_writing) * 100

    def _update_overall_writing_status(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID):
        """
        Проверяет, завершены ли все подблоки письменной речи, и обновляет статус общего блока "writing".
        Также обновляет средний балл общего блока.
        """
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        sub_blocks = ["writing_sentences", "writing_translation"]

        all_sub_blocks_completed = True
        for sb_name in sub_blocks:
            if not lesson_stats["blocks"].get(sb_name, {}).get("completed", False):
                all_sub_blocks_completed = False
                break

        overall_score = self.get_overall_writing_score(user_id, lesson_id)
        self.update_block_status(user_id, "writing", all_sub_blocks_completed, overall_score, lesson_id)
        self._save_data()

    # --- Новые методы для блока говорения ---
    def add_speaking_attempt(self, user_id: int, sub_block_name: str, item_id: str, is_correct: bool,
                             lesson_id: str = CURRENT_LESSON_ID, user_result: str = None):
        """
        Добавляет или обновляет попытку для элемента в подблоке говорения.
        """
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        block_key = f"speaking_{sub_block_name}"

        if block_key not in lesson_stats["blocks"]:
            lesson_stats["blocks"][block_key] = {"completed": False, "average_score": 0.0, "attempts": []}
        elif "attempts" not in lesson_stats["blocks"][block_key]:
            lesson_stats["blocks"][block_key]["attempts"] = []

        attempts = lesson_stats["blocks"][block_key]["attempts"]

        found = False
        for attempt in attempts:
            if attempt["item_id"] == item_id:
                attempt["is_correct"] = is_correct
                attempt["timestamp"] = datetime.now().isoformat()
                if user_result:
                    attempt["user_result"] = user_result
                found = True
                break
        if not found:
            new_attempt = {
                "item_id": item_id,
                "is_correct": is_correct,
                "timestamp": datetime.now().isoformat()
            }
            if user_result:
                new_attempt["user_result"] = user_result
            attempts.append(new_attempt)
        self._save_data()

    def get_speaking_block_score(self, user_id: int, sub_block_name: str,
                                 lesson_id: str = CURRENT_LESSON_ID) -> Tuple[int, int]:
        """
        Возвращает (количество_правильных_уникальных_элементов, общее_количество_уникальных_элементов)
        для заданного подблока говорения.
        """
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        block_key = f"speaking_{sub_block_name}"

        speaking_data = lesson_stats["blocks"].get(block_key, {})
        
        # Сначала проверяем, есть ли прямые счетчики
        if "correct_count" in speaking_data and "total_count" in speaking_data:
            return speaking_data["correct_count"], speaking_data["total_count"]
        
        # Если нет прямых счетчиков, используем попытки
        attempts = speaking_data.get("attempts", [])

        unique_correct_items = set()
        unique_total_items = set()

        latest_results = {}
        for attempt in attempts:
            latest_results[attempt["item_id"]] = attempt["is_correct"]

        for item_id, is_correct in latest_results.items():
            unique_total_items.add(item_id)
            if is_correct:
                unique_correct_items.add(item_id)

        return len(unique_correct_items), len(unique_total_items)

    def get_overall_speaking_score(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID) -> float:
        """
        Рассчитывает общий средний балл по всем подблокам говорения.
        """
        sub_blocks = ["topics"]

        total_correct_all_speaking = 0
        total_questions_all_speaking = 0

        for sb_name in sub_blocks:
            correct, total = self.get_speaking_block_score(user_id, sb_name, lesson_id)
            total_correct_all_speaking += correct
            total_questions_all_speaking += total

        if total_questions_all_speaking == 0:
            return 0.0
        return (total_correct_all_speaking / total_questions_all_speaking) * 100

    def _update_overall_speaking_status(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID):
        """
        Проверяет, завершены ли все подблоки говорения, и обновляет статус общего блока "speaking".
        Также обновляет средний балл общего блока.
        """
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        sub_blocks = ["speaking_topics"]

        all_sub_blocks_completed = True
        for sb_name in sub_blocks:
            if not lesson_stats["blocks"].get(sb_name, {}).get("completed", False):
                all_sub_blocks_completed = False
                break

        overall_score = self.get_overall_speaking_score(user_id, lesson_id)
        self.update_block_status(user_id, "speaking", all_sub_blocks_completed, overall_score, lesson_id)
        self._save_data()

    def _check_and_mark_lesson_completed(self, user_id: int, lesson_id: str):
        """
        Проверяет, завершены ли все требуемые основные блоки в уроке,
        и отмечает урок как завершенный, если это так.
        """
        print(f"DEBUG: Вызвана _check_and_mark_lesson_completed для пользователя {user_id}, урок {lesson_id}.")
        try:
            lesson_stats = self.get_lesson_stats(user_id, lesson_id)
            print(f"DEBUG: Статус урока '{lesson_id}' для пользователя {user_id}: {lesson_stats['status']}.")

            # Определите все требуемые ОСНОВНЫЕ блоки для полного завершения урока
            required_blocks = [
                "terms",
                "pronunciation",
                "lexical",
                "grammar",
                "lexico_grammar",
                "listening",
                "writing",
                "speaking"
            ]

            if lesson_stats["status"] == "completed":
                print(f"DEBUG: Урок {lesson_id} уже завершен для пользователя {user_id}. Возврат.")
                return

            all_required_blocks_completed = True
            for block_name in required_blocks:
                is_completed = self.is_block_completed(user_id, block_name, lesson_id)
                print(f"DEBUG: Проверка блока '{block_name}': Завершен = {is_completed}.")
                if not is_completed:
                    all_required_blocks_completed = False
                    print(f"DEBUG: Блок '{block_name}' не завершен для пользователя {user_id}.")
                    # Если какой-то обязательный блок не завершен, то и урок не может быть завершен
                    break

            if all_required_blocks_completed:
                print(f"DEBUG: Все необходимые блоки завершены для пользователя {user_id}. Отмечаем урок как завершенный.")
                self.mark_lesson_completed(user_id, lesson_id)
            else:
                print(f"DEBUG: Не все необходимые блоки завершены для пользователя {user_id}. Урок не отмечен как завершенный.")
        except Exception as e:
            print(f"ERROR: Ошибка в _check_and_mark_lesson_completed для пользователя {user_id}: {e}")
            print(traceback.format_exc())


    def init_lesson_block_data(self, user_id: int, lesson_id: str, block_name: str, sub_block_name: str = None):
        """Инициализирует данные для подблока внутри основного блока."""
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        if block_name not in lesson_stats["blocks"]:
            lesson_stats["blocks"][block_name] = {"completed": False, "average_score": 0.0}

        if sub_block_name:
            full_sub_block_name = f"{block_name}_{sub_block_name}"
            if full_sub_block_name not in lesson_stats["blocks"]:
                lesson_stats["blocks"][full_sub_block_name] = {"completed": False, "average_score": 0.0,
                                                               "attempts": []}
        self._save_data()

    def update_block_score(self, user_id: int, lesson_id: str, block_name: str, sub_block_name: str, score: int,
                           total: int):
        """Обновляет счет для конкретного подблока."""
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        full_sub_block_name = f"{block_name}_{sub_block_name}"

        if full_sub_block_name not in lesson_stats["blocks"]:
            self.init_lesson_block_data(user_id, lesson_id, block_name, sub_block_name)

        # Сохраняем счет как средний процент
        average_score = (score / total) * 100 if total > 0 else 0.0
        lesson_stats["blocks"][full_sub_block_name]["average_score"] = average_score

        # Для упражнений с подсчетом правильных/всего
        lesson_stats["blocks"][full_sub_block_name]["correct_count"] = score
        lesson_stats["blocks"][full_sub_block_name]["total_count"] = total

        self._save_data()

        # После обновления счета подблока, проверяем и обновляем статус родительского блока
        if block_name == "lexico_grammar":
            self._update_overall_lexico_grammar_status(user_id, lesson_id)
        elif block_name == "lexical":
            self._update_overall_lexical_status(user_id, lesson_id)
        elif block_name == "listening":
            self._update_overall_listening_status(user_id, lesson_id)
        elif block_name == "writing":
            self._update_overall_writing_status(user_id, lesson_id)
        elif block_name == "speaking":
            self._update_overall_speaking_status(user_id, lesson_id)


    def mark_block_completed(self, user_id: int, lesson_id: str, block_name: str, sub_block_name: str = None,
                             completed: bool = True):
        """Отмечает блок или подблок как завершенный."""
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)

        if sub_block_name:
            full_sub_block_name = f"{block_name}_{sub_block_name}"
            if full_sub_block_name not in lesson_stats["blocks"]:
                self.init_lesson_block_data(user_id, lesson_id, block_name, sub_block_name)
            lesson_stats["blocks"][full_sub_block_name]["completed"] = completed
        else:
            if block_name not in lesson_stats["blocks"]:
                lesson_stats["blocks"][block_name] = {"completed": False, "average_score": 0.0}
            lesson_stats["blocks"][block_name]["completed"] = completed
        self._save_data()

        # После отметки подблока как завершенного, проверяем и обновляем статус родительского блока
        if sub_block_name and block_name == "lexico_grammar":
            self._update_overall_lexico_grammar_status(user_id, lesson_id)
        elif sub_block_name and block_name == "lexical":
            self._update_overall_lexical_status(user_id, lesson_id)
        elif sub_block_name and block_name == "listening":
            self._update_overall_listening_status(user_id, lesson_id)
        elif sub_block_name and block_name == "writing":
            self._update_overall_writing_status(user_id, lesson_id)
        elif sub_block_name and block_name == "speaking":
            self._update_overall_speaking_status(user_id, lesson_id)

        # Если это основной блок, то сразу проверяем завершение урока
        if not sub_block_name:
            self._check_and_mark_lesson_completed(user_id, lesson_id)

    # --- Новые методы для сбора детальной статистики ---
    
    def save_pronunciation_data(self, user_id: int, word: str, user_phonemes: str, 
                               expected_phonemes: str, accuracy: float):
        """
        Сохраняет детальные данные о произношении пользователя в существующую структуру attempts.
        
        Args:
            user_id: ID пользователя
            word: слово для произношения
            user_phonemes: фонемы, произнесенные пользователем
            expected_phonemes: ожидаемые фонемы
            accuracy: точность произношения (0.0-100.0)
        """
        lesson_stats = self.get_lesson_stats(user_id)
        
        # Находим существующую попытку для этого слова
        pronunciation_attempts = lesson_stats.get("blocks", {}).get("pronunciation", {}).get("attempts", [])
        
        # Ищем последнюю попытку для этого слова
        for attempt in reversed(pronunciation_attempts):
            if attempt.get("word") == word:
                # Добавляем фонемы к существующей попытке
                attempt["user_phonemes"] = user_phonemes
                attempt["expected_phonemes"] = expected_phonemes
                break
        else:
            # Если попытка не найдена, создаем новую
            new_attempt = {
                "word": word,
                "score": accuracy,
                "timestamp": datetime.now().isoformat(),
                "user_phonemes": user_phonemes,
                "expected_phonemes": expected_phonemes
            }
            pronunciation_attempts.append(new_attempt)
        
        self._save_data()
        
        print(f"DEBUG: Сохранены фонемы произношения для пользователя {user_id}: "
              f"слово '{word}', пользователь: '{user_phonemes}', ожидаемые: '{expected_phonemes}'")

    def save_speaking_dialogue(self, user_id: int, user_message: str, gpt_response: str, 
                              topic: str = None, dialogue_id: str = None):
        """
        Сохраняет диалог между пользователем и GPT в блоке говорения.
        
        Args:
            user_id: ID пользователя
            user_message: сообщение пользователя
            gpt_response: ответ GPT
            topic: тема диалога (опционально)
            dialogue_id: ID диалога для группировки сообщений
        """
        lesson_stats = self.get_lesson_stats(user_id)
        
        # Инициализируем структуру для диалогов говорения
        if "speaking_dialogues" not in lesson_stats:
            lesson_stats["speaking_dialogues"] = []
        
        # Если есть dialogue_id, ищем существующий диалог
        existing_dialogue = None
        if dialogue_id:
            for dialogue in lesson_stats["speaking_dialogues"]:
                if dialogue.get("dialogue_id") == dialogue_id:
                    existing_dialogue = dialogue
                    break
        
        if existing_dialogue:
            # Добавляем сообщение к существующему диалогу
            if "messages" not in existing_dialogue:
                existing_dialogue["messages"] = []
            
            existing_dialogue["messages"].append({
                "timestamp": datetime.now().isoformat(),
                "user_message": user_message,
                "gpt_response": gpt_response
            })
            existing_dialogue["dialogue_length"] = len(existing_dialogue["messages"])
        else:
            # Создаем новый диалог
            dialogue_record = {
                "dialogue_id": dialogue_id or f"dialogue_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "timestamp": datetime.now().isoformat(),
                "topic": topic,
                "messages": [{
                    "timestamp": datetime.now().isoformat(),
                    "user_message": user_message,
                    "gpt_response": gpt_response
                }],
                "dialogue_length": 1
            }
            
            lesson_stats["speaking_dialogues"].append(dialogue_record)
        
        self._save_data()
        
        print(f"DEBUG: Сохранен диалог говорения для пользователя {user_id}: "
              f"тема '{topic}', сообщение пользователя: '{user_message[:50]}...'")



    def get_speaking_statistics(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID) -> Dict[str, Any]:
        """
        Возвращает детальную статистику по говорению.
        
        Returns:
            Словарь с статистикой говорения
        """
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        speaking_dialogues = lesson_stats.get("speaking_dialogues", [])
        
        if not speaking_dialogues:
            return {
                "total_dialogues": 0,
                "total_messages": 0,
                "average_dialogue_length": 0.0,
                "topics_covered": [],
                "recent_dialogues": []
            }
        
        # Подсчет статистики
        total_dialogues = len(speaking_dialogues)
        total_messages = sum(d.get("dialogue_length", 1) for d in speaking_dialogues)
        average_dialogue_length = total_messages / total_dialogues if total_dialogues > 0 else 0
        
        # Темы диалогов
        topics_covered = list(set(d["topic"] for d in speaking_dialogues if d.get("topic")))
        
        # Последние диалоги (последние 5)
        recent_dialogues = sorted(speaking_dialogues, key=lambda x: x["timestamp"], reverse=True)[:5]
        
        return {
            "total_dialogues": total_dialogues,
            "total_messages": total_messages,
            "average_dialogue_length": round(average_dialogue_length, 2),
            "topics_covered": topics_covered,
            "recent_dialogues": recent_dialogues
        }

    def get_exercise_statistics(self, user_id: int, exercise_type: str, lesson_id: str = CURRENT_LESSON_ID) -> Dict[str, Any]:
        """
        Возвращает детальную статистику по конкретному типу упражнений.
        
        Args:
            user_id: ID пользователя
            exercise_type: тип упражнения (pronunciation, speaking, lexical, etc.)
            lesson_id: ID урока
            
        Returns:
            Словарь с детальной статистикой
        """
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        
        if exercise_type == "pronunciation":
            return self.get_pronunciation_statistics(user_id, lesson_id)
        elif exercise_type == "speaking":
            return self.get_speaking_statistics(user_id, lesson_id)
        else:
            # Для других типов упражнений возвращаем базовую статистику
            block_data = lesson_stats["blocks"].get(exercise_type, {})
            attempts = block_data.get("attempts", [])
            
            return {
                "total_attempts": len(attempts),
                "completed": block_data.get("completed", False),
                "average_score": block_data.get("average_score", 0.0),
                "recent_attempts": attempts[-10:] if attempts else []
            }

    def get_user_activity_timeline(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID) -> List[Dict[str, Any]]:
        """
        Возвращает временную шкалу активности пользователя.
        
        Returns:
            Список событий активности, отсортированных по времени
        """
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        timeline = []
        
        # Добавляем попытки произношения из blocks.pronunciation.attempts
        pronunciation_attempts = lesson_stats.get("blocks", {}).get("pronunciation", {}).get("attempts", [])
        for p in pronunciation_attempts:
            # Определяем результат на основе точности
            score = p.get("score", 0)
            if score >= 85.0:
                result = "correct"
            elif score < 68.0:
                result = "incorrect"
            else:
                result = "partially_correct"
                
            timeline.append({
                "timestamp": p["timestamp"],
                "activity_type": "pronunciation",
                "word": p["word"],
                "result": result,
                "accuracy": score,
                "user_phonemes": p.get("user_phonemes"),
                "expected_phonemes": p.get("expected_phonemes")
            })
        
        # Добавляем диалоги говорения
        speaking_dialogues = lesson_stats.get("speaking_dialogues", [])
        for d in speaking_dialogues:
            timeline.append({
                "timestamp": d["timestamp"],
                "activity_type": "speaking",
                "topic": d.get("topic"),
                "dialogue_length": d.get("dialogue_length", 1)
            })
            
            # Добавляем отдельные сообщения из диалога
            messages = d.get("messages", [])
            for msg in messages:
                timeline.append({
                    "timestamp": msg["timestamp"],
                    "activity_type": "speaking_message",
                    "topic": d.get("topic"),
                    "message_length": len(msg.get("user_message", ""))
                })
        
        # Добавляем попытки других упражнений
        for block_name, block_data in lesson_stats["blocks"].items():
            attempts = block_data.get("attempts", [])
            for attempt in attempts:
                timeline.append({
                    "timestamp": attempt["timestamp"],
                    "activity_type": block_name,
                    "item": attempt.get("word", attempt.get("item_id", "unknown")),
                    "result": attempt.get("is_correct", attempt.get("score", "unknown"))
                })
        
        # Сортируем по времени (новые сначала)
        timeline.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return timeline

    def get_user_progress_summary(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID) -> Dict[str, Any]:
        """
        Возвращает общую сводку прогресса пользователя.
        
        Returns:
            Словарь с общей сводкой прогресса
        """
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        
        # Подсчет завершенных блоков
        completed_blocks = sum(1 for block_data in lesson_stats["blocks"].values() 
                              if block_data.get("completed", False))
        total_blocks = len(lesson_stats["blocks"])
        
        # Общий средний балл
        total_score = sum(block_data.get("average_score", 0.0) for block_data in lesson_stats["blocks"].values())
        overall_average = total_score / total_blocks if total_blocks > 0 else 0.0
        
        # Статистика активности
        pronunciation_attempts = len(lesson_stats.get("blocks", {}).get("pronunciation", {}).get("attempts", []))
        speaking_stats = self.get_speaking_statistics(user_id, lesson_id)
        
        return {
            "lesson_status": lesson_stats["status"],
            "completed_blocks": completed_blocks,
            "total_blocks": total_blocks,
            "completion_percentage": round((completed_blocks / total_blocks) * 100, 2) if total_blocks > 0 else 0.0,
            "overall_average_score": round(overall_average, 2),
            "pronunciation_attempts": pronunciation_attempts,
            "speaking_dialogues": speaking_stats["total_dialogues"],
            "last_activity": lesson_stats.get("last_activity", "unknown")
        }



    def get_speaking_fluency_analysis(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID) -> Dict[str, Any]:
        """
        Анализирует беглость речи пользователя.
        
        Returns:
            Словарь с анализом беглости речи
        """
        speaking_stats = self.get_speaking_statistics(user_id, lesson_id)
        dialogues = speaking_stats.get("recent_dialogues", [])
        
        fluency_data = {
            "total_dialogues": len(dialogues),
            "average_response_length": 0,
            "vocabulary_diversity": set(),
            "grammar_accuracy": 0,
            "topics_covered": speaking_stats.get("topics_covered", []),
            "suggested_improvements": []
        }
        
        if dialogues:
            # Анализируем длину ответов
            response_lengths = []
            for dialogue in dialogues:
                user_message = dialogue.get("user_message", "")
                response_lengths.append(len(user_message.split()))
                # Добавляем слова в словарь
                fluency_data["vocabulary_diversity"].update(user_message.lower().split())
            
            fluency_data["average_response_length"] = sum(response_lengths) / len(response_lengths)
            fluency_data["vocabulary_diversity"] = len(fluency_data["vocabulary_diversity"])
            
            # Простая оценка грамматики (можно улучшить)
            fluency_data["grammar_accuracy"] = 85.0  # Заглушка
            
            # Предложения по улучшению
            if fluency_data["average_response_length"] < 5:
                fluency_data["suggested_improvements"].append("Попробуйте давать более развернутые ответы")
            if fluency_data["vocabulary_diversity"] < 20:
                fluency_data["suggested_improvements"].append("Используйте больше разнообразных слов")
        
        return fluency_data

    def get_learning_patterns(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID) -> Dict[str, Any]:
        """
        Анализирует паттерны обучения пользователя.
        
        Returns:
            Словарь с паттернами обучения
        """
        timeline = self.get_user_activity_timeline(user_id, lesson_id)
        
        patterns = {
            "total_sessions": 0,
            "average_session_duration": 0,
            "preferred_exercise_types": {},
            "peak_activity_hours": {},
            "learning_consistency": "unknown"
        }
        
        if timeline:
            # Группируем по дням для определения сессий
            from collections import defaultdict
            daily_activities = defaultdict(list)
            
            for event in timeline:
                timestamp = event["timestamp"]
                date = timestamp.split("T")[0]
                daily_activities[date].append(event)
                
                # Подсчитываем типы упражнений
                activity_type = event["activity_type"]
                patterns["preferred_exercise_types"][activity_type] = \
                    patterns["preferred_exercise_types"].get(activity_type, 0) + 1
                
                # Анализируем часы активности
                hour = int(timestamp.split("T")[1].split(":")[0])
                patterns["peak_activity_hours"][hour] = \
                    patterns["peak_activity_hours"].get(hour, 0) + 1
            
            patterns["total_sessions"] = len(daily_activities)
            
            # Определяем консистентность
            if patterns["total_sessions"] >= 5:
                patterns["learning_consistency"] = "high"
            elif patterns["total_sessions"] >= 3:
                patterns["learning_consistency"] = "medium"
            else:
                patterns["learning_consistency"] = "low"
        
        return patterns

    def export_user_data(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID) -> Dict[str, Any]:
        """
        Экспортирует все данные пользователя для анализа.
        
        Returns:
            Полный набор данных пользователя
        """
        return {
            "user_id": user_id,
            "lesson_id": lesson_id,
            "progress_summary": self.get_user_progress_summary(user_id, lesson_id),
            "pronunciation_stats": self.get_pronunciation_statistics(user_id, lesson_id),
            "speaking_stats": self.get_speaking_statistics(user_id, lesson_id),
            "pronunciation_improvement": self.get_pronunciation_improvement_analysis(user_id, lesson_id),
            "speaking_fluency": self.get_speaking_fluency_analysis(user_id, lesson_id),
            "learning_patterns": self.get_learning_patterns(user_id, lesson_id),
            "activity_timeline": self.get_user_activity_timeline(user_id, lesson_id),
            "lesson_data": self.get_lesson_stats(user_id, lesson_id)
        }

    def get_recommendations(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID) -> List[str]:
        """
        Генерирует персональные рекомендации для пользователя.
        
        Returns:
            Список рекомендаций
        """
        recommendations = []
        
        # Анализируем данные
        progress_summary = self.get_user_progress_summary(user_id, lesson_id)
        pronunciation_improvement = self.get_pronunciation_improvement_analysis(user_id, lesson_id)
        speaking_fluency = self.get_speaking_fluency_analysis(user_id, lesson_id)
        learning_patterns = self.get_learning_patterns(user_id, lesson_id)
        
        # Рекомендации по произношению
        if pronunciation_improvement["words_needing_attention"]:
            recommendations.append("Практикуйте произношение слов, которые вызывают трудности")
        
        if pronunciation_improvement["words_with_improvement"] < len(pronunciation_improvement["total_words_practiced"]) / 2:
            recommendations.append("Повторяйте упражнения по произношению для закрепления навыков")
        
        # Рекомендации по говорению
        if speaking_fluency["average_response_length"] < 5:
            recommendations.append("Попробуйте давать более развернутые ответы в упражнениях по говорению")
        
        if len(speaking_fluency["topics_covered"]) < 3:
            recommendations.append("Изучите больше тем для расширения словарного запаса")
        
        # Рекомендации по обучению
        if learning_patterns["learning_consistency"] == "low":
            recommendations.append("Старайтесь заниматься регулярно для лучшего прогресса")
        
        if not recommendations:
            recommendations.append("Отличная работа! Продолжайте в том же духе")
        
        return recommendations


    def clear_user_data(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID):
        """
        Очищает все данные пользователя для конкретного урока.
        Используйте с осторожностью!
        """
        user_id_str = str(user_id)
        if user_id_str in self.data and lesson_id in self.data[user_id_str]["lessons"]:
            del self.data[user_id_str]["lessons"][lesson_id]
            self._save_data()
            print(f"DEBUG: Данные пользователя {user_id} для урока {lesson_id} очищены")

    def backup_user_data(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID) -> Dict[str, Any]:
        """
        Создает резервную копию данных пользователя.
        
        Returns:
            Резервная копия данных
        """
        user_id_str = str(user_id)
        if user_id_str in self.data and lesson_id in self.data[user_id_str]["lessons"]:
            backup = {
                "user_id": user_id,
                "lesson_id": lesson_id,
                "backup_timestamp": datetime.now().isoformat(),
                "data": self.data[user_id_str]["lessons"][lesson_id].copy()
            }
            return backup
        return None

    def restore_user_data(self, backup_data: Dict[str, Any]):
        """
        Восстанавливает данные пользователя из резервной копии.
        """
        user_id = backup_data["user_id"]
        lesson_id = backup_data["lesson_id"]
        user_id_str = str(user_id)
        
        if user_id_str not in self.data:
            self.data[user_id_str] = self._get_default_user_data_structure()
        
        self.data[user_id_str]["lessons"][lesson_id] = backup_data["data"]
        self._save_data()
        print(f"DEBUG: Данные пользователя {user_id} для урока {lesson_id} восстановлены")

    def get_global_statistics(self) -> Dict[str, Any]:
        """
        Возвращает глобальную статистику по всем пользователям.
        
        Returns:
            Словарь с глобальной статистикой
        """
        global_stats = {
            "total_users": len(self.data),
            "total_lessons_completed": 0,
            "average_lesson_completion": 0.0,
            "most_active_users": [],
            "exercise_type_popularity": {},
            "pronunciation_accuracy_distribution": {
                "excellent": 0,
                "good": 0,
                "needs_improvement": 0
            }
        }
        
        user_activity = []
        
        for user_id_str, user_data in self.data.items():
            # Подсчитываем завершенные уроки
            total_completed = user_data.get("total_lessons_completed", 0)
            global_stats["total_lessons_completed"] += total_completed
            
            # Анализируем активность пользователя
            total_activities = 0
            for lesson_data in user_data.get("lessons", {}).values():
                # Подсчитываем попытки в разных блоках
                for block_data in lesson_data.get("blocks", {}).values():
                    attempts = block_data.get("attempts", [])
                    total_activities += len(attempts)
                
                # Анализируем произношение
                pronunciation_details = lesson_data.get("pronunciation_details", [])
                for p in pronunciation_details:
                    accuracy = p.get("accuracy", 0)
                    if accuracy >= 85.0:
                        global_stats["pronunciation_accuracy_distribution"]["excellent"] += 1
                    elif accuracy >= 68.0:
                        global_stats["pronunciation_accuracy_distribution"]["good"] += 1
                    else:
                        global_stats["pronunciation_accuracy_distribution"]["needs_improvement"] += 1
            
            user_activity.append({
                "user_id": int(user_id_str),
                "total_activities": total_activities,
                "lessons_completed": total_completed
            })
        
        # Сортируем по активности
        user_activity.sort(key=lambda x: x["total_activities"], reverse=True)
        global_stats["most_active_users"] = user_activity[:10]
        
        # Среднее количество завершенных уроков
        if global_stats["total_users"] > 0:
            global_stats["average_lesson_completion"] = round(
                global_stats["total_lessons_completed"] / global_stats["total_users"], 2
            )
        
        return global_stats

    def get_user_comparison(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID) -> Dict[str, Any]:
        """
        Сравнивает прогресс пользователя с общими показателями.
        
        Returns:
            Словарь с сравнением
        """
        user_stats = self.get_user_progress_summary(user_id, lesson_id)
        global_stats = self.get_global_statistics()
        
        comparison = {
            "user_id": user_id,
            "lesson_id": lesson_id,
            "user_performance": user_stats,
            "comparison_with_average": {},
            "percentile_rank": 0
        }
        
        # Сравниваем с общими показателями
        if global_stats["average_lesson_completion"] > 0:
            user_lessons = user_stats.get("completed_blocks", 0)
            avg_lessons = global_stats["average_lesson_completion"]
            
            comparison["comparison_with_average"] = {
                "lessons_completed": {
                    "user": user_lessons,
                    "average": avg_lessons,
                    "difference": user_lessons - avg_lessons
                },
                "pronunciation_attempts": {
                    "user": user_stats.get("pronunciation_attempts", 0),
                    "status": "above_average" if user_stats.get("pronunciation_attempts", 0) > 10 else "below_average"
                }
            }
        
        return comparison

    def generate_learning_report(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID) -> str:
        """
        Генерирует текстовый отчет о прогрессе пользователя.
        
        Returns:
            Текстовый отчет
        """
        progress_summary = self.get_user_progress_summary(user_id, lesson_id)
        pronunciation_improvement = self.get_pronunciation_improvement_analysis(user_id, lesson_id)
        speaking_fluency = self.get_speaking_fluency_analysis(user_id, lesson_id)
        recommendations = self.get_recommendations(user_id, lesson_id)
        
        report = f"""
📊 ОТЧЕТ О ПРОГРЕССЕ

🎯 Общий прогресс:
• Статус урока: {progress_summary['lesson_status']}
• Завершено блоков: {progress_summary['completed_blocks']}/{progress_summary['total_blocks']} ({progress_summary['completion_percentage']}%)
• Общий средний балл: {progress_summary['overall_average_score']}%

🗣️ Произношение:
• Всего попыток: {progress_summary['pronunciation_attempts']}
• Слов с улучшением: {pronunciation_improvement['words_with_improvement']}
• Слов, требующих внимания: {len(pronunciation_improvement['words_needing_attention'])}

💬 Говорение:
• Всего диалогов: {progress_summary['speaking_dialogues']}
• Средняя длина ответа: {speaking_fluency['average_response_length']:.1f} слов
• Разнообразие лексики: {speaking_fluency['vocabulary_diversity']} уникальных слов

💡 Рекомендации:
"""
        
        for i, recommendation in enumerate(recommendations, 1):
            report += f"• {recommendation}\n"
        
        return report.strip()

    def get_lesson_overall_percentage(self, user_id: int, lesson_id: str = CURRENT_LESSON_ID) -> float:
        """
        Рассчитывает общий процент прохождения урока на основе всех 8 основных блоков.
        Непройденные блоки считаются как 0%.
        
        Returns:
            Общий процент прохождения урока (0-100)
        """
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        blocks = lesson_stats.get("blocks", {})
        
        # 8 основных блоков урока
        main_blocks = [
            "terms",           # Изучение терминов
            "pronunciation",   # Произношение
            "lexical",         # Лексика (Общий)
            "grammar",         # Грамматика (Правило)
            "lexico_grammar",  # Лексико-грамматика (Общий)
            "listening",       # Аудирование (Общий)
            "writing",         # Письмо (Общий)
            "speaking"         # Говорение (Общий)
        ]
        
        total_score = 0
        
        for block_name in main_blocks:
            block_data = blocks.get(block_name, {})
            
            if block_name == "terms":
                # Для терминов: если completed = True, то 100%, иначе 0%
                score = 100.0 if block_data.get("completed", False) else 0.0
            elif block_name == "pronunciation":
                # Для произношения используем average_score
                score = block_data.get("average_score", 0.0)
            elif block_name == "lexical":
                # Для общего лексического блока считаем среднее по подблокам
                sub_blocks = ["lexical_en_to_ru", "lexical_ru_to_en", "lexical_word_build"]
                sub_scores = []
                for sub_block in sub_blocks:
                    sub_data = blocks.get(sub_block, {})
                    if "correct_count" in sub_data and "total_count" in sub_data:
                        correct = sub_data["correct_count"]
                        total = sub_data["total_count"]
                        if total > 0:
                            sub_scores.append((correct / total) * 100)
                    else:
                        correct, total = self.get_lexical_block_score(user_id, sub_block.replace("lexical_", ""), lesson_id)
                        if total > 0:
                            sub_scores.append((correct / total) * 100)
                score = sum(sub_scores) / len(sub_scores) if sub_scores else 0.0
            elif block_name == "grammar":
                # Для грамматики: если completed = True, то 100%, иначе 0%
                score = 100.0 if block_data.get("completed", False) else 0.0
            elif block_name == "lexico_grammar":
                # Для общего лексико-грамматического блока считаем среднее по подблокам
                sub_blocks = ["lexico_grammar_verb", "lexico_grammar_mchoice", "lexico_grammar_negative", 
                             "lexico_grammar_question", "lexico_grammar_missing_word"]
                sub_scores = []
                for sub_block in sub_blocks:
                    sub_data = blocks.get(sub_block, {})
                    if "correct_count" in sub_data and "total_count" in sub_data:
                        correct = sub_data["correct_count"]
                        total = sub_data["total_count"]
                        if total > 0:
                            sub_scores.append((correct / total) * 100)
                    else:
                        correct, total = self.get_lexical_block_score(user_id, sub_block.replace("lexico_grammar_", ""), lesson_id)
                        if total > 0:
                            sub_scores.append((correct / total) * 100)
                score = sum(sub_scores) / len(sub_scores) if sub_scores else 0.0
            elif block_name == "listening":
                # Для общего аудирования считаем среднее по подблокам
                sub_blocks = ["listening_true_false", "listening_choice", "listening_phrases"]
                sub_scores = []
                for sub_block in sub_blocks:
                    sub_data = blocks.get(sub_block, {})
                    if "correct_count" in sub_data and "total_count" in sub_data:
                        correct = sub_data["correct_count"]
                        total = sub_data["total_count"]
                        if total > 0:
                            sub_scores.append((correct / total) * 100)
                    else:
                        if sub_block == "listening_phrases":
                            correct, total = self.get_listening_phrases_score(user_id, lesson_id)
                        else:
                            correct, total = self.get_listening_block_score(user_id, sub_block.replace("listening_", ""), lesson_id)
                        if total > 0:
                            sub_scores.append((correct / total) * 100)
                score = sum(sub_scores) / len(sub_scores) if sub_scores else 0.0
            elif block_name == "writing":
                # Для общего письма считаем среднее по подблокам
                sub_blocks = ["writing_sentences", "writing_translation"]
                sub_scores = []
                for sub_block in sub_blocks:
                    sub_data = blocks.get(sub_block, {})
                    if "correct_count" in sub_data and "total_count" in sub_data:
                        correct = sub_data["correct_count"]
                        total = sub_data["total_count"]
                        if total > 0:
                            sub_scores.append((correct / total) * 100)
                    else:
                        correct, total = self.get_writing_block_score(user_id, sub_block.replace("writing_", ""), lesson_id)
                        if total > 0:
                            sub_scores.append((correct / total) * 100)
                score = sum(sub_scores) / len(sub_scores) if sub_scores else 0.0
            elif block_name == "speaking":
                # Для общего говорения считаем среднее по подблокам
                sub_blocks = ["speaking_topics"]
                sub_scores = []
                for sub_block in sub_blocks:
                    sub_data = blocks.get(sub_block, {})
                    if "correct_count" in sub_data and "total_count" in sub_data:
                        correct = sub_data["correct_count"]
                        total = sub_data["total_count"]
                        if total > 0:
                            sub_scores.append((correct / total) * 100)
                    else:
                        correct, total = self.get_speaking_block_score(user_id, "topics", lesson_id)
                        if total > 0:
                            sub_scores.append((correct / total) * 100)
                score = sum(sub_scores) / len(sub_scores) if sub_scores else 0.0
            
            total_score += score
        
        # Возвращаем среднее по всем 8 блокам
        return round(total_score / len(main_blocks), 1)

    def get_block_percentage(self, user_id: int, block_name: str, lesson_id: str = CURRENT_LESSON_ID) -> float:
        """
        Рассчитывает процент прохождения для конкретного блока.
        
        Returns:
            Процент прохождения блока (0-100)
        """
        lesson_stats = self.get_lesson_stats(user_id, lesson_id)
        block_data = lesson_stats.get("blocks", {}).get(block_name, {})
        
        if block_name in ["terms", "grammar"]:
            # Для терминов и грамматики: если completed = True, то 100%, иначе 0%
            return 100.0 if block_data.get("completed", False) else 0.0
        
        if block_name == "speaking":
            # Для общего блока говорения возвращаем 0, так как он не участвует в расчете
            return 0.0
        
        if block_name == "pronunciation":
            lesson_stats = self.get_lesson_stats(user_id, lesson_id)
            block_data = lesson_stats.get("blocks", {}).get(block_name, {})
            return block_data.get("average_score", 0.0)
        
        elif block_name in ["lexical_en_to_ru", "lexical_ru_to_en", "lexical_word_build"]:
            sub_block = block_name.replace("lexical_", "")
            correct, total = self.get_lexical_block_score(user_id, sub_block, lesson_id)
            if total > 0:
                return round((correct / total) * 100, 1)
            return 0.0
        
        elif block_name.startswith("lexico_grammar_"):
            sub_block = block_name.replace("lexico_grammar_", "")
            correct, total = self.get_lexical_block_score(user_id, sub_block, lesson_id)
            if total > 0:
                return round((correct / total) * 100, 1)
            return 0.0
        
        elif block_name.startswith("listening_"):
            sub_block = block_name.replace("listening_", "")
            if sub_block == "phrases":
                correct, total = self.get_listening_phrases_score(user_id, lesson_id)
            else:
                correct, total = self.get_listening_block_score(user_id, sub_block, lesson_id)
            if total > 0:
                return round((correct / total) * 100, 1)
            return 0.0
        
        elif block_name.startswith("writing_"):
            sub_block = block_name.replace("writing_", "")
            correct, total = self.get_writing_block_score(user_id, sub_block, lesson_id)
            if total > 0:
                return round((correct / total) * 100, 1)
            return 0.0
        
        elif block_name == "speaking_topics":
            # Сначала проверяем прямые счетчики в JSON
            lesson_stats = self.get_lesson_stats(user_id, lesson_id)
            block_data = lesson_stats.get("blocks", {}).get(block_name, {})
            
            if "correct_count" in block_data and "total_count" in block_data:
                correct = block_data["correct_count"]
                total = block_data["total_count"]
                if total > 0:
                    return round((correct / total) * 100, 1)
            
            # Если нет прямых счетчиков, используем метод get_speaking_block_score
            correct, total = self.get_speaking_block_score(user_id, "topics", lesson_id)
            if total > 0:
                return round((correct / total) * 100, 1)
            return 0.0
        
        return 0.0

