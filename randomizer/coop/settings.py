def supported_reward(reward):
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


