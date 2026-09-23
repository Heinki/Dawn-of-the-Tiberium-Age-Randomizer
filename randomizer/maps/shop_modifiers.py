"""Apply Shop run modifiers to isolated player clone sections."""

from randomizer.config.tuning import stacking_multiplier
from randomizer.rewards.catalogue import BUFF_TARGETS


_COMBAT_CATEGORIES = frozenset({'infantry', 'units', 'aircraft'})
_MOBILE_TYPE_LISTS = ('InfantryTypes', 'VehicleTypes', 'AircraftTypes')
_TECHNO_TYPE_LISTS = (*_MOBILE_TYPE_LISTS, 'BuildingTypes')
_WEAPON_REFERENCE_FIELDS = frozenset({
    'primary', 'secondary', 'elite', 'eliteprimary', 'elitesecondary',
    'deathweapon', 'explosion',
})


def _key(values, requested):
    requested = requested.casefold()
    return next(
        (key for key in values if str(key).casefold() == requested),
        None,
    )


def _number(values, requested, fallback):
    key = _key(values, requested)
    try:
        return float(values[key]) if key is not None else float(fallback)
    except (TypeError, ValueError):
        return float(fallback)


def _set_number(values, requested, value, *, integer=False):
    key = _key(values, requested) or requested
    if integer:
        values[key] = str(max(1, int(round(value))))
    else:
        rendered = f'{float(value):.6f}'.rstrip('0').rstrip('.')
        values[key] = rendered or '0'


def apply_shop_clone_modifiers(rule_sections, handled_by_unit, settings):
    """Compose run modifiers after normal Shop buff clone calculation."""
    if isinstance(handled_by_unit, dict) and 'applied' in handled_by_unit:
        report = handled_by_unit
        handled_by_unit = {}
        weapon_fields = {
            'primary', 'secondary', 'elite', 'eliteprimary', 'elitesecondary',
            'deathweapon', 'explosion',
        }
        for item in report.get('applied', ()):
            source_id = str(item.get('unit') or '').upper()
            clone_id = str(item.get('output_type') or '')
            linked_routes = list(item.get('linked_deploy_routes') or ())
            linked_route = item.get('linked_deploy_route')
            if linked_route and linked_route not in linked_routes:
                linked_routes.append(linked_route)
            clone_ids = [
                candidate for candidate in dict.fromkeys((
                    clone_id,
                    *(
                        str(route.get('output_type') or '')
                        for route in linked_routes
                    ),
                ))
                if candidate in rule_sections
            ]
            weapon_ids = {
                str(value)
                for candidate in clone_ids
                for key, value in rule_sections.get(candidate, {}).items()
                if (
                    str(key).casefold() in weapon_fields
                    and str(value) in rule_sections
                    and _key(rule_sections[str(value)], 'Damage') is not None
                )
            }
            handled_by_unit[source_id] = {
                'clone_id': clone_id,
                'clone_ids': clone_ids,
                'weapon_clone_ids': {
                    weapon_id: weapon_id for weapon_id in weapon_ids
                },
            }
    damage_factor = float(settings.get('shop_player_damage_percent', 1.0))
    armor_factor = float(settings.get('shop_player_armor_percent', 1.0))
    production_factor = float(
        settings.get('shop_production_time_percent', 1.0)
    )
    combat_production_factor = float(
        settings.get('shop_combat_production_time_percent', 1.0)
    )
    cost_factor = float(settings.get('shop_player_cost_percent', 1.0))
    armor_seed_stacks = {
        str(key).upper(): max(0, int(value))
        for key, value in dict(settings.get(
            'shop_modifier_armor_seed_stacks', {}
        )).items()
    }
    damage_seed_stacks = {
        str(key).upper(): max(0, int(value))
        for key, value in dict(settings.get(
            'shop_modifier_damage_seed_stacks', {}
        )).items()
    }
    counts = {
        'damage_weapons': 0,
        'armor_clones': 0,
        'production_clones': 0,
        'cost_clones': 0,
    }
    for source_id, details in handled_by_unit.items():
        clone_id = str((details or {}).get('clone_id') or '')
        clone_values = rule_sections.get(clone_id)
        if not clone_id or clone_values is None:
            continue
        clone_ids = list(dict.fromkeys(
            str(candidate)
            for candidate in (
                (details or {}).get('clone_ids') or (clone_id,)
            )
            if str(candidate) in rule_sections
        ))
        target = BUFF_TARGETS.get(str(source_id).upper(), {})
        category = str(target.get('category') or '')

        if armor_factor != 1.0:
            base_strength = target.get('strength', 1)
            # active_launch_rewards adds one Armor stack solely to guarantee
            # an isolated clone. Remove that seed stack, then apply the run
            # tradeoff to every deploy/transform form's fully buffed value.
            existing_stacks = armor_seed_stacks.get(str(source_id).upper())
            correction = armor_factor
            if existing_stacks is not None:
                correction *= (
                    stacking_multiplier('armor', existing_stacks + 1)
                    / stacking_multiplier('armor', existing_stacks)
                )
            for candidate in clone_ids:
                candidate_values = rule_sections[candidate]
                current = _number(
                    candidate_values, 'Strength', base_strength
                )
                _set_number(
                    candidate_values,
                    'Strength',
                    current * correction,
                    integer=True,
                )
                counts['armor_clones'] += 1

        combined_production = production_factor
        if category in _COMBAT_CATEGORIES:
            combined_production *= combat_production_factor
        if combined_production != 1.0:
            current = _number(clone_values, 'BuildTimeMultiplier', 1.0)
            _set_number(
                clone_values,
                'BuildTimeMultiplier',
                current * combined_production,
            )
            counts['production_clones'] += 1

        if cost_factor != 1.0 and category in _COMBAT_CATEGORIES:
            current = _number(clone_values, 'Cost', target.get('cost', 1))
            _set_number(clone_values, 'Cost', current * cost_factor, integer=True)
            counts['cost_clones'] += 1

        if damage_factor != 1.0:
            existing_stacks = damage_seed_stacks.get(str(source_id).upper())
            correction = damage_factor
            if existing_stacks is not None:
                correction *= (
                    stacking_multiplier('damage', existing_stacks)
                    / stacking_multiplier('damage', existing_stacks + 1)
                )
            for weapon_clone_id in dict(
                (details or {}).get('weapon_clone_ids') or {}
            ).values():
                weapon_values = rule_sections.get(str(weapon_clone_id), {})
                damage_key = _key(weapon_values, 'Damage')
                if damage_key is None:
                    continue
                try:
                    current = float(weapon_values[damage_key])
                except (TypeError, ValueError):
                    continue
                _set_number(
                    weapon_values,
                    'Damage',
                    current * correction,
                    integer=True,
                )
                counts['damage_weapons'] += 1
    return counts


def _registered_ids(installed_sections, map_sections, rule_sections, list_name):
    values = []
    for source in (installed_sections, map_sections, rule_sections):
        values.extend((source.get(list_name) or {}).values())
    return tuple(dict.fromkeys(
        str(value).strip() for value in values if str(value).strip()
    ))


def _effective_values(section_id, installed_sections, map_sections, rule_sections):
    values = dict(installed_sections.get(section_id, {}))
    values.update(map_sections.get(section_id, {}))
    values.update(rule_sections.get(section_id, {}))
    return values


def apply_shop_global_modifiers(
    rule_sections,
    source_lines,
    installed_sections,
    settings,
):
    """Apply intentionally global Shop chaos modifiers after clone creation."""
    from randomizer.maps.ini import all_section_value_maps

    demolition = bool(settings.get('shop_demolition_charges', 0))
    melee = bool(settings.get('shop_melee_fighters', 0))
    one_health = bool(settings.get('shop_one_shot_one_kill', 0))
    if not any((demolition, melee, one_health)):
        return {'technos': 0, 'weapons': 0}

    map_sections = all_section_value_maps(source_lines)
    touched_technos = set()
    touched_weapons = set()
    mobile_ids = {
        type_id
        for list_name in _MOBILE_TYPE_LISTS
        for type_id in _registered_ids(
            installed_sections, map_sections, rule_sections, list_name
        )
    }
    techno_ids = {
        type_id
        for list_name in _TECHNO_TYPE_LISTS
        for type_id in _registered_ids(
            installed_sections, map_sections, rule_sections, list_name
        )
    }

    if demolition:
        for type_id in mobile_ids:
            rule_sections.setdefault(type_id, {})['Explodes'] = 'yes'
            touched_technos.add(type_id)
    if one_health:
        for type_id in techno_ids:
            rule_sections.setdefault(type_id, {})['Strength'] = '1'
            touched_technos.add(type_id)

    if melee:
        weapon_users = set(mobile_ids)
        for building_id in _registered_ids(
            installed_sections, map_sections, rule_sections, 'BuildingTypes'
        ):
            values = _effective_values(
                building_id, installed_sections, map_sections, rule_sections
            )
            defense_key = _key(values, 'IsBaseDefense')
            if str(values.get(defense_key, '')).casefold() in {
                'yes', 'true', '1',
            }:
                weapon_users.add(building_id)
        for type_id in weapon_users:
            values = _effective_values(
                type_id, installed_sections, map_sections, rule_sections
            )
            for key, value in values.items():
                lowered = str(key).casefold()
                if (
                    lowered not in _WEAPON_REFERENCE_FIELDS
                    and not lowered.startswith('weapon')
                    and not lowered.startswith('eliteweapon')
                ):
                    continue
                weapon_id = str(value).strip()
                if (
                    not weapon_id
                    or _key(_effective_values(
                        weapon_id,
                        installed_sections,
                        map_sections,
                        rule_sections,
                    ), 'Damage') is None
                ):
                    continue
                weapon_values = rule_sections.setdefault(weapon_id, {})
                weapon_values['Range'] = '2.35'
                weapon_values['MinimumRange'] = '0'
                touched_weapons.add(weapon_id)

    return {
        'technos': len(touched_technos),
        'weapons': len(touched_weapons),
    }
