"""Separate standard and all-unlocked debug profiles in source and EXE builds."""

from randomizer.core.paths import APP_DIR

from .config import validate_config
from .perks import ranks
from .state import new_state, normalize_state

STANDARD_PROFILE = 'Standard'
ALL_UNLOCKS_PROFILE = 'Debug (all unlocks)'
PROFILE_PATHS = {
    STANDARD_PROFILE: APP_DIR / 'final_fortress_state.json',
    ALL_UNLOCKS_PROFILE: APP_DIR / 'final_fortress_testing_state.json',
}


def all_unlocks_state(config):
    """Create purchased maximum ranks without inventing gameplay receipts."""
    validate_config(config)
    state = new_state()
    state['owned_perks'] = [perk['id'] for perk in config['perks']]
    state['selected_perks'] = list(state['owned_perks'])
    state['perk_ranks'] = {perk['id']: len(ranks(perk)) for perk in config['perks']}
    state['preferences'].update(player_country='GDI', workspace_selected=True)
    return normalize_state(state)
