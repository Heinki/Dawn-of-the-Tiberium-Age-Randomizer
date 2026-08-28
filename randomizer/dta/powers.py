"""Player-only DTA superweapon and support-power rewards."""

from hashlib import sha1

from randomizer.config.static import static_config_section
from randomizer.core.paths import GAME_ROOT
from randomizer.dta.clones import _player_production_context
from randomizer.dta.maps import mission_source_path
from randomizer.dta.rules import effective_section, ini_sections
from randomizer.maps.ini import action_group_tokens, parse_action_groups

POWER_SETTINGS = static_config_section(
    'rewards/powers.json', 'settings', dict
)
POWER_SPECS = tuple(static_config_section(
    'rewards/powers.json', 'powers', list
))
POWER_SPEC_BY_ID = {spec['id'].upper(): spec for spec in POWER_SPECS}
POWER_EFFECT_CHAINS = {
    spec['id'].upper(): spec['effect']
    for spec in POWER_SPECS
    if spec.get('effect')
}

ANIMATION_REFERENCE_FIELDS = {
    'Next', 'TrailerAnim', 'ExpireAnim', 'StartAnims', 'MiddleAnims',
}

# A SuperWeaponType's Action is also its sidebar identity. Reusing the source
# action makes a map-local clone collide with the installed power. Vinifera
# loads ActionTypes from Action.ini before it reads the scenario, so these
# stable identities are installed there before starting the game.
POWER_CLONE_ACTION_TYPES = {
    spec['id'].upper(): (
        spec['action']['id'],
        f'{spec["action"]["cursor"]},{spec["action"]["no_cursor"]}',
    )
    for spec in POWER_SPECS
}
RETIRED_POWER_ACTION_TYPES = frozenset({
    'DTAAIRSTRIKESPECIALACT',
    'DTACHEMICALSPECIALACT',
    'DTAMULTISPECIALACT',
    'DTAVORTEXSPECIALACT',
}) - {
    action_name
    for action_name, _cursor_pair in POWER_CLONE_ACTION_TYPES.values()
}
MAX_TYPE_ID_LENGTH = 23
POWER_AREA_CELLS_PER_STACK = float(
    POWER_SETTINGS['area_cells_per_stack']
)

PARATROOPER_BUFF_FIELDS = {
    'Strength', 'Armor', 'Speed', 'Sight', 'Ammo',
    'Primary', 'Secondary', 'Elite',
    'Cloakable', 'CloakingSpeed', 'Sensors',
    'SelfHealing', 'SelfHealingCap', 'SelfHealingRate', 'SelfHealingStep',
}


def power_unlock_rewards():
    return [
        {
            'name': f'Unlock {spec["label"]}',
            'description': spec['description'],
            'rules': {},
            'factions': list(spec['factions']),
            'kind': 'superweapon',
            'superweapon': spec['id'],
            'cameo_superweapon': spec['id'],
            'power_category': spec['category'],
            'dta_player_power': True,
            'special_reward': False,
        }
        for spec in POWER_SPECS
    ]


def ensure_power_action_types(path=None):
    """Install stable randomizer ActionTypes in DTA's global Action.ini."""
    path = path or GAME_ROOT / 'INI' / 'Action.ini'
    raw = path.read_text(encoding='cp1252')
    newline = '\r\n' if '\r\n' in raw else '\n'
    trailing_newline = raw.endswith(('\r', '\n'))
    lines = raw.splitlines()
    section_start = next(
        (
            index for index, line in enumerate(lines)
            if line.strip().casefold() == '[actiontypes]'
        ),
        None,
    )
    if section_start is None:
        if lines and lines[-1].strip():
            lines.append('')
        lines.append('[ActionTypes]')
        section_start = len(lines) - 1
    section_end = next(
        (
            index for index in range(section_start + 1, len(lines))
            if lines[index].strip().startswith('[')
            and lines[index].strip().endswith(']')
        ),
        len(lines),
    )
    retired_indexes = []
    for index in range(section_start + 1, section_end):
        content = lines[index].split(';', 1)[0]
        key, separator, _value = content.partition('=')
        if (
            separator
            and key.strip().upper() in RETIRED_POWER_ACTION_TYPES
        ):
            retired_indexes.append(index)
    changed = []
    for index in reversed(retired_indexes):
        changed.append(f'-{lines[index].split("=", 1)[0].strip()}')
        lines.pop(index)
        section_end -= 1
    existing = {}
    for index in range(section_start + 1, section_end):
        content = lines[index].split(';', 1)[0]
        key, separator, _value = content.partition('=')
        if separator:
            existing[key.strip().casefold()] = index
    for action_name, cursor_pair in POWER_CLONE_ACTION_TYPES.values():
        desired = f'{action_name}={cursor_pair}'
        index = existing.get(action_name.casefold())
        if index is None:
            lines.insert(section_end, desired)
            section_end += 1
            changed.append(action_name)
        elif lines[index].split(';', 1)[0].strip() != desired:
            lines[index] = desired
            changed.append(action_name)
    if changed:
        output = newline.join(lines)
        if trailing_newline:
            output += newline
        temporary = path.with_name(f'{path.name}.randomizer.tmp')
        temporary.write_bytes(output.encode('cp1252'))
        temporary.replace(path)
    return changed


def _without_managed_blocks(lines, marker):
    start = f'; BEGIN {marker}'
    end = f'; END {marker}'
    output = []
    skipping = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(start):
            skipping = True
            continue
        if skipping and stripped.startswith(end):
            skipping = False
            continue
        if not skipping:
            output.append(line)
    return output


def _write_managed_ini_types(path, list_entries, sections, marker):
    """Replace isolated randomizer type blocks without touching native data."""
    raw = path.read_text(encoding='cp1252')
    newline = '\r\n' if '\r\n' in raw else '\n'
    trailing_newline = raw.endswith(('\r', '\n'))
    lines = _without_managed_blocks(raw.splitlines(), marker)

    for list_name, type_ids in list_entries.items():
        type_ids = list(dict.fromkeys(
            str(type_id).strip() for type_id in type_ids
            if str(type_id).strip()
        ))
        if not type_ids:
            continue
        section_start = next(
            (
                index for index, line in enumerate(lines)
                if line.strip().casefold() == f'[{list_name}]'.casefold()
            ),
            None,
        )
        if section_start is None:
            if lines and lines[-1].strip():
                lines.append('')
            lines.append(f'[{list_name}]')
            section_start = len(lines) - 1
        section_end = next(
            (
                index for index in range(section_start + 1, len(lines))
                if lines[index].strip().startswith('[')
                and lines[index].strip().endswith(']')
            ),
            len(lines),
        )
        keys = []
        for line in lines[section_start + 1:section_end]:
            content = line.split(';', 1)[0]
            key, separator, _value = content.partition('=')
            if separator and key.strip().isdigit():
                keys.append(int(key.strip()))
        next_key = max(keys, default=0) + 1
        block = [f'; BEGIN {marker} {list_name}']
        block.extend(
            f'{next_key + offset}={type_id}'
            for offset, type_id in enumerate(type_ids)
        )
        block.append(f'; END {marker} {list_name}')
        insertion_index = section_end
        while (
            insertion_index > section_start + 1
            and not lines[insertion_index - 1].strip()
        ):
            insertion_index -= 1
        lines[insertion_index:insertion_index] = block

    if sections:
        if lines and lines[-1].strip():
            lines.append('')
        lines.append(f'; BEGIN {marker} Sections')
        for section, values in sections.items():
            lines.append(f'[{section}]')
            lines.extend(
                f'{key}={value}' for key, value in values.items()
                if value is not None
            )
            lines.append('')
        if lines and not lines[-1].strip():
            lines.pop()
        lines.append(f'; END {marker} Sections')

    output = newline.join(lines)
    if trailing_newline:
        output += newline
    if output == raw:
        return False
    temporary = path.with_name(f'{path.name}.randomizer.tmp')
    temporary.write_bytes(output.encode('cp1252'))
    temporary.replace(path)
    return True


def ensure_power_runtime_types(rule_sections, art_sections, rules_path=None, art_path=None):
    """Install dynamic helper types where DTA's Rules and Art loaders see them."""
    rules_path = rules_path or GAME_ROOT / 'INI' / 'Rules.ini'
    art_path = art_path or GAME_ROOT / 'INI' / 'Art.ini'
    rule_sections = {
        section: dict(values)
        for section, values in (rule_sections or {}).items()
    }
    art_sections = {
        section: dict(values)
        for section, values in (art_sections or {}).items()
    }
    rule_lists = {
        list_name: list(rule_sections.pop(list_name, {}).values())
        for list_name in ('WeaponTypes', 'Warheads')
    }
    art_lists = {
        'Animations': list(art_sections.pop('Animations', {}).values())
    }
    changed = []
    if _write_managed_ini_types(
        rules_path,
        rule_lists,
        rule_sections,
        'DTA Randomizer Power Rules',
    ):
        changed.append(rules_path.name)
    if _write_managed_ini_types(
        art_path,
        art_lists,
        art_sections,
        'DTA Randomizer Power Art',
    ):
        changed.append(art_path.name)
    return changed


def _clone_type_id(source_id, occupied):
    stem = str(source_id).upper().removesuffix('SPECIAL')
    candidate = f'DTA{stem}RNG'
    if len(candidate) > MAX_TYPE_ID_LENGTH:
        digest = sha1(candidate.encode('ascii', errors='ignore')).hexdigest()[:6].upper()
        tail = f'{digest}RNG'
        candidate = f'DTA{stem[:MAX_TYPE_ID_LENGTH-len(tail)-3]}{tail}'
    counter = 2
    base = candidate
    while candidate.casefold() in occupied:
        suffix = str(counter)
        candidate = f'{base[:MAX_TYPE_ID_LENGTH-len(suffix)]}{suffix}'
        counter += 1
    occupied.add(candidate.casefold())
    return candidate


def _clone_auxiliary_id(source_id, token, occupied):
    source = ''.join(
        character for character in str(source_id).upper()
        if character.isalnum()
    )
    token = ''.join(
        character for character in str(token).upper()
        if character.isalnum()
    )
    candidate = f'DTA{source}{token}'
    if len(candidate) > MAX_TYPE_ID_LENGTH:
        digest = sha1(candidate.encode('ascii', errors='ignore')).hexdigest()[:6].upper()
        tail = f'{digest}{token[:3]}'
        candidate = f'DTA{source[:MAX_TYPE_ID_LENGTH-len(tail)-3]}{tail}'
    base = candidate
    counter = 2
    while candidate.casefold() in occupied:
        suffix = str(counter)
        candidate = f'{base[:MAX_TYPE_ID_LENGTH-len(suffix)]}{suffix}'
        counter += 1
    occupied.add(candidate.casefold())
    return candidate


def _next_list_key(installed, authored, list_name, offsets):
    if list_name not in offsets:
        keys = set(installed.get(list_name, {})) | set(authored.get(list_name, {}))
        numeric = [int(key) for key in keys if str(key).isdigit()]
        offsets[list_name] = max(numeric, default=-1) + 1
    value = str(offsets[list_name])
    offsets[list_name] += 1
    return value


def _scaled_integer(value, factor):
    try:
        original = int(float(value))
    except (TypeError, ValueError):
        return value
    if original <= 0:
        return value
    return str(max(original + 1, int(round(original * factor))))


def _clone_power_effect_chain(
    source_id,
    power_values,
    buff_counts,
    installed,
    authored,
    art,
    occupied,
    list_offsets,
):
    """Build isolated Rules.ini and Art.ini helpers for one buffed power."""
    chain = POWER_EFFECT_CHAINS.get(source_id.upper())
    damage_count = buff_counts.get('damage', 0)
    area_count = buff_counts.get('area', 0)
    weapon_id = str(power_values.get('WeaponType') or '').strip()
    if (
        not chain
        or not weapon_id
        or not (
            damage_count
            or area_count
            or bool(chain.get('always_clone'))
        )
    ):
        return {}, {}, power_values

    mission_rules = {
        section: dict(values) for section, values in installed.items()
    }
    for section, values in authored.items():
        mission_rules.setdefault(section, {}).update(values)
    rule_output = {}
    art_output = {}

    def register(list_name, type_id):
        key = _next_list_key(
            installed, authored, list_name, list_offsets
        )
        rule_output.setdefault(list_name, {})[key] = type_id

    cloned_warheads = {}

    def clone_warhead(warhead_id, *, expand_area=False):
        marker = (warhead_id.upper(), bool(expand_area))
        if marker in cloned_warheads:
            return cloned_warheads[marker]
        clone_id = _clone_auxiliary_id(
            warhead_id, 'A' if expand_area else 'W', occupied
        )
        values = effective_section(mission_rules, warhead_id)
        clone_values = dict(values)
        clone_values.pop('BaseSection', None)
        clone_values.pop('$Inherits', None)
        if expand_area and area_count:
            try:
                if 'CellSpread' in clone_values:
                    base_spread = float(clone_values['CellSpread'])
                else:
                    base_spread = float(clone_values.get('Spread', 0)) / 128.0
                spread = (
                    base_spread
                    + POWER_AREA_CELLS_PER_STACK * area_count
                )
                clone_values['CellSpread'] = f'{spread:.3f}'.rstrip('0').rstrip('.')
            except (TypeError, ValueError):
                pass
        rule_output[clone_id] = clone_values
        register('Warheads', clone_id)
        cloned_warheads[marker] = clone_id
        return clone_id

    animation_ids = {
        animation_id: _clone_auxiliary_id(animation_id, 'AN', occupied)
        for animation_id in chain['animations']
    }
    damage_factor = 1.15 ** damage_count
    for animation_id in chain['animations']:
        source_values = effective_section(art, animation_id)
        clone_values = dict(source_values)
        clone_values.pop('BaseSection', None)
        clone_values.pop('$Inherits', None)
        clone_values.setdefault('Image', source_values.get('Image', animation_id))
        clone_values.update(
            chain.get('animation_overrides', {}).get(animation_id, {})
        )
        for field in ANIMATION_REFERENCE_FIELDS:
            if field not in clone_values:
                continue
            clone_values[field] = ','.join(
                animation_ids.get(item.strip(), item.strip())
                for item in clone_values[field].split(',')
            )
        damage_field = chain.get('damage_fields', {}).get(animation_id)
        if damage_field and damage_count and damage_field in clone_values:
            clone_values[damage_field] = _scaled_integer(
                clone_values[damage_field], damage_factor
            )
        radius_field = chain.get('radius_fields', {}).get(animation_id)
        if radius_field and area_count and radius_field in clone_values:
            try:
                radius = (
                    int(float(clone_values[radius_field]))
                    + int(256 * POWER_AREA_CELLS_PER_STACK * area_count)
                )
                clone_values[radius_field] = str(radius)
            except (TypeError, ValueError):
                pass
        area_warhead = chain.get('area_warheads', {}).get(animation_id)
        if area_warhead and area_count:
            clone_values['Warhead'] = clone_warhead(
                area_warhead, expand_area=True
            )
        art_output[animation_ids[animation_id]] = clone_values
        animation_key = str(len(art_output))
        art_output.setdefault('Animations', {})[
            animation_key
        ] = animation_ids[animation_id]

    weapon_values = effective_section(mission_rules, weapon_id)
    impact_warhead = str(
        chain.get('impact_warhead')
        or weapon_values.get('Warhead')
        or ''
    ).strip()
    if not impact_warhead:
        return {}, {}, power_values
    impact_clone = clone_warhead(
        impact_warhead,
        expand_area=bool(chain.get('expand_impact_area')),
    )
    rule_output[impact_clone]['AnimList'] = animation_ids[chain['root']]
    weapon_clone = _clone_auxiliary_id(weapon_id, 'WP', occupied)
    weapon_clone_values = dict(weapon_values)
    weapon_clone_values.pop('BaseSection', None)
    weapon_clone_values.pop('$Inherits', None)
    weapon_clone_values['Warhead'] = impact_clone
    damage_source = chain.get('damage_source') or {}
    if damage_source:
        base_damage = effective_section(
            mission_rules, damage_source.get('section', '')
        ).get(damage_source.get('field', ''), weapon_clone_values.get('Damage'))
        weapon_clone_values['Damage'] = (
            _scaled_integer(base_damage, damage_factor)
            if damage_count
            else str(base_damage)
        )
    # The standalone provider fires from the physical map border. Remove the
    # native weapon's range gate so every playable target remains valid.
    weapon_clone_values['Range'] = '9999'
    rule_output[weapon_clone] = weapon_clone_values
    register('WeaponTypes', weapon_clone)
    enhanced_power = dict(power_values)
    enhanced_power['WeaponType'] = weapon_clone
    enhanced_power['Range'] = '9999'
    return rule_output, art_output, enhanced_power


def _clone_ion_cannon_effect(
    buff_counts,
    installed,
    authored,
    occupied,
    list_offsets,
):
    """Apply native Ion Cannon buffs after its access is player-exclusive."""
    damage_count = buff_counts.get('damage', 0)
    area_count = buff_counts.get('area', 0)
    if not (damage_count or area_count):
        return {}
    mission_rules = {
        section: dict(values) for section, values in installed.items()
    }
    for section, values in authored.items():
        mission_rules.setdefault(section, {}).update(values)
    combat = effective_section(mission_rules, 'CombatDamage')
    output = {'CombatDamage': {}}
    if damage_count:
        output['CombatDamage']['IonCannonDamage'] = _scaled_integer(
            combat.get('IonCannonDamage', '600'),
            1.15 ** damage_count,
        )
    if area_count:
        warhead_id = str(
            combat.get('IonCannonWarhead') or 'IonCannonWH'
        ).strip()
        clone_id = _clone_auxiliary_id(warhead_id, 'ION', occupied)
        clone_values = dict(effective_section(mission_rules, warhead_id))
        clone_values.pop('BaseSection', None)
        clone_values.pop('$Inherits', None)
        try:
            if 'CellSpread' in clone_values:
                base_spread = float(clone_values['CellSpread'])
            else:
                base_spread = float(clone_values.get('Spread', 0)) / 128.0
        except (TypeError, ValueError):
            base_spread = 0.0
        spread = base_spread + POWER_AREA_CELLS_PER_STACK * area_count
        clone_values['CellSpread'] = f'{spread:.4f}'.rstrip('0').rstrip('.')
        output[clone_id] = clone_values
        key = _next_list_key(installed, authored, 'Warheads', list_offsets)
        output.setdefault('Warheads', {})[key] = clone_id
        output['CombatDamage']['IonCannonWarhead'] = clone_id
    return output


def _exclusive_native_power_rules(
    source_id,
    native_index,
    installed,
    authored,
):
    """Remove native providers/grants while keeping the player reward clone."""
    mission_rules = {
        section: dict(values) for section, values in installed.items()
    }
    for section, values in authored.items():
        mission_rules.setdefault(section, {}).update(values)
    # Native Type=IonCannon must remain installed because player clone uses
    # same engine implementation. Make native entry practically unavailable,
    # then remove every known provider and scripted grant. Player clone keeps
    # configured recharge and receives its own action-34 grant.
    output = {source_id: {'RechargeTime': '9999'}}
    provider_fields_cleared = []
    source_key = source_id.casefold()
    for section, values in mission_rules.items():
        for field in ('SuperWeapon', 'SuperWeapon2', 'SuperWeapons'):
            if field not in values:
                continue
            powers = [
                item.strip() for item in str(values[field]).split(',')
                if item.strip()
            ]
            if source_key not in {item.casefold() for item in powers}:
                continue
            remaining = [
                item for item in powers if item.casefold() != source_key
            ]
            output.setdefault(section, {})[field] = ','.join(remaining)
            provider_fields_cleared.append(f'{section}.{field}')

    native_grants_removed = 0
    for action_id, value in authored.get('Actions', {}).items():
        count, groups = parse_action_groups(str(value))
        if count <= 0 or not groups:
            continue
        changed = False
        rewritten = []
        for group in groups:
            replacement = list(group)
            try:
                grants_native = (
                    replacement[0] in {'33', '34'}
                    and int(replacement[2]) == native_index
                )
            except (TypeError, ValueError, IndexError):
                grants_native = False
            if grants_native:
                replacement = ['0', '0', '0', '0', '0', '0', '0', 'A']
                native_grants_removed += 1
                changed = True
            rewritten.append(replacement)
        if changed:
            output.setdefault('Actions', {})[action_id] = (
                f'{len(rewritten)},{",".join(action_group_tokens(rewritten))}'
            )
    return output, provider_fields_cleared, native_grants_removed


def _provider_coordinates(authored, reserved):
    """Choose an unused launcher cell inside the playable local map."""
    raw_size = str(authored.get('Map', {}).get('Size') or '0,0,100,100')
    raw_local_size = str(
        authored.get('Map', {}).get('LocalSize') or '2,2,96,96'
    )
    try:
        _map_x, _map_y, width, height = (
            int(part.strip()) for part in raw_size.split(',')[:4]
        )
        local_x, local_y, local_width, local_height = (
            int(part.strip()) for part in raw_local_size.split(',')[:4]
        )
    except (TypeError, ValueError):
        width, height = 100, 100
        local_x, local_y, local_width, local_height = 2, 2, 96, 96
    width = max(32, width)
    height = max(32, height)
    occupied = set(reserved)
    for section in ('Structures', 'Units', 'Infantry', 'Aircraft'):
        for value in authored.get(section, {}).values():
            parts = [item.strip() for item in str(value).split(',')]
            if len(parts) < 5:
                continue
            try:
                object_x, object_y = int(parts[3]), int(parts[4])
            except (TypeError, ValueError):
                continue
            clearance = 4 if section == 'Structures' else 1
            for dx in range(-clearance, clearance + 1):
                for dy in range(-clearance, clearance + 1):
                    occupied.add((object_x + dx, object_y + dy))
    # Scenario objects outside LocalSize can exist far enough to grant a power,
    # but BuildingClass::Mission_Missile cannot launch a valid projectile from
    # them. Keep these non-selectable one-cell launchers just inside the playable
    # rectangle so the engine treats them as live launch sites.
    local_right = min(width - 1, local_x + max(1, local_width) - 1)
    local_bottom = min(height - 1, local_y + max(1, local_height) - 1)
    spacing = max(4, min(10, max(4, local_height // 12)))
    for index in range(128):
        lane = index // 12
        slot = index % 12
        rect_x = min(local_right, local_x + 1 + lane)
        rect_y = min(local_bottom, local_y + 2 + slot * spacing)
        candidate = (
            height + rect_x - rect_y,
            rect_x + rect_y,
        )
        if candidate[0] > 0 and candidate[1] > 0 and candidate not in occupied:
            reserved.add(candidate)
            return candidate
    rect_x = min(local_right, local_x + 1)
    rect_y = min(local_bottom, local_y + 1)
    candidate = (height + rect_x - rect_y, rect_x + rect_y)
    reserved.add(candidate)
    return candidate


def player_power_rules(
    mission,
    rewards,
    launch_building_ids=(),
    paratrooper_unit_id='',
    reserved_rules=None,
    production_context=None,
    rule_overlays=None,
):
    """Clone earned powers and grant only the exact scenario player house."""
    installed = ini_sections(GAME_ROOT / 'INI' / 'Rules.ini')
    art = ini_sections(GAME_ROOT / 'INI' / 'Art.ini')
    authored = ini_sections(mission_source_path(mission.get('scenario')))
    allocation_authored = {
        section: dict(values) for section, values in authored.items()
    }
    reserved_rules = reserved_rules or {}
    for section in (
        'SuperWeaponTypes', 'BuildingTypes', 'VehicleTypes', 'AircraftTypes',
        'WeaponTypes', 'Warheads', 'Animations', 'Structures', 'TaskForces',
        'ScriptTypes', 'TeamTypes',
    ):
        allocation_authored.setdefault(section, {}).update(
            reserved_rules.get(section, {})
        )
    mission_rules = {
        section: dict(values) for section, values in installed.items()
    }
    for section, values in authored.items():
        mission_rules.setdefault(section, {}).update(values)
    for section, values in (rule_overlays or {}).items():
        mission_rules.setdefault(section, {}).update(values)
    exclusive_context = {
        section: dict(values) for section, values in mission_rules.items()
    }
    for section, values in reserved_rules.items():
        exclusive_context.setdefault(section, {}).update(values)
    context = (
        dict(production_context)
        if production_context is not None
        else _player_production_context(authored)
    )
    player_house = context['player_house']
    report = {
        'player_house': player_house,
        'applied': [],
        'skipped': [],
        'map_objects_rewritten': 0,
        'enemy_grants': 0,
        'provider_buildings': [],
        'paratrooper_unit': '',
        'paratrooper_buff_source': '',
        'paratrooper_buff_fields': [],
        'paradrop_team': '',
        'paradrop_aircraft': '',
        'exclusive_native_provider_fields': [],
        'exclusive_native_grants_removed': 0,
    }
    if not player_house:
        report['skipped'].append({'power': '*', 'reason': 'missing_player_house'})
        return {}, [], report

    installed_types = [
        str(value).strip()
        for value in installed.get('SuperWeaponTypes', {}).values()
        if str(value).strip()
    ]
    runtime_types = list(installed_types)
    runtime_lookup = {value.casefold() for value in runtime_types}
    for value in authored.get('SuperWeaponTypes', {}).values():
        value = str(value).strip()
        if value and value.casefold() not in runtime_lookup:
            runtime_types.append(value)
            runtime_lookup.add(value.casefold())

    occupied = {
        str(section).casefold()
        for section in set(installed) | set(authored) | set(art)
        | set(reserved_rules)
        if not str(section).upper().startswith('DTA')
    }
    list_offsets = {}
    list_keys = set(installed.get('SuperWeaponTypes', {})) | set(
        allocation_authored.get('SuperWeaponTypes', {})
    )
    numeric_keys = [int(key) for key in list_keys if str(key).isdigit()]
    next_key = max(numeric_keys, default=0) + 1
    rules = {}
    runtime_rule_sections = {}
    runtime_art_sections = {}
    actions = []
    provider_cells = set()
    seen = set()
    power_buff_counts = {}
    recharge_multipliers = {}
    # Local import avoids the definition module's catalogue-time import of
    # POWER_SPECS while still enforcing saved-state stack caps at launch.
    from randomizer.rewards.dta_power_buffs import power_buff_stack_limit
    for reward in rewards or ():
        if (
            reward.get('kind') == 'superweapon'
            and reward.get('superweapon_recharge_multiplier') is not None
        ):
            power_id = str(reward.get('superweapon') or '').upper()
            recharge_multipliers[power_id] = float(
                reward['superweapon_recharge_multiplier']
            )
        if reward.get('dta_player_power_buff'):
            power_id = str(reward.get('superweapon') or '').upper()
            buff_type = str(reward.get('power_buff_type') or '')
            counts = power_buff_counts.setdefault(power_id, {})
            counts[buff_type] = min(
                counts.get(buff_type, 0) + 1,
                power_buff_stack_limit(reward),
            )
    for reward in rewards or ():
        if reward.get('kind') != 'superweapon' or not reward.get('dta_player_power'):
            continue
        source_id = str(reward.get('superweapon') or '').strip()
        marker = source_id.casefold()
        if not source_id or marker in seen:
            continue
        seen.add(marker)
        spec = POWER_SPEC_BY_ID.get(source_id.upper(), {})
        if not spec:
            report['skipped'].append({
                'power': source_id,
                'reason': 'unsupported_or_retired_power',
            })
            continue
        configured_values = spec.get('values')
        if not isinstance(configured_values, dict) or not configured_values.get('Type'):
            report['skipped'].append({'power': source_id, 'reason': 'missing_power_rules'})
            continue
        clone_id = _clone_type_id(source_id, occupied)
        # Start from exact installed/map-local power definition. Config values
        # then apply player identity, recharge, voices, and sidebar adjustments.
        clone_values = dict(effective_section(mission_rules, source_id))
        clone_values.pop('BaseSection', None)
        clone_values.pop('$Inherits', None)
        clone_values.update(configured_values)
        clone_action, _cursor_pair = POWER_CLONE_ACTION_TYPES.get(
            source_id.upper(), ('', '')
        )
        if clone_action:
            clone_values['Action'] = clone_action
        buff_counts = power_buff_counts.get(source_id.upper(), {})
        buff_count = buff_counts.get('recharge', 0)
        if buff_count:
            try:
                recharge = float(clone_values.get('RechargeTime', 0))
                clone_values['RechargeTime'] = str(
                    max(0.01, round(recharge * (0.9 ** buff_count), 3))
                )
            except (TypeError, ValueError):
                pass
        recharge_multiplier = recharge_multipliers.get(source_id.upper(), 1.0)
        if recharge_multiplier != 1.0:
            try:
                recharge = float(clone_values.get('RechargeTime', 0))
                clone_values['RechargeTime'] = str(
                    max(0.01, round(recharge * recharge_multiplier, 3))
                )
            except (TypeError, ValueError):
                pass
        effect_rules, effect_art, clone_values = _clone_power_effect_chain(
            source_id,
            clone_values,
            buff_counts,
            installed,
            allocation_authored,
            art,
            occupied,
            list_offsets,
        )
        for section, values in effect_rules.items():
            runtime_rule_sections.setdefault(section, {}).update(values)
        for section, values in effect_art.items():
            if section == 'Animations':
                registered = runtime_art_sections.setdefault(section, {})
                for animation_id in values.values():
                    registered[str(len(registered) + 1)] = animation_id
            else:
                runtime_art_sections.setdefault(section, {}).update(values)
        if spec.get('exclusive_player'):
            native_index = next(
                (
                    index for index, type_id in enumerate(runtime_types)
                    if type_id.casefold() == source_id.casefold()
                ),
                -1,
            )
            exclusive_rules, cleared_fields, removed_grants = (
                _exclusive_native_power_rules(
                    source_id,
                    native_index,
                    installed,
                    exclusive_context,
                )
            )
            for section, values in exclusive_rules.items():
                rules.setdefault(section, {}).update(values)
            report['exclusive_native_provider_fields'].extend(cleared_fields)
            report['exclusive_native_grants_removed'] += removed_grants
        if source_id.upper() == 'IONCANNONSPECIAL':
            ion_rules = _clone_ion_cannon_effect(
                buff_counts,
                installed,
                allocation_authored,
                occupied,
                list_offsets,
            )
            for section, values in ion_rules.items():
                rules.setdefault(section, {}).update(values)
        rules[clone_id] = clone_values
        payload = spec.get('payload')
        payload_units = ''
        if payload:
            payload_count = buff_counts.get('payload', 0)
            aircraft_id = payload['aircraft_id']
            capacity_field = payload['capacity_field']
            aircraft = effective_section(mission_rules, aircraft_id)
            try:
                base_capacity = int(float(aircraft.get(
                    capacity_field, payload['baseline_capacity']
                )))
            except (TypeError, ValueError):
                base_capacity = int(payload['baseline_capacity'])
            payload_total = max(
                1,
                base_capacity
                + payload_count * int(payload['units_per_buff']),
            )
            payload_units = str(payload_total)
            requested_paratrooper = str(paratrooper_unit_id or '').strip()
            inherited_values = reserved_rules.get(requested_paratrooper, {})
            inherited_buffs = sorted(
                key
                for key, value in inherited_values.items()
                if key in PARATROOPER_BUFF_FIELDS
            )
            house_heap_id = next((
                int(key)
                for key, value in authored.get('Houses', {}).items()
                if str(key).isdigit()
                and str(value).strip().casefold() == player_house.casefold()
            ), None)
            if house_heap_id is not None:
                # Vinifera first searches for PARADROPINF_<HouseHeapID>. A
                # predeclared player-only team bypasses its fallback E1/BADGER
                # task force, so payload and infantry buffs do not touch enemy
                # paradrops or native types.
                team_id = f'PARADROPINF_{house_heap_id}'
                occupied.add(team_id.casefold())
                taskforce_id = _clone_auxiliary_id(
                    source_id, 'PARATF', occupied
                )
                script_id = _clone_auxiliary_id(
                    source_id, 'PARASC', occupied
                )
                aircraft_clone = _clone_auxiliary_id(
                    aircraft_id, 'PARA', occupied
                )
                aircraft_values = dict(
                    effective_section(mission_rules, aircraft_id)
                )
                aircraft_values.pop('BaseSection', None)
                aircraft_values.pop('$Inherits', None)
                aircraft_values['Image'] = aircraft_values.get(
                    'Image', aircraft_id
                )
                aircraft_values[capacity_field] = str(payload_total)
                rules[aircraft_clone] = aircraft_values
                for list_name, type_id in (
                    ('AircraftTypes', aircraft_clone),
                    ('TaskForces', taskforce_id),
                    ('ScriptTypes', script_id),
                    ('TeamTypes', team_id),
                ):
                    key = _next_list_key(
                        installed, allocation_authored, list_name, list_offsets
                    )
                    rules.setdefault(list_name, {})[key] = type_id
                drop_unit = (
                    requested_paratrooper
                    if requested_paratrooper in reserved_rules
                    else 'E1'
                )
                rules[taskforce_id] = {
                    '0': f'{payload_total},{drop_unit}',
                    '1': f'1,{aircraft_clone}',
                    'Name': 'DTA Randomizer Player Paradrop',
                    'Group': '-1',
                }
                rules[script_id] = {
                    '0': '1,100',
                    '1': '11,4',
                    'Name': 'DTA Randomizer Player Paradrop',
                }
                rules[team_id] = {
                    'Name': 'DTA Randomizer Player Paradrop',
                    'Group': '-1',
                    'Max': '1',
                    'Priority': '5',
                    'TechLevel': '0',
                    'VeteranLevel': '1',
                    'House': player_house,
                    'Script': script_id,
                    'TaskForce': taskforce_id,
                    'Waypoint': '100',
                    'Full': 'no',
                    'Whiner': 'no',
                    'Droppod': 'no',
                    'Suicide': 'yes',
                    'Loadable': 'no',
                    'Prebuild': 'no',
                    'Annoyance': 'no',
                    'IonImmune': 'no',
                    'Recruiter': 'no',
                    'Reinforce': 'no',
                    'Aggressive': 'no',
                    'Autocreate': 'no',
                    'GuardSlower': 'no',
                    'OnTransOnly': 'no',
                    'AvoidThreats': 'no',
                    'LooseRecruit': 'no',
                    'IsBaseDefense': 'no',
                    'OnlyTargetHouseEnemy': 'no',
                    'TransportsReturnOnUnload': 'no',
                    'AreTeamMembersRecruitable': 'no',
                }
                report['paratrooper_unit'] = drop_unit
                report['paratrooper_buff_source'] = requested_paratrooper
                report['paratrooper_buff_fields'] = inherited_buffs
                report['paradrop_team'] = team_id
                report['paradrop_aircraft'] = aircraft_clone
        rules.setdefault('SuperWeaponTypes', {})[str(next_key)] = clone_id
        runtime_index = len(runtime_types)
        runtime_types.append(clone_id)
        runtime_lookup.add(clone_id.casefold())
        next_key += 1
        provider_id = ''
        grant_mode = 'trigger'
        provider = spec.get('provider')
        if provider:
            provider_id = _clone_auxiliary_id(source_id, 'PROVIDER', occupied)
            provider_source = str(provider.get('source') or '').strip()
            source_provider_values = effective_section(
                mission_rules, provider_source
            )
            buildable_provider = bool(provider.get('buildable'))
            if buildable_provider:
                provider_values = dict(source_provider_values)
                provider_values.pop('BaseSection', None)
                provider_values.pop('$Inherits', None)
                for key in list(provider_values):
                    folded = str(key).casefold()
                    if (
                        folded in {
                            'owner', 'requiredhouses', 'forbiddenhouses',
                            'builtat', 'factoryowners',
                            'factoryowners.forbidden', 'buildability',
                            'superweapon', 'superweapon2', 'superweapons',
                        }
                        or folded.startswith('prerequisite')
                    ):
                        provider_values.pop(key, None)
                provider_values.update(provider.get('values') or {})
                provider_values.update({
                    'Image': str(
                        source_provider_values.get('Image') or provider_source
                    ),
                    'Owner': context['production_house'],
                    'RequiredHouses': context['production_house'],
                    'TechLevel': '1',
                    'Buildability': 'HumanOnly',
                    'AIBuildThis': 'no',
                    'SuperWeapon': clone_id,
                })
                # Keep the native provider available to campaign AI while the
                # human sees only the prerequisite-free isolated clone.
                rules.setdefault(provider_source, {})[
                    'Buildability'
                ] = 'AIOnly'
                grant_mode = 'building'
            else:
                provider_values = {
                    'BaseSection': provider_source,
                    'Image': str(
                        source_provider_values.get('Image') or provider_source
                    ),
                }
                provider_values.update(provider.get('values') or {})
                provider_values.update({
                    'Name': f'{clone_values["Name"]} Provider',
                    'Strength': '60000',
                    'Owner': context['production_house'],
                    'RequiredHouses': context['production_house'],
                    'TechLevel': '-1',
                    'Power': '0',
                    'Powered': 'no',
                    'Selectable': 'no',
                    'Immune': 'yes',
                    'LegalTarget': 'no',
                    'Insignificant': 'yes',
                    'InvisibleInGame': 'no',
                    'RadarInvisible': 'yes',
                    'BaseNormal': 'no',
                    'WallOwner': 'no',
                    'PlaceAnywhere': 'yes',
                    'NukeSilo': 'yes',
                    'SuperWeapon': clone_id,
                    'HasStupidGuardMode': 'false',
                })
            rules[provider_id] = provider_values
            building_key = _next_list_key(
                installed, allocation_authored, 'BuildingTypes', list_offsets
            )
            rules.setdefault('BuildingTypes', {})[building_key] = provider_id
            provider_x = provider_y = None
            if not buildable_provider:
                structure_key = _next_list_key(
                    installed, allocation_authored, 'Structures', list_offsets
                )
                provider_x, provider_y = _provider_coordinates(
                    authored, provider_cells
                )
                rules.setdefault('Structures', {})[structure_key] = ','.join((
                    player_house,
                    provider_id,
                    '256',
                    str(provider_x),
                    str(provider_y),
                    '0', 'None', '0', '0', '1', '0', '0',
                    'None', 'None', 'None', '1', '0',
                ))
            report['provider_buildings'].append({
                'power': source_id,
                'provider': provider_id,
                'source': provider_source,
                'house': player_house,
                'buildable': buildable_provider,
                'coordinates': (
                    [provider_x, provider_y]
                    if provider_x is not None and provider_y is not None
                    else []
                ),
            })
            if not buildable_provider:
                grant_mode = 'provider'
        else:
            actions.append([
                '34', '0', str(runtime_index), '0', '0', '0', '0', 'A'
            ])
        report['applied'].append({
            'power': source_id,
            'clone': clone_id,
            'runtime_index': runtime_index,
            'house': player_house,
            'action': clone_action,
            'grant_mode': grant_mode,
            'provider': provider_id,
            'provider_source': (
                provider_source if provider_id else ''
            ),
            'recharge_buffs': buff_count,
            'damage_buffs': buff_counts.get('damage', 0),
            'area_buffs': buff_counts.get('area', 0),
            'payload_buffs': buff_counts.get('payload', 0),
            'payload_units': payload_units,
            'payload_aircraft': (
                payload['aircraft_id'] if payload else ''
            ),
        })
    report['_runtime_rules'] = runtime_rule_sections
    report['_runtime_art'] = runtime_art_sections
    return rules, actions, report
