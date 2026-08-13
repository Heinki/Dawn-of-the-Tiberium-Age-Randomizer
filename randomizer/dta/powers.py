"""Player-only DTA superweapon and support-power rewards."""

from hashlib import sha1

from randomizer.core.paths import GAME_ROOT
from randomizer.dta.clones import _player_production_context
from randomizer.dta.maps import mission_source_path
from randomizer.dta.rules import effective_section, ini_sections


POWER_EFFECT_CHAINS = {
    'AIRSTRIKESPECIAL': {
        'root': 'AIRSINIT',
        'animations': (
            'AIRSINIT', 'AIRSTIMR', 'AIRSBOMB', 'AIRSEXPL', 'AIRSSPRD',
            'AIRSSTRT', 'AIRSAPPR', 'AIRSSHOT', 'AIRSMISS', 'AIRSATTK',
            'AIRSEXIT',
        ),
        'damage_fields': {'AIRSEXPL': 'Damage', 'AIRSSPRD': 'Damage'},
        'radius_fields': {'AIRSEXPL': 'DamageRadius', 'AIRSSPRD': 'DamageRadius'},
    },
    'CHEMICALSPECIAL': {
        'root': 'NUKEINIT',
        'animations': ('NUKEINIT', 'NUKEDOWN', 'ATOMEXPL'),
        'damage_fields': {'ATOMEXPL': 'ExplosionDamage'},
        'area_warheads': {'ATOMEXPL': 'AtomicWH'},
    },
    'MULTISPECIAL': {
        'root': 'NUKEINIT',
        'animations': ('NUKEINIT', 'NUKEDOWN', 'ATOMEXPL'),
        'damage_fields': {'ATOMEXPL': 'ExplosionDamage'},
        'area_warheads': {'ATOMEXPL': 'AtomicWH'},
    },
    'VORTEXSPECIAL': {
        'root': 'REVERSED_CHRONOSHIFT',
        'animations': (
            'REVERSED_CHRONOSHIFT', 'R_CHRONOSHIFT_OUTER',
            'CHRONO_VORTEX', 'CHRONO_VORTEX_CENTER',
            'CHRONO_VORTEX_SHADOW', 'CHRONO_VORTEX_LIGHTNING',
        ),
        'damage_fields': {
            'CHRONO_VORTEX': 'Damage',
            'CHRONO_VORTEX_LIGHTNING': 'Damage',
        },
        'area_warheads': {'CHRONO_VORTEX': 'VortexWH'},
    },
}

ANIMATION_REFERENCE_FIELDS = {
    'Next', 'TrailerAnim', 'ExpireAnim', 'StartAnims', 'MiddleAnims',
}


POWER_SPECS = (
    {
        'id': 'IonCannonSpecial',
        'label': 'GDI Ion Cannon',
        'description': 'Grants a repeating player-only Ion Cannon.',
        'factions': ('GDI',),
        'category': 'offensive',
    },
    {
        'id': 'AirstrikeSpecial',
        'label': 'GDI Airstrike',
        'description': 'Grants a repeating player-only Airstrike.',
        'factions': ('GDI',),
        'category': 'offensive',
    },
    {
        'id': 'ChemicalSpecial',
        'label': 'Nod Nuclear Strike',
        'description': 'Grants a repeating player-only Nod Nuclear Strike.',
        'factions': ('Nod',),
        'category': 'offensive',
    },
    {
        'id': 'VortexSpecial',
        'label': 'Allied Chrono Vortex',
        'description': 'Grants a repeating player-only Chrono Vortex.',
        'factions': ('Allies',),
        'category': 'offensive',
    },
    {
        'id': 'HuntSeekSpecial',
        'label': 'Allied Chrono Tank',
        'description': (
            'Deploys a repeating teleport-mode Allied Chrono Tank.'
        ),
        'factions': ('Allies',),
        'category': 'aid',
    },
    {
        'id': 'MultiSpecial',
        'label': 'Soviet Nuclear Strike',
        'description': 'Grants a repeating player-only Soviet Nuclear Strike.',
        'factions': ('Soviet',),
        'category': 'offensive',
    },
    {
        'id': 'DropPodSpecial',
        'label': 'Soviet Paratroopers',
        'description': 'Grants the repeating Soviet Paratroopers support power.',
        'factions': ('Soviet',),
        'category': 'aid',
    },
)

POWER_SPEC_BY_ID = {spec['id'].upper(): spec for spec in POWER_SPECS}
MAX_TYPE_ID_LENGTH = 23


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
    """Clone animation damage/radius chains for one player-only power."""
    chain = POWER_EFFECT_CHAINS.get(source_id.upper())
    damage_count = buff_counts.get('damage', 0)
    area_count = buff_counts.get('area', 0)
    weapon_id = str(power_values.get('WeaponType') or '').strip()
    if not chain or not weapon_id or not (damage_count or area_count):
        return {}, power_values

    mission_rules = {
        section: dict(values) for section, values in installed.items()
    }
    for section, values in authored.items():
        mission_rules.setdefault(section, {}).update(values)
    output = {}

    def register(list_name, type_id):
        key = _next_list_key(
            installed, authored, list_name, list_offsets
        )
        output.setdefault(list_name, {})[key] = type_id

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
        if expand_area and area_count and 'CellSpread' in clone_values:
            try:
                spread = float(clone_values['CellSpread']) + 0.5 * area_count
                clone_values['CellSpread'] = f'{spread:.3f}'.rstrip('0').rstrip('.')
            except (TypeError, ValueError):
                pass
        output[clone_id] = clone_values
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
        clone_values.setdefault('Image', source_values.get('Image', animation_id))
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
                radius = int(float(clone_values[radius_field])) + 128 * area_count
                clone_values[radius_field] = str(radius)
            except (TypeError, ValueError):
                pass
        area_warhead = chain.get('area_warheads', {}).get(animation_id)
        if area_warhead and area_count:
            clone_values['Warhead'] = clone_warhead(
                area_warhead, expand_area=True
            )
        output[animation_ids[animation_id]] = clone_values
        register('Animations', animation_ids[animation_id])

    weapon_values = effective_section(mission_rules, weapon_id)
    impact_warhead = str(weapon_values.get('Warhead') or '').strip()
    if not impact_warhead:
        return {}, power_values
    impact_clone = clone_warhead(impact_warhead)
    output[impact_clone]['AnimList'] = animation_ids[chain['root']]
    weapon_clone = _clone_auxiliary_id(weapon_id, 'WP', occupied)
    weapon_clone_values = dict(weapon_values)
    weapon_clone_values.pop('BaseSection', None)
    weapon_clone_values['Warhead'] = impact_clone
    output[weapon_clone] = weapon_clone_values
    register('WeaponTypes', weapon_clone)
    enhanced_power = dict(power_values)
    enhanced_power['WeaponType'] = weapon_clone
    return output, enhanced_power


def player_power_rules(mission, rewards):
    """Clone earned powers and grant only the exact scenario player house."""
    installed = ini_sections(GAME_ROOT / 'INI' / 'Rules.ini')
    art = ini_sections(GAME_ROOT / 'INI' / 'Art.ini')
    authored = ini_sections(mission_source_path(mission.get('scenario')))
    mission_rules = {
        section: dict(values) for section, values in installed.items()
    }
    for section, values in authored.items():
        mission_rules.setdefault(section, {}).update(values)
    context = _player_production_context(authored)
    player_house = context['player_house']
    report = {
        'player_house': player_house,
        'applied': [],
        'skipped': [],
        'map_objects_rewritten': 0,
        'enemy_grants': 0,
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
    }
    list_offsets = {}
    list_keys = set(installed.get('SuperWeaponTypes', {})) | set(
        authored.get('SuperWeaponTypes', {})
    )
    numeric_keys = [int(key) for key in list_keys if str(key).isdigit()]
    next_key = max(numeric_keys, default=0) + 1
    rules = {}
    actions = []
    seen = set()
    power_buff_counts = {}
    for reward in rewards or ():
        if reward.get('dta_player_power_buff'):
            power_id = str(reward.get('superweapon') or '').upper()
            buff_type = str(reward.get('power_buff_type') or '')
            counts = power_buff_counts.setdefault(power_id, {})
            counts[buff_type] = counts.get(buff_type, 0) + 1
    for reward in rewards or ():
        if reward.get('kind') != 'superweapon' or not reward.get('dta_player_power'):
            continue
        source_id = str(reward.get('superweapon') or '').strip()
        marker = source_id.casefold()
        if not source_id or marker in seen:
            continue
        seen.add(marker)
        spec = POWER_SPEC_BY_ID.get(source_id.upper(), {})
        source_values = effective_section(mission_rules, source_id)
        if not source_values or not source_values.get('Type'):
            source_values = dict(spec.get('template', {}))
        if not source_values or not source_values.get('Type'):
            report['skipped'].append({'power': source_id, 'reason': 'missing_power_rules'})
            continue
        clone_id = _clone_type_id(source_id, occupied)
        clone_values = dict(source_values)
        clone_values.pop('BaseSection', None)
        clone_values['Name'] = POWER_SPEC_BY_ID.get(
            source_id.upper(), {}
        ).get('label', clone_values.get('Name', source_id))
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
        effect_rules, clone_values = _clone_power_effect_chain(
            source_id,
            clone_values,
            buff_counts,
            installed,
            authored,
            art,
            occupied,
            list_offsets,
        )
        for section, values in effect_rules.items():
            rules.setdefault(section, {}).update(values)
        rules[clone_id] = clone_values
        if source_id.upper() == 'HUNTSEEKSPECIAL':
            # Vinifera resolves this power through the owning Side extension.
            # DTA names the power Chrono Tank but leaves AlliesSide blank, so
            # activation otherwise aborts without creating anything.
            chrono_id = _clone_auxiliary_id('CTNKT', 'HS', occupied)
            chrono_values = effective_section(mission_rules, 'CTNKT')
            if not chrono_values:
                report['skipped'].append({
                    'power': source_id,
                    'reason': 'missing_chrono_tank_teleport_mode',
                })
                continue
            chrono_values = dict(chrono_values)
            chrono_values.pop('BaseSection', None)
            chrono_values['HunterSeeker'] = 'yes'
            chrono_values['TechLevel'] = '-1'
            chrono_values['AllowedToStartInMultiplayer'] = 'no'
            rules[chrono_id] = chrono_values
            vehicle_key = _next_list_key(
                installed, authored, 'VehicleTypes', list_offsets
            )
            rules.setdefault('VehicleTypes', {})[vehicle_key] = chrono_id
            rules.setdefault('AlliesSide', {})['HunterSeeker'] = chrono_id
        rules.setdefault('SuperWeaponTypes', {})[str(next_key)] = clone_id
        runtime_index = len(runtime_types)
        runtime_types.append(clone_id)
        runtime_lookup.add(clone_id.casefold())
        next_key += 1
        actions.append(['34', '0', str(runtime_index), '0', '0', '0', '0', 'A'])
        report['applied'].append({
            'power': source_id,
            'clone': clone_id,
            'runtime_index': runtime_index,
            'house': player_house,
            'recharge_buffs': buff_count,
            'damage_buffs': buff_counts.get('damage', 0),
            'area_buffs': buff_counts.get('area', 0),
        })
    return rules, actions, report
