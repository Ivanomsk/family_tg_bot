import json
import subprocess
import sys
from datetime import datetime, timedelta

from services.ssh_service import (
    get_ssh,
    exec_ssh,
    SSH_HOST,
)

from repositories.vpn_repository import (
    load_vpn_db,
    save_vpn_db,
)

from services.vpn_config import (
    DOCKER_CONTAINER,
    WG_INTERFACE,
    WG_SERVER_PORT,
    WG_SERVER_PUBLIC_KEY,
    WG_PRESHARED_KEY,
    WG_CONFIG_EXPIRY_DAYS,
)
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


