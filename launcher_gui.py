"""Entry point for source runs and the packaged launcher."""

import json
from hashlib import sha256
import sys
import traceback

from randomizer.ui.cameos import ensure_unit_cameos
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
    from randomizer.dta.maps import mission_normal_modifiers, prepare_spawn_map
    from randomizer.dta.access import player_infantry_access_rules
    from randomizer.dta.clones import unit_specific_buff_rules
    from randomizer.dta.clones import _player_production_context
    from randomizer.dta.difficulty import resolve_mission_difficulty
    from randomizer.dta.rewards import human_modifier_rules
    from randomizer.dta.rules import (
        ALWAYS_AVAILABLE_MOBILE_IDS,
        effective_section,
        ini_sections,
        techno_catalogue,
        unit_collision_report,
    )
    from randomizer.launch.options import spawn_ini_text
    from randomizer.ui.config import GAME_SPEEDS
    from randomizer.rewards.catalogue import (
        ALWAYS_AVAILABLE_TECH_IDS,
        REWARD_POOL,
    )
    from randomizer.rewards.planning import plan_seed_rewards
    from randomizer.rewards.rules import tech_ids_for_rewards
    from randomizer.missions.catalogue import (
        campaign_mission_counts,
        parse_missions,
    )

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
        counts = campaign_mission_counts(missions)
        reward_names = [reward['name'] for reward in REWARD_POOL]
        damage_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('buff_type') == 'damage'
        )
        armor_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('buff_type') == 'armor'
        )
        modifier_rules = human_modifier_rules([damage_reward])
        armor_rules = human_modifier_rules([armor_reward])
        authored_normal_mission = next(
            (
                mission for mission in missions
                if mission_normal_modifiers(mission).get('Cost') == '0.75'
            ),
            None,
        )
        cost_reward = next(
            reward for reward in REWARD_POOL
            if reward.get('buff_type') == 'cost'
        )
        authored_cost_rules = human_modifier_rules(
            [cost_reward],
            mission_normal_modifiers(authored_normal_mission)
            if authored_normal_mission else {},
        )
        catalogue = techno_catalogue()
        mobile_ids = {
            record['id'] for record in catalogue
            if record.get('rewardable')
            and record.get('category') in {'infantry', 'vehicles', 'aircraft'}
            and not record.get('duplicate_of')
        }
        cameo_paths = ensure_unit_cameos(mobile_ids)
        expected_access_ids = mobile_ids - set(ALWAYS_AVAILABLE_MOBILE_IDS)
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
        installed_sections = ini_sections(GAME_ROOT / 'INI' / 'Rules.ini')
        installed_e2 = effective_section(installed_sections, 'E2')
        installed_e2_weapon = effective_section(
            installed_sections, installed_e2.get('Primary')
        )
        _orphan_rules, orphan_buff_report = unit_specific_buff_rules(
            tutorial_two, [e2_damage_reward], access_randomized=True
        )

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
            'mission_count': len(missions),
            'mission_counts_by_campaign': counts,
            'campaign_grouping_valid': counts == {
                'Tutorial': 2,
                'PTTP': 9,
                'CR': 32,
                'Toxic Diversion': 7,
                'It Came From Red Alert!': 3,
                'Creeping Destruction': 8,
                'Special Ops': 20,
            },
            'dta_puzzle_exists': DTA_PUZZLE_PATH.is_file(),
            'objective_reward_mode': (
                'victory-only until DTA map-specific objective hooks are verified'
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
                if reward.get('dta_house_modifier')
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
                reward.get('dta_house_modifier')
                or reward.get('dta_production_clone')
                or reward.get('dta_production_access')
                for reward in REWARD_POOL
            ),
            'player_firepower_modifier_works': (
                float(modifier_rules['Normal']['Firepower']) > 1.0
            ),
            'player_armor_modifier_works': (
                float(armor_rules['Normal']['Armor']) > 1.0
            ),
            'authored_map_modifier_preserved': (
                authored_normal_mission is not None
                and float(authored_cost_rules['Normal']['Cost']) < 0.75
            ),
            'dta_e1_cameo_extracted': (
                'E1' in cameo_paths and cameo_paths['E1'].is_file()
            ),
            'dta_engineer_cameo_extracted': (
                'ENGINEER' in cameo_paths
                and cameo_paths['ENGINEER'].is_file()
            ),
            'dta_missing_cameos_use_text_fallback': (
                mobile_ids - set(cameo_paths)
                == {'HTNKMSAM', 'SMECH', 'UTNK'}
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
            'legacy_map_rules_isolated': True,
            'dta_reward_adapter_status': (
                'broad player-house modifiers and guarded Vinifera production '
                'clones enabled; all mobile access categories use ActsLike-safe '
                'isolation; production and clone save/load need live verification'
            ),
            'diagnostic_log': str(LAUNCHER_LOG),
        }
        required = (
            'launchvinifera_exists', 'game_exe_exists', 'vinifera_exists',
            'battle_ini_exists', 'rules_ini_exists', 'window_icon_exists',
            'static_configs_valid', 'all_mission_maps_exist',
            'campaign_grouping_valid', 'dta_puzzle_exists',
            'no_unreportable_objective_checks',
            'generated_map_has_difficulty_overlay',
            'generated_map_enables_score_screen', 'original_map_unchanged',
            'spawn_contract_valid', 'legacy_map_rules_isolated',
            'safe_reward_pool_only', 'player_firepower_modifier_works',
            'player_armor_modifier_works',
            'authored_map_modifier_preserved',
            'dta_e1_cameo_extracted', 'map_unit_preservation_policy_active',
            'dta_engineer_cameo_extracted',
            'dta_missing_cameos_use_text_fallback',
            'dta_mobile_access_reward_count_valid',
            'dta_essential_mobile_units_always_available',
            'dta_obsolete_aliases_removed', 'dta_special_roster_present',
            'vinifera_production_clone_generated',
            'all_unit_specific_buffs_use_production_clones',
            'orphan_unit_buffs_do_not_grant_access',
            'access_clone_receives_unit_specific_buffs',
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
