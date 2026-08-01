from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_config
from bot.database.models import User, UserRole, UserStatus
from bot.keyboards.menus import contact_request_kb, guest_menu_kb, menu_for_role, remove_kb
from bot.services.user_service import (
    create_pending_user, ensure_super_admin, get_user_by_telegram_id,
)
from bot.utils.states import Registration

router = Router(name="start")
config = get_config()

WELCOME_TEXT = (
    "👋 Assalomu alaykum! <b>Miradel Academy</b> botiga xush kelibsiz.\n\n"
    "Bu yerda o'quv markazimiz yangiliklari, kurslar jadvali va konkurslar bilan "
    "tanishishingiz mumkin.\n\n"
    "O'quvchi sifatida tizimga qo'shilish uchun \"📝 Ro'yxatdan o'tish\" tugmasini bosing."
)


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()
    telegram_id = message.from_user.id

    # Config.super_admin_id orqali birinchi admin avtomatik tasdiqlanadi
    if telegram_id == config.super_admin_id:
        await ensure_super_admin(session, telegram_id)

    user = await get_user_by_telegram_id(session, telegram_id)

    if user is not None:
        if user.status == UserStatus.APPROVED:
            await message.answer(
                f"Xush kelibsiz, {user.full_name}!",
                reply_markup=menu_for_role(user.role),
            )
        elif user.status == UserStatus.PENDING:
            await message.answer("⏳ Arizangiz hali ko'rib chiqilmoqda. Iltimos, kuting.")
        elif user.status == UserStatus.BLOCKED:
            await message.answer("🚫 Hisobingiz bloklangan.")
        elif user.status == UserStatus.REJECTED:
            await message.answer(WELCOME_TEXT, reply_markup=guest_menu_kb())
        return

    # Diqqat: ref_ havoladagi referal AccessControlMiddleware'da allaqachon
    # DB'ga (Referral, status=pending) yozib qo'yilgan - bu yerda qayta ishlash shart emas.
    await message.answer(WELCOME_TEXT, reply_markup=guest_menu_kb())


@router.message(F.text == "📝 Ro'yxatdan o'tish")
async def start_registration(message: Message, session: AsyncSession, state: FSMContext, **kwargs):
    existing = await get_user_by_telegram_id(session, message.from_user.id)
    if existing is not None and existing.status == UserStatus.APPROVED:
        await message.answer("Siz allaqachon ro'yxatdan o'tgansiz.", reply_markup=menu_for_role(existing.role))
        return
    if existing is not None and existing.status == UserStatus.PENDING:
        await message.answer("⏳ Arizangiz allaqachon yuborilgan, admin javobini kuting.")
        return

    await message.answer(
        "Ro'yxatdan o'tish uchun to'liq ism-familiyangizni kiriting:",
        reply_markup=remove_kb(),
    )
    await state.set_state(Registration.waiting_full_name)


@router.message(Registration.waiting_full_name)
async def process_full_name(message: Message, state: FSMContext):
    full_name = (message.text or "").strip()
    if len(full_name) < 3:
        await message.answer("Iltimos, to'liq ism-familiyangizni kiriting (kamida 3 belgi):")
        return
    await state.update_data(full_name=full_name)
    await message.answer(
        "Rahmat! Endi telefon raqamingizni yuboring:",
        reply_markup=contact_request_kb(),
    )
    await state.set_state(Registration.waiting_phone)


@router.message(Registration.waiting_phone, F.contact)
async def process_phone_contact(message: Message, state: FSMContext, session: AsyncSession):
    await _finish_registration(message, state, session, message.contact.phone_number)


@router.message(Registration.waiting_phone, F.text)
async def process_phone_text(message: Message, state: FSMContext, session: AsyncSession):
    phone = message.text.strip()
    if len(phone) < 7:
        await message.answer("Noto'g'ri format. Telefon raqamingizni yuboring (masalan +998901234567):")
        return
    await _finish_registration(message, state, session, phone)


async def _finish_registration(message: Message, state: FSMContext, session: AsyncSession, phone: str):
    data = await state.get_data()
    full_name = data["full_name"]

    user = await create_pending_user(
        session, message.from_user.id, full_name, phone,
        username=message.from_user.username,
    )
    await state.clear()

    await message.answer(
        "✅ Arizangiz qabul qilindi!\n"
        "Admin tasdiqlashini kuting - tez orada sizga xabar beramiz.",
        reply_markup=remove_kb(),
    )

    await _notify_admins_new_request(message, session, user)


async def _notify_admins_new_request(message: Message, session: AsyncSession, user: User):
    from sqlalchemy import select

    from bot.keyboards.admin_kb import approval_kb

    result = await session.execute(
        select(User).where(User.role == UserRole.ADMIN, User.status == UserStatus.APPROVED)
    )
    admins = result.scalars().all()
    text = (
        f"🆕 Yangi so'rov!\n\n"
        f"Ism: {user.full_name}\n"
        f"Telefon: {user.phone}\n"
        f"Telegram ID: {user.telegram_id}"
    )
    for admin in admins:
        try:
            await message.bot.send_message(admin.telegram_id, text, reply_markup=approval_kb(user.id))
        except Exception:
            continue
