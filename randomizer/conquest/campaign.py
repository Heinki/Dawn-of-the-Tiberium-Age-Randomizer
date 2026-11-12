"""Deterministic campaign transitions, independent of Tk and native game files."""

from copy import deepcopy
from collections import deque
import hashlib
import math
import random
import secrets
import uuid
from .teams import TEAM_VERSION, plan_participants, team_power
from .players import roster, human_ids, human, country, label, bonus_owners, validate_roster

from .catalogue import (FACTIONS, DIFFICULTIES, STATS, PERKS, MAX_STRENGTH,
                        RECRUIT_COST, RESEARCH_COST, SUPPLY_COST, RULES_VERSION,
                        REPAIR_KIT_COST, MAX_REPAIR_KITS, combat_power, starting_force)


def record(state, text, faction='player', node=None):
    state['history'].append(dict(id=state['next_event'], turn=state['turn'],
                                 faction=faction, node=node, text=text))
    state['next_event'] += 1


def random_number(state, maximum):
    value = state['random']
    value ^= (value << 13) & 0xffffffff
    value ^= value >> 17
    value ^= (value << 5) & 0xffffffff
    state['random'] = value & 0xffffffff
    return state['random'] % maximum


def _layout(count, seed):
    rng = random.Random(seed + ':routes')
    side = math.isqrt(count)
    points = []
    for y in range(side):
        for x in range(side):
            points.append((x * 140 + rng.uniform(-30, 30), y * 140 + rng.uniform(-30, 30)))
    edges, connected = [], {0}
    distance = lambda a, b: sum((points[a][i] - points[b][i]) ** 2 for i in (0, 1))
    nearest = {b: (distance(0, b), 0, b) for b in range(1, count)}
    while len(connected) < count:
        _, a, b = min(nearest.values())
        edges.append(sorted((a, b)))
        connected.add(b)
        del nearest[b]
        for target in nearest:
            nearest[target] = min(nearest[target], (distance(b, target), b, target))
    for a in range(count):
        nearby = sorted((b for b in range(count) if a != b), key=lambda b: (distance(a, b), b))[:3]
        for b in nearby:
            edge = sorted((a, b))
            if edge not in edges and rng.random() < .35:
                edges.append(edge)
    return points, edges


def new_campaign(settings, maps):
    settings = deepcopy(settings)
    if isinstance(settings.get('seed'), str):
        settings['seed'] = settings['seed'].strip() or secrets.token_hex(8)
    if (settings.get('size') not in (9, 25, 64, 100) or
        settings.get('player_country') not in FACTIONS or settings.get('ai_country') not in FACTIONS or
        settings.get('difficulty') not in DIFFICULTIES or settings.get('density') not in (0, 1, 2) or
        type(settings.get('credits')) is not int or not 100 <= settings['credits'] <= 10000 or
        not isinstance(settings.get('seed'), str) or not 1 <= len(settings['seed']) <= 80):
        raise ValueError('Choose valid Conquest settings.')
    players = settings.pop('coop_players', None)
    shared_nodes = settings.pop('shared_nodes', False)
    if players is not None:
        validate_roster(players)
        if type(shared_nodes) is not bool:
            raise ValueError('Choose whether to share territory bonuses.')
        settings['player_country'] = players[0]['country']
    countries = [p['country'] for p in players] if players else [settings['player_country']]
    pool = [deepcopy(m) for m in maps if len(m['starts']) >= (len(players) + 1 if players else 2) and
            all(c in m['countries'] for c in (*countries, settings['ai_country']))]
    if not pool:
        raise ValueError('No installed Conquest maps fit every human commander plus the enemy and support their factions.')
    pool.sort(key=lambda m: m['path'])
    seed = settings['seed']
    rng = random.Random(seed + ':territories')
    rng.shuffle(pool)
    points, edges = _layout(settings['size'], seed)
    state = dict(schema=1, rules_version=RULES_VERSION, game='dta', revision=0,
                 id=uuid.uuid4().hex, settings=settings, turn=1, phase='player', winner=None,
                 random=int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16) or 1,
                 nodes=[], edges=edges, armies=[], next_army=3, next_event=1,
                 history=[], pending=None, attempts=[], ai_purchase=False, ai_recruits=0)
    if players:
        state['coop'] = dict(version=1, players=deepcopy(players), shared_nodes=shared_nodes,
                             gifts={p['id']: 0 for p in players})
    for side in (*human_ids(state), 'ai'):
        state[side] = dict(credits=settings['credits'], research={k: 0 for k in STATS},
                           perks={}, supplies=0)
    rewards = [key for key, value in PERKS.items() if not value['local']]
    for i, (x, y) in enumerate(points):
        count = max(0, rng.randrange(3) + settings['density'] - 1)
        buffs = {k: rng.choice((5, 10)) for k in rng.sample(list(STATS), count)}
        state['nodes'].append(dict(id=i, x=x, y=y, owner='neutral',
            income=max(50, 250 - count * 60 + rng.randrange(5) * 25), buffs=buffs,
            perks={'garrison': 1} if rng.randrange(100) < 8 else {},
            reward=rng.choice(rewards) if rng.randrange(100) < 15 + settings['density'] * 10 else None,
            claimed=[], map=deepcopy(pool[i % len(pool)])))
    starts = [('player', 0), ('ai', settings['size'] - 1)]
    for player in human_ids(state)[1:]:
        occupied = [i for _, i in starts]
        index = max((i for i in range(settings['size']) if i not in occupied),
                    key=lambda i: min(sum((points[i][d] - points[j][d])**2 for d in (0, 1)) for j in occupied))
        starts.append((player, index))
    state['next_army'] = len(starts) + 1
    for army_id, (side, index) in enumerate(starts, 1):
        state['nodes'][index]['owner'] = side
        state['nodes'][index]['hq'] = side
        state['armies'].append(dict(id=army_id, faction=side, node=index, strength=8, acted=False))
        record(state, f'Campaign started with {settings["credits"]} credits and army strength 8.', side, index)
        _claim(state, state['nodes'][index])
    record(state, 'Your turn. Select an army, then a connected territory.')
    return state


def neighbors(state, node):
    return [b if a == node else a for a, b in state['edges'] if a == node or b == node]


def army_at(state, node):
    return next((a for a in state['armies'] if a['node'] == node), None)


def totals(state, faction):
    if faction == 'neutral':
        return {k: 0 for k in STATS}
    return {k: min(100, state[faction]['research'][k] * 10 +
            sum(n['buffs'].get(k, 0) for n in state['nodes'] if n['owner'] in bonus_owners(state, faction))) for k in STATS}


def income(state, faction):
    amount = sum(n['income'] for n in state['nodes'] if n['owner'] == faction and n.get('income_after', 0) <= state['turn'])
    amount += state[faction]['perks'].get('income', 0) * 25
    multiplier = {'Easy': .75, 'Normal': 1}.get(state['settings']['difficulty'], 1.25)
    return int(amount * (multiplier if faction == 'ai' else 1))


def _turn(state, faction):
    if state['phase'] != faction or state['pending'] or state['winner']:
        raise ValueError('This action requires your active campaign turn.')


def _node(state, index):
    if type(index) is not int or not 0 <= index < len(state['nodes']):
        raise ValueError('Select a valid campaign territory.')
    return state['nodes'][index]


def _spend(state, faction, amount):
    if state[faction]['credits'] < amount:
        raise ValueError('Not enough campaign credits.')
    state[faction]['credits'] -= amount


def recruit(state, node, faction='player'):
    _turn(state, faction)
    target = _node(state, node)
    if target['owner'] != faction:
        raise ValueError('Recruit on an owned territory.')
    army = army_at(state, node)
    if army and (army['acted'] or army['strength'] >= MAX_STRENGTH):
        raise ValueError('This army already acted or has maximum strength.')
    amount = min(5 + state[faction]['perks'].get('recruitment', 0),
                 MAX_STRENGTH - (army['strength'] if army else 0))
    _spend(state, faction, RECRUIT_COST)
    if army is None:
        army = dict(id=state['next_army'], faction=faction, node=node, strength=0, acted=False)
        state['next_army'] += 1
        state['armies'].append(army)
    army['strength'] += amount
    army['acted'] = True
    record(state, f'Recruited +{amount} strength for {RECRUIT_COST} credits. Army action spent.', faction, node)


def purchase(state, kind, key='', node=None, faction='player'):
    _turn(state, faction)
    wallet = state[faction]
    if kind == 'research':
        if key not in STATS or wallet['research'][key] >= 3:
            raise ValueError('This research is unavailable or already at maximum rank.')
        _spend(state, faction, RESEARCH_COST)
        wallet['research'][key] += 1
        record(state, f'{STATS[key]} research rank {wallet["research"][key]} purchased for {RESEARCH_COST}.', faction)
    elif kind == 'supply':
        if wallet['supplies'] >= 3:
            raise ValueError('Supply reserve is full.')
        _spend(state, faction, SUPPLY_COST)
        wallet['supplies'] += 1
        record(state, f'Bought a supply charge for {SUPPLY_COST} credits.', faction)
    elif kind == 'item' and key == 'field_repairs':
        if wallet.get('repair_kits', 0) >= MAX_REPAIR_KITS:
            raise ValueError('Field Repairs inventory is full.')
        _spend(state, faction, REPAIR_KIT_COST)
        wallet['repair_kits'] = wallet.get('repair_kits', 0) + 1
        record(state, f'Bought a Field Repairs kit for {REPAIR_KIT_COST} credits.', faction)
    elif kind == 'perk':
        perk = PERKS.get(key)
        if perk is None:
            raise ValueError('Unknown Conquest perk.')
        if key == 'veterans' and wallet['perks'].get('elite_deployment'):
            raise ValueError('Elite Deployment already grants a higher starting rank.')
        inventory = wallet['perks']
        if perk['local']:
            if node is None or _node(state, node)['owner'] != faction:
                raise ValueError('Select an owned territory for this local improvement.')
            inventory = state['nodes'][node]['perks']
        if inventory.get(key, 0) >= perk['maximum']:
            raise ValueError('This perk is already at maximum rank.')
        cost = purchase_cost(state, faction, key)
        _spend(state, faction, cost)
        inventory[key] = inventory.get(key, 0) + 1
        record(state, f'{perk["name"]} rank {inventory[key]} purchased for {cost}.',
               faction, node if perk['local'] else None)
    else:
        raise ValueError('Unknown purchase.')


def purchase_cost(state, faction, key):
    perk = PERKS[key]
    discount = 10 * state[faction]['perks'].get('civil_engineers', 0) if perk['local'] else 0
    return (perk['cost'] * (100 - discount) + 99) // 100


def use_item(state, key, faction='player'):
    _turn(state, faction)
    if key != 'field_repairs':
        raise ValueError('Unknown Conquest item.')
    wallet = state[faction]
    if not wallet.get('repairs_armed') and not wallet.get('repair_kits', 0):
        raise ValueError('Buy a Field Repairs kit first.')
    wallet['repairs_armed'] = not wallet.get('repairs_armed', False)
    record(state, 'Field Repairs armed for the next battle.' if wallet['repairs_armed'] else
           'Field Repairs disarmed. Kit retained.', faction)


def _claim(state, node):
    key, faction = node['reward'], node['owner']
    if not key or faction == 'neutral' or faction in node['claimed']:
        return
    node['claimed'].append(faction)
    inventory, perk = state[faction]['perks'], PERKS[key]
    if inventory.get(key, 0) < perk['maximum']:
        inventory[key] = inventory.get(key, 0) + 1
        record(state, f'Permanent capture reward: {perk["name"]}, rank {inventory[key]}.', faction, node['id'])


def _loadout(state, faction, strength, node, defending):
    stats = totals(state, faction)
    perks = deepcopy(state[faction]['perks']) if faction != 'neutral' else {}
    if defending:
        perks.update(node['perks'])
    if faction != 'neutral' and state[faction]['supplies']:
        state[faction]['supplies'] -= 1
        stats['damage'] += 20
        record(state, 'Supply committed: +20% damage for this battle.', faction, node['id'])
    native_country = country(state, faction)
    headquarters = bool(defending and node.get('hq') == faction)
    repairs = bool(faction != 'neutral' and state[faction].get('repairs_armed'))
    if repairs:
        state[faction]['repair_kits'] -= 1
        state[faction]['repairs_armed'] = False
        record(state, 'Field Repairs consumed: combat units heal up to 50% health this battle; +10% autobattle power.', faction, node['id'])
    result = dict(faction=faction, country=native_country, strength=strength, stats=stats, perks=perks,
                headquarters=headquarters,
                power=combat_power(strength, stats, perks, headquarters=headquarters, field_repairs=repairs),
                force=starting_force(native_country, strength, perks, headquarters=headquarters))
    if repairs:
        result['field_repairs'] = True
    return result


def move(state, source, target, faction='player'):
    _turn(state, faction)
    _node(state, source)
    _node(state, target)
    army = army_at(state, source)
    if not army or army['faction'] != faction or army['acted'] or target not in neighbors(state, source):
        raise ValueError('Select a ready army and an adjacent territory.')
    destination, defender = state['nodes'][target], army_at(state, target)
    if human(state, faction) and human(state, destination['owner']) and destination['owner'] != faction:
        raise ValueError('Teammate territory is allied. Ask its owner to give you an empty node before moving there.')
    if destination['owner'] == faction:
        if defender and defender['strength'] + army['strength'] > MAX_STRENGTH:
            raise ValueError(f'Merged armies cannot exceed {MAX_STRENGTH} strength.')
        army['acted'] = True
        if defender:
            defender['strength'] += army['strength']
            defender['acted'] = True
            state['armies'].remove(army)
        else:
            army['node'] = target
        record(state, 'Armies merged; both actions spent.' if defender else 'Army moved.', faction, target)
        return
    army['acted'] = True
    attack = _loadout(state, faction, army['strength'], destination, False)
    defense = _loadout(state, destination['owner'], defender['strength'] if defender else 2, destination, True)
    map_info = deepcopy(destination['map'])
    starts = map_info['starts']
    first = random_number(state, len(starts))
    others = [s for s in starts if s != starts[first]]
    positions = map_info.get('positions', {})
    if positions:
        center = positions[str(starts[first])]
        farthest = max(sum((positions[str(s)][i] - center[i]) ** 2 for i in (0, 1)) for s in others)
        others = [s for s in others if sum((positions[str(s)][i] - center[i]) ** 2 for i in (0, 1)) == farthest]
    state['pending'] = dict(id=uuid.uuid4().hex, army=army['id'], source=source, target=target,
        attacker=faction, attack=attack, defense=defense, map=map_info,
        seed=1 + random_number(state, 2**31 - 2),
        starts=[starts[first], others[random_number(state, len(others))]],
        difficulty=state['settings']['difficulty'], rules_version=RULES_VERSION,
        attempt=None)
    battle = state['pending']
    if state.get('coop') and (human(state, faction) or human(state, destination['owner'])):
        battle['human_team'] = 'attack' if human(state, faction) else 'defense'
        battle['decision_actor'] = faction if human(state, faction) else destination['owner']
        main = battle[battle['human_team']]
        battle['human_loadouts'] = []
        for player in roster(state):
            actor = player['id']
            strength = max((a['strength'] for a in state['armies'] if a['faction'] == actor), default=2)
            loadout = main if actor == main['faction'] else _loadout(state, actor, strength, destination, False)
            battle['human_loadouts'].append(dict(player=deepcopy(player), loadout=deepcopy(loadout)))
    battle['team_version'] = TEAM_VERSION
    battle['participants'] = plan_participants(battle)
    state['phase'] = 'battle'
    record(state, f'Attack committed: {team_power(battle, "attack"):g} attack / {team_power(battle, "defense"):g} defense; {len(battle["participants"])} combatants.', faction, target)


def player_chance(battle):
    attack, defense = team_power(battle, 'attack'), team_power(battle, 'defense')
    return (attack if battle.get('human_team', 'attack' if battle['attacker'] == 'player' else 'defense') == 'attack' else defense) / (attack + defense)


def resolve(state, battle_id, attacker_won, *, method):
    battle = state['pending']
    if not battle or battle['id'] != battle_id:
        return False
    army = next(a for a in state['armies'] if a['id'] == battle['army'])
    node = state['nodes'][battle['target']]
    defender = army_at(state, node['id'])
    winner = battle['attacker'] if attacker_won else node['owner']
    record(state, f'{method}: {label(state, winner)} won the battle.', winner, node['id'])
    if attacker_won:
        if defender:
            state['armies'].remove(defender)
        if node['owner'] != 'neutral':
            record(state, 'Territory lost; its income and local bonuses are no longer yours.', node['owner'], node['id'])
        node['owner'] = battle['attacker']
        army['node'] = node['id']
        army['strength'] = max(1, army['strength'] - max(1, round(team_power(battle, 'defense') / 3)))
        record(state, f'Territory captured. Surviving strategic strength: {army["strength"]}.', winner, node['id'])
        _claim(state, node)
    else:
        state['armies'].remove(army)
        if defender:
            defender['strength'] = max(1, defender['strength'] - max(1, round(team_power(battle, 'attack') / 3)))
        record(state, 'Attacking army destroyed.', battle['attacker'], node['id'])
    state['pending'] = None
    state['phase'] = battle['attacker']
    if not any(n['owner'] == 'ai' for n in state['nodes']):
        state['winner'] = 'player'
    elif not any(human(state, n['owner']) for n in state['nodes']):
        state['winner'] = 'ai'
    if state['winner']:
        state['phase'] = 'finished'
        record(state, 'Campaign victory. All opposing territories have fallen.', state['winner'])
    return True


def autobattle(state):
    battle = state['pending']
    if not battle or battle['attempt']:
        raise ValueError('No unresolved battle is available for autobattle.')
    chance = team_power(battle, 'attack') / (team_power(battle, 'attack') + team_power(battle, 'defense'))
    return resolve(state, battle['id'], random_number(state, 1_000_000) < round(chance * 1_000_000), method='Autobattle')


def _begin_turn(state, faction):
    state['phase'] = faction
    for army in state['armies']:
        if army['faction'] == faction:
            army['acted'] = False
    amount = income(state, faction)
    state[faction]['credits'] = min(100_000_000, state[faction]['credits'] + amount)
    record(state, f'Turn started: +{amount} campaign credits.', faction)


def end_turn(state, faction='player'):
    _turn(state, faction)
    if not human(state, faction):
        raise ValueError('Only a human player can end this turn.')
    record(state, f'{label(state, faction)} ended their turn.', faction)
    remaining = human_ids(state)[human_ids(state).index(faction) + 1:]
    for actor in remaining:
        if any(n['owner'] == actor for n in state['nodes']):
            _begin_turn(state, actor)
            return
    state['ai_purchase'], state['ai_recruits'] = False, 0
    _begin_turn(state, 'ai')


def _front_distance(state, start):
    queue, visited = deque([(start, 0)]), {start}
    while queue:
        node, distance = queue.popleft()
        if state['nodes'][node]['owner'] != 'ai':
            return distance
        for neighbor in neighbors(state, node):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, distance + 1))
    return len(state['nodes'])


def step_ai(state):
    if state['phase'] == 'battle':
        battle = state['pending']
        if battle['attacker'] == 'ai' and battle['defense']['faction'] == 'neutral':
            autobattle(state)
            return True
        return False
    if state['phase'] != 'ai':
        return False
    if not state['ai_purchase']:
        state['ai_purchase'] = True
        wallet = state['ai']
        options = [('perk', key, p['cost']) for key, p in PERKS.items()
                   if not p['local'] and wallet['perks'].get(key, 0) < p['maximum'] and
                   not (key == 'veterans' and wallet['perks'].get('elite_deployment'))]
        options += [('research', key, RESEARCH_COST) for key in STATS if wallet['research'][key] < 3]
        if wallet['supplies'] < 3:
            options.append(('supply', '', SUPPLY_COST))
        options = [o for o in options if wallet['credits'] >= o[2] + 200]
        if options:
            kind, key, _ = options[random_number(state, len(options))]
            purchase(state, kind, key, faction='ai')
            return True
    army = next((a for a in state['armies'] if a['faction'] == 'ai' and not a['acted']), None)
    if army:
        def priority(index):
            node, other = state['nodes'][index], army_at(state, index)
            if node['owner'] == 'ai':
                return (1, _front_distance(state, index), index)
            strength = other['strength'] if other else 2
            return (0, strength - node['income'] / 100, index)
        choices = sorted(neighbors(state, army['node']), key=priority)
        choices = [n for n in choices if state['nodes'][n]['owner'] != 'ai' or
                   not army_at(state, n) or army_at(state, n)['strength'] + army['strength'] <= MAX_STRENGTH]
        if choices:
            move(state, army['node'], choices[0], 'ai')
        else:
            army['acted'] = True
        return True
    if state['ai_recruits'] < min(3, 1 + state['turn'] // 5) and state['ai']['credits'] >= RECRUIT_COST:
        locations = [n['id'] for n in state['nodes'] if n['owner'] == 'ai' and not army_at(state, n['id'])]
        if locations:
            location = min(locations, key=lambda n: (_front_distance(state, n), n))
            recruit(state, location, 'ai')
            state['ai_recruits'] += 1
            return True
    record(state, 'Turn ended.', 'ai')
    state['turn'] += 1
    first = next((actor for actor in human_ids(state) if any(n['owner'] == actor for n in state['nodes'])), 'player')
    _begin_turn(state, first)
    return True
