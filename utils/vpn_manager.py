#!/usr/bin/env python3
"""Менеджер VPN пользователей - работа с сервером Amnezia"""

import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

import paramiko

# Загружаем настройки из .env
def load_env():
    env_path = '/opt/durdom-bot/.env'
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars

ENV = load_env()

# Настройки
SSH_HOST = ENV.get('VPN_SSH_HOST', '')
SSH_PORT = int(ENV.get('VPN_SSH_PORT', 22))
SSH_USER = ENV.get('VPN_SSH_USER', 'root')
SSH_KEY_PATH = ENV.get('VPN_SSH_KEY_PATH', '/opt/durdom-bot/ssh_keys/durdom_vpn_key')
DOCKER_CONTAINER = ENV.get('DOCKER_CONTAINER', 'amnezia-awg2')
WG_INTERFACE = ENV.get('WG_INTERFACE', 'awg0')
WG_SERVER_PORT = int(ENV.get('WG_SERVER_PORT', 45135))
WG_SERVER_PUBLIC_KEY = ENV.get('WG_SERVER_PUBLIC_KEY', '')
WG_PRESHARED_KEY = ENV.get('WG_PRESHARED_KEY', '')
WG_SUBNET = '10.8.1.0/24'
WG_CONFIG_EXPIRY_DAYS = 30

# Путь к локальной БД пользователей
VPN_DB_PATH = Path('/opt/durdom-bot/bot_data/vpn_users.json')
VPN_DB_PATH.parent.mkdir(exist_ok=True)
# Для совместимости с другими модулями
VPN_CONFIGS_DIR = Path('/opt/durdom-bot/bot_data/vpn_configs')
BACKUP_DIR = Path('/opt/durdom-bot/bot_data/backups')


def get_ssh():
    """Создаёт SSH подключение"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        hostname=SSH_HOST, port=SSH_PORT,
        username=SSH_USER, key_filename=SSH_KEY_PATH, timeout=10
    )
    return ssh


def exec_ssh(ssh, command):
    """Выполняет команду по SSH"""
    stdin, stdout, stderr = ssh.exec_command(command)
    return stdout.read().decode(), stderr.read().decode()


def load_vpn_db():
    """Загружает локальную БД VPN пользователей"""
    if VPN_DB_PATH.exists():
        with open(VPN_DB_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_vpn_db(db):
    """Сохраняет локальную БД"""
    with open(VPN_DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def get_next_free_ip(ssh):
    """Находит следующий свободный IP в подсети 10.8.1.X"""
    clients_json, _ = exec_ssh(ssh, f"docker exec {DOCKER_CONTAINER} cat /opt/amnezia/awg/clientsTable")
    clients = json.loads(clients_json) if clients_json.strip() else []
    
    used_ips = set()
    for client in clients:
        allowed_ips = client.get('userData', {}).get('allowedIps', '')
        if allowed_ips:
            ip_match = re.search(r'10\.8\.1\.(\d+)', allowed_ips)
            if ip_match:
                used_ips.add(int(ip_match.group(1)))
    
    next_ip = 3
    while next_ip in used_ips and next_ip < 254:
        next_ip += 1
    
    return f"10.8.1.{next_ip}"


def issue_vpn_config(username: str, user_id: int = None):
    """
    Выдаёт VPN конфиг пользователю.
    Возвращает dict с информацией или None при ошибке.
    """
    ssh = None
    try:
        ssh = get_ssh()
        
        # Генерация ключей клиента
        client_private_key, _ = exec_ssh(ssh, f"docker exec {DOCKER_CONTAINER} wg genkey")
        client_private_key = client_private_key.strip()
        
        client_public_key, _ = exec_ssh(
            ssh,
            f"docker exec {DOCKER_CONTAINER} sh -c 'echo \"{client_private_key}\" | wg pubkey'"
        )
        client_public_key = client_public_key.strip()
        
        if not client_private_key or not client_public_key:
            return {'error': 'Не удалось сгенерировать ключи'}
        
        # Определяем следующий свободный IP
        client_ip = get_next_free_ip(ssh)
        
        # Добавляем пир в awg0.conf
        new_peer = f"""
[Peer]
PublicKey = {client_public_key}
PresharedKey = {WG_PRESHARED_KEY}
AllowedIPs = {client_ip}/32
"""
        exec_ssh(ssh, f"docker exec {DOCKER_CONTAINER} sh -c 'echo \"{new_peer}\" >> /opt/amnezia/awg/awg0.conf'")
        
        # Добавляем в clientsTable
        creation_date = datetime.now().strftime('%a %b %d %H:%M:%S %Y')
        
        clients_json, _ = exec_ssh(ssh, f"docker exec {DOCKER_CONTAINER} cat /opt/amnezia/awg/clientsTable")
        clients = json.loads(clients_json) if clients_json.strip() else []
        
        new_client = {
            "clientId": client_public_key,
            "userData": {
                "allowedIps": f"{client_ip}/32",
                "clientName": username,
                "creationDate": creation_date
            }
        }
        clients.append(new_client)
        
        clients_json_new = json.dumps(clients, indent=4)
        clients_escaped = clients_json_new.replace("'", "'\\''")
        exec_ssh(ssh, f"docker exec {DOCKER_CONTAINER} sh -c 'cat > /opt/amnezia/awg/clientsTable << EOF\n{clients_escaped}\nEOF'")
        
        # Добавляем пир в WireGuard
        exec_ssh(ssh, f"docker exec {DOCKER_CONTAINER} sh -c 'echo \"{WG_PRESHARED_KEY}\" > /tmp/psk && wg set {WG_INTERFACE} peer {client_public_key} preshared-key /tmp/psk allowed-ips {client_ip}/32 && rm /tmp/psk'")
        
        # Генерируем конфиг через внешний скрипт
        import sys
        result = subprocess.run(
            [
                sys.executable, '/opt/durdom-bot/utils/vpn_generator.py',
                client_private_key,
                client_public_key,
                client_ip,
                SSH_HOST,
                str(WG_SERVER_PORT),
                WG_SERVER_PUBLIC_KEY,
                WG_PRESHARED_KEY
            ],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return {'error': f'Ошибка генерации конфига: {result.stderr}'}
        
        amnezia_string = result.stdout.strip()
        
        # Сохраняем в локальную БД
        db = load_vpn_db()
        from datetime import timedelta
        expiry_date = datetime.now() + timedelta(days=WG_CONFIG_EXPIRY_DAYS)
        
        db[client_public_key] = {
            'username': username,
            'user_id': user_id,
            'ip': client_ip,
            'issued_at': datetime.now().isoformat(),
            'expires_at': expiry_date.isoformat(),
            'active': True
        }
        save_vpn_db(db)
        
        return {
            'success': True,
            'username': username,
            'user_id': user_id,
            'ip': client_ip,
            'public_key': client_public_key,
            'private_key': client_private_key,
            'config_string': amnezia_string,
            'expires_at': expiry_date.strftime('%d.%m.%Y')
        }
        
    except Exception as e:
        return {'error': str(e)}
    finally:
        if ssh:
            ssh.close()


def revoke_vpn_config(public_key: str):
    """
    Отозвать VPN конфиг по public key.
    Возвращает dict с информацией или None при ошибке.
    """
    ssh = None
    try:
        ssh = get_ssh()
        
        # Проверяем что ключ существует
        peers, _ = exec_ssh(ssh, f"docker exec {DOCKER_CONTAINER} wg show {WG_INTERFACE} peers")
        
        if public_key not in peers:
            return {'error': 'Ключ не найден на сервере'}
        
        # Удаляем пир
        _, stderr = exec_ssh(ssh, f"docker exec {DOCKER_CONTAINER} wg set {WG_INTERFACE} peer {public_key} remove")
        
        # Удаляем из clientsTable
        clients_json, _ = exec_ssh(ssh, f"docker exec {DOCKER_CONTAINER} cat /opt/amnezia/awg/clientsTable")
        clients = json.loads(clients_json) if clients_json.strip() else []
        clients = [c for c in clients if c.get('clientId') != public_key]
        
        clients_json_new = json.dumps(clients, indent=4)
        clients_escaped = clients_json_new.replace("'", "'\\''")
        exec_ssh(ssh, f"docker exec {DOCKER_CONTAINER} sh -c 'cat > /opt/amnezia/awg/clientsTable << EOF\n{clients_escaped}\nEOF'")
        
        # Удаляем из awg0.conf
        exec_ssh(ssh, f"docker exec {DOCKER_CONTAINER} sh -c \"sed -i '/{public_key}/,/AllowedIPs/d' /opt/amnezia/awg/awg0.conf\"")
        
        # Помечаем как неактивный в локальной БД
        db = load_vpn_db()
        if public_key in db:
            db[public_key]['active'] = False
            db[public_key]['revoked_at'] = datetime.now().isoformat()
            save_vpn_db(db)
        
        return {'success': True, 'public_key': public_key}
        
    except Exception as e:
        return {'error': str(e)}
    finally:
        if ssh:
            ssh.close()


def list_vpn_users():
    """Получить список активных VPN пользователей с сервера"""
    ssh = None
    try:
        ssh = get_ssh()
        
        clients_json, _ = exec_ssh(ssh, f"docker exec {DOCKER_CONTAINER} cat /opt/amnezia/awg/clientsTable")
        clients = json.loads(clients_json) if clients_json.strip() else []
        
        return {'success': True, 'users': clients}
        
    except Exception as e:
        return {'error': str(e)}
    finally:
        if ssh:
            ssh.close()


def test_ssh_connection():
    """Проверить SSH подключение к VPN серверу"""
    try:
        ssh = get_ssh()
        docker_out, _ = exec_ssh(ssh, f"docker ps --filter name={DOCKER_CONTAINER}")
        wg_out, _ = exec_ssh(ssh, f"docker exec {DOCKER_CONTAINER} wg show {WG_INTERFACE}")
        ssh.close()
        
        return {
            'success': True,
            'docker': docker_out,
            'wireguard': wg_out
        }
    except Exception as e:
        return {'error': str(e)}


# ============================================
# ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ПРОДЛЕНИЯ И АВТОУДАЛЕНИЯ
# ============================================

import shutil
from datetime import timedelta
from pathlib import Path
from config import BACKUP_DIR, VPN_DIR
from utils.logger import standard_logger, audit_logger

logger = standard_logger

# Алиас для совместимости с handlers/extend.py
VPN_USERS_FILE = VPN_DB_PATH

def extend_vpn_config(user_id: int, config_hash: str, days: int = 30):
    """
    Продлевает VPN-конфиг на N дней БЕЗ пересоздания.
    
    Args:
        user_id: Telegram ID пользователя
        config_hash: Хеш (public_key) конфига
        days: На сколько дней продлить (по умолчанию 30)
    
    Returns:
        (success: bool, result: str или datetime)
    """
    db = load_vpn_db()
    
    if config_hash not in db:
        return False, "Конфиг не найден"
    
    config_data = db[config_hash]
    
    # Проверяем, принадлежит ли конфиг этому пользователю
    if config_data.get('user_id') != user_id:
        return False, "Это не ваш конфиг"
    
    # Проверяем, активен ли конфиг
    if not config_data.get('active', True):
        return False, "Конфиг неактивен (был отозван)"
    
    # ✅ Если бессрочный — не продлеваем
    if config_data.get('permanent', False):
        return False, "Бессрочный конфиг не требует продления"
    
    expires_at_str = config_data.get('expires_at')
    if not expires_at_str:
        return False, "Дата истечения не найдена"
    
    try:
        current_expires = datetime.fromisoformat(expires_at_str)
    except ValueError:
        return False, "Некорректный формат даты"
    
    # Если конфиг уже истёк — продлеваем с сегодняшнего дня
    if current_expires < datetime.now():
        new_expires = datetime.now() + timedelta(days=days)
    else:
        new_expires = current_expires + timedelta(days=days)
    
    # Обновляем дату
    db[config_hash]['expires_at'] = new_expires.isoformat()
    save_vpn_db(db)
    
    logger.info(f"🔄 Продлен конфиг {config_hash[:20]}... для пользователя {user_id} до {new_expires.isoformat()}")
    audit_logger.info(
        f"ACTION:EXTEND_VPN | USER:{user_id} | "
        f"CONFIG:{config_hash[:20]}... | OLD:{expires_at_str} | NEW:{new_expires.isoformat()}"
    )
    
    return True, new_expires


def delete_expired_vpn():
    """
    Помечает истекшие VPN-конфиги как неактивные и перемещает их папки в backups.
    ✅ Пропускает бессрочные конфиги.
    
    Returns:
        int: Количество удалённых конфигов
    """
    db = load_vpn_db()
    now = datetime.now()
    deleted_count = 0
    updated = False
    
    for config_hash, config_data in list(db.items()):
        # Пропускаем уже неактивные
        if not config_data.get('active', True):
            continue
        
        # ✅ ПРОПУСКАЕМ БЕССРОЧНЫЕ
        if config_data.get('permanent', False):
            continue
        
        expires_at_str = config_data.get('expires_at')
        if not expires_at_str:
            continue
        
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if expires_at < now:
                # Помечаем как неактивный
                db[config_hash]['active'] = False
                db[config_hash]['expired_at'] = now.isoformat()
                updated = True
                deleted_count += 1
                
                username = config_data.get('username')
                if username:
                    user_dir = Path(VPN_DIR) / username
                    if user_dir.exists():
                        backup_name = f"expired_{username}_{now.strftime('%Y%m%d_%H%M%S')}"
                        backup_path = Path(BACKUP_DIR) / backup_name
                        shutil.move(str(user_dir), str(backup_path))
                        logger.info(f"🗑️ Конфиг {username} перемещен в backups/{backup_name}")
                
                audit_logger.info(
                    f"ACTION:DELETE_EXPIRED_VPN | USER:{config_data.get('user_id')} | "
                    f"CONFIG:{config_hash[:20]}... | EXPIRED_AT:{expires_at_str}"
                )
                
        except ValueError:
            continue
    
    if updated:
        save_vpn_db(db)
        logger.info(f"🗑️ Всего удалено {deleted_count} истекших VPN-конфигов")
    
    return deleted_count


def get_user_vpn_configs(user_id: int) -> list:
    """
    Возвращает список активных конфигов пользователя.
    
    Returns:
        list: Список словарей с полями: hash, username, expires_at, days_left, permanent
    """
    db = load_vpn_db()
    now = datetime.now()
    result = []
    
    for config_hash, config_data in db.items():
        if config_data.get('user_id') == user_id and config_data.get('active', True):
            expires_at_str = config_data.get('expires_at')
            days_left = None
            is_permanent = config_data.get('permanent', False)
            if expires_at_str and not is_permanent:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    days_left = (expires_at - now).days
                except ValueError:
                    pass
            
            result.append({
                'hash': config_hash,
                'username': config_data.get('username', 'unknown'),
                'expires_at': expires_at_str,
                'days_left': days_left,
                'ip': config_data.get('ip'),
                'issued_at': config_data.get('issued_at'),
                'permanent': is_permanent
            })
    
    return result


def get_expired_vpn_list() -> list:
    """
    Возвращает список истекших конфигов (без бессрочных).
    
    Returns:
        list: Список словарей с полями: hash, username, user_id, expires_at
    """
    db = load_vpn_db()
    now = datetime.now()
    result = []
    
    for config_hash, config_data in db.items():
        if not config_data.get('active', True):
            continue
        
        # ✅ ПРОПУСКАЕМ БЕССРОЧНЫЕ
        if config_data.get('permanent', False):
            continue
        
        expires_at_str = config_data.get('expires_at')
        if not expires_at_str:
            continue
        
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if expires_at < now:
                result.append({
                    'hash': config_hash,
                    'username': config_data.get('username'),
                    'user_id': config_data.get('user_id'),
                    'expires_at': expires_at_str
                })
        except ValueError:
            continue
    
    return result

# ============================================
# ПОЛУЧЕНИЕ ТРАФИКА С СЕРВЕРА
# ============================================

def parse_size(value: str, unit: str) -> int:
    """Переводит размер в байты"""
    multipliers = {
        'B': 1,
        'KiB': 1024,
        'MiB': 1024**2,
        'GiB': 1024**3,
        'TiB': 1024**4,
        'KB': 1000,
        'MB': 1000**2,
        'GB': 1000**3,
    }
    value = float(value)
    multiplier = multipliers.get(unit, 1)
    return int(value * multiplier)


def format_size(bytes_value: int) -> str:
    """Форматирует байты в читаемый вид"""
    if bytes_value < 1024:
        return f"{bytes_value} B"
    elif bytes_value < 1024**2:
        return f"{bytes_value/1024:.2f} KB"
    elif bytes_value < 1024**3:
        return f"{bytes_value/1024**2:.2f} MB"
    else:
        return f"{bytes_value/1024**3:.2f} GB"


def parse_size_from_string(size_str: str) -> int:
    """Парсит строку размера типа '712.76 MiB' в байты"""
    import re
    if not size_str:
        return 0
    match = re.match(r'([\d.]+)\s*([KMGT]?i?B)', size_str.strip())
    if not match:
        return 0
    value = float(match.group(1))
    unit = match.group(2)
    return parse_size(value, unit)


def get_user_traffic_from_clients_table() -> dict:
    """
    Получает трафик пользователей из clientsTable на сервере.
    Возвращает словарь {username: {received, sent, total, total_bytes, last_handshake, ip}}
    """
    ssh = None
    try:
        ssh = get_ssh()
        
        # Читаем clientsTable
        clients_json, _ = exec_ssh(ssh, f"docker exec {DOCKER_CONTAINER} cat /opt/amnezia/awg/clientsTable")
        clients = json.loads(clients_json) if clients_json.strip() else []
        
        # Получаем данные WireGuard для handshake
        wg_out, _ = exec_ssh(ssh, f"docker exec {DOCKER_CONTAINER} wg show {WG_INTERFACE}")
        
        # Парсим handshake из WireGuard
        import re
        handshakes = {}
        current_peer = None
        for line in wg_out.split('\n'):
            line = line.strip()
            if not line:
                continue
            peer_match = re.search(r'peer:\s*([A-Za-z0-9+/=]+)', line)
            if peer_match:
                current_peer = peer_match.group(1)
                handshakes[current_peer] = None
                continue
            handshake_match = re.search(r'latest handshake:\s*(.+?)(?:\n|$)', line)
            if handshake_match and current_peer:
                handshakes[current_peer] = handshake_match.group(1).strip()
        
        user_traffic = {}
        
        for client in clients:
            client_id = client.get('clientId', '')
            user_data = client.get('userData', {})
            username = user_data.get('clientName', 'unknown')
            
            # Парсим трафик
            received_str = user_data.get('dataReceived', '0 B')
            sent_str = user_data.get('dataSent', '0 B')
            
            # Преобразуем в байты
            received_bytes = parse_size_from_string(received_str)
            sent_bytes = parse_size_from_string(sent_str)
            total_bytes = received_bytes + sent_bytes
            
            # Получаем handshake
            handshake = handshakes.get(client_id, 'никогда')
            
            user_traffic[username] = {
                'client_id': client_id,
                'received': received_str,
                'sent': sent_str,
                'total': format_size(total_bytes),
                'total_bytes': total_bytes,
                'ip': user_data.get('allowedIps', ''),
                'last_handshake': handshake,
                'creation_date': user_data.get('creationDate', '')
            }
        
        return user_traffic
        
    except Exception as e:
        logger.error(f"Ошибка получения трафика из clientsTable: {e}")
        return {}
    finally:
        if ssh:
            ssh.close()


def get_user_traffic(username: str = None, user_id: int = None) -> dict:
    """
    Получить трафик пользователей с VPN-сервера (из WireGuard).
    Если username не указан — возвращает трафик всех пользователей.
    """
    ssh = None
    try:
        ssh = get_ssh()
        
        # Получаем данные WireGuard
        wg_out, _ = exec_ssh(ssh, f"docker exec {DOCKER_CONTAINER} wg show {WG_INTERFACE}")
        
        # Парсим вывод
        import re
        peers = {}
        current_peer = None
        
        for line in wg_out.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Ищем peer
            peer_match = re.search(r'peer:\s*([A-Za-z0-9+/=]+)', line)
            if peer_match:
                current_peer = peer_match.group(1)
                peers[current_peer] = {'received': 0, 'sent': 0, 'endpoint': None, 'ip': None}
                continue
            
            # Ищем endpoint
            endpoint_match = re.search(r'endpoint:\s*([\d.:]+)', line)
            if endpoint_match and current_peer:
                peers[current_peer]['endpoint'] = endpoint_match.group(1)
                continue
            
            # Ищем transfer
            transfer_match = re.search(r'transfer:\s*([\d.]+)\s*([KMGT]?i?B)\s+received,\s+([\d.]+)\s*([KMGT]?i?B)\s+sent', line)
            if transfer_match and current_peer:
                received = parse_size(transfer_match.group(1), transfer_match.group(2))
                sent = parse_size(transfer_match.group(3), transfer_match.group(4))
                peers[current_peer]['received'] = received
                peers[current_peer]['sent'] = sent
                continue
            
            # Ищем allowed ips
            ips_match = re.search(r'allowed ips:\s*([\d.]+/\d+)', line)
            if ips_match and current_peer:
                peers[current_peer]['ip'] = ips_match.group(1)
        
        # Сопоставляем с пользователями из vpn_users.json
        db = load_vpn_db()
        user_traffic = {}
        
        for public_key, peer_data in peers.items():
            if public_key in db:
                user_data = db[public_key]
                username_db = user_data.get('username', 'unknown')
                user_id_db = user_data.get('user_id')
                
                if username and username_db != username:
                    continue
                if user_id and user_id_db != user_id:
                    continue
                
                total = peer_data.get('received', 0) + peer_data.get('sent', 0)
                user_traffic[username_db] = {
                    'user_id': user_id_db,
                    'ip': peer_data.get('ip'),
                    'received': format_size(peer_data.get('received', 0)),
                    'sent': format_size(peer_data.get('sent', 0)),
                    'total': format_size(total),
                    'total_bytes': total
                }
        
        return user_traffic
        
    except Exception as e:
        logger.error(f"Ошибка получения трафика: {e}")
        return {}
    finally:
        if ssh:
            ssh.close()