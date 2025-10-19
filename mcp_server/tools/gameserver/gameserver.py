import json
import logging
import os
import socket
import subprocess
from typing import List, Literal, Annotated, Dict

import requests
from mcstatus import JavaServer
from steam import SteamQuery

from mcp_server.mcp_instance import mcp

from mcp_server.tools.gameserver.speedrun_server_properties import properties as speedrun_server_properties


@mcp.tool(tags={"Gameserver"})
def control_game_server(
        servers: List[Literal["minecraft_vanilla", "minecraft_drehmal", "minecraft_speedrun", "enshrouded"]],
        operation: Annotated[Literal["status", "start", "stop", "restart"], "Die Operation status gibt Online Status, Serveradresse, Servername und Spieleranzahl zurück. Außerdem sind start, stop und restart der Server möglich"]
) -> List[str]:
    """Management der Game-Server"""

    if not servers:
        raise Exception('Keine Server angegeben. Vorhandene Server: ["minecraft_vanilla", "minecraft_drehmal", "minecraft_speedrun", "enshrouded"]')


    output: List[str] = []

    for server in servers:
        if operation == "status":

            result = subprocess.run(
                ['systemctl', 'is-active', server],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.stdout.strip() == "active":
                output.append(f"{server}: {_get_extended_server_info(server)}")
            else:
                output.append(f"{server} ist offline")

        else:
            result = subprocess.run(
                ['sudo', 'service', server, operation],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                output.append(f"{server} {operation} erfolgreich")
            else:
                output.append(f"{server} {operation} fehlgeschlagen: {result.stderr.strip()}")

    return output

def _get_extended_server_info(server: Literal["enshrouded", "minecraft_vanilla", "minecraft_speedrun", "minecraft_drehmal"]) -> Dict:
    domain, port = _get_server_address(server)

    if server == "enshrouded":
        server_obj = SteamQuery(domain, port)
        return_dictionary = server_obj.query_server_info()
        return {
            "address": f"{domain}:{port}",
            "name": return_dictionary.get("name", "unbekannt"),
            "online": f"{return_dictionary.get("players")}/{return_dictionary.get("max_players")}"
        }

    if server.startswith("minecraft_"):
        server_obj = JavaServer.lookup(f"{domain}:{port}")
        status = server_obj.status()
        return {
            "address": f"{domain}:{port}",
            "version": status.version.name,
            "description": status.description,
            "online": "niemand" if status.players.online == 0 else ", ".join([name.name for name in status.players.sample])
        }


def _get_server_address(server: Literal["minecraft_vanilla", "minecraft_drehmal", "minecraft_speedrun", "enshrouded"]) -> (str, int):
    domain = "mathis.party"
    if server == "enshrouded":
        domain = socket.gethostbyname(domain)
        port = 15637
    elif server == "minecraft_vanilla":
        port = 25567
    elif server == "minecraft_drehmal":
        port = 25566
    elif server == "minecraft_speedrun":
        port = 25565
    else:
        raise Exception("Unbekannter Server")

    return domain, port


@mcp.tool(tags={"Gameserver"})
def set_minecraft_server_property(
        server: Literal["minecraft_vanilla", "minecraft_drehmal", "minecraft_speedrun"],
        server_property: str,
        value: str,
        check_if_property_exists: bool = True,
) -> str:
    """Ändert die server.properties Datei des angegebenen Minecraft Servers.
    Damit die Änderungen wirksam werden muss dieser Server neu gestartet werden."""

    server_paths = {
        "minecraft_vanilla": "/mnt/samsung/fabric",
        "minecraft_drehmal": "/mnt/samsung/drehmal",
        "minecraft_speedrun": "/mnt/samsung/speedrun",
    }

    if server not in server_paths:
        raise Exception(f"Unbekannter Server: {server}")

    path = server_paths[server]

    _set_minecraft_server_property(path, server_property, value, check_if_property_exists)

    return f"Die Property '{server_property}' für {server} wurde auf '{value}' gesetzt"


def _set_minecraft_server_property(path: str, server_property: str, value: str, check_if_property_exists: bool) -> None:

    path = os.path.join(path, "server.properties")

    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} wurde nicht gefunden")

    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    found = False
    for i, line in enumerate(lines):
        # ignoriert Kommentare
        if line.strip().startswith("#"):
            continue
        if line.startswith(f"{server_property}="):
            lines[i] = f"{server_property}={value}\n"
            found = True
            break

    # Falls Property nicht existiert → am Ende hinzufügen
    if not found:
        if check_if_property_exists:
            raise Exception(f"Property '{server_property}' wurde nicht gefunden in {path}")
        if not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(f"{server_property}={value}\n")

    # Datei überschreiben
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def _get_server_jar_url(version: Literal["latest", "snapshot"]|str):

    manifest_url = os.getenv("MINECRAFT_MANIFEST_URL")

    logging.info(manifest_url)

    manifest = requests.get(manifest_url).json()

    if version == "latest":
        version = manifest["latest"]["release"]
    elif version == "snapshot":
        version = manifest["latest"]["snapshot"]

    try:
        version_info = next(v for v in manifest["versions"] if v["id"] == version)
    except StopIteration:
        available_versions = sorted(
            (v["id"] for v in manifest["versions"]),
            reverse=True
        )
        available_versions_str = "\n - ".join(available_versions)
        raise Exception(
            f"{version} ist keine gültige Version. "
            f"Verfügbare Versionen sind: "
            f" - latest, "
            f" - snapshot, "
            f" - {available_versions_str}"
        )

    logging.info(version_info)

    extended_version_info = requests.get(version_info["url"]).json()

    logging.info(extended_version_info)

    return extended_version_info["downloads"]["server"]["url"]

@mcp.tool(tags={"Gameserver"})
def reset_minecraft_speedrun_server(hardcore: bool, version: Annotated[str, "\"latest\", \"snapshot\" sowie alle spezifische Minecraft Versionen können hier übergeben werden"]) -> str:
    """Löscht den Minecraft Speedrun Server und erstellt einen neuen."""

    path = os.getenv("MINECRAFT_SPEEDRUN_PATH")
    url = _get_server_jar_url(version)

    subprocess.run(
        ["sudo", "service", "minecraft_speedrun", "stop"],
        capture_output=True,
        text=True,
        timeout=10
    )

    subprocess.run(
        ["rm", "-rf", path],
        capture_output=True, text=True
    )

    subprocess.run(["mkdir", "-p", path], check=True)
    subprocess.run(["sudo", "chown", "minecraft", path], check=True)

    subprocess.run(["wget", "-O", os.path.join(path, "server.jar"), url], check=True)

    with open(f"{path}/eula.txt", "w") as f:
        f.write("eula=true\n")


    properties = speedrun_server_properties.replace("{HARDCORE_MODE}", "true" if hardcore else "false")

    with open(os.path.join(path, "server.properties"), "w", encoding="utf-8") as f:
        f.write(properties)

    subprocess.run(["sudo", "service", "minecraft_speedrun", "start"], check=True)

    return "Der Minecraft Speedrun Server wurde resettet"


def _get_uuid(name: str) -> str:
    """Ermittelt die UUID eines Minecraft-Spielers über die Mojang API."""
    resp = requests.get(f"https://api.mojang.com/users/profiles/minecraft/{name}")
    if resp.status_code == 200:
        return resp.json()["id"]
    raise Exception(f"Konnte UUID für {name} nicht finden.")

def _format_uuid(uuid: str) -> str:
    """Fügt die Dashes in eine Mojang-UUID ein."""
    return f"{uuid[0:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:32]}"

@mcp.tool(tags={"Gameserver"})
def give_minecraft_speedrun_admin(
        name: Literal["Perzer", "Mathisxy", "xVaiders", "Schokoboot", "PaddyderBOY", "808Bot"]
) -> str:
    """Gibt einem der erlaubten Spieler Adminrechte (OP) auf dem Minecraft Speedrun Server."""

    path = os.getenv("MINECRAFT_SPEEDRUN_PATH")
    if not path:
        raise Exception("MINECRAFT_SPEEDRUN_PATH ist nicht gesetzt")

    ops_path = os.path.join(path, "ops.json")
    logging.info(ops_path)

    # Aktuelle ops.json laden
    if os.path.exists(ops_path):
        try:
            with open(ops_path, "r", encoding="utf-8") as f:
                current_ops = json.load(f)
        except json.JSONDecodeError:
            logging.error("JSON Decode von ops.json fehlgeschlagen. Inhalt wird ignoriert und überschrieben.")
            current_ops = []
    else:
        raise FileNotFoundError("Die Datei ops.json wurde nicht gefunden")

    existing_names = {op.get("name", "") for op in current_ops}

    logging.info(current_ops)
    logging.info(existing_names)

    if name not in existing_names:
        uuid = _format_uuid(_get_uuid(name))
        logging.info(uuid)
        current_ops.append({
            "uuid": uuid,
            "name": name,
            "level": 4,
            "bypassesPlayerLimit": True
        })

        logging.info(current_ops)

        with open(ops_path, "w", encoding="utf-8") as f:
            logging.info("Writing to ops.json")
            f.write(json.dumps(current_ops, indent=2, ensure_ascii=False))

        with open(ops_path, "r", encoding="utf-8") as verify:
            logging.info("Content after write: %s", verify.read())

        subprocess.run(["sudo", "service", "minecraft_speedrun", "restart"], check=True)

        return f"{name} wurde als Admin hinzugefügt."
    else:
        return f"{name} ist bereits Admin."



@mcp.tool(tags={"Gameserver"})
def update_enshrouded_server() -> str:
    """Updated den Enshrouded Server"""

    cmd = (
        "sudo service enshrouded stop && "
        "sudo /usr/games/steamcmd "
        "+@sSteamCmdForcePlatformType windows "
        "+force_install_dir /mnt/samsung/enshrouded-server "
        "+login anonymous +app_update 2278520 +quit" #&& "
        #"sudo service enshrouded start"
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