"""Synchronize native mission decisions while keeping each Shop economy local."""

from dataclasses import replace

from randomizer.shop.config import SHOP_CONFIG
from randomizer.shop.missions import classify_mission
from randomizer.shop.model import MissionOffer, RunStatus
from randomizer.shop.state import normalize_shop_run
from randomizer.shop.transitions import (
    abandon_run, apply_mission_failure, apply_mission_victory,
)


CONTROL_FIELDS = (
    'mission_offers', 'selected_mission_code', 'mission_committed',
    'rerolls_used', 'assisted_mission_code', 'difficulty_assists_used',
    'precondition_unlocks',
)


def validate_partner_run(local, host):
    if local is None or host is None:
        raise ValueError('Each player must start their own co-op Shop run with the host seed.')
    starting_endless = (host.endless and not local.endless
                        and len(host.completed_missions) >= local.run_length)
    if (local.seed != host.seed or (local.endless != host.endless and not starting_endless)
            or (not local.endless and not starting_endless and local.run_length != host.run_length)
            or (local.allow_repeats != host.allow_repeats and not starting_endless)
            or set(local.modifiers) != set(host.modifiers)
            or set(local.eligible_mission_codes) != set(host.eligible_mission_codes)
            or local.reward_settings.get('coop_mode') is not True
            or local.reward_settings.get('coop_player_count') != host.reward_settings.get('coop_player_count')):
        raise ValueError('Shop players need matching seed, mission pool, run length and modifiers.')


def mission_view(local, host):
    """Use host mission controls over an already synchronized personal run."""
    validate_partner_run(local, host)
    if (local.status is not host.status or local.stage != host.stage
            or local.completed_missions != host.completed_missions
            or local.emergency_revivals_used != host.emergency_revivals_used):
        raise ValueError('Wait for every player to sync the current Shop stage and result.')
    if local.mission_committed and (
            local.selected_mission_code != host.selected_mission_code
            or local.mission_offers != host.mission_offers):
        raise ValueError('Host cannot change a committed Shop mission.')
    return replace(local, **{key: getattr(host, key) for key in CONTROL_FIELDS})


def gameplay_document(loadout):
    """Exclude mission-control acknowledgements when guarding prepared rewards."""
    document = dict(loadout)
    if document.get('run'):
        document['run'] = dict(document['run'])
        for key in CONTROL_FIELDS:
            document['run'].pop(key, None)
    return document


def sync_personal_run(profile, local, host, missions):
    """Replay durable host results through the guest's own currency transitions.

    Compute the entire update before persisting anything. Completion history
    makes repeated snapshots and reconnect recovery idempotent.
    """
    validate_partner_run(local, host)
    for offer in host.mission_offers:
        if (offer.mission_code not in local.eligible_mission_codes
                or offer.mission_code not in missions
                or classify_mission(missions[offer.mission_code]) is not offer.economy_class):
            raise ValueError('Host Shop offers differ from the local native catalogue.')
    completed = len(local.completed_missions)
    if local.completed_missions != host.completed_missions[:completed]:
        raise ValueError('Shop completion histories differ.')
    def continue_endless(run):
        if run.status is RunStatus.COMPLETED and host.endless and not run.endless:
            return replace(run, status=RunStatus.ACTIVE, stage=run.stage + 1,
                           run_length=run.run_length + 1, endless=True,
                           allow_repeats=True, mission_offers=host.mission_offers)
        return run

    local = continue_endless(local)
    missing = host.completed_missions[completed:]
    for index, code in enumerate(missing):
        if (local.status is not RunStatus.ACTIVE or not local.mission_committed
                or local.selected_mission_code != code):
            raise ValueError('Host Shop victory differs from the guest committed mission.')
        final = local.stage == local.run_length and not local.endless
        next_offers = host.mission_offers
        if not final and not next_offers:
            # A reconnect can deliver the final result after several stages.
            next_code = missing[index + 1] if index + 1 < len(missing) else None
            if next_code is None:
                raise ValueError('Host Shop result lacks next-stage mission offers.')
            next_offers = (MissionOffer(next_code, classify_mission(missions[next_code])),)
        result = apply_mission_victory(profile, local, code,
                                      next_offers=() if final else next_offers)
        profile, local = result.profile, result.run
        local = continue_endless(local)
        if index + 1 < len(missing):
            next_code = missing[index + 1]
            offer = MissionOffer(next_code, classify_mission(missions[next_code]))
            local = replace(local, mission_offers=(offer,),
                            selected_mission_code=next_code, mission_committed=True)
    if host.emergency_revivals_used != local.emergency_revivals_used:
        if (host.emergency_revivals_used != local.emergency_revivals_used + 1
                or not local.mission_committed or not host.mission_offers):
            raise ValueError('Host Shop revival differs from the guest committed stage.')
        result = apply_mission_failure(
            local, local.selected_mission_code, profile=profile,
            maximum_emergency_revivals=host.emergency_revivals_used,
            revival_offers=host.mission_offers,
        )
        local = result.run
    if host.status is RunStatus.FAILED and local.status is RunStatus.ACTIVE:
        if host.failed_mission_code == 'GAVE_UP':
            local = abandon_run(local).run
        else:
            salvage = SHOP_CONFIG.permanent_upgrades['recovery_salvage']
            result = apply_mission_failure(
                local, host.failed_mission_code, profile=profile,
                salvage_run_coins=(profile.upgrade_level('recovery_salvage')
                                   * int(salvage.effects['ore_per_level'])),
                maximum_salvaged_run_coins=int(salvage.effects['maximum_saved_ore']),
            )
            profile, local = result.profile, result.run
    if local.status is RunStatus.FAILED and (
            local.failed_stage != host.failed_stage
            or local.failed_mission_code != host.failed_mission_code):
        raise ValueError('Host and guest Shop failure results differ.')
    local = mission_view(local, host)
    return profile, normalize_shop_run(local.to_dict())
