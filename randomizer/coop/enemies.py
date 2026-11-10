"""Apply Shop pressure to native enemy slots without changing faction types."""

from collections import Counter
from math import isfinite

from randomizer.dta.rules import PLAYABLE_FACTIONS, ini_sections
from randomizer.maps.enemy_scripting import (
    _offmap_enemy_veterancy_rules, _team_taskforce_rules, _reinforcement_member_kind,
    enemy_script_buff_rules,
)
from randomizer.maps.ini import IniLines, parse_action_groups
from randomizer.rewards.enemy_scaling import enemy_effect_text, enemy_effect_values


STAT_FIELDS = {
    'armor': ('Armor',), 'production': ('BuildTime',),
    'firepower': ('Firepower',), 'reload': ('ROF',),
    'speed': ('Groundspeed', 'Airspeed'),
}
WAVE_EFFECTS = frozenset({'reinforcement_size', 'powerhouse'})
SUPPORTED_EFFECTS = frozenset(STAT_FIELDS) | WAVE_EFFECTS
DIFFICULTY_SECTIONS = {
    0: 'Easy', 1: 'Normal', 2: 'Difficult', 3: 'VeryEasy',
    4: 'BrutallyEasy', 5: 'ExtremelyEasy', 6: 'UltimatelyEasy',
}
ENEMY_HANDICAP = 6


def enemy_context(mission):
    """Spawn names refer to waypoints; Multi names refer to sorted roster slots."""
    protected = set(mission.get('_coop_protected_enemy_positions', ()))
    friendly_sides = {mission['coop_side'], *(side for side, _, _ in mission['coop_allies']),
                      *(side for side, _, position in mission['coop_enemies'] if position in protected)}
    houses = {}
    for side, _color, position in mission['coop_enemies']:
        if position in protected:
            continue
        houses[f'Spawn{position + 1}'] = side
        # Country-owned authored teams are unambiguous only when no friendly
        # actor uses that country. Explicit enemy Spawn owners always qualify.
        if side not in friendly_sides:
            houses[PLAYABLE_FACTIONS[side]] = side
    return houses


def scripted_allied_enemy_positions(mission, sections):
    """Protect authored helper houses even when the lobby lists them as enemies."""
    friendly_positions = {*range(mission['coop_player_count']),
                          *(position for _, _, position in mission['coop_allies'])}
    friendly_sides = {mission['coop_side'], *(side for side, _, _ in mission['coop_allies'])}
    friendly_targets = {*(str(50 + position) for position in friendly_positions),
                        *(str(side) for side in friendly_sides)}
    protected = set()
    for key, value in sections.get('Actions', {}).items():
        _count, groups = parse_action_groups(value)
        if not any(group[0] in {'37', '117'} and group[2] in friendly_targets for group in groups):
            continue
        owner = sections.get('Triggers', {}).get(key, '').split(',')[0].strip().casefold()
        for side, _color, position in mission['coop_enemies']:
            if owner in {f'spawn{position + 1}', PLAYABLE_FACTIONS[side].casefold()}:
                protected.add(position)
    return sorted(protected)


def available_wave_effects(mission, sections, installed):
    """Inspect actual native teams before offering a reinforcement bonus."""
    context = enemy_context(mission)
    factions = {house.casefold(): side for house, side in context.items()}
    protected = protected_wave_teams(sections, installed)
    effects = []
    for effect in sorted(WAVE_EFFECTS):
        _rules, applications = _team_taskforce_rules(
            sections, installed, context,
            1 if effect == 'reinforcement_size' else 0,
            1 if effect == 'powerhouse' else 0,
            house_factions=factions,
            excluded_teams=protected,
        )
        _rules, veteran_changes = _offmap_enemy_veterancy_rules(sections, context, 2, protected)
        if applications or veteran_changes:
            effects.append(effect)
    return effects


def protected_wave_teams(sections, installed):
    """Keep heroes, transports, MCVs and unknown objective actors authored."""
    by_lower = {name.casefold(): (name, values) for name, values in sections.items()}
    installed_lower = {name.casefold(): (name, values) for name, values in installed.items()}
    protected = []
    for team in sections.get('TeamTypes', {}).values():
        values = {key.casefold(): value for key, value in sections.get(team, {}).items()}
        taskforce = by_lower.get(str(values.get('taskforce', '')).casefold(), ('', {}))[1]
        members = [str(value).split(',')[-1].strip() for key, value in taskforce.items() if str(key).isdigit()]
        if not members or any(not _reinforcement_member_kind(unit, by_lower, installed_lower)[1]
                              for unit in members):
            protected.append(team)
    return protected


def _values(sections, name):
    return {key.casefold(): value for section, values in sections.items()
            if section.casefold() == name.casefold() for key, value in values.items()}


def apply_enemy_rewards(root, mission, sections, spawn_settings, rewards):
    """Reserve an unused handicap profile for hostile AI, retaining native actors.

    Vinifera 17b45db5 reads HouseHandicaps per AI and copies profile multipliers
    into each HouseClass. Copy the authored difficulty into the unused Ultimate
    profile before multiplying it. Humans and allied AI never select that profile.
    Extended AI handicaps use the engine's hard tactical difficulty internally.
    """
    rewards = list(rewards or ())
    invalid = [reward.get('name', '?') for reward in rewards
               if not reward.get('enemy_reward') or reward.get('enemy_effect') not in SUPPORTED_EFFECTS]
    if invalid:
        raise ValueError('Unsupported co-op enemy effects: ' + ', '.join(invalid))
    context = enemy_context(mission)
    if not context and rewards:
        raise ValueError('Co-op challenge has no native enemy slots.')
    installed = ini_sections(root / 'INI' / 'Rules.ini')
    if mission.get('required_addon'):
        from .catalogue import merge
        merge(installed, ini_sections(root / 'INI' / 'Enhance.ini'))
    counts = Counter(str(reward['enemy_effect_id']) for reward in rewards)
    definitions = {str(reward['enemy_effect_id']): reward for reward in rewards}
    applications = []
    applied = set()
    stat_rewards = [reward for reward in definitions.values() if reward['enemy_effect'] in STAT_FIELDS]
    if stat_rewards:
        base_handicap = int(spawn_settings['AIDifficulty'])
        if base_handicap not in (0, 1, 2, 4):
            raise ValueError('Co-op enemy profile requires a native authored difficulty.')
        base_name = DIFFICULTY_SECTIONS[base_handicap]
        base = {**_values(installed, base_name), **_values(sections, base_name)}
        # Fully replace the reserved profile's values, including fields omitted
        # by the base profile; otherwise its native Ultimate discounts leak in.
        profile = {key: base.get(key.casefold(), default) for key, default in {
            'Firepower': '1', 'Armor': '1', 'Groundspeed': '1', 'Airspeed': '1',
            'ROF': '1', 'Cost': '1', 'BuildTime': '1', 'RepairDelay': '.02',
            'BuildDelay': '.03', 'BuildSlowdown': 'no',
            'DestroyWalls': 'yes', 'ContentScan': 'no',
        }.items()}
        for reward in stat_rewards:
            effect_id = str(reward['enemy_effect_id'])
            count = min(counts[effect_id], int(reward.get('enemy_maximum', 5)))
            factor = enemy_effect_values(reward, count)['relative_engine_value']
            for field in STAT_FIELDS[reward['enemy_effect']]:
                base_value = float(profile[field])
                value = base_value * factor
                if not isfinite(value) or value <= 0:
                    raise ValueError('Co-op enemy profile contains an invalid multiplier.')
                profile[field] = f'{value:.6f}'.rstrip('0').rstrip('.')
                for side, _color, position in mission['coop_enemies']:
                    if f'Spawn{position + 1}' not in context:
                        continue
                    applications.append({
                        **enemy_effect_values(reward, count, base_value),
                        'effect_id': effect_id, 'effect': enemy_effect_text(reward, count, base_value),
                        'category': str(reward.get('enemy_category') or 'Enemy forces'),
                        'house': f'Spawn{position + 1}', 'country': PLAYABLE_FACTIONS[side],
                        'target': f'Spawn{position + 1}',
                        'engine_field': f'{DIFFICULTY_SECTIONS[ENEMY_HANDICAP]}.{field}',
                    })
            applied.add(effect_id)
        reserved = DIFFICULTY_SECTIONS[ENEMY_HANDICAP]
        existing = next((name for name in sections if name.casefold() == reserved.casefold()), reserved)
        sections[existing] = profile
        spawn_settings['_coop_enemy_handicap'] = ENEMY_HANDICAP
        spawn_settings['_coop_enemy_buff_positions'] = [position for _, _, position in mission['coop_enemies']
                                                       if f'Spawn{position + 1}' in context]
    wave_rewards = [reward for reward in rewards if reward['enemy_effect'] in WAVE_EFFECTS]
    if wave_rewards:
        lines = IniLines([line for section, values in sections.items()
                          for line in [f'[{section}]', *(f'{key}={value}' for key, value in values.items()), '']])
        rules, report = enemy_script_buff_rules(
            mission, lines, context, wave_rewards, installed,
            house_factions={house.casefold(): side for house, side in context.items()},
            excluded_teams=protected_wave_teams(sections, installed),
        )
        from .catalogue import merge
        merge(sections, rules)
        applied.update(report['applied'])
        applications.extend(report['applications'])
    applied_ids = [str(reward['name']) for reward in rewards if reward['enemy_effect_id'] in applied]
    skipped = sorted(set(definitions) - applied)
    return {'applications': applications, 'reward_ids': applied_ids, 'skipped': skipped,
            'hostile_houses': list(context)}
