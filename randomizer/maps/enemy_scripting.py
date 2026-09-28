"""Mission-script enemy buffs with house-safe, map-local mutations."""

from hashlib import sha256

from randomizer.rewards.enemy_scaling import (
    enemy_effect_text,
    enemy_effect_values,
)
from randomizer.dta.rules import CURATED_HERO_BUILD_LIMITS

from .ini import all_section_value_maps, parse_action_groups


SCRIPT_ENEMY_EFFECTS = frozenset({
    'ion_cannon',
    'team_delays',
    'reinforcement_size',
    'production_activation',
    'powerhouse',
})

_PRODUCTION_ACTIONS = frozenset({'3', '13', '74'})
_CREATE_TEAM_ACTIONS = frozenset({'4', '7', '80', '107'})
# Installed land specials with faction-specific AI versions where available.
_SPECIAL_UNITS_BY_ACTS_LIKE = {
    0: ('AIHTNK', 'AIXO', 'CARRTRUK'),
    1: ('AIPLSM', 'AISCRINTNK', 'ILHEMOTH'),
    2: ('TTNKMSL', 'AIBFRT', 'BRIG'),
    3: ('AI4TNK', 'AIBEHEMOTH', 'BEHEPLSM'),
}
_SPECIAL_REINFORCEMENT_IDS = frozenset(
    unit_id for pool in _SPECIAL_UNITS_BY_ACTS_LIKE.values()
    for unit_id in pool
)
_MCV_IDS = frozenset({'BASEUNIT', 'GMCV', 'NMCV', 'AMCV', 'SMCV'})


def _casefold_sections(sections):
    return {
        str(section).casefold(): (section, values)
        for section, values in sections.items()
    }


def _casefold_values(values):
    return {str(key).casefold(): value for key, value in values.items()}


def _effect_counts(rewards):
    counts = {}
    definitions = {}
    for reward in rewards or ():
        effect = str(reward.get('enemy_effect') or '')
        if not reward.get('enemy_reward') or effect not in SCRIPT_ENEMY_EFFECTS:
            continue
        effect_id = str(reward.get('enemy_effect_id') or '')
        maximum = max(1, int(reward.get('enemy_maximum', 1)))
        counts[effect_id] = min(counts.get(effect_id, 0) + 1, maximum)
        definitions[effect_id] = reward
    return counts, definitions


def _application(reward, count, house, target, field, base=1.0):
    values = enemy_effect_values(reward, count, base)
    return {
        **values,
        'effect_id': reward['enemy_effect_id'],
        'effect': enemy_effect_text(reward, count, base),
        'category': reward.get('enemy_category', 'Enemy forces'),
        'house': house,
        'country': '',
        'target': target,
        'engine_field': field,
    }


def _team_ids_created_by_actions(sections):
    known = {
        str(value).casefold()
        for value in sections.get('TeamTypes', {}).values()
        if value
    }
    result = set()
    for value in sections.get('Actions', {}).values():
        _count, groups = parse_action_groups(str(value))
        for group in groups:
            if group[0] not in _CREATE_TEAM_ACTIONS:
                continue
            result.update(
                str(token).casefold() for token in group[1:]
                if str(token).casefold() in known
            )
    return result


def _next_list_key(values):
    numeric = [int(key) for key in values if str(key).isdigit()]
    return str(max(numeric, default=-1) + 1)


def _taskforce_clone_id(team_id, occupied):
    stem = 'MORTF' + sha256(str(team_id).encode('utf-8')).hexdigest()[:8].upper()
    candidate = stem
    suffix = 2
    while candidate.casefold() in occupied:
        candidate = f'{stem[:12]}{suffix}'
        suffix += 1
    occupied.add(candidate.casefold())
    return candidate


def _house_acts_like(house, sections_by_lower):
    values = sections_by_lower.get(str(house).casefold(), ('', {}))[1]
    folded = _casefold_values(values)
    try:
        return int(folded.get('actslike', -1))
    except (TypeError, ValueError):
        return -1


def _reinforcement_unit_values(
    unit_id, map_sections, installed_sections, seen=None,
):
    """Resolve installed properties plus mission overrides for a TaskForce unit."""
    unit_id = str(unit_id).casefold()
    installed = installed_sections.get(unit_id, ('', {}))[1]
    mission = map_sections.get(unit_id, ('', {}))[1]
    mission_values = _casefold_values(mission)
    values = {**_casefold_values(installed), **mission_values}
    parent = mission_values.get('$inherits') or mission_values.get('basesection')
    if not installed:
        parent = parent or values.get('$inherits') or values.get('basesection')
    seen = set(seen or ())
    seen.add(unit_id)
    if parent and parent.casefold() not in seen:
        parent_values = _reinforcement_unit_values(
            parent, map_sections, installed_sections, seen
        )
        parent_values.update(values)
        return parent_values
    return values


def _reinforcement_member_kind(unit_id, map_sections, installed_sections):
    """Classify spawn terrain; reject units unsafe to duplicate."""
    values = _reinforcement_unit_values(
        unit_id, map_sections, installed_sections
    )
    if not values:
        return 'unknown', False
    if not any(
        key in values for key in ('category', 'speedtype', 'movementzone', 'naval')
    ):
        return 'unknown', False
    unit_id = str(unit_id).upper()
    try:
        passengers = int(values.get('passengers') or 0)
        build_limit = int(values.get('buildlimit') or 0)
    except (TypeError, ValueError):
        return 'unknown', False
    safe = not (
        unit_id in _MCV_IDS
        or unit_id.endswith('MCV')
        or unit_id in CURATED_HERO_BUILD_LIMITS
        or unit_id in _SPECIAL_REINFORCEMENT_IDS
        or values.get('category', '').casefold() == 'transport'
        or passengers > 0
        or build_limit > 0
        or values.get('isvehicletransport', '').casefold() == 'yes'
        or values.get('carryall', '').casefold() == 'yes'
    )
    naval = (
        values.get('naval', '').casefold() == 'yes'
        or values.get('speedtype', '').casefold() == 'float'
        or values.get('movementzone', '').casefold() == 'water'
    )
    air = (
        values.get('category', '').casefold() == 'airpower'
        or values.get('movementzone', '').casefold() == 'fly'
    )
    return ('naval' if naval else 'air' if air else 'land'), safe


def _offmap_enemy_veterancy_rules(
    sections, hostile_houses, desired_level,
):
    """Promote every hostile TeamType created as an off-map wave."""
    if desired_level <= 1:
        return {}, []
    map_by_lower = _casefold_sections(sections)
    hostile = {str(house).casefold() for house in hostile_houses}
    rules = {}
    changed = []
    action_teams = _team_ids_created_by_actions(sections)
    team_ids = dict.fromkeys(
        str(value).casefold()
        for value in sections.get('TeamTypes', {}).values()
    )
    for team_id in team_ids:
        team_item = map_by_lower.get(team_id)
        if team_item is None:
            continue
        team_name, team_values = team_item
        folded = _casefold_values(team_values)
        house = str(folded.get('house') or '').strip()
        if house.casefold() not in hostile:
            continue
        if (
            team_id not in action_teams
            and str(folded.get('reinforce') or '').casefold()
            not in {'yes', 'true', '1'}
        ):
            continue
        taskforce_id = str(folded.get('taskforce') or '').casefold()
        taskforce_item = map_by_lower.get(taskforce_id)
        if taskforce_item is None:
            continue
        if not any(str(key).isdigit() for key in taskforce_item[1]):
            continue
        try:
            current_level = int(folded.get('veteranlevel', 1))
        except (TypeError, ValueError):
            current_level = 1
        if current_level >= desired_level:
            continue
        rules.setdefault(team_name, {})['VeteranLevel'] = str(desired_level)
        changed.append((house, 'TeamType.VeteranLevel'))
    return rules, changed


def _team_taskforce_rules(
    sections,
    installed_sections,
    hostile_houses,
    regional_count,
    powerhouse_count,
):
    if regional_count <= 0 and powerhouse_count <= 0:
        return {}, []
    by_lower = _casefold_sections(sections)
    installed_by_lower = _casefold_sections(installed_sections)
    hostile = {str(house).casefold() for house in hostile_houses}
    reinforcement_teams = _team_ids_created_by_actions(sections)
    occupied = set(by_lower)
    taskforce_list = dict(sections.get('TaskForces', {}))
    rules = {}
    applications = []
    team_ids = [
        str(value).strip()
        for value in sections.get('TeamTypes', {}).values()
        if str(value).strip()
    ]
    mission_identity = repr((
        sections.get('Basic', {}), sections.get('TeamTypes', {}),
        sections.get('TaskForces', {}),
    ))
    special_cursors = {
        faction: int.from_bytes(
            sha256(f'{faction}|{mission_identity}'.encode('utf-8')).digest()[:4],
            'big',
        ) % len(pool)
        for faction, pool in _SPECIAL_UNITS_BY_ACTS_LIKE.items()
    }
    for team_id in team_ids:
        team_item = by_lower.get(team_id.casefold())
        if team_item is None:
            continue
        _team_name, team_values = team_item
        team_folded = _casefold_values(team_values)
        house = str(team_folded.get('house', '')).strip()
        if house.casefold() not in hostile:
            continue
        is_reinforcement = (
            team_id.casefold() in reinforcement_teams
            or str(team_folded.get('reinforce', '')).casefold()
            in {'yes', 'true', '1'}
        )
        apply_regional = regional_count > 0 and is_reinforcement
        apply_powerhouse = powerhouse_count > 0 and is_reinforcement
        if not apply_regional and not apply_powerhouse:
            continue
        taskforce_id = str(team_folded.get('taskforce', '')).strip()
        taskforce_item = by_lower.get(taskforce_id.casefold())
        if taskforce_item is None:
            continue
        _taskforce_name, taskforce_values = taskforce_item
        clone_values = dict(taskforce_values)
        member_keys = sorted(
            (key for key in clone_values if str(key).isdigit()),
            key=lambda key: int(key),
        )
        if not member_keys:
            continue
        unit_ids = [
            str(clone_values[key]).split(',')[-1].strip().upper()
            for key in member_keys
        ]
        members = [
            _reinforcement_member_kind(
                unit_id, by_lower, installed_by_lower,
            )
            for unit_id in unit_ids
        ]
        land_team = all(kind == 'land' for kind, _safe in members)
        regional_applied = 0
        if apply_regional:
            # Preserve Regional Presence for land and air members. Extra
            # ships can spill onto land; unknown members lack safe terrain.
            eligible_keys = [
                key for key, (_kind, safe) in zip(member_keys, members)
                if safe
            ] if all(
                kind in {'land', 'air'} for kind, _safe in members
            ) else []
            for offset in range(regional_count):
                if not eligible_keys:
                    break
                key = eligible_keys[offset % len(eligible_keys)]
                fields = [item.strip() for item in str(clone_values[key]).split(',')]
                if len(fields) < 2:
                    continue
                try:
                    fields[0] = str(max(1, int(fields[0])) + 1)
                except ValueError:
                    continue
                clone_values[key] = ','.join(fields)
                regional_applied += 1
        same_type_applied = False
        # Air and naval teams already have suitable spawn paths. Reinforce an
        # existing type instead of inserting a land-only faction special.
        if apply_powerhouse and not land_team:
            eligible_keys = [
                key for key, (kind, safe) in zip(member_keys, members)
                if safe and kind in {'air', 'naval'}
            ]
            if eligible_keys:
                key = eligible_keys[0]
                fields = [item.strip() for item in str(clone_values[key]).split(',')]
                if len(fields) >= 2:
                    try:
                        fields[0] = str(max(1, int(fields[0])) + powerhouse_count)
                    except ValueError:
                        pass
                    else:
                        clone_values[key] = ','.join(fields)
                        same_type_applied = True
        special_ids_added = []
        faction = _house_acts_like(house, by_lower)
        special_pool = _SPECIAL_UNITS_BY_ACTS_LIKE.get(faction, ())
        if apply_powerhouse and land_team and any(
            safe or unit_id in special_pool
            for unit_id, (_kind, safe) in zip(unit_ids, members)
        ) and special_pool:
            for offset in range(min(2, len(special_pool))):
                special_id = special_pool[
                    (special_cursors[faction] + offset) % len(special_pool)
                ]
                existing_key = next((
                    key for key in clone_values if str(key).isdigit()
                    and str(clone_values[key]).split(',')[-1].strip().casefold()
                    == special_id.casefold()
                ), None)
                if existing_key is not None:
                    fields = [item.strip() for item in str(
                        clone_values[existing_key]
                    ).split(',')]
                    try:
                        fields[0] = str(max(1, int(fields[0])) + 1)
                    except (IndexError, ValueError):
                        continue
                    clone_values[existing_key] = ','.join(fields)
                else:
                    next_member = str(max(
                        int(key) for key in clone_values if str(key).isdigit()
                    ) + 1)
                    clone_values[next_member] = f'1,{special_id}'
                special_ids_added.append(special_id)
            if special_ids_added:
                special_cursors[faction] = (
                    special_cursors[faction] + 1
                ) % len(special_pool)
        if not regional_applied and not same_type_applied and not special_ids_added:
            continue
        clone_id = _taskforce_clone_id(team_id, occupied)
        taskforce_list[_next_list_key(taskforce_list)] = clone_id
        rules.setdefault('TaskForces', {}).update({
            key: value for key, value in taskforce_list.items()
            if value == clone_id
        })
        rules[clone_id] = clone_values
        rules.setdefault(team_id, {})['TaskForce'] = clone_id
        added_strength = regional_applied + (
            powerhouse_count if same_type_applied or special_ids_added else 0
        )
        # DTA TeamTypes use VeteranLevel=2 for veteran (100 experience)
        # and VeteranLevel=3 for elite (200 experience).
        desired_level = 3 if added_strength >= 3 else 2
        try:
            current_level = int(team_folded.get('veteranlevel', 1))
        except (TypeError, ValueError):
            current_level = 1
        if current_level < desired_level:
            rules[team_id]['VeteranLevel'] = str(desired_level)
        if regional_applied:
            applications.append((
                'reinforcement_size', house, team_id, regional_applied,
                'TaskForce unit counts',
            ))
        if same_type_applied:
            applications.append((
                'powerhouse', house, team_id, powerhouse_count,
                'TaskForce air/naval unit count',
            ))
        for special_id in special_ids_added:
            applications.append((
                'powerhouse', house, f'{team_id} / {special_id}', 1,
                'TaskForce special unit',
            ))
    return rules, applications


def _production_activation_rules(sections, hostile_houses, factor):
    if factor >= 1.0:
        return {}, []
    houses = {
        str(key): str(value).casefold()
        for key, value in sections.get('Houses', {}).items()
    }
    hostile = {str(house).casefold() for house in hostile_houses}
    rules = {}
    changed = []
    for trigger_id, action_value in sections.get('Actions', {}).items():
        _count, action_groups = parse_action_groups(str(action_value))
        production_houses = {
            houses.get(str(group[2]), '')
            for group in action_groups
            if group[0] in _PRODUCTION_ACTIONS and len(group) > 2
        }
        if not production_houses.intersection(hostile):
            continue
        event_value = sections.get('Events', {}).get(trigger_id)
        if event_value is None:
            continue
        tokens = [token.strip() for token in str(event_value).split(',')]
        try:
            event_count = int(tokens[0])
        except (ValueError, IndexError):
            continue
        event_changed = False
        for index in range(event_count):
            offset = 1 + index * 3
            if offset + 2 >= len(tokens) or tokens[offset] != '13':
                continue
            try:
                old_delay = int(tokens[offset + 2])
            except ValueError:
                continue
            new_delay = max(1, int(round(old_delay * factor)))
            if new_delay < old_delay:
                tokens[offset + 2] = str(new_delay)
                event_changed = True
        if event_changed:
            rules.setdefault('Events', {})[trigger_id] = ','.join(tokens)
            changed.append(str(trigger_id))
    return rules, changed


def _unique_control_id(sections, seed):
    occupied = {
        str(key)
        for name in ('Triggers', 'Events', 'Actions', 'Tags')
        for key in sections.get(name, {})
    }
    candidate = 90000000 + int.from_bytes(
        sha256(str(seed).encode('utf-8')).digest()[:3], 'big'
    ) % 9000000
    while str(candidate) in occupied or str(candidate + 1) in occupied:
        candidate += 2
    return str(candidate), str(candidate + 1)


def _ion_cannon_rules(mission, sections, hostile_houses, cooldown):
    if (
        mission.get('build_classification') != 'base_build'
        or not hostile_houses
    ):
        return {}, ''
    house = str(next(iter(hostile_houses)))
    trigger_id, tag_id = _unique_control_id(
        sections, f'{mission.get("code", "")}:ion-thunderbolt'
    )
    name = 'Ion Thunderbolt'
    return {
        'Triggers': {
            trigger_id: f'{house},<none>,{name},1,1,1,1,0',
        },
        'Events': {
            trigger_id: f'1,13,0,{int(cooldown)}',
        },
        'Actions': {
            trigger_id: (
                f'2,33,0,3,0,0,0,0,A,54,2,{trigger_id},0,0,0,0,A'
            ),
        },
        'Tags': {
            tag_id: f'2,{name} (tag),{trigger_id}',
        },
    }, house


def enemy_script_buff_rules(
    mission,
    lines,
    hostile_houses,
    rewards,
    installed_sections,
    reserved_rules=None,
):
    """Apply reviewed AI script buffs without touching player-owned teams."""
    counts, definitions = _effect_counts(rewards)
    if not counts or not hostile_houses:
        return {}, {'applied': [], 'applications': []}
    sections = all_section_value_maps(lines)
    for section, values in (reserved_rules or {}).items():
        sections.setdefault(section, {}).update(values)
    rules = {}
    applied = []
    applications = []

    def merge(extra):
        for section, values in extra.items():
            rules.setdefault(section, {}).update(values)

    by_effect = {
        reward.get('enemy_effect'): (effect_id, counts[effect_id], reward)
        for effect_id, reward in definitions.items()
    }
    logistics = by_effect.get('team_delays')
    if logistics:
        effect_id, count, reward = logistics
        base_value = _casefold_values(
            sections.get('General', {})
        ).get('teamdelays') or _casefold_values(
            installed_sections.get('General', {})
        ).get('teamdelays') or '1200,2400,2400'
        factor = enemy_effect_values(reward, count)['relative_engine_value']
        try:
            delays = [
                str(max(1, int(round(float(value.strip()) * factor))))
                for value in str(base_value).split(',')
            ]
        except ValueError:
            delays = []
        if delays:
            merge({'General': {'TeamDelays': ','.join(delays)}})
            applied.append(effect_id)
            for house in hostile_houses:
                applications.append(_application(
                    reward, count, house, 'All AI teams', 'General.TeamDelays'
                ))

    regional = by_effect.get('reinforcement_size')
    powerhouse = by_effect.get('powerhouse')
    team_rules, team_results = _team_taskforce_rules(
        sections,
        installed_sections,
        hostile_houses,
        regional[1] if regional else 0,
        powerhouse[1] if powerhouse else 0,
    )
    merge(team_rules)
    for effect, house, target, applied_count, field in team_results:
        _effect_id, count, reward = by_effect[effect]
        applications.append(_application(
            reward, count, house, target, field, max(1, applied_count)
        ))
    if regional and any(item[0] == 'reinforcement_size' for item in team_results):
        applied.append(regional[0])
    if powerhouse and any(item[0] == 'powerhouse' for item in team_results):
        applied.append(powerhouse[0])
    if regional or powerhouse:
        strength = (regional[1] if regional else 0) + (
            powerhouse[1] if powerhouse else 0
        )
        desired_level = 3 if strength >= 3 else 2
        veteran_rules, veteran_changes = _offmap_enemy_veterancy_rules(
            sections, hostile_houses, desired_level,
        )
        merge(veteran_rules)
        counts_by_target = {}
        for house, field in veteran_changes:
            target = (house, field)
            counts_by_target[target] = counts_by_target.get(target, 0) + 1
        for effect in (regional, powerhouse):
            if effect is None or not veteran_changes:
                continue
            effect_id, count, reward = effect
            if effect_id not in applied:
                applied.append(effect_id)
            for (house, field), changed_count in counts_by_target.items():
                applications.append(_application(
                    reward, count, house,
                    f'{changed_count} off-map teams',
                    field, changed_count,
                ))

    readiness = by_effect.get('production_activation')
    if readiness:
        effect_id, count, reward = readiness
        factor = enemy_effect_values(reward, count)['relative_engine_value']
        readiness_rules, changed = _production_activation_rules(
            sections, hostile_houses, factor
        )
        merge(readiness_rules)
        if changed:
            applied.append(effect_id)
            for house in hostile_houses:
                applications.append(_application(
                    reward, count, house, f'{len(changed)} production triggers',
                    'Events.Elapsed Time',
                ))

    ion = by_effect.get('ion_cannon')
    if ion:
        effect_id, count, reward = ion
        factor = enemy_effect_values(reward, count)['relative_engine_value']
        cooldown = max(150, int(round(600 * factor)))
        ion_rules, house = _ion_cannon_rules(
            mission, sections, hostile_houses, cooldown
        )
        merge(ion_rules)
        if house:
            applied.append(effect_id)
            applications.append(_application(
                reward, count, house, 'Periodic Ion Cannon',
                'Trigger.Elapsed Time', 600,
            ))

    return rules, {
        'applied': applied,
        'applications': applications,
    }
