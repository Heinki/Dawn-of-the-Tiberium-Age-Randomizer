from copy import deepcopy
from dataclasses import replace

from randomizer.shop.archipelago import archipelago_shop_identity, shop_reward_ids_from_ap_ledger
from randomizer.shop.model import RunStatus
from randomizer.shop.transitions import merge_archipelago_entitlements


def shared_run_state(state, slot_data=None):
    shared = deepcopy(state)
    ap = shared.get('archipelago')
    if isinstance(ap, dict):
        allowed = ('enabled', 'activation', 'manifest_checksum', 'run_manifest',
                   'slot_data', 'team', 'slot', 'received_rewards')
        shared['archipelago'] = {key: ap[key] for key in allowed if key in ap}
        shared['archipelago']['shared_coop'] = True
        if isinstance(slot_data, dict):
            mapping = shared['archipelago'].setdefault('slot_data', {})
            for key in ('locations', 'local_victories', 'items', 'shop'):
                if key in slot_data:
                    mapping[key] = deepcopy(slot_data[key])
        shared['archipelago']['checkpoint'] = {
            'seed_name': (ap.get('checkpoint') or {}).get('seed_name', ''),
        }
    return shared


def shared_shop_inventory(run, state):
    ap = state.get('archipelago')
    if run is None or not isinstance(ap, dict) or not ap.get('enabled'):
        return run
    identity = archipelago_shop_identity(ap)
    if not identity or run.seed != state.get('seed'):
        raise ValueError('Personal Shop run differs from the shared Archipelago seed.')
    if run.ap_identity and run.ap_identity != identity:
        raise ValueError('Personal Shop run belongs to another Archipelago slot.')
    pool = tuple(((ap.get('slot_data') or {}).get('shop') or {}).get('mission_pool', ()))
    if (not run.reward_settings.get('coop_mode') or not pool
            or set(pool) != set(run.eligible_mission_codes)):
        raise ValueError('Shared Archipelago Shop mission pool differs from your co-op save.')
    run = replace(run, ap_identity=identity)
    return merge_archipelago_entitlements(
        run, identity, shop_reward_ids_from_ap_ledger(ap.get('received_rewards', ())))
