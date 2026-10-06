"""Normalize registered native co-op maps without changing the solo catalogue."""

import hashlib
import json
import re
from pathlib import Path

from randomizer.dta.rules import PLAYABLE_FACTIONS, ini_sections
from randomizer.missions.catalogue import normalize_long_description
from .compatibility import normalize_text, text_hash


# These retired checkboxes are absent from the installed client. The native
# client ignores their old map entries and uses its current queue/silo defaults.
RETIRED_CONTROLS = frozenset({'chkQueuing', 'chkSilosNeeded'})


def unpublished_campaign(name, metadata=None):
    stem = str(name).replace('\\', '/').rsplit('/', 1)[-1].casefold()
    return bool(re.match(r'(?:sov|scu)[_-]?\d', stem)
                or any(re.match(r'^\s*(?:\[\d+\]\s*)?Soviet\s+\d+\b', title, re.I)
                       for key, title in (metadata or {}).items() if key in {'Description', 'Name'}))


def metadata_hash(mission):
    values = {key: value for key, value in mission.items()
              if key.startswith('coop_') and key != 'coop_metadata_hash'}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def refresh_metadata_hashes(mission):
    mission['coop_metadata_hash'] = metadata_hash(mission)
    # Old catalogues hashed raw bytes and preserved OS-dependent map spelling.
    # Accept only hashes reconstructed from this installation's unchanged
    # content, then upgrade the saved fingerprint without resetting progress.
    variants = []
    for style in range(3):
        for windows_names in (False, True):
            dependencies = {}
            for name, hashes in mission['_coop_legacy_dependencies'].items():
                if windows_names and name.endswith('.map'):
                    parent, leaf = name.rsplit('/', 1)
                    name = parent + '/' + Path(leaf).stem.upper() + '.map'
                dependencies[name] = hashes[style]
            variants.append(metadata_hash(dict(mission, coop_dependencies=dependencies)))
    mission['_coop_legacy_metadata_hashes'] = tuple(sorted(set(variants)))


def truth(value):
    return str(value).strip().casefold() in {'yes', 'true', '1'}


def resolve_path(root, name, parent=None):
    parts = str(name).replace('\\', '/').split('/')
    path = Path(parent or root)
    for part in parts:
        if part in {'', '.'}:
            continue
        if part == '..':
            path = path.parent
        else:
            exact = path / part
            path = exact if exact.exists() else next(
                (child for child in path.iterdir() if child.name.casefold() == part.casefold()),
                exact,
            )
    path = path.resolve()
    if not path.is_relative_to(Path(root).resolve()) or not path.is_file():
        raise ValueError(f'Missing or unsafe native co-op dependency: {name}')
    return path


def inherited_sections(root, path, stack=(), dependencies=None, legacy_dependencies=None):
    path = Path(path).resolve()
    if path in stack or len(stack) >= 20:
        raise ValueError(f'Cyclic or excessive native map inheritance: {path.name}')
    data = path.read_bytes()
    name = str(path.relative_to(root)).replace('\\', '/')
    if dependencies is not None:
        dependencies[name.casefold()] = text_hash(data)
    if legacy_dependencies is not None:
        normalized = normalize_text(data)
        legacy_dependencies[name] = tuple(hashlib.sha256(content).hexdigest() for content in
                                          (data, normalized, normalized.replace(b'\n', b'\r\n')))
    local = ini_sections(path)
    result = {}
    for name in local.get('INISystem', {}).get('BasedOn', '').split(','):
        if name.strip():
            source = resolve_path(root, name.strip(), path.parent)
            merge(result, inherited_sections(root, source, (*stack, path), dependencies, legacy_dependencies))
    local.pop('INISystem', None)
    merge(result, local)
    return result


def merge(target, source):
    for section, values in source.items():
        target.setdefault(section, {}).update(values)


def native_options(root, sections):
    """Mirror the installed client's forced checkbox/dropdown interpretation."""
    controls = ini_sections(root / 'Resources' / 'SkirmishLobby.ini')
    settings = dict(ini_sections(root / 'Resources' / 'GameOptions.ini').get('ForcedSpawnIniOptions', {}))
    overlays = []
    forced = sections.get('ForcedOptions', {})
    for name, control in controls.items():
        if not name.startswith(('chk', 'cmb')):
            continue
        if name.startswith('chk'):
            checked = truth(forced.get(name, control.get('Checked', 'false')))
            active = not checked if truth(control.get('Reversed')) else checked
            key = control.get('SpawnIniOption')
            if key:
                settings[key] = control.get(
                    'EnabledSpawnIniValue' if active else 'DisabledSpawnIniValue',
                    'Yes' if active else 'No',
                )
            if active and control.get('CustomIniPath'):
                overlays.append(resolve_path(root, control['CustomIniPath']))
        elif name in forced:
            index = int(forced[name])
            if index == -1:
                continue  # Map supplies Credits/UnitCount instead of a dropdown.
            values = control.get('Items', '').split(',')
            if not 0 <= index < len(values):
                raise ValueError(f'Unsupported forced dropdown {name}={index}')
            key = control.get('SpawnIniOption')
            mode = control.get('DataWriteMode', 'Index').casefold()
            if key:
                settings[key] = ('Yes' if index else 'No') if mode == 'boolean' else values[index] if mode == 'string' else str(index)
    # Old shipped maps retain removed, disabled client controls. An absent
    # unchecked checkbox has no code to apply; enabled unknown options fail.
    unknown = {name for name in set(forced) - set(controls) - RETIRED_CONTROLS if truth(forced[name])}
    if unknown:
        raise ValueError('Unsupported forced native controls: ' + ', '.join(sorted(unknown)))
    for key in ('Credits', 'UnitCount', 'Bases'):
        if key in sections.get('Basic', {}):
            settings[key] = sections['Basic'][key]
    settings.setdefault('Credits', '10000')
    settings.setdefault('UnitCount', '0')
    # Vinifera defaults Bases to true. Unscripted co-op maps rely on this to
    # receive MCVs; scripted campaign maps explicitly override it to No.
    settings.setdefault('Bases', 'Yes')
    return settings, overlays


def _houses(metadata, prefix):
    result = []
    for key in sorted(metadata, key=lambda value: (len(value), value)):
        if re.fullmatch(prefix + r'\d+', key):
            values = tuple(int(value.strip()) for value in metadata[key].split(','))
            if len(values) != 3 or not 0 <= values[0] <= 3 or not 0 <= values[2] <= 7:
                raise ValueError(f'Unsupported native {key}={metadata[key]}')
            result.append(values)
    return result


def discover_coop_missions(root, *, include_excluded=False):
    root = Path(root).resolve()
    catalogue = ini_sections(root / 'INI' / 'MPMaps.ini')
    colors = sorted(int(value.split(',')[-1]) for value in ini_sections(
        root / 'Resources' / 'GameOptions.ini'
    ).get('MPColors', {}).values())
    missions = []
    registered = {name.replace('\\', '/').casefold()
                  for name in catalogue.get('MultiMaps', {}).values()}
    for name, values in catalogue.items():
        normalized_name = name.replace('\\', '/').casefold()
        if (not normalized_name.startswith('maps/co-op/')
                or normalized_name not in registered or unpublished_campaign(name)):
            continue
        mission = {'code': 'COOP_' + normalized_name.rsplit('/', 1)[-1].upper(), 'coop_mode': True}
        try:
            dependencies = {}
            legacy_dependencies = {}
            path = resolve_path(root, name + '.map')
            sections = inherited_sections(root, path, dependencies=dependencies,
                                          legacy_dependencies=legacy_dependencies)
            if (unpublished_campaign(name, sections.get('Basic', {}))
                    or any(unpublished_campaign(source) for source in dependencies)):
                continue
            metadata = dict(sections.get('Basic', {}))
            merge_metadata = dict(values)
            seen = {name}
            while merge_metadata.get('BaseSection'):
                parent = merge_metadata.pop('BaseSection')
                if parent in seen or parent not in catalogue:
                    raise ValueError('Invalid catalogue BaseSection')
                seen.add(parent)
                merge_metadata = {**catalogue[parent], **merge_metadata}
            metadata.update(sections.get('CoopInfo', {}))
            metadata.update(merge_metadata)
            if unpublished_campaign(name, metadata):
                continue  # Never expose the unpublished Soviet campaign, even in diagnostics.
            if not truth(metadata.get('IsCoopMission')):
                raise ValueError('Not explicitly marked IsCoopMission')
            def limit(keys):
                return int(next((source[key] for key in keys
                                 for source in (merge_metadata, metadata) if key in source), 0))
            minimum = limit(('ClientMinPlayer', 'MinPlayers', 'MinPlayer'))
            maximum = limit(('ClientMaxPlayer', 'MaxPlayers', 'MaxPlayer'))
            if not 2 <= minimum <= maximum <= 4:
                raise ValueError(f'Unsupported authored human count, got {minimum}–{maximum}')
            if minimum != maximum:
                optional_humans = '|'.join(f'Spawn{slot + 1}' for slot in range(minimum, maximum))
                if any(re.search(r'\b(?:' + optional_humans + r')\b', value, re.I)
                       for section, entries in sections.items() if section != 'Houses'
                       for value in entries.values()):
                    raise ValueError('Variable-count map scripts require optional human houses')
            denied = {int(value) for value in metadata.get('DisallowedPlayerSides', '').split(',') if value.strip()}
            sides = set(range(4)) - denied
            allies = _houses(metadata, 'AllyHouse')
            enemies = _houses(metadata, 'EnemyHouse')
            if truth(metadata.get('CoopEvenPlayers')):
                raise ValueError('CoopEvenPlayers dynamic AI allocation is not supported')
            if not enemies or maximum + len(allies) + len(enemies) > 8:
                raise ValueError('Invalid native AI slot count')
            if not sides:
                raise ValueError('Native mission allows no human side')
            # Prefer an unused faction, but native HumanOnly production gates
            # also safely separate humans from AI sharing the same faction.
            sides = sides - {house[0] for house in (*allies, *enemies)} or sides
            # Choose one native allowed faction for the whole team. Nuclear
            # Winter permits GDI/Allies; both masks are distinct from its AI.
            side = min(sides)
            denied_colors = {int(value) for value in metadata.get('DisallowedPlayerColors', '').split(',') if value.strip()}
            allowed_colors = [color for color in colors if color not in denied_colors]
            if len(allowed_colors) < maximum:
                raise ValueError('Not enough allowed human colors')
            positions = [*range(maximum), *(house[2] for house in (*allies, *enemies))]
            if len(positions) != len(set(positions)):
                raise ValueError('Human and AI starting locations overlap')
            settings, overlays = native_options(root, sections)
            required_positions = positions if truth(settings['Bases']) or int(settings['UnitCount']) else range(maximum)
            if any(str(position) not in sections.get('Waypoints', {}) for position in required_positions):
                raise ValueError('Missing required native starting waypoint')
            for overlay in overlays:
                inherited_sections(root, overlay, dependencies=dependencies,
                                   legacy_dependencies=legacy_dependencies)
            modes = metadata.get('GameModes', metadata.get('GameMode', '')).split(',')
            for mode in modes:
                mode = mode.strip()
                if mode.startswith('Co-Op '):
                    inherited_sections(root, resolve_path(root, f'INI/Map Code/Difficulty {mode[6:]}.ini'),
                                       dependencies=dependencies, legacy_dependencies=legacy_dependencies)
            faction = PLAYABLE_FACTIONS[side]
            mission.update({
                'index': len(missions) + 1, 'scenario': str(path.relative_to(root)),
                'title': metadata.get('Description', metadata.get('Name', path.stem)),
                'side': faction, 'campaign': faction,
                'briefing': normalize_long_description(metadata.get('Briefing', '')),
                'objectives': [], 'objective_count': 1, 'build_classification': 'base_build',
                'reward_class': 'act_1', 'reward_multiplier': 1,
                'required_addon': truth(settings.get('Firestorm', metadata.get('RequiredAddOn', '0'))),
                'coop_player_count': maximum, 'coop_side': side,
                'coop_colors': allowed_colors[:maximum], 'coop_allies': allies, 'coop_enemies': enemies,
                'coop_settings': settings, 'coop_dependencies': dependencies,
                '_coop_legacy_dependencies': legacy_dependencies,
                'coop_modes': [mode.strip() for mode in modes],
                'coop_excluded_reason': '', 'no_build': False, 'true_no_build': False,
                'no_build_production': False, 'operation': False,
            })
            if minimum != maximum:
                mission.update({'coop_min_player_count': minimum, 'coop_max_player_count': maximum})
            refresh_metadata_hashes(mission)
        except (OSError, ValueError, KeyError) as exc:
            mission['coop_excluded_reason'] = str(exc)
        if include_excluded or not mission['coop_excluded_reason']:
            missions.append(mission)
    return missions


def eligible(missions, count):
    from .feature import player_count
    count = player_count(count)
    result = []
    for mission in missions:
        if mission.get('coop_excluded_reason'):
            continue
        minimum = mission.get('coop_min_player_count', mission['coop_player_count'])
        maximum = mission.get('coop_max_player_count', mission['coop_player_count'])
        if minimum <= count <= maximum:
            if 'coop_min_player_count' in mission:
                mission = dict(mission, coop_player_count=count,
                               coop_colors=mission['coop_colors'][:count])
                refresh_metadata_hashes(mission)
            result.append(mission)
    return result


def validate_pool(missions, codes, count, metadata=None):
    """Validate native content and upgrade matching legacy hashes in place."""
    by_code = {mission['code']: mission for mission in eligible(missions, count)}
    codes = tuple(codes)
    invalid = [code for code in codes if code not in by_code or (metadata is not None
               and metadata.get(code) not in {by_code[code]['coop_metadata_hash'],
                                             *by_code[code].get('_coop_legacy_metadata_hashes', ())})]
    if invalid:
        raise ValueError('Saved co-op pool no longer matches player count/native metadata: ' + ', '.join(invalid[:8]))
    if metadata is not None:
        metadata.update({code: by_code[code]['coop_metadata_hash'] for code in codes})
    return by_code
