import subprocess

# Definiere erlaubte Servernamen und ihre systemd-Services
SERVERS = {
    "drehmal": "drehmal",
    "minecraft": "minecraft"
}

def get_server_list():
    return list(SERVERS.keys())

def start_server(name):
    service = SERVERS.get(name)
    if not service:
        return False
    try:
        subprocess.run(["systemctl", "start", service], check=True)
        return True
    except subprocess.CalledProcessError:
        return False