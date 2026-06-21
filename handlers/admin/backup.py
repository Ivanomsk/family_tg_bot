from aiogram import Router, types, F
from aiogram.filters import Command

from config import BACKUP_DIR
from handlers.main_menu import admin_private_only
from utils.logger import standard_logger, audit_logger

import os
import tarfile
from datetime import datetime

router = Router()
logger = standard_logger

@router.callback_query(F.data == "menu_backup")
async def menu_backup(callback: types.CallbackQuery):
    """Меню бэкапов"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()

    text = (
        "📦 <b>УПРАВЛЕНИЕ БЭКАПАМИ</b>\n\n"
        "💡 <b>Используйте команды:</b>\n\n"
        "<code>/backup</code> — создать резервную копию\n"
        "<code>/list_backups</code> — показать все бэкапы\n"
        "<code>/cleanup_backups N</code> — оставить N последних бэкапов\n\n"
        "📝 <b>Примеры:</b>\n"
        "<code>/backup</code>\n"
        "<code>/list_backups</code>\n"
        "<code>/cleanup_backups 5</code>\n\n"
        "🤖 <b>Автобэкап:</b>\n"
        "• Каждый день в 03:00\n"
        "• Хранится 7 последних\n"
        "• Уведомление приходит в ЛС"
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("menu_admin_main").as_markup()
    )

@router.message(Command("backup"))
async def cmd_backup(message: types.Message):
    if not await admin_private_only(message):
        return
    
    await message.answer("⏳ Создаю бэкап...")
    
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"backup_{timestamp}.tar.gz"
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        
        with tarfile.open(backup_path, "w:gz") as tar:
            data_dirs = ['bot_data']
            for dir_name in data_dirs:
                dir_path = os.path.join('/opt/durdom-bot', dir_name)
                if os.path.exists(dir_path):
                    tar.add(dir_path, arcname=dir_name)
        
        size = os.path.getsize(backup_path)
        size_str = f"{size/1024:.2f} KB" if size < 1024*1024 else f"{size/1024/1024:.2f} MB"
        
        await message.answer(
            f"✅ <b>Бэкап создан!</b>\n\n"
            f"📁 Имя: {backup_name}\n"
            f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
            f"📦 Размер: {size_str}\n"
            f"📂 Путь: {backup_path}",
            parse_mode="HTML"
        )
        
        audit_logger.info(f"ACTION:BACKUP_CREATE | ADMIN:{message.from_user.id} | FILE:{backup_name}")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка создания бэкапа: {e}")
        logger.error(f"Ошибка создания бэкапа: {e}")


@router.message(Command("list_backups"))
async def cmd_list_backups(message: types.Message):
    if not await admin_private_only(message):
        return
    
    if not os.path.exists(BACKUP_DIR):
        await message.answer("📭 Папка с бэкапами пуста.")
        return
    
    backups = []
    for f in os.listdir(BACKUP_DIR):
        if f.endswith('.tar.gz'):
            file_path = os.path.join(BACKUP_DIR, f)
            mtime = os.path.getmtime(file_path)
            size = os.path.getsize(file_path)
            backups.append({
                'name': f,
                'date': datetime.fromtimestamp(mtime).strftime('%d.%m.%Y %H:%M:%S'),
                'size': f"{size/1024:.2f} KB" if size < 1024*1024 else f"{size/1024/1024:.2f} MB"
            })
    
    if not backups:
        await message.answer("📭 Нет бэкапов.")
        return
    
    backups.sort(key=lambda x: x['date'], reverse=True)
    
    text = "📋 <b>СПИСОК БЭКАПОВ</b>\n\n"
    for b in backups[:10]:
        text += f"📁 {b['name']}\n"
        text += f"   📅 {b['date']} | 📦 {b['size']}\n\n"
    
    if len(backups) > 10:
        text += f"💡 ... и ещё {len(backups) - 10} бэкапов\n\n"
    
    text += "💡 <b>Команда для очистки:</b>\n"
    text += "<code>/cleanup_backups 5</code> — оставить 5 последних"
    
    await message.answer(text, parse_mode="HTML")


@router.message(Command("cleanup_backups"))
async def cmd_cleanup_backups(message: types.Message):
    if not await admin_private_only(message):
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "Используйте: <code>/cleanup_backups N</code>\n"
            "Пример: <code>/cleanup_backups 5</code> — оставить 5 последних",
            parse_mode="HTML"
        )
        return
    
    try:
        keep_count = int(parts[1])
    except ValueError:
        await message.answer("❌ N должно быть числом.")
        return
    
    if not os.path.exists(BACKUP_DIR):
        await message.answer("📭 Папка с бэкапами пуста.")
        return
    
    backups = []
    for f in os.listdir(BACKUP_DIR):
        if f.endswith('.tar.gz'):
            file_path = os.path.join(BACKUP_DIR, f)
            mtime = os.path.getmtime(file_path)
            backups.append({'name': f, 'path': file_path, 'mtime': mtime})
    
    if not backups:
        await message.answer("📭 Нет бэкапов.")
        return
    
    backups.sort(key=lambda x: x['mtime'], reverse=True)
    
    deleted = 0
    for b in backups[keep_count:]:
        os.remove(b['path'])
        deleted += 1
    
    await message.answer(
        f"✅ <b>Очистка завершена!</b>\n\n"
        f"🗑️ Удалено старых бэкапов: {deleted}\n"
        f"📁 Оставлено последних: {keep_count}",
        parse_mode="HTML"
    )
    
    audit_logger.info(f"ACTION:CLEANUP_BACKUPS | ADMIN:{message.from_user.id} | KEPT:{keep_count} | DELETED:{deleted}")
