"""Reviewed AI-only rewards and deterministic completion planning."""

import random
import re

from randomizer.config.static import load_static_config
from randomizer.config.tuning import stacking_multiplier


_CONFIG = load_static_config('rewards/enemy_scaling.json')
ENEMY_SCALING_DEFAULTS = dict(_CONFIG['defaults'])

def _tier_unit_buff_definitions():
    definitions = []
    for tier in (1, 2, 3):
        for template in _CONFIG.get('tier_unit_buff_templates', ()):
            definition = dict(template)
            definition.update({
                'id': f'tier{tier}_{template["id"]}',
                'name': f'Enemy T{tier} {template["name"]} I',
                'type': template['name'],
                'category': f'Tier {tier} units',
                'effect': 'unit',
                'tier': tier,
            })
            definitions.append(definition)
    return definitions


ENEMY_BUFF_DEFINITIONS = tuple(
    [dict(item) for item in _CONFIG['buffs']]
    + _tier_unit_buff_definitions()
)
ENEMY_BUFF_BY_ID = {
    str(item['id']): item for item in ENEMY_BUFF_DEFINITIONS
}
SUPPORTED_AI_REWARD_IDS = frozenset(
    definition['id']
    for definition in ENEMY_BUFF_DEFINITIONS
    if definition.get('effect') in {
        'armor', 'production', 'firepower', 'reload', 'speed', 'unit',
        'ion_cannon', 'team_delays', 'reinforcement_size',
        'production_activation', 'powerhouse',
    }
)


def _enemy_group_ids(*, effects=(), types=()):
    return tuple(
        definition['id']
        for definition in ENEMY_BUFF_DEFINITIONS
        if (
            definition.get('effect') in effects
            or definition.get('type') in types
        )
    )


ENEMY_BUFF_GROUP_DEFINITIONS = (
    {
        'id': 'stat_bonuses',
        'label': 'AI unit durability / mobility',
        'effect_ids': tuple(
            definition['id'] for definition in ENEMY_BUFF_DEFINITIONS
            if definition.get('effect') in {'armor', 'speed'}
            or (
                definition.get('effect') == 'unit'
                and definition.get('unit_buff_type')
                in {'health', 'armor', 'speed', 'sight', 'ammo'}
            )
        ),
    },
    {
        'id': 'weapon_bonuses',
        'label': 'AI unit weapon buffs',
        'effect_ids': tuple(
            definition['id'] for definition in ENEMY_BUFF_DEFINITIONS
            if definition.get('effect') in {'firepower', 'reload'}
            or (
                definition.get('effect') == 'unit'
                and definition.get('unit_buff_type')
                in {'damage', 'range', 'reload'}
            )
        ),
    },
    {
        'id': 'production',
        'label': 'AI production-speed bonuses',
        'effect_ids': _enemy_group_ids(effects={'production'}),
    },
    {
        'id': 'strategic_pressure',
        'label': 'AI strategic pressure',
        'effect_ids': _enemy_group_ids(effects={
            'ion_cannon', 'team_delays', 'reinforcement_size',
            'production_activation', 'powerhouse',
        }),
    },
)
UNSUPPORTED_AI_REWARD_REASONS = (
    'AI unit unlocks skipped: generic production changes can replace '
    'story-critical unit identities or alter mission scripts.',
    'Generic AI support-power unlocks skipped: only the reviewed '
    'Ion Thunderbolt mission trigger is supported.',
)
MAX_AI_REWARDS_PER_COMPLETION = 10
MAX_ENEMY_BUFF_CAP = 100
ENEMY_STACK_MODEL_VERSION = 2


def _bounded_int(value, minimum, maximum, default):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = int(default)
    return max(minimum, min(maximum, number))


def normalize_enemy_scaling_settings(value):
    """Normalize seed-frozen AI reward settings."""
    source = value if isinstance(value, dict) else {}
    try:
        stack_model_version = max(
            0, int(source.get('stack_model_version', 1))
        )
    except (TypeError, ValueError):
        stack_model_version = 1
    legacy_basis = str(source.get('progress_basis', 'objectives')).lower()
    legacy_enabled = bool(source.get('progress_enabled', False))
    legacy_count = source.get('progress_rewards_per_tier', 1)
    objective_default = ENEMY_SCALING_DEFAULTS[
        'rewards_per_completed_objective'
    ]
    mission_default = ENEMY_SCALING_DEFAULTS[
        'rewards_per_completed_mission'
    ]
    objective_source = source.get('rewards_per_completed_objective')
    mission_source = source.get('rewards_per_completed_mission')
    if objective_source is None:
        objective_source = (
            legacy_count if legacy_enabled and legacy_basis == 'objectives'
            else objective_default
        )
    if mission_source is None:
        mission_source = (
            legacy_count if legacy_enabled and legacy_basis == 'missions'
            else mission_default
        )
    allowed_source = source.get(
        'allowed_buff_ids', ENEMY_SCALING_DEFAULTS['allowed_buff_ids']
    )
    if not isinstance(allowed_source, (list, tuple, set)):
        allowed_source = ENEMY_SCALING_DEFAULTS['allowed_buff_ids']
    allowed_values = {str(item) for item in allowed_source}
    allowed = [
        buff_id for buff_id in ENEMY_BUFF_BY_ID
        if buff_id in SUPPORTED_AI_REWARD_IDS
        and ('*' in allowed_values or buff_id in allowed_values)
    ]
    caps_source = source.get('caps')
    if not isinstance(caps_source, dict):
        caps_source = ENEMY_SCALING_DEFAULTS['caps']
    caps = {}
    for buff_id, definition in ENEMY_BUFF_BY_ID.items():
        hard_maximum = int(definition['maximum_stacks'])
        raw_cap = caps_source.get(
            buff_id,
            ENEMY_SCALING_DEFAULTS['caps'].get(buff_id, hard_maximum),
        )
        # Version 1 exposed no cap controls and shipped a fixed value of 3.
        # Upgrade that legacy default to the corrected five-stack model while
        # preserving explicit lower values such as 0, 1, or 2.
        if stack_model_version < ENEMY_STACK_MODEL_VERSION and raw_cap == 3:
            raw_cap = hard_maximum
        configured = _bounded_int(
            raw_cap,
            0,
            min(MAX_ENEMY_BUFF_CAP, hard_maximum),
            hard_maximum,
        )
        caps[buff_id] = configured
    return {
        'stack_model_version': ENEMY_STACK_MODEL_VERSION,
        'reward_enabled': bool(source.get(
            'reward_enabled', ENEMY_SCALING_DEFAULTS['reward_enabled']
        )),
        'rewards_per_completed_objective': _bounded_int(
            objective_source,
            0,
            MAX_AI_REWARDS_PER_COMPLETION,
            objective_default,
        ),
        'rewards_per_completed_mission': _bounded_int(
            mission_source,
            0,
            MAX_AI_REWARDS_PER_COMPLETION,
            mission_default,
        ),
        'allowed_buff_ids': allowed,
        'caps': caps,
    }


def _enemy_power_clone_id(superweapon):
    short = re.sub(r'Special$', '', str(superweapon), flags=re.IGNORECASE)
    return ('MORE' + re.sub(r'[^A-Za-z0-9_]', '', short))[:24]


def build_enemy_reward_pool(power_rewards):
    """Build canonical enemy rewards, reusing reviewed portable power plans."""
    powers = {
        str(reward.get('superweapon') or '').upper(): reward
        for reward in power_rewards
    }
    rewards = []
    for definition in ENEMY_BUFF_DEFINITIONS:
        power_id = str(definition.get('superweapon') or '').upper()
        reward = dict(powers.get(power_id, {})) if power_id else {}
        reward.update({
            'name': definition['name'],
            'description': enemy_effect_text(definition, 1),
            'rules': {},
            'factions': ['Neutral'],
            'kind': 'buff',
            'buff_type': 'enemy',
            'enemy_reward': True,
            'enemy_effect_id': definition['id'],
            'enemy_type': definition['type'],
            'enemy_category': definition['category'],
            'enemy_effect': definition['effect'],
            'tier': int(definition.get('tier', 0)),
            'unit_buff_type': definition.get('unit_buff_type'),
            'enemy_country_suffix': definition.get('country_suffix', ''),
            'enemy_per_stack_percent': float(
                definition.get('per_stack_percent', 0)
            ),
            'enemy_per_stack_value': float(definition.get(
                'per_stack_value', definition.get('per_stack_percent', 0)
            )),
            'enemy_value_unit': str(definition.get('value_unit', '%')),
            'enemy_minimum_engine_multiplier': float(
                definition.get('minimum_engine_multiplier', 0.001)
            ),
            'enemy_maximum': int(definition['maximum_stacks']),
        })
        if power_id:
            reward['superweapon'] = definition['superweapon']
            reward['enemy_ai_targeting'] = definition['ai_targeting']
            reward['enemy_superweapon_clone'] = _enemy_power_clone_id(
                definition['superweapon']
            )
        rewards.append(reward)
    return rewards


def configured_enemy_reward(reward, settings):
    """Return one seed-settings copy, or None when disabled/invalid."""
    if not reward.get('enemy_reward'):
        return reward
    settings = normalize_enemy_scaling_settings(settings)
    effect_id = str(reward.get('enemy_effect_id') or '')
    cap = settings['caps'].get(effect_id, 0)
    if effect_id not in settings['allowed_buff_ids'] or cap <= 0:
        return None
    configured = dict(reward)
    configured['enemy_maximum'] = cap
    configured['_runtime_canonical'] = True
    return configured


def enemy_effect_values(reward, count=1, base_engine_value=1.0):
    """Return exact cumulative engine and human-facing AI bonus values."""
    effect_id = str(reward.get('enemy_effect_id') or reward.get('id') or '')
    definition = ENEMY_BUFF_BY_ID.get(effect_id, reward)
    maximum = max(1, int(
        reward.get('enemy_maximum', definition.get('maximum_stacks', 1))
    ))
    count = min(maximum, max(1, int(count)))
    per_stack = max(0.0, float(
        reward.get(
            'enemy_per_stack_percent',
            definition.get('per_stack_percent', 0),
        )
    ))
    per_stack_value = max(0.0, float(reward.get(
        'enemy_per_stack_value', definition.get('per_stack_value', per_stack)
    )))
    try:
        base_engine_value = float(base_engine_value)
    except (TypeError, ValueError):
        base_engine_value = 1.0
    base_engine_value = max(0.001, base_engine_value)
    effect = definition.get('effect')
    fraction = per_stack / 100.0
    if effect == 'armor':
        # Country Armor*Mult is armor strength. Convert the configured human
        # bonus to its reciprocal received-damage multiplier, then back to the
        # engine value explicitly so UI and INI use the same calculation.
        armor_strength = 1.0 + (fraction * count)
        received_damage = 1.0 / max(0.001, armor_strength)
        relative_engine = 1.0 / received_damage
    elif effect in {
        'production', 'ion_cannon', 'team_delays', 'production_activation',
    }:
        minimum = max(0.001, float(reward.get(
            'enemy_minimum_engine_multiplier',
            definition.get('minimum_engine_multiplier', 0.001),
        )))
        relative_engine = max(minimum, 1.0 - (fraction * count))
        received_damage = None
    elif effect in {'firepower', 'speed'}:
        relative_engine = 1.0 + (fraction * count)
        received_damage = None
    elif effect == 'reload':
        minimum = max(0.001, float(reward.get(
            'enemy_minimum_engine_multiplier',
            definition.get('minimum_engine_multiplier', 0.001),
        )))
        relative_engine = max(minimum, 1.0 - (fraction * count))
        received_damage = None
    elif effect == 'unit':
        buff_type = definition.get('unit_buff_type')
        if buff_type in {'health', 'damage', 'speed'}:
            relative_engine = stacking_multiplier(buff_type, count)
        elif buff_type == 'armor':
            relative_engine = 1.0 / max(
                0.001, stacking_multiplier('armor', count)
            )
        elif buff_type == 'reload':
            relative_engine = stacking_multiplier('reload', count)
        else:
            relative_engine = 1.0
        received_damage = None
    else:
        relative_engine = 1.0
        received_damage = None
    final_engine = max(0.001, base_engine_value * relative_engine)
    # Map multipliers are serialized to three decimals. Make the receipt and
    # UI report the exact value the engine receives, not an unrounded ideal.
    final_engine = float(f'{final_engine:.3f}')
    relative_applied = final_engine / base_engine_value
    displayed = (
        (relative_applied - 1.0) * 100.0
        if effect in {'armor', 'firepower', 'speed'}
        or (
            effect == 'unit'
            and definition.get('unit_buff_type')
            in {'health', 'damage', 'speed', 'armor'}
        )
        else (1.0 - relative_applied) * 100.0
        if effect in {
            'production', 'reload', 'ion_cannon', 'team_delays',
            'production_activation',
        }
        or (
            effect == 'unit'
            and definition.get('unit_buff_type') == 'reload'
        )
        else 0.0
    )
    return {
        'per_stack_value': per_stack_value,
        'current_stacks': count,
        'maximum_stacks': maximum,
        'base_engine_value': base_engine_value,
        'relative_engine_value': relative_applied,
        'final_engine_value': final_engine,
        'damage_received_multiplier': received_damage,
        'displayed_percentage': max(0, int(round(displayed))),
    }


def enemy_effect_text(reward, count=1, base_engine_value=1.0):
    """Describe the exact cumulative effect applied to the generated map."""
    effect_id = str(reward.get('enemy_effect_id') or reward.get('id') or '')
    definition = ENEMY_BUFF_BY_ID.get(effect_id, reward)
    values = enemy_effect_values(reward, count, base_engine_value)
    category = definition.get('category', 'forces')
    effect = definition.get('effect')
    if effect == 'armor':
        return f'{category} Armor {values["displayed_percentage"]}% stronger'
    if effect == 'production':
        return (
            f'{category} Production '
            f'{values["displayed_percentage"]}% faster'
        )
    if effect == 'firepower':
        return f'{category} Damage +{values["displayed_percentage"]}%'
    if effect == 'reload':
        return f'{category} Reload delay {values["displayed_percentage"]}% shorter'
    if effect == 'speed':
        return f'{category} Speed +{values["displayed_percentage"]}%'
    if effect == 'ion_cannon':
        cooldown = max(150, int(round(600 * values['relative_engine_value'])))
        return f'{category} fires an Ion Cannon every {cooldown / 60:g} minutes'
    if effect == 'team_delays':
        return (
            f'{category} creation delay '
            f'{values["displayed_percentage"]}% shorter'
        )
    if effect == 'reinforcement_size':
        return f'{category} gain +{int(count)} units per scripted team'
    if effect == 'production_activation':
        return (
            f'{category} elapsed delays '
            f'{values["displayed_percentage"]}% shorter'
        )
    if effect == 'powerhouse':
        return f'{category} gain one faction-specific special unit'
    if effect == 'unit':
        buff_type = definition.get('unit_buff_type')
        value = definition.get('per_stack_value', 0) * int(count)
        if buff_type == 'health':
            detail = f'Health +{values["displayed_percentage"]}%'
        elif buff_type == 'armor':
            detail = f'Armor {values["displayed_percentage"]}% stronger'
        elif buff_type == 'speed':
            detail = f'Speed +{values["displayed_percentage"]}%'
        elif buff_type == 'damage':
            detail = f'Damage +{values["displayed_percentage"]}%'
        elif buff_type == 'reload':
            detail = f'Reload delay {values["displayed_percentage"]}% shorter'
        elif buff_type == 'sight':
            detail = f'Sight +{value:g} cells'
        elif buff_type == 'range':
            detail = f'Range +{value:g} cells'
        elif buff_type == 'ammo':
            detail = f'Ammo +{value:g}'
        else:
            detail = definition.get('name', 'stronger')
        return f'{category} {detail}'
    if effect == 'power':
        return f'{definition.get("name", "AI power")} unlocked for hostile AI'
    return definition.get('name', 'Hostile AI strengthened')


def enemy_reward_display_name(reward, count=1):
    values = enemy_effect_values(reward, count)
    return (
        f'AI Reward: Enemy {enemy_effect_text(reward, count)} '
        f'(Stack {values["current_stacks"]}/{values["maximum_stacks"]})'
    )


def enemy_progress_events(mission_codes, mission_checks):
    """Return deterministic objective/victory completion slots."""
    events = []
    objective_index = 0
    mission_index = 0
    for code in mission_codes:
        checks = mission_checks.get(code, [])
        for check in checks:
            if not isinstance(check, dict) or check.get('id') == 'victory':
                continue
            objective_index += 1
            events.append({
                'basis': 'objectives',
                'event_index': objective_index,
            })
        if any(
            isinstance(check, dict) and check.get('id') == 'victory'
            for check in checks
        ):
            mission_index += 1
            events.append({
                'basis': 'missions',
                'event_index': mission_index,
            })
    return events


def plan_enemy_progress_rewards(
    seed,
    settings,
    reward_pool,
    events=(),
    initial_rewards=(),
):
    """Roll seed-fixed completion rewards within the supplied planning caps."""
    settings = normalize_enemy_scaling_settings(settings)
    objective_count = settings['rewards_per_completed_objective']
    mission_count = settings['rewards_per_completed_mission']
    if objective_count <= 0 and mission_count <= 0:
        return []
    configured = [
        candidate
        for reward in reward_pool
        if reward.get('enemy_reward')
        if (candidate := configured_enemy_reward(reward, settings)) is not None
    ]
    rng = random.Random(f'{seed}:ai-completion-rewards')
    counts = {}
    for reward in initial_rewards or ():
        if not isinstance(reward, dict) or not reward.get('enemy_reward'):
            continue
        effect_id = str(reward.get('enemy_effect_id') or '')
        if effect_id:
            counts[effect_id] = counts.get(effect_id, 0) + 1
    plan = []
    count_by_basis = {
        'objectives': objective_count,
        'missions': mission_count,
    }
    for event in events or ():
        if not isinstance(event, dict):
            continue
        basis = str(event.get('basis') or '')
        event_index = int(event.get('event_index', 0))
        if basis not in count_by_basis or event_index <= 0:
            continue
        for _draw in range(count_by_basis[basis]):
            candidates = [
                reward for reward in configured
                if counts.get(reward['enemy_effect_id'], 0)
                < int(reward['enemy_maximum'])
            ]
            if not candidates:
                break
            reward = dict(rng.choice(candidates))
            effect_id = reward['enemy_effect_id']
            counts[effect_id] = counts.get(effect_id, 0) + 1
            plan.append({
                'basis': basis,
                'event_index': event_index,
                'reward': reward,
            })
    return plan


def progress_plan_rewards(plan):
    """Return canonical rewards reserved by a completion plan."""
    return [
        entry['reward'] for entry in (plan or ())
        if isinstance(entry, dict) and isinstance(entry.get('reward'), dict)
    ]
