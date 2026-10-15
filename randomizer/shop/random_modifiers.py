from hashlib import sha256

from .catalogue import canonical_reward_for_id, catalogue_entry, shop_catalogue, shop_entry_available
from .config import SHOP_CONFIG
from .model import ShopRewardType
from .modifiers import modifier_allows_shop_offer, modifier_effects, modifier_shop_faction


def _rank(run, stream, value):
    return sha256(
        f'{run.seed}:{run.stage}:{stream}:{value}'.encode('utf-8')
    ).digest()


def random_access_candidates(run, *, mutation=False):
    effects = modifier_effects(run.modifiers)
    faction = modifier_shop_faction(
        run.modifiers, run.stage,
        run.reward_settings.get('shop_faction_filter') or run.campaign_filter,
        run_key=f'{run.seed}:{run.run_id}',
    )
    excluded = {
        str(item).upper()
        for item in run.reward_settings.get('excluded_unit_access_ids', ())
    }
    for entry in shop_catalogue():
        if entry.reward_type not in {
            ShopRewardType.UNIT_ACCESS, ShopRewardType.POWER_ACCESS,
        } or mutation and entry.reward_type is not ShopRewardType.POWER_ACCESS:
            continue
        reward = canonical_reward_for_id(entry.reward_id)
        if not mutation and not modifier_allows_shop_offer(
            entry, reward, run.modifiers, automatic=True,
        ):
            continue
        if entry.reward_type is ShopRewardType.UNIT_ACCESS and entry.target_id in excluded:
            continue
        if shop_entry_available(
            entry,
            campaign_filter=(
                'All Campaigns' if effects['cross_faction_power_offers']
                and entry.reward_type is ShopRewardType.POWER_ACCESS else faction
            ),
            reward_mode=run.reward_mode,
            strict_faction=True,
        ):
            yield entry


def mutation_reward_ids(run):
    if not modifier_effects(run.modifiers)['unknown_mutation']:
        return ()
    candidates = tuple(random_access_candidates(run, mutation=True))
    if not candidates:
        return ()
    entry = min(candidates, key=lambda item: _rank(run, 'mutation', item.reward_id))
    return (entry.reward_id,)


def filter_mutation_rewards(run, reward_ids):
    if not modifier_effects(run.modifiers)['unknown_mutation']:
        return tuple(reward_ids)
    return tuple(
        reward_id for reward_id in reward_ids
        if canonical_reward_for_id(reward_id).get('kind') != 'superweapon'
    ) + mutation_reward_ids(run)


def victory_unlock(run):
    from .active import active_shop_power_ids, active_shop_role_tech_ids

    if not modifier_effects(run.modifiers)['vibe_unlocking']:
        return None
    units = set(active_shop_role_tech_ids(run))
    powers = set(active_shop_power_ids(run))
    candidates = [
        entry for entry in random_access_candidates(run)
        if entry.target_id not in (
            units if entry.reward_type is ShopRewardType.UNIT_ACCESS else powers
        )
    ]
    return min(
        candidates, key=lambda entry: _rank(run, 'vibe-unlock', entry.reward_id),
        default=None,
    )


def random_training_price(run, config=SHOP_CONFIG):
    effects = modifier_effects(run.modifiers, config)
    interval = effects['random_training_stage_interval']
    return (
        effects['random_training_price'] + (max(1, run.stage) - 1) // interval
        if interval else 0
    )


def random_training_entry(run, loadout):
    from .active import active_shop_rewards, active_shop_role_tech_ids, role_buff_stack_count
    from randomizer.rewards.catalogue import unit_role_equivalents

    active = set(active_shop_role_tech_ids(loadout))
    rewards = active_shop_rewards(loadout)
    faction = run.reward_settings.get('shop_faction_filter') or run.campaign_filter
    effects = modifier_effects(run.modifiers)
    candidates = {}
    for entry in shop_catalogue():
        if entry.reward_type is not ShopRewardType.UNIT_BUFF or entry.target_id not in active:
            continue
        if not modifier_allows_shop_offer(
            entry, canonical_reward_for_id(entry.reward_id), run.modifiers, automatic=True,
        ):
            continue
        if not shop_entry_available(
            entry, campaign_filter=(
                'All Campaigns' if effects['rotate_shop_faction'] else faction
            ), reward_mode=run.reward_mode, strict_faction=True,
        ):
            continue
        stacks = role_buff_stack_count(rewards, canonical_reward_for_id(entry.reward_id))
        if entry.stack_limit is not None and stacks >= entry.stack_limit:
            continue
        unit = tuple(sorted(unit_role_equivalents(entry.target_id)))
        candidates.setdefault(unit, []).append(entry)
    if not candidates:
        return None
    sequence = sum(
        item.stacks for item in run.run_buffs
        if (entry := catalogue_entry(canonical_reward_for_id(item.reward_id))) is not None
        and entry.reward_type is ShopRewardType.UNIT_BUFF
    )
    stream = f'random-training:{sequence}'
    unit = min(candidates, key=lambda item: _rank(run, stream, ','.join(item)))
    return min(candidates[unit], key=lambda item: _rank(run, stream, item.reward_id))
