"""Vinifera multiplayer configuration; never use YR-specific spawn fields."""

import hashlib
import ipaddress
import re

from .feature import player_count, require_enabled


ALLY_KEYS = ('One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight')


def spawn_data(mission, players, local_slot, game_id, map_data, settings, game_speed):
    require_enabled()
    count = player_count(len(players))
    if count != mission['coop_player_count'] or not 0 <= local_slot < count:
        raise ValueError('Co-op roster does not match the authored player count.')
    if not 1 <= int(game_id) <= 2**31 - 1:
        raise ValueError('Invalid cooperative game ID.')
    names = set()
    for player in players:
        name = player['name']
        if not name.strip() or not re.fullmatch(r'[A-Za-z0-9 _-]{1,15}', name) or name.casefold() in names:
            raise ValueError('Co-op players need distinct ASCII names of 1–15 characters.')
        names.add(name.casefold())
        ipaddress.IPv4Address(player['ip'])
        if not 1 <= int(player['port']) <= 65535:
            raise ValueError('Invalid cooperative UDP port.')
    local = players[local_slot]
    section_settings = dict(settings)
    section_settings.update({
        'Scenario': 'spawnmap.ini', 'Name': local['name'],
        'Host': 'Yes' if local_slot == 0 else 'No', 'IsSinglePlayer': 'No',
        'PlayerCount': str(count), 'GameID': str(game_id), 'Seed': str(game_id),
        'Side': str(mission['coop_side']), 'Color': str(mission['coop_colors'][local_slot]),
        'Port': str(local['port']), 'MapHash': hashlib.sha1(map_data).hexdigest(),
        'UIMapName': mission['title'], 'GameSpeed': str(game_speed),
        'AIPlayers': str(len(mission['coop_allies']) + len(mission['coop_enemies'])),
    })
    sections = {'Settings': section_settings, 'SpawnLocations': {}}
    for other_index, slot in enumerate((slot for slot in range(count) if slot != local_slot), 1):
        peer = players[slot]
        sections[f'Other{other_index}'] = {
            'Name': peer['name'], 'Side': str(mission['coop_side']),
            'Color': str(mission['coop_colors'][slot]), 'Ip': peer['ip'], 'Port': str(peer['port']),
        }
    for slot in range(count):
        sections['SpawnLocations'][f'Multi{slot + 1}'] = str(slot)
    allies = mission['coop_allies']
    enemies = mission['coop_enemies']
    for slot, (side, color, position) in enumerate([*allies, *enemies], count):
        multi = f'Multi{slot + 1}'
        sections.setdefault('HouseCountries', {})[multi] = str(side)
        sections.setdefault('HouseColors', {})[multi] = str(color)
        sections.setdefault('HouseHandicaps', {})[multi] = settings['AIDifficulty']
        sections['SpawnLocations'][multi] = str(position)
    groups = (range(count + len(allies)), range(count + len(allies), count + len(allies) + len(enemies)))
    for group in groups:
        for slot in group:
            sections[f'Multi{slot + 1}_Alliances'] = {
                f'HouseAlly{ALLY_KEYS[index]}': str(peer)
                for index, peer in enumerate(peer for peer in group if peer != slot)
            }
    return ('\r\n'.join(line for section, values in sections.items()
                          for line in [f'[{section}]', *(f'{key}={value}' for key, value in values.items()), '']) + '\r\n').encode('cp1252')
