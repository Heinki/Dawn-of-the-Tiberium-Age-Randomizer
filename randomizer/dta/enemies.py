"""Conservative DTA enemy-only country bonuses."""

from collections import Counter

from randomizer.dta.maps import mission_source_path
from randomizer.dta.rules import comma_items, ini_sections
from randomizer.rewards.enemy_scaling import enemy_effect_values


FAMILY_BY_ACTS_LIKE = {0: 'GDI', 1: 'Nod', 2: 'Allies', 3: 'Soviet'}


def _integer(value, default=-1):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def enemy_buff_rules(mission, rewards):
    """Apply bonuses only where no player/allied house uses that family."""
    sections = ini_sections(mission_source_path(mission.get('scenario')))
    houses = {
        str(value).strip()
        for value in sections.get('Houses', {}).values()
        if str(value).strip()
    }
    player = str(sections.get('Basic', {}).get('Player') or '').strip()
    players = {
        name for name in houses
        if sections.get(name, {}).get('PlayerControl', '').casefold()
        in {'yes', 'true', '1'}
    }
    if player:
        players.add(player)

    friendly = set(players)
    for name in tuple(players):
        friendly.update(
            ally for ally in comma_items(sections.get(name, {}).get('Allies'))
            if ally in houses
        )
    for name in houses:
        allies = set(comma_items(sections.get(name, {}).get('Allies')))
        if allies.intersection(players):
            friendly.add(name)

    active = set(players)
    for list_name in ('Infantry', 'Units', 'Aircraft', 'Structures'):
        for value in sections.get(list_name, {}).values():
            fields = comma_items(value)
            if fields and fields[0] in houses:
                active.add(fields[0])
    for name in houses:
        values = sections.get(name, {})
        if _integer(values.get('NodeCount'), 0) > 0 or _integer(values.get('IQ'), 0) > 0:
            active.add(name)
    for values in sections.values():
        team_house = str(values.get('House') or '').strip()
        if team_house in houses:
            active.add(team_house)

    family = {
        name: FAMILY_BY_ACTS_LIKE.get(
            _integer(sections.get(name, {}).get('ActsLike'))
        )
        for name in houses
    }
    friendly_families = {family[name] for name in friendly if family.get(name)}
    hostile_houses = {
        name for name in active
        if name not in friendly
        and name.casefold() not in {'neutral', 'special'}
    }
    hostile_families = {
        family[name] for name in hostile_houses
        if family.get(name) and family[name] not in friendly_families
    }

    counts = Counter(
        str(reward.get('enemy_effect_id') or '')
        for reward in rewards or ()
        if reward.get('enemy_reward')
    )
    rules = {}
    applied = []
    for reward in rewards or ():
        effect_id = str(reward.get('enemy_effect_id') or '')
        if not reward.get('enemy_reward') or effect_id in {item['effect_id'] for item in applied}:
            continue
        count = min(counts[effect_id], int(reward.get('enemy_maximum', 5)))
        if count <= 0:
            continue
        effect = reward.get('enemy_effect')
        field = 'Armor' if effect == 'armor' else 'BuildTime' if effect == 'production' else ''
        if not field:
            continue
        value = enemy_effect_values(reward, count)['final_engine_value']
        serialized = f'{value:.3f}'.rstrip('0').rstrip('.')
        for target_family in hostile_families:
            rules.setdefault(target_family, {})[field] = serialized
        applied.append({
            'effect_id': effect_id,
            'stacks': count,
            'families': sorted(hostile_families),
            'field': field,
            'value': serialized,
        })
    return rules, {
        'player_houses': sorted(players),
        'friendly_families': sorted(friendly_families),
        'hostile_houses': sorted(hostile_houses),
        'hostile_families': sorted(hostile_families),
        'applied': applied,
    }
