import json
import os
from threading import Lock

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
PROGRESS_FILE = os.path.join(DATA_DIR, 'user_progress.json')
DIALOG_FILE = os.path.join(DATA_DIR, 'user_gpt_dialog.json')

_lock = Lock()

CEFR_LEVELS = [
    (0, 'A1'),
    (20, 'A2'),
    (40, 'B1'),
    (60, 'B2'),
    (80, 'C1'),
    (100, 'C2'),
]

def _load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def _save_json(path, data):
    with _lock:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

class ProgressManager:
    def __init__(self):
        self.progress_data = _load_json(PROGRESS_FILE)
        self.dialog_data = _load_json(DIALOG_FILE)

    def save_all(self):
        _save_json(PROGRESS_FILE, self.progress_data)
        _save_json(DIALOG_FILE, self.dialog_data)

    def init_user(self, user_id):
        user_id = str(user_id)
        if user_id not in self.progress_data:
            self.progress_data[user_id] = {
                "status": "not_started",  # or "in_progress", "completed"
                "progress_points": 0,
                "completed_blocks": [],
                "current_block": None,
                "current_item": 0,
            }
        if user_id not in self.dialog_data:
            self.dialog_data[user_id] = []

    def add_points_for_block(self, user_id, block_name, points=5):
        user_id = str(user_id)
        self.init_user(user_id)
        user_progress = self.progress_data[user_id]
        if block_name not in user_progress["completed_blocks"]:
            user_progress["completed_blocks"].append(block_name)
            user_progress["progress_points"] = min(user_progress["progress_points"] + points, 100)
            user_progress["status"] = "in_progress" if user_progress["progress_points"] < 100 else "completed"
            self.save_all()

    def record_dialog(self, user_id, dialog_entry):
        """
        dialog_entry: dict with keys like "message", "response", "pronunciation_score" etc.
        """
        user_id = str(user_id)
        self.init_user(user_id)
        self.dialog_data[user_id].append(dialog_entry)
        self.save_all()

    def calculate_cefr(self, user_id):
        """
        Пример простой оценки CEFR.
        Берется прогресс по очкам + средняя оценка произношения из диалогов.
        """
        user_id = str(user_id)
        self.init_user(user_id)
        p = self.progress_data[user_id]
        dialogs = self.dialog_data[user_id]

        points = p.get("progress_points", 0)

        # Рассчитаем средний балл произношения по диалогам, если есть
        pron_scores = [d.get("pronunciation_score", None) for d in dialogs]
        pron_scores = [s for s in pron_scores if s is not None]
        pron_score_avg = sum(pron_scores) / len(pron_scores) if pron_scores else 0

        # Скорректируем очки по произношению (макс 20 очков доп.)
        adj_points = points + (pron_score_avg * 20 / 100)
        adj_points = min(adj_points, 100)

        level = 'A1'
        for threshold, lvl in reversed(CEFR_LEVELS):
            if adj_points >= threshold:
                level = lvl
                break
        return level

    def get_statistics(self, user_id):
        user_id = str(user_id)
        self.init_user(user_id)
        p = self.progress_data[user_id]

        progress_points = p.get("progress_points", 0)
        cefr_level = self.calculate_cefr(user_id)
        completed_blocks = p.get("completed_blocks", [])

        stats_text = (
            f"📊 Прогресс пользователя: {progress_points}/100 очков\n"
            f"🔤 Предположительная оценка CEFR: {cefr_level}\n"
            f"✅ Сдано заданий по блокам: {', '.join(completed_blocks) if completed_blocks else 'нет'}"
        )
        return stats_text