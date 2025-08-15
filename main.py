# main.py
import asyncio
from threading import Thread
import logging
from admin import run_flask
from tg_bot import run_bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def start_flask_thread():
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("✅ Flask сервер запущен в отдельном потоке")

if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()  # глобальный loop
        loop.create_task(run_bot())      # запускаем бота в этом loop
        start_flask_thread()             # запускаем Flask в отдельном потоке
        logger.info("🚀 Запуск Telegram-бота...")
        loop.run_forever()               # запускаем loop
    except KeyboardInterrupt:
        logger.info("🛑 Приложение остановлено пользователем")
    except Exception as e:
        logger.exception(f"❌ Ошибка запуска: {e}")
