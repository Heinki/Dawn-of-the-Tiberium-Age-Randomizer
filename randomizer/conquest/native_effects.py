"""Automatic house-specific combat, aircraft and infrastructure effects."""

from copy import deepcopy

from randomizer.dta.rules import comma_items
from randomizer.dta.aircraft import docked_reload_time as _reload_time
from randomizer.final_fortress.engine import _private_type
from randomizer.final_fortress.utilities import infrastructure_building, unit_updates
from .teams import HOUSE_ALIASES


WEAPONS = ('Primary', 'Secondary', 'Elite', 'ElitePrimary', 'EliteSecondary')
TYPE_LISTS = ('InfantryTypes', 'VehicleTypes', 'AircraftTypes', 'BuildingTypes')


def _combat_weapon(rules, name):
    row = rules.get(name, {})
    try:
        return (float(row.get('Damage', 0)) > 0 and float(row.get('Range', 0)) > 0 and
                row.get('Suicide', 'no').casefold() not in ('yes', 'true', '1'))
    except ValueError:
        return False


def apply_effects(writer, members, *, balance_version=4):
    """Preserve separate upgrades even when both opponents use one faction."""
    rules = writer.rules
    aliases = {}
    categories = {kind: category for category in TYPE_LISTS for kind in rules[category].values()}
    for member in members:
        loadout = member['loadout']
        rank = loadout['perks'].get('extended_arsenal', 0)
        repairs = loadout.get('field_repairs', False)
        rearm = loadout['perks'].get('rapid_rearm', 0)
        hardening = loadout['perks'].get('hardened_infrastructure', 0)
        hazard = loadout['perks'].get('hazard_training', 0)
        health_percent = min(50, hardening * 10) if balance_version >= 4 else hardening * 15
        rearm_percent = min(50, rearm * 10) if balance_version >= 4 else rearm * 15
        cache = aliases[member['slot']] = {}
        if not any((rank, repairs, rearm, hardening, hazard)):
            continue
        owner = HOUSE_ALIASES[member['slot']]
        country = loadout['country']
        for kind, category in categories.items():
            row = rules[kind]
            required = comma_items(row.get('RequiredHouses'))
            if (country not in comma_items(row.get('Owner')) or
                required and country not in required or country in comma_items(row.get('ForbiddenHouses'))):
                continue
            combat = any(_combat_weapon(rules, row.get(field)) for field in WEAPONS)
            infrastructure = category == 'BuildingTypes' and infrastructure_building(kind, row, defense=combat)
            combat_effect = combat and (rank or repairs and category != 'BuildingTypes') and not row.get('Factory')
            if not (combat_effect or rearm and _reload_time(rules, category, row) or
                    hardening and infrastructure or hazard and category == 'InfantryTypes'):
                continue
            _private_type(writer, kind, suffix='CQ', owners=[owner], cache=cache)
        weapons = {}
        for kind, alias in list(cache.items()):
            row = writer.sections[alias]
            original = rules[kind]
            if hazard and categories[kind] == 'InfantryTypes':
                row['TiberiumProof'] = 'yes'
            if hardening and categories[kind] == 'BuildingTypes':
                row.update(unit_updates(kind, original,
                    {'infrastructure_health_percent': health_percent}, building=True,
                    defense=any(_combat_weapon(rules, original.get(field)) for field in WEAPONS)))
            reload_time = _reload_time(rules, categories[kind], original)
            if rearm and reload_time:
                row['ReloadRate'] = f'{reload_time * (100 - rearm_percent) / 100:.8g}'
            if repairs and categories[kind] != 'BuildingTypes' and any(
                    _combat_weapon(rules, original.get(field)) for field in WEAPONS):
                row['SelfHealing'] = 'yes'
                cap = original.get('SelfHealingCap', rules.get('General', {}).get('SelfHealCap', '50%'))
                cap = float(cap.rstrip('%')) / (100 if cap.endswith('%') else 1)
                row['SelfHealingCap'] = f'{max(.5, cap):g}'
                row['SelfHealingRate'] = str(min(.016, float(original.get('SelfHealingRate', '.016'))))
                row['SelfHealingStep'] = str(max(10, int(original.get('SelfHealingStep', '10'))))
            for field in WEAPONS:
                name = original.get(field)
                if not rank or not _combat_weapon(rules, name):
                    continue
                if name not in weapons:
                    weapon = deepcopy(rules[name])
                    weapon['Range'] = f'{float(weapon["Range"]) + rank:g}'
                    if float(weapon.get('ProjectileRange', 0)) > 0:
                        weapon['ProjectileRange'] = f'{float(weapon["ProjectileRange"]) + rank:g}'
                    weapons[name] = writer.key()
                    writer.sections[weapons[name]] = weapon
                row[field] = weapons[name]
            # First-ownable AI lookups do not consult ForbiddenHouses.
            current = {**original, **writer.sections.get(kind, {})}
            writer.put(kind, 'Owner', ','.join(v for v in comma_items(current.get('Owner')) if v != owner))
            writer.put(kind, 'ForbiddenHouses', ','.join(dict.fromkeys([
                *comma_items(current.get('ForbiddenHouses')), owner])))
        # Preserve each private building's production, deployment and docking
        # relationships. Recursive MCV copies must deploy into private yards.
        for alias in cache.values():
            row = writer.sections[alias]
            for field in ('BuiltAt', 'Dock', 'FreeUnit', 'PowersUpBuilding', 'ClonedAs',
                          'DeploysInto', 'UndeploysInto', 'TransformsInto'):
                if field in row:
                    values = comma_items(row[field])
                    mapped = [cache.get(v, v) for v in values]
                    row[field] = ','.join(dict.fromkeys([*values, *mapped] if field in ('BuiltAt', 'Dock') else mapped))

    if not any(aliases.values()):
        return aliases
    # Keep prerequisites and native construction choices valid for private
    # defenses and deployed forms, without replacing another house's types.
    for category in ('General', 'AI'):
        for key, value in rules.get(category, {}).items():
            if (category == 'AI' and not key.startswith('Build') or
                category == 'General' and not key.startswith('Prerequisite') and
                key not in ('BuildConst', 'BaseUnit', 'HarvesterUnit', 'PadAircraft', 'BuildRefinery')):
                continue
            current = comma_items(writer.sections.get(category, {}).get(key, value))
            additions = [cache[v] for cache in aliases.values() for v in comma_items(value) if v in cache]
            if additions:
                writer.put(category, key, ','.join(dict.fromkeys([*current, *additions])))
    buildings = {kind for cache in aliases.values() for kind in cache if categories[kind] == 'BuildingTypes'}
    # Native collectors and unmodified/captured aircraft must still recognize
    # private copies of their existing docking families. Never add other pads.
    for kind, original in rules.items():
        docks = comma_items(original.get('Dock'))
        additions = [cache[v] for cache in aliases.values() for v in docks if v in cache and v in buildings]
        if additions:
            current = comma_items(writer.sections.get(kind, {}).get('Dock', original['Dock']))
            writer.put(kind, 'Dock', ','.join(dict.fromkeys([*current, *additions])))
    for kind in sorted(buildings):
        group = 'DCQPRE_' + kind
        copies = [cache[kind] for cache in aliases.values() if kind in cache]
        writer.put('PrerequisiteGroups', group, ','.join([kind, *copies]))
        for target, original in [*rules.items(), *list(writer.sections.items())]:
            current = {**original, **writer.sections.get(target, {})}
            items = comma_items(current.get('Prerequisite'))
            if kind in items:
                writer.put(target, 'Prerequisite', ','.join(group if item == kind else item for item in items))
        for key, value in rules.get('PrerequisiteGroups', {}).items():
            if kind in comma_items(value):
                current = comma_items(writer.sections.get('PrerequisiteGroups', {}).get(key, value))
                writer.put('PrerequisiteGroups', key, ','.join(dict.fromkeys([*current, *copies])))
    return aliases
