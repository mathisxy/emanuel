from enum import Enum
from dataclasses import dataclass
import socket


class DomainRepresentation(Enum):
    HOSTNAME = "hostname"
    IP = "ip"


@dataclass
class ServerInfo:
    domain: str
    port: int
    representation: DomainRepresentation = DomainRepresentation.HOSTNAME

    def domain_as_ip(self) -> str:
        return socket.gethostbyname(self.domain)

    @property
    def resolved_domain(self) -> str:
        match self.representation:
            case DomainRepresentation.HOSTNAME:
                return self.domain
            case DomainRepresentation.IP:
                return self.domain_as_ip()

domain = "mathis.party"

server_infos = {
    "enshrouded": ServerInfo(domain, 15637, DomainRepresentation.IP),
    "minecraft_vanilla": ServerInfo(domain, 25567),
    "minecraft_drehmal": ServerInfo(domain, 25566),
    "minecraft_speedrun": ServerInfo(domain, 25565),
    "minecraft_community": ServerInfo(domain, 25564),
}

minecraft_server_paths = {
    "minecraft_vanilla": "/mnt/samsung/fabric",
    "minecraft_drehmal": "/mnt/samsung/drehmal",
    "minecraft_speedrun": "/mnt/samsung/speedrun",
    "minecraft_community": "/mnt/samsung/community",
}