"""Convert reviewed DTA skirmish layouts without editing installed maps."""

from copy import deepcopy
import hashlib
from pathlib import Path
from randomizer.dta.rules import ini_sections, effective_section
from randomizer.maps.ini import IniLines, merge_ini_section_values, section_value_map
from .terrain import Terrain
from .placement import foundation


def map_definitions(config):
    return [config['map'], *config.get('maps', [])]


def select_map(config, map_id):
    definition = next((m for m in map_definitions(config) if m['id'] == map_id), None)
    if definition is None:
        raise ValueError('Unknown DTA Fortress map.')
    selected = deepcopy(config)
    selected.pop('maps', None)
    selected['map'] = deepcopy(definition)
    return selected


def map_sections(game_root, definition):
    sections = ini_sections(Path(game_root) / definition['source'])
    for number, p in definition.get('start_positions', {}).items():
        sections.setdefault('Waypoints', {})[number] = str(p['y'] * 1000 + p['x'])
    return sections


def source_lines(game_root, definition):
    root = Path(game_root).resolve()
    source = (root / definition['source']).resolve()
    if not source.is_relative_to(root):
        raise ValueError('Map must be inside the DTA installation.')
    lines = IniLines(source.read_text(encoding='cp1252').splitlines())
    if definition.get('clear_source_scripts'):
        from randomizer.maps.ini import find_section_bounds

        for section in ('Triggers', 'Events', 'Actions', 'Tags', 'CellTags', 'VariableNames'):
            start, end = find_section_bounds(lines, section)
            if start is not None:
                del lines[start:end]
        # Decorations retain their positions, but no source gameplay tags.
        tag_columns = (('Structures', 6), ('Units', 10), ('Infantry', 11), ('Aircraft', 10))
        for category, tag_index in tag_columns:
            values = section_value_map(lines, category)
            for key, value in values.items():
                fields = value.split(',')
                if len(fields) > tag_index:
                    fields[tag_index] = 'None'
                    values[key] = ','.join(fields)
            if values:
                merge_ini_section_values(lines, {category: values})
    merge_ini_section_values(lines, {'Waypoints': {
        key: str(p['y'] * 1000 + p['x'])
        for key, p in definition.get('start_positions', {}).items()
    }})
    return lines


def inspect_map(game_root, definition):
    root = Path(game_root)
    source = root / definition['source']
    sections = map_sections(root, definition)
    registered = ini_sections(root / 'INI/MPMaps.ini')
    registration = Path(definition['source']).with_suffix('').as_posix().casefold()
    if not any(k.casefold() == registration for k in registered):
        raise ValueError(definition['display_name'] + ' is not registered as a DTA skirmish map.')
    if sections['Basic'].get('IgnoreGlobalAITriggers', 'no').casefold() not in ('no', '0', 'false'):
        raise ValueError('Source map disables ordinary skirmish AI.')
    for number in [
        definition['player_waypoint'],
        *definition['allied_waypoints'],
        *definition['enemy_waypoints'],
    ]:
        if not sections['Waypoints'].get(str(number), '').isdigit():
            raise ValueError('Missing DTA start waypoint.')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != definition['source_sha256']:
        raise ValueError('Fortress source map changed; reviewed layout needs updating.')
    return {'source': str(source), 'sha256': digest}


def validate_layout(root, definition, rules):
    """Validate full footprints, scenery, source structures and deployment space."""
    root = Path(root)
    source = map_sections(root, definition)
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
    for category in ('Units', 'Infantry', 'Aircraft'):
        for value in source.get(category, {}).values():
            fields = value.split(',')
            occupied.add((int(fields[3]), int(fields[4])))
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
    friendly = [definition['player_waypoint'], *definition['allied_waypoints']]
    limits = definition.get('camp_clearance', {'friendly': 32, 'hostile': 40, 'camps': 32})
    for camp in definition['camps']:
        cells = {(p['x'], p['y']) for p in [camp['position'], *camp['guard_positions']]}
        if not terrain.clear(cells, occupied=occupied):
            raise ValueError('Unsafe camp formation: ' + camp['id'])
        if any(
            max(abs(x - points[n][0]), abs(y - points[n][1])) < clearance
            for x, y in cells
            for n, clearance in [
                *((n, limits['friendly']) for n in friendly),
                *((n, limits['hostile']) for n in definition['enemy_waypoints']),
            ]
        ):
            raise ValueError('Camp formation intrudes on a protected base region.')
        occupied.update(cells)
    for i, camp in enumerate(definition['camps']):
        for other in definition['camps'][:i]:
            distance = max(
                abs(camp['position'][axis] - other['position'][axis]) for axis in ('x', 'y')
            )
            if distance < limits['camps']:
                raise ValueError('Fortress camps are too close together.')
    return terrain


def validate_generated_placements(writer, definition, root):
    """Check actual emitted foundations, not only their reviewed layout slots."""
    root = Path(root)
    source = map_sections(root, definition)
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
    for category in ('Units', 'Infantry', 'Aircraft'):
        for value in source.get(category, {}).values():
            fields = value.split(',')
            occupied.add((int(fields[3]), int(fields[4])))
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
