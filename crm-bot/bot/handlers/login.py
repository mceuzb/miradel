from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User, UserStatus
from bot.keyboards.menus import guest_menu_kb, menu_for_role, remove_kb
from bot.services.teacher_student_service import LinkResult, link_telegram_by_credentials
from bot.utils.states import CredentialsLogin

router = Router(name="login")


@router.message(F.text == "🔑 Login orqali kirish")
async def login_start(message: Message, state: FSMContext, db_user: User | None, session: AsyncSession, **kwargs):
    if db_user is not None:
        # Bu telegram allaqachon boshqa profilga bog'langan.
        await message.answer(
            "Siz allaqachon tizimga kirgansiz.",
            reply_markup=await menu_for_role(session, db_user),
        )
        return
    await message.answer(
        "O'qituvchingiz bergan login kodini kiriting (masalan: ST4821):",
        reply_markup=remove_kb(),
    )
    await state.set_state(CredentialsLogin.waiting_login)


@router.message(CredentialsLogin.waiting_login)
async def login_enter_login(message: Message, state: FSMContext):
    login = (message.text or "").strip()
    if len(login) < 3:
        await message.answer("Noto'g'ri login. Qaytadan kiriting:")
        return
    await state.update_data(login=login)
    await message.answer("Endi parolingizni kiriting:")
    await state.set_state(CredentialsLogin.waiting_password)


@router.message(CredentialsLogin.waiting_password)
async def login_enter_password(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    login = data.get("login", "")
    password = (message.text or "").strip()
    await state.clear()

    result, user = await link_telegram_by_credentials(
        session, login, password,
        telegram_id=message.from_user.id,
        username=message.from_user.username,
    )

    if result == LinkResult.BAD_CREDENTIALS:
        await message.answer(
            "❌ Login yoki parol noto'g'ri. Qaytadan urinish uchun "
            "\"🔑 Login orqali kirish\" tugmasini bosing.",
            reply_markup=guest_menu_kb(),
        )
        return

    if result == LinkResult.ALREADY_LINKED:
        await message.answer(
            "❌ Bu login boshqa Telegram hisobiga allaqachon bog'langan. "
            "Agar bu xato deb hisoblasangiz, adminга murojaat qiling.",
            reply_markup=guest_menu_kb(),
        )
        return

    if result == LinkResult.TELEGRAM_TAKEN:
        await message.answer(
            "❌ Sizning Telegram hisobingiz allaqachon boshqa profilga bog'langan. "
            "Adminga murojaat qiling.",
            reply_markup=guest_menu_kb(),
        )
        return

    assert user is not None
    if user.status == UserStatus.PENDING:
        await message.answer(
            f"✅ Login muvaffaqiyatli tasdiqlandi, {user.full_name}!\n\n"
            f"⏳ Lekin hisobingiz hali admin tomonidan ko'rib chiqilmoqda. "
            f"Tasdiqlangach xabar beramiz."
        )
        return
    if user.status == UserStatus.BLOCKED:
        await message.answer("🚫 Hisobingiz bloklangan. Administratorga murojaat qiling.")
        return
    if user.status == UserStatus.REJECTED:
        await message.answer("❌ Hisobingiz rad etilgan. Administratorga murojaat qiling.")
        return

    await message.answer(
        f"🎉 Xush kelibsiz, {user.full_name}! Shaxsiy kabinetingiz va Alpino'dan foydalanishingiz mumkin.",
        reply_markup=await menu_for_role(session, user),
    )
