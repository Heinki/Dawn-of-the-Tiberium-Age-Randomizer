"""Live DTA Rules.ini catalogue and conservative unit collision audits."""

import re
from functools import lru_cache
from pathlib import Path

from randomizer.core.paths import GAME_ROOT


PLAYABLE_FACTIONS = ('GDI', 'Nod', 'Allies', 'Soviet')
ALWAYS_AVAILABLE_MOBILE_IDS = frozenset({
    'ENGINEER',
    'GMCV', 'NMCV', 'AMCV', 'SMCV',
    'TDHARV', 'RAHARV',
    'GLST', 'NLST', 'ALST', 'SLST',
})
# Installed campaign identities made buildable by mission progression or used
# as reviewed human reward units despite a global TechLevel of -1.
CAMPAIGN_SPECIAL_MOBILE_IDS = frozenset({
    'BFRT', 'COASTARTY', 'MSA', 'SHILKA',
})
TYPE_LISTS = {
    'InfantryTypes': 'infantry',
    'VehicleTypes': 'vehicles',
    'AircraftTypes': 'aircraft',
    'BuildingTypes': 'buildings',
    'SuperWeaponTypes': 'superweapons',
}


def ini_sections(path):
    sections = {}
    current = None
    for raw in Path(path).read_text(encoding='cp1252', errors='ignore').splitlines():
        line = raw.split(';', 1)[0].strip()
        if line.startswith('[') and line.endswith(']'):
            current = line[1:-1].strip()
            sections.setdefault(current, {})
        elif current and '=' in line:
            key, value = line.split('=', 1)
            sections[current][key.strip()] = value.strip()
    return sections


def comma_items(value):
    return tuple(item.strip() for item in str(value or '').split(',') if item.strip())


def effective_section(sections, section_id, _seen=None):
    """Resolve Vinifera ``BaseSection`` inheritance for one INI section."""
    lookup = {str(name).casefold(): (name, values) for name, values in sections.items()}
    item = lookup.get(str(section_id or '').casefold())
    if item is None:
        return {}
    actual_name, values = item
    seen = set(_seen or ())
    marker = actual_name.casefold()
    if marker in seen:
        return dict(values)
    seen.add(marker)
    base_name = values.get('BaseSection', '')
    merged = effective_section(sections, base_name, seen) if base_name else {}
    merged.update(values)
    return merged


@lru_cache(maxsize=1)
def techno_catalogue():
    """Build the DTA catalogue from the installed consolidated Rules.ini."""
    sections = ini_sections(GAME_ROOT / 'INI' / 'Rules.ini')
    records = []
    for list_name, category in TYPE_LISTS.items():
        for type_id in sections.get(list_name, {}).values():
            values = effective_section(sections, type_id)
            owners = comma_items(values.get('Owner'))
            required = comma_items(values.get('RequiredHouses'))
            forbidden = comma_items(values.get('ForbiddenHouses'))
            try:
                tech_level = int(values.get('TechLevel', -1))
            except ValueError:
                tech_level = -1
            try:
                cost = int(values.get('Cost', 0))
            except ValueError:
                cost = 0
            try:
                speed = int(float(values.get('Speed', 0)))
            except ValueError:
                speed = 0
            try:
                strength = int(float(values.get('Strength', 0)))
            except ValueError:
                strength = 0
            playable_owners = tuple(
                faction for faction in PLAYABLE_FACTIONS
                if faction in owners
                and (not required or faction in required)
                and faction not in forbidden
            )
            editor_name = values.get('EditorName', '')
            editor_category = values.get('EditorCategory', '')
            buildability = values.get('Buildability', '')
            obsolete = editor_name.casefold().startswith('obsolete')
            ai_only = buildability.casefold() == 'aionly'
            campaign_special = (
                type_id.upper() in CAMPAIGN_SPECIAL_MOBILE_IDS
                or editor_category.casefold() == 'special units'
                or buildability.casefold() == 'humanonly'
            )
            rewardable = bool(
                playable_owners
                and cost > 0
                and not obsolete
                and not ai_only
                and (
                    tech_level >= 0
                    or campaign_special
                )
            )
            records.append({
                'id': type_id.upper(),
                'label': values.get('Name') or values.get('UIName') or type_id,
                'editor_name': editor_name,
                'editor_category': editor_category,
                'buildability': buildability,
                'category': category,
                'owners': owners,
                'playable_owners': playable_owners,
                'prerequisites': comma_items(values.get('Prerequisite')),
                'tech_level': tech_level,
                'cost': cost,
                'speed': speed,
                'strength': strength,
                'image': values.get('Image', type_id).upper(),
                'primary_weapon': values.get('Primary', ''),
                'secondary_weapon': values.get('Secondary', ''),
                'deploys_into': values.get('DeploysInto', ''),
                'undeploys_into': values.get('UndeploysInto', ''),
                'naval': values.get('Naval', '').casefold() in {
                    'yes', 'true', '1',
                },
                'special': campaign_special,
                'obsolete': obsolete,
                'ai_only': ai_only,
                'rewardable': rewardable,
                'buildable': bool(playable_owners and tech_level >= 0 and cost > 0),
                'duplicate_of': '',
            })

    # Mission-only country aliases sometimes duplicate a normal skirmish unit
    # byte-for-byte while changing only Owner/Prerequisite (E1N, E3N, APCN).
    # Keep one reward identity when an earlier canonical type covers every
    # playable owner of the alias.
    canonical_by_signature = {}
    for record in records:
        if record['category'] not in {'infantry', 'vehicles', 'aircraft'}:
            continue
        if record['obsolete'] or record['ai_only'] or record['id'].startswith('AI'):
            continue
        signature = (
            record['category'], record['label'].casefold(), record['image'],
            record['primary_weapon'].casefold(),
            record['secondary_weapon'].casefold(),
            record['cost'], record['speed'], record['strength'],
            str(record['deploys_into']).casefold(),
            str(record['undeploys_into']).casefold(),
        )
        prior = canonical_by_signature.get(signature)
        if (
            prior
            and set(record['playable_owners']).issubset(
                prior['playable_owners']
            )
        ):
            record['duplicate_of'] = prior['id']
            continue
        canonical_by_signature[signature] = record
    return tuple(records)


def catalogue_by_id():
    return {record['id']: record for record in techno_catalogue()}


def _player_houses(sections):
    houses = set()
    player = sections.get('Basic', {}).get('Player')
    if player:
        houses.add(player.casefold())
    for section, values in sections.items():
        if values.get('PlayerControl', '').casefold() in {'yes', 'true', '1'}:
            houses.add(section.casefold())
    return houses


def _token_occurs(value, wanted):
    return wanted in {
        token.upper()
        for token in re.split(r'[^A-Za-z0-9_]+', str(value or ''))
        if token
    }


def unit_collision_report(map_path, unit_id):
    """Return every reason an original type is unsafe for a map-local buff.

    The scan is intentionally conservative. Any authored TaskForce or generic
    script reference keeps the original type unchanged; a later production
    adapter may route only newly built human units to a clone.
    """
    unit_id = str(unit_id or '').upper()
    sections = ini_sections(map_path)
    player_houses = _player_houses(sections)
    nonplayer_placements = []
    player_placements = []
    for section_name in ('Infantry', 'Units', 'Aircraft', 'Structures'):
        for key, value in sections.get(section_name, {}).items():
            fields = comma_items(value)
            if len(fields) < 2 or fields[1].upper() != unit_id:
                continue
            entry = {'section': section_name, 'key': key, 'house': fields[0]}
            if fields[0].casefold() in player_houses:
                player_placements.append(entry)
            else:
                nonplayer_placements.append(entry)

    taskforce_refs = []
    scripted_refs = []
    taskforce_sections = {
        section_id.casefold()
        for section_id in sections.get('TaskForces', {}).values()
    }
    ignored_sections = {
        'Infantry', 'Units', 'Aircraft', 'Structures',
        'InfantryTypes', 'VehicleTypes', 'AircraftTypes', 'BuildingTypes',
    }
    for section_name, values in sections.items():
        for key, value in values.items():
            if not _token_occurs(value, unit_id):
                continue
            reference = {'section': section_name, 'key': key}
            if section_name.casefold() in taskforce_sections:
                taskforce_refs.append(reference)
            elif section_name not in ignored_sections and section_name.upper() != unit_id:
                scripted_refs.append(reference)

    catalogue = catalogue_by_id()
    target = catalogue.get(unit_id, {})
    weapons = {
        target.get('primary_weapon', '').upper(),
        target.get('secondary_weapon', '').upper(),
    } - {''}
    shared_weapon_users = sorted(
        record['id'] for record in catalogue.values()
        if record['id'] != unit_id
        and weapons.intersection({
            record.get('primary_weapon', '').upper(),
            record.get('secondary_weapon', '').upper(),
        })
    )
    reasons = []
    if nonplayer_placements:
        reasons.append('nonplayer_map_placement')
    if taskforce_refs:
        reasons.append('authored_taskforce_reference')
    if scripted_refs:
        reasons.append('authored_script_reference')
    if shared_weapon_users:
        reasons.append('shared_weapon_dependency')
    return {
        'unit_id': unit_id,
        'player_placements': player_placements,
        'nonplayer_placements': nonplayer_placements,
        'taskforce_references': taskforce_refs,
        'scripted_references': scripted_refs,
        'shared_weapon_users': shared_weapon_users,
        'original_type_buff_safe': not reasons,
        'requires_production_clone': bool(reasons),
        'reasons': reasons,
        'map_objects_must_remain_original': True,
    }
