import json
import re

from services.vpn_config import DOCKER_CONTAINER, WG_INTERFACE
from utils.logger import standard_logger
from repositories.vpn_repository import load_vpn_db
from services.ssh_service import get_ssh, exec_ssh

logger = standard_logger


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
    Получает трафик пользователей из clientsTable.
    """
    ssh = None

    try:
        ssh = get_ssh()

        clients_json, _ = exec_ssh(
            ssh,
            f"docker exec {DOCKER_CONTAINER} cat /opt/amnezia/awg/clientsTable"
        )

        clients = json.loads(clients_json) if clients_json.strip() else []

        wg_out, _ = exec_ssh(
            ssh,
            f"docker exec {DOCKER_CONTAINER} wg show {WG_INTERFACE}"
        )

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

            received_str = user_data.get('dataReceived', '0 B')
            sent_str = user_data.get('dataSent', '0 B')

            received_bytes = parse_size_from_string(received_str)
            sent_bytes = parse_size_from_string(sent_str)
            total_bytes = received_bytes + sent_bytes

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
    Получить трафик пользователей с VPN-сервера.
    """
    ssh = None

    try:
        ssh = get_ssh()

        wg_out, _ = exec_ssh(
            ssh,
            f"docker exec {DOCKER_CONTAINER} wg show {WG_INTERFACE}"
        )

        peers = {}
        current_peer = None

        for line in wg_out.split('\n'):
            line = line.strip()

            if not line:
                continue

            peer_match = re.search(r'peer:\s*([A-Za-z0-9+/=]+)', line)

            if peer_match:
                current_peer = peer_match.group(1)
                peers[current_peer] = {
                    'received': 0,
                    'sent': 0,
                    'endpoint': None,
                    'ip': None
                }
                continue

            endpoint_match = re.search(r'endpoint:\s*([\d.:]+)', line)

            if endpoint_match and current_peer:
                peers[current_peer]['endpoint'] = endpoint_match.group(1)
                continue

            transfer_match = re.search(
                r'transfer:\s*([\d.]+)\s*([KMGT]?i?B)\s+received,\s+([\d.]+)\s*([KMGT]?i?B)\s+sent',
                line
            )

            if transfer_match and current_peer:
                received = parse_size(
                    transfer_match.group(1),
                    transfer_match.group(2)
                )

                sent = parse_size(
                    transfer_match.group(3),
                    transfer_match.group(4)
                )

                peers[current_peer]['received'] = received
                peers[current_peer]['sent'] = sent
                continue

            ips_match = re.search(r'allowed ips:\s*([\d.]+/\d+)', line)

            if ips_match and current_peer:
                peers[current_peer]['ip'] = ips_match.group(1)

        db = load_vpn_db()

        user_traffic = {}

        for public_key, peer_data in peers.items():

            if public_key not in db:
                continue

            user_data = db[public_key]

            username_db = user_data.get('username', 'unknown')
            user_id_db = user_data.get('user_id')

            if username and username_db != username:
                continue

            if user_id and user_id_db != user_id:
                continue

            total = (
                peer_data.get('received', 0)
                + peer_data.get('sent', 0)
            )

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
