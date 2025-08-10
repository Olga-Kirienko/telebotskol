import sys
import os

# Добавляем путь к корневой директории
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram.fsm.state import State, StatesGroup


class LessonStates(StatesGroup):
    # Блок 1: Введение терминов
    TERMS_START = State()
    TERMS_SHOW_TERM = State()
    TERMS_SHOW_TRANSLATION = State()
    TERMS_SHOW_TRANSCRIPTION = State()
    TERMS_SHOW_IMAGE = State()
    TERMS_SHOW_AUDIO = State()
    TERMS_COMPLETE = State()
    
    # Блок 2: Произношение
    PRONUNCIATION_START = State()
    PRONUNCIATION_LISTEN = State()
    PRONUNCIATION_RECORD = State()
    PRONUNCIATION_COMPLETE = State()
    
    # Блок 3: Лексика
    LEXICAL_EN_TO_RU = State()    # Английский -> Русский
    LEXICAL_RU_TO_EN = State()
    LEXICAL_WORD_BUILD = State()
    LEXICAL_EN_COMPLETE = State()
    LEXICAL_RU_COMPLETE = State()
    LEXICAL_WORD_COMPLETE = State()
    

     
    # Блок 4: Грамматика
    GRAMMAR_EXPLANATION = State()  # Показ правила
    GRAMMAR_CHOICE = State()       # Выбор: понятно/есть вопросы
    GRAMMAR_QA = State()           # Режим вопросов-ответов
    GRAMMAR_COMPLETE = State()     # Завершение блока
    
    # Блок 5: Лексико-грамматические упражнения
    VERB_EXERCISE = State()        # Упражнение с глаголами
    VERB_COMPLETE = State()
    MCHOICE_EXERCISE = State()     # Множественный выбор
    MCHOICE_COMPLETE = State()
    MISSING_WORD_EXERCISE = State() # Вставка пропущенных слов
    MISSING_WORD_COMPLETE = State()
    NEGATIVE_EXERCISE = State()     # Отрицательные предложения
    NEGATIVE_COMPLETE = State()
    QUESTION_EXERCISE = State()     # Вопросительные предложения  
    QUESTION_COMPLETE = State()
    MISSING_WORD_EXERCISE = State() # Вставка пропущенных слов
    MISSING_WORD_COMPLETE = State()
    
    # Блок 6: Аудирование
    LISTENING_TRUE_FALSE = State()     # True/False упражнения
    LISTENING_TRUE_FALSE_COMPLETE = State()
    LISTENING_CHOICE = State()         # Множественный выбор
    LISTENING_CHOICE_COMPLETE = State()
    LISTENING_PHRASES = State()        # Повторение фраз
    LISTENING_PHRASES_RECORD = State() # Запись произношения фраз
    LISTENING_PHRASES_COMPLETE = State()
    
    # Блок 7: Письменная речь
    WRITING_SENTENCES = State()        # Составление предложений
    WRITING_SENTENCES_COMPLETE = State()
    WRITING_TRANSLATION = State()      # Перевод предложений
    WRITING_TRANSLATION_COMPLETE = State()
    
    # Блок 8: Говорение
    SPEAKING = State()
    SPEAKING_START = State() # Добавьте эту строку
    SPEAKING_RECORD = State()
    SPEAKING_COMPLETE = State()
    SPEAKING_ANALYZING = State() # Если у вас есть такое состояние
    # Завершение урока
    LESSON_COMPLETE = State()


class AuthStates(StatesGroup):
    # Состояния для авторизации
    AUTH_CHOICE = State()              # Выбор между регистрацией и авторизацией
    
    # Состояния для регистрации
    REGISTER_USERNAME = State()
    REGISTER_EMAIL = State()
    REGISTER_PASSWORD = State()
    REGISTER_PASSWORD_CONFIRM = State()
    REGISTER_FIRST_NAME = State()
    REGISTER_LAST_NAME = State()
    REGISTER_CONFIRM = State()
    
    # Состояния для авторизации
    LOGIN_EMAIL = State()
    LOGIN_PASSWORD = State()