import asyncio
import logging
import sys
import os
import sys
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

# Добавляем текущую директорию в путь Python
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import BOT_TOKEN
from bot.statistics import UserStatistics
from bot.utils import UserProgress
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

    bot = Bot(token=BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Инициализируем UserStatistics ОДИН РАЗ и делаем его доступным для хэндлеров
    user_statistics = UserStatistics()
    dp["user_statistics"] = user_statistics

    # Инициализируем UserProgress ОДИН РАЗ и делаем его доступным для хэндлеров
    user_progress = UserProgress()
    dp["user_progress"] = user_progress

    try:
        from bot.handlers.start import router as start_router
        from bot.handlers.lesson import router as lesson_router
        from bot.handlers.auth import router as auth_router
        from bot.commands import set_bot_commands
        from aiogram import F
        from aiogram.types import CallbackQuery

        dp.include_router(auth_router)
        print(f"🔍 DEBUG: auth_router включен: {auth_router}")
        dp.include_router(start_router)
        print(f"🔍 DEBUG: start_router включен")
        dp.include_router(lesson_router)
        print(f"🔍 DEBUG: lesson_router включен")
        
        # ОБРАБОТЧИКИ СОСТОЯНИЙ (перенесены из auth.py для стабильности)
        from aiogram.types import Message
        from aiogram.fsm.context import FSMContext
        from aiogram.filters import StateFilter
        from bot.states import AuthStates
        from bot.database import db_manager
        import re

        @dp.message(StateFilter(AuthStates.REGISTER_USERNAME))
        async def register_username_handler(message: Message, state: FSMContext):
            """Обработка имени пользователя"""
            username = message.text.strip()
            
            if len(username) < 3:
                from aiogram.utils.keyboard import InlineKeyboardBuilder
                keyboard = InlineKeyboardBuilder()
                keyboard.button(text="🔙 Отмена", callback_data="auth_menu")
                await message.answer(
                    "❌ Имя пользователя должно содержать минимум 3 символа.\n"
                    "Попробуйте еще раз:",
                    reply_markup=keyboard.as_markup()
                )
                return
            
            if db_manager.user_exists_by_username(username):
                from aiogram.utils.keyboard import InlineKeyboardBuilder
                keyboard = InlineKeyboardBuilder()
                keyboard.button(text="🔙 Отмена", callback_data="auth_menu")
                await message.answer(
                    "❌ Это имя пользователя уже занято.\n"
                    "Введите другое имя пользователя:",
                    reply_markup=keyboard.as_markup()
                )
                return
            
            await state.update_data(username=username)
            await state.set_state(AuthStates.REGISTER_EMAIL)
            
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="🔙 Отмена", callback_data="auth_menu")
            await message.answer(
                "📧 Введите <b>email</b> (обязательно):",
                parse_mode="HTML",
                reply_markup=keyboard.as_markup()
            )


        @dp.message(StateFilter(AuthStates.REGISTER_EMAIL))
        async def register_email_handler(message: Message, state: FSMContext):
            """Обработка email"""
            email = message.text.strip().lower()
            
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                from aiogram.utils.keyboard import InlineKeyboardBuilder
                keyboard = InlineKeyboardBuilder()
                keyboard.button(text="🔙 Отмена", callback_data="auth_menu")
                await message.answer(
                    "❌ Неверный формат email.\n"
                    "Введите корректный email:",
                    reply_markup=keyboard.as_markup()
                )
                return
            
            if db_manager.user_exists_by_email(email):
                from aiogram.utils.keyboard import InlineKeyboardBuilder
                keyboard = InlineKeyboardBuilder()
                keyboard.button(text="🔙 Отмена", callback_data="auth_menu")
                await message.answer(
                    "❌ Этот email уже зарегистрирован.\n"
                    "Введите другой email:",
                    reply_markup=keyboard.as_markup()
                )
                return
            
            await state.update_data(email=email)
            await state.set_state(AuthStates.REGISTER_PASSWORD)
            
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="🔙 Отмена", callback_data="auth_menu")
            await message.answer(
                "🔒 Введите <b>пароль</b> (обязательно, минимум 6 символов):",
                parse_mode="HTML",
                reply_markup=keyboard.as_markup()
            )

        @dp.message(StateFilter(AuthStates.REGISTER_PASSWORD))
        async def register_password_handler(message: Message, state: FSMContext):
            """Обработка пароля"""
            password = message.text.strip()
            
            if len(password) < 6:
                from aiogram.utils.keyboard import InlineKeyboardBuilder
                keyboard = InlineKeyboardBuilder()
                keyboard.button(text="🔙 Отмена", callback_data="auth_menu")
                await message.answer(
                    "❌ Пароль должен содержать минимум 6 символов.\n"
                    "Введите пароль:",
                    reply_markup=keyboard.as_markup()
                )
                return
            
            await state.update_data(password=password)
            await state.set_state(AuthStates.REGISTER_PASSWORD_CONFIRM)
            
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="🔙 Отмена", callback_data="auth_menu")
            await message.answer(
                "🔒 <b>Подтвердите пароль</b> (введите пароль еще раз для проверки):",
                parse_mode="HTML",
                reply_markup=keyboard.as_markup()
            )

        @dp.message(StateFilter(AuthStates.REGISTER_PASSWORD_CONFIRM))
        async def register_password_confirm_handler(message: Message, state: FSMContext):
            """Подтверждение пароля"""
            password_confirm = message.text.strip()
            data = await state.get_data()
            original_password = data['password']
            
            if password_confirm != original_password:
                from aiogram.utils.keyboard import InlineKeyboardBuilder
                keyboard = InlineKeyboardBuilder()
                keyboard.button(text="🔙 Отмена", callback_data="auth_menu")
                await message.answer(
                    "❌ Пароли не совпадают!\n"
                    "Введите пароль еще раз:",
                    reply_markup=keyboard.as_markup()
                )
                await state.set_state(AuthStates.REGISTER_PASSWORD)
                return
            
            await state.set_state(AuthStates.REGISTER_FIRST_NAME)
            
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="🔙 Отмена", callback_data="auth_menu")
            await message.answer(
                "👤 Введите <b>имя</b> (необязательно, нажмите /skip для пропуска):",
                parse_mode="HTML",
                reply_markup=keyboard.as_markup()
            )

        @dp.message(StateFilter(AuthStates.REGISTER_FIRST_NAME))
        async def register_first_name_handler(message: Message, state: FSMContext):
            """Обработка имени"""
            if message.text.strip().lower() == '/skip':
                await state.update_data(first_name="")
            else:
                await state.update_data(first_name=message.text.strip())
            
            await state.set_state(AuthStates.REGISTER_LAST_NAME)
            
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="🔙 Отмена", callback_data="auth_menu")
            await message.answer(
                "👤 Введите <b>фамилию</b> (необязательно, нажмите /skip для пропуска):",
                parse_mode="HTML",
                reply_markup=keyboard.as_markup()
            )

        @dp.message(StateFilter(AuthStates.REGISTER_LAST_NAME))
        async def register_last_name_handler(message: Message, state: FSMContext):
            """Обработка фамилии"""
            if message.text.strip().lower() == '/skip':
                await state.update_data(last_name="")
            else:
                await state.update_data(last_name=message.text.strip())
            
            await state.set_state(AuthStates.REGISTER_CONFIRM)
            
            data = await state.get_data()
            
            confirm_text = "📝 <b>Подтвердите данные регистрации:</b>\n\n"
            confirm_text += f"👤 <b>Имя пользователя:</b> {data['username']}\n"
            confirm_text += f"📧 <b>Email:</b> {data['email']}\n"
            confirm_text += f"🔒 <b>Пароль:</b> {'*' * len(data['password'])}\n"
            if data.get('first_name'):
                confirm_text += f"👤 <b>Имя:</b> {data['first_name']}\n"
            if data.get('last_name'):
                confirm_text += f"👤 <b>Фамилия:</b> {data['last_name']}\n"
            
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="✅ Подтвердить", callback_data="register_confirm")
            keyboard.button(text="🔄 Начать заново", callback_data="auth_register")
            keyboard.button(text="🔙 Отмена", callback_data="auth_menu")
            keyboard.adjust(2, 1)
            
            await message.answer(
                confirm_text,
                parse_mode="HTML",
                reply_markup=keyboard.as_markup()
            )

        @dp.message(StateFilter(AuthStates.LOGIN_EMAIL))
        async def login_email_handler(message: Message, state: FSMContext):
            """Обработка email при авторизации"""
            email = message.text.strip().lower()
            
            if not db_manager.user_exists_by_email(email):
                from aiogram.utils.keyboard import InlineKeyboardBuilder
                keyboard = InlineKeyboardBuilder()
                keyboard.button(text="📝 Регистрация", callback_data="auth_register")
                keyboard.button(text="🔑 Авторизация", callback_data="auth_login")
                keyboard.button(text="🔙 Назад", callback_data="main_menu")
                keyboard.adjust(2, 1)
                await message.answer(
                    "❌ Пользователь с таким email не найден.\n"
                    "Проверьте email или зарегистрируйтесь:",
                    reply_markup=keyboard.as_markup()
                )
                await state.clear()
                return
            
            await state.update_data(email=email)
            await state.set_state(AuthStates.LOGIN_PASSWORD)
            
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="🔙 Отмена", callback_data="auth_menu")
            await message.answer(
                "🔒 Введите ваш <b>пароль</b>:",
                parse_mode="HTML",
                reply_markup=keyboard.as_markup()
            )

        @dp.message(StateFilter(AuthStates.LOGIN_PASSWORD))
        async def login_password_handler(message: Message, state: FSMContext):
            """Обработка пароля при авторизации"""
            password = message.text.strip()
            data = await state.get_data()
            email = data['email']
            telegram_id = message.from_user.id
            
            print(f"🔍 DEBUG: Попытка авторизации - Email: {email}, Telegram ID: {telegram_id}")
            
            try:
                user = db_manager.authenticate_user(email, password)
                
                if user:
                    print(f"🔍 DEBUG: Пользователь найден - ID: {user['id']}, Username: {user['username']}")
                    
                    # Всегда обновляем telegram_id при успешной авторизации
                    update_success = db_manager.update_telegram_id(user['id'], telegram_id)
                    print(f"🔍 DEBUG: Обновление telegram_id: {'успешно' if update_success else 'ошибка'}")
                    
                    from aiogram.utils.keyboard import InlineKeyboardBuilder
                    keyboard = InlineKeyboardBuilder()
                    keyboard.button(text="🏠 Главное меню", callback_data="main_menu")
                    await message.answer(
                        "✅ <b>Авторизация успешна!</b>\n\n"
                        f"👤 Добро пожаловать, {user['username']}!\n"
                        f"📧 Email: {user['email']}\n"
                        f"🆔 Telegram ID: {telegram_id}\n\n"
                        "Теперь вы можете использовать все функции бота!",
                        parse_mode="HTML",
                        reply_markup=keyboard.as_markup()
                    )
                else:
                    from aiogram.utils.keyboard import InlineKeyboardBuilder
                    keyboard = InlineKeyboardBuilder()
                    keyboard.button(text="📝 Регистрация", callback_data="auth_register")
                    keyboard.button(text="🔑 Авторизация", callback_data="auth_login")
                    keyboard.button(text="🔙 Назад", callback_data="main_menu")
                    keyboard.adjust(2, 1)
                    await message.answer(
                        "❌ <b>Неверный пароль!</b>\n\n"
                        "Проверьте пароль и попробуйте снова:",
                        reply_markup=keyboard.as_markup()
                    )
            except Exception as e:
                print(f"🔍 DEBUG: Ошибка при авторизации: {e}")
                from aiogram.utils.keyboard import InlineKeyboardBuilder
                keyboard = InlineKeyboardBuilder()
                keyboard.button(text="📝 Регистрация", callback_data="auth_register")
                keyboard.button(text="🔑 Авторизация", callback_data="auth_login")
                keyboard.button(text="🔙 Назад", callback_data="main_menu")
                keyboard.adjust(2, 1)
                await message.answer(
                    "❌ <b>Ошибка при авторизации!</b>\n\n"
                    "Попробуйте позже или обратитесь к администратору.",
                    parse_mode="HTML",
                    reply_markup=keyboard.as_markup()
                )
            
            await state.clear()

    except ImportError as e:
        logger.error(f"Ошибка импорта обработчиков: {e}")
        return

    logger.info("🤖 Бот запускается...")
    logger.info("🎯 Специализация: Английский для программистов и Data Science")

    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
