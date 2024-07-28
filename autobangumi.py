import argparse
from dataclasses import dataclass, field
import os
from qbittorrentapi import TorrentDictionary
import re
from typing import List, Dict, Literal

from module.bangumi import Bangumi
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
    local_mode: bool = True  # is running on same host(container) with qbittorrent


class Worker(QBWorker):
    def __init__(self, config: Config):
        super().__init__(config)
        self._config = config

    def handle(self, torrent: str | TorrentDictionary, force: bool = False, do_jellyfin_stds: bool = False) -> None:
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

            if do_jellyfin_stds:
                self.jellyfin_stds(torrent)

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

    def jellyfin_stds(self, torrent: str | TorrentDictionary) -> None:
        if isinstance(torrent, str):
            torrent = self._client.torrents_info(
                torrent_hashes=torrent,
                **self._config.torrent_filter,
            )
            if len(torrent) != 1:
                raise ValueError(f"Failed to find torrent")
            torrent = torrent[0]

        assert torrent["progress"] == 1.0

        # rename files & add .ignore
        for file in torrent.files:
            path_s = file["name"]
            path = path_s.split("/")
            match len(path):
                case 2:
                    try:
                        episode = Bangumi.parse_single(path[1])
                    except ValueError:
                        continue
                    new_path = os.path.join(path[0], episode.filename())
                    if path_s != new_path:
                        print(f"... rename: {path_s} -> {new_path}")
                        torrent.rename_file(
                            old_path=path_s,
                            new_path=new_path,
                        )
                case 3:
                    if not self._config.local_mode:
                        continue
                    # add .ignore file to subfolder
                    path = os.path.join(torrent["save_path"], path[0], path[1])
                    print(f"... add .ignore to {path}")
                    with open(os.path.join(path, ".ignore"), "w") as f:
                        pass
                case _:
                    pass

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
        try:
            worker.handle(args.hash, args.force)
        except NotImplementedError as e:
            print(f"Skipped: {e}")
        except ValueError as e:
            print(f"Skipped: {e}")
