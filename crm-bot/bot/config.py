import os
from dataclasses import dataclass, field


def _get_env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Environment variable {name} is required but not set")
    return value


@dataclass
class Config:
    bot_token: str = field(default_factory=lambda: _get_env("BOT_TOKEN", required=True))
    database_url: str = field(default_factory=lambda: _get_env("DATABASE_URL", required=True))
    # Birinchi admin - bot birinchi marta ishga tushganda shu telegram_id avtomatik admin bo'ladi
    super_admin_id: int = field(default_factory=lambda: int(_get_env("SUPER_ADMIN_ID", "0")))
    timezone: str = field(default_factory=lambda: _get_env("TIMEZONE", "Asia/Tashkent"))


def get_config() -> Config:
    return Config()
