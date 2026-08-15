from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    waiting_full_name = State()
    waiting_phone = State()
    waiting_course = State()


class GroupCreation(StatesGroup):
    waiting_name = State()
    waiting_subject = State()
    waiting_status = State()


class TaskCreation(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_deadline = State()


class TaskSubmission(StatesGroup):
    waiting_content = State()


class ChannelCreation(StatesGroup):
    waiting_username = State()


class ContestCreation(StatesGroup):
    waiting_type = State()
    waiting_title = State()
    waiting_end_date = State()
    waiting_winners_count = State()
    waiting_prize = State()


class RandomContestFinish(StatesGroup):
    waiting_winner_id = State()


class BroadcastCreation(StatesGroup):
    waiting_text = State()
    waiting_group = State()
    waiting_confirm = State()


class BroadcastLeadCapture(StatesGroup):
    waiting_name = State()
    waiting_phone = State()


class TeacherAddStudent(StatesGroup):
    """O'qituvchi o'quvchini telegramsiz, ism-familiya+guruh bilan qo'shishi."""
    waiting_full_name = State()
    waiting_group = State()


class CredentialsLogin(StatesGroup):
    """Guruhga o'qituvchi tomonidan qo'shilgan, hali telegram_id bog'lanmagan
    o'quvchi login+parol kiritib o'z hisobini shu Telegram akkauntga bog'laydi."""
    waiting_login = State()
    waiting_password = State()
