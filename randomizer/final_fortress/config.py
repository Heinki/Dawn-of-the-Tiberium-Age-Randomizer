"""DTA-owned configuration, validated before purchases and native preparation."""

import re
from pathlib import PurePosixPath
from .catalogue import SIDE_COUNTRIES

DIFFICULTY_IDS = ('easy', 'normal', 'hard', 'brutal', 'extreme', 'ultimate', 'impossible')
WAVE_MULTIPLIERS = tuple(range(1, 11))


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f'{name} must be an integer >= {minimum}.')
    return value


def identifier(value, name):
    if not isinstance(value, str) or not re.fullmatch('[a-z][a-z0-9_]{0,63}', value):
        raise ValueError(f'{name} requires a lowercase identifier.')
    return value


def text(value, name):
    if not isinstance(value, str) or not value.strip() or any(c in value for c in '\r\n\0'):
        raise ValueError(f'{name} requires nonempty single-line text.')
    return value


def validate_wave_multiplier(value):
    if type(value) is not int or value not in WAVE_MULTIPLIERS:
        raise ValueError('Wave multiplier must be between x1 and x10.')
    return value


def _object(value, fields, name):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError(f'{name} requires exactly: {", ".join(fields)}.')


def _techno(value):
    if not isinstance(value, str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_]{0,22}', value):
        raise ValueError(f'Invalid DTA type ID: {value!r}.')


def _position(value):
    _object(value, ('x', 'y'), 'Position')
    integer(value['x'], 'Position x')
    integer(value['y'], 'Position y')


def _units(entries):
    if not isinstance(entries, list):
        raise ValueError('Units must be a list.')
    for unit in entries:
        _object(unit, ('type', 'count'), 'Unit')
        _techno(unit['type'])
        integer(unit['count'], 'Unit count', 1)


def stage_compositions(stage):
    return stage.get('variants', [{'id': 'default', 'units': stage.get('units', [])}])


def wave_rosters(config, difficulty):
    return config['wave_rosters']


def validate_map_definition(definition):
    identifier(definition['id'], 'Map ID')
    objective = definition['protected_building']
    _techno(objective['type'])
    _position(objective['position'])
    if 'base_strength' in objective:
        integer(objective['base_strength'], 'Objective base strength', 1)
    path = PurePosixPath(definition['source'])
    if (
        path.is_absolute()
        or '..' in path.parts
        or path.parts[:2] != ('Maps', 'Default')
        or path.name != definition['id'] + '.map'
    ):
        raise ValueError('Fortress requires an installed Default skirmish map.')
    if len(definition['camps']) != 6:
        raise ValueError('Configure exactly six camps.')
    ids = set()
    for camp in definition['camps']:
        identifier(camp['id'], 'Camp ID')
        if camp['id'] in ids:
            raise ValueError('Duplicate camp ID.')
        ids.add(camp['id'])
        _position(camp['position'])
        if len(camp['guard_positions']) != 30:
            raise ValueError('Each camp needs 30 reviewed guard cells.')
        for position in camp['guard_positions']:
            _position(position)
        cells = [camp['position'], *camp['guard_positions']]
        if len({(p['x'], p['y']) for p in cells}) != 31:
            raise ValueError('Camp guards and crate need distinct cells.')
        if type(camp['enemy_index']) is not int or camp['enemy_index'] not in range(3):
            raise ValueError('Camp owner must be one of three enemy houses.')
    text(definition['display_name'], 'Map name')
    digest = definition['source_sha256']
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('Fortress maps require a reviewed source SHA-256.')
    allied, hostile = definition['allied_waypoints'], definition['enemy_waypoints']
    active = [definition['player_waypoint'], *allied, *hostile]
    if len(allied) != 2 or len(hostile) != 3 or len(set(active)) != 6 or any(
        type(n) is not int or n not in range(8) for n in active
    ):
        raise ValueError('Fortress requires three friendly and three distinct enemy starts.')
    layouts = definition['perk_layouts']
    if set(layouts) != {str(n) for n in active}:
        raise ValueError('Every Fortress start needs a reviewed base layout.')
    for waypoint, layout in layouts.items():
        _position(layout['arrival'])
        _position(layout['controller'])
        if len(layout['army']) < 16:
            raise ValueError('Reserve sixteen starting army cells per base.')
        for position in layout['army']:
            _position(position)
        friendly = int(waypoint) in [definition['player_waypoint'], *allied]
        if len(layout['slots']) < (14 if friendly else 6):
            raise ValueError('Reserve enough production and defense slots per base.')
        for i, slot in enumerate(layout['slots']):
            _object(slot, ('x', 'y', 'width', 'height'), 'Base slot')
            _position({key: slot[key] for key in ('x', 'y')})
            width = (4 if i in (2, 4) else 2) if friendly else (3 if i < 2 else 2)
            integer(slot['width'], 'Slot width', width)
            integer(slot['height'], 'Slot height', 3 if friendly and i in (2, 4) else 2)
    if 'start_positions' in definition:
        if set(definition['start_positions']) != {str(n) for n in active}:
            raise ValueError('Review all six overridden Fortress starts together.')
        for p in definition['start_positions'].values():
            _position(p)
    clearance = definition.get('camp_clearance', {'friendly': 32, 'hostile': 40, 'camps': 32})
    _object(clearance, ('friendly', 'hostile', 'camps'), 'Camp clearance')
    for key, minimum in (('friendly', 16), ('hostile', 20), ('camps', 20)):
        integer(clearance[key], 'Camp ' + key + ' clearance', minimum)
    if 'clear_source_scripts' in definition and type(definition['clear_source_scripts']) is not bool:
        raise ValueError('clear_source_scripts must be boolean.')


def validate_static_config(config):
    """Validate the configuration contract without requiring a DTA installation."""
    required = {
        'game_id',
        'settings',
        'map',
        'difficulties',
        'wave_pressure',
        'wave_rosters',
        'milestones',
        'performance',
        'perks',
        'challenges',
        'camp_balance',
        'crate_rewards',
        'wave_priorities',
        'wave_air_support',
        'capabilities',
    }
    if not isinstance(config, dict) or set(config) - {'maps'} != required or config['game_id'] != 'dta':
        raise ValueError('Final Fortress requires a DTA-owned configuration.')
    settings = config['settings']
    for field in ('survival_seconds', 'wave_interval_seconds', 'completion_gems', 'max_wave_units'):
        integer(settings[field], field, 1)
    if settings['survival_seconds'] != 3600 or settings['wave_interval_seconds'] != 300:
        raise ValueError('DTA Fortress requires the 60-minute, five-minute delivery contract.')
    if set(config['difficulties']) != set(DIFFICULTY_IDS):
        raise ValueError('Configure all seven DTA difficulty grades.')
    for grade in config['difficulties'].values():
        if type(grade['engine_difficulty']) is not int or grade['engine_difficulty'] not in range(
            7
        ):
            raise ValueError('Invalid native Vinifera AI handicap.')
        integer(grade['starting_wave_units'], 'Opening wave', 1)
    from .maps import map_definitions

    if 'maps' in config and not isinstance(config['maps'], list):
        raise ValueError('Fortress maps must be a list.')
    maps = map_definitions(config)
    for definition in maps:
        validate_map_definition(definition)
    for field in ('id', 'display_name', 'source'):
        if len({m[field] for m in maps}) != len(maps):
            raise ValueError('Duplicate Fortress map ' + field + '.')
    if set(config['wave_rosters']) != set(SIDE_COUNTRIES):
        raise ValueError('Wave rosters must cover all four DTA factions.')
    for stages in config['wave_rosters'].values():
        if not stages or stages[0]['from_seconds'] > 300:
            raise ValueError('Missing opening wave roster.')
        for stage in stages:
            for variant in stage_compositions(stage):
                _units(variant['units'])
                if not 1 <= len(variant['units']) <= 6:
                    raise ValueError('DTA teams support six types.')
    from .perks import validate_perk
    from randomizer.dta.powers import POWER_SPEC_BY_ID

    ids = set()
    for perk in config['perks']:
        identifier(perk['id'], 'Perk ID')
        validate_perk(perk)
        unsupported = {
            'income_stacks',
            'lab_emergency_repair',
            'defense_veterancy',
        }
        for rank in perk.get('ranks', [perk]):
            if set(rank['effects']) & unsupported:
                raise ValueError('This perk is unavailable in DTA Final Fortress: ' + perk['id'])
            for field in ('support_powers_by_country', 'superweapons_by_country'):
                for country, powers in rank['effects'].get(field, {}).items():
                    for power in powers:
                        spec = POWER_SPEC_BY_ID.get(power.upper())
                        if not spec or not ({country, 'Neutral'} & set(spec['factions'])):
                            raise ValueError('Power is not available to this DTA faction: ' + power)
        if perk['id'] in ids:
            raise ValueError('Duplicate perk ID.')
        ids.add(perk['id'])
    from .challenges import definition as challenge_definition, maximum

    ids = set()
    for entry in config['challenges']:
        identifier(entry['id'], 'Challenge ID')
        challenge_definition(entry)
        maximum(entry)
        if entry['id'] in ids:
            raise ValueError('Duplicate Challenge ID.')
        ids.add(entry['id'])
    if not 3 <= config['wave_pressure']['max_active_units'] <= 480:
        raise ValueError('DTA scripted enemy population limit must be 3–480.')
    for grade in DIFFICULTY_IDS:
        integer(config['camp_balance']['guards_by_difficulty'][grade], 'Camp guards', 1)
    for reward in config['crate_rewards']:
        integer(reward['weight'], 'Crate weight', 1)
        if set(reward['units_by_country']) != set(SIDE_COUNTRIES):
            raise ValueError('Crate rosters must cover all factions.')
        for units in reward['units_by_country'].values():
            _units(units)
    return config


def validate_config(config):
    """Validate the static contract and type IDs against the installed DTA rules."""
    validate_static_config(config)
    from randomizer.dta.rules import installed_effective_sections

    installed = installed_effective_sections(enhanced=True)

    def validate_native_units(value):
        if isinstance(value, dict):
            if 'type' in value and value['type'] not in installed:
                raise ValueError('Missing installed DTA type: ' + str(value['type']))
            for child in value.values():
                validate_native_units(child)
        elif isinstance(value, list):
            for child in value:
                validate_native_units(child)

    validate_native_units(config)
    from .perks import ranks
    from randomizer.dta.rules import catalogue_by_id

    catalogue = catalogue_by_id()
    for perk in config['perks']:
        for rank in ranks(perk):
            for country, kinds in rank['effects'].get('support_technology_by_country', {}).items():
                for kind in kinds:
                    record = catalogue.get(kind)
                    if (
                        not record or country not in record['playable_owners']
                        or record['category'] not in {'vehicles', 'buildings', 'defenses'}
                    ):
                        raise ValueError(f'Unsupported {country} specialist support type: {kind}.')
    return config


def configuration_gaps(config, difficulty, wave_multiplier=1):
    validate_config(config)
    validate_wave_multiplier(wave_multiplier)
    if difficulty not in DIFFICULTY_IDS:
        return ['Choose a DTA difficulty.']
    return []


def load_config():
    from randomizer.config.static import load_static_config

    return validate_config(load_static_config('final_fortress.json'))
