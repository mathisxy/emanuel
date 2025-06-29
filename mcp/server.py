import random
import socket
import subprocess

from fastmcp import FastMCP

# FastMCP Server initialisieren
mcp = FastMCP("game_servers")

@mcp.tool()
def roll_dice(sides: int = 6) -> int:
    """Würfelt einen Würfel mit der angegebenen Seitenanzahl"""
    if sides < 2:
        raise Exception("Ein Würfel muss mindestens zwei Seiten haben")

    result = random.randint(1, sides)
    print("RESULT")
    print(result)
    return result

@mcp.tool()
def get_minecraft_vanilla_server_status() -> str:
    """Gibt den aktuellen Online Status des Minecraft Vanilla Servers zurück.
    Der Server läuft über die Adresse: mathis.party:25565"""
    result = subprocess.run(
        ['systemctl', 'is-active', 'minecraft'],
        capture_output=True,
        text=True,
        timeout=5
    )
    return result.stdout.strip()

@mcp.tool()
def start_minecraft_vanilla_server() -> str:
    """Startet den Minecraft Vanilla Server"""
    result = subprocess.run(
        ['sudo', 'service', 'minecraft', 'start'],
        capture_output=True,
        text=True,
        timeout=10
    )
    if result.returncode == 0:
        return "Server wird gestartet"
    else:
        return f"Fehler beim Starten: {result.stderr.strip()}"

@mcp.tool()
def stop_minecraft_vanilla_server() -> str:
    """Stoppt den Minecraft Vanilla Server"""
    result = subprocess.run(
        ['sudo', 'service', 'minecraft', 'stop'],
        capture_output=True,
        text=True,
        timeout=10
    )
    if result.returncode == 0:
        return "Server wird gestoppt"
    else:
        return f"Fehler beim Stoppen: {result.stderr.strip()}"

@mcp.tool()
def restart_minecraft_vanilla_server() -> str:
    """Startet den Minecraft Vanilla Server neu"""
    result = subprocess.run(
        ['sudo', 'service', 'minecraft', 'restart'],
        capture_output=True,
        text=True,
        timeout=15
    )
    if result.returncode == 0:
        return "Server wird neu gestartet"
    else:
        return f"Fehler beim Neustarten: {result.stderr.strip()}"


@mcp.tool()
def get_minecraft_drehmal_server_status() -> str:
    """Gibt den aktuellen Online Status des Minecraft Drehmal Adventure Servers zurück.
    Der Server läuft über die Adresse: mathis.party:25566"""
    result = subprocess.run(
        ['systemctl', 'is-active', 'drehmal'],
        capture_output=True,
        text=True,
        timeout=5
    )
    return result.stdout.strip()

@mcp.tool()
def start_minecraft_drehmal_server() -> str:
    """Startet den Minecraft Drehmal Adventure Server"""
    result = subprocess.run(
        ['sudo', 'service', 'drehmal', 'start'],
        capture_output=True,
        text=True,
        timeout=10
    )
    if result.returncode == 0:
        return "Server wird gestartet"
    else:
        return f"Fehler beim Starten: {result.stderr.strip()}"

@mcp.tool()
def stop_minecraft_drehmal_server() -> str:
    """Stoppt den Minecraft Drehmal Adventure Server"""
    result = subprocess.run(
        ['sudo', 'service', 'drehmal', 'stop'],
        capture_output=True,
        text=True,
        timeout=10
    )
    if result.returncode == 0:
        return "Server wird gestoppt"
    else:
        return f"Fehler beim Stoppen: {result.stderr.strip()}"

@mcp.tool()
def restart_minecraft_drehmal_server() -> str:
    """Startet den Minecraft Drehmal Adventure Server neu"""
    result = subprocess.run(
        ['sudo', 'service', 'drehmal', 'restart'],
        capture_output=True,
        text=True,
        timeout=15
    )
    if result.returncode == 0:
        return "Server wird neu gestartet"
    else:
        return f"Fehler beim Neustarten: {result.stderr.strip()}"

@mcp.tool()
def get_enshrouded_server_status() -> str:
    """Gibt den aktuellen Online Status des Enshrouded Servers zurück.
     Falls der Server online ist, aber im Spiel nicht auftaucht, schlage ein Server Update vor.
     """
    result = subprocess.run(
        ['systemctl', 'is-active', 'enshrouded'],
        capture_output=True,
        text=True,
        timeout=5
    )
    return result.stdout.strip()

@mcp.tool()
def get_enshrouded_server_address() -> str:
    """Gibt die aktuelle IPv4-Adresse des Enshrouded Servers mit Port zurück, für das manuelle Verbinden."""

    try:
        ip_address = socket.gethostbyname("mathis.party")
        return f"{ip_address}:15637"
    except socket.gaierror as e:
        return f"Fehler bei der DNS-Auflösung von mathis.party: {str(e)}"


@mcp.tool()
def start_enshrouded_server() -> str:
    """Startet den Enshrouded Server"""
    result = subprocess.run(
        ['sudo', 'service', 'enshrouded', 'start'],
        capture_output=True,
        text=True,
        timeout=10
    )
    if result.returncode == 0:
        return "Server wird gestartet"
    else:
        return f"Fehler beim Starten: {result.stderr.strip()}"

@mcp.tool()
def stop_enshrouded_server() -> str:
    """Stoppt den Enshrouded Server"""
    result = subprocess.run(
        ['sudo', 'service', 'enshrouded', 'stop'],
        capture_output=True,
        text=True,
        timeout=10
    )
    if result.returncode == 0:
        return "Server wird gestoppt"
    else:
        return f"Fehler beim Stoppen: {result.stderr.strip()}"

@mcp.tool()
def restart_enshrouded_server() -> str:
    """Startet den Enshrouded Server neu"""
    result = subprocess.run(
        ['sudo', 'service', 'enshrouded', 'restart'],
        capture_output=True,
        text=True,
        timeout=15
    )
    if result.returncode == 0:
        return "Server wird neu gestartet"
    else:
        return f"Fehler beim Neustarten: {result.stderr.strip()}"


@mcp.tool()
def update_enshrouded_server() -> str:
    """Stoppt den Enshrouded Server und startet ein SteamCMD-Update"""

    cmd = (
        "sudo service enshrouded stop && "
        "sudo /usr/games/steamcmd "
        "+@sSteamCmdForcePlatformType windows "
        "+force_install_dir /mnt/samsung/enshrouded-server "
        "+login anonymous +app_update 2278520 +quit"
    )

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300  # 5 Minuten Timeout, anpassbar
        )

        if result.returncode == 0:
            return "Enshrouded Server Update wurde erfolgreich durchgeführt."
        else:
            return f"Fehler beim Update:\n{result.stderr.strip() or result.stdout.strip()}"

    except subprocess.TimeoutExpired:
        return "Timeout: Das Update hat zu lange gedauert und wurde abgebrochen."
    except Exception as e:
        return f"Fehler beim Ausführen des Updates: {str(e)}"

# Server erstellen und starten
if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8001
    )