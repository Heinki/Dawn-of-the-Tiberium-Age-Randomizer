"""Native skirmish teams, house bonuses, and terrain-checked starting grants."""

from collections import Counter, deque
from copy import deepcopy
from functools import lru_cache
import hashlib
import math
import os
from pathlib import Path
import re
import tempfile

from randomizer.coop.catalogue import inherited_sections, merge
from randomizer.dta.rules import ini_sections, effective_section, comma_items
from randomizer.maps.ini import IniLines
from randomizer.maps.hooks import append_hook_team
from randomizer.skirmish import discover_maps, _dta_naval_options, _serialize
from randomizer.final_fortress.engine import MapWriter, _action
from randomizer.final_fortress.terrain import Terrain, BUILDABLE_TILES
from randomizer.final_fortress.placement import foundation
from .catalogue import FACTIONS, DIFFICULTIES, RULES_VERSION, BATTLE_CREDITS_PER_RANK, AIRCRAFT_BUILDINGS
from .teams import HOUSE_ALIASES, participants
from .players import human


# Flat roads, floors and platform LAT from the installed DTA theater registries.
# Fortress's deliberately narrow placement palette omits ordinary skirmish
# surfaces. Impassable floors, equipment, platform edges, ramps and water stay
# excluded; foundations and same-height access remain checked separately.
CONQUEST_GROUND = {
    'temperate': BUILDABLE_TILES['temperate'] | frozenset({
        *range(196, 231), *range(1082, 1183), *range(1972, 2339),
        *range(3164, 3461), *range(4382, 4481), *range(9133, 9430),
        *range(789, 806),       # Platform LAT and platform/dirt transitions.
        *range(6865, 6885),     # Tiled and brick floors (not impassable floors).
        *range(6955, 7054),     # Tiled/brick floor transitions.
    }),
    'desert': BUILDABLE_TILES['desert'] | frozenset({
        *range(1383, 1581), *range(3595, 3793),
    }),
}


def installation_fingerprint(root):
    digest = hashlib.sha256()
    for relative in ('INI/Rules.ini', 'INI/Enhance.ini', 'INI/Art.ini', 'INI/AI.ini',
                     'INI/MPMaps.ini', 'Resources/SkirmishLobby.ini', 'Vinifera.dll', 'game.exe'):
        path = Path(root) / relative
        digest.update(relative.encode())
        digest.update(path.read_bytes() if path.is_file() else b'<absent>')
    return digest.hexdigest()


@lru_cache(maxsize=2)
def _current_rules(root, signature):
    """Refresh flattened rules when the client regenerates its installed INIs."""
    rows = ini_sections(root / 'INI/Rules.ini')
    merge(rows, ini_sections(root / 'INI/Enhance.ini'))
    return {key: effective_section(rows, key) for key in rows}


def _validate_runtime(root, battle):
    """Check the committed army against today's installation, not its age.

    Client updates and regenerated art files must not invalidate an entire solo
    campaign. Frozen maps, force definitions, house seats and installed types
    still have to match the native adapter before anything is committed.
    """
    for relative in ('game.exe', 'Vinifera.dll', 'LaunchVinifera.dat',
                     'INI/Rules.ini', 'INI/Enhance.ini', 'INI/Art.ini', 'INI/AI.ini',
                     'INI/MPMaps.ini', 'Resources/SkirmishLobby.ini'):
        path = root / relative
        if not path.is_file() or not path.stat().st_size:
            raise ValueError(f'DTA installation is incomplete: {relative}. Repair the game, then retry this battle.')
    signature = tuple((path.stat().st_mtime_ns, path.stat().st_size)
                      for path in (root / 'INI/Rules.ini', root / 'INI/Enhance.ini'))
    rules = _current_rules(root, signature)
    buildings = set(rules.get('BuildingTypes', {}).values())
    mobiles = set(rules.get('VehicleTypes', {}).values()) | set(rules.get('InfantryTypes', {}).values())
    for member in participants(battle):
        loadout, slot = member['loadout'], member['slot']
        country, force = loadout['country'], loadout['force']
        if (rules.get('Houses', {}).get(str(FACTIONS.index(country))) != country or
            rules.get('Houses', {}).get(str(6 + slot)) != HOUSE_ALIASES[slot] or
            rules.get(country, {}).get('Side') not in rules.get('Sides', {})):
            raise ValueError('The installed DTA faction registry is incompatible with this battle. Repair the game, then retry.')
        required = [(kind, mobiles) for kind in (*force['units'], force['collector'])]
        required += [(kind, buildings) for kind in (*force['structures'], force['power_type'])]
        for kind, registry in required:
            if kind not in registry or not rules.get(kind):
                raise ValueError(f'DTA no longer provides the required starting type {kind}. Repair the game, then retry this battle.')
    return deepcopy(rules)


def map_fingerprint(root, source):
    rows = inherited_sections(Path(root), source)
    _dta_naval_options(Path(root), source, rows)
    return hashlib.sha256(_serialize(rows).encode('cp1252')).hexdigest()


def catalogue(root):
    """Offer installed 2–8-start skirmishes with supported native terrain."""
    root = Path(root).resolve()
    result = []
    cache = {}
    for relative, definition in discover_maps(root, cache=cache).items():
        if not 2 <= len(definition['starts']) <= 8:
            continue
        path = Path(definition['path']).resolve()
        rows = inherited_sections(root, path, cache=cache)
        if (any(rows.get(s) for s in ('Triggers', 'TeamTypes', 'AITriggerTypes', 'Houses')) or
            rows.get('Basic', {}).get('IgnoreGlobalAITriggers', 'no').casefold() in ('yes', 'true', '1') or
            rows.get('Map', {}).get('Theater', '').casefold() not in ('temperate', 'desert')):
            continue
        positions = {str(w): [int(rows['Waypoints'][str(w)]) % 1000, int(rows['Waypoints'][str(w)]) // 1000]
                     for w in definition['starts']}
        _dta_naval_options(root, path, rows)
        fingerprint = hashlib.sha256(_serialize(rows).encode('cp1252')).hexdigest()
        result.append(dict(path=relative, name=definition['name'], starts=list(definition['starts']),
                           positions=positions, countries=list(definition['countries']), sha256=fingerprint))
    if not result:
        raise ValueError('No compatible 2–8-player DTA skirmish maps were found.')
    return result, installation_fingerprint(root)


def marker(attempt_id):
    if not isinstance(attempt_id, str) or not re.fullmatch('[0-9a-f]{32}', attempt_id):
        raise ValueError('Invalid Conquest attempt ID.')
    return 'DCQ_' + attempt_id + '_START'


class ConquestWriter(MapWriter):
    def key(self):
        self.counter += 1
        return f'DCQ{self.counter:05X}'


def _clear_house_rosters(writer):
    """Remove the native identities of seats that Conquest reassigns.

    ActsLike changes AI and sidebar identity, but does not revoke Owner or
    RequiredHouses entries. A Soviet using GDI1 must not inherit GDI1's GDI
    refinery or Nod1's infantry when those seats are reassigned.
    """
    aliases = set(HOUSE_ALIASES)
    for kind, native in writer.rules.items():
        for field in ('Owner', 'RequiredHouses', 'ForbiddenHouses'):
            values = comma_items(native.get(field))
            if aliases.intersection(values):
                remaining = [value for value in values if value not in aliases]
                if field == 'RequiredHouses' and not remaining:
                    remaining = ['Neutral']
                writer.put(kind, field, ','.join(remaining))


def _apply_house(writer, loadout, alias, index, *, impossible=False):
    country = loadout['country']
    if writer.rules.get('Houses', {}).get(str(index)) != alias:
        raise ValueError('The installed DTA house registry is incompatible with Conquest.')
    stats, perks = loadout['stats'], loadout['perks']
    row = deepcopy(writer.rules[country])
    # Native ActsLike retains this faction's technology, factories and AI recipes.
    # Separate registered HouseTypes carry each combatant's independent modifiers.
    row.update(ActsLike=str(FACTIONS.index(country)), Multiplay='yes', MultiplayPassive='no')
    factors = {
        'Armor': (1 + stats['health'] / 100) * (1 + stats['armor'] / 100),
        'Firepower': (1 + stats['damage'] / 100) * (1.25 if impossible else 1),
        'ROF': 1 / (1 + stats['reload'] / 100),
        'Groundspeed': 1 + stats['speed'] / 100,
        'Airspeed': 1 + stats['speed'] / 100,
        'BuildTime': 1 - perks.get('production', 0) * .1,
        'Cost': 1 - perks.get('discount', 0) * .1,
    }
    for field, factor in factors.items():
        row[field] = f'{float(row.get(field, "1")) * factor:.8g}'
    writer.sections[alias] = row
    # Native first-ownable lookups also see the selected country identity.
    for kind, native in writer.rules.items():
        for field in ('Owner', 'RequiredHouses', 'ForbiddenHouses'):
            if country in comma_items(native.get(field)):
                current = writer.sections.get(kind, {}).get(field, native[field])
                writer.put(kind, field, ','.join(dict.fromkeys([*comma_items(current), alias])))


def _starting_structure_type(writer, kind, cache, *, template=None, refinery=True):
    """Keep grant buildings' bonuses while suppressing automatic free units."""
    source = template or kind
    if source in cache:
        return cache[source]
    alias = writer.key()
    cache[source] = alias
    native = writer.sections[template] if template else writer.rules[kind]
    writer.sections[alias] = dict(native, Image=native.get('Image', kind),
        FreeUnit='none', TechLevel='-1', BuildLimit='0', AIBuildThis='no')
    writer.register('BuildingTypes', alias)
    group = ('DCQREF_' if refinery else 'DCQGRANT_') + kind
    members = comma_items(writer.sections.get('PrerequisiteGroups', {}).get(group, kind))
    writer.put('PrerequisiteGroups', group, ','.join(dict.fromkeys([*members, alias])))
    for key, values in list(writer.sections.get('PrerequisiteGroups', {}).items()):
        members = comma_items(values)
        if kind in members or source in members:
            writer.put('PrerequisiteGroups', key, ','.join(dict.fromkeys([*members, alias])))
    for target, original in [*writer.rules.items(), *list(writer.sections.items())]:
        values = {**original, **writer.sections.get(target, {})}
        prerequisites = comma_items(values.get('Prerequisite'))
        if kind in prerequisites:
            writer.put(target, 'Prerequisite', ','.join(group if v == kind else v for v in prerequisites))
        docks = list(comma_items(values.get('Dock')))
        if kind in docks:
            writer.put(target, 'Dock', ','.join([*docks, alias]))
    fields = (('AI', 'BuildRefinery'), ('PrerequisiteGroups', 'REFINERY')) if refinery else ()
    for section, field in fields:
        values = writer.sections.get(section, {}).get(field, writer.rules.get(section, {}).get(field, ''))
        writer.put(section, field, ','.join(dict.fromkeys([*comma_items(values), alias])))
    return alias


def _placements(writer, source, sides, *, private_types=None):
    terrain = Terrain(source)
    flat_tiles = CONQUEST_GROUND[terrain.theater]
    raw_art = ini_sections(writer.root / 'INI/Art.ini')
    art = {key.casefold(): effective_section(raw_art, key) for key in raw_art}
    occupied = set(terrain.objects)
    rules = writer.rules
    walls = {i for i, kind in enumerate(rules['OverlayTypes'].values())
             if rules.get(kind, {}).get('Wall', '').casefold() in ('yes', 'true', '1')}

    def cells(kind, x, y):
        return {(x + dx, y + dy) for dx, dy in foundation({'Image': kind, **rules[kind]}, art)}

    for value in source.get('Structures', {}).values():
        row = value.split(',')
        occupied.update(cells(row[1], int(row[3]), int(row[4])))
    for category in ('Units', 'Infantry', 'Aircraft'):
        for value in source.get(category, {}).values():
            row = value.split(',')
            occupied.add((int(row[3]), int(row[4])))
    centers = {}
    # Only occupied seats spawn an MCV. Reserving unused neighboring starts
    # can consume the entire building area on tightly paired city maps.
    for index in sorted({waypoint for _, waypoint in sides}):
        cell = source.get('Waypoints', {}).get(str(index))
        if cell is None:
            continue
        x, y = int(cell) % 1000, int(cell) // 1000
        centers[index] = (x, y)
        occupied.update((x + dx, y + dy) for dx in range(-4, 5) for dy in range(-4, 5))
        # Keep two escape lanes open through any starting production compound.
        occupied.update((x + step, y + width) for step in range(5, 13) for width in (-1, 0, 1))
        occupied.update((x + width, y + step) for step in range(5, 13) for width in (-1, 0, 1))
    refinery_cache, reports = {}, []
    for loadout, waypoint in sides:
        private = (private_types or {}).get(waypoint, {})
        force = loadout['force']
        cx, cy = centers[waypoint]
        height = terrain.heights.get((cx, cy), 0)
        walkable = {(x, y) for x in range(cx - 26, cx + 27) for y in range(cy - 26, cy + 27)
                    if 0 <= x < 512 and 0 <= y < 512 and
                    terrain.heights.get((x, y), 0) == height and
                    terrain.cells.get((x, y), (0, 0, 0))[0] in flat_tiles and
                    terrain.overlays[y * 512 + x] not in walls and
                    (x, y) not in terrain.objects and terrain.bounds.contains({(x, y)}, heights=terrain.heights)}
        connected, pending = set(), deque([(cx, cy)])
        while pending:
            point = pending.popleft()
            if point in connected or point not in walkable:
                continue
            connected.add(point)
            pending.extend((point[0] + dx, point[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        candidates = sorted((p for p in connected if terrain.clear({p}, flat_tiles=flat_tiles)),
                            key=lambda p: ((p[0] - cx)**2 + (p[1] - cy)**2, p))
        if not candidates:
            raise ValueError(f'No connected clear ground near start {waypoint + 1}. Battle remains pending; autobattle is available.')
        structures = Counter(force['structures'])
        balance = sum(float(rules[k].get('Power', '0')) * count for k, count in structures.items())
        # Purchased node generators are extra capacity. Do not replace the
        # minimum power already promised for the node's other buildings.
        balance -= float(rules[force['power_type']].get('Power', '0')) * loadout['perks'].get('node_power', 0)
        if balance < 0:
            output = float(rules[force['power_type']].get('Power', '0'))
            if output <= 0:
                raise ValueError('The selected faction has no valid starting generator.')
            structures[force['power_type']] += math.ceil(-balance / output)
        tag = writer.transfer_tag(waypoint, 'Conquest starting forces')
        placed = []
        # Large foundations first; every building retains an access apron.
        buildings = [k for k, count in structures.items() for _ in range(count)]
        buildings.sort(key=lambda k: -len(cells(k, 0, 0)))
        for kind in buildings:
            for x, y in candidates:
                footprint = cells(kind, x, y)
                apron = {(px + dx, py + dy) for px, py in footprint
                         for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
                if footprint <= connected and terrain.clear(apron, flat_tiles=flat_tiles, occupied=occupied):
                    occupied.update(apron)
                    output = (_starting_structure_type(writer, kind, refinery_cache, template=private.get(kind))
                              if kind in ('TDPROC', 'RAPROC') else private.get(kind, kind))
                    if kind in {*AIRCRAFT_BUILDINGS.values(), 'SHPAD'}:
                        pad = {**rules[kind], **writer.sections.get(output, {})}
                        if pad.get('FreeUnit', 'none').casefold() not in ('none', '<none>', ''):
                            output = _starting_structure_type(writer, kind, refinery_cache, template=private.get(kind), refinery=False)
                    writer.place('Structures', output, {'x': x, 'y': y}, tag=tag)
                    placed.append(dict(type=kind, output_type=output, x=x, y=y))
                    break
            else:
                raise ValueError(f'{kind} cannot fit safely near start {waypoint + 1}. Battle remains pending; autobattle is available.')
        for kind, count in force['units'].items():
            if kind not in rules:
                raise ValueError('Missing DTA starting unit: ' + kind)
            category = 'Infantry' if kind in rules['InfantryTypes'].values() else 'Units'
            for _ in range(count):
                position = next((p for p in candidates if terrain.clear({p}, flat_tiles=flat_tiles, occupied=occupied)), None)
                if position is None:
                    raise ValueError('Starting army cannot fit safely. Battle remains pending; autobattle is available.')
                occupied.add(position)
                writer.place(category, private.get(kind, kind), dict(zip(('x', 'y'), position)), tag=tag,
                             veterancy=0 if kind == force['collector'] else force['veterancy'])
                placed.append(dict(type=kind, output_type=private.get(kind, kind), x=position[0], y=position[1]))
        reports.append(dict(country=loadout['country'], waypoint=waypoint,
                            structures=dict(structures), units=force['units'], placements=placed))
    return reports


def render(root, state, attempt_id, *, game_speed=2, coop_slot=0, endpoints=None):
    """Prepare bytes without touching installed runtime files or campaign saves."""
    from .persistence import validate
    validate(state)
    battle = state['pending']
    if not battle or battle['rules_version'] != RULES_VERSION:
        raise ValueError('No supported Conquest battle is pending.')
    if battle['attacker'] == 'ai' and not human(state, battle['defense']['faction']):
        raise ValueError('AI battles against neutral territories use autobattle.')
    root = Path(root).resolve()
    source = (root / battle['map']['path']).resolve()
    if not source.is_relative_to(root) or not source.is_file():
        raise ValueError('The assigned battle map is missing. Autobattle remains available.')
    if map_fingerprint(root, source) != battle['map']['sha256']:
        raise ValueError('The assigned battle map changed. Autobattle remains available.')
    if state.get('coop'):
        from .network import validate_endpoints
        validate_endpoints(state, endpoints)
    rules = _validate_runtime(root, battle)
    if type(game_speed) is not int or not 0 <= game_speed <= 6:
        raise ValueError('Invalid game speed.')
    rows = inherited_sections(root, source)
    if any(rows.get(s) for s in ('Triggers', 'TeamTypes', 'AITriggerTypes', 'Houses')):
        raise ValueError('This map contains unsupported scenario scripting.')
    rows.pop('INISystem', None)
    _dta_naval_options(root, source, rows)
    difficulty = battle['difficulty']
    overlay = 'Medium' if difficulty == 'Normal' else difficulty if difficulty in ('Easy', 'Hard') else 'Brutal'
    for section, values in inherited_sections(root, root / 'INI/Map Code' / f'Difficulty {overlay}.ini').items():
        rows.setdefault(section, {}).update(values)
    for section, values in rows.items():
        rules.setdefault(section, {}).update(values)
    rows.setdefault('Basic', {}).update(Name='Conquest: ' + battle['map']['name'], MultiplayerOnly='yes', IgnoreGlobalAITriggers='no')
    rows['Basic'].pop('Player', None)
    lines = IniLines(_serialize(rows).splitlines())
    writer = ConquestWriter(lines, rules, root)
    for i in range(8):
        writer.put('Houses', 50 + i, f'Spawn{i+1}')
    members = participants(battle)
    humans = [m for m in members if m['controller'] == 'human']
    if (not 1 <= len(humans) <= 4 or [m['slot'] for m in humans] != list(range(len(humans))) or
        type(coop_slot) is not int or not 0 <= coop_slot < len(humans) or
        len(humans) > 1 and endpoints is None):
        raise ValueError('Invalid Conquest human seats or local player slot.')
    _clear_house_rosters(writer)
    for member in members:
        slot = member['slot']
        _apply_house(writer, member['loadout'], HOUSE_ALIASES[slot], 6 + slot,
                     impossible=difficulty == 'Impossible' and member['controller'] == 'ai')
        credits = BATTLE_CREDITS_PER_RANK * member['loadout']['perks'].get('battle_treasury', 0)
        if credits:
            writer.trigger('Conquest Battle Treasury', [(13, 0, 0)], [_action(106, 50 + member['waypoint'], extra=credits)])
    aliases = set(HOUSE_ALIASES[:len(members)])
    for name, native_members in rules['Sides'].items():
        values = [v for v in comma_items(native_members) if v not in aliases]
        for member in members:
            loadout, alias = member['loadout'], HOUSE_ALIASES[member['slot']]
            if name == rules[loadout['country']]['Side']:
                values.append(alias)
        writer.put('Sides', name, ','.join(values))
    from .native_effects import apply_effects
    private = apply_effects(writer, members, balance_version=battle.get('team_version', 1))
    grants = _placements(writer, rows, [(m['loadout'], m['waypoint']) for m in members],
                         private_types={m['waypoint']: private[m['slot']] for m in members})
    team, force, script = writer.key(), writer.key(), writer.key()
    append_hook_team(lines, team, force, script, marker(attempt_id), 'Neutral')
    writer.trigger('Conquest battle identity', [(13, 0, 0)], [_action(4, team=team)])
    from randomizer.dta.maps import preserve_collateral_damage_coefficients
    # Apply preservation after all newly created refinery definitions exist.
    data = writer.finish()
    lines = IniLines(data.decode('cp1252').splitlines())
    preserve_collateral_damage_coefficients(lines)
    data = ('\r\n'.join(lines) + '\r\n').encode('cp1252')
    game_id = int(attempt_id[:8], 16) % (2**31 - 1) + 1
    local = humans[coop_slot]
    settings = dict(Scenario='spawnmap.ini', Name=local.get('name', 'Commander'), Host='Yes' if coop_slot == 0 else 'No', IsSinglePlayer='No',
        PlayerCount=str(len(humans)), AIPlayers=str(len(members) - len(humans)), Side=str(6 + coop_slot), Color=str(coop_slot), Seed=str(battle['seed']), GameID=str(game_id),
        GameSpeed=str(game_speed), ShortGame='No', AutoSurrender='No', TechLevel='7', Bases='Yes',
        UnitCount='0', Credits='10000', Crates='No', MCVRedeploy='Yes', FogOfWar='No',
        MultiEngineer='Yes', BuildOffAlly='Yes', Protocol='0', FrameSendRate='1', Firestorm='Yes',
        CoachMode='Yes', WriteStatistics='Yes', AIDifficulty=str(DIFFICULTIES[difficulty]),
        LoadSaveGame='No', AutoSaveGame='0', UIGameMode='Conquest', UIMapName=battle['map']['name'],
        MapHash=hashlib.sha1(data).hexdigest())
    spawn = dict(Settings=settings, SpawnLocations={}, HouseCountries={}, HouseColors={}, HouseHandicaps={})
    if endpoints:
        settings.update(Ip=endpoints[coop_slot]['address'], Port=str(endpoints[coop_slot]['port']))
        for j, slot in enumerate(i for i in range(len(humans)) if i != coop_slot):
            endpoint = endpoints[slot]
            spawn[f'Other{j+1}'] = dict(Name=endpoint['name'], Side=str(6 + slot), Color=str(slot),
                                       Ip=endpoint['address'], Port=str(endpoint['port']))
    ordinals = ('One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven')
    for member in members:
        slot = member['slot']
        multi = f'Multi{slot + 1}'
        spawn['SpawnLocations'][multi] = str(member['waypoint'])
        spawn['HouseHandicaps'][multi] = str(1 if member['controller'] == 'human' else DIFFICULTIES[difficulty])
        if member['controller'] == 'ai':
            spawn['HouseCountries'][multi] = str(6 + slot)
            spawn['HouseColors'][multi] = str(member['color'])
        allies = [other['slot'] for other in members if other['team'] == member['team'] and other['slot'] != slot]
        spawn[multi + '_Alliances'] = {'HouseAlly' + word: str(other) for word, other in zip(ordinals, allies)}
    return dict(map=data, spawn=_serialize(spawn).encode('cp1252'), grants=grants,
                marker=marker(attempt_id), game_id=game_id)


def install(root, prepared):
    """Called only under the launcher's runtime lease after attempt persistence."""
    # Write the committed bytes exactly; Windows text translation changes CRLF
    # into CRCRLF and invalidates the durable attempt's content hashes.
    for relative, key in (('spawnmap.ini', 'map'), ('spawn.ini', 'spawn')):
        descriptor, temporary = tempfile.mkstemp(prefix='.' + relative, dir=root)
        try:
            with os.fdopen(descriptor, 'wb') as handle:
                handle.write(prepared[key])
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, Path(root) / relative)
        finally:
            Path(temporary).unlink(missing_ok=True)


def verify_prepared(root, attempt):
    for relative, key in (('spawnmap.ini', 'map_hash'), ('spawn.ini', 'spawn_hash')):
        if hashlib.sha256((Path(root) / relative).read_bytes()).hexdigest() != attempt[key]:
            raise ValueError('Prepared Conquest battle changed before launch. Retry preparation.')
