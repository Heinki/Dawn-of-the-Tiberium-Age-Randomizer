"""Versioned Conquest economy and faction-native battle grants."""

from collections import Counter

FACTIONS = ('GDI', 'Nod', 'Allies', 'Soviet')
DIFFICULTIES = {'Easy': 2, 'Normal': 1, 'Hard': 0, 'Brutal': 4,
                'Extreme': 5, 'Ultimate': 6, 'Impossible': 6}
SIZES = {'Short — 9 territories': 9, 'Standard — 25 territories': 25,
         'Long — 64 territories': 64, 'Epic — 100 territories': 100}
STATS = {'health': 'Health', 'armor': 'Armor', 'speed': 'Movement speed',
         'reload': 'Attack speed', 'damage': 'Damage'}
MAX_STRENGTH = 40
RECRUIT_COST = 100
RESEARCH_COST = 400
SUPPLY_COST = 150
REPAIR_KIT_COST = 350
MAX_REPAIR_KITS = 3
BATTLE_CREDITS_PER_RANK = 2500
RULES_VERSION = 1
HQ_INFANTRY = 8
HQ_DEFENSES = 2

# Grants use native faction identities, including the Soviet infantry voice.
ROSTERS = {
    'GDI': ('E1', 'JEEP', 'MTNK', 'NUKE', 'PYLE', 'TDPROC', 'TDHARV', 'TWR'),
    'Nod': ('E1N', 'BGGY', 'LTNK', 'NUKE', 'HAND', 'TDPROC', 'TDHARV', 'GUN'),
    'Allies': ('E1A', 'RANG', '2TNK', 'RAPOWR', 'RATENT', 'RAPROC', 'RAHARV', 'RAPBOX'),
    'Soviet': ('E1S', 'SHILKA', '3TNK', 'RAPOWR', 'RABARR', 'RAPROC', 'RAHARV', 'RAFTUR'),
}
FACTORIES = {'GDI': 'WEAP', 'Nod': 'AFLD', 'Allies': 'AWEAP', 'Soviet': 'SWEAP'}
HELIPADS = {'GDI': 'GHPAD', 'Nod': 'NHPAD', 'Allies': 'AHPAD', 'Soviet': 'SHPAD'}


def _perk(name, cost, maximum, power, description, *, local=False):
    return dict(name=name, cost=cost, maximum=maximum, power=power,
                description=description, local=local)


PERKS = {
    'allies': _perk('Coalition allies', 1500, 3, 0,
        'Add 1 AI teammate per rank, up to 3. Each deployed ally has its own base, 10,000 battle credits and strength 8, sharing your faction upgrades and starting perks. Spare map starts limit deployment; unused allies stay in reserve and add no autobattle power. Available to both campaign factions.'),
    'infantry': _perk('Infantry escort', 500, 3, 3,
        'Start every battle with 3 extra faction rifle infantry per rank. +3 army power per rank.'),
    'vehicles': _perk('Armored escort', 750, 3, 5,
        'Start every battle with 1 extra faction tank per rank. +5 army power per rank.'),
    'veterans': _perk('Veteran starting army', 700, 1, 0,
        'Your starting combat troops and purchased escorts begin at Veteran rank. +15% mobile army power.'),
    'power': _perk('Field power plant', 500, 1, 1,
        'Start every battle with a faction power plant. +1 army power.'),
    'barracks': _perk('Forward Barracks', 500, 1, 2,
        'Start every battle with a faction barracks. Required power is included. +2 army power.'),
    'refinery': _perk('Field refinery', 800, 1, 4,
        'Start every battle with a faction refinery and exactly one harvester. Required power is included. +4 army power.'),
    'garrison': _perk('Territory garrison', 450, 3, 4,
        'Place 1 faction defense per rank when this territory is attacked. Power is included. Local; passes to its captor. +4 defense power per rank.', local=True),
    'node_power': _perk('Node power plant', 300, 2, 1,
        'Add 1 faction power plant per rank beyond the power required for other starting buildings when defending this node. Local; stays after capture. +1 defense power per rank.', local=True),
    'node_barracks': _perk('Node barracks', 500, 1, 2,
        'Start defenses of this node with a faction barracks and required power. Stacks with Forward Barracks. Local; stays after capture. +2 defense power.', local=True),
    'node_refinery': _perk('Node refinery', 800, 1, 4,
        'Start defenses of this node with a faction refinery, one harvester and required power. Stacks with field refineries. Local; stays after capture. +4 defense power.', local=True),
    'node_factory': _perk('Node vehicle factory', 1000, 1, 5,
        'Start defenses of this node with a faction vehicle factory and required power. Local; stays after capture. +5 defense power.', local=True),
    'production': _perk('Production logistics', 600, 3, 2,
        'Reduce unit and building production time by 10% per rank, up to 30%. +2 army power per rank.'),
    'discount': _perk('Efficient procurement', 600, 3, 2,
        'Reduce unit and building costs by 10% per rank, up to 30%. +2 army power per rank.'),
    'recruitment': _perk('Recruitment training', 500, 3, 0,
        'Add 1 extra strength per recruitment per rank. Recruitment still consumes the army action.'),
    'income': _perk('War treasury', 500, 3, 0,
        'Earn 25 extra campaign credits each turn per rank. Campaign credits are separate from battle credits.'),
    'battle_treasury': _perk('Battle Treasury', 750, 3, 3,
        'Start each battle with 2,500 extra battle credits per rank, up to 7,500. Personal armies and sponsored AI allies receive the bonus. +3 army power per rank.'),
    'extended_arsenal': _perk('Extended Arsenal', 900, 2, 3,
        'Add 1 cell of range per rank to eligible combat weapons, up to 2 cells. Applies to starting and produced combat units and defenses. Utility and suicide weapons are excluded. +3 army power per rank.'),
    'civil_engineers': _perk('Civil Engineers', 600, 3, 0,
        'Reduce all local node-upgrade prices by 10% per rank, up to 30%. Discounts apply to future purchases on your owned nodes.'),
    'rapid_rearm': _perk('Rapid Rearm', 600, 3, 2,
        'Reduce docked aircraft ammunition reload time by 15% per rank, up to 45%. Applies to eligible starting and produced aircraft. Does not change weapon fire rate or ground-unit ammunition. +2 army power per rank.'),
    'hardened_infrastructure': _perk('Hardened Infrastructure', 700, 3, 2,
        'Add 15% maximum health per rank, up to 45%, to construction yards, production buildings, refineries, power plants and silos. Includes starting buildings and future construction. Uses the same eligibility as Fortress Fortified Infrastructure. +2 army power per rank.'),
    'hazard_training': _perk('Hazard Training', 400, 1, 0,
        'Your starting and produced infantry gain native Tiberium protection. Ordinary combat damage remains unchanged. Sponsored AI allies share this training.'),
    'elite_deployment': _perk('Elite Deployment', 1600, 1, 0,
        'Starting combat troops and escorts arrive at Elite rank. Harvesters remain unpromoted. Replaces the Veteran starting-rank bonus with +30% mobile army power; the two rank bonuses do not stack.'),
    'factory': _perk('Forward Factory', 1000, 1, 5,
        'Start every battle with a faction vehicle factory and required power. Stacks with a local node factory when defending. +5 army power.'),
    'helipad': _perk('Forward Helipad', 800, 1, 3,
        'Start every battle with a faction helipad and required power. Aircraft can dock and rearm there according to their native docking rules. +3 army power.'),
}
LOCAL_PERKS = tuple(key for key, perk in PERKS.items() if perk['local'])


def starting_force(country, strength, perks, *, headquarters=False):
    """The same frozen strength/perks feed battle grants and combat ratings."""
    infantry, scout, tank, power, barracks, refinery, collector, defense = ROSTERS[country]
    scouts = strength // 5
    units = Counter({infantry: strength - scouts * 3, scout: scouts})
    units[infantry] += 3 * perks.get('infantry', 0)
    units[tank] += perks.get('vehicles', 0)
    refineries = perks.get('refinery', 0) + perks.get('node_refinery', 0)
    structures = Counter({power: perks.get('power', 0) + perks.get('node_power', 0),
                          barracks: perks.get('barracks', 0) + perks.get('node_barracks', 0),
                          refinery: refineries, defense: perks.get('garrison', 0),
                          FACTORIES[country]: perks.get('factory', 0) + perks.get('node_factory', 0),
                          HELIPADS[country]: perks.get('helipad', 0)})
    if headquarters:
        units[infantry] += HQ_INFANTRY
        structures[defense] += HQ_DEFENSES
    if refineries:
        units[collector] += refineries
    return {'units': dict(+units), 'structures': dict(+structures),
            'veterancy': deployment_rank(perks), 'collector': collector,
            'power_type': power}


def deployment_rank(perks):
    return 2 if perks.get('elite_deployment') else perks.get('veterans', 0)


def combat_power(strength, stats, perks, *, headquarters=False, field_repairs=False):
    mobile = strength + 3 * perks.get('infantry', 0) + 5 * perks.get('vehicles', 0)
    if headquarters:
        mobile += HQ_INFANTRY
    value = mobile * (1 + .15 * deployment_rank(perks))
    value += sum(p['power'] * perks.get(key, 0) for key, p in PERKS.items()
                 if key not in ('infantry', 'vehicles'))
    if headquarters:
        value += HQ_DEFENSES * PERKS['garrison']['power']
    for stat in STATS:
        value *= (1 + stats.get(stat, 0) / 100) ** (.25 if stat == 'speed' else .5)
    if field_repairs:
        value *= 1.1
    return max(1, round(value, 3))
