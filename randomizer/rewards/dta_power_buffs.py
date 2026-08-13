"""Reviewed DTA support-power buff definitions."""

from randomizer.dta.powers import POWER_SPEC_BY_ID


POWER_BUFF_TYPES = ({
    'id': 'recharge',
    'name': 'Rapid Charging',
    'setting_label': 'Recharge speed',
    'description': 'Reduces this power\'s recharge time by 10% per stack.',
    'maximum_stacks': 5,
}, {
    'id': 'damage',
    'name': 'Amplified Payload',
    'setting_label': 'Damage',
    'description': 'Increases supported power damage by 15% per stack.',
    'maximum_stacks': 5,
}, {
    'id': 'area',
    'name': 'Expanded Blast',
    'setting_label': 'Effect radius',
    'description': 'Increases supported power radius by 0.5 cells per stack.',
    'maximum_stacks': 5,
})


POWER_BUFF_CONFIG = {
    'recharge': {'factor_per_stack': 0.9},
    'cost': {'factor_per_stack': 1.0, 'minimum_absolute': 0},
    'area': {
        'rectangle_amount_per_stack': 0,
        'amount_per_stack': 0.5,
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
    count = max(1, min(5, int(stack_count)))
    buff_type = reward.get('power_buff_type')
    if buff_type == 'damage':
        increase = ((1.15 ** count) - 1.0) * 100.0
        return f'Damage {increase:.1f}% higher.'
    if buff_type == 'area':
        return f'Effect radius +{0.5 * count:g} cells.'
    reduction = (1.0 - (0.9 ** count)) * 100.0
    return f'Recharge time {reduction:.1f}% faster.'


def power_buff_stack_limit(_reward):
    return 5


def power_buff_type_ids(power_id=None):
    power_id = str(power_id or '').upper()
    if not power_id:
        return tuple(item['id'] for item in POWER_BUFF_TYPES)
    if power_id in POWER_SPEC_BY_ID:
        supported = ['recharge']
        if power_id in {
            'AIRSTRIKESPECIAL', 'CHEMICALSPECIAL', 'MULTISPECIAL',
            'VORTEXSPECIAL',
        }:
            supported.extend(('damage', 'area'))
        return tuple(supported)
    return ()
