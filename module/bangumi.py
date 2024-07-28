from dataclasses import dataclass, field
from typing import List, Dict, Literal
import re

@dataclass
class Bangumi:
    type: Literal["single", "multi"] | None = None
    groups: List[str] | None = None
    name: str | None = None
    season: int = -1
    episode: int = -1  # valid for type == "single"
    version: int = -1  # valid for type == "single"
    meta: List[str] | None = None
    ext: str | None = None

    @staticmethod
    def parse_multi(name: str) -> "Bangumi":
        for pattern in [
            # [group] name [episodes][meta]
            re.compile(r"\[(.*?)\] (.*?)(?: (?:S(?:eason ?)?)?(\d+))? ?(?:\[(?:\d+)-(?:\d+)(?: ?[Ff][Ii][Nn])(?:\+SP)??\])?\[(.*)\]"),
        ]:
            match = pattern.match(name)
            if match:
                return Bangumi(
                    type="multi",
                    groups=match.group(1).split("&"),
                    name=match.group(2),
                    season=1 if match.group(3) is None else int(match.group(3)),
                    meta=match.group(4).replace("][", " ").split(),
                )
        raise ValueError(f"Failed to match name: {name}")

    @staticmethod
    def parse_single(name: str) -> "Bangumi":
        for pattern in [
            # [group] name - episode [meta].ext
            re.compile(r"\[(.*?)\] (.*?)(?: (?:S(?:eason ?)?)?(\d+))? - (\d+)(?:v(\d+))? \[(.*)\]\.(.*)"),
            # [group] name [episode][meta].ext
            re.compile(r"\[(.*?)\] (.*?)(?: (?:S(?:eason ?)?)?(\d+))? \[(\d+)(?:v(\d+))?\]\[(.*)\]\.(.*)"),
        ]:
            match = pattern.match(name)
            if match:
                return Bangumi(
                    type="single",
                    groups=match.group(1).split("&"),
                    name=match.group(2),
                    season=1 if match.group(3) is None else int(match.group(3)),
                    episode=int(match.group(4)),
                    version=1 if match.group(5) is None else int(match.group(5)),
                    meta=match.group(6).replace("][", " ").split(),
                    ext=match.group(7),
                )
        raise ValueError(f"Failed to match name: {name}")

    @staticmethod
    def parse(name: str, preffered: Literal["single", "multi"] = "single") -> "Bangumi":
        if preffered == "single":
            first = Bangumi.parse_single
            second = Bangumi.parse_multi
        elif preffered == "multi":
            first = Bangumi.parse_multi
            second = Bangumi.parse_single

        try:
            return first(name)
        except ValueError:
            return second(name)
