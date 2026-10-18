from aiogram.fsm.state import State, StatesGroup


class AppealForm(StatesGroup):
    choosing_type = State()
    choosing_district = State()
    choosing_topic = State()
    entering_text = State()
    choosing_reply = State()
    confirming = State()


class AdminReply(StatesGroup):
    waiting_text = State()
