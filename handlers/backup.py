from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import FSInputFile
from config import ADMIN_IDS, BACKUP_DIR, MAX_BACKUPS
from utils.auto_delete import schedule_delete, delete_temp, delete_user, delete_proxy_card, delete_admin
from utils.rate_limit import is_rate_limited
from utils.audit import log_admin_action
import os, tarfile, logging
from datetime import datetime

router = Router()
logger = logging.getLogger(__name__)

def get_backup_list():
    if not os.path.exists(BACKUP_DIR): return []
    backups = []
    for f in os.listdir(BACKUP_DIR):
        if f.startswith("durdom-backup-") and f.endswith(".tar.gz"):
            full_path = os.path.join(BACKUP_DIR, f)
            backups.append({"name": f, "path": full_path, "size": os.path.getsize(full_path), "created": datetime.fromtimestamp(os.path.getctime(full_path))})
    backups.sort(key=lambda x: x["created"], reverse=True)
    return backups

def cleanup_backups(keep_count: int):
    backups = get_backup_list()
    deleted = []
    if len(backups) > keep_count:
        for backup in backups[keep_count:]:
            try:
                os.remove(backup["path"])
                deleted.append(backup)
                logger.info(f"🗑 Удалён старый бэкап: {backup['name']}")
            except Exception as e: logger.error(f"❌ Ошибка удаления {backup['name']}: {e}")
    return deleted, backups[:keep_count]

@router.message(Command("backup"))
async def cmd_backup(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        msg = await message.answer("❌ Только админ", parse_mode="HTML")
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    is_limited, retry_after = is_rate_limited(message.from_user.id, "backup")
    if is_limited:
        msg = await message.answer(f"⏳ Слишком много запросов. Попробуйте через {retry_after} сек.", parse_mode="HTML")
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    log_admin_action(message.from_user.id, "CREATE_BACKUP", "Создание резервной копии")

    msg = await message.answer("📦 <b>Создаю резервную копию...</b>\n⏳ Подождите...", parse_mode="HTML")
    delete_temp(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)

    try:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        archive_name = f"durdom-backup-{timestamp}.tar.gz"
        archive_path = os.path.join(BACKUP_DIR, archive_name)
        project_root = os.path.dirname(os.path.dirname(__file__))

        items_to_backup = ["main.py", "config.py", "requirements.txt", ".env", ".gitignore", "handlers", "utils", "database", "states", "keyboards", "bot_data/stats.json", "bot_data/user_proxies.json", "bot_data/vpn_configs"]

        with tarfile.open(archive_path, "w:gz") as tar:
            for item in items_to_backup:
                full_path = os.path.join(project_root, item)
                if os.path.exists(full_path): tar.add(full_path, arcname=item)

        size_mb = os.path.getsize(archive_path) / (1024 * 1024)
        deleted_backups, remaining = cleanup_backups(MAX_BACKUPS)

        caption = f"✅ <b>Резервная копия создана!</b>\n\n📄 Файл: <code>{archive_name}</code>\n📦 Размер: <b>{size_mb:.2f} МБ</b>\n🕐 Время: {datetime.now().strftime('%H:%M:%S')}\n💾 Сохранено в: <code>bot_data/backups/</code>\n\n"
        if deleted_backups:
            caption += f"🗑 <b>Удалено старых бэкапов: {len(deleted_backups)}</b>\n"
            for b in deleted_backups[:3]: caption += f"  • {b['name']}\n"
            if len(deleted_backups) > 3: caption += f"  • ... и ещё {len(deleted_backups) - 3}\n"
        caption += f"\n📊 <b>Всего бэкапов: {len(remaining)}/{MAX_BACKUPS}</b>"

        # ✅ ФАЙЛ БЭКАПА НЕ УДАЛЯЕТСЯ НИКОГДА
        await message.answer_document(document=FSInputFile(archive_path, filename=archive_name), caption=caption, parse_mode="HTML")
        logger.info(f"📦 Создана резервная копия: {archive_name} ({size_mb:.2f} МБ)")

    except Exception as e:
        logger.error(f"Ошибка создания бэкапа: {e}", exc_info=True)
        msg = await message.answer(f"❌ <b>Ошибка при создании бэкапа:</b>\n<code>{e}</code>", parse_mode="HTML")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)

@router.message(Command("cleanup_backups"))
async def cmd_cleanup_backups(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        msg = await message.answer("❌ Только админ", parse_mode="HTML")
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    is_limited, retry_after = is_rate_limited(message.from_user.id, "cleanup_backups")
    if is_limited:
        msg = await message.answer(f"⏳ Слишком много запросов. Попробуйте через {retry_after} сек.", parse_mode="HTML")
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    parts = message.text.split()
    try:
        keep_count = int(parts[1]) if len(parts) > 1 else 3
        if keep_count < 1: keep_count = 1
    except (ValueError, IndexError): keep_count = 3
    
    log_admin_action(message.from_user.id, "CLEANUP_BACKUPS", f"Keep: {keep_count}")

    backups_before = get_backup_list()
    deleted_backups, remaining = cleanup_backups(keep_count)

    if deleted_backups:
        freed_mb = sum(b["size"] for b in deleted_backups) / (1024 * 1024)
        text = f"🧹 <b>Очистка завершена!</b>\n\n📊 Было бэкапов: <b>{len(backups_before)}</b>\n🗑 Удалено: <b>{len(deleted_backups)}</b>\n📦 Освобождено: <b>{freed_mb:.2f} МБ</b>\n✅ Осталось: <b>{len(remaining)}</b>\n\n<b>Удалённые файлы:</b>\n"
        for b in deleted_backups: text += f"  • {b['name']} ({b['size'] / (1024 * 1024):.2f} МБ)\n"
    else:
        text = f"✅ <b>Очистка не требуется!</b>\n\n📊 Текущее количество бэкапов: <b>{len(backups_before)}</b>\n📦 Оставляю последние: <b>{keep_count}</b>\n💡 Чтобы удалить больше, укажите меньшее число:\n   <code>/cleanup_backups 2</code>"

    msg = await message.answer(text, parse_mode="HTML")
    delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)

@router.message(Command("list_backups"))
async def cmd_list_backups(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        msg = await message.answer("❌ Только админ", parse_mode="HTML")
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    is_limited, retry_after = is_rate_limited(message.from_user.id, "list_backups")
    if is_limited:
        msg = await message.answer(f"⏳ Слишком много запросов. Попробуйте через {retry_after} сек.", parse_mode="HTML")
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    backups = get_backup_list()
    if not backups:
        text = "📂 <b>Бэкапы не найдены</b>\n\nИспользуйте /backup для создания первого бэкапа"
    else:
        total_size = sum(b["size"] for b in backups) / (1024 * 1024)
        text = f"📂 <b>Список бэкапов ({len(backups)} шт., {total_size:.2f} МБ):</b>\n\n"
        for i, backup in enumerate(backups, 1):
            size_mb = backup["size"] / (1024 * 1024)
            created = backup["created"].strftime("%d.%m.%Y %H:%M")
            marker = "⭐" if i <= MAX_BACKUPS else ""
            text += f"{marker} <b>{i}. {backup['name']}</b>\n   📦 Размер: {size_mb:.2f} МБ\n   🕐 Создан: {created}\n\n"
        text += f"━━━━━━━━━━━━━━━━━━━━\n\n💡 <b>Управление:</b>\n• <code>/cleanup_backups 3</code> — оставить 3 последних\n• <code>/delete_backup имя_файла.tar.gz</code> — удалить конкретный"

    msg = await message.answer(text, parse_mode="HTML")
    delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)

@router.message(Command("delete_backup"))
async def cmd_delete_backup(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        msg = await message.answer("❌ Только админ", parse_mode="HTML")
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    is_limited, retry_after = is_rate_limited(message.from_user.id, "delete_backup")
    if is_limited:
        msg = await message.answer(f"⏳ Слишком много запросов. Попробуйте через {retry_after} сек.", parse_mode="HTML")
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        text = "🗑 <b>Удаление конкретного бэкапа:</b>\n\nФормат: <code>/delete_backup имя_файла.tar.gz</code>\n\nПример: <code>/delete_backup durdom-backup-2026-06-13_14-21.tar.gz</code>\n\n📋 Используйте /list_backups чтобы увидеть список файлов"
        msg = await message.answer(text, parse_mode="HTML")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    filename = parts[1].strip()
    file_path = os.path.join(BACKUP_DIR, filename)

    if not os.path.abspath(file_path).startswith(os.path.abspath(BACKUP_DIR)):
        msg = await message.answer("❌ Недопустимое имя файла", parse_mode="HTML")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    if not os.path.exists(file_path):
        msg = await message.answer(f"❌ Файл <code>{filename}</code> не найден", parse_mode="HTML")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    try:
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        os.remove(file_path)
        log_admin_action(message.from_user.id, "DELETE_BACKUP", f"File: {filename}, Size: {size_mb:.2f} MB")
        msg = await message.answer(f"✅ Бэкап <b>{filename}</b> удалён!\n📦 Освобождено: <b>{size_mb:.2f} МБ</b>", parse_mode="HTML")
        logger.info(f"🗑 Удалён бэкап: {filename}")
    except Exception as e:
        msg = await message.answer(f"❌ Ошибка удаления: {e}", parse_mode="HTML")
        logger.error(f"Ошибка удаления бэкапа {filename}: {e}")
    
    delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)