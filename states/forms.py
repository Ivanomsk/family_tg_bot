from aiogram.fsm.state import State, StatesGroup


class ConfigRequest(StatesGroup):
    waiting_for_device = State()
    waiting_for_reject_reason = State()


class ProxyRequest(StatesGroup):
    waiting_for_admin = State()
    waiting_for_name = State()
    waiting_for_key = State()
    waiting_for_data = State()


class NewsRequest(StatesGroup):
    waiting_for_text = State()


class ProblemReport(StatesGroup):
    waiting_for_text = State()


class ProxyIssue(StatesGroup):
    waiting_for_name = State()
    waiting_for_key = State()


class VpnIssue(StatesGroup):
    waiting_for_username = State()
    waiting_for_device = State()
    waiting_for_confirm = State()


class ProxyExtend(StatesGroup):
    waiting_for_decision = State()
