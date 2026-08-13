"""Vinifera production clones for player-only unit-specific buffs."""

from collections import Counter
from hashlib import sha1

from randomizer.config.tuning import stacking_multiplier
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
}
WEAPON_KEYS = ('Primary', 'Secondary', 'ElitePrimary', 'EliteSecondary')


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
    if len(candidate) > 31:
        digest = sha1(candidate.encode('ascii', errors='ignore')).hexdigest()[:6].upper()
        candidate = f'{source[:20]}_{digest}_{suffix[:3]}'[:31]
    base = candidate
    counter = 2
    while candidate.casefold() in occupied:
        tail = str(counter)
        candidate = f'{base[:31-len(tail)]}{tail}'
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


def _unit_overrides(values, counts):
    overrides = {}
    if counts['production']:
        try:
            base = float(values.get('BuildTimeMultiplier', 1.0))
        except (TypeError, ValueError):
            base = 1.0
        overrides['BuildTimeMultiplier'] = _number(
            base * stacking_multiplier('production', counts['production'])
        )
    if counts['cost']:
        scaled = _scaled_integer(
            values.get('Cost'), stacking_multiplier('cost', counts['cost'])
        )
        if scaled is not None:
            overrides['Cost'] = str(scaled)
    if counts['speed']:
        scaled = _scaled_integer(
            values.get('Speed'), stacking_multiplier('speed', counts['speed'])
        )
        if scaled is not None:
            overrides['Speed'] = str(scaled)
    if counts['armor']:
        scaled = _scaled_integer(
            values.get('Strength'),
            1.0 / stacking_multiplier('armor', counts['armor']),
        )
        if scaled is not None:
            overrides['Strength'] = str(scaled)
    return overrides


def _weapon_overrides(values, counts):
    overrides = {}
    if counts['damage']:
        scaled = _scaled_integer(
            values.get('Damage'), stacking_multiplier('damage', counts['damage'])
        )
        if scaled is not None:
            overrides['Damage'] = str(scaled)
    if counts['reload']:
        scaled = _scaled_integer(
            values.get('ROF'), stacking_multiplier('reload', counts['reload'])
        )
        if scaled is not None:
            overrides['ROF'] = str(scaled)
    return overrides


def unit_specific_buff_rules(mission, rewards, access_randomized=False):
    """Build map-local original buffs or player production clones.

    Authored placements, TaskForces, teams, triggers, and scripts are never
    rewritten. When the original identity has any non-player/authored collision,
    only newly produced human units use the clone.
    """
    source = mission_source_path(mission.get('scenario'))
    installed = ini_sections(GAME_ROOT / 'INI' / 'Rules.ini')
    authored = ini_sections(source)
    combined = _merged_sections(installed, authored)
    production_context = _player_production_context(authored)
    player_house = production_context['player_house']
    production_house = production_context['production_house']
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
    for reward in rewards or ():
        unit_id = str(reward.get('unit') or '').upper()
        buff_type = str(reward.get('buff_type') or '').lower()
        if unit_id and reward.get('dta_production_access'):
            access_units.add(unit_id)
            continue
        if (
            not unit_id
            or reward.get('global_buff')
            or reward.get('dta_house_modifier')
            or buff_type not in {'production', 'cost', 'speed', 'armor', 'damage', 'reload'}
        ):
            continue
        counts_by_unit.setdefault(unit_id, Counter())[buff_type] += 1

    catalogue = catalogue_by_id()
    occupied = {name.casefold() for name in combined}
    list_offsets = {}
    rules = {}
    for unit_id in sorted(set(counts_by_unit) | access_units):
        target = catalogue.get(unit_id)
        if not target or target.get('category') not in TYPE_LIST_BY_CATEGORY:
            report['skipped'].append({'unit': unit_id, 'reason': 'unsupported_type'})
            continue
        values = effective_section(combined, unit_id)
        if not values:
            report['skipped'].append({'unit': unit_id, 'reason': 'missing_rules'})
            continue

        collision = unit_collision_report(source, unit_id)
        counts = counts_by_unit.get(unit_id, Counter())
        production_access = unit_id in access_units
        if (
            counts
            and access_randomized
            and not production_access
            and unit_id not in ALWAYS_AVAILABLE_MOBILE_IDS
        ):
            report['skipped'].append({
                'unit': unit_id,
                'reason': 'buff_without_access',
                'buffs': dict(counts),
            })
            continue
        weapon_collision = bool(
            {'damage', 'reload'}.intersection(counts)
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
            or identity_collision
            or weapon_collision
        )
        producible = _can_player_produce(values, production_house)
        if production_access and not producible:
            use_clone = True
        if use_clone and production_context['shared_hostile_houses']:
            report['skipped'].append({
                'unit': unit_id,
                'reason': 'production_house_shared_with_hostile_house',
                'production_house': production_house,
                'hostile_houses': production_context['shared_hostile_houses'],
                'collisions': collision['reasons'],
            })
            continue
        if use_clone and not producible and not production_access:
            report['skipped'].append({
                'unit': unit_id,
                'reason': 'collision_without_player_production',
                'collisions': collision['reasons'],
            })
            continue
        if (
            use_clone
            and not production_access
            and (
                values.get('DeploysInto', '').casefold() not in {'', 'none'}
                or values.get('UndeploysInto', '').casefold() not in {'', 'none'}
            )
        ):
            report['skipped'].append({
                'unit': unit_id,
                'reason': 'linked_deploy_identity_not_routed',
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
        unit_rules = _unit_overrides(values, counts)
        if use_clone:
            output_id = _clone_id(unit_id, 'PLAYER', occupied)
            clone_values = dict(values)
            clone_values.pop('BaseSection', None)
            clone_values.pop('ForbiddenHouses', None)
            if production_access:
                for key in list(clone_values):
                    if (
                        key.casefold() in {
                            'owner', 'requiredhouses', 'builtat', 'buildlimit',
                        }
                        or key.casefold().startswith('prerequisite')
                    ):
                        clone_values.pop(key, None)
                clone_values['TechLevel'] = '1'
            unit_rules = {
                **clone_values,
                'Image': values.get('Image', unit_id),
                'Owner': production_house,
                'RequiredHouses': production_house,
                **unit_rules,
            }
            if producible and (counts or production_access):
                existing_forbidden = list(comma_items(values.get('ForbiddenHouses')))
                if production_house.casefold() not in {
                    item.casefold() for item in existing_forbidden
                }:
                    existing_forbidden.append(production_house)
                rules.setdefault(unit_id, {})['ForbiddenHouses'] = ','.join(
                    existing_forbidden
                )
            list_name = TYPE_LIST_BY_CATEGORY[target['category']]
            list_key = _next_list_key(
                installed, authored, list_name, list_offsets
            )
            rules.setdefault(list_name, {})[list_key] = output_id

        weapon_clones = {}
        if {'damage', 'reload'}.intersection(counts):
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
                    cloned_weapon_values.update(overrides)
                    rules[clone_id] = cloned_weapon_values
                    weapon_clones[marker] = clone_id
                unit_rules[weapon_key] = clone_id

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
        report['applied'].append({
            'unit': unit_id,
            'output_type': output_id,
            'route': (
                'production_access_clone'
                if use_clone and production_access
                else 'production_clone'
                if use_clone
                else 'original_type'
            ),
            'buffs': dict(counts),
            'production_access': production_access,
            'collisions': collision['reasons'],
        })
    return rules, report
