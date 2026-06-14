from aiogram.fsm.state import State, StatesGroup

class ConfigRequest(StatesGroup):
    waiting_for_device = State()
    waiting_for_reject_reason = State()

class ProxyRequest(StatesGroup):
    waiting_for_name = State()
    waiting_for_data = State()

class NewsRequest(StatesGroup):
    """Состояния для публикации новости"""
    waiting_for_text = State()

class ProblemReport(StatesGroup):
    """Состояния для сообщения о проблеме"""
    waiting_for_text = State()