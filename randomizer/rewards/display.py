"""Reward canonicalization, stacking, and human-readable display."""

import re

from .dta_definitions import (
    BUFF_EFFECTS,
    BUFF_TARGETS,
    NONTRAINABLE_UNIT_IDS,
    RETIRED_REWARD_BY_NAME,
    REWARD_ALIASES,
    REWARD_BY_BUFF_KEY,
    REWARD_BY_NAME,
    _UNIT_POLICY_CONFIG,
    capped_movement_speed,
    capped_sight_range,
    movement_speed_ceiling,
    movement_speed_stack_limit,
    sight_range_ceiling,
    sight_stack_limit,
    unit_display_label,
)
from randomizer.config.tuning import (
    REWARD_PLANNING,
    stacked_cost,
    stacked_self_heal_rate,
    stacked_weapon_damage,
    stacked_weapon_rof,
    stacking_amount,
    stacking_multiplier,
    stacking_stack_limit,
)
from randomizer.rewards.dta_power_buffs import (
    power_buff_effect_text,
    power_buff_stack_limit,
    power_buff_type_ids,
)
from randomizer.rewards.enemy_scaling import (
    enemy_effect_text,
    enemy_reward_display_name,
)

def canonical_reward(reward):
    if not isinstance(reward, dict):
        return {}
    if (
        reward.get('buff_type') == 'opportunity_fire'
        or str(reward.get('name', '')).endswith(' Run-and-Gun I')
    ):
        return {
            'name': f'{reward.get("name", "Run-and-Gun")} (retired: unsupported moving fire)',
            'description': 'Removed because this buff cannot reliably enable firing while moving.',
            'kind': 'retired', 'retired_reward': True, 'rules': {},
        }
    if reward.get('_runtime_canonical') and not reward.get('enemy_reward'):
        return reward

    reward_name = reward.get('name')
    if not reward_name:
        return reward
    reward_name = REWARD_ALIASES.get(reward_name, reward_name)

    if reward.get('enemy_reward'):
        current_enemy = REWARD_BY_NAME.get(reward_name)
        if current_enemy and current_enemy.get('enemy_reward'):
            merged = dict(current_enemy)
            for key in (
                'enemy_maximum', 'enemy_source', 'enemy_earned_from',
                'enemy_progress_tier', 'enemy_progress_threshold',
                'enemy_per_stack_percent',
                'enemy_minimum_engine_multiplier',
            ):
                if key in reward:
                    merged[key] = reward[key]
            merged['_runtime_canonical'] = True
            return merged
        return {
            'name': f'{reward_name} (retired: unverified AI reward)',
            'description': (
                'Disabled because no end-to-end hostile-AI application or '
                'launch is currently verified.'
            ),
            'kind': 'message',
            'retired_reward': True,
        }

    if reward_name in RETIRED_REWARD_BY_NAME:
        return RETIRED_REWARD_BY_NAME[reward_name]
    current_reward = REWARD_BY_NAME.get(reward_name)
    if current_reward:
        return current_reward
    if reward.get('kind') == 'superweapon' or reward.get('dta_player_power'):
        return {
            'name': f'{reward_name} (retired: unavailable DTA power)',
            'description': (
                'Disabled because this power is not part of the DTA '
                'Randomizer reward pool.'
            ),
            'kind': 'retired',
            'retired_reward': True,
        }
    if reward.get('kind') == 'buff' and reward.get('power_buff_type'):
        if reward.get('power_buff_type') not in power_buff_type_ids(
            reward.get('superweapon')
        ):
            return {
                'name': f'{reward_name} (retired: inapplicable)',
                'description': (
                    'Disabled because this power does not support that buff.'
                ),
                'rules': {},
                'factions': list(reward.get('factions') or []),
                'kind': 'retired',
                'retired_reward': True,
            }
    if reward.get('kind') == 'buff' and reward.get('buff_type'):
        if (
            reward.get('buff_type') == 'veteran'
            and str(reward.get('unit') or '').upper() in NONTRAINABLE_UNIT_IDS
        ):
            replacement = REWARD_BY_BUFF_KEY.get(
                (str(reward.get('unit') or '').upper(), 'armor')
            )
            if replacement:
                return replacement
        active_reward = REWARD_BY_BUFF_KEY.get(
            (reward.get('unit'), reward.get('buff_type'))
        )
        if active_reward:
            return active_reward
        return {
            'name': f'{reward_name} (retired: redundant or inapplicable)',
            'description': (
                'Disabled because the installed unit already has this capability '
                'or has no compatible combat weapon.'
            ),
            'rules': {},
            'factions': list(reward.get('factions') or []),
            'kind': 'retired',
            'retired_reward': True,
        }
    if reward.get('dta_production_access'):
        unit_id = str(reward.get('unit') or '').upper()
        if unit_id and unit_id not in BUFF_TARGETS:
            return {
                'name': f'{reward_name} (retired: unavailable DTA unit)',
                'description': (
                    'Disabled because this unit is not part of the DTA '
                    'Randomizer reward pool.'
                ),
                'kind': 'retired',
                'retired_reward': True,
            }
    return reward


def canonical_rewards(rewards):
    if isinstance(rewards, list):
        return [canonical_reward(reward) for reward in rewards if isinstance(reward, dict)]
    if isinstance(rewards, dict):
        return [canonical_reward(rewards)]
    return []


def check_rewards(check):
    rewards = canonical_rewards(check.get('rewards'))
    if rewards:
        return rewards
    return canonical_rewards(check.get('reward'))


def reward_names(rewards):
    names = [reward_display_name(reward) for reward in rewards]
    return ', '.join(names) if names else 'No reward'


def clamp_int(value, minimum, maximum, default):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def valid_choice(value, choices, default):
    return value if value in choices else default


HOUSE_CATEGORY_SUFFIXES = {
    'infantry': 'Infantry',
    'units': 'Units',
    'vehicles': 'Units',
    'aircraft': 'Aircraft',
    'buildings': 'Buildings',
    'defenses': 'Defenses',
}

# Only the dedicated global-production reward is house-wide. Ordinary unit
# rewards stay attached to their exact TechnoType; veterancy still needs the
# CountryType Veteran* lists because the engine exposes no per-type equivalent.
HOUSE_SCOPED_BUFF_TYPES = {'production', 'veteran'}
HOUSE_WIDE_BUFF_TYPES = {'production'}
WEAPON_STAT_BUFF_TYPES = {'damage', 'range', 'reload', 'area'}
UNIT_STAT_BUFF_TYPES = {
    'health', 'sight', 'ammo', 'passenger_capacity', 'open_topped',
    'self_healing', 'self_healing_cap', 'self_healing_rate', 'cloak',
    'sensors', 'amphibious',
}
MAP_GUARDED_BUFF_TYPES = WEAPON_STAT_BUFF_TYPES | UNIT_STAT_BUFF_TYPES
CLONE_REQUIRED_BUFF_TYPES = (
    MAP_GUARDED_BUFF_TYPES
    | {'cost', 'armor', 'speed', 'build_limit', 'building_limit'}
)


def buff_group_key(reward):
    """Keep each power-buff effect separate despite buff_type='power'."""
    if (
        reward.get('power_buff_type') == 'payload'
        and reward.get('payload_unit_id')
    ):
        return f'payload:{str(reward["payload_unit_id"]).upper()}'
    return reward.get('power_buff_type') or reward.get('buff_type')


def reward_display_name(reward):
    reward = canonical_reward(reward)
    if reward.get('enemy_reward'):
        return enemy_reward_display_name(reward)
    name = reward.get('name', 'Unknown reward')
    if reward.get('kind') == 'buff' and (
        reward.get('buff_type') or reward.get('power_buff_type')
    ):
        effect_lines = buff_effect_lines(reward, include_stack=False)
        if effect_lines:
            return effect_lines[0]
    if reward.get('kind') == 'buff' and name.endswith(' I'):
        return name[:-2]
    return name


def house_category_suffix(target):
    return HOUSE_CATEGORY_SUFFIXES.get(target.get('category', 'units'), 'Units')


def house_wide_buff_scope(reward, unit_specific_mode=False):
    """Return the sole supported global buff scope: all production time."""
    reward = canonical_reward(reward)
    if (
        reward.get('kind') != 'buff'
        or reward.get('power_buff_type')
    ):
        return None
    buff_type = str(reward.get('buff_type') or '')
    target = BUFF_TARGETS.get(str(reward.get('unit') or '').upper(), {})
    if not target or buff_type not in HOUSE_WIDE_BUFF_TYPES:
        return None
    if buff_type != 'production' or not target.get('global_production'):
        return None
    return ('All', buff_type)


def house_wide_buff_label(scope):
    suffix, buff_type = scope
    subjects = {
        'All': 'All Production',
        'Infantry': 'Infantry',
        'Units': 'Vehicles / Naval',
        'Aircraft': 'Aircraft',
        'Buildings': 'Buildings',
        'Defenses': 'Defenses',
    }
    effects = {
        'production': 'Production',
        'cost': 'Cost',
        'armor': 'Armor',
    }
    subject = subjects.get(suffix, suffix)
    effect = effects.get(buff_type, buff_type.title())
    if suffix == 'All' and buff_type == 'production':
        return subject
    return f'{subject} {effect}'


def house_wide_buff_effect_lines(
    scope,
    count=1,
    include_stack=True,
    stack_limit=None,
):
    suffix, buff_type = scope
    label = house_wide_buff_label(scope)
    count = max(1, int(count))
    if buff_type == 'production':
        multiplier = stacking_multiplier('production', count)
        text = f'{label} time {int(round((1.0 - multiplier) * 100))}% shorter'
    elif buff_type == 'cost':
        multiplier = stacking_multiplier('cost', count)
        text = f'{label} {int(round((1.0 - multiplier) * 100))}% cheaper'
    elif buff_type == 'armor':
        multiplier = stacking_multiplier('armor', count)
        text = f'{label} {int(round(((1.0 / multiplier) - 1.0) * 100))}% stronger'
    else:
        return []
    if include_stack:
        text = f'{text} ({stack_label(count, stack_limit)})'
    return [text]


def _uncached_buff_stack_limit(reward):
    reward = canonical_reward(reward)
    if reward.get('kind') != 'buff':
        return None
    if reward.get('enemy_reward'):
        try:
            return max(1, int(reward.get('enemy_maximum', 1)))
        except (TypeError, ValueError):
            return 1
    if reward.get('buff_type') == 'starting_credits':
        try:
            per_stack = max(1, int(reward['credits_per_stack']))
            maximum = max(per_stack, int(reward['maximum_credits']))
        except (KeyError, TypeError, ValueError):
            return 1
        return max(1, maximum // per_stack)
    if reward.get('power_buff_type'):
        return power_buff_stack_limit(reward)
    buff_type = reward.get('buff_type')
    if buff_type in {
        'production', 'armor', 'health', 'range', 'area', 'ammo',
    }:
        return stacking_stack_limit(buff_type)
    if buff_type == 'sight':
        return sight_stack_limit(BUFF_TARGETS.get(reward.get('unit'), {}))
    if buff_type == 'cost':
        target = BUFF_TARGETS.get(reward.get('unit'), {})
        configured = stacking_stack_limit('cost')
        base_cost = max(1, int(round(float(target.get('cost', 1)))))
        previous = base_cost
        for count in range(1, configured + 1):
            current = stacked_cost(base_cost, count)
            if current == previous:
                return max(1, count - 1)
            previous = current
        return configured
    if buff_type in {'damage', 'reload'}:
        target = BUFF_TARGETS.get(reward.get('unit'), {})
        field = 'damage' if buff_type == 'damage' else 'rof'
        minimum = 0 if buff_type == 'damage' else 1
        values = [
            int(round(float(stats[field])))
            for stats in target.get('weapons', {}).values()
            if float(stats.get(field, 0)) > minimum
        ]
        configured = stacking_stack_limit(buff_type)
        if not values:
            return configured
        calculator = (
            stacked_weapon_damage
            if buff_type == 'damage'
            else stacked_weapon_rof
        )
        final = tuple(calculator(value, configured) for value in values)
        for count in range(1, configured + 1):
            current = tuple(calculator(value, count) for value in values)
            if current == final:
                return count
        return configured
    if buff_type == 'self_healing':
        target = BUFF_TARGETS.get(reward.get('unit'), {})
        return max(1, int(target.get('self_healing_unlock_stacks', 2)))
    if buff_type == 'self_healing_cap':
        return 1
    if buff_type == 'self_healing_rate':
        target = BUFF_TARGETS.get(reward.get('unit'), {})
        configured = max(
            1, int(BUFF_EFFECTS['self_heal_rate']['stack_limit'])
        )
        base_rate = target.get('self_healing_rate') or None
        for count in range(1, configured + 1):
            if stacked_self_heal_rate(
                count, base_rate
            ) == stacked_self_heal_rate(count + 1, base_rate):
                return count
        return configured
    if buff_type == 'building_limit':
        target = BUFF_TARGETS.get(reward.get('unit'), {})
        return max(1, int(target.get('capacity_stack_limit', 4)))
    if buff_type in {'passenger_capacity', 'build_limit'}:
        return max(1, int(
            REWARD_PLANNING['buff_stack_limits'][buff_type]
        ))
    if buff_type == 'speed':
        target = BUFF_TARGETS.get(reward.get('unit'), {})
        configured = stacking_stack_limit('speed')
        if target.get('global_buff'):
            return configured
        return movement_speed_stack_limit(target) or configured
    if buff_type in {
        'open_topped', 'cloak', 'sensors', 'veteran', 'amphibious',
    }:
        return 1
    return None


_BUFF_STACK_LIMIT_BY_NAME = {}


def buff_stack_limit(reward):
    """Return immutable catalogue limits without recalculating stat curves."""
    reward = canonical_reward(reward)
    reward_name = reward.get('name')
    if reward_name and REWARD_BY_NAME.get(reward_name) is reward:
        if reward_name not in _BUFF_STACK_LIMIT_BY_NAME:
            _BUFF_STACK_LIMIT_BY_NAME[reward_name] = (
                _uncached_buff_stack_limit(reward)
            )
        return _BUFF_STACK_LIMIT_BY_NAME[reward_name]
    return _uncached_buff_stack_limit(reward)


def effective_buff_count(reward, count):
    limit = buff_stack_limit(reward)
    if limit is None:
        return count
    return min(count, limit)


def starting_credit_bonus(rewards):
    """Return capped real-credit bonus earned for every mission start."""
    total = 0
    maximum = 0
    for reward in canonical_rewards(rewards):
        if reward.get('buff_type') != 'starting_credits':
            continue
        try:
            total += max(0, int(reward['credits_per_stack']))
            maximum = max(maximum, int(reward['maximum_credits']))
        except (KeyError, TypeError, ValueError):
            continue
    return min(total, max(0, maximum))


def stack_label(count, limit=None):
    return f'{count}/{limit} stacks' if limit is not None else f'{count} stacks'


def inherited_unit_buff_rewards(rewards, unit_id):
    """Project earned army-wide effects onto a unit for display only.

    Use that unit's canonical buff definition so base stats and stack caps
    match its own clone. Never change the saved reward or grant unit access.
    """
    target = BUFF_TARGETS.get(unit_id, {})
    if not target or target.get('global_buff'):
        return []
    inherited = []
    for reward in canonical_rewards(list(rewards)):
        if reward.get('kind') != 'buff' or not reward.get('global_buff'):
            continue
        kind = reward.get('buff_type')
        source = BUFF_TARGETS.get(reward.get('unit'), {})
        applies = bool(
            reward.get('dta_global_clone_buff')
            and kind in {'production', 'cost', 'speed', 'damage', 'reload'}
        )
        if not applies:
            continue
        unit_reward = REWARD_BY_BUFF_KEY.get((unit_id, kind))
        if unit_reward is not None:
            inherited.append(unit_reward)
    return inherited


def unit_buff_counts(rewards, unit_id):
    """Combine earned copies from every source for one displayed unit."""
    rewards = canonical_rewards(list(rewards))
    inherited = inherited_unit_buff_rewards(rewards, unit_id)
    counts = {}
    for reward in [*rewards, *inherited]:
        if reward.get('kind') != 'buff' or reward.get('unit') != unit_id:
            continue
        kind = reward.get('buff_type')
        counts[kind] = effective_buff_count(reward, counts.get(kind, 0) + 1)
    return counts


def buff_effect_lines(
    reward, count=1, include_label=True, include_stack=True, *,
    buff_counts=None, multiline=False, show_base_values=True,
):
    reward = canonical_reward(reward)
    if reward.get('kind') != 'buff':
        return []

    if reward.get('enemy_reward'):
        count = effective_buff_count(reward, count)
        text = enemy_effect_text(reward, count)
        if include_label:
            text = f'AI Reward: {text}'
        if include_stack:
            text = f'{text} ({stack_label(count, buff_stack_limit(reward))})'
        return [text]

    limit = buff_stack_limit(reward)
    if reward.get('power_buff_type'):
        count = effective_buff_count(reward, count)
        prefix = (
            f'{reward.get("power_name", reward.get("superweapon", "Power"))}: '
            if include_label else ''
        )
        text = f'{prefix}{power_buff_effect_text(reward, count)}'
        if include_stack:
            text = f'{text} ({stack_label(count, limit)})'
        return [text]

    if reward.get('buff_type') == 'starting_credits':
        count = effective_buff_count(reward, count)
        amount = count * max(0, int(reward.get('credits_per_stack', 0)))
        text = f'Starting credits +{amount:,} per mission'
        if include_stack:
            text = f'{text} ({stack_label(count, limit)})'
        return [text]

    target = BUFF_TARGETS.get(reward.get('unit'), {})
    buff_type = reward.get('buff_type')
    label = target.get('label', reward.get('unit', 'Unit'))
    prefix = f'{label}: ' if include_label else ''
    count = effective_buff_count(reward, count)

    def stacked(text):
        if not include_stack or limit == 1:
            return text
        return f'{text} · {stack_label(count, limit)}'

    def number(value):
        return f'{value:,.6f}'.rstrip('0').rstrip('.')

    def value_text(label, current, base, unit=''):
        text = f'{prefix}{label} {number(current)}'
        if count and show_base_values:
            text += f' [{number(base)}]'
        return [stacked(text + unit)]

    def weapon_text(label, field, calculator, minimum=0, unit='', show_base=True):
        pairs = {}
        for weapon, stats in target.get('weapons', {}).items():
            base = float(stats.get(field, 0))
            if base <= minimum or not stats.get('buff_safe', True):
                continue
            current = calculator(base)
            pairs.setdefault((current, base if show_base else None), []).append(weapon)
        if not pairs:
            return [stacked(f'{prefix}{label}: no applicable weapon')]
        parts = []
        for (current, base), weapons in pairs.items():
            detail = number(current)
            if count and show_base and show_base_values:
                detail += f' [{number(base)}]'
            detail += unit
            if len(pairs) > 1:
                detail = f'{" / ".join(weapons)}: {detail}'
            parts.append(detail)
        if multiline and len(parts) > 1:
            return [stacked(f'{prefix}{label}') + '\n    ' + '\n    '.join(parts)]
        return [stacked(f'{prefix}{label} ' + '; '.join(parts))]

    def durability():
        counts = dict(buff_counts or {})
        counts[buff_type] = count
        for kind in ('health', 'armor'):
            other = REWARD_BY_BUFF_KEY.get((reward.get('unit'), kind))
            if other:
                counts[kind] = effective_buff_count(other, counts.get(kind, 0))
        base = max(1, int(round(float(target.get('strength', 1)))))
        health = stacking_multiplier('health', counts.get('health', 0))
        armor = stacking_multiplier('armor', counts.get('armor', 0))
        return base, max(1, int(round(base * health / armor)))

    if target.get('global_buff') and buff_type in {'cost', 'damage', 'reload'}:
        multiplier = stacking_multiplier(buff_type, count)
        if buff_type == 'reload':
            return [stacked(f'{prefix}Fire rate {round((1 / multiplier - 1) * 100)}% faster')]
        label = {'cost': 'Cost', 'damage': 'Damage', 'reload': 'Reload time'}[buff_type]
        return value_text(f'{label} multiplier', multiplier, 1, '×')

    if buff_type == 'production':
        multiplier = stacking_multiplier('production', count)
        effect = (
            'Construction time'
            if target.get('category') in {'buildings', 'defenses'}
            else 'Production time'
        )
        return [stacked(f'{prefix}{effect} {round((1 - multiplier) * 100)}% shorter')]
    if buff_type == 'cost':
        base = int(round(float(target.get('cost', 0))))
        return value_text('Cost', stacked_cost(base, count), base, ' credits')

    if buff_type == 'speed':
        if target.get('global_buff'):
            return [stacked(
                f'{prefix}Global and unit speed stacks combine, then stop at '
                'safe ceilings '
                '(infantry 8; vehicles 12; aircraft 30; naturally faster '
                'units unchanged)'
            )]
        safe_ceiling = movement_speed_ceiling(target)
        if safe_ceiling is not None:
            base_speed = int(round(float(target.get('speed', 1))))
            speed = capped_movement_speed(target, count)
            base_text = f' [{base_speed}]' if show_base_values else ''
            return [stacked(f'{prefix}Speed {speed}{base_text}')]
        multiplier = stacking_multiplier('speed', count)
        faster = int(round((multiplier - 1.0) * 100))
        return [stacked(f'{prefix}Speed {faster}% faster')]
    if buff_type == 'armor':
        base, strength = durability()
        armor = stacking_multiplier('armor', count)
        stronger = int(round(((1.0 / armor) - 1.0) * 100))
        base_text = f' [{number(base)} base]' if show_base_values else ''
        return [stacked(
            f'{prefix}Armor {stronger}% stronger; '
            f'effective HP {number(strength)}{base_text}'
        )]

    if buff_type == 'health':
        base, strength = durability()
        return value_text('Health', strength, base, ' HP')

    if buff_type == 'sight':
        base = int(round(float(target.get('sight', 0))))
        return value_text('Vision', capped_sight_range(target, count), base, ' cells')

    if buff_type == 'veteran':
        return [stacked(f'{prefix}Veteran start')]
    if buff_type in {'build_limit', 'building_limit'}:
        base_limit = int(target.get('build_limit', 1))
        subject = (
            'Simultaneous structure limit'
            if target.get('category') == 'special_buildings'
            else 'Simultaneous unit limit'
        )
        return value_text(subject, base_limit + count, base_limit)
    if buff_type == 'damage':
        return weapon_text('Damage', 'damage', lambda base: stacked_weapon_damage(base, count))

    if buff_type == 'reload':
        return weapon_text(
            'Fire rate', 'rof',
            lambda base: round((base / stacked_weapon_rof(base, count) - 1) * 100),
            minimum=1, unit='% faster', show_base=False,
        )

    if buff_type == 'range':
        return weapon_text(
            'Range', 'range', lambda base: base + stacking_amount('range', count),
            unit=' cells',
        )

    if buff_type == 'area':
        return weapon_text(
            'Area of effect', 'area_spread',
            lambda base: base + stacking_amount('area', count), unit=' cells',
        )

    if buff_type == 'ammo':
        increase = int(stacking_amount('ammo', count))
        base_ammo = int(target.get('ammo', 0))
        total_ammo = base_ammo + increase
        ammo_label = _UNIT_POLICY_CONFIG['ammo_display_labels'].get(
            reward.get('unit'), 'Ammo'
        )
        return value_text(ammo_label, total_ammo, base_ammo)
    if buff_type == 'passenger_capacity':
        base_passengers = int(target.get('passengers', 0))
        base_text = f' [{base_passengers}]' if show_base_values else ''
        return [stacked(
            f'{prefix}Passenger capacity {base_passengers + count}{base_text}'
        )]
    if buff_type == 'open_topped':
        return [stacked(f'{prefix}Passengers can fire from transport')]
    if buff_type == 'self_healing':
        unlock_stacks = int(target.get('self_healing_unlock_stacks', 2))
        rank = 'Rookie' if count >= unlock_stacks else 'Veteran'
        return [stacked(f'{prefix}Self-healing enabled from {rank} rank')]
    if buff_type == 'self_healing_cap':
        values = BUFF_EFFECTS['self_heal_cap']
        raw_base_cap = str(target.get('self_healing_cap') or '').strip()
        try:
            base_fraction = float(raw_base_cap.rstrip('%'))
            if raw_base_cap.endswith('%'):
                base_fraction /= 100.0
        except ValueError:
            base_fraction = float(values['base_fraction'])
        base_cap = int(round(base_fraction * 100))
        maximum_cap = int(round(float(values['maximum_fraction']) * 100))
        base_text = f' [{base_cap}%]' if show_base_values else ''
        return [stacked(
            f'{prefix}Self-healing cap {maximum_cap}%{base_text}'
        )]
    if buff_type == 'self_healing_rate':
        base_rate = target.get('self_healing_rate') or None
        base_seconds = stacked_self_heal_rate(0, base_rate) * 60
        tick_seconds = stacked_self_heal_rate(count, base_rate) * 60
        return value_text(
            'Self-healing tick interval', tick_seconds, base_seconds, ' seconds'
        )
    if buff_type == 'amphibious':
        return [stacked(f'{prefix}Amphibious movement enabled')]
    if buff_type == 'cloak':
        return [stacked(f'{prefix}Cloaking enabled')]
    if buff_type == 'sensors':
        sensor_range = int(round(
            target.get('sight', 5) + float(BUFF_EFFECTS['sensor_sight_bonus'])
        ))
        return [stacked(f'{prefix}Sensors {sensor_range} cells')]
    return []


def buff_effect_comparison_lines(reward, current_count, *, buff_counts=None):
    """Describe current and post-purchase effects without ambiguous base values."""
    reward = canonical_reward(reward)
    current_count = max(0, int(current_count))
    next_count = current_count + 1
    if reward.get('power_buff_type') == 'payload':
        unit_label = str(
            reward.get('payload_unit_label') or 'unit'
        ).strip()
        qualifier = 'more ' if current_count else ''
        return [
            f'Add 1 {qualifier}{unit_label} '
            f'({current_count} -> {next_count})'
        ]
    options = dict(
        include_label=False,
        include_stack=False,
        buff_counts=buff_counts,
        show_base_values=False,
    )
    next_lines = buff_effect_lines(reward, count=next_count, **options)
    if not next_lines:
        return []
    if reward.get('buff_type') == 'self_healing':
        return next_lines
    if buff_stack_limit(reward) == 1:
        return next_lines
    current_lines = buff_effect_lines(reward, count=current_count, **options)
    if len(current_lines) != len(next_lines):
        return next_lines

    def compare(current, following):
        if current == following:
            return following
        current_parts = current.split('; ')
        following_parts = following.split('; ')
        if len(current_parts) != len(following_parts):
            return f'{current} -> {following}'
        compared = []
        pattern = re.compile(r'([-+]?\d[\d,.]*)')
        for current_part, following_part in zip(
            current_parts, following_parts
        ):
            old = pattern.split(current_part)
            new = pattern.split(following_part)
            if len(old) == len(new) and old[::2] == new[::2]:
                compared.append(''.join(
                    old[index]
                    if index % 2 == 0 or old[index] == new[index]
                    else f'{old[index]} -> {new[index]}'
                    for index in range(len(old))
                ))
            else:
                compared.append(f'{current_part} -> {following_part}')
        return '\n'.join(compared)

    return [
        compare(current_line, next_line)
        for current_line, next_line in zip(current_lines, next_lines)
    ]


def reward_rule_summary(reward):
    reward = canonical_reward(reward)
    if reward.get('kind') == 'buff' and (
        reward.get('buff_type') or reward.get('power_buff_type')
    ):
        return buff_effect_lines(reward)
    if reward.get('kind') == 'superweapon':
        return ['Building-free repeating power; restored at the start of future missions.']

    summaries = []
    rules = reward.get('rules', {})
    for section, values in rules.items():
        changes = []
        for key, value in values.items():
            key_lower = key.lower()
            if key_lower == 'techlevel':
                changes.append('unlocked')
            elif key_lower == 'buildtimemultiplier':
                try:
                    multiplier = float(value)
                    delta = int(round((1.0 - multiplier) * 100))
                except (TypeError, ValueError):
                    delta = 0
                if delta > 0:
                    changes.append(f'production time {delta}% shorter')
                elif delta < 0:
                    changes.append(f'production time {abs(delta)}% longer')
                else:
                    changes.append(f'BuildTimeMultiplier={value}')
            elif key_lower in {'owner', 'requiredhouses', 'forbiddenhouses', 'prerequisiteoverride'}:
                continue
            else:
                changes.append(f'{key}={value}')

        if changes:
            summaries.append(f'{unit_display_label(section)}: {", ".join(changes)}')

    return summaries
