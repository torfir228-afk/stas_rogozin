import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _get_env(name: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(
            f"Переменная окружения {name} обязательна, но не задана. Проверьте файл .env"
        )
    return value


@dataclass(frozen=True)
class Config:
    bot_token: str
    channel_id: str
    channel_url: str
    lead_magnet_url: str
    lead_magnet_file_path: Optional[str]
    reminder_1_delay_minutes: int
    reminder_2_delay_minutes: int
    db_path: str
    jobs_db_path: str


def load_config() -> Config:
    return Config(
        bot_token=_get_env("BOT_TOKEN", required=True),
        channel_id=_get_env("CHANNEL_ID", required=True),
        channel_url=_get_env("CHANNEL_URL", required=True),
        lead_magnet_url=_get_env("LEAD_MAGNET_URL", required=True),
        lead_magnet_file_path=_get_env("LEAD_MAGNET_FILE_PATH") or None,
        reminder_1_delay_minutes=int(_get_env("REMINDER_1_DELAY_MINUTES", "10")),
        reminder_2_delay_minutes=int(_get_env("REMINDER_2_DELAY_MINUTES", "120")),
        db_path=_get_env("DB_PATH", "data/bot.sqlite3"),
        jobs_db_path=_get_env("JOBS_DB_PATH", "data/jobs.sqlite3"),
    )


config = load_config()
