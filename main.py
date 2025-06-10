import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

# Добавляем текущую директорию в путь Python
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import BOT_TOKEN

# Включаем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def main():
    """Главная функция запуска бота"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не найден! Создайте файл .env и добавьте BOT_TOKEN=your_token")
        return
    
    # Создаем бота и диспетчер
    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Импортируем роутеры здесь, чтобы избежать циклических импортов
    try:
        from bot.handlers.start import router as start_router
        from bot.handlers.lesson import router as lesson_router
        from bot.commands import set_bot_commands
        
        # Регистрируем роутеры
        dp.include_router(start_router)
        dp.include_router(lesson_router)
        
        # Устанавливаем команды бота
        await set_bot_commands(bot)
        
    except ImportError as e:
        logger.error(f"Ошибка импорта обработчиков: {e}")
        return
    
    logger.info("🤖 Бот запускается...")
    logger.info("🎯 Специализация: Английский для программистов и Data Science")
    
    try:
        # Запускаем бота
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")