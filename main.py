import asyncio
from threading import Thread
import logging
from admin import run_flask
from tg_bot import run_bot, bot_loop_ready

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def start_flask_thread():
    """Запуск Flask в отдельном потоке, чтобы не блокировать asyncio loop"""
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("✅ Flask сервер запущен в отдельном потоке")

async def main():
    # Запускаем бот
    bot_task = asyncio.create_task(run_bot())

    # Ждём, пока бот будет готов
    await bot_loop_ready.wait()
    start_flask_thread()  # запуск Flask после готовности бота

    # Ждём завершения работы бота (ctrl+c)
    await bot_task

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Приложение остановлено")
    except Exception as e:
        logger.error(f"Ошибка запуска: {e}")
