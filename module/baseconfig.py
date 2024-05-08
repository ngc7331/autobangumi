from dataclasses import dataclass
import json

class BaseConfig:
    def load(self, path: str) -> "BaseConfig":
        with open(path, "r") as f:
            self.__init__(**json.load(f))
        return self
