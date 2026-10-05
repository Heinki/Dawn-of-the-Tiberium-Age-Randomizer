"""Map-local compatibility between native types and reward clones."""

from randomizer.dta.rules import comma_items, effective_section


# DTA 16.2 registers three engine building types after Rules.ini's list.
# Its debug log reports 501 types for the 498 entries in [BuildingTypes].
_IMPLICIT_ENGINE_BUILDING_TYPES = 3


def docking_rules(combined, generated, report):
    """Share docking types; the engine still enforces building ownership.

    This permits captured foreign/AI facilities, not hostile-owned docking.
    Native scripted aircraft and harvesters need the same lists as clones.
    """
    sections = {name: dict(values) for name, values in combined.items()}
    for name, values in generated.items():
        sections.setdefault(name, {}).update(values)
    buildings = list(dict.fromkeys(sections.get('BuildingTypes', {}).values()))
    pads, refineries = [], []
    for building in buildings:
        values = effective_section(sections, building)
        if (
            values.get('UnitReload', '').lower() in {'yes', 'true', '1'}
            and (
                values.get('Helipad', '').lower() in {'yes', 'true', '1'}
                or values.get('Factory', '').lower() == 'aircrafttype'
            )
        ):
            pads.append(building)
        if values.get('Refinery', '').lower() in {'yes', 'true', '1'}:
            refineries.append(building)
    rules = {}
    source_by_output = {
        item['output_type']: item['unit'] for item in report['applied']
    }
    for list_name, destinations in (
        ('AircraftTypes', pads), ('VehicleTypes', refineries),
    ):
        for unit in dict.fromkeys(sections.get(list_name, {}).values()):
            values = effective_section(sections, unit)
            source = source_by_output.get(unit, unit)
            native_docks = comma_items(effective_section(combined, source).get('Dock'))
            if not native_docks:
                continue
            if list_name == 'VehicleTypes' and not any(
                dock in refineries for dock in native_docks
            ):
                continue
            rules[unit] = {'Dock': ','.join(dict.fromkeys([
                *native_docks, *destinations,
            ]))}
    return rules


def building_event_rules(installed, authored, generated, report):
    """Bridge one-shot building events to production/deployment clones.

    Built-by-player and building-exists events use heap indexes, not the
    arbitrary BuildingTypes INI keys. A companion runs the authored actions
    when the clone satisfies the event. Either path destroys the other
    trigger, so mission progression runs only once.
    """
    installed_buildings = list(dict.fromkeys(
        installed.get('BuildingTypes', {}).values()
    ))
    added_buildings = [
        building for building in dict.fromkeys([
            *authored.get('BuildingTypes', {}).values(),
            *generated.get('BuildingTypes', {}).values(),
        ])
        if building not in installed_buildings
    ]
    # Original trigger indices still point into Rules.ini's list. New map
    # types follow the engine's three implicit entries in the runtime heap.
    buildings = [
        *installed_buildings,
        *([None] * _IMPLICIT_ENGINE_BUILDING_TYPES),
        *added_buildings,
    ]
    # A helper can deploy a different clone than the human produces. Keep
    # every route under its actual scenario owner; a source-only mapping can
    # silently replace the scripted MCV's yard with another production clone.
    clones_by_house = {}

    def add_route(houses, source, output):
        if output not in buildings or output == source:
            return
        for house in houses:
            house = str(house or '').casefold()
            if not house:
                continue
            outputs = clones_by_house.setdefault(house, {}).setdefault(source, [])
            if output not in outputs:
                outputs.append(output)

    player_houses = (report.get('player_house'),)
    for item in report['applied']:
        if item.get('category') in {'buildings', 'defenses'}:
            add_route(player_houses, item['unit'], item['output_type'])
        linked = item.get('linked_deploy_route')
        if linked:
            add_route(player_houses, linked['source_type'], linked['output_type'])
        for route in item.get('allied_helper_routes', ()):
            houses = route.get('scenario_houses', ())
            if item.get('category') in {'buildings', 'defenses'}:
                add_route(houses, item['unit'], route['output_type'])
            linked = route.get('linked_deploy_route')
            if linked:
                add_route(houses, linked['source_type'], linked['output_type'])
    rules = {}
    occupied = set(authored) | set(generated)
    for values in authored.values():
        occupied.update(values)

    def unique(prefix):
        index = 1
        while f'{prefix}{index:04d}' in occupied:
            index += 1
        name = f'{prefix}{index:04d}'
        occupied.add(name)
        return name

    for trigger_id, event in authored.get('Events', {}).items():
        fields = list(comma_items(event))
        trigger = list(comma_items(authored.get('Triggers', {}).get(trigger_id)))
        if (
            len(fields) != 4
            or fields[0] != '1'
            or fields[1] not in {'19', '32'}
            or len(trigger) != 8 or trigger[3] != '0'
            or trigger[0].casefold() not in clones_by_house
        ):
            continue
        tags = [comma_items(value) for value in authored.get('Tags', {}).values()]
        if not any(len(tag) == 3 and tag[0] == '0' and tag[2] == trigger_id for tag in tags):
            continue
        try:
            native = buildings[int(fields[3])]
        except (ValueError, IndexError):
            continue
        outputs = clones_by_house[trigger[0].casefold()].get(native, ())
        if not outputs:
            continue
        actions = list(comma_items(authored.get('Actions', {}).get(trigger_id)))
        if not actions or len(actions) != 1 + 8 * int(actions[0]):
            continue
        companions = []
        for output in outputs:
            companion, tag_id = unique('DTABE'), unique('DTABT')
            companions.append(companion)
            clone_fields, clone_trigger = list(fields), list(trigger)
            clone_fields[3] = str(buildings.index(output))
            clone_trigger[2] += ' (player clone)'
            rules.setdefault('Events', {})[companion] = ','.join(clone_fields)
            rules.setdefault('Triggers', {})[companion] = ','.join(clone_trigger)
            rules.setdefault('Tags', {})[tag_id] = f'0,{clone_trigger[2]},{companion}'
        trigger_ids = [trigger_id, *companions]
        for key in trigger_ids:
            destroy_actions = [
                field
                for other in trigger_ids if other != key
                for field in ('12', '2', other, '0', '0', '0', '0', 'A')
            ]
            rules.setdefault('Actions', {})[key] = ','.join([
                str(int(actions[0]) + len(trigger_ids) - 1), *actions[1:],
                *destroy_actions,
            ])
    return rules
