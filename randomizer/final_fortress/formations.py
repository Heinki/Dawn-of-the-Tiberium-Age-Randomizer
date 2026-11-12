"""Compact production cores and terrain-aware defensive perimeters."""

from math import cos, hypot, pi, sin
from pathlib import Path
from copy import deepcopy
from functools import lru_cache
import json

from .placement import foundation
from .maps import map_sections
from .terrain import Terrain, BUILDABLE_TILES
from randomizer.dta.rules import ini_sections, effective_section


def footprint(kind, position, rules, art):
    return {(position['x'] + dx, position['y'] + dy)
            for dx, dy in foundation({'Image': kind, **rules[kind]}, art)}


def compound(terrain, rules, art, production, defenses, center, occupied, *,
             maximum_radius=12, shifts=4, protected=()):
    """Keep production inside a shared perimeter, on the center's ground level.

    Every structure retains a full-cell exit apron. Cliff-facing sectors can
    use adjacent accessible perimeter cells; each production foundation must
    still be covered by a nearby emplacement. Return None when no safe group fits.
    """
    cx, cy = center['x'], center['y']
    height = terrain.heights.get((cx, cy), 0)
    offsets = {k: foundation({'Image': k, **rules[k]}, art) for k in production + defenses}
    available, walkable = set(), set()
    overlays = list(rules['OverlayTypes'].values())
    walls = {i for i, k in enumerate(overlays) if rules.get(k, {}).get('Wall', '').casefold() in ('yes', 'true', '1')}
    for x in range(cx - maximum_radius - shifts - 2, cx + maximum_radius + shifts + 3):
        for y in range(cy - maximum_radius - shifts - 2, cy + maximum_radius + shifts + 3):
            if terrain.heights.get((x, y), 0) == height and terrain.clear({(x, y)}):
                available.add((x, y))
            if (
                0 <= x < 512 and 0 <= y < 512
                and terrain.heights.get((x, y), 0) == height
                and terrain.cells.get((x, y), (0, 0, 0))[0] in BUILDABLE_TILES[terrain.theater]
                and (x, y) not in terrain.objects
                and terrain.overlays[y * 512 + x] not in walls
                and terrain.bounds.contains({(x, y)}, heights=terrain.heights)
            ):
                walkable.add((x, y))
    # Same-height connected ground prevents production on a nearby isolated ledge.
    connected, pending = set(), [(cx, cy)]
    while pending:
        p = pending.pop()
        if p in connected or p not in walkable:
            continue
        connected.add(p)
        pending.extend((p[0] + dx, p[1] + dy)
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)))
    if not connected:
        return None
    anchors = [(cx + dx, cy + dy) for dx in range(-shifts, shifts + 1)
               for dy in range(-shifts, shifts + 1)]
    anchors.sort(key=lambda p: ((p[0] - cx) ** 2 + (p[1] - cy) ** 2, p))
    ground = available & connected
    candidates_by_anchor = {
        (ax, ay): sorted(ground, key=lambda p: ((p[0] - ax) ** 2 + (p[1] - ay) ** 2, p))
        for ax, ay in anchors if (ax, ay) in connected
    }
    order = sorted(range(len(production)), key=lambda i: (-len(offsets[production[i]]), i))
    extents = {kind: (min(x for x, y in cells), max(x for x, y in cells),
                      min(y for x, y in cells), max(y for x, y in cells))
               for kind, cells in offsets.items()}
    geometry = {}

    def site(kind, x, y):
        key = (kind, x, y)
        if key not in geometry:
            cells = {(x + dx, y + dy) for dx, dy in offsets[kind]}
            apron = {(px + dx, py + dy) for px, py in cells
                     for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
            geometry[key] = cells, apron, cells <= available
        return geometry[key]

    # Try compact circles first, expanding the whole protected group together.
    for radius in range(6, maximum_radius + 1):
        for ax, ay in anchors:
            if (ax, ay) not in connected:
                continue
            if any(hypot(x - ax, y - ay) > radius - 1 for x, y in protected):
                continue
            candidates = candidates_by_anchor[(ax, ay)]
            taken, placed = set(occupied), {}
            for i in order:
                kind = production[i]
                left, right, top, bottom = extents[kind]
                rectangular = len(offsets[kind]) == (right - left + 1) * (bottom - top + 1)
                for x, y in candidates:
                    dx = max(abs(x + left - ax), abs(x + right - ax))
                    dy = max(abs(y + top - ay), abs(y + bottom - ay))
                    outside = (dx * dx + dy * dy > (radius - 2) ** 2) if rectangular else any(
                        hypot(x + px - ax, y + py - ay) > radius - 2 for px, py in offsets[kind])
                    if outside:
                        continue
                    cells, apron, clear = site(kind, x, y)
                    if clear and not apron.intersection(taken):
                        placed[i] = {'type': kind, 'position': {'x': x, 'y': y}}
                        taken.update(cells)
                        break
                else:
                    break
            if len(placed) != len(production):
                continue
            perimeter = []
            for i, kind in enumerate(defenses):
                angle = 2 * pi * i / len(defenses)
                target = ax + radius * cos(angle), ay + radius * sin(angle)
                choices = sorted(ground, key=lambda p: ((p[0] - target[0]) ** 2 + (p[1] - target[1]) ** 2, p))
                for x, y in choices:
                    distance = hypot(x - ax, y - ay)
                    if not radius - .75 <= distance <= radius + 1.25:
                        continue
                    cells, apron, clear = site(kind, x, y)
                    if clear and not apron.intersection(taken):
                        perimeter.append({'type': kind, 'position': {'x': x, 'y': y}})
                        taken.update(cells)
                        break
                else:
                    break
            if len(perimeter) != len(defenses):
                continue
            core = [placed[i] for i in range(len(production))]
            return {'structures': [*core, *perimeter], 'radius': radius,
                    'center': {'x': ax, 'y': ay}}
    return None


def context(root, definition, rules, *, reserve_friendly_slots=True):
    source = map_sections(root, definition)
    terrain = Terrain(source)
    raw = ini_sections(Path(root) / 'INI/Art.ini')
    art = {k.casefold(): effective_section(raw, k) for k in raw}
    occupied = set(terrain.objects)
    for value in source.get('Structures', {}).values():
        f = value.split(',')
        occupied.update(footprint(f[1], {'x': int(f[3]), 'y': int(f[4])}, rules, art))
    for category in ('Units', 'Infantry', 'Aircraft'):
        for value in source.get(category, {}).values():
            f = value.split(',')
            occupied.add((int(f[3]), int(f[4])))
    objective = definition['protected_building']
    occupied.update(footprint(objective['type'], objective['position'], rules, art))
    friendly = [definition['player_waypoint'], *definition['allied_waypoints']]
    for number, layout in definition['perk_layouts'].items():
        if reserve_friendly_slots or int(number) not in friendly:
            for slot in layout['slots']:
                occupied.update((slot['x'] + dx, slot['y'] + dy)
                                for dx in range(slot['width']) for dy in range(slot['height']))
        occupied.update((p['x'], p['y']) for p in layout['army'])
        p = layout['controller']
        occupied.add((p['x'], p['y']))
        p = layout['arrival']
        occupied.update((p['x'] + dx, p['y'] + dy) for dx in range(-2, 3) for dy in range(-1, 2))
        value = int(source['Waypoints'][number])
        x, y = value % 1000, value // 1000
        occupied.update((x + dx, y + dy) for dx in range(-3, 4) for dy in range(-3, 4))
    for camp in definition['camps']:
        occupied.update((p['x'], p['y']) for p in [camp['position'], *camp['guard_positions']])
    return terrain, art, occupied, source


def plan_bases(root, definition, effects, rules):
    """Replace independent grant slots with compact protected friendly groups."""
    layouts = _base_layouts(str(root), json.dumps(definition, sort_keys=True),
                           tuple([*effects['starting_buildings'], *effects['starting_power_buildings']]),
                           tuple(effects['defense_types']))
    for number, layout in layouts.items():
        definition['perk_layouts'][number].update(deepcopy(layout))


@lru_cache(maxsize=96)
def _base_layouts(root, definition_json, production, defenses):
    from .catalogue import installed_rules_registry

    definition = json.loads(definition_json)
    rules = installed_rules_registry()[1]
    production, defenses = list(production), list(defenses)
    terrain, art, occupied, source = context(root, definition, rules, reserve_friendly_slots=False)
    if not production and not defenses:
        return {}
    result = {}
    for number in [definition['player_waypoint'], *definition['allied_waypoints']]:
        value = int(source['Waypoints'][str(number)])
        center = {'x': value % 1000, 'y': value // 1000}
        protected = {(center['x'] + dx, center['y'] + dy) for dx in (-3, 3) for dy in (-3, 3)}
        if number == definition['player_waypoint']:
            obj = definition['protected_building']
            protected.update(footprint(obj['type'], obj['position'], rules, art))
        group = compound(terrain, rules, art, production, defenses, center, occupied,
                         maximum_radius=15, shifts=3, protected=protected)
        if group is None:
            raise ValueError(f'No protected starting-base layout fits {definition["display_name"]}, waypoint {number}.')
        slots = []
        for entry in group['structures']:
            f = footprint(entry['type'], entry['position'], rules, art)
            occupied.update(f)
            slots.append({**entry['position'], 'width': max(x for x, y in f) - entry['position']['x'] + 1,
                          'height': max(y for x, y in f) - entry['position']['y'] + 1})
        result[str(number)] = {'slots': slots, 'formation': {
            'center': group['center'], 'radius': group['radius'],
        }}
    return result
