import os
import paramiko


def load_env():
    env_path = "/opt/durdom-bot/.env"
    env_vars = {}

    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()

    return env_vars


ENV = load_env()

SSH_HOST = ENV.get("VPN_SSH_HOST", "")
SSH_PORT = int(ENV.get("VPN_SSH_PORT", 22))
SSH_USER = ENV.get("VPN_SSH_USER", "root")
SSH_KEY_PATH = ENV.get(
    "VPN_SSH_KEY_PATH",
    "/opt/durdom-bot/ssh_keys/durdom_vpn_key"
)

DOCKER_CONTAINER = ENV.get(
    "DOCKER_CONTAINER",
    "amnezia-awg2"
)

WG_INTERFACE = ENV.get(
    "WG_INTERFACE",
    "awg0"
)

WG_SERVER_PORT = int(
    ENV.get("WG_SERVER_PORT", 45135)
)

WG_SERVER_PUBLIC_KEY = ENV.get(
    "WG_SERVER_PUBLIC_KEY",
    ""
)

WG_PRESHARED_KEY = ENV.get(
    "WG_PRESHARED_KEY",
    ""
)

def get_ssh():
    """
    Создаёт SSH подключение.
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    ssh.connect(
        hostname=SSH_HOST,
        port=SSH_PORT,
        username=SSH_USER,
        key_filename=SSH_KEY_PATH,
        timeout=10,
    )

    return ssh


def exec_ssh(ssh, command):
    """
    Выполняет команду по SSH.
    """
    stdin, stdout, stderr = ssh.exec_command(command)

    return (
        stdout.read().decode(),
        stderr.read().decode()
    )
