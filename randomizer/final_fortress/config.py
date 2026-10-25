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
    if not isinstance(config, dict) or set(config) != required or config['game_id'] != 'dta':
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
    definition = config['map']
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
        or str(path) != 'Maps/Default/king_of_the_hills_extreme.map'
    ):
        raise ValueError('DTA Fortress supports King of the Hills Extreme only.')
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

    installed = installed_effective_sections()

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
