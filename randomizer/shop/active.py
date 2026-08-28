"""Resolve the active standalone Shop loadout from persisted state."""

import random

from randomizer.missions.tier_one import (
    STANDARD_TIER_ONE_FAMILIES,
    TIER_ONE_DEFENSE_ROLE_UNITS,
    TIER_ONE_DEFENSE_ROLES,
    TIER_ONE_GROUND_ROLES,
    TIER_ONE_ROLE_BY_MARKER,
    TIER_ONE_ROLE_MARKERS,
    TIER_ONE_ROLE_UNITS,
)
from randomizer.rewards.rules import tech_ids_for_rewards

from .catalogue import canonical_reward_for_id, catalogue_entry
from .archipelago import ap_automatic_reward_ids
from .model import ShopRewardType


_SHOP_STARTER_FAMILIES = {
    'All Campaigns': ('gdi', 'nod', 'allies', 'soviet'),
    'GDI': ('gdi',),
    'Nod': ('nod',),
    'Allies': ('allies',),
    'Soviet': ('soviet',),
}


def _starter_families(campaign):
    campaign = str(campaign or 'All Campaigns')
    return _SHOP_STARTER_FAMILIES.get(
        campaign, _SHOP_STARTER_FAMILIES['All Campaigns']
    )


def shop_starter_unit_ids(
    *, seed, starting_unit_ids, faction_filter, excluded_unit_ids=()
):
    """Resolve fixed Shop identities, or preserve saved concrete IDs."""
    if not starting_unit_ids:
        return ()
    families = _starter_families(faction_filter)
    requested_ids = tuple(dict.fromkeys(
        str(item).upper() for item in starting_unit_ids if str(item)
    ))
    if not set(requested_ids).intersection(TIER_ONE_ROLE_MARKERS.values()):
        return requested_ids
    excluded = {str(item).upper() for item in excluded_unit_ids}
    requested_roles = [
        TIER_ONE_ROLE_BY_MARKER[item]
        for item in requested_ids
        if item in TIER_ONE_ROLE_BY_MARKER
    ]
    rng = random.Random(f'{seed}:shop-tier-one-units')
    ground_families = list(families)
    rng.shuffle(ground_families)
    selected = []
    ground_index = 0
    for role in requested_roles:
        if role == 'basic_aircraft':
            family = rng.choice(list(families))
        else:
            family = ground_families[ground_index % len(ground_families)]
            ground_index += 1
        unit_id = str(TIER_ONE_ROLE_UNITS[role][family][0]).upper()
        if unit_id not in excluded:
            selected.append(unit_id)
    return tuple(selected)


def shop_starter_defense_ids(
    *, seed, starting_defense_ids, faction_filter, excluded_unit_ids=()
):
    """Resolve one seeded Shop defense identity per defense role."""
    requested = {
        str(item).upper() for item in starting_defense_ids if str(item)
    }
    if not requested:
        return ()
    excluded = {str(item).upper() for item in excluded_unit_ids}
    families = list(_starter_families(faction_filter))
    rng = random.Random(f'{seed}:shop-tier-one-defenses')
    rng.shuffle(families)
    selected = []
    for index, role in enumerate(TIER_ONE_DEFENSE_ROLES):
        family = families[index % len(families)]
        unit_id = str(TIER_ONE_DEFENSE_ROLE_UNITS[role][family]).upper()
        if unit_id not in excluded:
            selected.append(unit_id)
    return tuple(selected)


def active_shop_starter_unit_ids(run):
    """Return five fixed concrete Tier-1 starters for this run."""
    if run is None:
        return ()
    return shop_starter_unit_ids(
        seed=run.seed,
        starting_unit_ids=run.starting_unit_ids,
        faction_filter=(
            run.reward_settings.get('shop_faction_filter')
            or run.campaign_filter
        ),
        excluded_unit_ids=run.reward_settings.get(
            'excluded_unit_access_ids', ()
        ),
    )


def active_shop_starter_defense_ids(run):
    """Return fixed concrete Tier-1 defenses for this run."""
    if run is None:
        return ()
    return shop_starter_defense_ids(
        seed=run.seed,
        starting_defense_ids=run.starting_defense_ids,
        faction_filter=(
            run.reward_settings.get('shop_faction_filter')
            or run.campaign_filter
        ),
        excluded_unit_ids=run.reward_settings.get(
            'excluded_unit_access_ids', ()
        ),
    )


def active_shop_reward_ids(run):
    """Return canonical reward IDs selected or purchased for this run."""
    if run is None:
        return ()
    reward_ids = [
        *run.selected_permanent_units,
        *ap_automatic_reward_ids(run.ap_entitlements_snapshot),
        *(buff.reward_id for buff in run.permanent_buffs_snapshot),
        *(purchase.reward_id for purchase in run.run_purchases),
        *(buff.reward_id for buff in run.run_buffs),
        *(buff.reward_id for buff in run.starting_draft_buffs),
    ]
    return tuple(dict.fromkeys(str(reward_id) for reward_id in reward_ids))


def active_shop_rewards(run):
    """Return canonical launch rewards, preserving purchased stack counts."""
    if run is None:
        return ()
    reward_ids = list(run.selected_permanent_units)
    active_unit_access = set(run.selected_permanent_units)
    for reward_id in ap_automatic_reward_ids(run.ap_entitlements_snapshot):
        entry = catalogue_entry(canonical_reward_for_id(reward_id))
        if (
            entry is not None
            and entry.reward_type is ShopRewardType.UNIT_ACCESS
        ):
            if entry.reward_id in active_unit_access:
                continue
            active_unit_access.add(entry.reward_id)
        reward_ids.append(reward_id)
    for buff in run.permanent_buffs_snapshot:
        reward_ids.extend([buff.reward_id] * buff.stacks)
    for purchase in run.run_purchases:
        reward_ids.extend([purchase.reward_id] * purchase.quantity)
    for buff in run.run_buffs:
        reward_ids.extend([buff.reward_id] * buff.stacks)
    for buff in run.starting_draft_buffs:
        reward_ids.extend([buff.reward_id] * buff.stacks)
    return tuple(canonical_reward_for_id(reward_id) for reward_id in reward_ids)


def active_shop_tech_ids(run):
    if run is None:
        return ()
    tech_ids = set(active_shop_starter_unit_ids(run))
    tech_ids.update(active_shop_starter_defense_ids(run))
    rewards = [
        canonical_reward_for_id(reward_id)
        for reward_id in active_shop_reward_ids(run)
    ]
    tech_ids.update(tech_ids_for_rewards(rewards))
    return tuple(sorted(tech_ids))


def active_shop_power_ids(run):
    power_ids = set()
    for reward_id in active_shop_reward_ids(run):
        reward = canonical_reward_for_id(reward_id)
        power_id = str(reward.get('superweapon') or '').upper()
        if power_id and reward.get('kind') != 'buff':
            power_ids.add(power_id)
    return tuple(sorted(power_ids))
