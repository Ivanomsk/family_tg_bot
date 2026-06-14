from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from pathlib import Path
import os, re, datetime, logging, asyncio

from config import ADMIN_IDS, VPN_DIR
from utils.auto_delete import schedule_delete, delete_temp, delete_user, delete_proxy_card, delete_admin
from utils.stats import update_stats
from utils.expiry import get_vpn_config_age
from utils.notifications import send_vpn_expiry_notification
from utils.rate_limit import is_rate_limited
from utils.audit import log_admin_action, log_suspicious_activity
from database.storage import load_json, save_json
from states.forms import ConfigRequest
from keyboards.inline import get_admin_vpn_request_keyboard as get_vpn_request_keyboard

router = Router()
logger = logging.getLogger(__name__)

active_uploads = {}
pending_requests = {}

def get_user_dir(username: str) -> str:
    if not username or len(username) > 50:
        log_suspicious_activity(0, "INVALID_USERNAME", f"Username: {username}")
        raise ValueError("Некорректный username")
    safe_name = re.sub(r'[^\w\-]', '_', username)
    if safe_name.startswith('.') or safe_name.startswith('/'):
        log_suspicious_activity(0, "PATH_TRAVERSAL_ATTEMPT", f"Username: {safe_name}")
        raise ValueError("Некорректный username")
    path = os.path.join(VPN_DIR, safe_name)
    if not Path(path).resolve().is_relative_to(Path(VPN_DIR).resolve()):
        log_suspicious_activity(0, "PATH_TRAVERSAL_BLOCKED", f"Path: {path}")
        raise ValueError("Попытка path traversal!")
    os.makedirs(path, exist_ok=True)
    return path

def get_user_configs(username: str) -> list:
    if not username: return []
    user_dir = get_user_dir(username)
    try: return sorted([f for f in os.listdir(user_dir) if f.endswith('.vpn')])
    except Exception: return []

@router.message(Command("vpn"))
async def cmd_vpn(message: types.Message):
    # 🔒 ПРОВЕРКА: только в ЛС!
    if message.chat.type != "private":
        msg = await message.answer(
            "🔐 VPN конфиги доступны только в личных сообщениях!\n\n"
            f"👉 Напиши боту в ЛС: t.me/{(await message.bot.get_me()).username}",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    is_limited, retry_after = is_rate_limited(message.from_user.id, "vpn")
    if is_limited:
        msg = await message.answer(f"⏳ Слишком много запросов. Попробуйте через {retry_after} сек.", parse_mode="HTML")
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    update_stats(message.from_user, "vpn")
    username = message.from_user.username
    if not username:
        msg = await message.answer("❌ Установи username в Telegram!", parse_mode="HTML")
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    configs = get_user_configs(username)
    expired_configs, expiring_configs = [], []
    for conf in configs:
        age = get_vpn_config_age(username, conf)
        if age["status"] == "expired": expired_configs.append({"filename": conf, "days_expired": abs(age["days_left"])})
        elif age["status"] == "expiring_soon": expiring_configs.append({"filename": conf, "days_left": age["days_left"]})

    if expired_configs or expiring_configs:
        await send_vpn_expiry_notification(message.bot, message.from_user.id, username, expired_configs, expiring_configs)

    builder = InlineKeyboardBuilder()
    for i, conf in enumerate(configs):
        age = get_vpn_config_age(username, conf)
        key = f"vpn_{i}"
        if age["status"] == "expired": button_text = f"❌ {conf.replace('.vpn', '')} (истёк)"
        elif age["status"] == "expiring_soon": button_text = f"⚠️ {conf.replace('.vpn', '')} ({age['days_left']} дн.)"
        else: button_text = f"🔹 {conf.replace('.vpn', '')}"
        builder.button(text=button_text, callback_data=key)

    if configs: builder.button(text="📦 Отправить все", callback_data="vpn_all")
    builder.button(text="🔄 Запросить новый конфиг", callback_data="vpn_request_new")
    builder.adjust(1)

    text = f"🔐 <b>@{username}</b>, найдено: {len(configs)}\n"
    if expired_configs or expiring_configs:
        text += "\n━━━━━━━━━━━━━━━━━━━━\n"
        for conf in expired_configs: text += f"❌ <b>{conf['filename'].replace('.vpn', '')}</b> — ИСТЁК {conf['days_expired']} дн. назад!\n"
        for conf in expiring_configs: text += f"⚠️ <b>{conf['filename'].replace('.vpn', '')}</b> — истекает через {conf['days_left']} дн.\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n💡 Если конфиг истёк — запроси новый через кнопку ниже\n\n"
    text += "Выбери или запроси новый:" if configs else f"🔐 <b>@{username}</b>, конфигов нет.\nНажми кнопку, чтобы запросить:"

    msg = await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)

@router.callback_query(F.data == "vpn_all")
async def process_vpn_all(callback: types.CallbackQuery):
    await callback.answer()
    username = callback.from_user.username
    configs = get_user_configs(username)
    if not configs:
        msg = await callback.message.answer("❌ Нет конфигов для отправки.", parse_mode="HTML")
        delete_user(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=callback.from_user.id, chat_type=callback.message.chat.type)
        return

    msg = await callback.message.answer(f"📦 Отправляю все ({len(configs)})...", parse_mode="HTML")
    delete_temp(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=callback.from_user.id, chat_type=callback.message.chat.type)

    user_dir = get_user_dir(username)
    sent_count, failed_count = 0, 0
    for conf in configs:
        try:
            file_path = os.path.join(user_dir, conf)
            if os.path.exists(file_path):
                await callback.message.answer_document(document=FSInputFile(file_path, filename=conf), caption=f"🔹 <b>{conf.replace('.vpn', '')}</b>", parse_mode="HTML")
                sent_count += 1
                await asyncio.sleep(0.3)
            else: failed_count += 1
        except Exception as e:
            failed_count += 1
            logger.error(f"Ошибка отправки конфига {conf}: {e}")
            await asyncio.sleep(0.3)

    if sent_count > 0:
        result_msg = await callback.message.answer(f"✅ <b>Отправлено конфигов: {sent_count}/{len(configs)}</b>", parse_mode="HTML")
        delete_user(callback.message.bot, callback.message.chat.id, result_msg.message_id, user_id=callback.from_user.id, chat_type=callback.message.chat.type)

@router.callback_query(F.data.startswith("vpn_") & ~F.data.startswith("vpn_req_") & ~F.data.in_({"vpn_all", "vpn_request_new"}))
async def process_vpn_single(callback: types.CallbackQuery):
    await callback.answer()
    username = callback.from_user.username
    configs = get_user_configs(username)
    try:
        index = int(callback.data.split("_")[-1])
        conf_name = configs[index]
    except (IndexError, ValueError):
        msg = await callback.message.answer("❌ Конфиг не найден.", parse_mode="HTML")
        delete_user(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=callback.from_user.id, chat_type=callback.message.chat.type)
        return

    user_dir = get_user_dir(username)
    file_path = os.path.join(user_dir, conf_name)
    if os.path.exists(file_path):
        msg = await callback.message.answer_document(FSInputFile(file_path, filename=conf_name), caption=f"🔐 <b>{conf_name.replace('.vpn', '')}</b>", parse_mode="HTML")
        delete_user(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=callback.from_user.id, chat_type=callback.message.chat.type)
        logger.info(f"📤 Отправлен конфиг {conf_name} для @{username}")
    else:
        msg = await callback.message.answer("❌ Файл не найден на диске.", parse_mode="HTML")
        delete_user(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=callback.from_user.id, chat_type=callback.message.chat.type)

@router.callback_query(F.data == "vpn_request_new")
async def process_vpn_request_new(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ConfigRequest.waiting_for_device)
    msg = await callback.message.answer("📱 <b>Для какого устройства нужен конфиг?</b>\n\nНапиши название (например: iPhone, MacBook)\nИли нажми /cancel для отмены", parse_mode="HTML")
    delete_user(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=callback.from_user.id, chat_type=callback.message.chat.type)

@router.message(ConfigRequest.waiting_for_device, F.text)
async def process_device_info(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        msg = await message.answer("❌ Запрос отменён.", parse_mode="HTML")
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    device = message.text.strip().replace('<', '&lt;').replace('>', '&gt;')
    user = message.from_user
    username = user.username or f"ID:{user.id}"
    pending_requests[user.id] = {"device": device}

    request_msg = f"🔔 <b>ЗАПРОС НОВОГО КОНФИГА</b>\n\n👤 @{username}\n📱 ID: {user.id}\n💬 Устройство: {device}\n\nЖдёт новый конфиг!"
    builder = get_vpn_request_keyboard(user.id)

    for admin_id in ADMIN_IDS:
        try:
            msg = await message.bot.send_message(admin_id, request_msg, reply_markup=builder.as_markup(), parse_mode="HTML")
            pending_requests[user.id]["admin_msg_id"] = msg.message_id
            pending_requests[user.id]["admin_id"] = admin_id
        except Exception as e:
            logger.error(f"❌ Ошибка отправки админу {admin_id}: {e}")

    msg = await message.answer("✅ Запрос отправлен админу!\nОжидай ответа...", parse_mode="HTML")
    delete_temp(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
    await state.clear()

@router.callback_query(F.data.startswith("vpn_req_upload_"))
async def vpn_req_upload(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Только админ", show_alert=True)
        return
    await callback.answer()
    target_id = int(callback.data.split("_")[-1])
    active_uploads[callback.from_user.id] = {"target_id": target_id, "msg_id": callback.message.message_id, "chat_id": callback.message.chat.id}
    device_info = pending_requests.get(target_id, {}).get("device", "не указано")

    msg = await callback.message.answer(f"📤 <b>Жду файл .vpn!</b>\n👤 Пользователь: ID {target_id}\n💬 Устройство: {device_info}\n\n📁 Отправь файл следующим сообщением", parse_mode="HTML")
    delete_admin(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=callback.from_user.id, chat_type=callback.message.chat.type)

@router.callback_query(F.data.startswith("vpn_req_reject_"))
async def vpn_req_reject_start(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Только админ", show_alert=True)
        return
    await callback.answer()
    user_id = int(callback.data.split("_")[-1])
    pending_requests[user_id]["reject_admin"] = callback.from_user.id
    await state.set_state(ConfigRequest.waiting_for_reject_reason)
    await callback.message.edit_text(f"📄 <b>Укажи причину отклонения:</b>\n\nНапиши текст (или /skip для отмены)", parse_mode="HTML")

@router.message(ConfigRequest.waiting_for_reject_reason, F.text)
async def process_reject_reason(message: types.Message, state: FSMContext):
    target_user_id = None
    for uid, data in pending_requests.items():
        if data.get("reject_admin") == message.from_user.id:
            target_user_id = uid
            break
    if not target_user_id:
        msg = await message.answer("❌ Активный запрос не найден", parse_mode="HTML")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        await state.clear()
        return

    reason = message.text.strip() if not message.text.startswith('/skip') else "Без указания причины"
    reason = reason.replace('<', '&lt;').replace('>', '&gt;')

    try:
        msg = await message.bot.send_message(target_user_id, f"📄 <b>Запрос отклонён</b>\n\n📝 Причина: {reason}", parse_mode="HTML")
        delete_user(message.bot, target_user_id, msg.message_id, user_id=target_user_id, chat_type="private")
    except Exception: pass

    msg = await message.answer("✅ Пользователь уведомлён.", parse_mode="HTML")
    delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
    if target_user_id in pending_requests: del pending_requests[target_user_id]
    await state.clear()

@router.message(F.document)
async def handle_vpn_upload(message: types.Message):
    admin_id = message.from_user.id
    if admin_id not in ADMIN_IDS or admin_id not in active_uploads: return
    if not message.document.file_name.endswith('.vpn'):
        msg = await message.answer("❌ Пожалуйста, загрузите файл с расширением .vpn", parse_mode="HTML")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return
    
    MAX_FILE_SIZE = 5 * 1024 * 1024
    if message.document.file_size > MAX_FILE_SIZE:
        size_mb = message.document.file_size / (1024 * 1024)
        log_suspicious_activity(admin_id, "LARGE_FILE_UPLOAD", f"Size: {size_mb:.2f} MB")
        msg = await message.answer(f"❌ Файл слишком большой! Максимум: 5 МБ\n📦 Ваш файл: {size_mb:.2f} МБ", parse_mode="HTML")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return
    
    upload_info = active_uploads[admin_id]
    target_id = upload_info["target_id"]

    try:
        user = await message.bot.get_chat(target_id)
        username = user.username or f"user{target_id}"
    except Exception: username = f"user{target_id}"

    user_dir = get_user_dir(username)
    device = pending_requests.get(target_id, {}).get("device", "")
    device_clean = re.sub(r'[^\w\s\-]', '', device).replace(' ', '_')[:30].strip('_') if device else datetime.datetime.now().strftime('%H%M')
    if not device_clean: device_clean = "config"

    date_str = datetime.datetime.now().strftime('%d.%m')
    filename = f"{device_clean}_{date_str}.vpn"
    save_path = os.path.join(user_dir, filename)

    if os.path.exists(save_path):
        idx = 1
        while os.path.exists(os.path.join(user_dir, f"{device_clean}_{date_str}_{idx}.vpn")): idx += 1
        filename = f"{device_clean}_{date_str}_{idx}.vpn"
        save_path = os.path.join(user_dir, filename)

    try:
        await message.bot.download(message.document, destination=save_path)
        try:
            target_user = await message.bot.get_chat(target_id)
            update_stats(target_user, "config_uploaded")
        except Exception: pass

        device_info = pending_requests.get(target_id, {}).get("device", "")
        device_text = f"\n📱 Устройство: {device_info}" if device_info else ""

        msg = await message.bot.send_document(target_id, document=FSInputFile(save_path, filename=filename), caption=f"🔐 Твой новый конфиг{device_text}\n📁 {filename}", parse_mode="HTML")
        delete_user(message.bot, target_id, msg.message_id, user_id=target_id, chat_type="private")

        msg = await message.answer(f"✅ Файл сохранён в папку <b>@{username}</b>!\n📁 {filename}", parse_mode="HTML")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)

        if "msg_id" in upload_info:
            try:
                await message.bot.edit_message_text(chat_id=upload_info["chat_id"], message_id=upload_info["msg_id"], text=f"✅ <b>Конфиг отправлен!</b>\n\n👤 Пользователь: ID {target_id}\n📁 Файл: {filename}\n📤 Отправлено: {datetime.datetime.now().strftime('%H:%M:%S')}", parse_mode="HTML")
            except Exception as e: logger.warning(f"Не удалось отредактировать сообщение: {e}")

        logger.info(f"📤 Конфиг отправлен: {filename} для @{username}")
    except Exception as e:
        msg = await message.answer(f"❌ Ошибка: {e}", parse_mode=None)
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        logger.error(f"Upload error: {e}")
    finally:
        if admin_id in active_uploads: del active_uploads[admin_id]
        if target_id in pending_requests: del pending_requests[target_id]
