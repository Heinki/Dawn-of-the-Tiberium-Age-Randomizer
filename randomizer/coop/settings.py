"""Compatibility policy for the production-only native co-op adapter."""


SAFE_SHOP_MODIFIERS = frozenset({
    'greedy', 'veteran_economy', 'poor_logistics', 'generous_command',
    'blind_choice', 'no_safety_net', 'war_economy', 'narrow_intelligence',
    'liquid_assets', 'low_tech_war', 'blockbuster_special',
})
SHARED_SHOP_MODIFIERS = frozenset({'no_safety_net', 'narrow_intelligence'})


def modifier_unavailable_reason(modifier_id):
    if modifier_id in SAFE_SHOP_MODIFIERS:
        return ''
    if modifier_id in {'support_doctrine', 'superweapon_arms_race', 'unknown_mutation'}:
        return 'Unavailable in Co-op: custom reward powers are not supported in multiplayer.'
    return (
        'Unavailable in Co-op: this modifier has no supported multiplayer '
        'implementation for both its benefits and penalties.'
    )


POWER_UNAVAILABLE_REASON = (
    'Unavailable in Co-op: custom reward powers and their buffs require '
    'separate superweapon configurations that are not supported by the current '
    'multiplayer implementation. This applies to starting loadouts and '
    'in-run purchases. Native mission powers are unchanged.'
)


def power_unavailable_reason(reward):
    if (reward.get('kind') == 'superweapon' or reward.get('dta_player_power')
            or reward.get('power_buff_type') or reward.get('dta_player_power_buff')):
        return POWER_UNAVAILABLE_REASON
    return ''


def supported_reward(reward):
    if power_unavailable_reason(reward):
        return False
    return bool(
        reward.get('dta_production_access') or reward.get('buff_type') == 'starting_credits'
        or (reward.get('kind') == 'buff' and not reward.get('dta_house_modifier')
            and (reward.get('unit') or reward.get('dta_global_clone_buff')))
    )


def safe_settings(settings, count):
    settings = dict(settings)
    settings.update({
        'coop_mode': True, 'coop_player_count': count,
        'include_superweapon_rewards': False,
        'include_secondary_superweapon_rewards': False,
        'include_aid_power_rewards': False, 'include_power_buff_rewards': False,
        'buff_allied_helpers': False, 'failure_assistance': False,
        'enabled_reward_types': ['access', 'buff'],
    })
    scaling = dict(settings.get('enemy_scaling') or {})
    scaling.update({'reward_enabled': False, 'maximum_total_buffs': 0})
    settings['enemy_scaling'] = scaling
    arsenal = dict(settings.get('arsenal') or {})
    arsenal['power_counts'] = {key: 0 for key in arsenal.get('power_counts', {})}
    settings['arsenal'] = arsenal
    return settings


