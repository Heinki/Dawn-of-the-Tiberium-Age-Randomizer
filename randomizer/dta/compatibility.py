"""Map-local compatibility between native types and reward clones."""

from randomizer.dta.rules import comma_items, effective_section


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
    """Bridge enabled one-shot build events to production/deployment clones.

    Build events use heap indexes, not the arbitrary BuildingTypes INI keys.
    A companion runs the authored actions when the clone is built. Either
    path destroys the other trigger, so tutorial instructions run only once.
    """
    buildings = list(dict.fromkeys([
        *installed.get('BuildingTypes', {}).values(),
        *authored.get('BuildingTypes', {}).values(),
        *generated.get('BuildingTypes', {}).values(),
    ]))
    clones = {}
    for item in report['applied']:
        if item.get('category') in {'buildings', 'defenses'}:
            clones[item['unit']] = item['output_type']
        linked = item.get('linked_deploy_route')
        if linked and linked['output_type'] in buildings:
            clones[linked['source_type']] = linked['output_type']
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
            len(fields) != 4 or fields[:2] != ['1', '19']
            or len(trigger) != 8 or trigger[3] != '0'
            or trigger[0] != report['player_house']
        ):
            continue
        tags = [comma_items(value) for value in authored.get('Tags', {}).values()]
        if not any(len(tag) == 3 and tag[0] == '0' and tag[2] == trigger_id for tag in tags):
            continue
        try:
            native = buildings[int(fields[3])]
        except (ValueError, IndexError):
            continue
        output = clones.get(native)
        if not output or output == native:
            continue
        actions = list(comma_items(authored.get('Actions', {}).get(trigger_id)))
        if not actions or len(actions) != 1 + 8 * int(actions[0]):
            continue
        companion, tag_id = unique('DTABE'), unique('DTABT')
        fields[3] = str(buildings.index(output))
        trigger[2] += ' (player clone)'
        rules.setdefault('Events', {})[companion] = ','.join(fields)
        rules.setdefault('Triggers', {})[companion] = ','.join(trigger)
        rules.setdefault('Tags', {})[tag_id] = f'0,{trigger[2]},{companion}'
        for key, other in ((trigger_id, companion), (companion, trigger_id)):
            rules.setdefault('Actions', {})[key] = ','.join([
                str(int(actions[0]) + 1), *actions[1:],
                '12', '2', other, '0', '0', '0', '0', 'A',
            ])
    return rules
