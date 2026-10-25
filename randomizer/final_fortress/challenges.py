"""Reviewed DTA effects with strictly private hostile scope."""

from randomizer.rewards.enemy_scaling import (
    ENEMY_BUFF_BY_ID,
    enemy_effect_text,
    enemy_effect_values,
)

SUPPORTED_EFFECTS = frozenset(
    {'armor', 'production', 'firepower', 'reload', 'speed', 'unit', 'powerhouse'}
)
SUPPORTED_UNIT_STATS = frozenset({'health', 'armor', 'damage', 'reload', 'range', 'speed', 'ammo'})


def definition(entry):
    result = ENEMY_BUFF_BY_ID.get(entry.get('enemy_effect_id'))
    if (
        not result
        or result['effect'] not in SUPPORTED_EFFECTS
        or result['effect'] == 'unit'
        and result.get('unit_buff_type') not in SUPPORTED_UNIT_STATS
    ):
        raise ValueError('Unsupported DTA Fortress Challenge.')
    return result


def label(entry):
    return definition(entry)['name'].removesuffix(' I')


def maximum(entry):
    return int(definition(entry)['maximum_stacks'])


def description(entry, stacks=1):
    if definition(entry)['effect'] == 'powerhouse':
        return 'Replace two ordinary ground-wave units with faction specials where space permits; Veteran attacks, unchanged living population cap.'
    return (
        enemy_effect_text(definition(entry), stacks)
        + '; hostile houses, waves and camp guards only.'
    )


def house_modifiers(challenges):
    fields = {
        'armor': 'Armor',
        'production': 'BuildTime',
        'firepower': 'Firepower',
        'reload': 'ROF',
        'speed': 'Groundspeed',
    }
    result = {}
    for entry in challenges:
        effect = definition(entry)
        if effect['effect'] in fields:
            result[fields[effect['effect']]] = str(
                enemy_effect_values(effect, entry['stacks'])['final_engine_value']
            )
    return result
