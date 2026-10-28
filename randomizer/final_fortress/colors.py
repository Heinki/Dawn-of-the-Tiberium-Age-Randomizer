"""Apply a visual color choice without changing player, faction or team slots."""


def score_scheme(plan, actor):
    """Resolve DTA's native score scheme after the spawn color swap."""
    selected = plan.get('player_color', 0)
    color = actor['color']
    if not selected or color not in (0, selected):
        return actor['scheme']
    color = selected if color == 0 else 0
    # The first eight multiplayer color IDs use DTA's classic scheme mapping.
    # Additional choices in Resources/GameOptions.ini are direct scheme IDs.
    classic = (3, 21, 47, 73, 27, 55, 39, 33)
    return classic[color] if color < len(classic) else color


def remap_colors(sections, plan):
    selected = plan.get('player_color', 0)
    if selected == 0:
        return
    for section, values in sections.items():
        keys = tuple(values) if section == 'HouseColors' else ('Color',)
        for key in keys:
            if key not in values:
                continue
            color = int(values[key])
            if color in (0, selected):
                values[key] = str(selected if color == 0 else 0)

    players = plan.get('coop_players', [])
    if players:
        colors = {row['Name']: int(row['Color']) for name, row in sections.items()
                  if name == 'Settings' or name.startswith('Other')}
        waypoints = [plan['map']['player_waypoint'], *plan.get('allied_waypoints', [])]
        order = sorted(range(len(players)), key=lambda slot: colors[players[slot]])
        for house, slot in enumerate(order, 1):
            sections['SpawnLocations'][f'Multi{house}'] = str(waypoints[slot])
