"""Personal cooperative profiles and independently purchased Shop loadouts."""

from dataclasses import replace

from randomizer.rewards.catalogue import SHOP_ALWAYS_AVAILABLE_UNIT_GROUPS, unit_role_equivalents
from randomizer.shop.active import active_shop_role_tech_ids
from randomizer.shop.catalogue import canonical_reward_for_id, canonical_reward_id, catalogue_entry, shop_role_entry_available
from randomizer.shop.config import SHOP_CONFIG
from randomizer.shop.model import BuffPurchase, ShopRewardType
from randomizer.shop.modifiers import modifier_allows_loadout_entry
from randomizer.shop.state import normalize_shop_profile, normalize_shop_run

from .maps import supported_reward


PERSONAL_UPGRADES = {
    'global_production_speed': 'shop_production',
    'global_cost_reduction': 'shop_cost',
    'global_movement_speed': 'shop_speed',
    'global_armor': 'shop_armor',
    'global_firepower': 'shop_damage',
    'global_reload': 'shop_reload',
    'mission_starting_credits': None,
}


def contribution(profile, selected, run=None):
    """Validate owned selections and share only permanent gameplay data."""
    selected = tuple(dict.fromkeys(canonical_reward_id(item) for item in selected))
    if any(item not in profile.permanent_unit_unlocks for item in selected):
        raise ValueError('Co-op loadout contains an unowned permanent unit.')
    definition = SHOP_CONFIG.permanent_upgrades['expanded_loadout']
    maximum = (SHOP_CONFIG.max_selected_permanent_units
               + profile.upgrade_level('expanded_loadout') * int(definition.effects['slots_per_level']))
    if len(selected) > maximum:
        raise ValueError('Co-op loadout exceeds the player\'s permanent loadout slots.')
    for item in selected:
        reward = canonical_reward_for_id(item)
        entry = catalogue_entry(reward)
        if entry is None or entry.reward_type is not ShopRewardType.UNIT_ACCESS or not supported_reward(reward):
            raise ValueError('Co-op loadout contains an unsupported permanent unit.')
    return {
        'selected': list(selected),
        'run': run.to_dict() if run is not None else None,
        'profile': {
            'permanent_unit_unlocks': list(profile.permanent_unit_unlocks),
            'permanent_buffs': [item.to_dict() for item in profile.permanent_buffs
                                if supported_reward(canonical_reward_for_id(item.reward_id))],
            'permanent_upgrades': {key: profile.upgrade_level(key)
                                   for key in (*PERSONAL_UPGRADES, 'expanded_loadout')},
        },
    }


def normalize_contribution(document):
    if not isinstance(document, dict) or not isinstance(document.get('selected'), list):
        raise ValueError('Invalid co-op permanent loadout.')
    if 'run' not in document:
        raise ValueError('Update every launcher for personal co-op Shop purchases.')
    run = normalize_shop_run(document['run'])
    return contribution(normalize_shop_profile(document['profile']), document['selected'], run)


def personal_upgrade_levels(loadout):
    return {key: int(loadout['profile']['permanent_upgrades'].get(key, 0))
            for key in PERSONAL_UPGRADES}


def _buff_key(reward):
    unit = str(reward.get('unit') or '').upper()
    peers = set(unit_role_equivalents(unit))
    for group in SHOP_ALWAYS_AVAILABLE_UNIT_GROUPS:
        if unit in group:
            peers.update(group)
    return tuple(sorted(peers)), reward.get('buff_type')


def personal_shop_run(run, loadout):
    """Layer the player's permanent selections and buffs over their own run.

    Run purchases, starters and draft rewards belong to this player.
    This view is never written back to a run or personal profile.
    """
    if run is None:
        return run
    selected = []
    faction = run.reward_settings.get('shop_faction_filter') or run.campaign_filter
    for reward_id in loadout['selected']:
        reward = canonical_reward_for_id(reward_id)
        entry = catalogue_entry(reward)
        if (shop_role_entry_available(entry, campaign_filter=faction,
                                     reward_mode=run.reward_mode, strict_faction=True)
                and modifier_allows_loadout_entry(entry, reward, run.modifiers)):
            selected.append(reward_id)
    combined = replace(run, selected_permanent_units=tuple(selected),
                       permanent_buffs_snapshot=(), permanent_power_unlocks_snapshot=())
    active = set(active_shop_role_tech_ids(combined))
    own = {}
    if not run.reward_settings.get('disable_permanent_unit_buffs'):
        for item in normalize_shop_profile(loadout['profile']).permanent_buffs:
            reward = canonical_reward_for_id(item.reward_id)
            entry = catalogue_entry(reward)
            if (entry is None or entry.reward_type is not ShopRewardType.UNIT_BUFF
                    or not supported_reward(reward) or entry.target_id not in active):
                continue
            key = _buff_key(reward)
            previous = own.get(key)
            stacks = min((previous.stacks if previous else 0) + item.stacks, entry.stack_limit or 1)
            own[key] = BuffPurchase(item.reward_id, stacks)
    purchased = {}
    for item in (*run.run_buffs, *run.starting_draft_buffs):
        reward = canonical_reward_for_id(item.reward_id)
        key = _buff_key(reward)
        purchased[key] = purchased.get(key, 0) + item.stacks
    capped = []
    for key, item in own.items():
        entry = catalogue_entry(canonical_reward_for_id(item.reward_id))
        stacks = min(item.stacks, max(0, (entry.stack_limit or 1) - purchased.get(key, 0)))
        if stacks:
            capped.append(BuffPurchase(item.reward_id, stacks))
    # Purchased buffs only apply to units this player can actually produce.
    def accessible(item):
        entry = catalogue_entry(canonical_reward_for_id(item.reward_id))
        return entry is not None and entry.target_id in active
    return replace(combined, permanent_buffs_snapshot=tuple(capped),
                   run_buffs=tuple(item for item in run.run_buffs if accessible(item)),
                   starting_draft_buffs=tuple(item for item in run.starting_draft_buffs if accessible(item)))
