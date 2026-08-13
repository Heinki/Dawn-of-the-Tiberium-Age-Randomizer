"""Disabled power-buff compatibility surface for the first DTA port."""


POWER_BUFF_CONFIG = {
    'recharge': {'factor_per_stack': 1.0},
    'cost': {'factor_per_stack': 1.0, 'minimum_absolute': 0},
    'area': {
        'rectangle_amount_per_stack': 0,
        'amount_per_stack': 0,
        'direct_fields': {},
        'warhead_fields': {},
    },
    'damage': {'factor_per_stack': 1.0, 'direct_fields': {}},
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


def power_buff_effect_text(_reward, _stack_count=1):
    return ''


def power_buff_stack_limit(_reward):
    return None


def power_buff_type_ids(_power_id=None):
    return ()
