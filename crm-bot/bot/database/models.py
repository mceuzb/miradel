import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, JSON,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"


class UserStatus(str, enum.Enum):
    PENDING = "pending"      # tasdiqlanmagan, hech narsaga kira olmaydi
    APPROVED = "approved"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class LessonStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    DONE = "done"
    CANCELLED = "cancelled"


class AttendanceStatus(str, enum.Enum):
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"


class ContestStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    FINISHED = "finished"


class ContestType(str, enum.Enum):
    REFERRAL = "referral"  # Eng ko'p do'st taklif qilgan g'olib bo'ladi
    RANDOM = "random"      # Ishtirokchilar ro'yxati shakllantiriladi, g'olib admin tomonidan tanlanadi


class GroupEnrollmentStatus(str, enum.Enum):
    OPEN = "open"            # 🟢 Qabul ochiq
    FILLING = "filling"      # 🟡 To'lmoqda
    FEW_SPOTS = "few_spots"  # 🔴 Joylar kam qolmoqda
    CLOSED = "closed"        # Yopiq - ommaviy ro'yxatda ko'rinmaydi


class ReferralStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REVOKED = "revoked"  # Taklif qilingan odam kanaldan chiqib ketgach


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.STUDENT)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.PENDING)
    referred_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    taught_groups: Mapped[list["Group"]] = relationship(back_populates="teacher")
    group_memberships: Mapped[list["GroupStudent"]] = relationship(back_populates="student")


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    enrollment_status: Mapped[GroupEnrollmentStatus] = mapped_column(
        Enum(GroupEnrollmentStatus, name="group_enrollment_status"),
        default=GroupEnrollmentStatus.OPEN,
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    teacher: Mapped["User"] = relationship(back_populates="taught_groups")
    students: Mapped[list["GroupStudent"]] = relationship(back_populates="group")
    lessons: Mapped[list["Lesson"]] = relationship(back_populates="group")


class GroupStudent(Base):
    __tablename__ = "group_students"
    __table_args__ = (UniqueConstraint("group_id", "student_id", name="uq_group_student"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    group: Mapped["Group"] = relationship(back_populates="students")
    student: Mapped["User"] = relationship(back_populates="group_memberships")


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[LessonStatus] = mapped_column(Enum(LessonStatus), default=LessonStatus.SCHEDULED)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    group: Mapped["Group"] = relationship(back_populates="lessons")
    attendance: Mapped[list["Attendance"]] = relationship(back_populates="lesson")


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("lesson_id", "student_id", name="uq_lesson_student"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[AttendanceStatus] = mapped_column(Enum(AttendanceStatus), default=AttendanceStatus.ABSENT)

    lesson: Mapped["Lesson"] = relationship(back_populates="attendance")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"), nullable=True)
    student_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    submissions: Mapped[list["TaskSubmission"]] = relationship(back_populates="task")


class TaskSubmission(Base):
    __tablename__ = "task_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    grade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    teacher_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    task: Mapped["Task"] = relationship(back_populates="submissions")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[int] = mapped_column(Integer)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    method: Mapped[str | None] = mapped_column(String(64), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    type: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ModuleSetting(Base):
    __tablename__ = "module_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_key: Mapped[str] = mapped_column(String(64), unique=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ModuleChangeLog(Base):
    __tablename__ = "module_change_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    module_key: Mapped[str] = mapped_column(String(64))
    old_value: Mapped[bool] = mapped_column(Boolean)
    new_value: Mapped[bool] = mapped_column(Boolean)
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RequiredChannel(Base):
    __tablename__ = "required_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel_username: Mapped[str] = mapped_column(String(255))
    channel_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invite_link: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Visitor(Base):
    """Botga kirgan HAR BIR odam (ro'yxatdan o'tgan yoki mehmon) shu yerda
    kuzatiladi. Konkurs/referal tizimi ro'yxatdan o'tishni talab qilmagani
    uchun ism va username shu jadvaldan olinadi (users jadvalidan emas)."""
    __tablename__ = "visitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Taklif qiluvchi va taklif qilingan - ikkalasi ham ro'yxatdan o'tgan bo'lishi
    # shart emas, shuning uchun users.id emas, xom telegram_id saqlanadi (2.4/8.2-bo'lim)
    referrer_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    referred_telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    status: Mapped[ReferralStatus] = mapped_column(Enum(ReferralStatus), default=ReferralStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # True bo'lsa - bu tasdiqlanish ZANJIRLI ball sxemasi orqali qayta ishlangan
    # (yangi tizim ishga tushirilgandan keyingi tasdiqlanish). False (eski
    # yozuvlar) - eski sxema bo'yicha faqat 1 ball sifatida hisoblanadi.
    chain_processed: Mapped[bool] = mapped_column(Boolean, default=False)


class ReferralPointsLedger(Base):
    """Zanjirli ball tizimi: har bir YANGI tasdiqlanish zanjirdagi barcha
    ajdodlarga masofasiga teng ball beradi. Faqat yangi (birinchi marta)
    tasdiqlanishlarda yoziladi - qayta qo'shilish (rejoin) va eski
    tasdiqlanishlar bu yerga yozilmaydi."""
    __tablename__ = "referral_points_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipient_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    points: Mapped[int] = mapped_column(Integer)
    source_referred_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    distance: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # False bo'lsa - manba (source_referred_telegram_id) kanaldan chiqib ketgani
    # uchun bu ball vaqtincha hisobga olinmaydi (qaytib kirsa True'ga qaytadi)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Contest(Base):
    __tablename__ = "contests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    contest_type: Mapped[ContestType] = mapped_column(Enum(ContestType), default=ContestType.REFERRAL)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    prizes: Mapped[dict] = mapped_column(JSON, default=dict)
    min_requirement: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[ContestStatus] = mapped_column(Enum(ContestStatus), default=ContestStatus.DRAFT)


class ContestParticipant(Base):
    """RANDOM turdagi konkurslar uchun - ishtirokchi ro'yxati. ID sifatida
    userning o'z telegram_id'si ishlatiladi (alohida ID generatsiya qilinmaydi)."""
    __tablename__ = "contest_participants"
    __table_args__ = (UniqueConstraint("contest_id", "telegram_id", name="uq_contest_participant"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("contests.id"))
    telegram_id: Mapped[int] = mapped_column(BigInteger)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContestResult(Base):
    __tablename__ = "contest_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("contests.id"))
    # G'olib ro'yxatdan o'tmagan bo'lishi ham mumkin - shuning uchun users.id emas
    winner_telegram_id: Mapped[int] = mapped_column(BigInteger)
    referral_count: Mapped[int] = mapped_column(Integer, default=0)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prize: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Broadcast(Base):
    """Admin tomonidan yuborilgan ommaviy xabar (odatda yangi kurs haqida)."""
    __tablename__ = "broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    total_targeted: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    is_sending: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BroadcastClick(Base):
    """Xabardagi inline tugmani bosganlar - 'ko'rdi/qiziqdi' statistikasi uchun."""
    __tablename__ = "broadcast_clicks"
    __table_args__ = (UniqueConstraint("broadcast_id", "telegram_id", name="uq_broadcast_click"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    broadcast_id: Mapped[int] = mapped_column(ForeignKey("broadcasts.id"))
    telegram_id: Mapped[int] = mapped_column(BigInteger)
    clicked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BroadcastLead(Base):
    """Tugmani bosib, ism+telefon qoldirganlar - 'kursga yozildi' ro'yxati."""
    __tablename__ = "broadcast_leads"
    __table_args__ = (UniqueConstraint("broadcast_id", "telegram_id", name="uq_broadcast_lead"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    broadcast_id: Mapped[int] = mapped_column(ForeignKey("broadcasts.id"))
    telegram_id: Mapped[int] = mapped_column(BigInteger)
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReferralCardOrder(Base):
    """Jismoniy referal kartochkasi buyurtmasi - kartada ism, konkurs haqida
    ma'lumot va userning referal havolasiga bog'langan QR kod bo'ladi."""
    __tablename__ = "referral_card_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(32))
    pickup_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# ALPINO - marketing/geymifikatsiya mini-app (TZ v3)
# ============================================================

class AlpinoPointsStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AlpinoOrderStatus(str, enum.Enum):
    PENDING = "pending"
    DELIVERED = "delivered"


class AlpinoReferralStatus(str, enum.Enum):
    CAME = "came"
    PAID = "paid"


class AlpinoPointsHistory(Base):
    """O'qituvchi ball TAKLIF qiladi (pending), Admin TASDIQLAYDI/RAD ETADI."""
    __tablename__ = "alpino_points_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    amount: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(64))  # vazifa/topshiriq/imtihon/referral/musobaqa
    status: Mapped[AlpinoPointsStatus] = mapped_column(Enum(AlpinoPointsStatus), default=AlpinoPointsStatus.PENDING)
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)  # o'qituvchi qoldirgan izoh
    reject_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AlpinoReferral(Base):
    __tablename__ = "alpino_referrals"
    __table_args__ = (UniqueConstraint("referred_id", name="uq_alpino_referred_once"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referrer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    referred_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[AlpinoReferralStatus] = mapped_column(Enum(AlpinoReferralStatus), default=AlpinoReferralStatus.CAME)
    # "2026-08" ko'rinishida - bir oyda +300 bonusni ikki marta bermaslik uchun
    paid_bonus_month: Mapped[str | None] = mapped_column(String(7), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlpinoMarketItem(Base):
    """Admin boshqaradigan market katalogi - nom, narx, son, rasm."""
    __tablename__ = "alpino_market_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cost_points: Mapped[int] = mapped_column(Integer)
    condition_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    tier: Mapped[str] = mapped_column(String(32), default="silver")  # premium / gold / silver
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AlpinoMarketOrder(Base):
    __tablename__ = "alpino_market_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    item_id: Mapped[int | None] = mapped_column(ForeignKey("alpino_market_items.id"), nullable=True)
    item_name: Mapped[str] = mapped_column(String(255))    # tarixiy - buyurtma vaqtidagi nom
    cost_points: Mapped[int] = mapped_column(Integer)       # tarixiy - buyurtma vaqtidagi narx
    status: Mapped[AlpinoOrderStatus] = mapped_column(Enum(AlpinoOrderStatus), default=AlpinoOrderStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AlpinoCategoryLimit(Base):
    __tablename__ = "alpino_category_limits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(64), unique=True)
    max_points: Mapped[int] = mapped_column(Integer)
    set_by_admin_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AlpinoWeeklyWinner(Base):
    __tablename__ = "alpino_weekly_winners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(64))
    winner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    period: Mapped[str] = mapped_column(String(32))  # masalan "2026-W33"
    points_given: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AlpinoFunnelEvent(Base):
    """User -> O'quvchi konversiya voronkasi. telegram_id ishlatiladi (users.id
    emas), chunki 'User' roli hali users jadvalida umuman bo'lmasligi mumkin."""
    __tablename__ = "alpino_funnel_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    event: Mapped[str] = mapped_column(String(32))  # viewed_alpino / clicked_enroll / enrolled
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
