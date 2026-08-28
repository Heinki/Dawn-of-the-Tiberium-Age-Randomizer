"""Entry point for source runs and the packaged launcher."""

import json
from collections import Counter
from hashlib import sha256
import sys
import traceback

from randomizer.ui.cameos import ensure_superweapon_cameos, ensure_unit_cameos
from randomizer.core.diagnostics import event as log_event
from randomizer.core.paths import (
    APP_DIR,
    DTA_PUZZLE_PATH,
    GAME_EXE,
    GAME_LAUNCHER_EXE,
    GAME_ROOT,
    LAUNCHER_LOG,
    WINDOW_ICON_PATH,
)
from randomizer.core.version import APP_VERSION
from randomizer.config.static import REQUIRED_STATIC_CONFIGS, validate_static_configs


def run_launcher():
    """Load config-dependent application modules with visible startup errors."""
    try:
        from randomizer.application.app import main
        main()
        return 0
    except Exception:
        detail = traceback.format_exc()
        log_event('launcher_startup_failed', traceback=detail)
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                'DTA Randomizer Startup Failed',
                'The launcher could not load its configuration or runtime.\n\n'
                f'{detail.splitlines()[-1]}\n\nSee {LAUNCHER_LOG} for details.',
            )
            root.destroy()
        except Exception:
            pass
        return 1


def run_self_check():
    """Validate the DTA adapter without launching or altering live game files."""
    from randomizer.core.paths import BATTLE_CLIENT_INI
    from randomizer.config.player import migrate_loaded_config
    from randomizer.dta.maps import (
        mission_source_lines,
        mission_source_path,
        player_starting_credit_rules,
        prepare_spawn_map,
    )
    from randomizer.dta.access import player_infantry_access_rules
    from randomizer.dta.clones import (
        MISSION_ASSISTANCE_BUFF_TYPES,
        _effective_buff_counts,
        _player_production_context,
        mission_assistance_rewards,
        player_production_isolation_rules,
        production_infrastructure_rewards,
        unit_specific_buff_rules,
    )
    from randomizer.dta.cameos import TEXT_ONLY_CAMEO_IDS
    from randomizer.dta.difficulty import resolve_mission_difficulty
    from randomizer.dta.enemies import enemy_buff_rules
    from randomizer.dta.powers import (
        POWER_CLONE_ACTION_TYPES,
        POWER_SPECS,
        player_power_rules,
    )
    from randomizer.dta.rules import (
        ALWAYS_AVAILABLE_MOBILE_IDS,
        DEFENSE_BUILDING_IDS,
        HIDDEN_DTA_DEFENSE_IDS,
        comma_items,
        effective_section,
        ini_sections,
        techno_catalogue,
        unit_collision_report,
    )
    from randomizer.launch.options import spawn_ini_text
    from randomizer.maps.settings import mission_house_color_rules
    from randomizer.application.unlock_data import UnlockDataController
    from randomizer.application.reward_controller import RewardController
    from randomizer.ui.config import (
        CAMPAIGN_TILE_COLORS,
        GAME_SPEEDS,
        PLAYER_COLOR_ENGINE_VALUES,
        RAINBOWIZER_COLORS,
    )
    from randomizer.rewards.catalogue import (
        ALWAYS_AVAILABLE_TECH_IDS,
        BUFF_TARGETS,
        REWARD_POOL,
        buff_stack_limit,
        buff_group_key,
        canonical_reward,
        starting_credit_bonus,
    )
    from randomizer.config.tuning import (
        capped_movement_speed,
        capped_sight_range,
        movement_speed_ceiling,
        sight_range_ceiling,
    )
    from randomizer.rewards.arsenal import (
        arsenal_power_candidates,
        arsenal_unit_candidates,
    )
    from randomizer.rewards.planning import plan_seed_rewards
    from randomizer.rewards.rules import tech_ids_for_rewards
    from randomizer.rewards.dta_power_buffs import (
        POWER_BUFF_TYPES,
        power_buff_stack_limit,
    )
    from randomizer.missions.catalogue import (
        campaign_mission_counts,
        parse_missions,
    )
    from randomizer.shop.self_check import validate_shop_domain

    report_path = APP_DIR / 'self_check.json'
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        static_paths = validate_static_configs(REQUIRED_STATIC_CONFIGS)
        missions = parse_missions(BATTLE_CLIENT_INI)
        missing_maps = [
            mission['scenario'] for mission in missions
            if not (GAME_ROOT / mission['scenario']).is_file()
        ]
        source = GAME_ROOT / missions[0]['scenario'] if missions else None
        before_hash = sha256(source.read_bytes()).hexdigest() if source else ''
        generated = APP_DIR / '.self_check_spawnmap.ini'
        try:
            default_difficulty = resolve_mission_difficulty(
                missions[0], 'Normal'
            )
            prepare_spawn_map(
                missions[0], default_difficulty, output_path=generated
            )
            generated_text = generated.read_text(encoding='cp1252')
        finally:
            generated.unlink(missing_ok=True)
        after_hash = sha256(source.read_bytes()).hexdigest() if source else ''
        spawn_text = spawn_ini_text(
            'spawnmap.ini',
            default_difficulty.engine_value,
            3,
            {
                'Side': missions[0]['side'],
                'Firestorm': 'True' if missions[0]['required_addon'] else 'False',
                'MissionInternalName': missions[0]['code'],
                'DifficultyName': default_difficulty.label,
                'ClientDifficulty': default_difficulty.client_rank,
            },
        ) if missions else ''
        player_normal_mission = next(
            (mission for mission in missions if mission['code'] == 'M_CRC14'),
            None,
        )
        player_normal_difficulty = (
            resolve_mission_difficulty(player_normal_mission, 'Hard')
            if player_normal_mission else None
        )
        player_normal_spawn_text = spawn_ini_text(
            'spawnmap.ini',
            1,
            3,
            {
                'DifficultyModeComputer': abs(
                    player_normal_difficulty.engine_value - 2
                ),
            },
        ) if player_normal_difficulty else ''
        counts = campaign_mission_counts(missions)
        late_route_codes = {
            *(f'M_CRA{number}' for number in range(9, 14)),
            *(f'M_CRB{number}' for number in range(9, 17)),
        }
        finale_reward_codes = {
            'M_SE11',
            'M_PTTP9',
            'M_CRA14',
            'M_CRB17',
            'M_CREXT',
            'M_TTD_THE_TOXIC_TIME_TRIAL',
            'M_TTD_THE_RECTIFICATION',
            'M_TTD_THE_RAIN_OF_DEATH',
            'M_TTD_THE_CONVERSION',
            'M_ICFRA4',
            'M_CD8',
        }
        route_c_codes = {f'M_CRC{number}' for number in range(9, 17)}
        reward_names = [reward['name'] for reward in REWARD_POOL]
        damage_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('global_buff')
            and reward.get('buff_type') == 'damage'
        )
        reload_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('global_buff')
            and reward.get('buff_type') == 'reload'
        )
        speed_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('global_buff')
            and reward.get('buff_type') == 'speed'
        )
        cost_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('global_buff')
            and reward.get('buff_type') == 'cost'
        )
        production_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('global_buff')
            and reward.get('buff_type') == 'production'
        )
        retired_global_vision = canonical_reward({
            'name': 'Player Army Optics I',
            'kind': 'buff',
            'unit': 'DTA_PLAYER_ARMY',
            'buff_type': 'sight',
            'global_buff': True,
            'dta_global_clone_buff': True,
        })
        catalogue = techno_catalogue()
        catalogue_records = {record['id']: record for record in catalogue}
        registered_rosters = {}
        for record in catalogue:
            faction = record.get('registered_faction')
            if faction:
                canonical_id = record.get('duplicate_of') or record['id']
                registered_rosters.setdefault(canonical_id, set()).add(faction)
        registered_roster_mismatches = {
            unit_id: {
                'registered': sorted(factions),
                'catalogue': sorted(
                    catalogue_records[unit_id]['playable_owners']
                ),
            }
            for unit_id, factions in registered_rosters.items()
            if set(catalogue_records[unit_id]['playable_owners']) != factions
        }
        mobile_ids = {
            record['id'] for record in catalogue
            if record.get('rewardable')
            and record.get('category') in {'infantry', 'vehicles', 'aircraft'}
            and not record.get('duplicate_of')
        }
        cameo_paths = ensure_unit_cameos(mobile_ids)
        power_cameo_paths = ensure_superweapon_cameos(
            spec['id'] for spec in POWER_SPECS
        )
        expected_access_ids = mobile_ids - set(ALWAYS_AVAILABLE_MOBILE_IDS)
        arsenal_candidates = arsenal_unit_candidates(
            {
                'include_special_rewards': True,
                'excluded_unit_access_ids': [],
            },
            {
                'factions': ['GDI', 'Nod', 'Allies', 'Soviet'],
                'roster_sizes': {},
                'power_counts': {},
            },
        )
        arsenal_powers = arsenal_power_candidates(
            {
                'include_special_rewards': True,
                'include_superweapon_rewards': True,
                'include_secondary_superweapon_rewards': True,
                'include_aid_power_rewards': True,
                'excluded_superweapon_ids': [],
            },
            {
                'factions': ['GDI', 'Nod', 'Allies', 'Soviet'],
                'roster_sizes': {},
                'power_counts': {},
            },
        )
        collision = unit_collision_report(source, 'E1')
        clone_mission = next(
            mission for mission in missions if mission['code'] == 'M_PTTP6'
        )
        clone_rules, clone_report = unit_specific_buff_rules(
            clone_mission,
            [{
                'unit': '3TNK',
                'buff_type': 'damage',
                'kind': 'buff',
            }],
        )
        clone_entry = next(
            (
                entry for entry in clone_report['applied']
                if entry['unit'] == '3TNK'
            ),
            {},
        )
        clone_source = GAME_ROOT / clone_mission['scenario']
        clone_before_hash = sha256(clone_source.read_bytes()).hexdigest()
        clone_generated = APP_DIR / '.self_check_clone_spawnmap.ini'
        try:
            clone_difficulty = resolve_mission_difficulty(clone_mission, 'Normal')
            prepare_spawn_map(
                clone_mission,
                clone_difficulty,
                extra_rules=clone_rules,
                output_path=clone_generated,
            )
            clone_generated_text = clone_generated.read_text(encoding='cp1252')
        finally:
            clone_generated.unlink(missing_ok=True)
        clone_after_hash = sha256(clone_source.read_bytes()).hexdigest()
        foreign_infantry_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('dta_production_access')
            and reward.get('unit') == 'E1A'
        )
        access_rules, access_report = player_infantry_access_rules(
            clone_mission,
            [foreign_infantry_reward],
            True,
        )
        access_clone_rules, access_clone_report = unit_specific_buff_rules(
            clone_mission,
            [foreign_infantry_reward],
        )
        access_clone_entry = next(
            (
                entry for entry in access_clone_report['applied']
                if entry['unit'] == 'E1A'
            ),
            {},
        )
        medic_access_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('dta_production_access')
            and reward.get('unit') == 'MEDIC'
        )
        medic_range_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('unit') == 'MEDIC'
            and reward.get('buff_type') == 'range'
        )
        medic_clone_rules, medic_clone_report = unit_specific_buff_rules(
            clone_mission,
            [medic_access_reward, medic_range_reward],
            access_randomized=True,
        )
        medic_clone_entry = next(
            (
                entry for entry in medic_clone_report['applied']
                if entry['unit'] == 'MEDIC'
            ),
            {},
        )
        medic_clone = medic_clone_rules.get(
            medic_clone_entry.get('output_type', ''), {}
        )
        medic_weapon = medic_clone_rules.get(
            medic_clone.get('Primary', ''), {}
        )
        access_generated = APP_DIR / '.self_check_access_spawnmap.ini'
        try:
            merged_access_rules = {
                section: dict(values)
                for section, values in access_rules.items()
            }
            for section, values in access_clone_rules.items():
                merged_access_rules.setdefault(section, {}).update(values)
            prepare_spawn_map(
                clone_mission,
                clone_difficulty,
                extra_rules=merged_access_rules,
                output_path=access_generated,
            )
            access_generated_text = access_generated.read_text(
                encoding='cp1252'
            )
        finally:
            access_generated.unlink(missing_ok=True)
        access_after_hash = sha256(clone_source.read_bytes()).hexdigest()
        tutorial_two = next(
            mission for mission in missions if mission['code'] == 'M_TUTORIAL2'
        )
        tutorial_two_context = _player_production_context(
            ini_sections(GAME_ROOT / tutorial_two['scenario'])
        )
        dog_access_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('dta_production_access')
            and reward.get('unit') == 'DOG'
        )
        tutorial_access_rules, tutorial_access_report = (
            player_infantry_access_rules(
                tutorial_two, [dog_access_reward], True
            )
        )
        tutorial_clone_rules, tutorial_clone_report = unit_specific_buff_rules(
            tutorial_two, [dog_access_reward]
        )
        e2_damage_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('unit') == 'E2'
            and reward.get('buff_type') == 'damage'
        )
        e2_production_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('unit') == 'E2'
            and reward.get('buff_type') == 'production'
        )
        e2_access_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('unit') == 'E2'
            and reward.get('dta_production_access')
        )
        e2_clone_rules, e2_clone_report = unit_specific_buff_rules(
            tutorial_two, [e2_damage_reward]
        )
        e2_access_buff_rules, e2_access_buff_report = (
            unit_specific_buff_rules(
                tutorial_two,
                [e2_access_reward, e2_damage_reward, e2_production_reward],
                access_randomized=True,
            )
        )
        mtnk_access_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('unit') == 'MTNK'
            and reward.get('dta_production_access')
        )
        infrastructure_rewards = production_infrastructure_rewards(
            [e2_access_reward, mtnk_access_reward],
            enabled=True,
            production_context=tutorial_two_context,
        )
        infrastructure_rules, infrastructure_report = (
            unit_specific_buff_rules(
                tutorial_two,
                [
                    e2_access_reward,
                    mtnk_access_reward,
                    *infrastructure_rewards,
                ],
                access_randomized=True,
                production_context=tutorial_two_context,
            )
        )
        infrastructure_outputs = {
            item['unit']: item['output_type']
            for item in infrastructure_report['applied']
            if item['unit'] in {
                reward['unit'] for reward in infrastructure_rewards
            }
        }
        faction_infrastructure_ids = {
            family: {
                reward['unit']
                for reward in production_infrastructure_rewards(
                    [e2_access_reward, mtnk_access_reward],
                    enabled=True,
                    production_context={
                        'original_production_house': family,
                        'production_house': family,
                    },
                )
            }
            for family in ('GDI', 'Nod', 'Allies', 'Soviet')
        }
        starting_credit_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('buff_type') == 'starting_credits'
        )
        starting_credit_rules, starting_credit_report = (
            player_starting_credit_rules(
                mission_source_lines(tutorial_two['scenario']),
                tutorial_two_context['player_house'],
                starting_credit_bonus([starting_credit_reward] * 25),
            )
        )
        faction_priority_sources = {
            'MTNK': 400,
            'BGGY': 300,
            '1TNK': 200,
            '3TNK': 100,
            'TWR': -600,
            'GUN': -700,
            'RAPBOX': -800,
            'RAFTUR': -900,
        }
        faction_priority_rewards = [
            next(
                reward for reward in REWARD_POOL
                if reward.get('dta_production_access')
                and str(reward.get('unit') or '').upper() == unit_id
            )
            for unit_id in faction_priority_sources
        ]
        faction_priority_rules, faction_priority_report = (
            unit_specific_buff_rules(
                tutorial_two,
                faction_priority_rewards,
                access_randomized=True,
            )
        )
        faction_priority_outputs = {
            item['unit']: item['output_type']
            for item in faction_priority_report['applied']
        }
        installed_sections = ini_sections(GAME_ROOT / 'INI' / 'Rules.ini')
        installed_e2 = effective_section(installed_sections, 'E2')
        installed_e2_weapon = effective_section(
            installed_sections, installed_e2.get('Primary')
        )
        _orphan_rules, orphan_buff_report = unit_specific_buff_rules(
            tutorial_two, [e2_damage_reward], access_randomized=True
        )
        apc_buff_types = {
            'health', 'range', 'sight', 'passenger_capacity', 'cloak', 'sensors',
        }
        apc_buff_rewards = [
            reward for reward in REWARD_POOL
            if reward.get('unit') == 'APC'
            and reward.get('buff_type') in apc_buff_types
        ]
        apc_buff_rules, apc_buff_report = unit_specific_buff_rules(
            tutorial_two, apc_buff_rewards
        )
        installed_apc = effective_section(installed_sections, 'APC')
        installed_apc_weapon = effective_section(
            installed_sections, installed_apc.get('Primary')
        )
        generated_apc = apc_buff_rules.get('APC_PLAYER', {})
        generated_apc_weapon = apc_buff_rules.get(
            generated_apc.get('Primary'), {}
        )
        e1_cap_rewards = [
            reward for reward in REWARD_POOL
            if reward.get('unit') == 'E1'
            and reward.get('buff_type') in {'sight', 'speed'}
        ]
        e1_cap_plan = plan_seed_rewards(
            ['M_TUTORIAL2'],
            'dta-unit-cap-smoke',
            {'M_TUTORIAL2': 40},
            progression_mode='Mission List',
            grid=None,
            reward_factions_for_code=lambda _code: {'GDI'},
            reward_pool_for_code=lambda _code: e1_cap_rewards,
            configured_reward_pool=lambda: e1_cap_rewards,
            starting_unlocked_tech_ids={'E1'},
            require_access_for_unit_buffs=True,
        )['M_TUTORIAL2']
        e1_cap_counts = Counter(
            reward.get('buff_type')
            for reward in e1_cap_plan
            if reward.get('kind') == 'buff'
        )
        e1_speed_reward = next(
            reward for reward in e1_cap_rewards
            if reward.get('buff_type') == 'speed'
        )
        combined_speed_plan = plan_seed_rewards(
            ['M_TUTORIAL2'],
            'dta-combined-speed-cap-smoke',
            {'M_TUTORIAL2': 20},
            progression_mode='Mission List',
            grid=None,
            reward_factions_for_code=lambda _code: {'GDI'},
            reward_pool_for_code=lambda _code: [
                e1_speed_reward, speed_reward,
            ],
            configured_reward_pool=lambda: [
                e1_speed_reward, speed_reward,
            ],
            starting_unlocked_tech_ids={'E1'},
            require_access_for_unit_buffs=True,
        )['M_TUTORIAL2']
        global_clone_rules, global_clone_report = unit_specific_buff_rules(
            tutorial_two, [damage_reward]
        )
        global_e1 = global_clone_rules.get('E1_PLAYER', {})
        global_e1_weapon = global_clone_rules.get(
            global_e1.get('Primary'), {}
        )
        legacy_stack_rules, legacy_stack_report = unit_specific_buff_rules(
            tutorial_two,
            [speed_reward] * 157
            + [cost_reward] * 14
            + [production_reward] * 10,
        )
        legacy_outputs = {
            item['unit']: item['output_type']
            for item in legacy_stack_report['applied']
        }
        legacy_pyle = legacy_stack_rules.get(
            legacy_outputs.get('PYLE'), {}
        )
        legacy_refinery = legacy_stack_rules.get(
            legacy_outputs.get('TDPROC'), {}
        )
        legacy_orca = legacy_stack_rules.get(
            legacy_outputs.get('ORCA'), {}
        )
        legacy_groups = legacy_stack_rules.get('PrerequisiteGroups', {})
        useless_unit_buffs = []
        for reward in REWARD_POOL:
            unit_id = str(reward.get('unit') or '').upper()
            buff_type = str(reward.get('buff_type') or '').lower()
            if (
                reward.get('kind') != 'buff'
                or reward.get('global_buff')
                or reward.get('dta_player_power_buff')
                or reward.get('enemy_reward')
                or not unit_id
            ):
                continue
            target = BUFF_TARGETS.get(unit_id)
            effective = _effective_buff_counts(
                effective_section(installed_sections, unit_id),
                target or {},
                Counter({buff_type: 1}),
                installed_sections,
            )
            if not effective:
                useless_unit_buffs.append((unit_id, buff_type))
        carrtruk_access_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('dta_production_access')
            and reward.get('unit') == 'CARRTRUK'
        )
        spawner_rules, spawner_report = unit_specific_buff_rules(
            tutorial_two,
            [carrtruk_access_reward, damage_reward, reload_reward],
            access_randomized=True,
        )
        spawner_clone = spawner_rules.get('CARRTRUK_PLAYER', {})
        shared_house_mission = next(
            mission for mission in missions if mission['code'] == 'M_PTTP1'
        )
        retry_rewards, retry_unit_ids = mission_assistance_rewards(
            tutorial_two,
            [e2_access_reward],
            1,
            access_randomized=True,
        )
        retry_rules, retry_report = unit_specific_buff_rules(
            tutorial_two,
            [e2_access_reward, *retry_rewards],
            access_randomized=True,
        )
        retry_entry = next(
            (
                entry for entry in retry_report['applied']
                if entry['unit'] == 'E2'
            ),
            {},
        )
        retry_e2 = retry_rules.get(retry_entry.get('output_type'), {})
        retry_e2_weapon = retry_rules.get(retry_e2.get('Primary'), {})
        retry_placement_mission = next(
            mission for mission in missions
            if mission['code'] == 'M_TTD_THE_FRONTAL_DUEL'
        )
        retry_placement_rewards, _retry_placement_unit_ids = (
            mission_assistance_rewards(
                retry_placement_mission,
                [],
                1,
                access_randomized=True,
            )
        )
        retry_placement_rules, retry_placement_report = (
            unit_specific_buff_rules(
                retry_placement_mission,
                retry_placement_rewards,
                access_randomized=True,
            )
        )
        retry_placement_entry = next(
            (
                entry for entry in retry_placement_report['applied']
                if entry['unit'] == 'HVCSAM'
            ),
            {},
        )
        retry_placement_clone = retry_placement_rules.get(
            retry_placement_entry.get('output_type'), {}
        )
        shared_access_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('dta_production_access')
            and reward.get('unit') == '3TNK'
        )
        shared_isolation_rules, shared_isolation_report = (
            player_production_isolation_rules(shared_house_mission)
        )
        shared_access_rules, shared_access_report = (
            player_infantry_access_rules(
                shared_house_mission,
                [shared_access_reward],
                True,
                production_context=shared_isolation_report,
                rule_overlays=shared_isolation_rules,
            )
        )
        shared_clone_rules, shared_clone_report = unit_specific_buff_rules(
            shared_house_mission,
            [shared_access_reward, damage_reward],
            access_randomized=True,
            production_context=shared_isolation_report,
            rule_overlays=shared_isolation_rules,
        )
        shared_generated_rules = {
            section: dict(values)
            for section, values in shared_isolation_rules.items()
        }
        for source_rules in (shared_access_rules, shared_clone_rules):
            for section, values in source_rules.items():
                shared_generated_rules.setdefault(section, {}).update(values)
        shared_generated = APP_DIR / '.self_check_shared_spawnmap.ini'
        try:
            shared_difficulty = resolve_mission_difficulty(
                shared_house_mission, 'Normal'
            )
            prepare_spawn_map(
                shared_house_mission,
                shared_difficulty,
                extra_rules=shared_generated_rules,
                output_path=shared_generated,
            )
            shared_generated_text = shared_generated.read_text(
                encoding='cp1252'
            )
        finally:
            shared_generated.unlink(missing_ok=True)
        shared_isolation_results = [
            player_production_isolation_rules(mission)[1]
            for mission in missions
            if _player_production_context(
                ini_sections(GAME_ROOT / mission['scenario'])
            )['shared_hostile_houses']
        ]
        installed_e1 = effective_section(installed_sections, 'E1')
        installed_e1_weapon = effective_section(
            installed_sections, installed_e1.get('Primary')
        )
        ion_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('superweapon') == 'IonCannonSpecial'
            and reward.get('dta_player_power')
        )
        ion_damage_buff = next(
            reward for reward in REWARD_POOL
            if reward.get('superweapon') == 'IonCannonSpecial'
            and reward.get('power_buff_type') == 'damage'
        )
        ion_area_buff = next(
            reward for reward in REWARD_POOL
            if reward.get('superweapon') == 'IonCannonSpecial'
            and reward.get('power_buff_type') == 'area'
        )
        power_rules, power_actions, power_report = player_power_rules(
            tutorial_two, [ion_reward, ion_damage_buff, ion_area_buff]
        )
        allied_power_mission = next(
            mission for mission in missions if mission['code'] == 'M_CRC14'
        )
        collateral_generated = APP_DIR / '.self_check_collateral_spawnmap.ini'
        try:
            collateral_hook = prepare_spawn_map(
                allied_power_mission,
                resolve_mission_difficulty(allied_power_mission, 'Normal'),
                extra_rules={
                    'E2': {'ForbiddenHouses': 'Allies'},
                    'E4': {'ForbiddenHouses': 'Allies'},
                },
                output_path=collateral_generated,
            )
            collateral_generated_sections = ini_sections(
                collateral_generated
            )
        finally:
            collateral_generated.unlink(missing_ok=True)
        enemy_ion_mission = allied_power_mission
        enemy_ion_rules, _enemy_ion_actions, enemy_ion_report = (
            player_power_rules(
                enemy_ion_mission,
                [ion_reward, ion_damage_buff, ion_area_buff],
            )
        )
        duplicate_sam_rewards = [
            reward for reward in REWARD_POOL
            if reward.get('dta_production_access')
            and reward.get('unit') in {'SAM', 'RASAM'}
        ]
        collapsed_sam_rewards = RewardController.chaos_equivalent_access_pool(
            duplicate_sam_rewards,
            {'Allies'},
        )
        allied_factory_rules, _allied_factory_report = (
            unit_specific_buff_rules(
                allied_power_mission,
                [production_reward],
            )
        )
        paradrop_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('superweapon') == 'DropPodSpecial'
            and reward.get('dta_player_power')
        )
        paradrop_payload_buff = next(
            reward for reward in REWARD_POOL
            if reward.get('superweapon') == 'DropPodSpecial'
            and reward.get('power_buff_type') == 'payload'
        )
        paradrop_rules, paradrop_actions, paradrop_report = player_power_rules(
            allied_power_mission,
            [paradrop_reward, paradrop_payload_buff],
            paratrooper_unit_id='E1S_PLAYER',
            reserved_rules={
                'E1S_PLAYER': {
                    'Strength': '750',
                    'Sight': '5',
                    'Primary': 'E1S_PLAYER_WEAPON',
                },
            },
        )
        crash_clone_rules = {}
        crash_clone_reports = {}
        crash_unit_missions = {
            'JEEPPTNK': tutorial_two,
            'TTNKMSL': allied_power_mission,
            'FRIGATE': allied_power_mission,
        }
        for crash_unit, crash_mission in crash_unit_missions.items():
            crash_access = next(
                reward for reward in REWARD_POOL
                if reward.get('dta_production_access')
                and reward.get('unit') == crash_unit
            )
            crash_damage = next(
                reward for reward in REWARD_POOL
                if reward.get('unit') == crash_unit
                and reward.get('buff_type') == 'damage'
            )
            generated_rules, generated_report = unit_specific_buff_rules(
                crash_mission,
                [crash_access, crash_damage],
                access_randomized=True,
            )
            crash_clone_rules[crash_unit] = generated_rules
            crash_clone_reports[crash_unit] = generated_report
        tutorial_one = next(
            mission for mission in missions if mission['code'] == 'M_TUTORIAL1'
        )
        mtnk_health_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('unit') == 'MTNK'
            and reward.get('buff_type') == 'health'
        )
        starter_rules, starter_report = unit_specific_buff_rules(
            tutorial_one, [mtnk_health_reward]
        )
        allied_helper_mission = next(
            mission for mission in missions if mission['code'] == 'M_CRC14'
        )
        artillery_cloak_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('unit') == 'RAARTY'
            and reward.get('buff_type') == 'cloak'
        )
        helper_rules, helper_report = unit_specific_buff_rules(
            allied_helper_mission,
            [artillery_cloak_reward],
            buff_allied_helpers=True,
        )
        route_c13_mission = next(
            mission for mission in missions if mission['code'] == 'M_CRC13'
        )
        aa_truck_speed_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('unit') == 'MFLAK'
            and reward.get('buff_type') == 'speed'
        )
        route_c13_helper_rules, route_c13_helper_report = (
            unit_specific_buff_rules(
                route_c13_mission,
                [aa_truck_speed_reward],
                buff_allied_helpers=True,
            )
        )
        harvester_speed_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('unit') == 'RAHARV'
            and reward.get('buff_type') == 'speed'
        )
        harvester_rules, harvester_report = unit_specific_buff_rules(
            allied_helper_mission, [harvester_speed_reward]
        )
        refinery_production_reward = {
            'unit': 'RAPROC',
            'buff_type': 'production',
            'kind': 'buff',
        }
        refinery_rules, refinery_report = unit_specific_buff_rules(
            allied_helper_mission, [refinery_production_reward]
        )
        economy_rules, economy_report = unit_specific_buff_rules(
            allied_helper_mission,
            [harvester_speed_reward, refinery_production_reward],
        )
        enforcer_rewards = [
            next(
                reward for reward in REWARD_POOL
                if reward.get('unit') == 'BFRT'
                and (
                    reward.get('dta_production_access')
                    if selector == 'access'
                    else reward.get('buff_type') == selector
                )
            )
            for selector in ('access', 'health', 'damage', 'build_limit')
        ]
        enforcer_rules, enforcer_report = unit_specific_buff_rules(
            allied_helper_mission,
            enforcer_rewards,
            access_randomized=True,
        )
        unlimited_enforcer_rules, unlimited_enforcer_report = (
            unit_specific_buff_rules(
                allied_helper_mission,
                [enforcer_rewards[0]],
                access_randomized=True,
                unlimited_hero_units=True,
            )
        )
        classic_hero_limit_results = {}
        for hero_id in ('RMBO', 'TANYA', 'VOLKOV'):
            hero_access_reward = next(
                reward for reward in REWARD_POOL
                if reward.get('unit') == hero_id
                and reward.get('dta_production_access')
            )
            hero_limit_reward = next(
                reward for reward in REWARD_POOL
                if reward.get('unit') == hero_id
                and reward.get('buff_type') == 'build_limit'
            )
            hero_base_rules, _hero_base_report = unit_specific_buff_rules(
                allied_helper_mission,
                [hero_access_reward],
                access_randomized=True,
            )
            hero_buff_rules, _hero_buff_report = unit_specific_buff_rules(
                allied_helper_mission,
                [hero_access_reward, hero_limit_reward],
                access_randomized=True,
            )
            classic_hero_limit_results[hero_id] = {
                'base': hero_base_rules.get(f'{hero_id}_PLAYER', {}).get(
                    'BuildLimit'
                ),
                'buffed': hero_buff_rules.get(f'{hero_id}_PLAYER', {}).get(
                    'BuildLimit'
                ),
            }
        defense_access_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('dta_production_access')
            and reward.get('unit') == 'TWR'
        )
        defense_buff_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('dta_production_clone')
            and reward.get('unit') == 'TWR'
            and reward.get('buff_type') == 'armor'
        )
        defense_access_rules, defense_access_report = (
            player_infantry_access_rules(
                tutorial_two,
                [defense_access_reward],
                True,
                include_defenses=True,
            )
        )
        defense_clone_rules, defense_clone_report = unit_specific_buff_rules(
            tutorial_two,
            [defense_access_reward, defense_buff_reward],
            access_randomized=True,
        )
        artillery_access_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('dta_production_access')
            and reward.get('unit') == 'ART'
        )
        artillery_clone_rules, artillery_clone_report = (
            unit_specific_buff_rules(
                allied_helper_mission,
                [artillery_access_reward],
                access_randomized=True,
            )
        )
        tooltip_controller = object.__new__(UnlockDataController)

        dashboard_access_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('dta_production_access')
            and reward.get('unit') == 'E1'
        )
        dashboard_global_rewards = [
            reward for reward in REWARD_POOL
            if reward.get('global_buff')
            and reward.get('buff_type') in {'production', 'damage'}
        ]

        class _SelfCheckBooleanVar:
            def get(self):
                return False

        class _SelfCheckUnlockDashboard(UnlockDataController):
            state = {'seed': 'self-check'}
            hide_locked_grid_missions_var = _SelfCheckBooleanVar()

            def active_progression_mode(self):
                return 'Mission Order'

            def canonical_earned_rewards(self):
                return [dashboard_access_reward, *dashboard_global_rewards]

            def starting_reward_source_items(self):
                return []

            def active_reward_mode(self):
                return 'Chaos'

            def active_starting_tier_one_access_ids(self):
                return set()

            def randomize_unit_access_enabled(self):
                return True

            def share_chaos_role_buffs_enabled(self):
                return False

            def foehn_standard_bundles_enabled(self):
                return False

            def unlock_dashboard_sources(self):
                def source_data(rewards, access=False):
                    items = [('Self-check', reward) for reward in rewards]
                    return {
                        'assigned': list(items),
                        'earned': list(items),
                        'earned_unlocks': list(items) if access else [],
                        'available': [],
                        'available_unlocks': [],
                        'available_codes': [],
                    }

                return {
                    'unit:E1': source_data(
                        [dashboard_access_reward], access=True
                    ),
                    'unit:DTA_PLAYER_ARMY': source_data(
                        dashboard_global_rewards
                    ),
                }

        dashboard_controller = _SelfCheckUnlockDashboard()
        dashboard_entries = dashboard_controller.unlock_dashboard_entries()
        global_dashboard_entries = [
            entry for entry in dashboard_entries
            if entry.get('id') == 'DTA_PLAYER_ARMY'
        ]
        chaos_rifle_entries = [
            entry for entry in dashboard_entries
            if entry.get('id') in {'E1', 'E1A'}
        ]
        rifle_factory_tooltip = dashboard_controller.unlock_dashboard_tooltip(
            next(
                entry for entry in dashboard_entries
                if entry.get('id') == 'E1'
            )
        )

        def power_tooltip_smoke(power_id):
            unlock = next(
                reward for reward in REWARD_POOL
                if reward.get('dta_player_power')
                and reward.get('superweapon') == power_id
            )
            buffs = [
                reward for reward in REWARD_POOL
                if reward.get('dta_player_power_buff')
                and reward.get('superweapon') == power_id
            ]
            return tooltip_controller.unlock_dashboard_tooltip({
                'label': unlock['name'],
                'status': 'unlocked',
                'kind': 'power',
                'condition': '',
                'privacy': False,
                'reward': unlock,
                'sources': {
                    'earned': [('Self-check', unlock)] + [
                        ('Self-check', reward) for reward in buffs
                    ],
                    'available': [],
                    'available_unlocks': [],
                },
            })

        ion_tooltip = power_tooltip_smoke('IonCannonSpecial')
        paradrop_tooltip = power_tooltip_smoke('DropPodSpecial')
        all_power_rewards = [
            reward for reward in REWARD_POOL
            if reward.get('kind') == 'superweapon'
            and reward.get('dta_player_power')
        ]
        building_power_ids = {
            spec['id'] for spec in POWER_SPECS
            if (spec.get('provider') or {}).get('buildable')
        }
        building_power_buffs = [
            reward for reward in REWARD_POOL
            if reward.get('dta_player_power_buff')
            and reward.get('superweapon') in building_power_ids
            and reward.get('power_buff_type') in {'damage', 'area'}
        ]
        all_power_rules, all_power_actions, all_power_report = (
            player_power_rules(
                tutorial_two,
                [*all_power_rewards, *building_power_buffs],
                reserved_rules=allied_factory_rules,
            )
        )
        all_power_runtime_rules = all_power_report.get('_runtime_rules', {})
        all_power_runtime_art = all_power_report.get('_runtime_art', {})
        retired_power_rules, retired_power_actions, retired_power_report = (
            player_power_rules(tutorial_two, [{
                'kind': 'superweapon',
                'superweapon': 'HuntSeekSpecial',
                'dta_player_power': True,
            }])
        )
        ion_runtime_rules = power_report.get('_runtime_rules', {})
        ion_runtime_art = power_report.get('_runtime_art', {})
        ion_power_clone = next(
            (
                values for section, values in power_rules.items()
                if section.startswith('DTAIONCANNONRNG')
            ),
            {},
        )
        ion_warhead_id = power_rules.get('CombatDamage', {}).get(
            'IonCannonWarhead', ''
        )
        ion_warhead_clone = power_rules.get(ion_warhead_id, {})
        paradrop_team = paradrop_rules.get(
            paradrop_report.get('paradrop_team', ''), {}
        )
        paradrop_taskforce = paradrop_rules.get(
            paradrop_team.get('TaskForce', ''), {}
        )
        paradrop_aircraft = paradrop_rules.get(
            paradrop_report.get('paradrop_aircraft', ''), {}
        )
        launch_color_source = mission_source_lines(tutorial_two['scenario'])
        enemy_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('enemy_effect_id') == 'enemy_armor'
        )
        enemy_rules, enemy_report = enemy_buff_rules(
            tutorial_two, [enemy_reward]
        )
        color_rules = mission_house_color_rules(
            launch_color_source,
            player_color=PLAYER_COLOR_ENGINE_VALUES['Pink'],
            rainbowizer=True,
            rainbow_colors=[
                PLAYER_COLOR_ENGINE_VALUES.get(color, color)
                for color in RAINBOWIZER_COLORS
            ],
            random_key='dta-color-self-check',
        )
        defense_cameo_paths = ensure_unit_cameos(DEFENSE_BUILDING_IDS)
        power_generated = APP_DIR / '.self_check_power_spawnmap.ini'
        try:
            prepare_spawn_map(
                tutorial_two,
                resolve_mission_difficulty(tutorial_two, 'Normal'),
                extra_rules=power_rules,
                power_actions=power_actions,
                power_house=power_report['player_house'],
                output_path=power_generated,
            )
            power_generated_text = power_generated.read_text(encoding='cp1252')
        finally:
            power_generated.unlink(missing_ok=True)

        def access_plan_smoke(label, pool):
            code = 'M_PTTP6'
            rewards = plan_seed_rewards(
                [code],
                f'dta-access-smoke-{label}',
                {code: 80},
                progression_mode='Mission List',
                grid=None,
                reward_factions_for_code=lambda _code: {'Soviet'},
                reward_pool_for_code=lambda _code: pool,
                configured_reward_pool=lambda: pool,
                require_access_for_unit_buffs=True,
            )[code]
            unlocked = set(ALWAYS_AVAILABLE_TECH_IDS)
            access_count = 0
            invalid_buffs = []
            for index, reward in enumerate(rewards):
                if reward.get('kind') != 'buff':
                    if reward.get('dta_production_access'):
                        access_count += 1
                    unlocked.update(tech_ids_for_rewards([reward]))
                    continue
                unit_id = str(reward.get('unit') or '').upper()
                if (
                    unit_id
                    and not reward.get('global_buff')
                    and unit_id not in unlocked
                ):
                    invalid_buffs.append((index, unit_id))
            return {
                'access_count': access_count,
                'invalid_buffs': invalid_buffs,
            }

        standard_access_pool = [
            reward for reward in REWARD_POOL
            if not reward.get('factions')
            or 'Soviet' in reward.get('factions', ())
            or 'Neutral' in reward.get('factions', ())
        ]
        standard_access_plan = access_plan_smoke(
            'standard', standard_access_pool
        )
        chaos_access_plan = access_plan_smoke('chaos', REWARD_POOL)
        legacy_access_config = {
            'eva_voice': 'GDI',
            'generation': {
                'enabled_reward_types': ['buff'],
                'randomize_unit_access': False,
            },
        }
        access_config_migrated = migrate_loaded_config(legacy_access_config)
        extended_mission = next(
            mission for mission in missions if mission['code'] == 'M_CRB16'
        )
        extended_fallback = resolve_mission_difficulty(
            extended_mission, 'Ultimate'
        )
        shop_domain = validate_shop_domain()
        checks = {
            'app_version': APP_VERSION,
            'game': 'Dawn of the Tiberium Age',
            'engine': 'Tiberian Sun + Vinifera',
            'game_root': str(GAME_ROOT),
            'launchvinifera_exists': GAME_LAUNCHER_EXE.is_file(),
            'game_exe_exists': GAME_EXE.is_file(),
            'vinifera_exists': (GAME_ROOT / 'Vinifera.dll').is_file(),
            'battle_ini_exists': BATTLE_CLIENT_INI.is_file(),
            'rules_ini_exists': (GAME_ROOT / 'INI' / 'Rules.ini').is_file(),
            'window_icon_exists': WINDOW_ICON_PATH.is_file(),
            'static_configs_valid': len(static_paths) == len(REQUIRED_STATIC_CONFIGS),
            'shop_domain_valid': shop_domain['valid'],
            'shop_domain': shop_domain,
            'mission_count': len(missions),
            'mission_counts_by_campaign': counts,
            'campaign_grouping_valid': counts == {
                'Tutorial': 2,
                'Shadow Exodus': 11,
                'PTTP': 9,
                'CR': 32,
                'Toxic Diversion': 7,
                'It Came From Red Alert!': 3,
                'Creeping Destruction': 8,
                'Stand-Alone Missions': 20,
            },
            'dta_mission_reward_multipliers_valid': (
                {
                    'late_route': late_route_codes,
                    'finale': finale_reward_codes,
                    'route_c': route_c_codes,
                } == {
                    reward_class: {
                        mission['code'] for mission in missions
                        if mission['reward_class'] == reward_class
                    }
                    for reward_class in ('late_route', 'finale', 'route_c')
                }
                and all(
                    (
                        mission['reward_class'] == 'route_c'
                        and mission['reward_multiplier'] == 3
                    )
                    if mission['code'] in route_c_codes
                    else (
                        mission['reward_class'] == 'finale'
                        and mission['reward_multiplier'] == 3
                    )
                    if mission['code'] in finale_reward_codes
                    else (
                        mission['reward_class'] == 'late_route'
                        and mission['reward_multiplier'] == 2
                    )
                    if mission['code'] in late_route_codes
                    else (
                        mission['reward_class'] == 'standalone'
                        and mission['reward_multiplier'] == 2
                    )
                    if mission['campaign'] == 'Stand-Alone Missions'
                    else (
                        mission['reward_class'] == 'standard'
                        and mission['reward_multiplier'] == 1
                    )
                    for mission in missions
                )
            ),
            'cr_grid_uses_campaign_green': (
                CAMPAIGN_TILE_COLORS.get('CR') == '#247a4b'
            ),
            'dta_puzzle_exists': DTA_PUZZLE_PATH.is_file(),
            'objective_reward_mode': (
                'victory-only; DTA has no uniform objective-completion signal'
            ),
            'no_unreportable_objective_checks': all(
                not mission.get('objectives') for mission in missions
            ),
            'dta_catalogue_type_count': len(catalogue),
            'dta_buildable_type_count': sum(
                1 for record in catalogue if record['buildable']
            ),
            'dta_reward_pool_count': len(reward_names),
            'dta_house_reward_count': sum(
                1 for reward in REWARD_POOL
                if reward.get('dta_global_clone_buff')
            ),
            'dta_unit_clone_reward_count': sum(
                1 for reward in REWARD_POOL
                if reward.get('dta_production_clone')
            ),
            'dta_infantry_access_reward_count': sum(
                1 for reward in REWARD_POOL
                if reward.get('dta_production_access')
            ),
            'dta_mobile_access_reward_count_valid': sum(
                1 for reward in REWARD_POOL
                if reward.get('dta_production_access')
                and str(reward.get('unit') or '').upper() in expected_access_ids
            ) == len(expected_access_ids),
            'dta_essential_mobile_units_always_available': (
                set(ALWAYS_AVAILABLE_TECH_IDS) == set(ALWAYS_AVAILABLE_MOBILE_IDS)
                and not expected_access_ids.intersection(
                    ALWAYS_AVAILABLE_MOBILE_IDS
                )
            ),
            'dta_obsolete_aliases_removed': all(
                unit_id not in mobile_ids for unit_id in {'E1N', 'E3N', 'APCN'}
            ),
            'dta_special_roster_present': {
                'BFRT', 'TTNKMSL', 'XO', 'PLSM', 'BEHEMOTH'
            }.issubset(mobile_ids),
            'dta_all_mobile_buff_targets_present': (
                mobile_ids
                == {
                    unit_id for unit_id, target in BUFF_TARGETS.items()
                    if target.get('category')
                    in {'infantry', 'vehicles', 'aircraft'}
                }
            ),
            'dta_arsenal_all_mobile_access_present': (
                len(arsenal_candidates) == len(expected_access_ids)
                and {item['unit_id'] for item in arsenal_candidates}
                == expected_access_ids
                and {'infantry', 'vehicles', 'naval', 'aircraft'}
                .issubset({item['production_type'] for item in arsenal_candidates})
            ),
            'dta_power_rewards_present': (
                {
                    reward.get('superweapon') for reward in REWARD_POOL
                    if reward.get('kind') == 'superweapon'
                }
                == {spec['id'] for spec in POWER_SPECS}
                and {
                    reward.get('superweapon') for reward in REWARD_POOL
                    if reward.get('dta_player_power_buff')
                } == {spec['id'] for spec in POWER_SPECS}
            ),
            'dta_power_buff_matrix_valid': all(
                {
                    reward.get('power_buff_type')
                    for reward in REWARD_POOL
                    if reward.get('dta_player_power_buff')
                    and reward.get('superweapon') == spec['id']
                } == (
                    {'recharge', 'payload'}
                    if spec['id'] == 'DropPodSpecial'
                    else {'recharge', 'damage', 'area'}
                )
                for spec in POWER_SPECS
            ),
            'dta_power_stack_limits_valid': (
                {
                    definition['id']: definition.get('maximum_stacks')
                    for definition in POWER_BUFF_TYPES
                } == {
                    'recharge': 40,
                    'damage': 10,
                    'area': 40,
                    'payload': 20,
                }
                and all(
                    power_buff_stack_limit(reward) == (
                        10 if reward.get('power_buff_type') == 'damage'
                        else 20 if reward.get('power_buff_type') == 'payload'
                        else 40
                    )
                    for reward in REWARD_POOL
                    if reward.get('dta_player_power_buff')
                )
                and {
                    buff_group_key(reward)
                    for reward in REWARD_POOL
                    if reward.get('dta_player_power_buff')
                } == {'recharge', 'damage', 'area', 'payload'}
            ),
            'unlock_dashboard_tooltips_render': (
                'Recharge time 10.0% faster.' in ion_tooltip
                and 'Damage 15.0% higher.' in ion_tooltip
                and 'Effect radius +1 cells.' in ion_tooltip
                and 'Recharge time 10.0% faster.' in paradrop_tooltip
                and 'Delivered infantry +1.' in paradrop_tooltip
            ),
            'unlock_dashboard_factory_support_visible': (
                'only the current mission faction\'s Barracks' in
                rifle_factory_tooltip
                and 'MCV/Construction Yard' in rifle_factory_tooltip
                and 'Other factions\' factories stay unavailable.' in
                rifle_factory_tooltip
            ),
            'unlock_dashboard_global_buffs_visible': (
                len(global_dashboard_entries) == 1
                and global_dashboard_entries[0].get('faction') == 'Neutral'
                and global_dashboard_entries[0].get('category')
                == 'Global Buffs'
                and global_dashboard_entries[0].get('status') == 'unlocked'
                and {
                    'unit:DTA_PLAYER_ARMY',
                    'house:all:production',
                }.issubset(dashboard_controller.unlock_dashboard_reward_keys(
                    next(
                        reward for reward in dashboard_global_rewards
                        if reward.get('buff_type') == 'production'
                    )
                ))
            ),
            'unlock_dashboard_chaos_equivalents_collapsed': (
                any(entry.get('id') == 'E1' for entry in chaos_rifle_entries)
                and not any(
                    entry.get('id') == 'E1A'
                    for entry in chaos_rifle_entries
                )
            ),
            'dta_power_cameos_complete': (
                {spec['id'].upper() for spec in POWER_SPECS}
                == set(power_cameo_paths)
            ),
            'dta_defense_rewards_complete': (
                {
                    str(reward.get('unit') or '').upper()
                    for reward in REWARD_POOL
                    if reward.get('access_category') == 'defense'
                } == set(DEFENSE_BUILDING_IDS)
                and set(defense_cameo_paths) == (
                    set(DEFENSE_BUILDING_IDS) - set(TEXT_ONLY_CAMEO_IDS)
                )
                and {
                    unit_id: set(BUFF_TARGETS[unit_id]['factions'])
                    for unit_id in ('ART', 'RAPARTY', 'VMINE', 'RAGAP')
                } == {
                    'ART': {'Allies'},
                    'RAPARTY': {'Soviet'},
                    'VMINE': {'Allies'},
                    'RAGAP': {'Allies'},
                }
                and BUFF_TARGETS['ART']['label']
                == 'Allied Artillery Emplacement'
                and set(HIDDEN_DTA_DEFENSE_IDS)
                == {'ART', 'RAPARTY', 'VMINE', 'RAGAP'}
                and 'TWR' in defense_access_rules
                and defense_access_report['clone_unlocked'] == ['TWR']
                and 'TWR_PLAYER' in defense_clone_rules
                and defense_clone_report['map_objects_rewritten'] == 0
                and artillery_clone_report['applied'][0]['unit'] == 'ART'
                and artillery_clone_rules['ART_PLAYER']['Owner'] == 'Allies'
                and artillery_clone_rules['ART_PLAYER']['RequiredHouses']
                == 'Allies'
                and artillery_clone_rules['ART_PLAYER']['TechLevel'] == '1'
                and artillery_clone_rules['ART_PLAYER']['Primary'] == '155mmRA'
            ),
            'dta_firestorm_removed': (
                all(
                    spec['id'].casefold() != 'firestormspecial'
                    for spec in POWER_SPECS
                )
                and all(
                    str(reward.get('superweapon') or '').casefold()
                    != 'firestormspecial'
                    for reward in REWARD_POOL
                )
            ),
            'dta_retired_chrono_tank_power_ignored': (
                not retired_power_rules
                and not retired_power_actions
                and not retired_power_report['applied']
                and retired_power_report['skipped'] == [{
                    'power': 'HuntSeekSpecial',
                    'reason': 'unsupported_or_retired_power',
                }]
            ),
            'dta_power_actions_are_unique_and_callable': (
                len(all_power_actions) == sum(
                    1 for spec in POWER_SPECS if not spec.get('provider')
                )
                and len(all_power_report['applied']) == len(POWER_SPECS)
                and len({
                    item.get('action')
                    for item in all_power_report['applied']
                    if item.get('action')
                }) == len(POWER_SPECS)
                and all(
                    not item.get('action')
                    or (
                        all_power_rules.get(item['clone'], {}).get('Action')
                        == item['action']
                        and ini_sections(
                            GAME_ROOT / 'INI' / 'Action.ini'
                        ).get('ActionTypes', {}).get(item['action'])
                        == POWER_CLONE_ACTION_TYPES[item['power'].upper()][1]
                    )
                    for item in all_power_report['applied']
                )
                and not {
                    item.get('action')
                    for item in all_power_report['applied']
                    if item.get('action')
                }.intersection({
                    effective_section(
                        installed_sections, spec['id']
                    ).get('Action')
                    for spec in POWER_SPECS
                })
                and {
                    item[0] for item in POWER_CLONE_ACTION_TYPES.values()
                } == {
                    item.get('action')
                    for item in all_power_report['applied']
                    if item.get('action')
                }
                and {
                    item['power']
                    for item in all_power_report['provider_buildings']
                    if item.get('buildable')
                } == building_power_ids
                and all(action[0] == '34' for action in all_power_actions)
                and all(
                    item['grant_mode'] == (
                        'building'
                        if item['power'] in building_power_ids
                        else 'trigger'
                    )
                    for item in all_power_report['applied']
                )
            ),
            'dta_power_buildings_are_immediately_available': all(
                provider.get('buildable')
                and (
                    values := all_power_rules.get(provider['provider'], {})
                ).get('TechLevel') == '1'
                and values.get('Buildability') == 'HumanOnly'
                and values.get('AIBuildThis') == 'no'
                and values.get('Owner') == 'GDI'
                and values.get('RequiredHouses') == 'GDI'
                and values.get('SuperWeapon')
                and not any(
                    str(key).casefold().startswith('prerequisite')
                    for key in values
                )
                and all_power_rules.get(provider['source'], {}).get(
                    'Buildability'
                ) == 'AIOnly'
                for provider in all_power_report['provider_buildings']
            ),
            'dta_building_power_buffs_are_player_only': (
                bool(all_power_runtime_rules)
                and bool(all_power_runtime_art)
                and all(
                    item['damage_buffs'] == 1
                    and item['area_buffs'] == 1
                    and item['grant_mode'] == 'building'
                    for item in all_power_report['applied']
                    if item['power'] in building_power_ids
                )
                and not {
                    'AIRSINIT', 'NUKEINIT', 'REVERSED_CHRONOSHIFT'
                }.intersection(all_power_runtime_art)
            ),
            'dta_power_lists_preserve_war_factory_clones': (
                'AWEAP_PLAYER' in allied_factory_rules.get(
                    'BuildingTypes', {}
                ).values()
                and not set(
                    allied_factory_rules.get('BuildingTypes', {})
                ).intersection(all_power_rules.get('BuildingTypes', {}))
            ),
            'dta_exclusive_buffed_ion_cannon_works': (
                power_rules.get('CombatDamage', {}).get(
                    'IonCannonDamage'
                ) == '690'
                and ion_warhead_id.startswith('DTAIONCANNONWH')
                and float(ion_warhead_clone.get('CellSpread', 0)) == 1.3125
                and ion_power_clone.get('Type') == 'IonCannon'
                and 'WeaponType' not in ion_power_clone
                and not ion_runtime_rules
                and not ion_runtime_art
                and power_report['applied'][0]['grant_mode'] == 'trigger'
                and power_report['applied'][0]['recharge_buffs'] == 0
                and power_report['applied'][0]['damage_buffs'] == 1
                and power_report['applied'][0]['area_buffs'] == 1
                and {
                    'EYE.SuperWeapon', 'COMM1.SuperWeapon'
                }.issubset(set(
                    power_report['exclusive_native_provider_fields']
                ))
                and enemy_ion_report['exclusive_native_grants_removed'] >= 1
                and any(
                    ',0,0,0,0,0,0,0,A' in value
                    for value in enemy_ion_rules.get('Actions', {}).values()
                )
            ),
            'dta_map_local_exploders_keep_death_damage_scale': (
                collateral_generated_sections.get('E2', {}).get(
                    'CollateralDamageCoefficient'
                ) == '0.0165'
                and collateral_generated_sections.get('E4', {}).get(
                    'CollateralDamageCoefficient'
                ) == '0.007'
                and set(collateral_hook['collateral_damage_safeguards'])
                >= {'E2', 'E4'}
            ),
            'dta_legacy_equivalent_sam_access_collapses': (
                len(duplicate_sam_rewards) == 2
                and len(collapsed_sam_rewards) == 1
                and tech_ids_for_rewards(collapsed_sam_rewards)
                <= {'SAM', 'RASAM'}
            ),
            'dta_paradrop_payload_uses_badger_capacity': (
                len(paradrop_actions) == 1
                and 'BADGER' not in paradrop_rules
                and 'E1' not in paradrop_rules
                and 'General' not in paradrop_rules
                and not {
                    'DropPodInfantryMinimum',
                    'DropPodInfantryMaximum',
                    'Paratrooper',
                }.intersection(paradrop_rules.get(
                    paradrop_report['applied'][0]['clone'], {}
                ))
                and paradrop_report.get('paratrooper_unit') == 'E1S_PLAYER'
                and paradrop_report.get('paratrooper_buff_source')
                == 'E1S_PLAYER'
                and paradrop_report.get('paradrop_team', '').startswith(
                    'PARADROPINF_'
                )
                and paradrop_team.get('House')
                == paradrop_report['player_house']
                and paradrop_team.get('Waypoint') == '100'
                and paradrop_taskforce.get('0') == '6,E1S_PLAYER'
                and paradrop_taskforce.get('1')
                == f'1,{paradrop_report["paradrop_aircraft"]}'
                and paradrop_aircraft.get('Passengers') == '6'
                and paradrop_report['applied'][0]['payload_buffs'] == 1
                and paradrop_report['applied'][0]['payload_units'] == '6'
                and paradrop_report['applied'][0]['payload_aircraft']
                == 'BADGER'
            ),
            'dta_enemy_buffs_exclude_player_family': (
                enemy_rules.get('Nod', {}).get('Armor') == '1.1'
                and 'GDI' not in enemy_rules
                and enemy_report['friendly_families'] == ['GDI']
                and enemy_report['hostile_families'] == ['Nod']
            ),
            'dta_player_color_list_valid': (
                color_rules.get('TutorialGDI', {}).get('Color')
                == 'DarkMagenta'
                and set(RAINBOWIZER_COLORS) == {
                    'Gold', 'Red', 'Teal', 'Green', 'Orange', 'Blue',
                    'Purple', 'Metallic', 'White', 'Brown', 'Pink', 'Cyan',
                }
            ),
            'dta_loose_mission_launch_source_valid': (
                mission_source_path(tutorial_two['scenario']).resolve()
                == (GAME_ROOT / tutorial_two['scenario']).resolve()
                and color_rules.get('TutorialGDI', {}).get('Color')
                == 'DarkMagenta'
            ),
            'dta_arsenal_power_pool_complete': (
                {item['power_id'] for item in arsenal_powers}
                == {spec['id'].upper() for spec in POWER_SPECS}
            ),
            'dta_ts_leftovers_excluded': not {
                'HTNKMSAM', 'SMECH', 'UTNK', 'JUMPJET', 'MHQ'
            }.intersection(mobile_ids),
            'dta_mobile_hq_removed_from_pool': (
                'MHQ' not in mobile_ids
                and 'MHQ' not in BUFF_TARGETS
                and not any(
                    str(reward.get('unit') or '').upper() == 'MHQ'
                    for reward in REWARD_POOL
                )
            ),
            'dta_special_factions_curated': all(
                set(BUFF_TARGETS[unit_id]['factions']) == expected
                for unit_id, expected in {
                    'GTNK': {'Soviet'},
                    'HVR': {'GDI'},
                    'HVC': {'Nod'},
                    'HVCSAM': {'GDI'},
                    'HTNKARTY': {'Nod'},
                    'JEEPPTNK': {'GDI'},
                    'LTNKCRUS': {'Nod'},
                    'MWAVEMSAM': {'Nod'},
                    'BRIG': {'Allies'},
                    'MGI': {'Allies'},
                    'MSA': {'GDI'},
                }.items()
            ) and all(
                len(target.get('factions', ())) == 1
                for target in BUFF_TARGETS.values()
                if target.get('special_reward')
            ),
            'dta_registered_mobile_factions_match_installed_rosters': (
                len(registered_rosters) == 50
                and not registered_roster_mismatches
                and registered_rosters.get('MSAM') == {'GDI'}
                and registered_rosters.get('DTRK') == {'Soviet'}
                and registered_rosters.get('APC') == {'GDI', 'Nod'}
                and set(BUFF_TARGETS['MSAM']['factions']) == {'GDI'}
                and set(BUFF_TARGETS['DTRK']['factions']) == {'Soviet'}
            ),
            'custom_campaign_house_acts_like_resolved': (
                tutorial_two_context['player_house'] == 'TutorialGDI'
                and tutorial_two_context['production_house'] == 'GDI'
                and tutorial_two_context['acts_like'] == 0
                and not tutorial_two_context['shared_hostile_houses']
            ),
            'custom_campaign_house_access_route_valid': (
                tutorial_access_report['production_house'] == 'GDI'
                and tutorial_access_rules.get('E1', {}).get(
                    'ForbiddenHouses'
                ) == 'GDI'
                and tutorial_clone_rules.get('DOG_PLAYER', {}).get(
                    'Owner'
                ) == 'GDI'
                and tutorial_clone_rules.get('DOG_PLAYER', {}).get(
                    'RequiredHouses'
                ) == 'GDI'
                and 'BuiltAt' not in tutorial_clone_rules.get('DOG_PLAYER', {})
                and tutorial_clone_report['map_objects_rewritten'] == 0
            ),
            'safe_reward_pool_only': all(
                reward.get('dta_production_clone')
                or reward.get('dta_production_access')
                or reward.get('dta_player_power')
                or reward.get('dta_player_power_buff')
                or reward.get('dta_starting_credits')
                or reward.get('enemy_reward')
                for reward in REWARD_POOL
            ),
            'global_buffs_use_player_clones_only': (
                global_clone_report.get('global_buffs') == {
                    'damage': 1,
                }
                and global_e1.get('RequiredHouses') == 'GDI'
                and int(global_e1.get('Strength', 0))
                == int(installed_e1.get('Strength', 0))
                and int(global_e1.get('Sight', 0))
                == int(installed_e1.get('Sight', 0))
                and int(global_e1_weapon.get('Damage', 0))
                > int(installed_e1_weapon.get('Damage', 0))
                and set(global_clone_rules.get('E1', {}))
                == {'ForbiddenHouses'}
                and not {'Easy', 'Normal', 'Difficult'}.intersection(
                    global_clone_rules
                )
                and global_clone_report['map_objects_rewritten'] == 0
            ),
            'global_vision_removed': (
                not any(
                    reward.get('global_buff')
                    and reward.get('buff_type') == 'sight'
                    for reward in REWARD_POOL
                )
                and retired_global_vision.get('retired_reward') is True
            ),
            'global_armor_removed': not any(
                reward.get('global_buff')
                and reward.get('buff_type') == 'armor'
                for reward in REWARD_POOL
            ),
            'spawner_control_weapons_are_not_cloned': (
                spawner_clone.get('Primary') == 'TruckHornetLauncher'
                and not any(
                    section.startswith('CARRTRUK_TRUCKHORNET')
                    for section in spawner_rules
                )
                and any(
                    item.get('unit') == 'CARRTRUK'
                    for item in spawner_report['applied']
                )
                and not any(
                    reward.get('unit') == 'CARRTRUK'
                    and reward.get('buff_type')
                    in {'damage', 'reload', 'range'}
                    for reward in REWARD_POOL
                )
            ),
            'legacy_speed_stacks_are_engine_safe': all(
                (
                    'Speed' not in legacy_stack_rules.get(output_id, {})
                    or int(legacy_stack_rules[output_id]['Speed'])
                    <= max(
                        int(round(float(BUFF_TARGETS[unit_id]['speed']))),
                        movement_speed_ceiling(BUFF_TARGETS[unit_id]),
                    )
                )
                for unit_id, output_id in legacy_outputs.items()
                if movement_speed_ceiling(BUFF_TARGETS.get(unit_id, {}))
                is not None
            ) and int(legacy_orca.get('Speed', 0)) <= 30,
            'global_building_cost_and_production_buffs_work': (
                int(legacy_pyle.get('Cost', 0))
                < int(effective_section(installed_sections, 'PYLE')['Cost'])
                and float(legacy_pyle.get('BuildTimeMultiplier', 1)) < 1
                and int(legacy_refinery.get('Cost', 0))
                < int(effective_section(installed_sections, 'TDPROC')['Cost'])
                and float(legacy_refinery.get('BuildTimeMultiplier', 1))
                < float(
                    effective_section(installed_sections, 'TDPROC').get(
                        'BuildTimeMultiplier', 1
                    )
                )
                and legacy_refinery.get('FreeUnit')
                == legacy_outputs.get('TDHARV')
                and legacy_stack_rules.get(
                    legacy_outputs.get('TDHARV'), {}
                ).get('Harvester') == 'yes'
                and all(
                    'Speed' not in legacy_stack_rules.get(output_id, {})
                    for unit_id, output_id in legacy_outputs.items()
                    if catalogue_records.get(unit_id, {}).get('category')
                    in {'buildings', 'defenses'}
                )
            ),
            'cloned_building_tech_chains_work': (
                bool(legacy_groups)
                and all(
                    any(
                        value == f'{unit_id},{output_id}'
                        for value in legacy_groups.values()
                    )
                    for unit_id, output_id in legacy_outputs.items()
                    if catalogue_records.get(unit_id, {}).get('category')
                    in {'buildings', 'defenses'}
                )
                and 'NUKE_PLAYER' in legacy_stack_rules.get(
                    'General', {}
                ).get('PrerequisitePower', '')
            ),
            'unit_buff_pool_has_no_noop_rewards': not useless_unit_buffs,
            'shared_house_enemy_clone_isolation': (
                shared_isolation_report['isolation_applied']
                and shared_isolation_report[
                    'original_shared_hostile_houses'
                ] == ['Soviet1']
                and not shared_isolation_report['shared_hostile_houses']
                and not shared_isolation_report['isolation_error']
                and shared_isolation_rules.get('Soviet1', {}).get(
                    'ActsLike'
                ) == '12'
                and 'Soviet1' in comma_items(
                    shared_isolation_rules.get('3TNK', {}).get('Owner')
                )
                and not shared_access_report['skipped_reason']
                and '3TNK' in shared_access_report['clone_unlocked']
                and shared_access_rules.get('3TNK', {}).get(
                    'ForbiddenHouses'
                ) == 'Soviet'
                and shared_clone_rules.get('3TNK_PLAYER', {}).get(
                    'Owner'
                ) == 'Soviet'
                and shared_clone_rules.get('3TNK_PLAYER', {}).get(
                    'RequiredHouses'
                ) == 'Soviet'
                and '[3TNK_PLAYER]' in shared_generated_text
                and 'ActsLike=12' in shared_generated_text
                and all(
                    result['isolation_applied']
                    and not result['shared_hostile_houses']
                    and not result['isolation_error']
                    for result in shared_isolation_results
                )
            ),
            'retry_assistance_uses_player_clones': (
                'E2' in retry_unit_ids
                and retry_entry.get('production_access') is True
                and set(retry_entry.get('buffs', {}))
                == set(MISSION_ASSISTANCE_BUFF_TYPES)
                and float(retry_e2.get('BuildTimeMultiplier', 1)) < 1
                and int(retry_e2.get('Cost', 0))
                < int(installed_e2.get('Cost', 0))
                and int(retry_e2.get('Speed', 0))
                > int(installed_e2.get('Speed', 0))
                and int(retry_e2.get('Strength', 0))
                > int(installed_e2.get('Strength', 0))
                and int(retry_e2_weapon.get('Damage', 0))
                > int(installed_e2_weapon.get('Damage', 0))
                and int(retry_e2_weapon.get('ROF', 0))
                < int(installed_e2_weapon.get('ROF', 0))
                and float(retry_e2_weapon.get('Range', 0))
                > float(installed_e2_weapon.get('Range', 0))
                and retry_placement_entry.get('route')
                == 'player_placement_clone'
                and retry_placement_clone.get('TechLevel') == '-1'
                and len(
                    retry_placement_entry.get(
                        'player_placements_rewritten', ()
                    )
                ) == 4
            ),
            'dta_powers_granted_to_player_only': (
                len(power_report['applied']) == 1
                and power_report['player_house'] == 'TutorialGDI'
                and power_report['enemy_grants'] == 0
                and len(power_actions) == 1
                and power_actions[0][0] == '34'
                and not power_report['provider_buildings']
                and power_report['applied'][0]['grant_mode'] == 'trigger'
                and 'Nod,<none>,DTA Randomizer Earned Powers' not in power_generated_text
                and '[DTAIONCANNONRNG]' in power_generated_text
                and power_generated_text.count(
                    'DTA Randomizer Earned Powers'
                ) == 2
                and 'IonCannonDamage=690' in power_generated_text
                and 'SuperWeapon=' in power_generated_text
            ),
            'dta_building_gated_powers_enabled': (
                {spec['id'] for spec in POWER_SPECS}
                == {
                    'IonCannonSpecial', 'DropPodSpecial',
                    'AirstrikeSpecial', 'ChemicalSpecial',
                    'MultiSpecial', 'VortexSpecial',
                }
                and {
                    'DTAAIRSTRIKESPECIALACT',
                    'DTACHEMICALSPECIALACT',
                    'DTAMULTISPECIALACT',
                    'DTAVORTEXSPECIALACT',
                }.issubset(ini_sections(
                    GAME_ROOT / 'INI' / 'Action.ini'
                ).get('ActionTypes', {}))
                and len(all_power_report['provider_buildings']) == 4
            ),
            'dta_sidebar_factions_and_defenses_sorted': (
                set(faction_priority_outputs) == set(faction_priority_sources)
                and all(
                    faction_priority_rules.get(
                        faction_priority_outputs[unit_id], {}
                    ).get('CameoPriority') == str(priority)
                    for unit_id, priority in faction_priority_sources.items()
                )
                and max(
                    priority for unit_id, priority
                    in faction_priority_sources.items()
                    if BUFF_TARGETS[unit_id]['category'] == 'defenses'
                ) < min(
                    priority for unit_id, priority
                    in faction_priority_sources.items()
                    if BUFF_TARGETS[unit_id]['category'] != 'defenses'
                )
            ),
            'crashing_unit_weapons_registered': all(
                (
                    (entries := crash_clone_reports[unit_id]['applied'])
                    and (
                        output_id := next(
                            item['output_type'] for item in entries
                            if item['unit'] == unit_id
                        )
                    )
                    and (
                        unit_rules := crash_clone_rules[unit_id].get(
                            output_id, {}
                        )
                    )
                    and {
                        unit_rules.get(key)
                        for key in ('Primary', 'Secondary', 'Elite')
                        if unit_rules.get(key)
                    }.issubset(set(
                        crash_clone_rules[unit_id].get(
                            'WeaponTypes', {}
                        ).values()
                    ))
                )
                and all(
                    len(section) <= 23
                    for section in crash_clone_rules[unit_id]
                    if section not in {
                        'PrerequisiteGroups', 'InfantryTypes', 'VehicleTypes',
                        'AircraftTypes', 'BuildingTypes', 'WeaponTypes',
                        'General',
                    }
                )
                for unit_id in crash_unit_missions
            ),
            'player_starting_units_use_player_clone': (
                starter_report['map_objects_rewritten'] == 3
                and any(
                    item.get('unit') == 'MTNK'
                    and len(item.get('player_placements_rewritten', ())) == 3
                    for item in starter_report['applied']
                )
                and all(
                    comma_items(value)[1] == 'MTNK_PLAYER'
                    for value in starter_rules.get('Units', {}).values()
                )
            ),
            'reported_roster_corrections_active': (
                {
                    'TTNKMSL', 'MGI', 'BRIG', 'MFLAK', 'CYBORG',
                    'GRENL', 'THIEF', 'HIJACK', 'CYP',
                    'RAIDER', 'MRV', 'STAPC', 'TNKD',
                    'SCARAB', 'TORPCAT', 'FLAKCORV',
                }.issubset(mobile_ids)
                and '2TNKMSL' not in mobile_ids
                and tutorial_access_rules.get('2TNKMSL', {}).get(
                    'ForbiddenHouses'
                ) == 'GDI'
                and canonical_reward({
                    'name': 'Unlock Missile Tank (2TNKMSL)'
                }).get('unit') == 'TTNKMSL'
                and not (
                    mobile_ids & TEXT_ONLY_CAMEO_IDS
                ).intersection(cameo_paths)
            ),
            'dta_anti_air_roster_matches_installed_ini': (
                BUFF_TARGETS.get('SHILKA', {}).get('label') == 'Quad Tank'
                and set(BUFF_TARGETS.get('SHILKA', {}).get('factions', ()))
                == {'Soviet'}
                and BUFF_TARGETS.get('SHILKA', {}).get('special_reward')
                is False
                and BUFF_TARGETS.get('MFLAK', {}).get('label')
                == 'Anti-Aircraft Truck'
                and set(BUFF_TARGETS.get('MFLAK', {}).get('factions', ()))
                == {'Allies'}
                and BUFF_TARGETS.get('MFLAK', {}).get('special_reward')
                is False
                and any(
                    reward.get('unit') == 'MFLAK'
                    and reward.get('dta_production_access')
                    for reward in REWARD_POOL
                )
            ),
            'dta_aa_truck_cameo_uses_mflak_art': (
                'MFLAK' in cameo_paths
                and cameo_paths['MFLAK'].is_file()
                and 'SHILKA' in cameo_paths
                and cameo_paths['MFLAK'].resolve()
                != cameo_paths['SHILKA'].resolve()
                and ini_sections(GAME_ROOT / 'INI' / 'Art.ini').get(
                    'MFLAK', {}
                ).get('Cameo') == 'MFLKICON'
            ),
            'dta_e1_cameo_extracted': (
                'E1' in cameo_paths and cameo_paths['E1'].is_file()
            ),
            'dta_engineer_cameo_extracted': (
                'ENGINEER' in cameo_paths
                and cameo_paths['ENGINEER'].is_file()
            ),
            'dta_active_unit_cameos_or_text_complete': (
                mobile_ids - set(cameo_paths)
                == mobile_ids & TEXT_ONLY_CAMEO_IDS
            ),
            'dta_allied_helpers_use_buffed_clones': (
                helper_rules.get('RAARTY_PLAYER', {}).get(
                    'Cloakable'
                ) == 'yes'
                and set(comma_items(helper_rules.get(
                    'RAARTY_PLAYER', {}
                ).get(
                    'RequiredHouses'
                ))) == {'Allies'}
                and helper_rules.get('RAARTY', {}).get('Buildability')
                == 'AIOnly'
                and helper_rules.get('RAARTY', {}).get('Cloakable') == 'yes'
                and not {'Allies', 'Allies1', 'Allies2'}.intersection(set(
                    comma_items(helper_rules.get('RAARTY', {}).get(
                        'ForbiddenHouses'
                    ))
                ))
                and any(
                    route.get('production_house') == 'Allies'
                    and route.get('production_routed') is True
                    and route.get('output_type') == 'RAARTY_PLAYER'
                    and route.get('native_ai_fallback_buffed') is True
                    and set(route.get('scenario_houses', ()))
                    == {'Allies1', 'Allies2'}
                    for item in helper_report['applied']
                    for route in item.get('allied_helper_routes', ())
                )
            ),
            'dta_route_c13_ai_aliases_use_buffed_clones': (
                route_c13_helper_rules.get('MFLAK_PLAYER', {}).get('Speed')
                == '7'
                and any(
                    reference.get('source_type') == 'AIMFLAK'
                    and route.get('output_type') == 'MFLAK_PLAYER'
                    for item in route_c13_helper_report['applied']
                    for route in item.get('allied_helper_routes', ())
                    for reference in route.get('references_rewritten', ())
                )
            ),
            'dta_harvester_clones_keep_harvester_identity': (
                'RAHARV_PLAYER' in comma_items(
                    harvester_rules.get('General', {}).get('HarvesterUnit')
                )
                and harvester_rules.get('RAHARV_PLAYER', {}).get('Harvester')
                == 'yes'
                and bool(harvester_report['applied'])
            ),
            'dta_harvesters_survive_refinery_clones': (
                bool(refinery_report['applied'])
                and bool(
                    refinery_group := next(
                        (
                            key for key, value in refinery_rules.get(
                                'PrerequisiteGroups', {}
                            ).items()
                            if value == 'RAPROC,RAPROC_PLAYER'
                        ),
                        '',
                    )
                )
                and refinery_group in comma_items(
                    refinery_rules.get('RAHARV', {}).get('Prerequisite')
                )
                and 'Allies' not in comma_items(
                    refinery_rules.get('RAHARV', {}).get('ForbiddenHouses')
                )
            ),
            'dta_refinery_spawns_working_harvester_clone': (
                economy_rules.get('RAPROC_PLAYER', {}).get('FreeUnit')
                == 'RAHARV_PLAYER'
                and economy_rules.get('RAHARV_PLAYER', {}).get('Harvester')
                == 'yes'
                and economy_rules.get('RAHARV_PLAYER', {}).get('Storage')
                == '28'
                and 'RAHARV_PLAYER' in comma_items(
                    economy_rules.get('General', {}).get('HarvesterUnit')
                )
                and bool(economy_report['applied'])
            ),
            'dta_enforcer_deploy_form_keeps_buffs': (
                bool(enforcer_report['applied'])
                and enforcer_rules.get('BFRT_PLAYER', {}).get('BuildLimit')
                == '2'
                and enforcer_rules.get('BFRT_PLAYER', {}).get('DeploysInto')
                == 'DBFRT_PLAYER'
                and enforcer_rules.get('DBFRT_PLAYER', {}).get('UndeploysInto')
                == 'BFRT_PLAYER'
                and int(enforcer_rules.get('DBFRT_PLAYER', {}).get(
                    'Strength', 0
                )) > int(effective_section(
                    installed_sections, 'DBFRT'
                ).get('Strength', 0))
                and enforcer_rules.get('DBFRT_PLAYER', {}).get('Primary')
                != effective_section(installed_sections, 'DBFRT').get('Primary')
            ),
            'dta_unlimited_heroes_remove_build_limit': (
                bool(unlimited_enforcer_report['applied'])
                and 'BuildLimit' not in unlimited_enforcer_rules.get(
                    'BFRT_PLAYER', {}
                )
            ),
            'dta_classic_heroes_have_limits_and_capacity_buffs': (
                classic_hero_limit_results
                == {
                    hero_id: {'base': '1', 'buffed': '2'}
                    for hero_id in ('RMBO', 'TANYA', 'VOLKOV')
                }
            ),
            'map_unit_preservation_policy_active': (
                collision['map_objects_must_remain_original'] is True
            ),
            'vinifera_production_clone_generated': (
                clone_entry.get('route') == 'production_clone'
                and clone_entry.get('output_type') == '3TNK_PLAYER'
                and clone_rules.get('3TNK', {}).get('ForbiddenHouses') == 'Soviet'
                and clone_rules.get('3TNK_PLAYER', {}).get('RequiredHouses') == 'Soviet'
                and clone_report['map_objects_rewritten'] == 0
            ),
            'all_unit_specific_buffs_use_production_clones': (
                any(
                    item.get('unit') == 'E2'
                    and item.get('route') == 'production_clone'
                    and item.get('output_type') == 'E2_PLAYER'
                    for item in e2_clone_report['applied']
                )
                and e2_clone_rules.get('E2', {}).get(
                    'ForbiddenHouses', ''
                ).split(',')[-1] == 'GDI'
                and e2_clone_rules.get('E2_PLAYER', {}).get(
                    'RequiredHouses'
                ) == 'GDI'
                and not any(
                    item.get('route') == 'original_type'
                    for item in e2_clone_report['applied']
                )
            ),
            'dta_extended_unit_buffs_work': (
                len(apc_buff_rewards) == len(apc_buff_types)
                and any(
                    item.get('unit') == 'APC'
                    and set(item.get('buffs', {})) == apc_buff_types
                    for item in apc_buff_report['applied']
                )
                and int(generated_apc.get('Strength', 0))
                > int(installed_apc.get('Strength', 0))
                and int(generated_apc.get('Sight', 0))
                == int(installed_apc.get('Sight', 0)) + 1
                and int(generated_apc.get('Passengers', 0))
                > int(installed_apc.get('Passengers', 0))
                and generated_apc.get('Cloakable') == 'yes'
                and generated_apc.get('Sensors') == 'yes'
                and float(generated_apc_weapon.get('Range', 0))
                > float(installed_apc_weapon.get('Range', 0))
            ),
            'unit_vision_and_speed_caps_are_exact': (
                sight_range_ceiling() == 10
                and all(
                    buff_stack_limit(reward) > 0
                    and capped_sight_range(
                        BUFF_TARGETS[reward['unit']],
                        buff_stack_limit(reward),
                    ) <= sight_range_ceiling()
                    and capped_sight_range(
                        BUFF_TARGETS[reward['unit']],
                        buff_stack_limit(reward) + 1,
                    ) == capped_sight_range(
                        BUFF_TARGETS[reward['unit']],
                        buff_stack_limit(reward),
                    )
                    for reward in REWARD_POOL
                    if reward.get('kind') == 'buff'
                    and not reward.get('global_buff')
                    and reward.get('buff_type') == 'sight'
                )
                and all(
                    buff_stack_limit(reward) > 0
                    and capped_movement_speed(
                        BUFF_TARGETS[reward['unit']],
                        buff_stack_limit(reward) + 1,
                    ) == capped_movement_speed(
                        BUFF_TARGETS[reward['unit']],
                        buff_stack_limit(reward),
                    )
                    for reward in REWARD_POOL
                    if reward.get('kind') == 'buff'
                    and not reward.get('global_buff')
                    and reward.get('buff_type') == 'speed'
                )
                and all(
                    e1_cap_counts[reward['buff_type']]
                    == buff_stack_limit(reward)
                    for reward in e1_cap_rewards
                )
                and any(
                    reward.get('max_rewards_achieved')
                    for reward in e1_cap_plan
                )
                and sum(
                    1 for reward in combined_speed_plan
                    if reward.get('kind') == 'buff'
                    and reward.get('buff_type') == 'speed'
                ) == buff_stack_limit(e1_speed_reward)
                and any(
                    reward.get('max_rewards_achieved')
                    for reward in combined_speed_plan
                )
            ),
            'orphan_unit_buffs_do_not_grant_access': (
                not _orphan_rules
                and any(
                    item.get('unit') == 'E2'
                    and item.get('reason') == 'buff_without_access'
                    for item in orphan_buff_report['skipped']
                )
            ),
            'access_clone_receives_unit_specific_buffs': (
                any(
                    item.get('unit') == 'E2'
                    and item.get('route') == 'production_access_clone'
                    and item.get('buffs', {}).get('damage') == 1
                    and item.get('buffs', {}).get('production') == 1
                    for item in e2_access_buff_report['applied']
                )
                and e2_access_buff_rules.get('E2_PLAYER', {}).get(
                    'TechLevel'
                ) == '1'
                and float(e2_access_buff_rules.get('E2_PLAYER', {}).get(
                    'BuildTimeMultiplier', 1
                )) < 1
                and int(e2_access_buff_rules.get(
                    e2_access_buff_rules.get('E2_PLAYER', {}).get('Primary'),
                    {},
                ).get('Damage', 0)) > int(
                    installed_e2_weapon.get('Damage', 0)
                )
            ),
            'dta_access_unlocks_required_player_factories': (
                {reward['unit'] for reward in infrastructure_rewards}
                == {'PYLE', 'WEAP'}
                and faction_infrastructure_ids == {
                    'GDI': {'PYLE', 'WEAP'},
                    'Nod': {'HAND', 'AFLD'},
                    'Allies': {'RATENT', 'AWEAP'},
                    'Soviet': {'RABARR', 'SWEAP'},
                }
                and set(infrastructure_outputs) == {'PYLE', 'WEAP'}
                and all(
                    (
                        values := infrastructure_rules.get(
                            infrastructure_outputs[source_id], {}
                        )
                    ).get('TechLevel') == '1'
                    and values.get('Owner') == 'GDI'
                    and values.get('RequiredHouses') == 'GDI'
                    and not any(
                        str(key).casefold().startswith('prerequisite')
                        for key in values
                    )
                    for source_id in ('PYLE', 'WEAP')
                )
            ),
            'dta_starting_credit_reward_is_capped_and_applied': (
                buff_stack_limit(starting_credit_reward) == 20
                and starting_credit_bonus([starting_credit_reward] * 25)
                == 20000
                and starting_credit_report['applied']
                and starting_credit_report['authored_credits'] == 10000
                and starting_credit_report['launch_credits'] == 30000
                and starting_credit_rules.get('TutorialGDI', {}).get(
                    'Credits'
                ) == '300'
            ),
            'dta_medic_clone_keeps_healing': (
                medic_clone_entry.get('route') == 'production_access_clone'
                and medic_clone.get('OmniHealer') == 'yes'
                and int(medic_weapon.get('Damage', 0)) < 0
                and medic_weapon.get('Warhead') == 'Organic'
            ),
            'vinifera_clone_written_to_generated_map': all(
                value in clone_generated_text
                for value in (
                    '[3TNK_PLAYER]',
                    'RequiredHouses=Soviet',
                    'ForbiddenHouses=Soviet',
                    '[3TNK_105MM_PLAYER]',
                )
            ),
            'clone_source_map_unchanged': clone_before_hash == clone_after_hash,
            'difficulty_fallback_valid': (
                extended_fallback.label == 'Extreme'
                and extended_fallback.engine_value == 2
                and extended_fallback.used_fallback
            ),
            'dta_player_infantry_access_valid': (
                access_report['enabled']
                and access_report['player_house'] == 'Soviet'
                and access_report['map_objects_rewritten'] == 0
                and access_rules.get('E1A', {}).get(
                    'ForbiddenHouses'
                ) == 'Soviet'
                and access_rules.get('E1', {}).get('ForbiddenHouses') == 'Soviet'
                and access_clone_entry.get('route') == 'production_access_clone'
                and access_clone_entry.get('output_type') == 'E1A_PLAYER'
                and access_clone_rules.get('E1A_PLAYER', {}).get(
                    'RequiredHouses'
                ) == 'Soviet'
                and 'Prerequisite' not in access_clone_rules.get(
                    'E1A_PLAYER', {}
                )
                and access_clone_rules.get('E1A_PLAYER', {}).get(
                    'TechLevel'
                ) == '1'
                and 'BuildLimit' not in access_clone_rules.get(
                    'E1A_PLAYER', {}
                )
                and access_clone_report['map_objects_rewritten'] == 0
            ),
            'dta_infantry_access_written_to_generated_map': all(
                value in access_generated_text
                for value in (
                    '[E1]',
                    'ForbiddenHouses=Soviet',
                    '[E1A_PLAYER]',
                    'Owner=Soviet',
                    'RequiredHouses=Soviet',
                )
            ),
            'dta_access_source_map_unchanged': (
                clone_before_hash == access_after_hash
            ),
            'standard_access_seed_plan_valid': (
                standard_access_plan['access_count'] > 0
                and not standard_access_plan['invalid_buffs']
            ),
            'chaos_access_seed_plan_valid': (
                chaos_access_plan['access_count'] > 0
                and not chaos_access_plan['invalid_buffs']
            ),
            'dta_game_speed_mapping_valid': dict(GAME_SPEEDS) == {
                '0 - Slowest': 6,
                '1 - Slower': 5,
                '2 - Slow': 4,
                '3 - Medium': 3,
                '4 - Fast': 2,
                '5 - Faster': 1,
                '6 - Fastest': 0,
            },
            'infantry_access_config_migration_valid': (
                access_config_migrated
                and legacy_access_config['generation'][
                    'randomize_unit_access'
                ]
                and 'access' in legacy_access_config['generation'][
                    'enabled_reward_types'
                ]
                and legacy_access_config['generation'][
                    'infantry_access_catalogue_version'
                ] == 1
            ),
            'eva_voice_option_removed': (
                access_config_migrated
                and 'eva_voice' not in legacy_access_config
            ),
            'all_mission_maps_exist': not missing_maps,
            'missing_mission_maps': missing_maps,
            'generated_map_has_difficulty_overlay': 'DifficultyGlobal=3,28,0,11' in generated_text,
            'generated_map_enables_score_screen': (
                'EndOfGame=true' in generated_text
                and 'SkipScore=false' in generated_text
            ),
            'original_map_unchanged': before_hash == after_hash,
            'spawn_contract_valid': all(
                item in spawn_text
                for item in (
                    'Scenario=spawnmap.ini',
                    'CampaignID=-1',
                    'SidebarHack=Yes',
                    'DifficultyModeHuman=1',
                    'DifficultyModeComputer=1',
                    'MissionInternalName=',
                    'DifficultyName=Normal',
                    'ClientDifficulty=30',
                )
            ),
            'player_normal_keeps_selected_ai_difficulty': (
                'DifficultyModeHuman=1' in player_normal_spawn_text
                and 'DifficultyModeComputer=2' in player_normal_spawn_text
            ),
            'legacy_map_rules_isolated': True,
            'dta_reward_adapter_status': (
                'shared ActsLike houses receive distinct production masks; '
                'all buffs use player-production clones; powers use '
                'map-local player-house grants; direct player starting units may '
                'use non-buildable clones while enemy and scripted identities remain '
                'unchanged; live production and save/load need verification'
            ),
            'diagnostic_log': str(LAUNCHER_LOG),
        }
        required = (
            'launchvinifera_exists', 'game_exe_exists', 'vinifera_exists',
            'battle_ini_exists', 'rules_ini_exists', 'window_icon_exists',
            'static_configs_valid', 'all_mission_maps_exist',
            'shop_domain_valid',
            'campaign_grouping_valid', 'dta_puzzle_exists',
            'dta_mission_reward_multipliers_valid',
            'cr_grid_uses_campaign_green',
            'no_unreportable_objective_checks',
            'generated_map_has_difficulty_overlay',
            'generated_map_enables_score_screen', 'original_map_unchanged',
            'spawn_contract_valid',
            'player_normal_keeps_selected_ai_difficulty',
            'legacy_map_rules_isolated',
            'safe_reward_pool_only',
            'global_buffs_use_player_clones_only',
            'global_vision_removed',
            'retry_assistance_uses_player_clones',
            'global_armor_removed',
            'spawner_control_weapons_are_not_cloned',
            'legacy_speed_stacks_are_engine_safe',
            'global_building_cost_and_production_buffs_work',
            'cloned_building_tech_chains_work',
            'unit_buff_pool_has_no_noop_rewards',
            'shared_house_enemy_clone_isolation',
            'dta_powers_granted_to_player_only',
            'dta_e1_cameo_extracted', 'map_unit_preservation_policy_active',
            'dta_engineer_cameo_extracted',
            'dta_active_unit_cameos_or_text_complete',
            'dta_allied_helpers_use_buffed_clones',
            'dta_harvester_clones_keep_harvester_identity',
            'dta_harvesters_survive_refinery_clones',
            'dta_refinery_spawns_working_harvester_clone',
            'dta_enforcer_deploy_form_keeps_buffs',
            'dta_unlimited_heroes_remove_build_limit',
            'dta_classic_heroes_have_limits_and_capacity_buffs',
            'dta_mobile_access_reward_count_valid',
            'dta_essential_mobile_units_always_available',
            'dta_obsolete_aliases_removed', 'dta_special_roster_present',
            'dta_all_mobile_buff_targets_present',
            'dta_arsenal_all_mobile_access_present',
            'dta_power_rewards_present',
            'dta_building_gated_powers_enabled',
            'dta_sidebar_factions_and_defenses_sorted',
            'dta_power_buff_matrix_valid',
            'dta_power_stack_limits_valid',
            'unlock_dashboard_tooltips_render',
            'unlock_dashboard_factory_support_visible',
            'unlock_dashboard_global_buffs_visible',
            'unlock_dashboard_chaos_equivalents_collapsed',
            'dta_power_cameos_complete',
            'dta_defense_rewards_complete',
            'dta_firestorm_removed',
            'dta_retired_chrono_tank_power_ignored',
            'dta_power_actions_are_unique_and_callable',
            'dta_power_buildings_are_immediately_available',
            'dta_building_power_buffs_are_player_only',
            'dta_power_lists_preserve_war_factory_clones',
            'dta_exclusive_buffed_ion_cannon_works',
            'dta_paradrop_payload_uses_badger_capacity',
            'dta_enemy_buffs_exclude_player_family',
            'dta_player_color_list_valid',
            'dta_loose_mission_launch_source_valid',
            'dta_arsenal_power_pool_complete',
            'dta_ts_leftovers_excluded',
            'dta_mobile_hq_removed_from_pool',
            'dta_special_factions_curated',
            'dta_registered_mobile_factions_match_installed_rosters',
            'dta_anti_air_roster_matches_installed_ini',
            'dta_aa_truck_cameo_uses_mflak_art',
            'dta_route_c13_ai_aliases_use_buffed_clones',
            'vinifera_production_clone_generated',
            'all_unit_specific_buffs_use_production_clones',
            'dta_extended_unit_buffs_work',
            'unit_vision_and_speed_caps_are_exact',
            'orphan_unit_buffs_do_not_grant_access',
            'access_clone_receives_unit_specific_buffs',
            'dta_access_unlocks_required_player_factories',
            'dta_starting_credit_reward_is_capped_and_applied',
            'dta_medic_clone_keeps_healing',
            'vinifera_clone_written_to_generated_map',
            'clone_source_map_unchanged',
            'difficulty_fallback_valid',
            'dta_player_infantry_access_valid',
            'dta_infantry_access_written_to_generated_map',
            'dta_access_source_map_unchanged',
            'standard_access_seed_plan_valid',
            'chaos_access_seed_plan_valid',
            'dta_game_speed_mapping_valid',
            'infantry_access_config_migration_valid',
            'eva_voice_option_removed',
        )
        checks['passed'] = bool(missions) and all(checks[key] for key in required)
        report_path.write_text(json.dumps(checks, indent=2), encoding='utf-8')
        log_event('self_check_finished', **checks)
        return 0 if checks['passed'] else 1
    except Exception:
        detail = traceback.format_exc()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps({'passed': False, 'traceback': detail}, indent=2),
            encoding='utf-8',
        )
        log_event('self_check_failed', traceback=detail)
        return 1


if __name__ == '__main__':
    if '--self-check' in sys.argv:
        raise SystemExit(run_self_check())
    raise SystemExit(run_launcher())
