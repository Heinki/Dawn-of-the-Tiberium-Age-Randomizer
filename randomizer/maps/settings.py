"""Launch-time map appearance settings."""

import hashlib

from randomizer.core.collections import unique_in_order
from randomizer.maps.houses import (
    map_house_records,
    player_controlled_houses,
    player_house_from_map,
)


def mission_house_color_rules(
    lines,
    player_color='Default',
    rainbowizer=False,
    rainbow_colors=(),
    random_key='',
):
    """Return deterministic per-House color overrides for one launch."""
    records = map_house_records(lines)
    player_houses = set(player_controlled_houses(lines, records=records))
    if not player_houses:
        player_house = player_house_from_map(lines, records=records)
        if player_house:
            player_houses.add(player_house)

    rules = {}
    selected_color = str(player_color or '').strip()
    if selected_color and selected_color.lower() != 'default':
        for house in player_houses:
            rules[house] = {'Color': selected_color}

    if not rainbowizer:
        return rules

    colors = unique_in_order(
        str(color or '').strip()
        for color in rainbow_colors
        if str(color or '').strip()
        and str(color).strip().lower() != selected_color.lower()
    )
    if not colors:
        return rules

    def is_neutral_house(name, record):
        side = str(record.get('side') or '').strip().lower()
        identities = {
            str(name or '').removesuffix(' House').strip().lower(),
            str(record.get('country') or '').strip().lower(),
            str(record.get('parent_country') or '').strip().lower(),
        }
        return (
            side in {'civilian', 'mutant'}
            or bool(identities.intersection({'neutral', 'special', 'civilian'}))
        )

    ai_houses = [
        name
        for name, record in records.items()
        if name not in player_houses and not is_neutral_house(name, record)
    ]
    key = str(random_key or '')
    ai_houses.sort(
        key=lambda name: hashlib.sha256(
            f'{key}|house|{name.lower()}'.encode('utf-8')
        ).digest()
    )
    colors.sort(
        key=lambda color: hashlib.sha256(
            f'{key}|color|{color.lower()}'.encode('utf-8')
        ).digest()
    )
    for index, house in enumerate(ai_houses):
        rules[house] = {'Color': colors[index % len(colors)]}
    return rules
