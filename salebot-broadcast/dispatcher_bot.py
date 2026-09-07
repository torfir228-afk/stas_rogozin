#!/usr/bin/env python3
"""Локальный бот-диспетчер рассылок: форвард сообщения + инструкция -> Salebot.

Запускается вручную, когда нужно (не постоянный сервис):
    python3 dispatcher_bot.py
и останавливается Ctrl+C, когда рассылки на сегодня разобраны.

Как пользоваться (в Telegram, в чате с этим ботом):
    1. Форвардите сообщение клиента с текстом рассылки.
    2. Следующим сообщением (в ответ на форвард или просто следующим) пишете
       инструкцию построчно:
           бот: 2
           время: 18:00
           кнопка: Записаться | https://example.com
       Строки "время" и "кнопка" необязательны.
    3. Бот показывает превью и кнопки [Отправить] / [Отмена].
    4. Только по вашему тапу "Отправить" уходит запрос в Salebot.

Настройка: скопируйте .env.example в .env, впишите DISPATCHER_BOT_TOKEN
(токен НОВОГО бота, созданного через @BotFather специально для этого — не
токен рабочих ботов) и OWNER_TELEGRAM_ID (ваш личный Telegram ID, чтобы
никто другой не мог им воспользоваться). Данные о целевых аудиториях Salebot
берутся из clients.json (alias, group_id, api_key) — см. clients.example.json.
Разные боты одного проекта различаются по ID списка (group_id), не по
bot_id — так настроен проект в Salebot: каждый бот пишет своих подписчиков
в свой отдельный список.
"""
import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

from send_broadcast import build_payload, load_clients, send_broadcast

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("DISPATCHER_BOT_TOKEN")
OWNER_ID_RAW = os.getenv("OWNER_TELEGRAM_ID")

if not BOT_TOKEN:
    raise SystemExit("Не задан DISPATCHER_BOT_TOKEN. Скопируйте .env.example в .env и заполните.")
if not OWNER_ID_RAW:
    raise SystemExit("Не задан OWNER_TELEGRAM_ID. Скопируйте .env.example в .env и заполните.")
OWNER_ID = int(OWNER_ID_RAW)


@dataclass
class PendingForward:
    text: str


@dataclass
class PendingBroadcast:
    client_name: str
    text: str
    group_id: str | None
    send_time: str | None
    button_text: str | None
    button_url: str | None


# Простое состояние в памяти процесса — бот и так рассчитан на короткие
# ручные сессии, между запусками ничего сохранять не нужно.
pending_forwards: dict[int, PendingForward] = {}
pending_broadcasts: dict[str, PendingBroadcast] = {}


def resolve_client(clients: dict, token: str) -> tuple[str, dict] | None:
    token = token.strip()
    for name, cfg in clients.items():
        if cfg.get("alias") and cfg["alias"].strip().lower() == token.lower():
            return name, cfg
    if token in clients:
        return token, clients[token]
    return None


def parse_instruction(raw: str) -> dict:
    fields: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip().lower()] = value.strip()
    return fields


def parse_send_time(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    # Полный формат уже подходит для Salebot as-is.
    try:
        datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        return value
    except ValueError:
        pass
    # Короткий формат "ЧЧ:ММ" -> сегодняшняя дата.
    try:
        parsed_time = datetime.strptime(value, "%H:%M").time()
        today = datetime.now().date()
        return datetime.combine(today, parsed_time).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise ValueError(
            f"Не понял время '{value}'. Используйте 'ЧЧ:ММ' (сегодня) или "
            f"'ГГГГ-ММ-ДД ЧЧ:ММ:СС'."
        )


def format_preview(name: str, cfg: dict, b: PendingBroadcast) -> str:
    username = cfg.get("telegram_username")
    lines = [
        f"Получатель: {name}" + (f" ({username})" if username else ""),
        f"Список (group_id): {b.group_id or '(не указан!)'}",
        f"Время отправки: {b.send_time or 'сразу'}",
    ]
    if b.button_text:
        lines.append(f"Кнопка: {b.button_text} -> {b.button_url}")
    lines.append("")
    lines.append("Текст:")
    lines.append(b.text)
    lines.append("")
    lines.append("⚠️ Проверьте получателя (имя и @username) — это тот бот, куда должна уйти именно эта рассылка.")
    if b.button_text:
        lines.append(
            "⚠️ Формат кнопки в Salebot Broadcast API не подтверждён официальной "
            "документацией — при первом использовании проверьте результат на "
            "тестовой аудитории."
        )
    return "\n".join(lines)


def confirm_keyboard(token: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Отправить", callback_data=f"confirm:{token}")
    builder.button(text="❌ Отмена", callback_data=f"cancel:{token}")
    return builder.as_markup()


async def owner_only(message: Message) -> bool:
    if message.from_user is None or message.from_user.id != OWNER_ID:
        await message.answer("Этот бот приватный и настроен для другого пользователя.")
        return False
    return True


async def cmd_start(message: Message) -> None:
    if not await owner_only(message):
        return
    await message.answer(
        "Диспетчер рассылок готов.\n\n"
        "1. Форвардните сообщение клиента с текстом рассылки.\n"
        "2. Следующим сообщением пришлите инструкцию:\n"
        "   бот: <алиас из clients.json>\n"
        "   время: 18:00 (необязательно, по умолчанию — сразу)\n"
        "   кнопка: Текст | Ссылка (необязательно)\n"
        "3. Проверьте превью и нажмите «Отправить»."
    )


async def handle_forward(message: Message) -> None:
    if not await owner_only(message):
        return
    text = message.text or message.caption
    if not text:
        await message.answer("В этом сообщении нет текста — форвардните текстовую рассылку.")
        return
    pending_forwards[message.chat.id] = PendingForward(text=text)
    await message.answer(
        "Принял текст рассылки. Теперь пришлите инструкцию:\n"
        "бот: <алиас>\nвремя: 18:00 (необязательно)\nкнопка: Текст | Ссылка (необязательно)"
    )


async def handle_instruction(message: Message) -> None:
    if not await owner_only(message):
        return
    pending = pending_forwards.get(message.chat.id)
    if pending is None:
        await message.answer(
            "Сначала форвардните сообщение с текстом рассылки, потом пришлите инструкцию."
        )
        return

    fields = parse_instruction(message.text or "")
    bot_token = fields.get("бот") or fields.get("бот_id") or fields.get("bot")
    if not bot_token:
        await message.answer("Не нашёл строку 'бот: <алиас>' в инструкции. Попробуйте ещё раз.")
        return

    clients = load_clients()
    resolved = resolve_client(clients, bot_token)
    if resolved is None:
        available = ", ".join(
            f"{cfg.get('alias')} ({name})" if cfg.get("alias") else name
            for name, cfg in clients.items()
        )
        await message.answer(f"Не нашёл получателя '{bot_token}'. Доступные: {available or '(пусто)'}")
        return
    name, cfg = resolved

    try:
        send_time = parse_send_time(fields.get("время") or fields.get("time"))
    except ValueError as e:
        await message.answer(str(e))
        return

    button_text = button_url = None
    button_raw = fields.get("кнопка") or fields.get("button")
    if button_raw:
        if "|" not in button_raw:
            await message.answer("Кнопку укажите в формате 'Текст | Ссылка'.")
            return
        button_text, button_url = (part.strip() for part in button_raw.split("|", 1))

    broadcast = PendingBroadcast(
        client_name=name,
        text=pending.text,
        group_id=cfg.get("group_id"),
        send_time=send_time,
        button_text=button_text,
        button_url=button_url,
    )
    token = f"{message.chat.id}:{message.message_id}"
    pending_broadcasts[token] = broadcast
    del pending_forwards[message.chat.id]

    await message.answer(format_preview(name, cfg, broadcast), reply_markup=confirm_keyboard(token))


async def handle_confirm(callback: CallbackQuery) -> None:
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Недоступно.", show_alert=True)
        return
    token = callback.data.split(":", 1)[1]
    broadcast = pending_broadcasts.pop(token, None)
    if broadcast is None:
        await callback.message.edit_text("Эта рассылка уже обработана или устарела.")
        await callback.answer()
        return

    clients = load_clients()
    cfg = clients[broadcast.client_name]
    extra = {}
    if broadcast.button_text:
        extra["buttons"] = [
            {"line": 0, "index_in_line": 0, "text": broadcast.button_text,
             "type": "inline", "url": broadcast.button_url}
        ]
    payload = build_payload(broadcast.text, broadcast.group_id, broadcast.send_time,
                             extra=extra)
    result = send_broadcast(cfg["api_key"], payload)
    await callback.message.edit_text(
        callback.message.text + f"\n\n✅ Отправлено. Ответ Salebot: {result}"
    )
    await callback.answer("Отправлено")


async def handle_cancel(callback: CallbackQuery) -> None:
    if callback.from_user.id != OWNER_ID:
        await callback.answer("Недоступно.", show_alert=True)
        return
    token = callback.data.split(":", 1)[1]
    pending_broadcasts.pop(token, None)
    await callback.message.edit_text(callback.message.text + "\n\n❌ Отменено.")
    await callback.answer("Отменено")


async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.message.register(cmd_start, Command("start"))
    dp.message.register(handle_forward, F.forward_origin)
    dp.message.register(handle_instruction, F.text, ~F.forward_origin)
    dp.callback_query.register(handle_confirm, F.data.startswith("confirm:"))
    dp.callback_query.register(handle_cancel, F.data.startswith("cancel:"))

    logger.info("Диспетчер запущен, жду сообщений. Остановить — Ctrl+C.")
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
