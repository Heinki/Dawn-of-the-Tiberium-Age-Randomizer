"""Regression checks against a real Archipelago checkout and a freshly built APWorld.

Run with an environment containing Archipelago's dependencies:
    python tools/check_archipelago_generation.py --ap-root /path/to/Archipelago
"""

import argparse
from argparse import Namespace
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class GenerationTests(unittest.TestCase):
    def test_yaml_settings_only_round_trip(self):
        from Archipelago.yaml_config import serialize_player_yaml, parse_player_yaml
        from Archipelago.run_manifest import gameplay_config_snapshot
        from randomizer.config.player import DEFAULT_CONFIG
        import yaml

        settings = deepcopy(DEFAULT_CONFIG)
        settings['seed'] = 'LOCAL-SEED-MUST-NOT-LEAK'
        text = serialize_player_yaml(settings, "Commander's slot")
        parsed = yaml.safe_load(text)
        self.assertEqual(set(parsed['Dawn of the Tiberium Age']), {'launcher_settings'})
        self.assertNotIn(settings['seed'], text)
        expected = gameplay_config_snapshot(settings)
        expected.pop('seed')
        self.assertEqual(parsed['Dawn of the Tiberium Age']['launcher_settings'], expected)
        self.assertEqual(parse_player_yaml(text)['launcher_settings'], expected)
        self.assertIsNone(parse_player_yaml(text)['run_manifest'])

    def test_each_mode_reproducible_and_new_seeds_change_content(self):
        for mode in ('Classic', 'Mission List', 'Grid Mode', 'Shop Mode'):
            with self.subTest(mode=mode):
                settings = {'progression_mode': mode}
                first = generate_manifest(settings, 'DTA-seed-one')
                repeat = generate_manifest(settings, 'DTA-seed-one')
                second = generate_manifest(settings, 'DTA-seed-two')
                self.assertEqual(first, repeat)
                self.assertNotEqual(first['item_pool'], second['item_pool'])
                if mode != 'Classic':
                    self.assertNotEqual(first['mission_order'], second['mission_order'])
                if mode == 'Grid Mode':
                    self.assertNotEqual(first['grid'], second['grid'])
                self.assertEqual(settings, {'progression_mode': mode})

    def test_edits_exclusions_and_starters(self):
        first = generate_manifest({'progression_mode': 'Grid Mode'}, 'DTA-settings')
        excluded = first['mission_order'][0]
        settings = {
            'progression_mode': 'Grid Mode', 'mission_goal': 9,
            'grid_two_start_positions': True,
            'generation': {'excluded_mission_codes': [excluded],
                           'starting_reward_count': 3, 'starting_reward_types': ['access']},
        }
        edited = generate_manifest(settings, 'DTA-settings')
        self.assertNotIn(excluded, edited['mission_order'])
        self.assertEqual(len(edited['mission_order']), 9)
        self.assertTrue(edited['grid']['two_start_positions'])
        self.assertEqual(sum(edited['starting_items'].values()), 3)
        self.assertEqual(edited['frozen_settings']['launcher']['mission_goal'], 9)

    def test_reward_modes_and_buff_pools(self):
        for mode in ('Standard', 'Chaos', 'Randomizer Arsenal'):
            with self.subTest(mode=mode):
                manifest = generate_manifest({
                    'progression_mode': 'Grid Mode',
                    'generation': {'reward_mode': mode,
                                   'arsenal': {'roster_sizes': {'tier_1': {'infantry': 2, 'vehicles': 2}}}},
                }, 'DTA-rewards')
                self.assertEqual(manifest['state_snapshot']['reward_mode'], mode)
                self.assertTrue(any(ITEM_DATA[name]['classification_name'] == 'useful'
                                    for name in manifest['item_pool']))
                if mode == 'Randomizer Arsenal':
                    self.assertTrue(manifest['state_snapshot']['mission_arsenals'])

    def test_launcher_and_archive_generate_identical_runs(self):
        from randomizer.generation.service import RunGenerator
        from randomizer.core.paths import BATTLE_CLIENT_INI
        from randomizer.missions.catalogue import parse_missions
        from Archipelago.run_manifest import (
            build_run_manifest, gameplay_config_snapshot, validate_run_manifest_for_state,
        )
        for mode in ('Grid Mode', 'Shop Mode'):
            generator = RunGenerator({'progression_mode': mode}, parse_missions(BATTLE_CLIENT_INI))
            state = generator.generate('DTA-parity')
            settings = gameplay_config_snapshot(generator.config)
            settings['seed'] = 'DTA-parity'
            local = build_run_manifest(state, settings)
            remote = generate_manifest({'progression_mode': mode}, 'DTA-parity')
            self.assertEqual(local, remote)
            validate_run_manifest_for_state(remote['state_snapshot'], remote)

    def test_invalid_settings_fail(self):
        for settings in ({'progression_mode': 'bogus'}, {'rewards_per_objective': 0},
                         {'mission_goal': -1}, {'generation': {'excluded_mission_codes': list(MISSION_DATA)}}):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                generate_manifest(settings, 'DTA-invalid')

    def test_ap_seed_controls_run_and_legacy_yaml_is_regenerated(self):
        from BaseClasses import MultiWorld
        import json

        def generate(seed, values):
            multiworld = MultiWorld(1)
            multiworld.game[1] = DTAWorld.game
            multiworld.player_name = {1: 'Commander'}
            multiworld.set_seed(seed)
            args = Namespace(**{
                name: {1: option.from_any(values.get(name, option.default))}
                for name, option in DTAWorld.options_dataclass.type_hints.items()
            })
            multiworld.set_options(args)
            world = multiworld.worlds[1]
            world.generate_early()
            return world.run_manifest

        values = {'launcher_settings': {'progression_mode': 'Grid Mode'}}
        first = generate(10, values)
        self.assertEqual(first, generate(10, values))
        self.assertEqual(first, generate(10, {**values, 'generated_world': {'obsolete': True}}))
        self.assertNotEqual(first['grid'], generate(20, values)['grid'])
        for option in ('generated_world', 'run_manifest'):
            legacy = first if option == 'generated_world' else json.dumps(first)
            updated = generate(30, {option: legacy})
            self.assertNotEqual(first['grid'], updated['grid'])
            self.assertNotEqual(first['randomizer_seed'], updated['randomizer_seed'])

    def test_real_ap_generation_fill_and_slot_data(self):
        from BaseClasses import MultiWorld, CollectionState
        from worlds.AutoWorld import call_all
        from Fill import distribute_items_restrictive
        for mode in ('Classic', 'Mission List', 'Grid Mode', 'Shop Mode'):
            with self.subTest(mode=mode):
                multiworld = MultiWorld(1)
                multiworld.game[1] = DTAWorld.game
                multiworld.player_name = {1: 'Commander'}
                multiworld.set_seed(123456)
                args = Namespace(**{
                    name: {1: option.from_any({'progression_mode': mode} if name == 'launcher_settings' else option.default)}
                    for name, option in DTAWorld.options_dataclass.type_hints.items()
                })
                multiworld.set_options(args)
                multiworld.state = CollectionState(multiworld)
                for step in ('generate_early', 'create_regions', 'create_items', 'set_rules'):
                    call_all(multiworld, step)
                self.assertEqual(len(multiworld.itempool), len(multiworld.get_unfilled_locations()))
                distribute_items_restrictive(multiworld)
                self.assertFalse(multiworld.get_unfilled_locations())
                self.assertTrue(multiworld.can_beat_game())
                world = multiworld.worlds[1]
                slot = world.fill_slot_data()
                self.assertEqual(slot['run_manifest'], world.run_manifest)
                self.assertEqual(slot['randomizer_seed'], world.run_manifest['state_snapshot']['seed'])
                if mode == 'Shop Mode':
                    self.assertEqual(len(slot['shop']['item_locations']), 120)
                    self.assertEqual(len(slot['shop']['stage_victories']), slot['shop']['run_length'])

    def test_export_does_not_generate_or_replace_local_run(self):
        from randomizer.application.archipelago_yaml_controller import ArchipelagoYamlController
        from Archipelago.yaml_config import parse_player_yaml
        class Value:
            def __init__(self, value): self.value = value
            def get(self): return self.value
            def set(self, value): self.value = value
        class Launcher(ArchipelagoYamlController):
            config = {'progression_mode': 'Grid Mode'}
            state = {'seed': 'existing', 'completed_missions': ['TEST']}
            archipelago_slot_var = Value('Commander')
            archipelago_yaml_status_var = Value('')
            def gameplay_settings_locked(self): return False
            def save_current_launcher_config(self): pass
            def append_archipelago_history(self, message): pass
            def handle_seed_generation_error(self, exc, detail): raise exc
        launcher = Launcher()
        before = deepcopy(launcher.state)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'player.yaml'
            with patch('randomizer.application.archipelago_yaml_controller.filedialog.asksaveasfilename', return_value=str(path)):
                launcher.save_archipelago_yaml()
            self.assertIsNone(parse_player_yaml(path.read_text())['run_manifest'])
        self.assertEqual(launcher.state, before)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ap-root', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.ap_root.resolve()))
    from Archipelago.build_apworld import build
    with tempfile.TemporaryDirectory() as directory:
        archive = build(Path(directory))
        # Avoid loading every unrelated world from the developer's checkout.
        worlds = types.ModuleType('worlds')
        worlds.__path__ = [str(args.ap_root.resolve() / 'worlds'), str(archive)]
        sys.modules['worlds'] = worlds
        from worlds.dta import DTAWorld
        from worlds.dta.generation import generate_manifest
        from worlds.dta.data import ITEM_DATA, MISSION_DATA
        result = unittest.main(argv=[sys.argv[0]], exit=False, verbosity=2).result
        sys.exit(not result.wasSuccessful())
