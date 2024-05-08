import argparse
from dataclasses import dataclass, field
import os
from qbittorrentapi import TorrentDictionary
import re
from typing import List, Dict, Literal

from module.qbittorrent import QBConfig, QBWorker


@dataclass
class Config(QBConfig):
    torrent_filter: Dict[str, str] = field(default_factory = lambda: {
        "status_filter": "completed",
        "category": "动漫",
    })
    tag_mapping: Dict[str, str] = field(default_factory = lambda: {
        "todo": "RSS",
        "completed": "完结",
        "ongoing": "连载",
    })
    library: str = "/jellyfin/anime"


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
            re.compile(r"\[(.*?)\] (.*?)(?: (?:S(?:eason ?)?)?(\d+))? ?(?:\[(?:\d+)-(?:\d+)(?: ?[Ff][Ii][Nn])(?:\+SP)??\])?\[(.*?)\]"),
        ]:
            match = pattern.match(name)
            if match:
                return Bangumi(
                    type="multi",
                    groups=match.group(1).split("&"),
                    name=match.group(2),
                    season=1 if match.group(3) is None else int(match.group(3)),
                    meta=match.group(4).split(),
                )
        raise ValueError(f"Failed to match name: {name}")

    @staticmethod
    def parse_single(name: str) -> "Bangumi":
        for pattern in [
            # [group] name - episode [meta].ext
            re.compile(r"\[(.*?)\] (.*?)(?: (?:S(?:eason ?)?)?(\d+))? - (\d+)(?:v(\d+))? \[(.*?)\]\.(.*)"),
            # [group] name [episode][meta].ext
            re.compile(r"\[(.*?)\] (.*?)(?: (?:S(?:eason ?)?)?(\d+))? \[(\d+)(?:v(\d+))?\]\[(.*?)\]\.(.*)"),
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
                    meta=match.group(6).split(),
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

class Worker(QBWorker):
    def __init__(self, config: Config):
        super().__init__(config)
        self._config = config

    def handle(self, torrent: str | TorrentDictionary, force: bool = False) -> None:
        if isinstance(torrent, str):
            torrent = self._client.torrents_info(
                torrent_hashes=torrent,
                **self._config.torrent_filter,
            )
            if len(torrent) != 1:
                raise ValueError(f"Failed to find torrent")
            torrent = torrent[0]

        assert torrent["progress"] == 1.0

        print(f"Handling torrent {torrent['hash']}")

        if not (force or self._config.tag_mapping["todo"] in torrent["tags"]):
            print(f"... already handled")
            return

        if self._config.tag_mapping["completed"] in torrent["tags"]:
            preffered = "multi"
        elif self._config.tag_mapping["ongoing"] in torrent["tags"]:
            preffered = "single"
        else:
            raise NotImplementedError(f"has no known tag: {torrent['tags']}")

        print(f"... name: {torrent['name']}")
        bangumi = Bangumi.parse(torrent["name"], preffered)

        if bangumi.type == "multi":
            print(f"... match: '{bangumi.name}' (multi-episode)")
            torrent.set_location(os.path.join(
                self._config.library,
                bangumi.name,
            ))
            torrent.rename_folder(
                old_path=torrent["name"],
                new_path=f"S{bangumi.season:02d}",
            )
        else:
            print(f"... match: '{bangumi.name}' S{bangumi.season:02d}E{bangumi.episode:02d}")
            torrent.set_location(os.path.join(
                self._config.library,
                bangumi.name,
                f"S{bangumi.season:02d}",
            ))

        torrent.remove_tags(self._config.tag_mapping["todo"])

    def handle_all(self, force: bool = False) -> None:
        for torrent in self._client.torrents_info(**self._config.torrent_filter):
            try:
                self.handle(torrent, force)
            except NotImplementedError as e:
                print(f"Skipped: {e}")
            except ValueError as e:
                print(f"Skipped: {e}")

    def set_rss_tag(self) -> None:
        for (name, rule) in self._client.rss_rules().items():
            if self._config.tag_mapping["todo"] in rule["torrentParams"]["tags"]:
                continue
            print(f"Adding tag {self._config.tag_mapping['todo']} to rule {name}")
            rule["torrentParams"]["tags"].append(self._config.tag_mapping["todo"])
            self._client.rss_set_rule(
                rule_name=name,
                rule_def=rule,
            )


parser = argparse.ArgumentParser()
parser.add_argument("--config", default="./config.json", type=str, help="Path to the config file")
parser.add_argument("--hash", default="all", type=str, help="Torrent hash")
parser.add_argument("--force", action="store_true", help="Force handle all torrents")

parser.add_argument("--set-rss-tag", action="store_true", help="Set RSS tag to all rules")

args = parser.parse_args()

if __name__ == "__main__":
    config = Config().load(args.config)
    worker = Worker(config)

    if args.set_rss_tag:
        worker.set_rss_tag()
        exit()

    if args.hash == "all":
        worker.handle_all(args.force)
    else:
        worker.handle(args.hash, args.force)
