"""Read-only conversion of the registered DTA skirmish map."""

from copy import deepcopy
import hashlib
from pathlib import Path
from randomizer.dta.rules import ini_sections, effective_section
from randomizer.maps.ini import IniLines, merge_ini_section_values, section_value_map
from .terrain import Terrain
from .placement import foundation


def map_definitions(config):
    return [config['map']]


def select_map(config, map_id):
    if config['map']['id'] != map_id:
        raise ValueError('Unknown DTA Fortress map.')
    return deepcopy(config)


def source_lines(game_root, definition):
    root = Path(game_root).resolve()
    source = (root / definition['source']).resolve()
    if not source.is_relative_to(root):
        raise ValueError('Map must be inside the DTA installation.')
    return IniLines(source.read_text(encoding='cp1252').splitlines())


def inspect_map(game_root, definition):
    root = Path(game_root)
    source = root / definition['source']
    sections = ini_sections(source)
    registered = ini_sections(root / 'INI/MPMaps.ini')
    if not any(k.casefold() == 'maps/default/king_of_the_hills_extreme' for k in registered):
        raise ValueError('King of the Hills Extreme is not registered as a DTA skirmish map.')
    if int(sections['Basic'].get('MaxPlayer', 0)) < 6:
        raise ValueError('Fortress needs at least six skirmish seats.')
    if sections['Basic'].get('IgnoreGlobalAITriggers', 'no').casefold() not in ('no', '0', 'false'):
        raise ValueError('Source map disables ordinary skirmish AI.')
    for number in [
        definition['player_waypoint'],
        *definition['allied_waypoints'],
        *definition['enemy_waypoints'],
    ]:
        if not sections['Waypoints'].get(str(number), '').isdigit():
            raise ValueError('Missing DTA start waypoint.')
    return {'source': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}


def validate_layout(root, definition, rules):
    """Validate full footprints, scenery, source structures and deployment space."""
    root = Path(root)
    source = ini_sections(root / definition['source'])
    terrain = Terrain(source)
    raw_art = ini_sections(root / 'INI/Art.ini')
    art = {k.casefold(): effective_section(raw_art, k) for k in raw_art}
    occupied = set(terrain.objects)
    for value in source.get('Structures', {}).values():
        parts = value.split(',')
        x, y = int(parts[3]), int(parts[4])
        row = dict(rules.get(parts[1], {}))
        row.setdefault('Image', parts[1])
        occupied.update((x + dx, y + dy) for dx, dy in foundation(row, art))
    points = {int(k): (int(v) % 1000, int(v) // 1000) for k, v in source['Waypoints'].items()}
    active = [
        definition['player_waypoint'],
        *definition['allied_waypoints'],
        *definition['enemy_waypoints'],
    ]
    for number in active:
        x, y = points[number]
        cells = {(x + dx, y + dy) for dx in range(-3, 4) for dy in range(-3, 4)}
        if not terrain.clear(cells, occupied=occupied):
            raise ValueError(f'Blocked MCV deployment at waypoint {number}.')
        occupied.update(cells)

    def reserve(position, kind):
        row = dict(rules[kind])
        row.setdefault('Image', kind)
        cells = {(position['x'] + dx, position['y'] + dy) for dx, dy in foundation(row, art)}
        if not terrain.clear(cells, occupied=occupied):
            raise ValueError(f'Unsafe Fortress footprint: {kind} at {position}.')
        occupied.update(cells)

    objective = definition['protected_building']
    reserve(objective['position'], objective['type'])
    # Layout slots were chosen for maximum native foundations across factions.
    for layout in definition['perk_layouts'].values():
        for slot in layout['slots']:
            cells = {
                (slot['x'] + dx, slot['y'] + dy)
                for dx in range(slot['width'])
                for dy in range(slot['height'])
            }
            if not terrain.clear(cells, occupied=occupied):
                raise ValueError('Unsafe or overlapping base grant slot.')
            occupied.update(cells)
        p = layout['arrival']
        cells = {(p['x'] + dx, p['y'] + dy) for dx in range(-2, 3) for dy in range(-1, 2)}
        if not terrain.clear(cells, occupied=occupied):
            raise ValueError('Unsafe arrival apron.')
        occupied.update(cells)
        for p in layout['army']:
            if not terrain.clear({(p['x'], p['y'])}, occupied=occupied):
                raise ValueError('Blocked starting army cell.')
            occupied.add((p['x'], p['y']))
        p = layout['controller']
        if not terrain.clear({(p['x'], p['y'])}, occupied=occupied):
            raise ValueError('Blocked survival controller cell.')
        occupied.add((p['x'], p['y']))
    for camp in definition['camps']:
        cells = {(p['x'], p['y']) for p in [camp['position'], *camp['guard_positions']]}
        if not terrain.clear(cells, occupied=occupied):
            raise ValueError('Unsafe camp formation: ' + camp['id'])
        friendly = [definition['player_waypoint'], *definition['allied_waypoints']]
        if any(
            max(abs(x - points[n][0]), abs(y - points[n][1])) < clearance
            for x, y in cells
            for n, clearance in [
                *((n, 32) for n in friendly),
                *((n, 40) for n in definition['enemy_waypoints']),
            ]
        ):
            raise ValueError('Camp formation intrudes on a protected base region.')
        occupied.update(cells)
    return terrain


def validate_generated_placements(writer, definition, root):
    """Check actual emitted foundations, not only their reviewed layout slots."""
    root = Path(root)
    source = ini_sections(root / definition['source'])
    terrain = Terrain(source)
    raw_art = ini_sections(root / 'INI/Art.ini')
    art = {k.casefold(): effective_section(raw_art, k) for k in raw_art}
    occupied = set(terrain.objects)
    combined = {**writer.rules, **writer.sections}
    for value in source.get('Structures', {}).values():
        fields = value.split(',')
        row = dict(combined[fields[1]])
        row.setdefault('Image', fields[1])
        occupied.update(
            (int(fields[3]) + dx, int(fields[4]) + dy) for dx, dy in foundation(row, art)
        )
    for value in writer.sections.get('Structures', {}).values():
        fields = value.split(',')
        row = dict(combined[fields[1]])
        row.setdefault('Image', fields[1])
        cells = {(int(fields[3]) + dx, int(fields[4]) + dy) for dx, dy in foundation(row, art)}
        if not cells and row.get('Image') == 'INLITE':
            cells = {(int(fields[3]), int(fields[4]))}
        if not terrain.clear(cells, occupied=occupied):
            raise ValueError(
                f'Generated Fortress structure overlaps terrain or another object: {fields[1]} '
                f'({row.get("Image")}) at {fields[3]},{fields[4]}; cells {sorted(cells & occupied)}'
            )
        occupied.update(cells)
    for category in ('Units', 'Infantry'):
        for value in writer.sections.get(category, {}).values():
            fields = value.split(',')
            cell = (int(fields[3]), int(fields[4]))
            if not terrain.clear({cell}, occupied=occupied):
                raise ValueError(
                    'Generated Fortress unit has a blocked starting cell: ' + fields[1]
                )
            occupied.add(cell)
