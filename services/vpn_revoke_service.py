from datetime import datetime

from services.ssh_service import (
    get_ssh,
    exec_ssh,
)

from repositories.vpn_repository import (
    load_vpn_db,
    save_vpn_db,
)

from services.vpn_config import (
    DOCKER_CONTAINER,
    WG_INTERFACE,
)
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


