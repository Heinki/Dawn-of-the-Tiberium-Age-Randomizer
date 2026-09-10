"""Build the deterministic DTA APWorld on Windows, Linux, or macOS."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ARCHIPELAGO_DIR = Path(__file__).resolve().parent
MODULE_NAME = 'dta'
SOURCE_DIR = ARCHIPELAGO_DIR / 'APWorld' / MODULE_NAME
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

    output_directory = output_directory.resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f'{MODULE_NAME}.apworld'

    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest.update({
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
