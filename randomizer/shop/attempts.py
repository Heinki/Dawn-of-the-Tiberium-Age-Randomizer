"""Detect authored Shop defeats without treating missing victory as a loss."""

from randomizer.maps.hooks import append_hook_team, insert_actions_before_codes
from randomizer.maps.ini import parse_action_groups, section_value_map_preserve


def inject_defeat_markers(lines, mission_code):
    """Mark only loss actions targeting the authoritative player country.

    CountryType/HouseType action indices use the installed engine registry,
    not the map's active country ordering. Unknown targets remain retryable.
    """
    from randomizer.dta.rules import installed_effective_sections
    registry = dict(installed_effective_sections().get('Houses', {}))
    registry.update(section_value_map_preserve(lines, 'Houses'))
    basic = section_value_map_preserve(lines, 'Basic')
    player = next((str(value) for key, value in basic.items()
                   if key.casefold() == 'player'), '')
    player_values = section_value_map_preserve(lines, player)
    country = next((str(value) for key, value in player_values.items()
                    if key.casefold() == 'country'), player.removesuffix(' House'))
    if not country:
        return {}
    registry = {str(key).strip(): str(value).casefold() for key, value in registry.items()}
    actions = section_value_map_preserve(lines, 'Actions')
    targets = []
    for action_id, value in actions.items():
        count, groups = parse_action_groups(value)
        if count != len(groups):
            continue
        if any(len(group) >= 3 and (
                group[0] == '2' and registry.get(group[2].strip()) == country.casefold()
        ) for group in groups):
            targets.append(action_id)
    markers = {}
    existing = {line.strip()[1:-1].casefold() for line in lines
                if line.strip().startswith('[') and line.strip().endswith(']')}
    for section in ('TeamTypes', 'TaskForces', 'ScriptTypes'):
        existing.update(str(value).casefold()
                        for value in section_value_map_preserve(lines, section).values())
    for index, action_id in enumerate(targets, start=1):
        suffix = index
        while any(f'SHOPLOSS{kind}{suffix:03d}'.casefold() in existing for kind in 'TFS'):
            suffix += 1
        team, taskforce, script = (f'SHOPLOSS{kind}{suffix:03d}' for kind in 'TFS')
        marker = f'SHOP_{mission_code}_DEFEAT_{index:03d}'
        action = ['4', '1', team, '0', '0', '0', '0', 'A']
        if not insert_actions_before_codes(lines, action_id, [action], before_codes=('2',)):
            continue  # Never damage an authored action to force detection.
        append_hook_team(lines, team, taskforce, script, marker, country)
        existing.update(value.casefold() for value in (team, taskforce, script))
        markers[marker] = 'defeat'
    return markers
