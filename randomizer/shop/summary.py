"""Pure player-facing Shop reward and run summaries."""

from collections import Counter

from randomizer.rewards.enemy_scaling import enemy_effect_text

from .config import SHOP_CONFIG
from .economy import mission_reward
from .model import RunStatus
from .modifiers import modifier_difficulty
from .text import gem_text


def enemy_buff_breakdown_lines(entries):
    """Show total awarded stacks and cumulative effect of each distinct buff."""
    counts = Counter()
    rewards = {}
    for entry in entries:
        reward = entry['reward']
        effect_id = str(reward.get('enemy_effect_id') or reward.get('id') or '')
        if not effect_id:
            continue
        counts[effect_id] += 1
        rewards.setdefault(effect_id, reward)
    total = sum(counts.values())
    lines = [
        f'Enemy AI: {total} total buff stack{"s" if total != 1 else ""} '
        f'across {len(counts)} effect{"s" if len(counts) != 1 else ""}'
    ]
    if total:
        lines[0] += f' (+{total} Ore / +{gem_text(total)} on victory)'
        lines.extend(
            f'• {rewards[effect_id]["name"]} '
            f'({count} stack{"s" if count != 1 else ""}): '
            f'{enemy_effect_text(rewards[effect_id], count)}'
            for effect_id, count in counts.items()
        )
    return tuple(lines)


def run_modifier_reward_delta(
    mission_class,
    *,
    victory_coin_bonus_level=0,
    modifiers=(),
    mission_modifier=None,
    challenge_hunter_level=0,
    enemy_buff_count=0,
    config=SHOP_CONFIG,
):
    """Return exact Ore/Gem change caused by selected run modifiers."""
    modifiers = tuple(modifiers)
    modified = mission_reward(
        mission_class,
        victory_coin_bonus_level=victory_coin_bonus_level,
        modifiers=modifiers,
        mission_modifier=mission_modifier,
        challenge_hunter_level=challenge_hunter_level,
        enemy_buff_count=enemy_buff_count,
        config=config,
    )
    unmodified = mission_reward(
        mission_class,
        victory_coin_bonus_level=victory_coin_bonus_level,
        modifiers=(),
        mission_modifier=mission_modifier,
        challenge_hunter_level=challenge_hunter_level,
        enemy_buff_count=enemy_buff_count,
        config=config,
    )
    return (
        modified.run_coins - unmodified.run_coins,
        modified.meta_coins - unmodified.meta_coins,
    )


def run_modifier_bonus_text(run_coins, meta_coins):
    gem_label = 'Gem' if abs(meta_coins) == 1 else 'Gems'
    return (
        f'Run modifier bonus: {run_coins:+d} Ore / '
        f'{meta_coins:+d} {gem_label}'
    )


def run_modifier_reward_lines(
    mission_class,
    *,
    victory_coin_bonus_level=0,
    modifiers=(),
    mission_modifier=None,
    challenge_hunter_level=0,
    enemy_buff_count=0,
    config=SHOP_CONFIG,
):
    """Attribute exact reward deltas to run modifiers in selected order."""
    common = dict(
        victory_coin_bonus_level=victory_coin_bonus_level,
        mission_modifier=mission_modifier,
        challenge_hunter_level=challenge_hunter_level,
        enemy_buff_count=enemy_buff_count,
        config=config,
    )
    active = []
    previous = mission_reward(mission_class, modifiers=(), **common)
    lines = []
    for modifier_id in dict.fromkeys(modifiers):
        active.append(modifier_id)
        current = mission_reward(
            mission_class, modifiers=active, **common
        )
        ore = current.run_coins - previous.run_coins
        gems = current.meta_coins - previous.meta_coins
        if ore or gems:
            lines.append(
                f'• {config.modifiers[modifier_id].display_name}: '
                f'{ore:+d} Ore / {gems:+d} '
                f'{"Gem" if abs(gems) == 1 else "Gems"}'
            )
        previous = current
    return tuple(lines)


def reward_breakdown_lines(
    mission_class,
    *,
    victory_coin_bonus_level=0,
    modifiers=(),
    mission_modifier=None,
    challenge_hunter_level=0,
    enemy_buff_count=0,
    config=SHOP_CONFIG,
):
    definition = config.mission_rewards[mission_class]
    reward = mission_reward(
        mission_class,
        victory_coin_bonus_level=victory_coin_bonus_level,
        modifiers=modifiers,
        mission_modifier=mission_modifier,
        challenge_hunter_level=challenge_hunter_level,
        enemy_buff_count=enemy_buff_count,
        config=config,
    )
    lines = [
        f'{definition.display_name} base: +{definition.run_coins} Ore, '
        f'+{gem_text(definition.meta_coins)}',
    ]
    if modifiers:
        modifier_run_coins, modifier_meta_coins = run_modifier_reward_delta(
            mission_class,
            victory_coin_bonus_level=victory_coin_bonus_level,
            modifiers=modifiers,
            mission_modifier=mission_modifier,
            challenge_hunter_level=challenge_hunter_level,
            enemy_buff_count=enemy_buff_count,
            config=config,
        )
        if modifier_run_coins or modifier_meta_coins:
            lines.append(run_modifier_bonus_text(
                modifier_run_coins, modifier_meta_coins
            ))
    if reward.victory_bonus_run_coins:
        lines.append(
            'Permanent Victory Bonus: '
            f'+{reward.victory_bonus_run_coins} Ore'
        )
    if mission_modifier is not None:
        lines.append(
            f'{mission_modifier.title}: '
            f'+{reward.mission_bonus_run_coins} Ore, '
            f'+{gem_text(reward.mission_bonus_meta_coins)}'
        )
    if reward.challenge_hunter_run_coins or reward.challenge_hunter_meta_coins:
        lines.append(
            'Challenge Hunter: '
            f'+{reward.challenge_hunter_run_coins} Ore, '
            f'+{gem_text(reward.challenge_hunter_meta_coins)}'
        )
    if enemy_buff_count:
        lines.append(
            f'Enemy AI buffs ({enemy_buff_count}): '
            f'+{enemy_buff_count} Ore, +{gem_text(enemy_buff_count)}'
        )
    lines.append(
        f'Total: +{reward.run_coins} Ore, '
        f'+{gem_text(reward.meta_coins)}'
    )
    return tuple(lines)


def run_summary_lines(profile, run, mission_titles=None, config=SHOP_CONFIG):
    if run is None:
        return ('No Shop run exists.',)
    mission_titles = mission_titles or {}
    status_heading = {
        RunStatus.ACTIVE: 'RUN ACTIVE',
        RunStatus.FAILED: 'RUN OVER',
        RunStatus.COMPLETED: 'RUN VICTORY',
    }[run.status]
    token_definition = config.permanent_upgrades['free_buff_token']
    free_buff_token_capacity = (
        profile.upgrade_level('free_buff_token')
        * int(token_definition.effects['tokens_per_level'])
    )
    lines = [
        status_heading,
        f'Seed: {run.seed}',
        f'Missions won: {len(run.completed_missions)} / {run.run_length}',
        f'Run Ore remaining: {run.run_coins}',
        f'Permanent Gems: {profile.meta_coins}',
        f'Random starting unit unlocks: '
        f'{len(run.random_starting_unit_unlocks)}',
        f'Run purchases: {sum(item.quantity for item in run.run_purchases)}',
        f'Buff stacks purchased: {sum(item.stacks for item in run.run_buffs)}',
        f'Free starting draft buffs: '
        f'{sum(item.stacks for item in run.starting_draft_buffs)}',
        f'Free Buff Tokens used this stage: '
        f'{run.free_buff_tokens_used_stage} / {free_buff_token_capacity}',
        f'Free Buff Tokens used this run: {run.free_buff_tokens_used}',
        f'Emergency Revivals used: {run.emergency_revivals_used}',
        f'Run challenge modifiers: {modifier_difficulty(run.modifiers)}',
        'Modifiers: ' + (
            ', '.join(
                config.modifiers[item].display_name for item in run.modifiers
            )
            if run.modifiers else 'None'
        ),
    ]
    if run.status is RunStatus.FAILED:
        if run.failed_mission_code == 'GAVE_UP':
            lines.append(f'Run given up at stage {run.failed_stage}.')
        else:
            title = mission_titles.get(
                run.failed_mission_code, run.failed_mission_code
            )
            lines.append(f'Failed at stage {run.failed_stage}: {title}')
        if profile.salvaged_run_coins:
            lines.append(
                f'Recovery Salvage banked: {profile.salvaged_run_coins} Ore '
                'for the next run.'
            )
    if run.completed_missions:
        lines.append('Completed missions:')
        lines.extend(
            f'  {index}. {mission_titles.get(code, code)}'
            for index, code in enumerate(run.completed_missions, start=1)
        )
    return tuple(lines)
