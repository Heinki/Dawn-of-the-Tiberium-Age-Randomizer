"""Native cooperative map preparation with shared, production-only rewards."""

import hashlib

from randomizer.dta.clones import unit_specific_buff_rules
from randomizer.dta.maps import preserve_collateral_damage_coefficients
from randomizer.dta.rules import PLAYABLE_FACTIONS
from randomizer.maps.ini import IniLines, append_section_entry
from randomizer.maps.hooks import unique_section_key

from .catalogue import inherited_sections, merge, native_options, resolve_path
from .feature import require_enabled


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


def prepare_map(root, mission, rewards, difficulty, *, settings=None, credit_bonus=0):
    require_enabled()
    verify_dependencies(root, mission)
    source = resolve_path(root, mission['scenario'])
    sections = inherited_sections(root, source)
    spawn_settings, overlays = native_options(root, sections)
    requested = str(getattr(difficulty, 'label', difficulty))
    choices = [('Easy', 2), ('Medium', 1), ('Hard', 0), ('Brutal', 4)]
    rank = {'Easy': 0, 'Normal': 1, 'Hard': 2, 'Brutal': 3}.get(requested, 3)
    modes = {mode.strip() for mode in mission['coop_modes']}
    available = [(name, level) for name, level in choices if f'Co-Op {name}' in modes]
    if not available:
        raise ValueError('Native co-op mission has no supported difficulty mode.')
    name, handicap = next(((name, level) for name, level in reversed(choices[:rank + 1]) if (name, level) in available), available[0])
    overlays.append(resolve_path(root, f'INI/Map Code/Difficulty {name}.ini'))
    for overlay in overlays:
        merge(sections, inherited_sections(root, overlay))
    faction = PLAYABLE_FACTIONS[mission['coop_side']]
    production_context = {
        # Synthetic actor ensures no placed unit, scripted house or team is
        # routed to a clone. Every real human uses the native faction mask.
        'player_house': '__COOP_PRODUCTION_ONLY__',
        'production_house': faction, 'acts_like': mission['coop_side'],
        'shared_hostile_houses': [],
    }
    rules, report = unit_specific_buff_rules(
        mission, [reward for reward in rewards if supported_reward(reward)],
        access_randomized=False, production_context=production_context,
        source_sections=sections, human_only_production=True,
        shop_global_buff_levels=(settings or {}).get('shop_global_buff_levels'),
    )
    if report['map_objects_rewritten'] or report['player_taskforce_routes']:
        raise ValueError('Co-op rewards attempted to rewrite authored actors.')
    merge(sections, rules)
    sections.setdefault('Basic', {}).update({'SkipScore': 'no', 'EndOfGame': 'no'})
    # Flatten inheritance: spawnmap.ini lives outside Maps/Co-Op and must
    # never resolve inherited map filenames relative to the game root.
    sections.pop('INISystem', None)
    lines = IniLines([line for section, values in sections.items()
                      for line in [f'[{section}]', *(f'{key}={value}' for key, value in values.items()), '']])
    # Settings/Credits initializes AI as well as humans. Native action 106
    # targets Spawn houses (50–57), so team bonuses/debits never touch AI.
    credit_bonus = max(-int(spawn_settings['Credits']), int(credit_bonus))
    if credit_bonus:
        trigger = unique_section_key(lines, ('Events', 'Actions', 'Triggers'), 'DTACC')
        tag = unique_section_key(lines, ('Tags',), 'DTACR')
        actions = [f'106,0,{50 + slot},{credit_bonus},0,0,0,A'
                   for slot in range(mission['coop_player_count'])]
        append_section_entry(lines, 'Events', trigger, '1,13,0,1')
        append_section_entry(lines, 'Actions', trigger, f'{len(actions)},' + ','.join(actions))
        append_section_entry(lines, 'Triggers', trigger, 'Spawn1,<none>,Co-op Starting Credits,0,1,1,1,0')
        append_section_entry(lines, 'Tags', tag, f'0,Co-op Starting Credits,{trigger}')
    preserve_collateral_damage_coefficients(lines)
    data = ('\r\n'.join(lines) + '\r\n').encode('cp1252')
    spawn_settings.update({'AIDifficulty': str(handicap), 'DifficultyName': name,
                           'CoachMode': 'Yes', 'WriteStatistics': 'Yes'})
    return data, spawn_settings, report, hashlib.sha256(data).hexdigest()


def verify_dependencies(root, mission):
    for name, digest in mission['coop_dependencies'].items():
        if hashlib.sha256(resolve_path(root, name).read_bytes()).hexdigest() != digest:
            raise ValueError('Native co-op map/options changed; refresh catalogue and generate a new run.')
