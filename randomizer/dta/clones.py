"""Vinifera production clones for player-only unit-specific buffs."""

from collections import Counter
from hashlib import sha1

from randomizer.config.static import static_config_section
from randomizer.config.tuning import (
    capped_movement_speed,
    capped_sight_range,
    mission_assistance_stack_count,
    stacked_cost,
    stacked_self_heal_amount,
    stacked_weapon_damage,
    stacked_weapon_rof,
    stacking_amount,
    stacking_multiplier,
)
from randomizer.core.paths import GAME_ROOT
from randomizer.dta.maps import mission_source_path
from randomizer.dta.rules import (
    ALWAYS_AVAILABLE_MOBILE_IDS,
    catalogue_by_id,
    comma_items,
    effective_section,
    ini_sections,
    unit_collision_report,
)


TYPE_LIST_BY_CATEGORY = {
    'infantry': 'InfantryTypes',
    'vehicles': 'VehicleTypes',
    'aircraft': 'AircraftTypes',
    'buildings': 'BuildingTypes',
    'defenses': 'BuildingTypes',
}
WEAPON_KEYS = (
    'Primary', 'Secondary', 'Elite', 'ElitePrimary', 'EliteSecondary',
)
HOUSE_MASK_FIELDS = {
    'owner',
    'requiredhouses',
    'forbiddenhouses',
    'factoryowners',
    'factoryowners.forbidden',
    'sw.requiredhouses',
    'sw.forbiddenhouses',
}
MAX_TYPE_ID_LENGTH = 23
FACTION_CAMEO_PRIORITIES = {
    'GDI': 400,
    'Nod': 300,
    'Allies': 200,
    'Soviet': 100,
}
DEFENSE_CAMEO_PRIORITY_OFFSET = 1000
MISSION_ASSISTANCE_BUFF_TYPES = (
    'production', 'cost', 'speed', 'armor', 'health', 'damage', 'reload',
    'range',
)
PRODUCTION_BUILDINGS = static_config_section(
    'factions.json', 'production_buildings', dict
)
PRIMARY_PRODUCTION_BUILDINGS = static_config_section(
    'factions.json', 'chaos_primary_production', dict
)
PRODUCTION_TYPE_ORDER = ('infantry', 'vehicles', 'air', 'naval')


def _faction_cameo_priority(target):
    """Return a sidebar priority band that keeps one-faction tech together."""
    factions = tuple(
        target.get('playable_owners')
        or target.get('owners')
        or target.get('factions')
        or ()
    )
    if len(factions) == 1:
        priority = FACTION_CAMEO_PRIORITIES.get(str(factions[0]), 0)
    else:
        priority = 0
    if target.get('category') == 'defenses':
        priority -= DEFENSE_CAMEO_PRIORITY_OFFSET
    return priority


def _number(value):
    return f'{float(value):.6f}'.rstrip('0').rstrip('.') or '0'


def _scaled_integer(value, multiplier, minimum=1):
    try:
        original = int(float(value))
    except (TypeError, ValueError):
        return None
    if original == 0:
        return 0
    sign = -1 if original < 0 else 1
    return sign * max(minimum, int(round(abs(original) * multiplier)))


def _clone_id(source_id, suffix, occupied):
    source = str(source_id or '').upper()
    candidate = f'{source}_{suffix}'
    if len(candidate) > MAX_TYPE_ID_LENGTH:
        digest = sha1(candidate.encode('ascii', errors='ignore')).hexdigest()[:6].upper()
        tail = f'_{digest}_{suffix[:3]}'
        candidate = f'{source[:MAX_TYPE_ID_LENGTH-len(tail)]}{tail}'
    base = candidate
    counter = 2
    while candidate.casefold() in occupied:
        tail = str(counter)
        candidate = f'{base[:MAX_TYPE_ID_LENGTH-len(tail)]}{tail}'
        counter += 1
    occupied.add(candidate.casefold())
    return candidate


def _merged_sections(installed, authored):
    sections = {name: dict(values) for name, values in installed.items()}
    lookup = {name.casefold(): name for name in sections}
    for name, values in authored.items():
        existing = lookup.get(name.casefold(), name)
        sections.setdefault(existing, {}).update(values)
        lookup[name.casefold()] = existing
    return sections


def _next_list_key(installed, authored, list_name, offsets):
    if list_name not in offsets:
        keys = set(installed.get(list_name, {})) | set(authored.get(list_name, {}))
        numeric = [int(key) for key in keys if str(key).isdigit()]
        offsets[list_name] = max(numeric, default=0) + 1
    value = offsets[list_name]
    offsets[list_name] += 1
    return str(value)


def _player_house(authored):
    player = authored.get('Basic', {}).get('Player', '').strip()
    if player:
        return player
    for section, values in authored.items():
        if values.get('PlayerControl', '').casefold() in {'yes', 'true', '1'}:
            return section
    return ''


def _player_production_context(authored):
    """Resolve the HouseType bit used by Vinifera production checks.

    RequiredHouses and ForbiddenHouses are parsed as HouseType masks, but
    Vinifera tests those masks against a scenario house's ``ActsLike`` value.
    A campaign house such as TutorialGDI therefore produces as GDI (index 0),
    not as the TutorialGDI list entry.
    """
    player_house = _player_house(authored)
    context = {
        'player_house': player_house,
        'production_house': '',
        'acts_like': None,
        'shared_hostile_houses': [],
    }
    if not player_house:
        return context
    house_values = authored.get(player_house, {})
    houses = authored.get('Houses', {})
    try:
        acts_like = int(house_values.get('ActsLike', -1))
    except (TypeError, ValueError):
        acts_like = -1
    production_house = str(houses.get(str(acts_like), '')).strip()
    if not production_house:
        production_house = player_house
    context['production_house'] = production_house
    context['acts_like'] = acts_like if acts_like >= 0 else None

    player_allies = {
        item.casefold() for item in comma_items(house_values.get('Allies'))
    }
    player_allies.add(player_house.casefold())
    registered_house_names = {
        str(name).strip() for name in houses.values() if str(name).strip()
    }
    active_houses = {player_house.casefold()}
    for list_name in ('Infantry', 'Units', 'Aircraft', 'Structures'):
        for value in authored.get(list_name, {}).values():
            fields = comma_items(value)
            if fields and fields[0] in registered_house_names:
                active_houses.add(fields[0].casefold())
    for values in authored.values():
        team_house = str(values.get('House', '')).strip()
        if team_house in registered_house_names:
            active_houses.add(team_house.casefold())
    for house_name in registered_house_names:
        try:
            node_count = int(authored.get(house_name, {}).get('NodeCount', 0))
        except (TypeError, ValueError):
            node_count = 0
        if node_count > 0:
            active_houses.add(house_name.casefold())
    for house_name in houses.values():
        house_name = str(house_name).strip()
        if not house_name or house_name.casefold() == player_house.casefold():
            continue
        if house_name.casefold() not in active_houses:
            continue
        other = authored.get(house_name)
        if not other:
            continue
        try:
            other_acts_like = int(other.get('ActsLike', -2))
        except (TypeError, ValueError):
            continue
        if other_acts_like != acts_like:
            continue
        other_allies = {
            item.casefold() for item in comma_items(other.get('Allies'))
        }
        friendly = (
            house_name.casefold() in player_allies
            or player_house.casefold() in other_allies
            or other.get('PlayerControl', '').casefold() in {'yes', 'true', '1'}
            or other.get('MultiplayPassive', '').casefold() in {'yes', 'true', '1'}
        )
        if not friendly:
            context['shared_hostile_houses'].append(house_name)
    return context


def _production_house_types(authored, configured_houses):
    """Resolve scenario Houses to the HouseType masks used by factories."""
    houses = authored.get('Houses', {})
    house_names = {
        str(name).strip().casefold(): str(name).strip()
        for name in houses.values()
        if str(name).strip()
    }
    resolved = []
    for configured in configured_houses or ():
        configured = str(configured or '').strip()
        if not configured:
            continue
        scenario_house = house_names.get(configured.casefold(), configured)
        try:
            acts_like = int(authored.get(scenario_house, {}).get('ActsLike', -1))
        except (TypeError, ValueError):
            acts_like = -1
        production_house = str(houses.get(str(acts_like), '')).strip()
        if not production_house:
            production_house = house_names.get(configured.casefold(), '')
        if (
            production_house
            and production_house.casefold()
            not in {house.casefold() for house in resolved}
        ):
            resolved.append(production_house)
    return tuple(resolved)


def production_infrastructure_rewards(
    rewards,
    *,
    enabled,
    production_context,
):
    """Create runtime access items for factories needed by earned unit access.

    Building clones stay absent without an earned access item. When present,
    their normal construction-yard production contract remains the physical
    gate; only authored tech prerequisites are removed by the clone builder.
    """
    if not enabled:
        return []
    catalogue = catalogue_by_id()
    production_types = set()
    for reward in rewards or ():
        if not reward.get('dta_production_access'):
            continue
        target = catalogue.get(str(reward.get('unit') or '').upper(), {})
        category = target.get('category')
        if category == 'infantry':
            production_types.add('infantry')
        elif category == 'aircraft':
            production_types.add('air')
        elif category == 'vehicles':
            production_types.add(
                'naval' if target.get('naval') else 'vehicles'
            )

    source_family = str(
        production_context.get('original_production_house')
        or production_context.get('production_house')
        or ''
    ).casefold()
    family_buildings = PRODUCTION_BUILDINGS.get(source_family, {})
    primary_buildings = PRIMARY_PRODUCTION_BUILDINGS.get(source_family, {})
    selected_buildings = []
    for production_type in PRODUCTION_TYPE_ORDER:
        if production_type not in production_types:
            continue
        configured_ids = {
            str(building_id).upper()
            for building_id in family_buildings.get(production_type, ())
            if str(building_id).strip()
        }
        building_id = str(primary_buildings.get(production_type) or '').upper()
        if building_id not in configured_ids:
            building_id = min(configured_ids, default='')
        if building_id:
            selected_buildings.append((production_type, building_id))
    return [
        {
            'name': f'Runtime access to {building_id}',
            'description': (
                'Makes exactly one matching current-faction production '
                'building available without authored technology prerequisites.'
            ),
            'rules': {building_id: {'TechLevel': '1'}},
            'factions': [],
            'kind': 'unit_access',
            'unit': building_id,
            'dta_production_access': True,
            'access_category': 'infrastructure',
            'production_family': source_family,
            'production_type': production_type,
            '_runtime_canonical': True,
        }
        for production_type, building_id in selected_buildings
    ]


def _active_house_names(authored):
    registered = {
        str(name).strip()
        for name in authored.get('Houses', {}).values()
        if str(name).strip()
    }
    active = set()
    for list_name in ('Infantry', 'Units', 'Aircraft', 'Structures'):
        for value in authored.get(list_name, {}).values():
            fields = comma_items(value)
            if fields and fields[0] in registered:
                active.add(fields[0])
    for values in authored.values():
        house = str(values.get('House', '')).strip()
        if house in registered:
            active.add(house)
    for house in registered:
        try:
            nodes = int(authored.get(house, {}).get('NodeCount', 0))
        except (TypeError, ValueError):
            nodes = 0
        if nodes > 0:
            active.add(house)
    player = _player_house(authored)
    if player:
        active.add(player)
    return active


def _house_index_by_name(authored):
    return {
        str(name).strip().casefold(): int(index)
        for index, name in authored.get('Houses', {}).items()
        if str(index).isdigit() and str(name).strip()
    }


def _house_name_by_index(authored):
    return {
        int(index): str(name).strip()
        for index, name in authored.get('Houses', {}).items()
        if str(index).isdigit() and str(name).strip()
    }


def _house_acts_like(authored, house_name):
    try:
        return int(authored.get(house_name, {}).get('ActsLike', -1))
    except (TypeError, ValueError):
        return -1


def _append_house_mask(value, source_house, isolated_house):
    houses = list(comma_items(value))
    if source_house.casefold() not in {
        house.casefold() for house in houses
    }:
        return None
    if isolated_house.casefold() not in {
        house.casefold() for house in houses
    }:
        houses.append(isolated_house)
    return ','.join(houses)


def player_production_isolation_rules(mission):
    """Give shared campaign houses distinct Vinifera production masks.

    Vinifera evaluates TechnoType house masks through ``ActsLike``. When the
    player and a hostile scenario house share one bit, reward clones cannot be
    restricted to the player while both keep that bit. Rebase the smaller side
    of the collision onto an otherwise unique HouseType bit already registered
    by the mission, then copy its previous Owner/Required/Forbidden membership
    to the new bit. Exact scenario-house names, placed objects, teams, triggers,
    alliances, and scripts remain unchanged.
    """
    source = mission_source_path(mission.get('scenario'))
    installed = ini_sections(GAME_ROOT / 'INI' / 'Rules.ini')
    authored = ini_sections(source)
    original_context = _player_production_context(authored)
    report = {
        **original_context,
        'original_player_house': original_context['player_house'],
        'original_production_house': original_context['production_house'],
        'original_acts_like': original_context['acts_like'],
        'original_shared_hostile_houses': list(
            original_context['shared_hostile_houses']
        ),
        'isolation_applied': False,
        'isolated_houses': [],
        'isolation_error': '',
    }
    shared_houses = list(original_context['shared_hostile_houses'])
    if not shared_houses:
        return {}, report

    houses_by_index = _house_name_by_index(authored)
    indices_by_house = _house_index_by_name(authored)
    active_houses = _active_house_names(authored)
    active_house_keys = {house.casefold() for house in active_houses}
    player_house = original_context['player_house']
    source_index = original_context['acts_like']
    source_production_house = original_context['production_house']
    player_index = indices_by_house.get(player_house.casefold(), -1)
    shared_indices = {
        house: indices_by_house.get(house.casefold(), -1)
        for house in shared_houses
    }

    # A canonical hostile HouseType cannot move to its own bit because it is
    # already using that bit. In custom-player missions, moving the one player
    # house is both smaller and safer than moving every hostile house.
    move_player = (
        player_index >= 0
        and player_index != source_index
        and any(index == source_index for index in shared_indices.values())
    )
    targets = [player_house] if move_player else shared_houses
    reserved_indices = {
        _house_acts_like(authored, house)
        for house in active_houses
        if _house_acts_like(authored, house) >= 0
    }
    assigned_indices = set()
    assignments = []
    for target in targets:
        target_index = indices_by_house.get(target.casefold(), -1)
        other_active_indices = {
            _house_acts_like(authored, house)
            for house in active_houses
            if house.casefold() != target.casefold()
            and _house_acts_like(authored, house) >= 0
        }
        candidate = target_index
        if (
            candidate < 0
            or candidate >= 31
            or candidate == source_index
            or candidate in other_active_indices
            or candidate in assigned_indices
        ):
            candidate = next((
                index
                for index, house in sorted(houses_by_index.items())
                if house.casefold() not in active_house_keys
                and 0 <= index < 31
                and index not in reserved_indices
                and index not in assigned_indices
                and index != source_index
            ), -1)
        if candidate < 0:
            report['isolation_error'] = (
                f'no unique HouseType bit is available for {target}'
            )
            return {}, report
        assigned_indices.add(candidate)
        assignments.append({
            'house': target,
            'old_acts_like': _house_acts_like(authored, target),
            'new_acts_like': candidate,
            'old_production_house': source_production_house,
            'new_production_house': houses_by_index[candidate],
        })

    rules = {}
    combined = _merged_sections(installed, authored)
    for assignment in assignments:
        rules.setdefault(assignment['house'], {})['ActsLike'] = str(
            assignment['new_acts_like']
        )
        old_house = assignment['old_production_house']
        new_house = assignment['new_production_house']
        for section, values in combined.items():
            for key, value in values.items():
                if key.casefold() not in HOUSE_MASK_FIELDS:
                    continue
                current = rules.get(section, {}).get(key, value)
                translated = _append_house_mask(
                    current, old_house, new_house
                )
                if translated is not None and translated != current:
                    rules.setdefault(section, {})[key] = translated

    isolated_authored = _merged_sections(authored, rules)
    isolated_context = _player_production_context(isolated_authored)
    if isolated_context['shared_hostile_houses']:
        report['isolation_error'] = (
            'production mask collision remains after isolation'
        )
        return {}, report
    report.update(isolated_context)
    report['isolation_applied'] = True
    report['isolated_houses'] = assignments
    return rules, report


def _allied_helper_context(authored, player_context):
    """Return AI allies whose ActsLike family has no active hostile house."""
    player = player_context['player_house']
    houses = authored.get('Houses', {})
    if not player:
        return {'houses': {}, 'families': {}}
    active = _active_house_names(authored)
    player_allies = {
        item.casefold()
        for item in comma_items(authored.get(player, {}).get('Allies'))
    }
    player_allies.add(player.casefold())
    friendly = {player.casefold()}
    for house in active:
        other_allies = {
            item.casefold()
            for item in comma_items(authored.get(house, {}).get('Allies'))
        }
        if house.casefold() in player_allies or player.casefold() in other_allies:
            friendly.add(house.casefold())

    family_by_house = {}
    members_by_family = {}
    for house in active:
        try:
            acts_like = int(authored.get(house, {}).get('ActsLike', -1))
        except (TypeError, ValueError):
            continue
        family = str(houses.get(str(acts_like), '')).strip()
        if not family:
            continue
        family_by_house[house.casefold()] = family
        members_by_family.setdefault(family.casefold(), set()).add(house.casefold())

    safe_families = {
        family
        for family, members in members_by_family.items()
        if members.issubset(friendly)
    }
    helper_houses = {
        house.casefold(): family_by_house[house.casefold()]
        for house in active
        if (
            house.casefold() != player.casefold()
            and house.casefold() in friendly
            and family_by_house.get(house.casefold(), '').casefold()
            in safe_families
            and authored.get(house, {}).get('PlayerControl', '').casefold()
            not in {'yes', 'true', '1'}
            and authored.get(house, {}).get('MultiplayPassive', '').casefold()
            not in {'yes', 'true', '1'}
        )
    }
    canonical_names = {house.casefold(): house for house in active}
    families = {}
    for house, family in helper_houses.items():
        families.setdefault(family, set()).add(canonical_names[house])
    return {'houses': helper_houses, 'families': families}


def _derived_techno_ids(sections, unit_id):
    """Return registered TechnoTypes inheriting from one canonical unit."""
    unit_id = str(unit_id or '').upper()
    lookup = {
        str(name).casefold(): (str(name), values)
        for name, values in sections.items()
    }
    registered = {
        str(value).strip()
        for list_name in ('InfantryTypes', 'VehicleTypes', 'AircraftTypes')
        for value in sections.get(list_name, {}).values()
        if str(value).strip()
    }
    matches = {unit_id}
    for candidate in registered:
        current = candidate
        seen = set()
        while current and current.casefold() not in seen:
            seen.add(current.casefold())
            item = lookup.get(current.casefold())
            if item is None:
                break
            base = str(
                item[1].get('BaseSection') or item[1].get('$Inherits') or ''
            ).strip()
            if not base:
                break
            if base.casefold() == unit_id.casefold():
                matches.add(candidate.upper())
                break
            current = base
    return matches


def _helper_unit_references(authored, sections, unit_id, helper_context):
    """Find helper placements and helper-exclusive TaskForce entries."""
    unit_id = str(unit_id or '').upper()
    reference_ids = _derived_techno_ids(sections, unit_id)
    house_families = helper_context['houses']
    by_family = {
        family: {'placements': [], 'taskforce_entries': []}
        for family in helper_context['families']
    }
    for section in ('Infantry', 'Units', 'Aircraft'):
        for key, value in authored.get(section, {}).items():
            fields = comma_items(value)
            if len(fields) < 2 or fields[1].upper() not in reference_ids:
                continue
            family = house_families.get(fields[0].casefold())
            if family:
                by_family[family]['placements'].append({
                    'section': section,
                    'key': key,
                    'house': fields[0],
                    'source_type': fields[1].upper(),
                })

    consumers = {}
    for section, values in authored.items():
        taskforce = str(values.get('TaskForce', '')).strip()
        house = str(values.get('House', '')).strip().casefold()
        if taskforce:
            consumers.setdefault(taskforce.casefold(), set()).add(house)
    for taskforce, team_houses in consumers.items():
        families = {
            house_families[house]
            for house in team_houses
            if house in house_families
        }
        if len(families) != 1 or any(
            house not in house_families for house in team_houses
        ):
            continue
        family = next(iter(families))
        section_name = next(
            (
                name for name in authored
                if name.casefold() == taskforce
            ),
            '',
        )
        for key, value in authored.get(section_name, {}).items():
            fields = comma_items(value)
            if len(fields) >= 2 and fields[1].upper() in reference_ids:
                by_family[family]['taskforce_entries'].append({
                    'section': section_name,
                    'key': key,
                    'source_type': fields[1].upper(),
                })
    return by_family


def _add_forbidden_house(rules, unit_id, values, production_house):
    existing = list(comma_items(
        rules.get(unit_id, {}).get(
            'ForbiddenHouses', values.get('ForbiddenHouses')
        )
    ))
    if production_house.casefold() not in {
        item.casefold() for item in existing
    }:
        existing.append(production_house)
    rules.setdefault(unit_id, {})['ForbiddenHouses'] = ','.join(existing)


def _can_player_produce(values, production_house):
    player = production_house.casefold()
    owners = {item.casefold() for item in comma_items(values.get('Owner'))}
    required = {
        item.casefold() for item in comma_items(values.get('RequiredHouses'))
    }
    forbidden = {
        item.casefold() for item in comma_items(values.get('ForbiddenHouses'))
    }
    try:
        tech_level = int(values.get('TechLevel', -1))
    except (TypeError, ValueError):
        tech_level = -1
    return (
        player in owners
        and (not required or player in required)
        and player not in forbidden
        and tech_level >= 0
    )


def mission_assistance_rewards(
    mission,
    rewards,
    stacks,
    access_randomized=False,
    production_context=None,
    rule_overlays=None,
):
    """Build temporary retry buffs for player-accessible DTA mobile types."""
    stacks = mission_assistance_stack_count(stacks)
    if not stacks:
        return [], []

    source = mission_source_path(mission.get('scenario'))
    installed = ini_sections(GAME_ROOT / 'INI' / 'Rules.ini')
    authored = ini_sections(source)
    combined = _merged_sections(installed, authored)
    if rule_overlays:
        combined = _merged_sections(combined, rule_overlays)
    context = (
        dict(production_context)
        if production_context is not None
        else _player_production_context(authored)
    )
    player_house = str(context.get('player_house') or '').casefold()
    production_house = str(context.get('production_house') or '')
    catalogue = catalogue_by_id()
    unit_ids = {
        str(reward.get('unit') or '').upper()
        for reward in rewards or ()
        if reward.get('dta_production_access')
    }

    for unit_id, target in catalogue.items():
        if (
            not target.get('rewardable')
            or target.get('duplicate_of')
            or target.get('category') not in {'infantry', 'vehicles', 'aircraft'}
        ):
            continue
        producible = _can_player_produce(
            effective_section(combined, unit_id), production_house
        )
        if (
            (not access_randomized and producible)
            or (unit_id in ALWAYS_AVAILABLE_MOBILE_IDS and producible)
        ):
            unit_ids.add(unit_id)

    # Exact player-owned starting units receive placement-only clones when
    # they are not normally producible. Authored enemy and scripted identities
    # remain untouched.
    for section in ('Infantry', 'Units', 'Aircraft'):
        for value in authored.get(section, {}).values():
            fields = comma_items(value)
            if (
                len(fields) >= 2
                and fields[0].casefold() == player_house
                and fields[1].upper() in catalogue
            ):
                unit_ids.add(fields[1].upper())

    assistance = [
        {
            'kind': 'buff',
            'unit': unit_id,
            'buff_type': buff_type,
            'global_buff': False,
            'dta_production_clone': True,
            'mission_assistance': True,
        }
        for unit_id in sorted(unit_ids)
        for _ in range(stacks)
        for buff_type in MISSION_ASSISTANCE_BUFF_TYPES
    ]
    return assistance, sorted(unit_ids)


def _unit_overrides(values, counts, target):
    overrides = {}
    if counts['build_limit']:
        try:
            base_limit = int(float(values.get('BuildLimit', 0)))
        except (TypeError, ValueError):
            base_limit = 0
        if base_limit <= 0:
            base_limit = int(target.get('build_limit', 0))
        if base_limit > 0:
            overrides['BuildLimit'] = str(
                base_limit + int(counts['build_limit'])
            )
    if counts['production']:
        try:
            base = float(values.get('BuildTimeMultiplier', 1.0))
        except (TypeError, ValueError):
            base = 1.0
        final = base * stacking_multiplier('production', counts['production'])
        if final != base:
            overrides['BuildTimeMultiplier'] = _number(final)
    if counts['cost']:
        try:
            base_cost = int(float(values.get('Cost')))
            final_cost = stacked_cost(values.get('Cost'), counts['cost'])
            if final_cost != base_cost:
                overrides['Cost'] = str(final_cost)
        except (TypeError, ValueError):
            pass
    if counts['speed']:
        try:
            base_speed = int(round(float(target.get('speed', 0))))
            final_speed = capped_movement_speed(target, counts['speed'])
            if base_speed > 0 and final_speed > base_speed:
                overrides['Speed'] = str(final_speed)
        except (TypeError, ValueError):
            pass
    durability_multiplier = 1.0
    if counts['armor']:
        durability_multiplier /= stacking_multiplier('armor', counts['armor'])
    if counts['health']:
        durability_multiplier *= stacking_multiplier('health', counts['health'])
    if durability_multiplier != 1.0:
        scaled = _scaled_integer(
            values.get('Strength'),
            durability_multiplier,
        )
        try:
            base_strength = int(float(values.get('Strength')))
        except (TypeError, ValueError):
            base_strength = None
        if scaled is not None and scaled != base_strength:
            overrides['Strength'] = str(scaled)
    if counts['sight']:
        scaled = _scaled_integer(values.get('Sight'), 1.0)
        if scaled is not None:
            final_sight = capped_sight_range(
                {'sight': scaled}, counts['sight']
            )
            if final_sight > scaled:
                overrides['Sight'] = str(final_sight)
    if counts['ammo']:
        scaled = _scaled_integer(values.get('Ammo'), 1.0)
        if scaled is not None and scaled > 0:
            overrides['Ammo'] = str(
                scaled + int(stacking_amount('ammo', counts['ammo']))
            )
    if counts['passenger_capacity']:
        scaled = _scaled_integer(values.get('Passengers'), 1.0)
        if scaled is not None and scaled > 0:
            overrides['Passengers'] = str(
                scaled + int(counts['passenger_capacity'])
            )
    if (
        counts['cloak']
        and values.get('Cloakable', '').casefold() not in {'yes', 'true', '1'}
    ):
        overrides['Cloakable'] = 'yes'
        overrides['CloakingSpeed'] = '1'
    if (
        counts['sensors']
        and values.get('Sensors', '').casefold() not in {'yes', 'true', '1'}
    ):
        overrides['Sensors'] = 'yes'
    if (
        counts['self_healing']
        and values.get('SelfHealing', '').casefold() not in {'yes', 'true', '1'}
    ):
        overrides['SelfHealing'] = 'yes'
        overrides['SelfHealingCap'] = '50%'
        overrides['SelfHealingRate'] = '.016'
        overrides['SelfHealingStep'] = str(stacked_self_heal_amount(
            values.get('Strength', target.get('strength', 1)),
            counts['self_healing'],
        ))
    return overrides


def _weapon_overrides(values, counts):
    overrides = {}
    if values.get('Spawner', '').casefold() in {'yes', 'true', '1'}:
        return overrides
    if counts['damage']:
        try:
            base_damage = int(float(values.get('Damage')))
            final_damage = stacked_weapon_damage(
                values.get('Damage'), counts['damage']
            )
            if final_damage != base_damage:
                overrides['Damage'] = str(final_damage)
        except (TypeError, ValueError):
            pass
    if counts['reload']:
        try:
            base_rof = int(float(values.get('ROF')))
            final_rof = stacked_weapon_rof(
                values.get('ROF'), counts['reload']
            )
            if final_rof != base_rof:
                overrides['ROF'] = str(final_rof)
        except (TypeError, ValueError):
            pass
    if counts['range']:
        try:
            base_range = float(values.get('Range', 0))
        except (TypeError, ValueError):
            base_range = 0
        if base_range > 0:
            overrides['Range'] = _number(
                base_range + stacking_amount('range', counts['range'])
            )
    return overrides


def _effective_buff_counts(values, target, counts, combined):
    """Discard legacy or inapplicable buffs before deciding to clone a type."""
    effective = Counter()
    for buff_type, count in counts.items():
        if count <= 0:
            continue
        single = Counter({buff_type: count})
        if _unit_overrides(values, single, target):
            effective[buff_type] = count
            continue
        if buff_type not in {'damage', 'range', 'reload'}:
            continue
        for weapon_key in WEAPON_KEYS:
            weapon_id = str(values.get(weapon_key) or '').strip()
            if not weapon_id:
                continue
            if _weapon_overrides(effective_section(combined, weapon_id), single):
                effective[buff_type] = count
                break
    return effective


def _rewrite_building_references(rules, report, catalogue, combined):
    """Make original and cloned structures equivalent for player tech checks."""
    clone_by_source = {
        item['unit'].upper(): item['output_type']
        for item in report['applied']
        if (
            item['output_type'] != item['unit']
            and catalogue.get(item['unit'], {}).get('category')
            in {'buildings', 'defenses'}
        )
    }
    if not clone_by_source:
        return
    group_by_source = {
        source: f'DTAP{sha1(source.encode("ascii")).hexdigest()[:8].upper()}'
        for source in clone_by_source
    }
    group_rules = rules.setdefault('PrerequisiteGroups', {})
    for source, clone_id in clone_by_source.items():
        group_rules[group_by_source[source]] = f'{source},{clone_id}'

    # DTA's built-in POWER/BARRACKS/FACTORY/etc. groups live in [General].
    # Add cloned buildings without removing map-authored originals.
    general = combined.get('General', {})
    for key, value in general.items():
        if not key.casefold().startswith('prerequisite'):
            continue
        items = comma_items(value)
        additions = [
            clone_by_source[item.upper()]
            for item in items
            if item.upper() in clone_by_source
        ]
        if additions:
            rules.setdefault('General', {})[key] = ','.join(
                [*items, *additions]
            )

    cloned_outputs = {
        item['output_type']
        for item in report['applied']
        if item['output_type'] != item['unit']
    }
    list_reference_keys = {
        'poweredby', 'powersupbuilding', 'clonedat', 'builtat', 'dock',
    }
    for output_id in cloned_outputs:
        values = rules.get(output_id, {})
        for key, value in list(values.items()):
            folded = key.casefold()
            items = comma_items(value)
            if (
                folded in {'prerequisite', 'prerequisiteoverride'}
                or folded.startswith('prerequisite.')
            ):
                values[key] = ','.join(
                    group_by_source.get(item.upper(), item) for item in items
                )
                continue
            if folded not in list_reference_keys:
                continue
            additions = [
                clone_by_source[item.upper()]
                for item in items
                if item.upper() in clone_by_source
            ]
            if additions:
                values[key] = ','.join([*items, *additions])

    # Always-available mobile types remain original identities. Rewrite their
    # map-local prerequisites to accept either the original or player clone,
    # otherwise a cloned refinery can make the original harvester disappear.
    for unit_id in ALWAYS_AVAILABLE_MOBILE_IDS:
        values = effective_section(combined, unit_id)
        for key, value in values.items():
            folded = key.casefold()
            if not (
                folded in {'prerequisite', 'prerequisiteoverride'}
                or folded.startswith('prerequisite.')
            ):
                continue
            items = comma_items(value)
            rewritten = [
                group_by_source.get(item.upper(), item) for item in items
            ]
            if rewritten != list(items):
                rules.setdefault(unit_id, {})[key] = ','.join(rewritten)


def unit_specific_buff_rules(
    mission,
    rewards,
    access_randomized=False,
    buff_allied_helpers=False,
    unlimited_hero_units=False,
    production_context=None,
    rule_overlays=None,
    production_owner_houses=(),
):
    """Build map-local original buffs or player production clones.

    Direct player placements may use the player clone. When enabled, isolated
    allied AI families receive helper clones and helper-exclusive TaskForces
    are rerouted. Enemy placements, teams, triggers, and scripts stay original.
    """
    source = mission_source_path(mission.get('scenario'))
    installed = ini_sections(GAME_ROOT / 'INI' / 'Rules.ini')
    authored = ini_sections(source)
    combined = _merged_sections(installed, authored)
    if rule_overlays:
        combined = _merged_sections(combined, rule_overlays)
    production_context = (
        dict(production_context)
        if production_context is not None
        else _player_production_context(authored)
    )
    helper_context = (
        _allied_helper_context(authored, production_context)
        if buff_allied_helpers
        else {'houses': {}, 'families': {}}
    )
    player_house = production_context['player_house']
    production_house = production_context['production_house']
    captured_production_houses = _production_house_types(
        combined, production_owner_houses
    )
    access_owner_houses = tuple(dict.fromkeys((
        production_house,
        *captured_production_houses,
    )))
    registered_houses = {
        value.casefold()
        for list_name in ('HouseTypes', 'Houses')
        for value in (
            list(installed.get(list_name, {}).values())
            + list(authored.get(list_name, {}).values())
        )
    }
    report = {
        'player_house': player_house,
        'production_house': production_house,
        'acts_like': production_context['acts_like'],
        'shared_hostile_houses': production_context['shared_hostile_houses'],
        'allied_helper_houses': sorted(helper_context['houses']),
        'allied_helper_families': sorted(helper_context['families']),
        'captured_production_houses': list(captured_production_houses),
        'applied': [],
        'skipped': [],
        'map_objects_rewritten': 0,
    }
    if not production_house or production_house.casefold() not in registered_houses:
        report['skipped'].append({
            'unit': '*',
            'reason': 'player_production_house_not_registered',
        })
        return {}, report

    counts_by_unit = {}
    access_units = set()
    assistance_units = set()
    global_counts = Counter()
    for reward in rewards or ():
        unit_id = str(reward.get('unit') or '').upper()
        buff_type = str(reward.get('buff_type') or '').lower()
        if unit_id and reward.get('mission_assistance'):
            assistance_units.add(unit_id)
        if unit_id and reward.get('dta_production_access'):
            access_units.add(unit_id)
            continue
        if (
            reward.get('global_buff')
            and reward.get('dta_global_clone_buff')
            and buff_type in {
                'production', 'cost', 'speed', 'damage', 'reload',
            }
        ):
            global_counts[buff_type] += 1
            continue
        if (
            not unit_id
            or reward.get('global_buff')
            or reward.get('dta_house_modifier')
            or buff_type not in {
                'production', 'cost', 'speed', 'armor', 'health', 'damage',
                'reload', 'range', 'sight', 'ammo', 'passenger_capacity',
                'build_limit', 'cloak', 'sensors', 'self_healing',
            }
        ):
            continue
        counts_by_unit.setdefault(unit_id, Counter())[buff_type] += 1

    catalogue = catalogue_by_id()
    unlimited_units = set()
    if unlimited_hero_units:
        for unit_id, target in catalogue.items():
            if target.get('build_limit', 0) <= 0:
                continue
            values = effective_section(combined, unit_id)
            if (
                (access_randomized and unit_id in access_units)
                or (not access_randomized and _can_player_produce(
                    values, production_house
                ))
            ):
                unlimited_units.add(unit_id)
    if global_counts:
        for unit_id, target in catalogue.items():
            if (
                target.get('category') not in TYPE_LIST_BY_CATEGORY
                or not target.get('rewardable')
                or target.get('duplicate_of')
                or unit_id.startswith('AI')
                or '_AI' in unit_id
            ):
                continue
            values = effective_section(combined, unit_id)
            producible = _can_player_produce(values, production_house)
            if target.get('category') == 'buildings':
                eligible = producible
            elif access_randomized:
                eligible = (
                    unit_id in access_units
                    or (
                        unit_id in ALWAYS_AVAILABLE_MOBILE_IDS
                        and producible
                    )
                )
            else:
                eligible = producible
            if eligible:
                effective_counts = _effective_buff_counts(
                    values, target, global_counts, combined
                )
                if effective_counts:
                    counts_by_unit.setdefault(unit_id, Counter()).update(
                        effective_counts
                    )
    report['global_buffs'] = dict(global_counts)
    occupied = {name.casefold() for name in combined}
    list_offsets = {}
    rules = {}
    for unit_id in sorted(
        set(counts_by_unit) | access_units | unlimited_units
    ):
        target = catalogue.get(unit_id)
        if (
            not target
            or not target.get('rewardable')
            or target.get('category') not in TYPE_LIST_BY_CATEGORY
        ):
            report['skipped'].append({'unit': unit_id, 'reason': 'unsupported_type'})
            continue
        values = effective_section(combined, unit_id)
        if not values:
            report['skipped'].append({'unit': unit_id, 'reason': 'missing_rules'})
            continue

        collision = unit_collision_report(source, unit_id)
        counts = _effective_buff_counts(
            values,
            target,
            counts_by_unit.get(unit_id, Counter()),
            combined,
        )
        production_access = unit_id in access_units
        unlimited_build_limit = unit_id in unlimited_units
        player_mobile_placements = [
            entry for entry in collision['player_placements']
            if entry['section'] in {'Infantry', 'Units', 'Aircraft'}
        ]
        helper_references = _helper_unit_references(
            authored, combined, unit_id, helper_context
        )
        is_harvester = unit_id in {
            item.upper()
            for item in comma_items(
                combined.get('General', {}).get('HarvesterUnit')
            )
        }
        helper_applicable = bool(counts) and any(
            _can_player_produce(values, family)
            or references['placements']
            or references['taskforce_entries']
            for family, references in helper_references.items()
        )
        if (
            counts
            and access_randomized
            and not production_access
            and target.get('category') != 'buildings'
            and unit_id not in ALWAYS_AVAILABLE_MOBILE_IDS
            and unit_id not in assistance_units
        ):
            report['skipped'].append({
                'unit': unit_id,
                'reason': 'buff_without_access',
                'buffs': dict(counts),
            })
            continue
        weapon_collision = bool(
            {'damage', 'range', 'reload'}.intersection(counts)
            and collision['shared_weapon_users']
        )
        identity_collision = bool(
            counts
            and (
                collision['nonplayer_placements']
                or collision['taskforce_references']
                or collision['scripted_references']
            )
        )
        # Every unit-specific reward uses a player production clone. Directly
        # changing an original TechnoType is map-global and cannot guarantee
        # player-only behavior, even when a static collision scan is empty.
        use_clone = (
            bool(counts)
            or production_access
            or unlimited_build_limit
            or identity_collision
            or weapon_collision
        )
        producible = _can_player_produce(values, production_house)
        if production_access and not producible:
            use_clone = True
        placement_only = bool(
            counts
            and player_mobile_placements
            and (
                production_context['shared_hostile_houses']
                or (
                    access_randomized
                    and unit_id in assistance_units
                    and not production_access
                    and unit_id not in ALWAYS_AVAILABLE_MOBILE_IDS
                )
            )
        )
        if (
            use_clone
            and production_context['shared_hostile_houses']
            and not placement_only
        ):
            report['skipped'].append({
                'unit': unit_id,
                'reason': 'production_house_shared_with_hostile_house',
                'production_house': production_house,
                'hostile_houses': production_context['shared_hostile_houses'],
                'collisions': collision['reasons'],
            })
            continue
        if (
            use_clone
            and not producible
            and not production_access
            and not player_mobile_placements
            and not helper_applicable
        ):
            report['skipped'].append({
                'unit': unit_id,
                'reason': 'collision_without_player_production',
                'collisions': collision['reasons'],
            })
            continue
        if not use_clone and not producible and not collision['player_placements']:
            report['skipped'].append({
                'unit': unit_id,
                'reason': 'not_present_or_player_producible',
            })
            continue

        output_id = unit_id
        unit_rules = _unit_overrides(values, counts, target)
        if use_clone:
            output_id = _clone_id(unit_id, 'PLAYER', occupied)
            clone_values = dict(values)
            clone_values.pop('BaseSection', None)
            clone_values.pop('$Inherits', None)
            clone_values.pop('ForbiddenHouses', None)
            try:
                clone_build_limit = int(float(
                    clone_values.get('BuildLimit', 0)
                ))
            except (TypeError, ValueError):
                clone_build_limit = 0
            native_build_limit = int(target.get('build_limit', 0))
            if native_build_limit > 0 and clone_build_limit <= 0:
                clone_values['BuildLimit'] = str(native_build_limit)
            elif production_access and clone_build_limit <= 0:
                for key in list(clone_values):
                    if key.casefold() == 'buildlimit':
                        clone_values.pop(key, None)
            if production_access:
                for key in list(clone_values):
                    if (
                        key.casefold() in {
                            'owner', 'requiredhouses', 'builtat',
                        }
                        or key.casefold().startswith('prerequisite')
                    ):
                        clone_values.pop(key, None)
                clone_values['TechLevel'] = '1'
            if unlimited_build_limit:
                for key in list(clone_values):
                    if key.casefold() == 'buildlimit':
                        clone_values.pop(key, None)
            unit_rules = {
                **clone_values,
                'Image': values.get('Image', unit_id),
                'Owner': ','.join(
                    access_owner_houses
                    if production_access else (production_house,)
                ),
                'RequiredHouses': production_house,
                'CameoPriority': str(_faction_cameo_priority(target)),
                **unit_rules,
            }
            if unit_id == 'MEDIC':
                # Vanilla recognizes only its fixed Medic type. Vinifera's
                # generic healer flag preserves infantry healing when the
                # player receives an isolated Medic clone.
                unit_rules['OmniHealer'] = 'yes'
            if placement_only:
                unit_rules['TechLevel'] = '-1'
            helper_family_fallback_needed = bool(
                buff_allied_helpers
                and production_house in helper_context['families']
            )
            if (
                helper_family_fallback_needed
                and producible
                and (counts or production_access)
                and not placement_only
            ):
                # The player and allied helpers share one ActsLike production
                # mask. Keep the native identity available to AI task forces,
                # but hide it from the human sidebar so only the buffed clone
                # is offered to the player.
                rules.setdefault(unit_id, {})['Buildability'] = 'AIOnly'
            if (
                producible
                and (counts or production_access)
                and not placement_only
                and not helper_family_fallback_needed
            ):
                _add_forbidden_house(
                    rules, unit_id, values, production_house
                )
            list_name = TYPE_LIST_BY_CATEGORY[target['category']]
            list_key = _next_list_key(
                installed, authored, list_name, list_offsets
            )
            rules.setdefault(list_name, {})[list_key] = output_id

        weapon_clones = {}
        if {'damage', 'range', 'reload'}.intersection(counts):
            for weapon_key in WEAPON_KEYS:
                weapon_id = str(values.get(weapon_key) or '').strip()
                if not weapon_id:
                    continue
                marker = weapon_id.casefold()
                clone_id = weapon_clones.get(marker)
                if clone_id is None:
                    weapon_values = effective_section(combined, weapon_id)
                    overrides = _weapon_overrides(weapon_values, counts)
                    if not overrides:
                        continue
                    clone_id = _clone_id(
                        f'{unit_id}_{weapon_id}', 'PLAYER', occupied
                    )
                    cloned_weapon_values = dict(weapon_values)
                    cloned_weapon_values.pop('BaseSection', None)
                    cloned_weapon_values.pop('$Inherits', None)
                    cloned_weapon_values.update(overrides)
                    rules[clone_id] = cloned_weapon_values
                    weapon_list_key = _next_list_key(
                        installed, authored, 'WeaponTypes', list_offsets
                    )
                    rules.setdefault('WeaponTypes', {})[
                        weapon_list_key
                    ] = clone_id
                    weapon_clones[marker] = clone_id
                unit_rules[weapon_key] = clone_id

        linked_route = None
        if use_clone and not is_harvester:
            for link_key, reverse_key in (
                ('DeploysInto', 'UndeploysInto'),
                ('UndeploysInto', 'DeploysInto'),
            ):
                linked_source = str(values.get(link_key) or '').strip()
                if linked_source.casefold() in {'', 'none'}:
                    continue
                linked_values = effective_section(combined, linked_source)
                linked_target = catalogue.get(linked_source.upper())
                if not linked_values or not linked_target:
                    continue
                linked_output = _clone_id(linked_source, 'PLAYER', occupied)
                linked_rules = dict(linked_values)
                linked_rules.pop('BaseSection', None)
                linked_rules.pop('$Inherits', None)
                linked_rules.pop('ForbiddenHouses', None)
                linked_rules['Image'] = linked_values.get('Image', linked_source)
                linked_rules['Owner'] = ','.join(
                    access_owner_houses
                    if production_access else (production_house,)
                )
                linked_rules['RequiredHouses'] = production_house
                linked_rules['TechLevel'] = '-1'
                linked_counts = Counter({
                    buff_type: count
                    for buff_type, count in counts.items()
                    if buff_type in {
                        'armor', 'health', 'damage', 'reload', 'range',
                        'sight', 'cloak', 'sensors', 'self_healing',
                    }
                })
                linked_rules.update(
                    _unit_overrides(linked_values, linked_counts, target)
                )
                linked_rules['CameoPriority'] = str(
                    _faction_cameo_priority(linked_target)
                )
                linked_rules[reverse_key] = output_id
                for weapon_key in WEAPON_KEYS:
                    weapon_id = str(linked_values.get(weapon_key) or '').strip()
                    if not weapon_id:
                        continue
                    overrides = _weapon_overrides(
                        effective_section(combined, weapon_id), linked_counts
                    )
                    if not overrides:
                        continue
                    linked_weapon = _clone_id(
                        f'{linked_source}_{weapon_id}', 'PLAYER', occupied
                    )
                    linked_weapon_values = dict(
                        effective_section(combined, weapon_id)
                    )
                    linked_weapon_values.pop('BaseSection', None)
                    linked_weapon_values.pop('$Inherits', None)
                    linked_weapon_values.update(overrides)
                    rules[linked_weapon] = linked_weapon_values
                    weapon_list_key = _next_list_key(
                        installed, authored, 'WeaponTypes', list_offsets
                    )
                    rules.setdefault('WeaponTypes', {})[
                        weapon_list_key
                    ] = linked_weapon
                    linked_rules[weapon_key] = linked_weapon
                rules[linked_output] = linked_rules
                list_name = TYPE_LIST_BY_CATEGORY[linked_target['category']]
                list_key = _next_list_key(
                    installed, authored, list_name, list_offsets
                )
                rules.setdefault(list_name, {})[list_key] = linked_output
                unit_rules[link_key] = linked_output
                linked_route = {
                    'source_type': linked_source.upper(),
                    'output_type': linked_output,
                    'link': link_key,
                }
                break

        helper_original_safe = bool(
            helper_family_fallback_needed
            and not collision['nonplayer_placements']
            and not collision['taskforce_references']
            and not collision['scripted_references']
        )
        if helper_original_safe:
            helper_original_values = _unit_overrides(values, counts, target)
            for weapon_key in WEAPON_KEYS:
                if unit_rules.get(weapon_key):
                    helper_original_values[weapon_key] = unit_rules[weapon_key]
            rules.setdefault(unit_id, {}).update(helper_original_values)

        helper_routes = []
        if counts and helper_references:
            for helper_family, references in helper_references.items():
                helper_producible = _can_player_produce(
                    values, helper_family
                )
                if not (
                    helper_producible
                    or references['placements']
                    or references['taskforce_entries']
                ):
                    continue
                helper_houses = sorted(
                    helper_context['families'][helper_family],
                    key=str.casefold,
                )
                if helper_family == production_house and use_clone:
                    helper_output = output_id
                else:
                    helper_output = _clone_id(
                        unit_id,
                        f'HELPER_{helper_family.upper()}',
                        occupied,
                    )
                    helper_values = dict(values)
                    helper_values.pop('BaseSection', None)
                    helper_values.pop('$Inherits', None)
                    helper_values.pop('ForbiddenHouses', None)
                    helper_values.update(_unit_overrides(values, counts, target))
                    for weapon_key in WEAPON_KEYS:
                        if unit_rules.get(weapon_key):
                            helper_values[weapon_key] = unit_rules[weapon_key]
                    helper_values['Image'] = values.get('Image', unit_id)
                    helper_values['Owner'] = helper_family
                    helper_values['RequiredHouses'] = helper_family
                    rules[helper_output] = helper_values
                    list_name = TYPE_LIST_BY_CATEGORY[target['category']]
                    list_key = _next_list_key(
                        installed, authored, list_name, list_offsets
                    )
                    rules.setdefault(list_name, {})[list_key] = helper_output
                rewritten = []
                for reference in (
                    references['placements']
                    + references['taskforce_entries']
                ):
                    source_value = authored.get(
                        reference['section'], {}
                    ).get(reference['key'], '')
                    fields = list(comma_items(source_value))
                    if len(fields) < 2:
                        continue
                    fields[1] = helper_output
                    rules.setdefault(reference['section'], {})[
                        reference['key']
                    ] = ','.join(fields)
                    rewritten.append(reference)
                report['map_objects_rewritten'] += len(rewritten)
                helper_routes.append({
                    'production_house': helper_family,
                    'scenario_houses': helper_houses,
                    'output_type': helper_output,
                    'production_routed': helper_producible,
                    'native_ai_fallback_buffed': helper_original_safe,
                    'references_rewritten': rewritten,
                })

        if not unit_rules and production_access and producible:
            report['applied'].append({
                'unit': unit_id,
                'output_type': unit_id,
                'route': 'already_producible',
                'buffs': dict(counts),
                'production_access': True,
                'collisions': collision['reasons'],
            })
            continue
        if not unit_rules:
            report['skipped'].append({'unit': unit_id, 'reason': 'no_effective_fields'})
            continue
        rules.setdefault(output_id, {}).update(unit_rules)
        rewritten_placements = []
        if counts and use_clone:
            for placement in player_mobile_placements:
                source_value = authored.get(
                    placement['section'], {}
                ).get(placement['key'], '')
                fields = list(comma_items(source_value))
                if len(fields) < 2:
                    continue
                fields[1] = output_id
                rules.setdefault(placement['section'], {})[
                    placement['key']
                ] = ','.join(fields)
                rewritten_placements.append(placement)
            report['map_objects_rewritten'] += len(rewritten_placements)
        report['applied'].append({
            'unit': unit_id,
            'output_type': output_id,
            'category': target.get('category'),
            'route': (
                'player_placement_clone'
                if placement_only
                else 'production_access_clone'
                if use_clone and production_access
                else 'production_clone'
                if use_clone
                else 'original_type'
            ),
            'buffs': dict(counts),
            'production_access': production_access,
            'player_placements_rewritten': rewritten_placements,
            'allied_helper_routes': helper_routes,
            'linked_deploy_route': linked_route,
            'collisions': collision['reasons'],
        })
    _rewrite_building_references(rules, report, catalogue, combined)
    output_by_source = {
        item['unit'].upper(): item['output_type']
        for item in report['applied']
    }
    for refinery_id, refinery_values in combined.items():
        if (
            refinery_values.get('Refinery', '').casefold()
            not in {'yes', 'true', '1'}
            or '_AI' in refinery_id.upper()
        ):
            continue
        free_unit = str(refinery_values.get('FreeUnit') or '').upper()
        harvester_output = output_by_source.get(free_unit)
        if not harvester_output:
            continue
        refinery_output = output_by_source.get(
            refinery_id.upper(), refinery_id
        )
        rules.setdefault(refinery_output, {})['FreeUnit'] = harvester_output
    harvester_sources = {
        item.upper()
        for item in comma_items(
            combined.get('General', {}).get('HarvesterUnit')
        )
    }
    harvester_outputs = []
    for item in report['applied']:
        if item['unit'].upper() not in harvester_sources:
            continue
        harvester_outputs.append(item['output_type'])
        harvester_outputs.extend(
            route['output_type']
            for route in item.get('allied_helper_routes', ())
        )
    if harvester_outputs:
        rules.setdefault('General', {})['HarvesterUnit'] = ','.join(
            dict.fromkeys([
                *comma_items(combined.get('General', {}).get('HarvesterUnit')),
                *harvester_outputs,
            ])
        )
    return rules, report
