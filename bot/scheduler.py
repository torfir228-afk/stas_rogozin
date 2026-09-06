import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from aiogram import Bot
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot import database, texts
from bot.config import config

logger = logging.getLogger(__name__)

_bot: Optional[Bot] = None

scheduler = AsyncIOScheduler(
    jobstores={"default": SQLAlchemyJobStore(url=f"sqlite:///{config.jobs_db_path}")},
    timezone=timezone.utc,
)


def bind_bot(bot: Bot) -> None:
    global _bot
    _bot = bot


def _reminder_job_id(user_id: int, stage: int) -> str:
    return f"reminder_{stage}_{user_id}"


async def send_reminder(user_id: int, stage: int) -> None:
    """Callback executed by APScheduler. Must stay a module-level function
    so the job survives being persisted to and reloaded from the job store."""
    if _bot is None:
        logger.error("Бот не привязан к планировщику, напоминание не отправлено")
        return
    if await database.is_delivered(user_id):
        return
    text, markup = texts.reminder_message(stage)
    try:
        await _bot.send_message(user_id, text, reply_markup=markup)
    except Exception:
        logger.exception("Не удалось отправить напоминание пользователю %s", user_id)


def schedule_reminders(user_id: int) -> None:
    now = datetime.now(timezone.utc)
    scheduler.add_job(
        send_reminder,
        "date",
        run_date=now + timedelta(minutes=config.reminder_1_delay_minutes),
        args=[user_id, 1],
        id=_reminder_job_id(user_id, 1),
        replace_existing=True,
        misfire_grace_time=None,
    )
    scheduler.add_job(
        send_reminder,
        "date",
        run_date=now + timedelta(minutes=config.reminder_2_delay_minutes),
        args=[user_id, 2],
        id=_reminder_job_id(user_id, 2),
        replace_existing=True,
        misfire_grace_time=None,
    )


def cancel_reminders(user_id: int) -> None:
    for stage in (1, 2):
        try:
            scheduler.remove_job(_reminder_job_id(user_id, stage))
        except Exception:
            pass
