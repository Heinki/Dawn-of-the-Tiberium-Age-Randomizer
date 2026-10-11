"""Launch-time map appearance settings."""

import hashlib

from randomizer.core.collections import unique_in_order
from randomizer.dta.rules import installed_effective_sections
from randomizer.maps.ini import all_section_value_maps
from randomizer.maps.houses import (
    map_house_records,
    player_controlled_houses,
    player_house_from_map,
)


def _color_hsv(value):
    """Read DTA's 0–255 HSV color scheme, ignoring INI comments."""
    try:
        components = tuple(
            int(component.strip())
            for component in str(value).split(';', 1)[0].split(',')
        )
    except ValueError:
        return None
    if len(components) != 3 or any(not 0 <= value <= 255 for value in components):
        return None
    return components


def _similar_house_colors(first, second, definitions):
    """Keep nearby hue shades and similar grays away from human players."""
    if first == second:
        return True
    first_hsv = definitions.get(first)
    second_hsv = definitions.get(second)
    if first_hsv is None or second_hsv is None:
        return False
    first_hue, first_saturation, first_value = first_hsv
    second_hue, second_saturation, second_value = second_hsv
    if first_saturation < 48 or second_saturation < 48:
        return (
            first_saturation < 48 and second_saturation < 48
            and abs(first_value - second_value) <= 64
        )
    hue_distance = abs(first_hue - second_hue)
    # Hue wraps at 256. Different brightness/saturation variants still share
    # a team color; exclude hues within roughly 34 degrees of the player.
    return min(hue_distance, 256 - hue_distance) <= 24


def mission_house_color_rules(
    lines,
    player_color='Default',
    rainbowizer=False,
    rainbow_colors=(),
    random_key='',
    installed_sections=None,
):
    """Return deterministic per-House color overrides for one launch."""
    sections = all_section_value_maps(lines)
    records = map_house_records(lines, sections=sections)
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

    installed = (
        installed_effective_sections()
        if installed_sections is None
        else installed_sections
    )
    player_identities = {
        identity.lower()
        for house in player_houses
        for identity in (
            house, records.get(house, {}).get('country', ''),
            records.get(house, {}).get('parent_country', ''),
        )
    }
    installed_by_lower = {
        name.lower(): {key.lower(): value for key, value in values.items()}
        for name, values in installed.items()
        if name.lower() == 'colors'
        or name.lower() in player_identities
    }
    by_lower = {name.lower(): values for name, values in sections.items()}
    definitions = {
        name.lower(): _color_hsv(value)
        for name, value in {
            **installed_by_lower.get('colors', {}),
            **by_lower.get('colors', {}),
        }.items()
    }
    player_colors = set()
    if selected_color and selected_color.lower() != 'default':
        player_colors.add(selected_color.lower())
    else:
        for house in player_houses:
            record = records.get(house, {})
            for identity in (house, record.get('country'), record.get('parent_country')):
                identity = str(identity or '').lower()
                color = (
                    by_lower.get(identity, {}).get('color')
                    or installed_by_lower.get(identity, {}).get('color')
                )
                if color:
                    player_colors.add(str(color).split(';', 1)[0].strip().lower())
                    break

    colors = unique_in_order(
        str(color or '').strip()
        for color in rainbow_colors
        if str(color or '').strip()
        and not any(
            _similar_house_colors(str(color).strip().lower(), player, definitions)
            for player in player_colors
        )
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
