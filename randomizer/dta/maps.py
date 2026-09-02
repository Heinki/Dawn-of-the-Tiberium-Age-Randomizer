"""DTA campaign-map preparation and completion-log discovery."""

from pathlib import Path

from randomizer.core.paths import GAME_ROOT, SPAWN_MAP_INI
from randomizer.dta.rules import effective_section, ini_sections
from randomizer.maps.hooks import unique_section_key
from randomizer.maps.ini import (
    IniLines,
    action_group_tokens,
    append_section_entry,
    merge_ini_section_values,
    read_text,
)


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
    components = [part for part in normalized.split('/') if part not in {'', '.'}]
    if not components or '..' in components:
        raise FileNotFoundError(f'Invalid DTA mission map path: {scenario}')

    source = GAME_ROOT.joinpath(*components)
    if not source.is_file():
        # Battle.ini uses Windows-style case-insensitive paths, while DTA's
        # installed loose maps are commonly all lowercase on Linux.
        source = GAME_ROOT
        try:
            for component in components:
                exact = source / component
                if exact.exists():
                    source = exact
                    continue
                folded = component.casefold()
                source = next(
                    child for child in source.iterdir()
                    if child.name.casefold() == folded
                )
        except (OSError, StopIteration):
            source = GAME_ROOT.joinpath(*components)
    if not source.is_file():
        raise FileNotFoundError(f'DTA mission map is missing: {source}')
    return source


def mission_source_lines(scenario):
    """Read one loose DTA mission without using the legacy MIX extractor."""
    return IniLines(
        mission_source_path(scenario).read_text(
            encoding='cp1252', errors='strict'
        ).splitlines()
    )


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


def preserve_collateral_damage_coefficients(lines):
    """Repeat installed death-damage scaling in map-local Techno sections.

    The engine resets CollateralDamageCoefficient to 1.0 whenever a TechnoType
    is mentioned by a map, even if the map only overrides an unrelated field.
    """
    map_sections = _ini_sections('\n'.join(lines))
    installed = ini_sections(GAME_ROOT / 'INI' / 'Rules.ini')
    safeguards = {}
    for section, local_values in map_sections.items():
        installed_values = effective_section(installed, section)
        if not installed_values:
            continue
        effective_values = dict(installed_values)
        effective_values.update(local_values)
        folded = {
            str(key).casefold(): value
            for key, value in effective_values.items()
        }
        local_keys = {str(key).casefold() for key in local_values}
        coefficient = folded.get('collateraldamagecoefficient')
        if (
            str(folded.get('explodes', '')).casefold() in {'yes', 'true', '1'}
            and coefficient not in (None, '')
            and 'collateraldamagecoefficient' not in local_keys
        ):
            safeguards.setdefault(section, {})[
                'CollateralDamageCoefficient'
            ] = coefficient
    if safeguards:
        merge_ini_section_values(lines, safeguards)
    return safeguards


def player_starting_credit_rules(lines, player_house, credit_bonus):
    """Add a real-credit bonus to the authored player House balance."""
    try:
        credit_bonus = max(0, int(credit_bonus))
    except (TypeError, ValueError):
        credit_bonus = 0
    report = {
        'player_house': str(player_house or ''),
        'credit_bonus': credit_bonus,
        'authored_credits': 0,
        'launch_credits': 0,
        'applied': False,
        'error': '',
    }
    if not credit_bonus:
        return {}, report
    if not player_house:
        report['error'] = 'missing_player_house'
        return {}, report

    sections = _ini_sections('\n'.join(lines))
    house_name = next(
        (
            section for section in sections
            if section.casefold() == str(player_house).casefold()
        ),
        '',
    )
    if not house_name:
        report['error'] = 'missing_player_house_section'
        return {}, report
    authored_value = next(
        (
            value for key, value in sections[house_name].items()
            if str(key).casefold() == 'credits'
        ),
        '0',
    )
    try:
        authored_units = int(str(authored_value or '0').strip())
    except (TypeError, ValueError):
        report['error'] = f'invalid_authored_credits:{authored_value!r}'
        return {}, report

    # DTA House Credits are stored in hundreds by the map format.
    authored_credits = authored_units * 100
    launch_credits = authored_credits + credit_bonus
    report.update({
        'authored_credits': authored_credits,
        'launch_credits': launch_credits,
        'applied': True,
    })
    return {house_name: {'Credits': str(launch_credits // 100)}}, report


def prepare_spawn_map(
    mission,
    difficulty,
    extra_rules=None,
    power_actions=(),
    power_house='',
    output_path=SPAWN_MAP_INI,
):
    """Copy one loose DTA mission, consolidate difficulty, then add safe rules."""
    source = mission_source_path(mission.get('scenario'))
    lines = mission_source_lines(mission.get('scenario'))

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
    collateral_safeguards = preserve_collateral_damage_coefficients(lines)
    power_actions = [list(action) for action in power_actions or ()]
    power_grant_triggers = []
    if power_actions and power_house:
        for chunk_index in range(0, len(power_actions), 20):
            chunk = power_actions[chunk_index:chunk_index + 20]
            trigger_id = unique_section_key(
                lines, ('Events', 'Actions', 'Triggers'), 'DTAPW'
            )
            tag_id = unique_section_key(lines, ('Tags',), 'DTAPT')
            delay = 1 + chunk_index // 20
            name = f'DTA Randomizer Earned Powers {delay}'
            append_section_entry(lines, 'Events', trigger_id, f'1,13,0,{delay}')
            append_section_entry(
                lines,
                'Actions',
                trigger_id,
                f'{len(chunk)},{",".join(action_group_tokens(chunk))}',
            )
            append_section_entry(
                lines,
                'Triggers',
                trigger_id,
                f'{power_house},<none>,{name},0,1,1,1,0',
            )
            append_section_entry(lines, 'Tags', tag_id, f'0,{name} 1,{trigger_id}')
            power_grant_triggers.append(trigger_id)
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
        'power_grant_triggers': power_grant_triggers,
        'collateral_damage_safeguards': collateral_safeguards,
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
