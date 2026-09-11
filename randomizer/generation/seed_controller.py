"""Generation methods shared with the launcher; no GUI dependency."""

import random
from randomizer.core.diagnostics import event as log_event
from randomizer.generation.constants import CHECK_SCHEMA_VERSION
from randomizer.maps.rules import now_stamp
from randomizer.missions.catalogue import (
    LATE_FOEHN_MISSION_CODES,
    LOW_LEVEL_MISSION_COUNT,
    NO_BUILD_MISSION_CODES,
    STARTING_UNLOCKED_MISSIONS,
    campaign_mission_counts,
    classic_mission_order,
    seed_campaign_limits,
    seed_mission_order,
)
from randomizer.progression.grid import (
    create_grid,
    grid_opening_mission_count,
)
from randomizer.rewards.arsenal import (
    ARSENAL_MODE,
    generate_mission_arsenals,
)
from randomizer.rewards.catalogue import (
    REWARD_POOL,
    check_rewards,
)
from randomizer.rewards.enemy_scaling import (
    UNSUPPORTED_AI_REWARD_REASONS,
    enemy_progress_events,
    normalize_enemy_scaling_settings,
    plan_enemy_progress_rewards,
)


class SeedGeneration:
    def build_seed_generation(self, options):
        progress = options.get('_progress') or (lambda *_args: None)
        progress('Building deterministic mission order.', 1, 5)
        seed = options['seed']
        seed_missions = options['seed_missions']
        mission_goal = options['mission_goal']
        rewards_per_check = options['rewards_per_check']
        rewards_on_victory_only = options['rewards_on_victory_only']
        use_act_based_reward_multipliers = options[
            'use_act_based_reward_multipliers'
        ]
        unlock_all_grid_rewards = options['unlock_all_grid_rewards']
        reward_settings = options['reward_settings']
        starting_defense_ids = options['starting_defense_ids']
        starting_unit_ids = options['starting_unit_ids']
        progression_mode = options['progression_mode']
        two_start_positions = options['two_start_positions']
        mission_pool_settings = options['mission_pool_settings']
        campaign_counts = campaign_mission_counts(seed_missions)
        rng = random.Random(seed)
        if progression_mode == 'Classic':
            mission_codes = classic_mission_order(seed_missions, mission_goal)
            campaign_limits = campaign_mission_counts(seed_missions[:len(mission_codes)])
        else:
            campaign_limits = seed_campaign_limits(seed_missions, mission_goal)
            try:
                low_level_count = (
                    grid_opening_mission_count(mission_goal, two_start_positions)
                    if progression_mode == 'Grid Mode'
                    else LOW_LEVEL_MISSION_COUNT
                )
            except ValueError as exc:
                raise ValueError(f'Cannot generate grid: {exc}.') from exc
            mission_codes = seed_mission_order(
                seed_missions,
                rng,
                mission_goal,
                low_level_count=low_level_count,
                preferred_opening_codes=(
                    NO_BUILD_MISSION_CODES
                    if mission_pool_settings['prioritize_no_build_missions']
                    else None
                ),
                excluded_opening_codes=LATE_FOEHN_MISSION_CODES,
            )
        grid = None
        if progression_mode == 'Grid Mode':
            try:
                grid = create_grid(
                    mission_codes,
                    two_start_positions,
                    protect_opening=True,
                )
            except ValueError as exc:
                raise ValueError(f'Cannot generate grid: {exc}.') from exc
        mission_arsenals = {}
        if options['reward_mode'] == ARSENAL_MODE:
            progress('Building seed-fixed mission arsenals.', 2, 5)
            mission_arsenals = generate_mission_arsenals(
                seed,
                mission_codes,
                reward_settings,
                reward_settings.get('arsenal'),
            )
            empty_codes = [
                code for code, arsenal in mission_arsenals.items()
                if not arsenal.get('units') and not arsenal.get('powers')
            ]
            if empty_codes:
                raise ValueError(
                    'Cannot generate seed: Arsenal exclusions leave no content for '
                    + ', '.join(empty_codes[:5])
                    + ('.' if len(empty_codes) <= 5 else ', and more.')
                )
            self._arsenal_override = mission_arsenals
        empty_reward_codes = (
            [
                code for code in mission_codes
                if not self.reward_pool_for_code(code)
            ]
            if options['reward_mode'] == ARSENAL_MODE
            else (
                [] if any(
                    self.reward_pool_for_code(code) for code in mission_codes
                ) else list(mission_codes[:1])
            )
        )
        if empty_reward_codes:
            detail = (
                ' for ' + ', '.join(empty_reward_codes[:5])
                + (', and more' if len(empty_reward_codes) > 5 else '')
                if options['reward_mode'] == ARSENAL_MODE else ''
            )
            raise ValueError(
                'Cannot generate seed: selected reward settings produce no '
                f'available rewards{detail}.'
            )

        progress('Selecting starting rewards.', 2, 5)
        manual_starting_rewards = (
            [] if options['reward_mode'] == ARSENAL_MODE
            else self.configured_manual_starting_rewards()
        )
        random_starting_rewards = (
            [] if options['reward_mode'] == ARSENAL_MODE
            else self.generate_starting_reward_plan(
                seed,
                initial_rewards=manual_starting_rewards,
            )
        )
        starting_rewards = manual_starting_rewards + random_starting_rewards
        enemy_settings = normalize_enemy_scaling_settings(
            reward_settings.get('enemy_scaling')
        )
        enemy_event_checks = {
            code: [
                {'id': check_id}
                for check_id, _name, _hint
                in self.objective_templates_for_code(code)
            ]
            for code in mission_codes
        }
        completion_events = enemy_progress_events(
            mission_codes, enemy_event_checks
        )
        enemy_progress_requested = sum(
            enemy_settings['rewards_per_completed_objective']
            if event['basis'] == 'objectives'
            else enemy_settings['rewards_per_completed_mission']
            for event in completion_events
        )
        progress_planning_settings = enemy_settings
        if (
            enemy_settings['reward_enabled']
            and enemy_progress_requested > 0
        ):
            # Both sources share one global cap. Reserve one stack per
            # multi-stack effect for normal reward rolls. For cap-one
            # effects, split effect IDs between the two sources so neither
            # option silently starves the other when several are enabled.
            progress_planning_settings = dict(enemy_settings)
            allowed_ids = sorted(enemy_settings['allowed_buff_ids'])
            progress_planning_settings['caps'] = {
                effect_id: (
                    max(0, cap - 1)
                    if cap > 1
                    else (
                        cap
                        if effect_id in allowed_ids
                        and allowed_ids.index(effect_id) % 2 == 0
                        else 0
                    )
                )
                for effect_id, cap in enemy_settings['caps'].items()
            }
        enemy_progress_plan = plan_enemy_progress_rewards(
            seed,
            progress_planning_settings,
            REWARD_POOL,
            completion_events,
            starting_rewards,
        )
        for entry in enemy_progress_plan:
            reward = dict(entry.get('reward', {}))
            effect_id = str(reward.get('enemy_effect_id') or '')
            reward['enemy_maximum'] = enemy_settings['caps'].get(
                effect_id, reward.get('enemy_maximum', 1)
            )
            entry['reward'] = reward
        progress('Planning base mission rewards.', 3, 5)
        mission_checks = self.build_mission_checks(
            mission_codes,
            seed,
            rewards_per_check=rewards_per_check,
            rewards_on_victory_only=rewards_on_victory_only,
            use_act_based_reward_multipliers=(
                use_act_based_reward_multipliers
            ),
            progression_mode=progression_mode,
            grid=grid,
            starting_rewards=starting_rewards,
            enemy_progress_plan=enemy_progress_plan,
            progress=progress,
        )
        ai_rewards_enabled = bool(
            enemy_settings['reward_enabled']
            or enemy_settings['rewards_per_completed_objective'] > 0
            or enemy_settings['rewards_per_completed_mission'] > 0
        )
        unsupported_ai_rewards = (
            list(UNSUPPORTED_AI_REWARD_REASONS) if ai_rewards_enabled else []
        )
        for reason in unsupported_ai_rewards:
            log_event('ai_reward_type_skipped', reason=reason)
        progress('Finalizing generated run.', 5, 5)
        rewards = [
            reward
            for code in mission_codes
            for check in mission_checks[code]
            for reward in check_rewards(check)
        ]
        mission_objectives = self.state_objective_summary(mission_codes)

        state = {
            'version': 1,
            'seed': seed,
            'seed_was_explicit': options.get('seed_was_explicit', False),
            'created_at': now_stamp(),
            'campaign_filter': options['campaign_filter'],
            'reward_mode': options['reward_mode'],
            'progression_mode': progression_mode,
            'mission_goal': mission_goal,
            'rewards_per_check': rewards_per_check,
            'rewards_on_victory_only': rewards_on_victory_only,
            'use_act_based_reward_multipliers': (
                use_act_based_reward_multipliers
            ),
            'unlock_all_rewards_after_final_grid_mission': unlock_all_grid_rewards,
            'starting_unlocked_missions': min(
                1 if progression_mode == 'Classic' else STARTING_UNLOCKED_MISSIONS,
                len(mission_codes),
            ),
            'mission_order': mission_codes,
            'campaign_mission_counts': campaign_counts,
            'campaign_mission_limits': campaign_limits,
            'mission_pool_settings': mission_pool_settings,
            'completed_missions': [],
            'started_missions': [],
            'mission_failure_stacks': {},
            'mission_assistance_units': {},
            'earned_rewards': [
                reward for reward in starting_rewards
                if not reward.get('max_rewards_achieved')
            ],
            'starting_rewards': starting_rewards,
            'manual_starting_rewards': manual_starting_rewards,
            'random_starting_rewards': random_starting_rewards,
            'starting_defense_ids': starting_defense_ids,
            'starting_unit_ids': starting_unit_ids,
            'reward_queue': rewards,
            'mission_checks': mission_checks,
            'mission_objectives': mission_objectives,
            'reward_settings': reward_settings,
            'enemy_progress_plan': enemy_progress_plan,
            'enemy_progress_earned': [],
            'enemy_progress_requested': enemy_progress_requested,
            'enemy_reward_applications': {},
            'mission_arsenals': mission_arsenals,
            'check_schema_version': CHECK_SCHEMA_VERSION,
        }
        if grid is not None:
            state['grid'] = grid
        return {
            'state': state,
            'seed': seed,
            'mission_goal': mission_goal,
            'rewards_per_check': rewards_per_check,
            'rewards_on_victory_only': rewards_on_victory_only,
            'use_act_based_reward_multipliers': (
                use_act_based_reward_multipliers
            ),
            'unlock_all_rewards_after_final_grid_mission': unlock_all_grid_rewards,
            'starting_defense_ids': starting_defense_ids,
            'starting_unit_ids': starting_unit_ids,
            'starting_rewards': starting_rewards,
            'manual_starting_rewards': manual_starting_rewards,
            'random_starting_rewards': random_starting_rewards,
            'campaign_counts': campaign_counts,
            'campaign_limits': campaign_limits,
            'progression_mode': progression_mode,
            'grid': grid,
            'campaign_filter': options['campaign_filter'],
            'reward_mode': options['reward_mode'],
            'reward_settings': reward_settings,
            'mission_codes': mission_codes,
            'unsupported_ai_rewards': unsupported_ai_rewards,
            'enemy_progress_requested': enemy_progress_requested,
        }

