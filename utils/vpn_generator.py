#!/usr/bin/env python3
"""Генератор конфига Amnezia VPN — ТОЧНАЯ копия оригинала"""

import json
import base64
import zlib
import sys

def generate_config(client_private_key, client_public_key, client_ip, server_host, server_port, server_public_key, preshared_key):
    """Генерирует конфиг в формате Amnezia"""
    
    # Создаём last_config как DICT
    last_config_dict = {
        "H1": "498113969-1484828766",
        "H2": "1811320663-2041913587",
        "H3": "2059977901-2085902908",
        "H4": "2100538693-2113803005",
        "I1": "<r 2><b 0x858000010001000000000669636c6f756403636f6d0000010001c00c000100010000105a00044d583737>",
        "I2": "",
        "I3": "",
        "I4": "",
        "I5": "",
        "Jc": "5",
        "Jmax": "50",
        "Jmin": "10",
        "S1": "55",
        "S2": "50",
        "S3": "33",
        "S4": "3",
        "allowed_ips": ["0.0.0.0/0", "::/0"],
        "clientId": client_public_key,
        "client_ip": client_ip,
        "client_priv_key": client_private_key,
        "client_pub_key": client_public_key,
        "config": (
            f"[Interface]\n"
            f"Address = {client_ip}/32\n"
            f"DNS = $PRIMARY_DNS, $SECONDARY_DNS\n"
            f"PrivateKey = {client_private_key}\n"
            f"Jc = 5\n"
            f"Jmin = 10\n"
            f"Jmax = 50\n"
            f"S1 = 55\n"
            f"S2 = 50\n"
            f"S3 = 33\n"
            f"S4 = 3\n"
            f"H1 = 498113969-1484828766\n"
            f"H2 = 1811320663-2041913587\n"
            f"H3 = 2059977901-2085902908\n"
            f"H4 = 2100538693-2113803005\n"
            f"I1 = <r 2><b 0x858000010001000000000669636c6f756403636f6d0000010001c00c000100010000105a00044d583737>\n"
            f"I2 = \n"
            f"I3 = \n"
            f"I4 = \n"
            f"I5 = \n"
            f"\n"
            f"[Peer]\n"
            f"PublicKey = {server_public_key}\n"
            f"PresharedKey = {preshared_key}\n"
            f"AllowedIPs = 0.0.0.0/0, ::/0\n"
            f"Endpoint = {server_host}:{server_port}\n"
            f"PersistentKeepalive = 25\n"
        ),
        "hostName": server_host,
        "mtu": "1376",
        "persistent_keep_alive": "25",
        "port": int(server_port),
        "psk_key": preshared_key,
        "server_pub_key": server_public_key
    }
    
    # Сериализуем last_config как СТРОКУ с indent=4 + \n в конце
    last_config_json = json.dumps(last_config_dict, indent=4, ensure_ascii=False) + "\n"
    
    # Основной шаблон
    config_template = {
        "containers": [
            {
                "awg": {
                    "H1": "498113969-1484828766",
                    "H2": "1811320663-2041913587",
                    "H3": "2059977901-2085902908",
                    "H4": "2100538693-2113803005",
                    "I1": "<r 2><b 0x858000010001000000000669636c6f756403636f6d0000010001c00c000100010000105a00044d583737>",
                    "I2": "",
                    "I3": "",
                    "I4": "",
                    "I5": "",
                    "Jc": "5",
                    "Jmax": "50",
                    "Jmin": "10",
                    "S1": "55",
                    "S2": "50",
                    "S3": "33",
                    "S4": "3",
                    "last_config": last_config_json,
                    "port": str(server_port),
                    "protocol_version": "2",
                    "subnet_address": "10.8.1.0",
                    "transport_proto": "udp"
                },
                "container": "amnezia-awg2"
            }
        ],
        "defaultContainer": "amnezia-awg2",
        "description": "Амстердам",
        "dns1": "1.1.1.1",
        "dns2": "1.0.0.1",
        "hostName": server_host,
        "nameOverriddenByUser": True
    }
    
    # Сериализуем основной JSON БЕЗ indent (компактно)
    config_json = json.dumps(config_template, ensure_ascii=False, separators=(',', ':'))
    
    # Сжимаем zlib
    compressed = zlib.compress(config_json.encode('utf-8'))
    
    # Добавляем заголовок 00 00 0b
    final_data = b'\x00\x00\x0b\x75' + compressed
    
    # Кодируем в base64 url-safe
    encoded = base64.urlsafe_b64encode(final_data).decode('utf-8').rstrip('=')
    
    return f"vpn://{encoded}"


if __name__ == "__main__":
    if len(sys.argv) < 7:
        print("Использование: python generate_config.py <client_priv_key> <client_pub_key> <client_ip> <server_host> <server_port> <server_pub_key> <preshared_key>")
        sys.exit(1)
    
    result = generate_config(*sys.argv[1:])
    print(result)