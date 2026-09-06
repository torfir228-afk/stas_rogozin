import logging
import os

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, FSInputFile, Message

from bot import database, scheduler, texts
from bot.config import config

logger = logging.getLogger(__name__)
router = Router(name="funnel")


async def _is_subscribed(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(config.channel_id, user_id)
    except Exception:
        logger.info("Не удалось проверить подписку пользователя %s", user_id)
        return False
    return member.status in ("member", "administrator", "creator")


async def _deliver_lead_magnet(message: Message, user_id: int) -> None:
    await database.mark_delivered(user_id)
    scheduler.cancel_reminders(user_id)
    caption = texts.lead_magnet_message()
    if config.lead_magnet_file_path and os.path.isfile(config.lead_magnet_file_path):
        await message.answer_document(FSInputFile(config.lead_magnet_file_path), caption=caption)
    else:
        await message.answer(caption)


async def _send_subscription_prompt(message: Message, user_id: int) -> None:
    text, markup = texts.subscription_required_message()
    await message.answer(text, reply_markup=markup)
    if not await database.reminders_already_scheduled(user_id):
        scheduler.schedule_reminders(user_id)
        await database.mark_reminders_scheduled(user_id)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await database.mark_started(message.from_user.id)
    text, markup = texts.welcome_message()
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == texts.CALLBACK_CHECK_ACCESS)
async def cb_check_access(callback: CallbackQuery) -> None:
    user_id = callback.from_user.id
    if await _is_subscribed(callback.bot, user_id):
        await _deliver_lead_magnet(callback.message, user_id)
    else:
        await _send_subscription_prompt(callback.message, user_id)
    await callback.answer()
