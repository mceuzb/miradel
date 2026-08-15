from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.config import get_config
from bot.database.models import Base


def _normalize_url(url: str) -> str:
    """Railway PostgreSQL DATABASE_URL odatda 'postgres://' yoki 'postgresql://'
    ko'rinishida beriladi, lekin asyncpg drayveri uchun 'postgresql+asyncpg://' kerak."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


config = get_config()
engine = create_async_engine(_normalize_url(config.database_url), pool_pre_ping=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------------------------------------------------------
# MUHIM: `create_all()` faqat YO'Q jadvallarni yaratadi - mavjud jadvalga
# keyinroq models.py'da qo'shilgan YANGI USTUNLARNI hech qachon qo'shmaydi.
# `migrations/0002_alpino_market_catalog.py` xato joyga (versions/ papkasi
# TASHQARISIGA) qo'yilib qolgani sababli Alembic orqali ham qo'llanmagan edi -
# natijada masalan `alpino_points_history.comment` bazada yo'q edi
# ("UndefinedColumnError"). Quyidagi ro'yxat - shu holatlar uchun
# o'z-o'zini tuzatuvchi (idempotent) yamoq: har bot ishga tushganda
# yetishmayotgan ustun bo'lsa - qo'shib qo'yadi, bo'lsa - hech narsa qilmaydi.
_MISSING_COLUMN_PATCHES: list[str] = [
    "ALTER TABLE alpino_points_history ADD COLUMN IF NOT EXISTS comment TEXT",
    "ALTER TABLE alpino_market_orders ADD COLUMN IF NOT EXISTS item_id INTEGER "
    "REFERENCES alpino_market_items(id)",
    "ALTER TABLE alpino_market_orders ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ",
    "ALTER TABLE alpino_referrals ADD COLUMN IF NOT EXISTS paid_bonus_month VARCHAR(7)",
    # market_items.image_url avval VARCHAR(500) edi - miniapp rasmni base64
    # (data:image/...) shaklida yuboradi, bu odatda 500 belgidan ancha uzun
    # bo'ladi va StringDataRightTruncationError berardi. TEXT ga o'tkazish
    # xavfsiz va qayta ishga tushirilsa ham xato bermaydi.
    "ALTER TABLE alpino_market_items ALTER COLUMN image_url TYPE TEXT",
    # Login/parol orqali ro'yxatga olish (telegramsiz o'quvchilar) - o'qituvchi
    # ism-familiya+guruh bilan qo'lda qo'shgan o'quvchida hali telegram_id
    # bo'lmaydi, shuning uchun bu ustun endi NOT NULL emas.
    "ALTER TABLE users ALTER COLUMN telegram_id DROP NOT NULL",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'telegram_lead'",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS login VARCHAR(16)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS added_by_teacher_id INTEGER REFERENCES users(id)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_login ON users(login) WHERE login IS NOT NULL",
    # Alpino kirish huquqi login+parol TO'G'RI kiritilganda True bo'ladi -
    # eski (allaqachon Telegram bog'langan) o'quvchilar ham shu orqali
    # o'tishi shart (bot/handlers/login.py).
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS alpino_verified BOOLEAN NOT NULL DEFAULT FALSE",
]

# Postgres native ENUM turlariga yangi qiymat qo'shish uchun (oddiy
# ALTER COLUMN/ADD COLUMN'dan farqli - alohida buyruq talab qiladi).
# SQLAlchemy `Enum(UserStatus)` uchun avtomatik nom (name= berilmagani
# uchun) - klass nomining kichik harflari: "userstatus".
_MISSING_ENUM_VALUE_PATCHES: list[tuple[str, str]] = [
    # (enum turi nomi, qo'shiladigan yangi qiymat)
    ("userstatus", "removed"),
]


async def _patch_missing_columns(conn) -> None:
    # Har bir buyruqni ALOHIDA SAVEPOINT'da bajaramiz - shu tarzda, agar
    # ulardan biri (masalan enum nomi noto'g'ri bo'lib chiqsa) xato bersa,
    # faqat o'sha buyruq bekor bo'ladi, QOLGAN patchlar (va create_all)
    # baribir muvaffaqiyatli commit bo'ladi. Avval BARCHASI bitta katta
    # tranzaksiyada edi - bittasi xato bersa, HAMMASI (hatto ilgari ishlab
    # turgan patchlar ham) bekor bo'lib, bot butunlay ishga tushmay qolardi.
    for statement in _MISSING_COLUMN_PATCHES:
        try:
            async with conn.begin_nested():
                await conn.execute(text(statement))
        except Exception as exc:
            print(f"[init_db] Patch o'tmadi (e'tiborsiz qoldirildi): {statement!r} -> {exc}")

    for enum_name, value in _MISSING_ENUM_VALUE_PATCHES:
        try:
            async with conn.begin_nested():
                await conn.execute(text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'"))
        except Exception as exc:
            print(f"[init_db] Enum patch o'tmadi (e'tiborsiz qoldirildi): {enum_name}.{value} -> {exc}")

    # Bitta odam faqat bir marta referral bo'la olishi - mavjud takrorlar
    # bo'lsa xato bermasligi uchun alohida, xavfsiz tekshiruv bilan.
    try:
        async with conn.begin_nested():
            exists = await conn.execute(text(
                "SELECT 1 FROM pg_constraint WHERE conname = 'uq_alpino_referred_once'"
            ))
            if exists.first() is None:
                await conn.execute(text(
                    "ALTER TABLE alpino_referrals ADD CONSTRAINT uq_alpino_referred_once UNIQUE (referred_id)"
                ))
    except Exception as exc:
        print(f"[init_db] Referral constraint patch o'tmadi: {exc}")


async def init_db() -> None:
    """MVP uchun jadvallarni avtomatik yaratadi. Keyingi bosqichda Alembic
    migratsiyalariga o'tish tavsiya etiladi (production uchun)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _patch_missing_columns(conn)
