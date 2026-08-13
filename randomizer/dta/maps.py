"""DTA campaign-map preparation and completion-log discovery."""

from pathlib import Path

from randomizer.core.paths import GAME_ROOT, SPAWN_MAP_INI
from randomizer.maps.ini import IniLines, merge_ini_section_values, read_text


DIFFICULTY_FILE_BY_VALUE = {
    0: 'Difficulty Easy.ini',
    1: 'Difficulty Medium.ini',
    2: 'Difficulty Hard.ini',
}


def _ini_sections(text):
    sections = {}
    current = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(';'):
            continue
        if line.startswith('[') and line.endswith(']'):
            current = line[1:-1].strip()
            sections.setdefault(current, {})
        elif current and '=' in raw_line:
            key, value = raw_line.split('=', 1)
            sections[current][key.strip()] = value.strip()
    return sections


def mission_source_path(scenario):
    normalized = str(scenario or '').replace('\\', '/').lstrip('/')
    source = GAME_ROOT.joinpath(*normalized.split('/'))
    if not source.is_file():
        raise FileNotFoundError(f'DTA mission map is missing: {source}')
    return source


def mission_difficulty_modifiers(mission, section_name='Normal'):
    """Read map-authored difficulty modifiers so rewards stack instead of erase."""
    source = mission_source_path(mission.get('scenario'))
    sections = _ini_sections(
        source.read_text(encoding='cp1252', errors='strict')
    )
    wanted = {
        'firepower': 'Firepower',
        'armor': 'Armor',
        'groundspeed': 'Groundspeed',
        'airspeed': 'Airspeed',
        'rof': 'ROF',
        'cost': 'Cost',
        'buildtime': 'BuildTime',
    }
    return {
        output_key: value
        for key, output_key in wanted.items()
        for source_key, value in sections.get(section_name, {}).items()
        if source_key.casefold() == key
    }


def mission_normal_modifiers(mission):
    """Backward-compatible accessor for map-authored ``[Normal]`` values."""
    return mission_difficulty_modifiers(mission, 'Normal')


def prepare_spawn_map(
    mission,
    difficulty,
    extra_rules=None,
    output_path=SPAWN_MAP_INI,
):
    """Copy one loose DTA mission, consolidate difficulty, then add safe rules."""
    source = mission_source_path(mission.get('scenario'))
    lines = IniLines(source.read_text(encoding='cp1252', errors='strict').splitlines())

    difficulty_value = int(getattr(difficulty, 'engine_value', difficulty))
    difficulty_name = DIFFICULTY_FILE_BY_VALUE.get(difficulty_value, 'Difficulty Medium.ini')
    difficulty_path = GAME_ROOT / 'INI' / 'Map Code' / difficulty_name
    if not difficulty_path.is_file():
        raise FileNotFoundError(f'DTA difficulty overlay is missing: {difficulty_path}')
    merge_ini_section_values(
        lines,
        _ini_sections(difficulty_path.read_text(encoding='cp1252', errors='strict')),
    )

    if bool(getattr(difficulty, 'apply_normal_modifiers', False)):
        normal_modifier_path = (
            source.parent
            / 'NormalDifficultyModifiers'
            / f'{source.stem}.ini'
        )
        if normal_modifier_path.is_file():
            merge_ini_section_values(
                lines,
                _ini_sections(normal_modifier_path.read_text(
                    encoding='cp1252', errors='strict'
                )),
            )

    if extra_rules:
        merge_ini_section_values(lines, extra_rules)
    merge_ini_section_values(lines, {
        'Basic': {
            'EndOfGame': 'true',
            'SkipScore': 'false',
        },
    })

    output_path = Path(output_path)
    output_path.write_text(
        '\r\n'.join(lines) + '\r\n',
        encoding='cp1252',
        newline='',
    )
    return {
        'mission_code': mission.get('code'),
        'scenario': 'spawnmap.ini',
        'source_scenario': mission.get('scenario'),
        'generated_map': str(output_path),
        'root_map': str(output_path),
        'markers': {},
        'seen': set(),
        'offset': 0,
        'dta': True,
        'difficulty_label': getattr(difficulty, 'label', ''),
        'difficulty_engine_value': difficulty_value,
        'normal_difficulty_modifiers': bool(
            getattr(difficulty, 'apply_normal_modifiers', False)
        ),
    }


def newest_debug_log(debug_directory):
    directory = Path(debug_directory)
    if not directory.is_dir():
        return None
    logs = [path for path in directory.glob('*.LOG') if path.is_file()]
    if not logs:
        logs = [path for path in directory.glob('*.log') if path.is_file()]
    return max(logs, key=lambda path: path.stat().st_mtime_ns) if logs else None


def score_screen_loaded(line):
    return line.lstrip().startswith('ScoreScreen: Loaded ')
