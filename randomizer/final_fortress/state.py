"""Target-owned saves, frozen plans and exactly-once native receipts."""

from copy import deepcopy
import re
from . import MODE_ID
from .catalogue import SIDE_COUNTRIES
from .config import DIFFICULTY_IDS, identifier, integer, validate_wave_multiplier

SCHEMA_VERSION = 1


def new_state():
    return {
        'schema_version': SCHEMA_VERSION,
        'game_id': 'dta',
        'mode_id': MODE_ID,
        'gems': 0,
        'owned_perks': [],
        'selected_perks': [],
        'perk_ranks': {},
        'preferences': {
            'difficulty': 'normal',
            'player_country': None,
            'wave_multiplier': 1,
            'workspace_selected': False,
            'selected_challenges': [],
            'challenge_stacks': {},
            'map_id': None,
        },
        'run': None,
        'coop_run_ids': [],
    }


def _ids(value, name):
    if not isinstance(value, list) or len(set(value)) != len(value):
        raise ValueError(f'{name} requires unique IDs.')
    for key in value:
        identifier(key, name)


def normalize_state(document):
    if (
        not isinstance(document, dict)
        or set(document) != set(new_state())
        or type(document['schema_version']) is not int
        or document['schema_version'] != SCHEMA_VERSION
        or document['game_id'] != 'dta'
        or document['mode_id'] != MODE_ID
    ):
        raise ValueError('Unsupported DTA Fortress save; other games cannot supply progression.')
    state = deepcopy(document)
    integer(state['gems'], 'Defensive Points')
    for field in ('owned_perks', 'selected_perks'):
        _ids(state[field], field)
    if not set(state['selected_perks']) <= set(state['owned_perks']):
        raise ValueError('Selected perks must be purchased.')
    if not isinstance(state['perk_ranks'], dict) or set(state['perk_ranks']) != set(
        state['owned_perks']
    ):
        raise ValueError('Purchased ranks must match ownership.')
    from .perks import rank_limit

    for key, rank in state['perk_ranks'].items():
        integer(rank, 'Perk rank', 1)
        if rank > rank_limit(key):
            raise ValueError('Invalid purchased perk rank.')
    preferences = state['preferences']
    if (
        not isinstance(preferences, dict)
        or set(preferences) != set(new_state()['preferences'])
        or preferences['difficulty'] not in DIFFICULTY_IDS
        or preferences['player_country'] not in (None, *SIDE_COUNTRIES)
        or type(preferences['workspace_selected']) is not bool
    ):
        raise ValueError('Invalid DTA Fortress preferences.')
    validate_wave_multiplier(preferences['wave_multiplier'])
    if preferences['map_id'] is not None:
        identifier(preferences['map_id'], 'Map ID')
    _ids(preferences['selected_challenges'], 'Selected Challenges')
    if not isinstance(preferences['challenge_stacks'], dict):
        raise ValueError('Invalid Challenge stacks.')
    for key, count in preferences['challenge_stacks'].items():
        identifier(key, 'Challenge ID')
        integer(count, 'Challenge stacks', 1)
        if count > 100:
            raise ValueError('Invalid Challenge stacks.')
    receipts = state['coop_run_ids']
    if (
        not isinstance(receipts, list)
        or len(set(receipts)) != len(receipts)
        or any(
            not isinstance(key, str) or not re.fullmatch('[0-9a-f]{32}', key) for key in receipts
        )
    ):
        raise ValueError('Invalid joined-run receipts.')
    run = state['run']
    if run is None:
        return state
    required = {'id', 'status', 'config', 'plan', 'claimed_events'}
    if (
        not isinstance(run, dict)
        or set(run) - required - {'coop_player', 'kill_counts'}
        or not required <= set(run)
    ):
        raise ValueError('Invalid Fortress run fields.')
    if not isinstance(run['id'], str) or not re.fullmatch('[0-9a-f]{32}', run['id']):
        raise ValueError('Invalid Fortress run ID.')
    if run['status'] not in ('active', 'victory', 'defeat', 'abandoned'):
        raise ValueError('Invalid Fortress result.')
    from .planning import build_run_plan

    plan = run['plan']
    rebuilt = build_run_plan(
        run['config'],
        difficulty=plan['difficulty'],
        seed=plan['seed'],
        player_country=plan['player_country'],
        player_color=plan.get('player_color'),
        wave_multiplier=plan['wave_multiplier'],
        selected_perks=plan['selected_perks'],
        perk_ranks=plan['perk_ranks'],
        selected_challenges=[e['id'] for e in plan['challenges']],
        challenge_stacks={e['id']: e['stacks'] for e in plan['challenges']},
        coop_players=plan.get('coop_players', ()),
        fundraising_ranks=plan['fundraising_ranks'],
        plan_version=plan['plan_version'],
    )
    if rebuilt != plan:
        raise ValueError('Stored run differs from its frozen balance snapshot.')
    guest = False
    if plan.get('coop_players'):
        slot = run.get('coop_player')
        if (
            type(slot) is not int
            or not 0 <= slot < len(plan['coop_players'])
            or run['id'] not in receipts
        ):
            raise ValueError('Invalid local co-op seat.')
        guest = slot > 0
    elif 'coop_player' in run:
        raise ValueError('Solo run cannot have a co-op seat.')
    if not guest and any(
        rank > state['perk_ranks'].get(key, 0) for key, rank in plan['perk_ranks'].items()
    ):
        raise ValueError('Run contains unpurchased perks.')
    claimed = run['claimed_events']
    if (
        not isinstance(claimed, list)
        or len(set(claimed)) != len(claimed)
        or set(claimed) - set(plan['gem_rewards']) - {'defeat', 'abandoned'}
    ):
        raise ValueError('Invalid reward receipts.')
    terminal = [e for e in claimed if e in ('victory', 'defeat', 'abandoned')]
    if terminal != ([] if run['status'] == 'active' else [run['status']]):
        raise ValueError('Result disagrees with terminal receipts.')
    if terminal and any(
        not e.startswith('kills:') for e in claimed[claimed.index(terminal[0]) + 1 :]
    ):
        raise ValueError('Only final native kill-score receipts may follow an outcome.')
    if run['status'] == 'abandoned' and any(e.startswith('kills:') for e in claimed):
        raise ValueError('Unfinished runs cannot earn a kill bonus.')
    if 'kill_counts' in run:
        counts = run['kill_counts']
        if (
            run['status'] not in ('victory', 'defeat')
            or not isinstance(counts, dict)
            or set(counts) != {'FFPLAYER', 'FFALLY1', 'FFALLY2'}
            or any(v is not None and (type(v) is not int or v < 0) for v in counts.values())
        ):
            raise ValueError('Invalid friendly native scores.')
    return state
