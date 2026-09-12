"""Build the deterministic DTA APWorld on Windows, Linux, or macOS."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ARCHIPELAGO_DIR = Path(__file__).resolve().parent
MODULE_NAME = 'dta'
SOURCE_DIR = ARCHIPELAGO_DIR / 'APWorld' / MODULE_NAME
GENERATION_SNAPSHOT = ARCHIPELAGO_DIR / 'generation_snapshot.json'
FIXED_TIMESTAMP = (2000, 1, 1, 0, 0, 0)


def archive_info(name: str) -> ZipInfo:
    info = ZipInfo(name, FIXED_TIMESTAMP)
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    return info


def build(output_directory: Path) -> Path:
    manifest_path = SOURCE_DIR / 'archipelago.json'
    catalogue_path = SOURCE_DIR / 'catalogue.json'
    if not manifest_path.is_file():
        raise FileNotFoundError(f'APWorld manifest not found: {manifest_path}')
    if not catalogue_path.is_file():
        raise FileNotFoundError(f'APWorld catalogue not found: {catalogue_path}')
    if not GENERATION_SNAPSHOT.is_file():
        raise FileNotFoundError(
            f'APWorld generation snapshot not found: {GENERATION_SNAPSHOT}'
        )

    sys.path.insert(0, str(ARCHIPELAGO_DIR.parent))
    from Archipelago.bundle_generation import (
        frozen_techno_records,
        generation_files,
    )
    from randomizer.core.version import APP_VERSION

    catalogue = json.loads(catalogue_path.read_text(encoding='utf-8'))
    generation_snapshot = json.loads(
        GENERATION_SNAPSHOT.read_text(encoding='utf-8')
    )
    if generation_snapshot.get('schema_version') != 1:
        raise ValueError('Unsupported APWorld generation snapshot schema.')
    if (
        generation_snapshot.get('catalogue_checksum')
        != catalogue.get('catalogue_checksum')
    ):
        raise ValueError(
            'APWorld catalogue and generation snapshot differ. Run '
            'python -m Archipelago.generate_catalogue from the launcher '
            'directory before building.'
        )
    techno_records = generation_snapshot.get('techno_catalogue')
    missions = generation_snapshot.get('missions')
    if not isinstance(techno_records, list) or not techno_records:
        raise ValueError('APWorld generation snapshot has no techno catalogue.')
    if not isinstance(missions, list) or not missions:
        raise ValueError('APWorld generation snapshot has no missions.')

    # Validate current reward/config code against checked-in game-derived data.
    # Importing these modules is safe after replacing both live DTA readers.
    from randomizer.dta import rules as dta_rules
    from randomizer.missions import catalogue as mission_catalogue
    dta_rules.techno_catalogue = lambda: frozen_techno_records(techno_records)
    mission_catalogue.parse_missions = lambda _path: missions
    from Archipelago.catalogue_contract import runtime_catalogue_checksum
    if catalogue['catalogue_checksum'] != runtime_catalogue_checksum():
        raise ValueError(
            'APWorld catalogue is stale. Run python -m '
            'Archipelago.generate_catalogue from the launcher directory '
            'before building.'
        )

    bundled_files = generation_files(techno_records)
    missions_data = json.dumps(missions, sort_keys=True).encode('utf-8')

    output_directory = output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f'{MODULE_NAME}.apworld'

    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest.update({
        'world_version': APP_VERSION,
        'compatible_version': 8,
        'version': 8,
        'maximum_ap_version': '0.6.7',
    })
    manifest_data = json.dumps(
        manifest,
        ensure_ascii=False,
        separators=(',', ':'),
    ).encode('utf-8')

    files = sorted(
        path for path in SOURCE_DIR.rglob('*')
        if path.is_file()
        and path != manifest_path
        and path.suffix != '.pyc'
        and '__pycache__' not in path.parts
    )
    with ZipFile(output_path, 'w') as archive:
        for source in files:
            relative = source.relative_to(SOURCE_DIR).as_posix()
            archive.writestr(
                archive_info(f'{MODULE_NAME}/{relative}'),
                source.read_bytes(),
            )
        for name, data in bundled_files:
            archive.writestr(archive_info(name), data)
        archive.writestr(archive_info(f'{MODULE_NAME}/generation_missions.json'), missions_data)
        archive.writestr(
            archive_info(f'{MODULE_NAME}/archipelago.json'),
            manifest_data,
        )

    print(output_path)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--output-directory',
        type=Path,
        default=ARCHIPELAGO_DIR,
    )
    arguments = parser.parse_args()
    build(arguments.output_directory)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
