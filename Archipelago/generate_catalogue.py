"""Regenerate the checked-in Dawn of the Tiberium Age AP item/location snapshot."""

from pathlib import Path
import json

from Archipelago.catalogue_contract import build_snapshot


OUTPUT_PATH = (
    Path(__file__).resolve().parent
    / "APWorld"
    / "dta"
    / "catalogue.json"
)
GENERATION_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent
    / "generation_snapshot.json"
)


def main():
    from randomizer.core.paths import BATTLE_CLIENT_INI
    from randomizer.dta.rules import techno_catalogue
    from randomizer.missions.catalogue import parse_missions

    existing = None
    if OUTPUT_PATH.is_file():
        existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    snapshot = build_snapshot(existing)
    OUTPUT_PATH.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    generation_snapshot = {
        "schema_version": 1,
        "catalogue_checksum": snapshot["catalogue_checksum"],
        "techno_catalogue": techno_catalogue(),
        "missions": parse_missions(BATTLE_CLIENT_INI),
    }
    GENERATION_SNAPSHOT_PATH.write_text(
        json.dumps(
            generation_snapshot,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"{OUTPUT_PATH}: {len(snapshot['items'])} items, "
        f"{len(snapshot['locations'])} locations, "
        f"{snapshot['catalogue_checksum']}"
    )
    print(
        f"{GENERATION_SNAPSHOT_PATH}: "
        f"{len(generation_snapshot['techno_catalogue'])} techno records, "
        f"{len(generation_snapshot['missions'])} missions"
    )


if __name__ == "__main__":
    main()
