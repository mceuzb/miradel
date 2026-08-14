from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import ModuleChangeLog, ModuleSetting

# 3.3-bo'limdagi "Nazorat qilinadigan modullar ro'yxati"
MODULE_KEYS: dict[str, str] = {
    "mandatory_subscription": "Majburiy kanalga a'zolik",
    "referral_system": "Referal tizimi",
    "contest_module": "Sovg'ali konkurslar",
    "payment_module": "To'lov moduli",
    "notifications": "Bildirishnomalar",
    "task_module": "Vazifa va topshiriqlar",
    "rating_leaderboard": "Reyting/gamifikatsiya",
    "parent_panel": "Ota-ona paneli",
    "alpino_module": "Alpino — ball, market va referral tizimi",
}


async def ensure_module_defaults(session: AsyncSession) -> None:
    """Barcha modullarni standart holatda (is_enabled=false) bazaga kiritadi,
    agar hali mavjud bo'lmasa. 3.3-bo'lim: hech bir modul admin yoqmaguncha ishlamaydi."""
    result = await session.execute(select(ModuleSetting.module_key))
    existing = {row[0] for row in result.all()}
    for key in MODULE_KEYS:
        if key not in existing:
            session.add(ModuleSetting(module_key=key, is_enabled=False))
    await session.commit()


async def is_module_enabled(session: AsyncSession, module_key: str) -> bool:
    result = await session.execute(
        select(ModuleSetting.is_enabled).where(ModuleSetting.module_key == module_key)
    )
    row = result.scalar_one_or_none()
    # Bazada topilmasa ham, xavfsizlik uchun standart holat - o'chiq
    return bool(row) if row is not None else False


async def get_all_modules(session: AsyncSession) -> list[ModuleSetting]:
    result = await session.execute(select(ModuleSetting).order_by(ModuleSetting.module_key))
    return list(result.scalars().all())


async def toggle_module(session: AsyncSession, module_key: str, changed_by: int) -> ModuleSetting:
    result = await session.execute(
        select(ModuleSetting).where(ModuleSetting.module_key == module_key)
    )
    setting = result.scalar_one_or_none()
    if setting is None:
        setting = ModuleSetting(module_key=module_key, is_enabled=False)
        session.add(setting)
        await session.flush()

    old_value = setting.is_enabled
    setting.is_enabled = not setting.is_enabled
    setting.updated_by = changed_by

    session.add(ModuleChangeLog(
        module_key=module_key,
        old_value=old_value,
        new_value=setting.is_enabled,
        changed_by=changed_by,
    ))
    await session.commit()
    await session.refresh(setting)
    return setting
