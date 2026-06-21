from services.ssh_service import (
    get_ssh,
    exec_ssh,
)

from services.vpn_config import (
    DOCKER_CONTAINER,
    WG_INTERFACE,
)
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

