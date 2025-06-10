import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault


async def set_bot_commands(bot: Bot):
    """Установка команд бота в меню Telegram"""
    commands = [
        BotCommand(command="start", description="🏠 Главное меню"),
        BotCommand(command="lesson", description="📚 Начать урок"),
        BotCommand(command="terms", description="📖 Изучение терминов"),
        BotCommand(command="pronunciation", description="🗣️ Произношение"),
        BotCommand(command="lexical", description="📝 Лексика"),
        BotCommand(command="grammar", description="📚 Грамматика"),
        BotCommand(command="exercises", description="✏️ Упражнения"),
        BotCommand(command="listening", description="🎧 Аудирование"),
        BotCommand(command="writing", description="✍️ Письмо"),
        BotCommand(command="restart", description="🔄 Перезапуск урока"),
        BotCommand(command="help", description="❓ Помощь"),
        
    ]
    
    await bot.set_my_commands(commands, BotCommandScopeDefault())