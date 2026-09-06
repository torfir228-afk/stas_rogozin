import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot import database
from bot import scheduler as scheduler_module
from bot.config import config
from bot.handlers import router

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def main() -> None:
    os.makedirs(os.path.dirname(config.db_path) or ".", exist_ok=True)
    os.makedirs(os.path.dirname(config.jobs_db_path) or ".", exist_ok=True)

    await database.init_db()

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    scheduler_module.bind_bot(bot)
    scheduler_module.scheduler.start()

    logger.info("Бот запущен, начинаю polling")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
