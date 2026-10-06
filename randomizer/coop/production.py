"""Separate human production masks without changing native Spawn actors.

Vinifera gates RequiredHouses/ForbiddenHouses through HouseClass.ActLike.
Use already registered, non-AI HouseTypes below bit 31 for the humans; copy
the native faction's ownership masks and side, then generate each player's
clones against that mask. Spawn identities, colors, AI countries and authored
placements remain unchanged. Every peer receives the same resulting map.
"""

from randomizer.dta.clones import HOUSE_MASK_FIELDS, unit_specific_buff_rules
from randomizer.dta.rules import (
    ALWAYS_AVAILABLE_MOBILE_IDS, PLAYABLE_FACTIONS, catalogue_by_id,
    comma_items, effective_section, ini_sections, player_unit_rule_overlays,
)

from .catalogue import merge


def player_production_rules(root, mission, sections, loadouts):
    count = mission['coop_player_count']
    if len(loadouts) != count:
        raise ValueError('Every player needs a separate cooperative loadout.')
    installed = ini_sections(root / 'INI' / 'Rules.ini')
    registered = installed.get('Houses', {})
    reserved = {0, 1, 2, 3, 4, 5, *[side for side, _color, _position in
                                  (*mission['coop_allies'], *mission['coop_enemies'])]}
    countries = [(int(index), house) for index, house in registered.items()
                 if str(index).isdigit() and 0 <= int(index) < 31
                 and int(index) not in reserved]
    countries.sort()
    countries = countries[:count]
    if len(countries) != count:
        raise ValueError('DTA lacks enough registered HouseTypes for personal co-op production.')
    faction = PLAYABLE_FACTIONS[mission['coop_side']]
    combined = {name: dict(values) for name, values in installed.items()}
    merge(combined, player_unit_rule_overlays())
    merge(combined, sections)
    side = effective_section(combined, faction).get('Side')
    if not side:
        raise ValueError('Native cooperative faction has no registered side.')
    # HouseTypes are already registered by Rules.ini before map additions.
    # Preserve every authored list entry, including maps listing Spawn1 at 6
    # instead of 50: Vinifera resolves Spawn names to 50–57 specially. Append
    # missing aliases using free INI keys; their runtime bits remain 6–13.
    houses = sections.setdefault('Houses', {})
    next_key = max((int(key) for key in houses if str(key).isdigit()), default=-1) + 1
    for index, house in countries:
        if house not in houses.values():
            houses[str(next_key)] = house
            next_key += 1
        sections[house] = dict(effective_section(combined, faction),
                               ActsLike=str(index), Side=side,
                               Multiplay='yes', MultiplayPassive='no')
    aliases = [house for _index, house in countries]
    # Remove the repurposed aliases from other faction side lists. This keeps
    # voice, sidebar, survivors and factory side checks on the native side.
    for name, value in combined.get('Sides', {}).items():
        members = [house for house in comma_items(value) if house not in aliases]
        if name == side:
            members.extend(aliases)
        sections.setdefault('Sides', {})[name] = ','.join(members)
    # Inherit the original faction's build permissions, including generic
    # factory routes and native MCV/refinery selection, without changing AI.
    for name in combined:
        values = effective_section(combined, name)
        for key, value in values.items():
            if key.casefold() not in HOUSE_MASK_FIELDS:
                continue
            members = list(comma_items(value))
            # An alias formerly belonged to another faction. Its previous
            # membership must not accidentally grant that faction's units.
            members = [member for member in members if member not in aliases]
            if faction.casefold() in {member.casefold() for member in members}:
                members.extend(aliases)
            if ','.join(members) != value:
                sections.setdefault(name, {})[key] = ','.join(members)
    report = {'applied': [], 'skipped': [], 'players': [],
              'map_objects_rewritten': 0, 'player_taskforce_routes': []}
    catalogue = catalogue_by_id()
    for slot, ((index, house), loadout) in enumerate(zip(countries, loadouts)):
        randomize = bool(loadout.get('randomize_access', True))
        # Hide randomized native types for this human only. Enemy production
        # and the other players' personal clones keep their own permissions.
        if randomize:
            for unit, target in catalogue.items():
                if (target.get('category') not in {'infantry', 'vehicles', 'aircraft', 'defenses'}
                        or not target.get('rewardable') or unit.startswith('AI')
                        or unit in ALWAYS_AVAILABLE_MOBILE_IDS):
                    continue
                _forbid(sections, combined, unit, house)
            _forbid(sections, combined, '2TNKMSL', house)
        context = {'player_house': '__COOP_PRODUCTION_ONLY__',
                   'production_house': house, 'acts_like': index,
                   'original_production_house': faction, 'shared_hostile_houses': []}
        rules, player = unit_specific_buff_rules(
            mission, loadout['rewards'], access_randomized=randomize,
            production_context=context, source_sections=sections,
            human_only_production=True, isolated_production_mask=True,
            shop_global_buff_levels=loadout['settings'].get('shop_global_buff_levels'),
        )
        if player['map_objects_rewritten'] or player['player_taskforce_routes']:
            raise ValueError('Co-op rewards attempted to rewrite authored actors.')
        merge(sections, rules)
        player.update(slot=slot, credit_bonus=loadout['credit_bonus'])
        report['players'].append(player)
        for key in ('applied', 'skipped'):
            report[key].extend(dict(item, slot=slot) for item in player[key])
    return [index for index, _house in countries], report


def _forbid(sections, installed, unit, house):
    values = effective_section(installed, unit)
    current = effective_section(sections, unit)
    houses = list(comma_items(current.get('ForbiddenHouses', values.get('ForbiddenHouses'))))
    if house not in houses:
        houses.append(house)
    sections.setdefault(unit, {})['ForbiddenHouses'] = ','.join(houses)
