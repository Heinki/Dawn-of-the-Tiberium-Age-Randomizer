"""Mission-script enemy buffs with house-safe, map-local mutations."""

from hashlib import sha256

from randomizer.rewards.enemy_scaling import (
    enemy_effect_text,
    enemy_effect_values,
)

from .ini import all_section_value_maps, parse_action_groups


SCRIPT_ENEMY_EFFECTS = frozenset({
    'ion_cannon',
    'team_delays',
    'reinforcement_size',
    'production_activation',
    'powerhouse',
})

_PRODUCTION_ACTIONS = frozenset({'3', '13', '74'})
_CREATE_TEAM_ACTIONS = frozenset({'4', '80'})
_SPECIAL_UNIT_BY_ACTS_LIKE = {
    0: 'AIHTNK',
    1: 'AIPLSM',
    2: 'TTNKMSL',
    3: 'AI4TNK',
}


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


def _team_taskforce_rules(
    sections,
    hostile_houses,
    regional_count,
    powerhouse_count,
):
    if regional_count <= 0 and powerhouse_count <= 0:
        return {}, []
    by_lower = _casefold_sections(sections)
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
    for team_id in team_ids:
        team_item = by_lower.get(team_id.casefold())
        if team_item is None:
            continue
        _team_name, team_values = team_item
        team_folded = _casefold_values(team_values)
        house = str(team_folded.get('house', '')).strip()
        if house.casefold() not in hostile:
            continue
        apply_regional = (
            regional_count > 0
            and (
                team_id.casefold() in reinforcement_teams
                or str(team_folded.get('reinforce', '')).casefold()
                in {'yes', 'true', '1'}
            )
        )
        apply_powerhouse = powerhouse_count > 0
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
        regional_applied = 0
        if apply_regional:
            for offset in range(regional_count):
                key = member_keys[offset % len(member_keys)]
                fields = [item.strip() for item in str(clone_values[key]).split(',')]
                if len(fields) < 2:
                    continue
                try:
                    fields[0] = str(max(1, int(fields[0])) + 1)
                except ValueError:
                    continue
                clone_values[key] = ','.join(fields)
                regional_applied += 1
        special_applied = False
        special_id = _SPECIAL_UNIT_BY_ACTS_LIKE.get(
            _house_acts_like(house, by_lower)
        )
        if apply_powerhouse and special_id:
            existing_key = next((
                key for key in member_keys
                if str(clone_values[key]).split(',')[-1].strip().casefold()
                == special_id.casefold()
            ), None)
            if existing_key is not None:
                fields = [item.strip() for item in str(
                    clone_values[existing_key]
                ).split(',')]
                fields[0] = str(max(1, int(fields[0])) + 1)
                clone_values[existing_key] = ','.join(fields)
                special_applied = True
            else:
                next_member = str(max(int(key) for key in member_keys) + 1)
                clone_values[next_member] = f'1,{special_id}'
                special_applied = True
        if not regional_applied and not special_applied:
            continue
        clone_id = _taskforce_clone_id(team_id, occupied)
        taskforce_list[_next_list_key(taskforce_list)] = clone_id
        rules.setdefault('TaskForces', {}).update({
            key: value for key, value in taskforce_list.items()
            if value == clone_id
        })
        rules[clone_id] = clone_values
        rules.setdefault(team_id, {})['TaskForce'] = clone_id
        if regional_applied:
            applications.append((
                'reinforcement_size', house, team_id, regional_applied,
                'TaskForce unit counts',
            ))
        if special_applied:
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
