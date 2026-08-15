"""O'qituvchi ism-familiya+guruh bilan qo'lda qo'shgan o'quvchilar uchun
xizmat funksiyalari: login/parol generatsiyasi, admin tasdig'i navbati va
o'quvchi keyinroq Telegram ochganda login orqali hisobini bog'lash.
"""

import enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User, UserRole, UserStatus
from bot.services.group_service import enroll_student
from bot.utils.credentials import generate_login_code, generate_password, hash_password, verify_password

TEACHER_ENROLLED_SOURCE = "teacher_enrolled"


class LinkResult(str, enum.Enum):
    OK = "ok"                          # muvaffaqiyatli bog'landi (yoki allaqachon shu odamga bog'liq edi)
    BAD_CREDENTIALS = "bad_credentials"  # login yoki parol xato
    ALREADY_LINKED = "already_linked"    # bu login boshqa Telegram hisobiga allaqachon bog'langan
    TELEGRAM_TAKEN = "telegram_taken"    # bu Telegram hisobi allaqachon boshqa profilga bog'langan


async def _generate_unique_login(session: AsyncSession) -> str:
    for _ in range(30):
        login = generate_login_code()
        existing = await session.scalar(select(User).where(User.login == login))
        if existing is None:
            return login
    raise RuntimeError("Login generatsiya qilib bo'lmadi, qaytadan urinib ko'ring")


async def create_teacher_student(
    session: AsyncSession, teacher: User, full_name: str, group_id: int | None,
) -> tuple[User, str]:
    """Yangi o'quvchini telegramsiz qo'shadi. Qaytaradi: (User, ochiq_parol).
    Ochiq parol faqat shu funksiya natijasida bir marta qaytariladi - bazaga
    faqat uning hash'i yoziladi, shuning uchun buni darhol o'qituvchiga
    ko'rsatish kerak."""
    login = await _generate_unique_login(session)
    password = generate_password()
    user = User(
        telegram_id=None,
        full_name=full_name,
        role=UserRole.STUDENT,
        status=UserStatus.PENDING,
        source=TEACHER_ENROLLED_SOURCE,
        login=login,
        password_hash=hash_password(password),
        added_by_teacher_id=teacher.id,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    if group_id is not None:
        await enroll_student(session, group_id, user.id)

    return user, password


async def get_teacher_added_pending(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User).where(
            User.source == TEACHER_ENROLLED_SOURCE,
            User.status == UserStatus.PENDING,
        )
    )
    return list(result.scalars().all())


async def link_telegram_by_credentials(
    session: AsyncSession, login: str, password: str, telegram_id: int, username: str | None,
) -> tuple[LinkResult, User | None]:
    """Login+parolni tekshiradi va to'g'ri bo'lsa shu Telegram hisobini
    profilga bog'laydi (birinchi marta). Profil allaqachon shu telegram_id'ga
    bog'langan bo'lsa ham OK qaytaradi (qayta urinishlar xavfsiz)."""
    user = await session.scalar(select(User).where(User.login == login.strip().upper()))
    if user is None or not user.password_hash or not verify_password(password, user.password_hash):
        return LinkResult.BAD_CREDENTIALS, None

    if user.telegram_id is not None:
        if user.telegram_id == telegram_id:
            return LinkResult.OK, user
        return LinkResult.ALREADY_LINKED, None

    other = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if other is not None:
        return LinkResult.TELEGRAM_TAKEN, None

    user.telegram_id = telegram_id
    user.username = username
    await session.commit()
    await session.refresh(user)
    return LinkResult.OK, user
