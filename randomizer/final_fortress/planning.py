"""Freeze target balance, factions, personal income and rewards before launch."""

from copy import deepcopy
import hashlib
import json
import random
from . import MODE_ID
from .catalogue import SIDE_COUNTRIES, validate_name
from .config import validate_config, validate_wave_multiplier, DIFFICULTY_IDS, integer, text
from .perks import resolve_effects
from .waves import build_wave_schedule
from .wave_priority import apply_priorities
from .pressure import size_composition

PLAN_VERSION = 1


def _starting_economy(effects, country):
    """Always supply one collector and only the power the actual grants need."""
    from math import ceil
    from randomizer.dta.rules import installed_effective_sections

    harvester = 'TDHARV' if country in ('GDI', 'Nod') else 'RAHARV'
    if not effects['starting_harvesters']:
        effects['starting_harvesters'] = [{'type': harvester, 'count': 1}]
    rules = installed_effective_sections()
    kinds = [*effects['starting_buildings'], *effects['defense_types']]
    demand = sum(max(0, -float(rules[k].get('Power', '0'))) for k in kinds)
    multiplier = 1 + effects['generator_power_percent'] / 100
    supply = sum(max(0, float(rules[k].get('Power', '0'))) * multiplier for k in kinds)
    missing = demand - supply
    effects['starting_power_buildings'] = []
    if missing > 0:
        # Friendly grant slots reserve the native small generator footprint.
        generator = 'NUKE' if country in ('GDI', 'Nod') else 'RAPOWR'
        effects['starting_power_buildings'] = [generator] * ceil(
            missing / (float(rules[generator]['Power']) * multiplier)
        )


def configuration_digest(config):
    return hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(',', ':')).encode()
    ).hexdigest()


def build_run_plan(
    config,
    *,
    difficulty,
    seed,
    player_country,
    selected_perks=(),
    wave_multiplier=1,
    plan_version=PLAN_VERSION,
    selected_challenges=(),
    challenge_stacks=None,
    perk_ranks=None,
    coop_players=(),
    fundraising_ranks=None,
):
    validate_config(config)
    validate_wave_multiplier(wave_multiplier)
    text(seed, 'Seed')
    if type(plan_version) is not int or plan_version != PLAN_VERSION:
        raise ValueError('Unsupported DTA Fortress plan version.')
    if difficulty not in DIFFICULTY_IDS or player_country not in SIDE_COUNTRIES:
        raise ValueError('Choose a DTA faction and difficulty.')
    if coop_players:
        if not isinstance(coop_players, (list, tuple)) or not 2 <= len(coop_players) <= 3:
            raise ValueError('Fortress supports two or three human players.')
        for name in coop_players:
            validate_name(name)
        if len({name.casefold() for name in coop_players}) != len(coop_players):
            raise ValueError('Every player needs a distinct name.')
    selected = sorted(selected_perks)
    catalogue = {p['id']: p for p in config['perks']}
    if len(set(selected)) != len(selected) or set(selected) - set(catalogue):
        raise ValueError('Invalid selected Fortress perks.')
    purchased = {key: (perk_ranks or {}).get(key, 1) for key in selected}
    effects = resolve_effects(
        config,
        selected,
        purchased,
        player_country,
        include_power=True,
        include_power_upgrades=True,
        include_arsenal=True,
        include_utilities=True,
        include_lab_support=True,
        include_lab_shield=True,
        include_lab_health=True,
        include_lab_veterancy=True,
        include_economy=True,
        include_generator_power=True,
        share_starting_power=True,
    )
    _starting_economy(effects, player_country)
    human_count = len(coop_players) or 1
    friend_count = human_count + min(effects['allied_helpers'], 3 - human_count)
    income = (
        [effects['fundraising_stacks']] * human_count
        if fundraising_ranks is None
        else list(fundraising_ranks)
    )
    if len(income) != human_count or any(type(v) is not int or not 0 <= v <= 4 for v in income):
        raise ValueError('Freeze one personal Fundraising rank per human.')
    if income[0] != effects['fundraising_stacks']:
        raise ValueError('Host Fundraising differs from enabled loadout.')
    enemies = random.Random(seed + ':dta:enemies').choices(SIDE_COUNTRIES, k=3)
    plan = {
        'game_id': 'dta',
        'mode_id': MODE_ID,
        'plan_version': plan_version,
        'config_digest': configuration_digest(config),
        'seed': seed,
        'difficulty': difficulty,
        'engine_difficulty': config['difficulties'][difficulty]['engine_difficulty'],
        'difficulty_profile': deepcopy(config['difficulties'][difficulty]),
        'player_country': player_country,
        'enemy_countries': enemies,
        'effects': effects,
        'selected_perks': selected,
        'perk_ranks': purchased,
        'wave_multiplier': wave_multiplier,
        'survival_seconds': config['settings']['survival_seconds'],
        'wave_interval_seconds': 300,
        'max_wave_units': config['settings']['max_wave_units'],
        'map': deepcopy(config['map']),
        'wave_pressure': deepcopy(config['wave_pressure']),
        'milestones': deepcopy(config['milestones']),
        'performance': deepcopy(config['performance']),
        'fundraising_ranks': income,
        'allied_countries': [player_country] * (friend_count - 1),
        'allied_waypoints': config['map']['allied_waypoints'][: friend_count - 1],
        'capabilities': deepcopy(config['capabilities']),
    }
    if coop_players:
        plan['coop_players'] = list(coop_players)
    plan['wave_schedule'] = build_wave_schedule(
        config,
        difficulty=difficulty,
        seed=seed,
        enemies=enemies,
        wave_multiplier=wave_multiplier,
        sized_waves=True,
    )
    from .waves import add_air_support

    add_air_support(plan, config)
    apply_priorities(plan, config['wave_priorities'])
    chosen = sorted(selected_challenges)
    challenges = {e['id']: e for e in config['challenges']}
    if len(set(chosen)) != len(chosen) or set(chosen) - set(challenges):
        raise ValueError('Unknown Fortress Challenge.')
    from .challenges import maximum

    plan['challenges'] = []
    for key in chosen:
        entry = deepcopy(challenges[key])
        count = (challenge_stacks or {}).get(key, 1)
        integer(count, 'Challenge stacks', 1)
        if count > maximum(entry):
            raise ValueError('Challenge stacks exceed reviewed cap.')
        entry.update(stacks=count, victory_gems=count * entry['victory_gems_per_stack'])
        plan['challenges'].append(entry)
    if any(e['enemy_effect_id'] == 'powerhouse' for e in plan['challenges']):
        for wave in plan['wave_schedule']:
            for group in wave['groups']:
                group['veteran_level'] = 2
                for heavy in config['camp_balance']['special_units_by_country'][group['country']][
                    :2
                ]:
                    candidates = [
                        u
                        for u in group['units']
                        if u['count'] > 1 and u['type'] not in group.get('air_types', [])
                    ]
                    if candidates:
                        largest = max(candidates, key=lambda u: u['count'])
                        largest['count'] -= 1
                        existing = next((u for u in group['units'] if u['type'] == heavy), None)
                        if existing:
                            existing['count'] += 1
                        else:
                            group['units'].append({'type': heavy, 'count': 1})
    rewards = {'victory': config['settings']['completion_gems']}
    rewards.update({'milestone:' + e['id']: e['gems'] for e in plan['milestones']})
    rewards.update({'challenge:' + e['id']: e['victory_gems'] for e in plan['challenges']})
    families = list(SIDE_COUNTRIES)
    camp_rng = random.Random(seed + ':dta:camps')
    countries = []
    while len(countries) < 6:
        camp_rng.shuffle(families)
        countries.extend(families)
    balance = config['camp_balance']
    plan['camp_balance'] = deepcopy(balance)
    for camp, faction in zip(plan['map']['camps'], countries):
        count = min(30, balance['guards_by_difficulty'][difficulty] * wave_multiplier)
        variants = [v for s in config['wave_rosters'][faction] for v in s['variants']]
        variant = camp_rng.choice(variants)
        special = (
            camp_rng.choice(balance['special_units_by_country'][faction])
            if count > 1 and camp_rng.randrange(100) < balance['special_chance_percent']
            else None
        )
        guards = size_composition(
            variant['units'][: 5 if special else 6],
            base_units=count - bool(special),
            seed=seed + camp['id'],
            house=camp['enemy_index'],
            seconds=0,
        )
        if special:
            existing = next((u for u in guards if u['type'] == special), None)
            if existing:
                existing['count'] += 1
            else:
                guards.append({'type': special, 'count': 1})
        camp.update(guards=guards, guard_country=faction, special_unit=special)
        rng = random.Random(seed + ':dta:crate:' + camp['id'])
        reward = deepcopy(
            rng.choices(
                config['crate_rewards'], weights=[e['weight'] for e in config['crate_rewards']]
            )[0]
        )
        reward['units'] = reward.pop('units_by_country')[player_country]
        reward.pop('weight')
        camp['crate_reward'] = reward
        rewards['camp:' + camp['id']] = camp['gems']
        for seat in range(human_count):
            rewards[f'camp_pick:{seat}:' + camp['id']] = 0
    performance = plan['performance']
    for i in range(1, performance['max_tiers'] + 1):
        rewards[f'kills:{i * performance["units_per_tier"]}'] = performance['gems_per_tier']
    plan['gem_rewards'] = rewards
    plan['reinforcement_schedule'] = (
        [
            {'seconds': n, 'units': deepcopy(effects['reinforcements']['units'])}
            for n in range(300, 3600, 300)
        ]
        if effects['reinforcements']
        else []
    )
    # Native direct credit actions need no escrow and add no transfer score.
    # Structure transfers are enumerated identically by the engine adapter.
    setup = (
        2
        + len(effects['starting_buildings'])
        + len(effects['starting_power_buildings'])
        + len(effects['defense_types'])
    )
    setup += sum(u['count'] for u in effects['starting_units']) + sum(
        u['count'] for u in effects['starting_harvesters']
    )
    plan['initial_transfer_kills'] = setup + 1
    plan['coop_initial_transfer_kills'] = [setup + (seat == 0) for seat in range(human_count)]
    plan['coalition_scores'] = [
        dict(
            actor=('FFPLAYER', 'FFALLY1', 'FFALLY2')[seat],
            name=(
                (list(coop_players)[seat] if coop_players else 'Commander')
                if seat < human_count
                else None
            ),
            color=seat,
            scheme=(3, 21, 47)[seat],
            camp_slot=seat if seat < human_count else None,
            initial_transfers=setup + (seat == 0) - (seat >= human_count),
        )
        for seat in range(friend_count)
    ]
    return plan
