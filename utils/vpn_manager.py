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
        expiry_date = datetime.now()
        from datetime import timedelta
        expiry_date = expiry_date + timedelta(days=WG_CONFIG_EXPIRY_DAYS)
        
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
