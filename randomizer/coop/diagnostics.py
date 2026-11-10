"""Keep the last co-op map available after another mode replaces spawnmap.ini."""

import hashlib
import json
import os
from zipfile import ZipFile, ZIP_DEFLATED

from randomizer.core.version import APP_VERSION
from randomizer.maps.ini import all_section_value_maps


def save_preparation(path, mission, map_data, spawn_data):
    """Atomically retain exact map bytes and connection-free launch settings."""
    sections = all_section_value_maps(spawn_data.decode('cp1252').splitlines())
    for values in sections.values():
        for key in ('name', 'ip', 'port'):
            values.pop(key, None)
    report = {'format': 1, 'launcher_version': APP_VERSION,
              'mission_code': mission['code'], 'source_map': mission['scenario'],
              'player_count': mission['coop_player_count'],
              'map_sha256': hashlib.sha256(map_data).hexdigest(),
              'spawn_sections': sections}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'.{path.name}.{os.getpid()}.tmp')
    try:
        with ZipFile(temporary, 'w', compression=ZIP_DEFLATED) as archive:
            archive.writestr('spawnmap.ini', map_data)
            archive.writestr('preparation.json', json.dumps(report, indent=2))
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
