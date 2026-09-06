from datetime import datetime, timezone

import aiosqlite

from bot.config import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL,
    delivered_at TEXT,
    reminders_scheduled INTEGER NOT NULL DEFAULT 0
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def init_db() -> None:
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute(_SCHEMA)
        await db.commit()


async def mark_started(user_id: int) -> None:
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute(
            "INSERT INTO users (user_id, started_at) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO NOTHING",
            (user_id, _now()),
        )
        await db.commit()


async def is_delivered(user_id: int) -> bool:
    async with aiosqlite.connect(config.db_path) as db:
        cursor = await db.execute(
            "SELECT delivered_at FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return bool(row and row[0])


async def mark_delivered(user_id: int) -> None:
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute(
            "INSERT INTO users (user_id, started_at, delivered_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET delivered_at = excluded.delivered_at",
            (user_id, _now(), _now()),
        )
        await db.commit()


async def reminders_already_scheduled(user_id: int) -> bool:
    async with aiosqlite.connect(config.db_path) as db:
        cursor = await db.execute(
            "SELECT reminders_scheduled FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return bool(row and row[0])


async def mark_reminders_scheduled(user_id: int) -> None:
    async with aiosqlite.connect(config.db_path) as db:
        await db.execute(
            "INSERT INTO users (user_id, started_at, reminders_scheduled) VALUES (?, ?, 1) "
            "ON CONFLICT(user_id) DO UPDATE SET reminders_scheduled = 1",
            (user_id, _now()),
        )
        await db.commit()
