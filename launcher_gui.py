"""Entry point for source runs and the packaged launcher."""

# The copied helper must run before normal imports resolve game/config paths.
import sys

if __name__ == '__main__' and len(sys.argv) == 3 and sys.argv[1] == '--apply-update':
    from randomizer.core.update_helper import main as apply_update_main
    raise SystemExit(apply_update_main(sys.argv[2]))

import json
import traceback

from randomizer.core.diagnostics import event as log_event
from randomizer.core.paths import APP_DIR, GAME_ROOT, LAUNCHER_LOG


def run_launcher():
    """Load config-dependent application modules with visible startup errors."""
    try:
        # DTA updates replace Action.ini. Restore the player-only power cursor
        # entries before the UI opens so every later launch has valid actions.
        from randomizer.dta.powers import ensure_power_action_types
        from randomizer.application.app import main
        restored_actions = ensure_power_action_types()
        if restored_actions:
            log_event(
                'power_action_types_restored', actions=restored_actions
            )
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
    """Report actual installation/configuration integrity without synthetic tests."""
    report_path = APP_DIR / 'self_check.json'
    try:
        from randomizer.config.static import REQUIRED_STATIC_CONFIGS, validate_static_configs
        from randomizer.core.paths import BATTLE_CLIENT_INI, GAME_EXE, GAME_LAUNCHER_EXE, WINDOW_ICON_PATH
        from randomizer.core.version import APP_VERSION
        from randomizer.missions.catalogue import campaign_mission_counts, parse_missions
        from randomizer.shop.catalogue import shop_catalogue

        static_paths = validate_static_configs(REQUIRED_STATIC_CONFIGS)
        missions = parse_missions(BATTLE_CLIENT_INI)
        entries = shop_catalogue()
        report = {
            'version': APP_VERSION,
            'game_root': str(GAME_ROOT),
            'executable': sys.executable,
            'game_exe_exists': GAME_EXE.is_file(),
            'game_launcher_exists': GAME_LAUNCHER_EXE.is_file(),
            'battle_ini_exists': BATTLE_CLIENT_INI.is_file(),
            'window_icon_exists': WINDOW_ICON_PATH.is_file(),
            'static_configs_valid': len(static_paths) == len(REQUIRED_STATIC_CONFIGS),
            'mission_count': len(missions),
            'mission_counts_by_campaign': campaign_mission_counts(missions),
            'shop_catalogue_entries': len(entries),
        }
        from randomizer.dta.maps import mission_source_path
        from randomizer.dta.rules import techno_catalogue
        report['engine'] = 'Tiberian Sun + Vinifera'
        report['vinifera_exists'] = (GAME_ROOT / 'Vinifera.dll').is_file()
        report['rules_ini_exists'] = (GAME_ROOT / 'INI' / 'Rules.ini').is_file()
        report['techno_catalogue_entries'] = len(techno_catalogue())
        missing_maps = []
        for mission in missions:
            try:
                mission_source_path(mission['scenario'])
            except FileNotFoundError:
                missing_maps.append(mission['scenario'])
        report['missing_campaign_maps'] = missing_maps
        report['passed'] = bool(
            report['game_exe_exists'] and report['game_launcher_exists']
            and report['battle_ini_exists'] and report['static_configs_valid']
            and missions and entries
            and report['vinifera_exists'] and report['rules_ini_exists']
            and report['techno_catalogue_entries'] and not missing_maps
        )
    except Exception:
        report = {
            'passed': False,
            'game_root': str(GAME_ROOT),
            'executable': sys.executable,
            'traceback': traceback.format_exc(),
        }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    log_event('self_check_finished', **report)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    if '--self-check' in sys.argv:
        raise SystemExit(run_self_check())
    raise SystemExit(run_launcher())
