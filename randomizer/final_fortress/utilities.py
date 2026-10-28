"""Friendly Fortress utilities using DTA's existing reward eligibility and caps."""

from collections import Counter

from randomizer.config.tuning import REWARD_PLANNING, stacking_stack_limit
from randomizer.dta.clones import _unit_overrides, _weapon_overrides
from randomizer.rewards.catalogue import BUFF_TARGETS


def infrastructure_building(kind, row, *, defense=False):
    """Production and economy structures, excluding support buildings and defenses."""
    return not defense and float(row.get('Strength', '0')) > 1 and (
        row.get('Factory', '').casefold() in {
            'buildingtype', 'infantrytype', 'unittype', 'aircrafttype',
        }
        or row.get('Refinery', '').casefold() in {'yes', 'true', '1'}
        or float(row.get('Power', '0')) > 0
        or kind in {'SILO', 'RASILO'}
    )


def capped_stacks(effect, count):
    limit = stacking_stack_limit(effect)
    return min(count, limit) if limit is not None else count


def unit_updates(kind, row, effects, *, building=False, defense=False):
    updates = {}
    health = effects.get('infrastructure_health_percent', 0)
    if building and health and infrastructure_building(kind, row, defense=defense):
        updates['Strength'] = str(round(float(row['Strength']) * (100 + health) / 100))
    target = BUFF_TARGETS.get(kind)
    if building or not target:
        return updates
    allowed = target.get('allowed_buff_types', ())
    counts = Counter()
    if 'ammo' in allowed and int(row.get('Ammo', '0')) > 0:
        counts['ammo'] = capped_stacks('ammo', effects.get('ammo_stacks', 0))
    capacity = effects.get('transport_capacity_stacks', 0)
    if (
        capacity and 'passenger_capacity' in allowed
        and int(row.get('Passengers', '0')) > 0
        and row.get('Gunner', '').casefold() not in {'yes', 'true', '1'}
        and row.get('NoManualUnload', '').casefold() not in {'yes', 'true', '1'}
    ):
        counts['passenger_capacity'] = min(
            capacity, REWARD_PLANNING['buff_stack_limits']['passenger_capacity']
        )
    updates.update(_unit_overrides(row, counts, target))
    return updates


def weapon_updates(kind, weapon, row, effects):
    target = BUFF_TARGETS.get(kind, {})
    count = effects.get('targeting_stacks', 0)
    if (
        not count or target.get('category') not in {'infantry', 'vehicles', 'aircraft'}
        or 'range' not in target.get('allowed_buff_types', ())
        or not target.get('weapons', {}).get(weapon, {}).get('buff_safe', True)
    ):
        return {}
    return _weapon_overrides(row, Counter(range=capped_stacks('range', count)))
