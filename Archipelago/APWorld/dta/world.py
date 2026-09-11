"""Settings-driven Dawn of the Tiberium Age Archipelago world."""

from collections import Counter

from BaseClasses import Item, ItemClassification, Location, Region, Tutorial
from worlds.AutoWorld import WebWorld, World

from .data import (
    CATALOGUE_CHECKSUM,
    GAME_NAME,
    ITEM_DATA,
    ITEM_NAME_GROUPS,
    ITEM_TABLE,
    LOCATION_TABLE,
    MISSION_DATA,
    VICTORY_EVENT,
    SHOP_PURCHASE_LOCATION_TABLE,
    SHOP_STAGE_LOCATION_TABLE,
    SHOP_STAGE_LOGIC_DATA,
    SHOP_STAGE_LOGIC_ITEM_TABLE,
    location_entries,
    shop_item_location_entries,
)
from .manifest import parse_manifest
from .options import DTAOptions


class DTAItem(Item):
    game = GAME_NAME


class DTALocation(Location):
    game = GAME_NAME


class DTAWebWorld(WebWorld):
    theme = "partyTime"
    tutorials = [
        Tutorial(
            "Dawn of the Tiberium Age Multiworld Setup Guide",
            "Connect the embedded Dawn of the Tiberium Age Randomizer client.",
            "English",
            "setup_en.md",
            "setup/en",
            ["Dawn of the Tiberium Age Randomizer contributors"],
        )
    ]


class DTAWorld(World):
    """Full catalogue; each seed's shape comes from one signed manifest."""

    game = GAME_NAME
    web = DTAWebWorld()
    options_dataclass = DTAOptions
    options: DTAOptions

    item_name_to_id = {
        **{name: data["id"] for name, data in ITEM_DATA.items()},
        **SHOP_STAGE_LOGIC_ITEM_TABLE,
    }
    location_name_to_id = dict(LOCATION_TABLE)
    item_name_groups = ITEM_NAME_GROUPS
    location_name_groups = {
        "Objectives": {
            name for name in LOCATION_TABLE if " - Objective " in name
        },
        "Mission Completion": {
            name for name in LOCATION_TABLE if " - Mission Complete - " in name
        },
    }

    def generate_early(self) -> None:
        from .generation import generate_manifest

        settings = self.options.launcher_settings.value
        legacy = self.options.generated_world.value or self.options.run_manifest.value
        if legacy and not settings:
            template = parse_manifest(legacy)
            # Old exports remain readable, but their frozen world is regenerated.
            settings = template.get("frozen_settings", {}).get("launcher")
            if not settings:
                raise ValueError("Legacy YAML has no launcher_settings; export it again.")
        self.run_manifest = generate_manifest(
            settings, f"DTA-{self.random.getrandbits(64):016X}"
        )

    def create_item(self, name: str) -> DTAItem:
        if name in SHOP_STAGE_LOGIC_ITEM_TABLE:
            return DTAItem(name, ItemClassification.progression,
                           SHOP_STAGE_LOGIC_ITEM_TABLE[name], self.player)
        item_id, classification = ITEM_TABLE[name]
        return DTAItem(name, classification, item_id, self.player)

    def _active_location_entries(self):
        for code in self.run_manifest["mission_order"]:
            for check_id, count in self.run_manifest["locations"][code].items():
                yield from location_entries(code, check_id, count)

    def create_regions(self) -> None:
        menu = Region("Menu", self.player, self.multiworld)
        victory = DTALocation(
            self.player,
            VICTORY_EVENT,
            None,
            menu,
        )
        if self.run_manifest.get("shop") is not None:
            regions = [menu]
            self._create_shop_regions(menu, victory, regions)
            self.multiworld.regions += regions
            return
        victory.place_locked_item(
            DTAItem(
                VICTORY_EVENT,
                ItemClassification.progression,
                None,
                self.player,
            )
        )
        menu.locations.append(victory)
        regions = [menu]
        by_location = {}
        for code in self.run_manifest["mission_order"]:
            mission = MISSION_DATA[code]
            region = Region(mission["title"], self.player, self.multiworld)
            active = {}
            for check_id, count in self.run_manifest["locations"][code].items():
                active.update(dict(location_entries(code, check_id, count)))
            region.add_locations(active, DTALocation)
            by_location.update({location.name: location for location in region.locations})
            menu.connect(region)
            regions.append(region)

        for placement in self.run_manifest.get("local_placements", []):
            name, _location_id = location_entries(
                placement["mission"],
                placement["check"],
                placement["slot"],
            )[-1]
            by_location[name].place_locked_item(
                self.create_item(placement["item"])
            )
        self.multiworld.regions += regions

    def _create_shop_regions(self, menu, victory, regions):
        shop = self.run_manifest["shop"]
        item_entries = shop_item_location_entries(
            shop["purchase_location_count"],
            shop["run_length"],
            shop["mission_victories_are_locations"],
            shop["item_location_count"],
        )
        menu.add_locations(dict(item_entries), DTALocation)
        previous_marker = None
        for stage in range(1, shop["run_length"] + 1):
            region = Region(
                f"Shop Run Stage {stage}", self.player, self.multiworld
            )
            if previous_marker is None:
                menu.connect(region)
            else:
                menu.connect(
                    region,
                    rule=lambda state, name=previous_marker: state.has(
                        name, self.player
                    ),
                )
            logic = SHOP_STAGE_LOGIC_DATA[stage]
            logic_location = DTALocation(
                self.player,
                logic["location_name"],
                logic["location_id"],
                region,
            )
            logic_location.place_locked_item(
                self.create_item(logic["item_name"])
            )
            region.locations.append(logic_location)
            previous_marker = logic["item_name"]
            regions.append(region)
        victory.access_rule = (
            lambda state, name=previous_marker: state.has(name, self.player)
        )
        victory.place_locked_item(DTAItem(
            VICTORY_EVENT,
            ItemClassification.progression,
            None,
            self.player,
        ))
        menu.locations.append(victory)

    def create_items(self) -> None:
        remaining = Counter(self.run_manifest["item_pool"])
        for placement in self.run_manifest.get("local_placements", []):
            remaining[placement["item"]] -= 1
        self.multiworld.itempool += [
            self.create_item(name)
            for name, count in remaining.items()
            for _ in range(count)
        ]
        for name, count in self.run_manifest.get("starting_items", {}).items():
            for _ in range(count):
                self.multiworld.push_precollected(self.create_item(name))

    def set_rules(self) -> None:
        # Runtime completion is reported by the embedded client from the
        # Randomizer's native goal logic.  This private event only tells AP's
        # generation audit that item placement never gates mission unlocking.
        self.multiworld.completion_condition[self.player] = (
            lambda state: state.has(VICTORY_EVENT, self.player)
        )

    def get_filler_item_name(self) -> str:
        return "Player Army Armor Plating I"

    def fill_slot_data(self) -> dict:
        locations = {}
        for code in self.run_manifest["mission_order"]:
            locations[code] = {
                check_id: [
                    location_id
                    for _name, location_id in location_entries(
                        code, check_id, count
                    )
                ]
                for check_id, count in self.run_manifest["locations"][code].items()
            }
        used_items = set(self.run_manifest["item_pool"]) | set(
            self.run_manifest.get("starting_items", {})
        )
        shop = self.run_manifest.get("shop")
        shop_slot_data = None
        if shop is not None:
            item_entries = shop_item_location_entries(
                shop["purchase_location_count"],
                shop["run_length"],
                shop["mission_victories_are_locations"],
                shop["item_location_count"],
            )
            shop_slot_data = {
                **shop,
                "item_locations": [
                    location_id for _name, location_id in item_entries
                ],
                "purchase_locations": list(
                    SHOP_PURCHASE_LOCATION_TABLE.values()
                )[:shop["purchase_location_count"]],
                "stage_victories": [
                    {
                        "stage": stage,
                        "location": (
                            SHOP_STAGE_LOCATION_TABLE[
                                f"Shop Run Mission {stage} Victory"
                            ]
                            if shop["mission_victories_are_locations"]
                            else None
                        ),
                        "logic_item": SHOP_STAGE_LOGIC_DATA[stage]["item_id"],
                        "logic_location": SHOP_STAGE_LOGIC_DATA[stage][
                            "location_id"
                        ],
                    }
                    for stage in range(1, shop["run_length"] + 1)
                ],
            }
        return {
            "slot_data_version": 7 if shop is not None else 4,
            "randomizer_version": self.run_manifest["randomizer_version"],
            "randomizer_seed": self.run_manifest["randomizer_seed"],
            "catalogue_checksum": CATALOGUE_CHECKSUM,
            "manifest_checksum": self.run_manifest["manifest_checksum"],
            "campaign_filter": self.run_manifest["campaign_filter"],
            "progression_mode": self.run_manifest["progression_mode"],
            "mission_goal": self.run_manifest["mission_goal"],
            "mission_order": self.run_manifest["mission_order"],
            "goal": self.run_manifest["goal"],
            "shop": shop_slot_data,
            "run_manifest": self.run_manifest,
            "items": {
                str(ITEM_DATA[name]["id"]): name
                for name in sorted(used_items)
            },
            "locations": locations,
        }
