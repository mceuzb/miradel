from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Group, GroupEnrollmentStatus, GroupStudent, User, UserRole, UserStatus


async def get_open_groups(session: AsyncSession) -> list[Group]:
    result = await session.execute(
        select(Group).where(
            Group.is_archived == False,  # noqa: E712
            Group.enrollment_status != GroupEnrollmentStatus.CLOSED,
        )
    )
    return list(result.scalars().all())


async def enroll_student(session: AsyncSession, group_id: int, student_id: int) -> None:
    existing = await session.execute(
        select(GroupStudent).where(
            GroupStudent.group_id == group_id, GroupStudent.student_id == student_id
        )
    )
    if existing.scalar_one_or_none() is not None:
        return
    session.add(GroupStudent(group_id=group_id, student_id=student_id))
    await session.commit()


async def get_students_without_group(session: AsyncSession) -> list[User]:
    """Kurs biriktirilmagan (birorta ham guruhga a'zo bo'lmagan), lekin
    allaqachon tasdiqlangan o'quvchilar - ular ESKI (kurs tanlash funksiyasi
    qo'shilishidan oldingi) foydalanuvchilar bo'lishi mumkin."""
    enrolled_ids = select(GroupStudent.student_id)
    result = await session.execute(
        select(User).where(
            User.role == UserRole.STUDENT,
            User.status == UserStatus.APPROVED,
            User.id.not_in(enrolled_ids),
        )
    )
    return list(result.scalars().all())
