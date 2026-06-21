from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from handlers.main_menu import require_private_chat

from keyboards.inline import get_vpn_request_keyboard

from config import ADMIN_IDS

from utils.logger import audit_logger
from states.forms import ConfigRequest

router = Router()

# ==========================================
# ЗАПРОС НОВОГО VPN
# ==========================================

@router.callback_query(F.data == "vpn_request")
async def vpn_request(callback: types.CallbackQuery, state: FSMContext):
    if not await require_private_chat(callback, "запрос VPN"):
        return
    await callback.answer()
    await state.set_state(ConfigRequest.waiting_for_device)
    await callback.message.edit_text(
        "?? <b>Запрос нового VPN конфига</b>\n\n"
        "Для какого устройства нужен конфиг?\n\n"
        "Напиши название (например: iPhone, MacBook, Android)\n\n"
        "Или нажми кнопку отмены.",
        reply_markup=get_vpn_request_keyboard().as_markup(),
        parse_mode="HTML"
    )


@router.message(ConfigRequest.waiting_for_device, F.text)
async def process_vpn_device(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        await message.answer("? Запрос отменён.", reply_markup=get_back_to_main_menu().as_markup())
        return
    
    device = message.text.strip()
    user = message.from_user
    username = user.username or f"ID:{user.id}"
    
    requests = load_json("bot_data/vpn_requests.json", {})
    requests[str(user.id)] = {
        "username": username,
        "device": device,
        "timestamp": datetime.now().isoformat()
    }
    save_json("bot_data/vpn_requests.json", requests)
    
    request_msg = (
        f"?? <b>НОВЫЙ ЗАПРОС VPN</b>\n\n"
        f"?? @{username}\n"
        f"?? ID: {user.id}\n"
        f"?? Устройство: {device}"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                request_msg,
                reply_markup=get_admin_vpn_request_keyboard(user.id).as_markup(),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки админу {admin_id}: {e}")
    
    await message.answer(
        "? <b>Запрос отправлен админу!</b>\n\nОжидай ответа.",
        reply_markup=get_back_to_main_menu().as_markup(),
        parse_mode="HTML"
    )
    await state.clear()
