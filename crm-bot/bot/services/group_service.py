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


# ---------------------------------------------------------------------------
# O'qituvchi uchun guruh boshqaruvi (Alpino ilovasi ichida) - TZ: o'qituvchi
# o'ziga biriktirilgan guruhlarga o'z kiritgan o'quvchilarini qo'sha oladi,
# guruh nomlay oladi, o'quvchini guruhdan guruhga ko'chira oladi. Guruhning
# enrollment_status'i (ochiq/yopiq) marketing maqsadida bo'lib, bu yerda
# ahamiyatsiz.
# ---------------------------------------------------------------------------

async def get_teacher_groups(session: AsyncSession, teacher_id: int) -> list[Group]:
    result = await session.execute(
        select(Group).where(Group.teacher_id == teacher_id, Group.is_archived == False)  # noqa: E712
        .order_by(Group.created_at)
    )
    return list(result.scalars().all())


async def create_teacher_group(session: AsyncSession, teacher_id: int, name: str, subject: str | None = None) -> Group:
    group = Group(name=name, subject=subject, teacher_id=teacher_id)
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return group


async def rename_teacher_group(session: AsyncSession, teacher_id: int, group_id: int, name: str) -> Group | None:
    group = await session.get(Group, group_id)
    if group is None or group.teacher_id != teacher_id:
        return None
    group.name = name
    await session.commit()
    await session.refresh(group)
    return group


async def get_group_student_counts(session: AsyncSession, group_ids: list[int]) -> dict[int, int]:
    if not group_ids:
        return {}
    from sqlalchemy import func as sa_func
    rows = await session.execute(
        select(GroupStudent.group_id, sa_func.count(GroupStudent.id))
        .where(GroupStudent.group_id.in_(group_ids))
        .group_by(GroupStudent.group_id)
    )
    return {gid: count for gid, count in rows.all()}


async def get_teacher_students_with_current_group(
    session: AsyncSession, teacher_id: int,
) -> list[tuple[User, int | None]]:
    """O'qituvchi botda o'zi qo'shgan barcha o'quvchilarni, har birining
    O'SHA O'QITUVCHIGA tegishli joriy guruhi (agar bor bo'lsa) bilan
    birga qaytaradi. (User, group_id | None) juftliklari."""
    from bot.database.models import UserStatus

    students_result = await session.execute(
        select(User).where(
            User.added_by_teacher_id == teacher_id,
            User.role == UserRole.STUDENT,
            User.status != UserStatus.REMOVED,
        ).order_by(User.full_name)
    )
    students = list(students_result.scalars().all())
    if not students:
        return []

    student_ids = [s.id for s in students]
    gs_result = await session.execute(
        select(GroupStudent.student_id, GroupStudent.group_id)
        .join(Group, Group.id == GroupStudent.group_id)
        .where(GroupStudent.student_id.in_(student_ids), Group.teacher_id == teacher_id)
    )
    current_group_by_student = {sid: gid for sid, gid in gs_result.all()}
    return [(s, current_group_by_student.get(s.id)) for s in students]


async def move_student_to_group(
    session: AsyncSession, teacher_id: int, group_id: int, student_id: int,
) -> bool:
    """O'quvchini shu o'qituvchining guruhiga qo'shadi/ko'chiradi - agar
    o'quvchi shu o'qituvchining boshqa guruhida bo'lsa, avval o'shandan
    chiqariladi (bir o'qituvchi doirasida bitta guruh)."""
    group = await session.get(Group, group_id)
    student = await session.get(User, student_id)
    if group is None or group.teacher_id != teacher_id:
        return False
    if student is None or student.added_by_teacher_id != teacher_id:
        return False

    # Shu o'qituvchining boshqa guruh(lar)idagi eski a'zolikni tozalaymiz.
    old_result = await session.execute(
        select(GroupStudent).join(Group, Group.id == GroupStudent.group_id)
        .where(GroupStudent.student_id == student_id, Group.teacher_id == teacher_id)
    )
    for old in old_result.scalars().all():
        await session.delete(old)

    existing = await session.scalar(
        select(GroupStudent).where(GroupStudent.group_id == group_id, GroupStudent.student_id == student_id)
    )
    if existing is None:
        session.add(GroupStudent(group_id=group_id, student_id=student_id))
    await session.commit()
    return True


async def remove_student_from_teacher_group(
    session: AsyncSession, teacher_id: int, group_id: int, student_id: int,
) -> bool:
    group = await session.get(Group, group_id)
    if group is None or group.teacher_id != teacher_id:
        return False
    row = await session.scalar(
        select(GroupStudent).where(GroupStudent.group_id == group_id, GroupStudent.student_id == student_id)
    )
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True
