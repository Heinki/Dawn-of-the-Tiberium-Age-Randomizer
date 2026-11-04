"""Powered camp outposts with terrain review and non-forced native placement."""

from collections import defaultdict
from copy import deepcopy
from functools import lru_cache
import json
import hashlib
from math import ceil
from pathlib import Path

from randomizer.dta.rules import effective_section, ini_sections, comma_items
from .maps import map_sections
from .placement import foundation
from .terrain import Terrain


FACTION_BUILDINGS = {
    'GDI': ('NUK2', 'PYLE', 'TDPROC', 'HQ', 'WEAP', 'GHPAD', 'FIX', 'GFACT'),
    'Nod': ('NUK2', 'HAND', 'TDPROC', 'HQ', 'AFLD', 'NHPAD', 'FIX', 'NFACT'),
    'Allies': ('RAAPWR', 'RATENT', 'RAPROC', 'RADOME', 'AWEAP', 'AHPAD', 'RAFIX', 'AFACT'),
    'Soviet': ('RAAPWR', 'RABARR', 'RAPROC', 'SDOME', 'SWEAP', 'SHPAD', 'RAFIX', 'SFACT'),
}
FACTION_DEFENSES = {
    'GDI': ('TWR', 'ATWR'),
    'Nod': ('GUN', 'SAM', 'OBLI'),
    'Allies': ('RAPBOX', 'RAGUN', 'RAHBOX', 'RAAGUN'),
    'Soviet': ('RAFTUR', 'RASAM', 'RATSLA'),
}


def outpost_buildings(country, rank, *, perimeter=False):
    """Cumulative grants; rank six retains two of every native defense type."""
    generator, barracks, refinery, radar, factory, helipad, repair, yard = FACTION_BUILDINGS[country]
    defenses = FACTION_DEFENSES[country]
    buildings = [barracks]
    if rank >= 2:
        buildings.append(refinery)
    if rank >= 3:
        buildings.append(radar)
    if rank >= 4:
        buildings.append(factory)
    if rank >= 5:
        buildings.extend((helipad, repair))
    if rank >= 6:
        buildings.append(yard)
    towers = [defenses[0], defenses[0]]
    if rank >= 3:
        # GDI's advanced tower also supplies its native air defense.
        towers.append(defenses[-1] if country == 'Allies' else defenses[1])
    if rank >= 4:
        towers.extend(kind for kind in defenses if kind not in towers)
    if rank >= 6:
        towers = ([kind for _ in range(12 // len(defenses)) for kind in defenses]
                  if perimeter else [kind for kind in defenses for _ in range(2)])
    return generator, buildings, towers


def plan_outposts(root, definition, country, rank, power_percent, *, version=5):
    """Return independent frozen layouts; reuse expensive installed terrain decoding."""
    planner = _plan_compact_outposts if version >= 6 else _plan_outposts
    return deepcopy(planner(
        str(Path(root).resolve()), json.dumps(definition, sort_keys=True),
        country, rank, power_percent,
    ))


@lru_cache(maxsize=96)
def _plan_compact_outposts(root, definition_json, country, rank, power_percent):
    from .catalogue import installed_rules_registry
    from .formations import context, compound, footprint

    definition = json.loads(definition_json)
    _, rules = installed_rules_registry()
    terrain, art, occupied, _ = context(root, definition, rules)
    generator, requested_production, defenses = outpost_buildings(country, rank, perimeter=True)
    layouts = []
    for camp in definition['camps']:
        # Reserve the crate approaches, without cutting the entire compound
        # into four disconnected quadrants as the former cross reservation did.
        center = camp['position']
        best = None
        production = list(requested_production)
        omitted = []
        while production:
            demand = sum(max(0, -int(rules[k].get('Power', '0'))) for k in production + defenses)
            output = round(int(rules[generator]['Power']) * (100 + power_percent) / 100)
            count = max(1, ceil(demand / output))
            best = compound(terrain, rules, art, [*([generator] * count), *production],
                            defenses, center, occupied, maximum_radius=11, shifts=4)
            if best is not None:
                break
            omitted.insert(0, production.pop())
        if best is None:
            # A narrow crate clearing can border a suitable nearby plateau.
            # Move the whole small compound together, never individual buildings.
            production = requested_production[:1]
            demand = sum(max(0, -int(rules[k].get('Power', '0'))) for k in production + defenses)
            count = max(1, ceil(demand / output))
            best = compound(terrain, rules, art, [*([generator] * count), *production],
                            defenses, center, occupied, maximum_radius=11, shifts=8)
            omitted = requested_production[1:]
        if best is None:
            layouts.append({'structures': [], 'omitted': [*requested_production, *defenses],
                            'power_output': 0, 'power_demand': 0, 'compact': True})
            continue
        for entry in best['structures']:
            occupied.update(footprint(entry['type'], entry['position'], rules, art))
        structures = best['structures']
        layouts.append({'structures': structures, 'omitted': omitted,
                        'power_output': sum(max(0, round(int(rules[e['type']].get('Power', '0'))
                                                * (100 + power_percent) / 100)) for e in structures),
                        'power_demand': sum(max(0, -int(rules[e['type']].get('Power', '0'))) for e in structures),
                        'compact': True, 'radius': best['radius']})
    return layouts


@lru_cache(maxsize=96)
def _plan_outposts(root, definition_json, country, rank, power_percent):
    from .catalogue import installed_rules_registry

    definition = json.loads(definition_json)
    _, rules = installed_rules_registry()
    source = map_sections(root, definition)
    terrain = Terrain(source)
    raw_art = ini_sections(Path(root) / 'INI/Art.ini')
    art = {k.casefold(): effective_section(raw_art, k) for k in raw_art}
    occupied = set(terrain.objects)

    def cells(kind, x, y):
        return {(x + dx, y + dy) for dx, dy in foundation(
            {'Image': kind, **rules[kind]}, art,
        )}

    for value in source.get('Structures', {}).values():
        fields = value.split(',')
        occupied.update(cells(fields[1], int(fields[3]), int(fields[4])))
    for category in ('Units', 'Infantry', 'Aircraft'):
        for value in source.get(category, {}).values():
            fields = value.split(',')
            occupied.add((int(fields[3]), int(fields[4])))
    objective = definition['protected_building']
    occupied.update(cells(objective['type'], **objective['position']))
    for layout in definition['perk_layouts'].values():
        for slot in layout['slots']:
            occupied.update((slot['x'] + dx, slot['y'] + dy)
                            for dx in range(slot['width']) for dy in range(slot['height']))
        occupied.update((p['x'], p['y']) for p in layout['army'])
        p = layout['arrival']
        occupied.update((p['x'] + dx, p['y'] + dy) for dx in range(-3, 4) for dy in range(-2, 3))
        p = layout['controller']
        occupied.add((p['x'], p['y']))
    for camp in definition['camps']:
        occupied.update((p['x'], p['y']) for p in [camp['position'], *camp['guard_positions']])
        p = camp['position']
        # Preserve crossing approach lanes through every camp instead of
        # encircling its crate with otherwise individually valid foundations.
        occupied.update((p['x'] + dx, p['y'] + dy)
                        for dx in range(-24, 25) for dy in range(-24, 25)
                        if abs(dx) <= 1 or abs(dy) <= 1)
    for number in [definition['player_waypoint'], *definition['allied_waypoints'], *definition['enemy_waypoints']]:
        value = int(source['Waypoints'][str(number)])
        x, y = value % 1000, value // 1000
        radius = 20 if number in definition['enemy_waypoints'] else 10
        occupied.update((x + dx, y + dy) for dx in range(-radius, radius + 1)
                        for dy in range(-radius, radius + 1))

    generator, production, defenses = outpost_buildings(country, rank)
    demand = sum(max(0, -int(rules[k].get('Power', '0'))) for k in production + defenses)
    output = round(int(rules[generator]['Power']) * (100 + power_percent) / 100)
    generators = max(1, ceil(demand / output))
    layouts = []
    for camp in definition['camps']:
        center = camp['position']
        candidates = [(center['x'] + dx, center['y'] + dy)
                      for dx in range(-22, 23) for dy in range(-22, 23)]
        candidates.sort(key=lambda p: ((p[0] - center['x']) ** 2 + (p[1] - center['y']) ** 2, p))
        placed, omitted = {}, []
        requested = [*([generator] * generators), *production, *defenses]
        # Protect the powered barracks promised at every rank, then allocate
        # large production foundations before small towers on cliff maps.
        order = sorted(range(len(requested)), key=lambda i: (
            0 if requested[i] == generator else 1 if i == generators else 2,
            -len(cells(requested[i], 0, 0)), i,
        ))
        for index in order:
            kind = requested[index]
            for x, y in candidates:
                footprint = cells(kind, x, y)
                # A full-cell apron keeps entrances, factory exits and walking
                # lanes free of every other planned foundation and source object.
                apron = {(px + dx, py + dy) for px, py in footprint
                         for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
                if terrain.clear(apron, occupied=occupied):
                    placed[index] = {'type': kind, 'position': {'x': x, 'y': y}}
                    occupied.update(footprint)
                    break
            else:
                omitted.append(kind)
        structures = [placed[i] for i in sorted(placed)]
        power = sum(max(0, round(int(rules[s['type']].get('Power', '0'))
                                 * (100 + power_percent) / 100)) for s in structures)
        load = sum(max(0, -int(rules[s['type']].get('Power', '0'))) for s in structures)
        # A cramped site must never emit more consumption than it can supply.
        while load > power:
            entry = structures.pop()
            omitted.append(entry['type'])
            load -= max(0, -int(rules[entry['type']].get('Power', '0')))
        layouts.append({'structures': structures, 'omitted': omitted,
                        'power_output': power, 'power_demand': load})
    return layouts


def _building_index(writer, kind):
    kinds = list(dict.fromkeys([*writer.rules['BuildingTypes'].values(),
                              *writer.sections.get('BuildingTypes', {}).values()]))
    return kinds.index(kind)


def prepare_outpost(writer, plan, camp, player_aliases, finished, markers=None):
    """Generate a one-time, collector-owned deployment with safe occupancy retries."""
    from .engine import _action, _set_local, coalition, FRIENDLY_ALIASES

    layout = camp.get('outpost')
    if not layout:
        return {}, {}
    if layout.get('after_recovery'):
        return _prepare_deferred_outpost(writer, plan, camp, player_aliases, finished)
    if layout.get('compact'):
        return _prepare_claimable_outpost(writer, plan, camp, player_aliases, finished, markers)
    recipient = writer.flag(camp['id'] + ' outpost recipient')
    friends = coalition(plan)
    # Helper-collected camps already route their rewards to the human host.
    humans = len(plan.get('coop_players', [])) or 1
    extra_aliases = defaultdict(list)
    previous = None
    for index, entry in enumerate(layout['structures']):
        native = entry['type']
        source = player_aliases[native]
        alias = writer.key()
        row = dict(writer.sections[source])
        row.update(TechLevel='-1', BuildLimit='0', AllowedToStartInMultiplayer='no',
                   Capturable='no', Unsellable='yes', UndeploysInto='none')
        # Direct creation should use a normal refinery's native free collector,
        # not the placement-only starting-refinery clone that suppresses it.
        writer.sections[alias] = row
        writer.register('BuildingTypes', alias)
        extra_aliases[source].append(alias)
        type_index = _building_index(writer, alias)
        waypoint = 100 + next(i for i, c in enumerate(plan['map']['camps']) if c['id'] == camp['id']) * 32 + index
        if index >= 32:
            raise ValueError('A camp outpost exceeds its reserved waypoint range.')
        p = entry['position']
        writer.put('Waypoints', waypoint, p['y'] * 1000 + p['x'])
        complete = writer.flag(camp['id'] + f' outpost building {index}')
        for seat in range(humans):
            wp = friends[seat][2]
            events = [(13, 0, 5), (71, 3, recipient, seat + 1),
                      (37, 0, complete), (37, 0, finished)]
            if previous is not None:
                events.append((36, 0, previous))
            # TriggerRect.X is the BuildingTypes heap index, Y=0 disables
            # forced placement. Unlimbo rejects occupied foundations, including
            # friendly/enemy units; retry until the actual building exists.
            create = _action(109, 50 + wp, extra=type_index, waypoint=waypoint)
            attempt, _ = writer.trigger(
                camp['id'] + f' outpost place {index}:{seat}', events, [create],
                persistence=2, owner=FRIENDLY_ALIASES[seat],
            )
            writer.trigger(
                camp['id'] + f' outpost placed {index}:{seat}',
                [(32, 0, type_index), (71, 3, recipient, seat + 1),
                 (37, 0, complete), (37, 0, finished)],
                [_action(56, complete), _action(54, trigger=attempt)],
                owner=FRIENDLY_ALIASES[seat],
            )
        if int(writer.rules[native].get('Power', '0')) > 0:
            previous = complete
    pickups = {}
    for seat in range(humans):
        pickups[seat] = [_set_local(recipient, seat + 1), writer.message(
            camp['display_name'] + ': outpost deploying; keep nearby building tiles clear.'
            + (f' {len(layout["omitted"])} structures omitted for terrain.' if layout['omitted'] else '')
        )]
    return pickups, extra_aliases


def _prepare_deferred_outpost(writer, plan, camp, player_aliases, finished):
    """Create nothing until pickup; blocked foundations retry without force."""
    from .engine import _action, _set_local, coalition, FRIENDLY_ALIASES

    layout = camp['outpost']
    humans = len(plan.get('coop_players', [])) or 1
    if not layout['structures']:
        return {seat: [writer.message(camp['display_name'] + ': no protected outpost fits this site.')]
                for seat in range(humans)}, {}
    recipient = writer.flag(camp['id'] + ' outpost recipient')
    allowed = {*FACTION_BUILDINGS[plan['player_country']], *FACTION_DEFENSES[plan['player_country']]}
    aliases = defaultdict(list)
    bindings = getattr(writer, '_deferred_outpost_bindings', None)
    if bindings is None:
        bindings = writer._deferred_outpost_bindings = []
    generators_ready = None
    camp_index = next(i for i, c in enumerate(plan['map']['camps']) if c['id'] == camp['id'])
    for index, entry in enumerate(layout['structures']):
        native = entry['type']
        if native not in allowed:
            raise ValueError('Outpost building does not belong to the player faction: ' + native)
        source = player_aliases[native]
        row = dict(writer.sections[source])
        if row.get('Image', native) != writer.rules[native].get('Image', native):
            raise ValueError('Outpost building alias has the wrong faction art: ' + native)
        alias = writer.key()
        row.update(TechLevel='-1', BuildLimit='0', Capturable='no', Unsellable='yes',
                   UndeploysInto='none', AIBuildThis='no', AllowedToStartInMultiplayer='no')
        # Keep the ordinary native FreeUnit on refineries: construction grants
        # the matching collector exactly once, after the refinery is deployed.
        writer.sections[alias] = row
        writer.register('BuildingTypes', alias)
        aliases[source].append(alias)
        if index >= 32:
            raise ValueError('A camp outpost exceeds its reserved waypoint range.')
        waypoint = 100 + camp_index * 32 + index
        position = entry['position']
        writer.put('Waypoints', waypoint, position['y'] * 1000 + position['x'])
        complete = writer.flag(camp['id'] + f' outpost building {index}')
        for seat, (_, _, wp) in enumerate(coalition(plan)[:humans]):
            events = [(13, 0, 1), (71, 3, recipient, seat + 1),
                      (37, 0, complete), (37, 0, finished)]
            if generators_ready is not None:
                events.append((36, 0, generators_ready))
            attempt, _ = writer.trigger(
                camp['id'] + f' outpost deploy {index}:{seat}', events,
                [_action(109, 50 + wp, extra=-1, waypoint=waypoint)],
                persistence=2, owner=FRIENDLY_ALIASES[seat],
            )
            confirmed, _ = writer.trigger(
                camp['id'] + f' outpost deployed {index}:{seat}',
                [(32, 0, -1), (71, 3, recipient, seat + 1),
                 (37, 0, complete), (37, 0, finished)],
                [_action(56, complete), _action(54, trigger=attempt)],
                owner=FRIENDLY_ALIASES[seat],
            )
            bindings.append((alias, attempt, confirmed))
        if int(writer.rules[native].get('Power', '0')) > 0:
            generators_ready = complete
    pickups = {seat: [_set_local(recipient, seat + 1), writer.message(
        camp['display_name'] + ': outpost deploying; keep building positions clear.'
        + (' Production reduced to keep this site protected.' if layout['omitted'] else '')
    )] for seat in range(humans)}
    return pickups, aliases


@lru_cache(maxsize=4)
def _reviewed_native_building_prefix(root, registration):
    """Use the native heap observed for the reviewed DTA runtime, not INI length.

    DTA's initial Rules processing reports 501 building types for this exact
    runtime/registration, although only 498 are explicitly listed. Unknown
    combinations must be reviewed instead of silently granting foreign tech.
    """
    root = Path(root)
    binary = tuple(hashlib.sha256((root / name).read_bytes()).hexdigest()
                   for name in ('game.exe', 'Vinifera.dll'))
    reviewed = {
        ('554dedfdae3948e50e61b0058689b8a265ae40908cb55fae31e6f05e0e549a23',
         '0a12176636e4f6aab7bf05651bbad64bf95cf4c76a5759fecfa115bfead5d051',
         '12025e116c95679841670789c0684584da5f914c8f96dfba19100ab7e1e900f9'): 501,
    }
    key = (*binary, registration)
    if key not in reviewed:
        raise ValueError('Forward Outposts requires a reviewed native building registry for this DTA/Vinifera installation.')
    return reviewed[key]


def finalize_deferred_outposts(writer):
    """Bind creation and existence events against final emitted native type order."""
    from randomizer.maps.ini import section_value_map_preserve, merge_ini_section_values

    bindings = getattr(writer, '_deferred_outpost_bindings', ())
    if not bindings:
        return
    rules = writer.rules
    payload = {'building_types': list(rules['BuildingTypes'].items()),
               'general': rules['General'], 'ai': rules['AI'],
               'deploys_into': {k: v['DeploysInto'] for k, v in rules.items() if v.get('DeploysInto')}}
    signature = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    prefix = _reviewed_native_building_prefix(str(writer.root), signature)
    seen = {k.casefold() for k in rules['BuildingTypes'].values()}
    indices = {}
    for kind in section_value_map_preserve(writer.lines, 'BuildingTypes').values():
        if kind.casefold() not in seen:
            seen.add(kind.casefold())
            indices[kind] = prefix + len(indices)
    actions = section_value_map_preserve(writer.lines, 'Actions')
    events = section_value_map_preserve(writer.lines, 'Events')
    edits = {'Actions': {}, 'Events': {}}
    for alias, attempt, confirmed in bindings:
        index = indices[alias]
        action = actions[attempt].split(',')
        event = events[confirmed].split(',')
        action[4] = event[3] = str(index)
        edits['Actions'][attempt] = ','.join(action)
        edits['Events'][confirmed] = ','.join(event)
    merge_ini_section_values(writer.lines, edits)


def _prepare_claimable_outpost(writer, plan, camp, player_aliases, finished, markers):
    """Named preplaced types avoid native heap-index drift in trigger action 109."""
    from .engine import _action, _set_local, coalition

    layout = camp['outpost']
    if not layout['structures']:
        return {seat: [writer.message(camp['display_name'] + ': no protected outpost fits this site.')]
                for seat in range(len(plan.get('coop_players', [])) or 1)}, {}
    recipient = writer.flag(camp['id'] + ' outpost recipient')
    humans = len(plan.get('coop_players', [])) or 1
    transfers = []
    previous = '<none>'
    for seat, (_, _, wp) in enumerate(coalition(plan)[:humans]):
        trigger, tag = writer.trigger(
            camp['id'] + ' outpost claimed ' + str(seat),
            [(71, 3, recipient, seat + 1), (37, 0, finished)],
            [_action(14, 50 + wp)], linked=previous,
        )
        previous = trigger
        transfers.append(tag)
    aliases = defaultdict(list)
    allowed = {*FACTION_BUILDINGS[plan['player_country']], *FACTION_DEFENSES[plan['player_country']]}
    for index, entry in enumerate(layout['structures']):
        native = entry['type']
        if native not in allowed:
            raise ValueError('Outpost building does not belong to the player faction: ' + native)
        source = player_aliases[native]
        alias = writer.key()
        row = dict(writer.sections[source])
        if row.get('Image', native) != writer.rules[native].get('Image', native):
            raise ValueError('Outpost building alias has the wrong faction art: ' + native)
        row.update(TechLevel='-1', BuildLimit='0', Capturable='no', Unsellable='yes',
                   UndeploysInto='none', FreeUnit='none', AIBuildThis='no')
        writer.sections[alias] = row
        writer.register('BuildingTypes', alias)
        _, tag = writer.trigger(
            camp['id'] + f' unclaimed structure lost {index}',
            [(48, 0, 0), (71, 3, recipient, 0), (37, 0, finished)],
            [_action(4, team=markers[f'outpost_lost:{camp["id"]}:{index}'])],
            linked=previous,
        )
        writer.place('Structures', alias, entry['position'], tag=tag, owner='Special')
        aliases[source].append(alias)
    pickups = {}
    for seat in range(humans):
        pickups[seat] = [_set_local(recipient, seat + 1), writer.message(
            camp['display_name'] + ': faction outpost claimed.'
            + (' Production reduced to keep this site protected.' if layout['omitted'] else '')
        )]
        refinery = FACTION_BUILDINGS[plan['player_country']][2]
        if any(e['type'] == refinery for e in layout['structures']):
            harvester = 'TDHARV' if plan['player_country'] in ('GDI', 'Nod') else 'RAHARV'
            wp = coalition(plan)[seat][2]
            camp_wp = 30 + next(i for i, c in enumerate(plan['map']['camps']) if c['id'] == camp['id'])
            team = writer.team('Outpost collector', [{'type': player_aliases[harvester], 'count': 1}],
                               wp, camp_wp, attack=False)
            script = writer.sections[team]['Script']
            writer.put(script, '0', '11,9')
            pickups[seat].append(writer.reinforce(team))
    return pickups, aliases


def route_outpost_factories(writer, extra_aliases):
    """Preserve production, docking and prerequisites for placement-only copies."""
    if not extra_aliases:
        return
    groups = {}
    for source, copies in extra_aliases.items():
        group = 'DFFOP_' + source
        groups[source] = group
        writer.put('PrerequisiteGroups', group, ','.join([source, *copies]))
    for kind, row in list(writer.sections.items()):
        if 'Prerequisite' in row:
            row['Prerequisite'] = ','.join(groups.get(k, k) for k in comma_items(row['Prerequisite']))
        for field in ('BuiltAt', 'Dock'):
            if field in row:
                items = comma_items(row[field])
                row[field] = ','.join(dict.fromkeys([*items, *[v for k in items for v in extra_aliases.get(k, [])]]))
    for section in ('PrerequisiteGroups', 'General'):
        combined = {**writer.rules.get(section, {}), **writer.sections.get(section, {})}
        for key, value in combined.items():
            if section == 'General' and not (key.startswith('Prerequisite') or key in ('BuildConst', 'BuildRefinery', 'PadAircraft')):
                continue
            items = comma_items(value)
            additions = [v for k in items for v in extra_aliases.get(k, [])]
            if additions:
                writer.put(section, key, ','.join(dict.fromkeys([*items, *additions])))
