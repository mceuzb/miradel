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
    # Alpino web-server porti (Railway avtomatik PORT beradi)
    port: int = field(default_factory=lambda: int(_get_env("PORT", "8080")))
    # Railway "Generate Domain" bosilgach avtomatik beriladigan domen
    # (masalan: miradel-production.up.railway.app). Bot buni o'zi WebApp
    # tugmasi uchun to'liq https:// havolaga aylantiradi.
    railway_public_domain: str | None = field(default_factory=lambda: os.getenv("RAILWAY_PUBLIC_DOMAIN"))
    # Agar domen boshqacha (custom domain) bo'lsa, buni qo'lda ham berish mumkin
    alpino_webapp_url: str | None = field(default_factory=lambda: os.getenv("ALPINO_WEBAPP_URL"))
    # Referral havolasi (t.me/{username}?start=...) qurish uchun - @ belgisisiz
    bot_username: str | None = field(default_factory=lambda: os.getenv("BOT_USERNAME"))

    def get_alpino_url(self) -> str | None:
        if self.alpino_webapp_url:
            return self.alpino_webapp_url
        if self.railway_public_domain:
            return f"https://{self.railway_public_domain}/alpino"
        return None


def get_config() -> Config:
    return Config()
