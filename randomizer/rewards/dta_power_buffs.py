"""Reviewed DTA support-power buff definitions."""

from randomizer.dta.powers import POWER_SETTINGS, POWER_SPEC_BY_ID
from randomizer.config.tuning import stacking_multiplier, stacking_stack_limit


POWER_BUFF_TYPES = ({
    'id': 'recharge',
    'name': 'Rapid Charging',
    'setting_label': 'Recharge speed',
    'description': 'Reduces this power\'s recharge time by 10% per stack.',
    'maximum_stacks': 40,
}, {
    'id': 'cost',
    'name': 'Efficient Construction',
    'setting_label': 'Provider building cost',
    'description': 'Reduces this power provider building\'s cost by 20% per stack.',
    'maximum_stacks': stacking_stack_limit('cost'),
}, {
    'id': 'production',
    'name': 'Rapid Construction',
    'setting_label': 'Provider construction speed',
    'description': 'Reduces this power provider building\'s construction time by 15% per stack.',
    'maximum_stacks': stacking_stack_limit('production'),
}, {
    'id': 'capacity',
    'name': 'Additional Launch Site',
    'setting_label': 'Provider building capacity',
    'description': (
        'Allows one additional provider building per stack. Every active '
        'building supplies one independently charging use of the power.'
    ),
    'maximum_stacks': int(
        POWER_SETTINGS['provider_capacity_maximum_stacks']
    ),
}, {
    'id': 'damage',
    'name': 'Amplified Payload',
    'setting_label': 'Damage',
    'description': 'Increases supported power damage by 15% per stack.',
    'maximum_stacks': 10,
}, {
    'id': 'area',
    'name': 'Expanded Blast',
    'setting_label': 'Effect radius',
    'description': (
        'Increases supported power radius by '
        f'{POWER_SETTINGS["area_cells_per_stack"]:g} cell per stack.'
    ),
    'maximum_stacks': 40,
}, {
    'id': 'payload',
    'name': 'Expanded Deployment',
    'setting_label': 'Delivered units',
    'description': (
        'Adds one infantry unit to each Paratroopers deployment. Variants name '
        'the delivered unit: standard infantry, Soviet Flamethrower, Chem '
        'Warrior, Soviet Rocket Soldier, Shock Trooper, or Medic.'
    ),
    'maximum_stacks': int(POWER_SETTINGS['payload_maximum_stacks']),
})


POWER_BUFF_CONFIG = {
    'recharge': {'factor_per_stack': 0.9},
    'cost': {'factor_per_stack': 1.0, 'minimum_absolute': 0},
    'capacity': {'amount_per_stack': 1},
    'area': {
        'rectangle_amount_per_stack': 0,
        'amount_per_stack': float(POWER_SETTINGS['area_cells_per_stack']),
        'direct_fields': {},
        'warhead_fields': {},
    },
    'damage': {'factor_per_stack': 1.15, 'direct_fields': {}},
    'duration': {
        'factor_per_stack': 1.0,
        'direct_fields': {},
        'warhead_fields': {},
    },
    'vision': {'amount_per_stack': 0, 'power_fields': {}},
    'payload': {
        'unit_delivery_power_ids': (),
        'paradrop_power_ids': (),
        'drop_pod_power_ids': (),
        'spy_plane_power_ids': (),
        'drop_pod_type_weight_additions': {},
    },
}


def power_buff_effect_text(reward, stack_count=1):
    limit = power_buff_stack_limit(reward)
    count = max(1, min(limit, int(stack_count)))
    buff_type = reward.get('power_buff_type')
    if buff_type == 'damage':
        increase = ((1.15 ** count) - 1.0) * 100.0
        return f'Damage {increase:.1f}% higher.'
    if buff_type == 'area':
        amount = float(POWER_SETTINGS['area_cells_per_stack']) * count
        return f'Effect radius +{amount:g} cells.'
    if buff_type == 'cost':
        reduction = (1.0 - stacking_multiplier('cost', count)) * 100.0
        return f'Provider building cost {reduction:.1f}% cheaper.'
    if buff_type == 'production':
        reduction = (1.0 - stacking_multiplier('production', count)) * 100.0
        return f'Provider construction time {reduction:.1f}% shorter.'
    if buff_type == 'capacity':
        total = count + 1
        return (
            f'Provider limit {total} buildings; up to {total} independently '
            'charging uses.'
        )
    if buff_type == 'payload':
        label_key = (
            'payload_unit_label' if count == 1 else 'payload_unit_plural'
        )
        unit_label = str(reward.get(label_key) or '').strip()
        if unit_label:
            return f'Each deployment adds {count} {unit_label}.'
        return f'Delivered infantry +{count}.'
    reduction = (1.0 - (0.9 ** count)) * 100.0
    return f'Recharge time {reduction:.1f}% faster.'


def power_buff_stack_limit(reward):
    explicit = reward.get('maximum_stacks')
    if explicit is not None:
        return max(1, int(explicit))
    buff_type = str(reward.get('power_buff_type') or '')
    return next(
        (
            int(definition['maximum_stacks'])
            for definition in POWER_BUFF_TYPES
            if definition['id'] == buff_type
        ),
        40,
    )


def power_buff_type_ids(power_id=None):
    power_id = str(power_id or '').upper()
    if not power_id:
        return tuple(item['id'] for item in POWER_BUFF_TYPES)
    spec = POWER_SPEC_BY_ID.get(power_id)
    return tuple(spec.get('buffs', ())) if spec else ()
