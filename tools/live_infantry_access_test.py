"""Prepare and run a reversible Vinifera player-clone experiment.

The test unlocks one unit through the same player-production clone used by
normal randomizer runs. Unit-specific and Player Army production rewards plus a
damage reward are applied to that clone. Another unit remains locked as the
control. Shared ActsLike production families are isolated first. Authored map
identities are never rewritten.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from randomizer.core.paths import (  # noqa: E402
    BATTLE_CLIENT_INI,
    DEBUG_LOG,
    GAME_LAUNCHER_EXE,
    GAME_ROOT,
    GENERATED_MAP_DIR,
    LOG_DIR,
    SPAWN_INI,
    SPAWN_MAP_INI,
)
from randomizer.dta.access import player_infantry_access_rules  # noqa: E402
from randomizer.dta.clones import (  # noqa: E402
    player_production_isolation_rules,
    unit_specific_buff_rules,
)
from randomizer.dta.difficulty import resolve_mission_difficulty  # noqa: E402
from randomizer.dta.maps import (  # noqa: E402
    newest_debug_log,
    prepare_spawn_map,
    score_screen_loaded,
)
from randomizer.dta.rules import (  # noqa: E402
    catalogue_by_id,
    effective_section,
    ini_sections,
)
from randomizer.launch.options import spawn_ini_text  # noqa: E402
from randomizer.missions.catalogue import parse_missions  # noqa: E402
from randomizer.rewards.catalogue import REWARD_POOL  # noqa: E402


ACTIVE_BACKUP = PROJECT_ROOT / 'backups' / 'live_infantry_access_active.json'
DEFAULT_REPORT = LOG_DIR / 'live_infantry_access_test.json'


def now_stamp():
    return datetime.now(timezone.utc).isoformat()


def file_hash(path):
    return sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding='utf-8')


def selected_reward(unit_id, *, access=False, buff_type=''):
    unit_id = unit_id.upper()
    return next(
        reward
        for reward in REWARD_POOL
        if str(reward.get('unit') or '').upper() == unit_id
        and bool(reward.get('dta_production_access')) == bool(access)
        and str(reward.get('buff_type') or '') == buff_type
    )


def merge_rules(*sources):
    merged = {}
    for source in sources:
        for section, values in source.items():
            merged.setdefault(section, {}).update(values)
    return merged


def backup_runtime_files(run_id):
    if ACTIVE_BACKUP.exists():
        raise RuntimeError(
            f'Unrestored live-test backup exists: {ACTIVE_BACKUP}. '
            'Run this tool with --restore first.'
        )
    backup_directory = PROJECT_ROOT / 'backups' / 'live_infantry_access' / run_id
    backup_directory.mkdir(parents=True, exist_ok=False)
    records = []
    for path in (SPAWN_INI, SPAWN_MAP_INI):
        existed = path.is_file()
        backup_path = backup_directory / path.name
        if existed:
            shutil.copy2(path, backup_path)
        records.append({
            'path': str(path),
            'existed': existed,
            'backup': str(backup_path),
        })
    manifest = {
        'run_id': run_id,
        'created_at': now_stamp(),
        'files': records,
    }
    write_json(ACTIVE_BACKUP, manifest)
    return manifest


def restore_runtime_files():
    if not ACTIVE_BACKUP.is_file():
        return False
    manifest = json.loads(ACTIVE_BACKUP.read_text(encoding='utf-8'))
    for record in manifest.get('files', []):
        path = Path(record['path'])
        backup = Path(record['backup'])
        if record.get('existed'):
            if not backup.is_file():
                raise FileNotFoundError(f'Live-test backup is missing: {backup}')
            shutil.copy2(backup, path)
        else:
            path.unlink(missing_ok=True)
    ACTIVE_BACKUP.unlink()
    return True


def debug_cursor():
    path = newest_debug_log(DEBUG_LOG)
    return {
        'path': str(path) if path else '',
        'offset': path.stat().st_size if path else 0,
    }


def debug_result(cursor):
    path = newest_debug_log(DEBUG_LOG)
    if path is None:
        return {'path': '', 'score_screen_loaded': False, 'new_lines': 0}
    offset = cursor['offset'] if str(path) == cursor['path'] else 0
    with path.open('r', encoding='utf-8', errors='ignore') as handle:
        handle.seek(min(offset, path.stat().st_size))
        lines = handle.readlines()
    return {
        'path': str(path),
        'score_screen_loaded': any(score_screen_loaded(line) for line in lines),
        'new_lines': len(lines),
    }


def prepare_experiment(args):
    missions = parse_missions(BATTLE_CLIENT_INI)
    mission = next(
        mission for mission in missions
        if mission['code'].upper() == args.mission.upper()
    )
    difficulty = resolve_mission_difficulty(mission, args.difficulty)
    unit_access = selected_reward(args.unit, access=True)
    unit_damage = selected_reward(
        args.unit, access=False, buff_type='damage'
    )
    unit_production = selected_reward(
        args.unit, access=False, buff_type='production'
    )
    global_production = next(
        reward for reward in REWARD_POOL
        if reward.get('global_buff')
        and reward.get('dta_global_clone_buff')
        and reward.get('buff_type') == 'production'
    )
    rewards = [
        unit_access, unit_damage, unit_production, global_production,
    ]
    isolation_rules, isolation_report = player_production_isolation_rules(
        mission
    )
    if isolation_report.get('isolation_error'):
        raise RuntimeError(
            'Could not isolate randomized player production: '
            + isolation_report['isolation_error']
        )
    access_rules, access_report = player_infantry_access_rules(
        mission,
        rewards,
        True,
        production_context=isolation_report,
        rule_overlays=isolation_rules,
    )
    clone_rules, clone_report = unit_specific_buff_rules(
        mission,
        rewards,
        access_randomized=True,
        production_context=isolation_report,
        rule_overlays=isolation_rules,
    )
    rules = merge_rules(
        isolation_rules, access_rules, clone_rules
    )
    clone_entry = next(
        entry for entry in clone_report['applied']
        if entry['unit'] == args.unit.upper()
    )
    source = GAME_ROOT.joinpath(*mission['scenario'].replace('\\', '/').split('/'))
    source_hash = file_hash(source)
    GENERATED_MAP_DIR.mkdir(parents=True, exist_ok=True)
    generated = GENERATED_MAP_DIR / 'live_infantry_access_spawnmap.ini'
    prepare_spawn_map(
        mission,
        difficulty,
        extra_rules=rules,
        output_path=generated,
    )
    generated_text = generated.read_text(encoding='cp1252')
    player_clone = clone_entry['output_type']
    clone_values = clone_rules[player_clone]
    weapon_id = clone_values.get('Primary', '')
    weapon_values = clone_rules.get(weapon_id, {})
    installed_sections = ini_sections(GAME_ROOT / 'INI' / 'Rules.ini')
    installed_unit = effective_section(installed_sections, args.unit.upper())
    installed_weapon = effective_section(
        installed_sections, installed_unit.get('Primary', '')
    )
    expected_build_limit = int(
        catalogue_by_id()[args.unit.upper()].get('build_limit', 0)
    )
    production_house = access_report['production_house']
    required_fragments = (
        f'[{player_clone}]',
        f'Owner={production_house}',
        f'RequiredHouses={production_house}',
        'TechLevel=1',
        f'[{weapon_id}]',
        f'[{args.locked.upper()}]',
        f'ForbiddenHouses={production_house}',
    )
    forbidden_clone_fields = {
        key for key in clone_values
        if key.casefold() == 'builtat'
        or key.casefold().startswith('prerequisite')
    }
    validation = {
        'source_map_unchanged': file_hash(source) == source_hash,
        'map_objects_untouched': (
            access_report['map_objects_rewritten'] == 0
            and clone_report['map_objects_rewritten'] == 0
        ),
        'player_clone_route': (
            clone_entry['route'] == 'production_access_clone'
        ),
        'production_route_isolated': (
            not access_report['shared_hostile_houses']
            and not isolation_report['isolation_error']
            and (
                isolation_report['isolation_applied']
                == bool(
                    isolation_report['original_shared_hostile_houses']
                )
            )
        ),
        'clone_has_unit_buffs': (
            clone_entry['buffs'].get('damage') == 1
            and clone_entry['buffs'].get('production') == 2
            and float(clone_values.get('BuildTimeMultiplier', 1)) < 1
            and float(weapon_values.get('Damage', 0)) > float(
                installed_weapon.get('Damage', 0)
            )
        ),
        'clone_has_safe_production_gates': (
            clone_values.get('TechLevel') == '1'
            and not forbidden_clone_fields
            and (
                clone_values.get('BuildLimit') == str(expected_build_limit)
                if expected_build_limit > 0
                else 'BuildLimit' not in clone_values
            )
        ),
        'global_production_buff_present': (
            clone_entry['buffs'].get('production') == 2
        ),
        'generated_sections_present': all(
            fragment in generated_text for fragment in required_fragments
        ),
    }
    if not all(validation.values()):
        raise RuntimeError(f'Live-test preflight failed: {validation}')
    return {
        'mission': mission,
        'difficulty': difficulty,
        'rewards': rewards,
        'isolation_report': isolation_report,
        'access_report': access_report,
        'clone_report': clone_report,
        'source': source,
        'source_hash': source_hash,
        'generated': generated,
        'generated_hash': file_hash(generated),
        'player_clone': player_clone,
        'weapon_clone': weapon_id,
        'validation': validation,
    }


def report_template(args, experiment):
    mission = experiment['mission']
    return {
        'status': 'prepared',
        'prepared_at': now_stamp(),
        'mission_code': mission['code'],
        'mission_title': mission['title'],
        'source_map': str(experiment['source']),
        'source_hash': experiment['source_hash'],
        'generated_map': str(experiment['generated']),
        'generated_hash': experiment['generated_hash'],
        'player_house': experiment['access_report']['player_house'],
        'production_isolation': experiment['isolation_report'],
        'unit_unlocked': args.unit.upper(),
        'player_clone': experiment['player_clone'],
        'weapon_clone': experiment['weapon_clone'],
        'locked_control': args.locked.upper(),
        'validation': experiment['validation'],
        'manual_checks': {
            'player_clone_visible': 'pending',
            'player_clone_builds_without_tech_gate': 'pending',
            'locked_control_hidden': 'pending',
            'unit_damage_buff_works': 'pending',
            'unit_production_buff_works': 'pending',
            'global_production_buff_includes_clone': 'pending',
            'save_load_preserves_clone': 'pending',
            'enemy_or_map_identity_regression': 'pending',
        },
        'instructions': [
            'Open the appropriate player production sidebar.',
            f'Confirm {experiment["player_clone"]} is visible and buildable immediately.',
            f'Confirm unearned {args.locked.upper()} is not buildable.',
            'Confirm the clone has its unit-specific production and damage rewards.',
            'Confirm the global production reward also affects the clone.',
            'Build the clone, save, load, and confirm it still exists and works.',
            'Do not judge map units by clone behavior; authored units must remain original.',
            'Close or finish the mission after checks.',
        ],
    }


def run(args):
    if args.restore:
        restored = restore_runtime_files()
        print('Restored live-test runtime files.' if restored else 'No active backup.')
        return 0

    experiment = prepare_experiment(args)
    report = report_template(args, experiment)
    report_path = Path(args.report).resolve()
    write_json(report_path, report)
    print(json.dumps({
        'report': str(report_path),
        'generated_map': str(experiment['generated']),
        'validation': experiment['validation'],
        'instructions': report['instructions'],
    }, indent=2))
    if not args.launch:
        return 0

    run_id = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = backup_runtime_files(run_id)
    cursor = debug_cursor()
    process = None
    try:
        shutil.copy2(experiment['generated'], SPAWN_MAP_INI)
        mission = experiment['mission']
        difficulty = experiment['difficulty']
        human_difficulty = (
            1 if mission.get('player_always_normal')
            else difficulty.engine_value
        )
        SPAWN_INI.write_text(
            spawn_ini_text(
                'spawnmap.ini',
                human_difficulty,
                args.game_speed,
                {
                    'Side': mission['side'],
                    'Firestorm': 'True' if mission['required_addon'] else 'False',
                    'MissionInternalName': mission['code'],
                    'DifficultyName': difficulty.label,
                    'ClientDifficulty': difficulty.client_rank,
                },
            ),
            encoding='utf-8',
            newline='',
        )
        report.update({
            'status': 'running',
            'launched_at': now_stamp(),
            'backup': backup,
            'command': [str(GAME_LAUNCHER_EXE), '-SPAWN', '-CD.'],
        })
        write_json(report_path, report)
        process = subprocess.Popen(
            report['command'],
            cwd=GAME_ROOT,
        )
        report['process_id'] = process.pid
        write_json(report_path, report)
        return_code = process.wait()
        time.sleep(1)
        report.update({
            'status': 'awaiting_manual_result',
            'closed_at': now_stamp(),
            'process_return_code': return_code,
            'debug': debug_result(cursor),
            'source_map_unchanged_after_run': (
                file_hash(experiment['source']) == experiment['source_hash']
            ),
        })
        return 0
    finally:
        try:
            restored = restore_runtime_files()
            report['runtime_files_restored'] = restored
        except Exception as exc:
            report['restore_error'] = str(exc)
        write_json(report_path, report)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Run a reversible DTA player-clone live test.'
    )
    parser.add_argument('--mission', default='M_TUTORIAL2')
    parser.add_argument('--unit', default='E2')
    parser.add_argument('--locked', default='E3')
    parser.add_argument('--difficulty', default='Normal')
    parser.add_argument('--game-speed', type=int, default=3)
    parser.add_argument('--report', default=str(DEFAULT_REPORT))
    parser.add_argument('--launch', action='store_true')
    parser.add_argument('--restore', action='store_true')
    return parser.parse_args()


if __name__ == '__main__':
    raise SystemExit(run(parse_args()))
