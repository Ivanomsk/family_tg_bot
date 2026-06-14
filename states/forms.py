from aiogram.fsm.state import State, StatesGroup

class ConfigRequest(StatesGroup):
    waiting_for_device = State()
    waiting_for_reject_reason = State()

class ProxyRequest(StatesGroup):
    waiting_for_name = State()
    waiting_for_data = State()