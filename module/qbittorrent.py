from dataclasses import dataclass
from qbittorrentapi import Client

from .baseconfig import BaseConfig

@dataclass
class QBConfig(BaseConfig):
    host: str = "http://localhost:8080/"
    username: str = "admin"
    password: str = "adminadmin"

class QBWorker:
    def __init__(self, config: QBConfig):
        self._config = config
        self._client = Client(
            host=config.host,
            username=config.username,
            password=config.password
        )
