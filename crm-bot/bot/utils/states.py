from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    waiting_full_name = State()
    waiting_phone = State()


class GroupCreation(StatesGroup):
    waiting_name = State()
    waiting_subject = State()


class TaskCreation(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_deadline = State()


class TaskSubmission(StatesGroup):
    waiting_content = State()


class ChannelCreation(StatesGroup):
    waiting_username = State()
