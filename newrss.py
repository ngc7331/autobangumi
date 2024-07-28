import argparse
from dataclasses import dataclass, field
from typing import Dict, Tuple

from module.qbittorrent import QBConfig, QBWorker


@dataclass
class Config(QBConfig):
    @dataclass
    class SeedingLimit:
        ratio: float
        time: int
        inactive_time: int
        class Constant:
            DISABLED = -1.0
            GLOBAL = -2.0

    tag_mapping: Dict[str, str] = field(default_factory = lambda: {
        "todo": "RSS",
        "ongoing": "连载",
        "bt": "BT",
    })
    completed_keyword: str = "TV"
    category: str = "动漫"
    stopped: bool = False
    seeding_limit_pt: SeedingLimit = field(default_factory = lambda: Config.SeedingLimit(
        ratio = Config.SeedingLimit.Constant.GLOBAL,
        time = Config.SeedingLimit.Constant.GLOBAL,
        inactive_time = Config.SeedingLimit.Constant.GLOBAL,
    ))
    seeding_limit_bt: SeedingLimit = field(default_factory = lambda: Config.SeedingLimit(
        ratio = 2.0,
        time = 10080,
        inactive_time = 10080,
    ))

class Worker(QBWorker):
    def __init__(self, config: Config):
        super().__init__(config)
        self._config = config

    def add(self):
        print("Creating new RSS rule for ongoing bangumi...")
        name = input("Rule name: ")
        rss_items = [(name, params) for name, params in self._client.rss_items().items()]
        print("\n".join([f"{i} {name}" for i, (name, _) in enumerate(rss_items)]))
        source = rss_items[int(input("Source: "))][1]["url"]
        keyword = input("Keyword(regex): ")
        bt = input("BT(y/N): ").lower() in ["y", "yes"]

        seeding_limit = self._config.seeding_limit_bt if bt else self._config.seeding_limit_pt

        self._client.rss_set_rule(
            rule_name=name,
            rule_def={
                "enabled": True,
                "mustContain": keyword,
                "mustNotContain": self._config.completed_keyword,
                "useRegex": True,
                "affectedFeeds": [source],
                "assignedCategory": self._config.category,
                "torrentParams": {
                    "category": self._config.category,
                    "tags": [
                        self._config.tag_mapping["ongoing"],
                        self._config.tag_mapping["todo"],
                    ] + ([self._config.tag_mapping["bt"]] if bt else []),
                    "stopped": self._config.stopped,
                    "ratio_limit": seeding_limit.ratio,
                    "seeding_time_limit": seeding_limit.time,
                    "inactive_seeding_time_limit": seeding_limit.inactive_time,
                },
            },
        )

    def show(self):
        print("RSS Rules:")
        for name, rule in self._client.rss_rules().items():
            print(f"{name}: {rule}")

        # print("Torrents:")
        # for torrent in self._client.torrents_info():
        #     print(f"{torrent['name']}: {torrent['seeding_time_limit']}")


parser = argparse.ArgumentParser()
parser.add_argument("--config", default="./config.json", type=str, help="Path to the config file")

parser.add_argument("--show", action="store_true", help="Show RSS rule")

args = parser.parse_args()

if __name__ == "__main__":
    config = Config().load(args.config)
    worker = Worker(config)

    if args.show:
        worker.show()
        exit()

    worker.add()
