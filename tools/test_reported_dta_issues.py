"""Focused regressions for reported DTA mission and reward behavior."""

import tempfile
import unittest
from pathlib import Path

from randomizer.config.tuning import stacked_weapon_rof
from randomizer.dta.clones import (
    player_production_isolation_rules,
    unit_specific_buff_rules,
)
from randomizer.dta.maps import mission_runtime_fixes, prepare_spawn_map
from randomizer.dta.rules import ini_sections, installed_effective_sections, techno_catalogue
from randomizer.maps.enemy_scripting import _team_taskforce_rules
from randomizer.rewards.catalogue import unit_role_equivalents
from randomizer.rewards.display import buff_effect_lines, buff_stack_limit
from randomizer.rewards.dta_definitions import BUFF_TARGETS, REWARD_BY_BUFF_KEY
from randomizer.shop.catalogue import canonical_reward_for_id, shop_catalogue
from randomizer.shop.meta import purchase_permanent_unit
from randomizer.shop.model import PurchaseResult, ShopProfile, ShopRewardType


class ReportedDtaIssuesTest(unittest.TestCase):
    def test_powerhouse_adds_specials_to_reinforcements_only(self):
        sections = {
            'Houses': {'0': 'Nod1', '1': 'Nod2'},
            'Nod1': {'ActsLike': '1'},
            'Nod2': {'ActsLike': '1'},
            'TeamTypes': {'0': 'T1', '1': 'T2', '2': 'T3', '3': 'T4'},
            'T1': {'House': 'Nod1', 'TaskForce': 'F1', 'Reinforce': 'yes'},
            'T2': {'House': 'Nod1', 'TaskForce': 'F2', 'Reinforce': 'yes'},
            'T3': {'House': 'Nod1', 'TaskForce': 'F3'},
            'T4': {'House': 'Nod2', 'TaskForce': 'F4', 'Reinforce': 'yes'},
            'TaskForces': {'0': 'F1', '1': 'F2', '2': 'F3', '3': 'F4'},
            'F1': {'0': '2,E1N'},
            'F2': {'0': '3,E3N'},
            'F3': {'0': '2,LTNK'},
            'F4': {'0': '1,E1N'},
        }
        rules, applications = _team_taskforce_rules(
            sections, installed_effective_sections(True), {'Nod1', 'Nod2'}, 0, 1
        )
        self.assertNotIn('T3', rules)
        cloned = [rules[rules[team]['TaskForce']] for team in ('T1', 'T2', 'T4')]
        self.assertEqual(
            {
                force[key].split(',')[-1]
                for force in cloned for key in ('1', '2')
            },
            {'AIPLSM', 'AISCRINTNK', 'ILHEMOTH'},
        )
        self.assertTrue(all(force['1'] != force['2'] for force in cloned))
        self.assertEqual(
            [int(next(value for value in force.values() if value.endswith(unit)).split(',')[0])
             for force, unit in zip(cloned, (',E1N', ',E3N', ',E1N'))],
            [2, 3, 1],
        )
        self.assertEqual(sum(item[4] == 'TaskForce special unit' for item in applications), 6)

    def test_powerhouse_rotates_only_each_factions_specials(self):
        pools = {
            0: {'AIHTNK', 'AIXO', 'CARRTRUK'},
            1: {'AIPLSM', 'AISCRINTNK', 'ILHEMOTH'},
            2: {'TTNKMSL', 'AIBFRT', 'BRIG'},
            3: {'AI4TNK', 'AIBEHEMOTH', 'BEHEPLSM'},
        }
        sections = {'TeamTypes': {}, 'TaskForces': {}}
        for faction in pools:
            house = f'House{faction}'
            sections[house] = {'ActsLike': str(faction)}
            for index in range(3):
                team, force = f'T{faction}_{index}', f'F{faction}_{index}'
                sections['TeamTypes'][team] = team
                sections['TaskForces'][force] = force
                sections[team] = {
                    'House': house, 'TaskForce': force, 'Reinforce': 'yes',
                }
                sections[force] = {'0': '2,E1N'}
        rules, _ = _team_taskforce_rules(
            sections, installed_effective_sections(True),
            {f'House{faction}' for faction in pools}, 0, 1,
        )
        for faction, expected in pools.items():
            chosen = [
                {
                    rules[rules[f'T{faction}_{index}']['TaskForce']][key].split(',')[-1]
                    for key in ('1', '2')
                }
                for index in range(3)
            ]
            self.assertTrue(all(len(pair) == 2 for pair in chosen))
            self.assertEqual(set().union(*chosen), expected)

    def test_powerhouse_reinforces_existing_special_only_teams(self):
        for faction, original in ((1, 'AIPLSM'), (2, 'TTNKMSL')):
            with self.subTest(original=original):
                sections = {
                    'Enemy': {'ActsLike': str(faction)},
                    'TeamTypes': {'0': 'T1'},
                    'TaskForces': {'0': 'F1'},
                    'T1': {'House': 'Enemy', 'TaskForce': 'F1', 'Reinforce': 'yes'},
                    'F1': {'0': f'1,{original}'},
                }
                rules, applications = _team_taskforce_rules(
                    sections, installed_effective_sections(True), {'Enemy'}, 0, 1
                )
                members = rules[rules['T1']['TaskForce']]
                self.assertEqual(
                    sum(int(value.split(',')[0]) for value in members.values()), 3
                )
                self.assertEqual(
                    len({value.split(',')[-1] for value in members.values()}), len(members)
                )
                self.assertEqual(len(applications), 2)

    def test_powerhouse_reuses_air_and_naval_types_and_skips_mcv_transports(self):
        sections = {
            'Nod': {'ActsLike': '1'},
            'TeamTypes': {str(index): f'T{index}' for index in range(1, 8)},
            'TaskForces': {str(index): f'F{index}' for index in range(1, 8)},
            'Actions': {'0': '1,80,0,T7,0,0,0,0,A'},
        }
        for index, unit in enumerate(('HELI', 'BOAT', 'GMCV', 'TRAN', 'SLST', 'E1N'), 1):
            sections[f'T{index}'] = {
                'House': 'Nod', 'TaskForce': f'F{index}', 'Reinforce': 'yes',
            }
            sections[f'F{index}'] = {'0': f'2,{unit}'}
        sections['T7'] = {'House': 'Nod', 'TaskForce': 'F7'}
        sections['F7'] = {'0': '1,E1N', '1': '2,HELI'}
        rules, applications = _team_taskforce_rules(
            sections, installed_effective_sections(True), {'Nod'}, 0, 1
        )
        for index, unit in ((1, 'HELI'), (2, 'BOAT')):
            clone = rules[rules[f'T{index}']['TaskForce']]
            self.assertEqual(clone['0'], f'3,{unit}')
            self.assertEqual(len(clone), 1)
        for index in (3, 4, 5):
            self.assertNotIn(f'T{index}', rules)
        land_clone = rules[rules['T6']['TaskForce']]
        self.assertEqual(land_clone['0'], '2,E1N')
        self.assertEqual(len({land_clone['1'], land_clone['2']}), 2)
        self.assertTrue(all(
            land_clone[key] in {'1,AIPLSM', '1,AISCRINTNK', '1,ILHEMOTH'}
            for key in ('1', '2')
        ))
        mixed_clone = rules[rules['T7']['TaskForce']]
        self.assertEqual(mixed_clone, {'0': '1,E1N', '1': '3,HELI'})
        self.assertEqual(len(applications), 5)
        regional_rules, _ = _team_taskforce_rules(
            sections, installed_effective_sections(True), {'Nod'}, 1, 0
        )
        self.assertEqual(
            regional_rules[regional_rules['T1']['TaskForce']]['0'], '3,HELI'
        )
        self.assertNotIn('T2', regional_rules)

    def test_flamethrowers_are_independent_shop_units(self):
        self.assertEqual(unit_role_equivalents('E4'), {'E4'})
        self.assertEqual(unit_role_equivalents('E4S'), {'E4S'})
        entries = shop_catalogue()
        rewards = [
            canonical_reward_for_id(next(
                entry.reward_id for entry in entries
                if entry.target_id == unit and entry.reward_type is ShopRewardType.UNIT_ACCESS
            ))
            for unit in ('E4', 'E4S')
        ]
        profile = ShopProfile(meta_coins=1000)
        first = purchase_permanent_unit(profile, rewards[0], price=1)
        second = purchase_permanent_unit(first.profile, rewards[1], price=1)
        self.assertEqual(first.validation.result, PurchaseResult.OK)
        self.assertEqual(second.validation.result, PurchaseResult.OK)

    def test_sensor_display_matches_installed_engine_key_and_range_is_offered(self):
        sensor = REWARD_BY_BUFF_KEY[('E1A', 'sensors')]
        self.assertIn('adjacent cells', buff_effect_lines(sensor, 1)[0])
        self.assertNotIn('SensorsSight', installed_effective_sections(True)['E1A'])
        mission = {'code': 'M_CR7', 'scenario': 'Maps/Missions/cr07.map', 'required_addon': True}
        rules, _report = unit_specific_buff_rules(mission, [sensor])
        self.assertEqual(rules['E1A_PLAYER']['Sensors'], 'yes')
        self.assertNotIn('SensorsSight', rules['E1A_PLAYER'])
        for record in techno_catalogue():
            target = BUFF_TARGETS.get(record['id'])
            if not record['rewardable'] or target is None or record['id'] == 'DTRK':
                continue
            safe_weapon = any(
                weapon.get('buff_safe', True) and weapon.get('range', 0) > 0
                for weapon in target.get('weapons', {}).values()
            )
            if safe_weapon:
                self.assertIn((record['id'], 'range'), REWARD_BY_BUFF_KEY)
        range_reward = REWARD_BY_BUFF_KEY[('E1A', 'range')]
        rules, _report = unit_specific_buff_rules(mission, [range_reward])
        weapon = rules['E1A_PLAYER']['Primary']
        self.assertGreater(float(rules[weapon]['Range']), BUFF_TARGETS['E1A']['weapons']['M1Carbine']['range'])

    def test_snowhopper_spy_and_mercurial_original_scripts(self):
        snowhopper = {'code': 'M_CR7', 'scenario': 'Maps/Missions/cr07.map', 'required_addon': True}
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'spawnmap.ini'
            prepare_spawn_map(snowhopper, 1, output_path=output)
            generated = ini_sections(output)
            self.assertEqual(generated['SPY']['Disguised'], 'yes')
            self.assertEqual(generated['AI']['AIDetectDisguise'], 'no')
            rules, _report = unit_specific_buff_rules(
                snowhopper, [REWARD_BY_BUFF_KEY[('SPY', 'sensors')]],
                rule_overlays=mission_runtime_fixes(snowhopper),
            )
            self.assertEqual(rules['SPY_PLAYER']['Disguised'], 'yes')

            mercurial = {'code': 'M_SE10', 'scenario': 'Maps/Missions/se10.map', 'required_addon': True}
            isolation, report = player_production_isolation_rules(mercurial)
            self.assertFalse(report['isolation_error'])
            self.assertEqual([item['house'] for item in report['isolated_houses']], ['Nod'])
            self.assertEqual(report['production_house'], 'Nod1')
            player_rules, player_report = unit_specific_buff_rules(
                mercurial, [REWARD_BY_BUFF_KEY[('E1', 'sensors')]],
                production_context=report, rule_overlays=isolation,
            )
            self.assertTrue(any(item['unit'] == 'E1' for item in player_report['applied']))
            self.assertEqual(player_rules['E1_PLAYER']['Sensors'], 'yes')
            prepare_spawn_map(mercurial, 1, extra_rules=isolation, output_path=output)
            original = ini_sections('../Maps/Missions/se10.map')
            generated = ini_sections(output)
            self.assertEqual(generated['Nod']['ActsLike'], '7')
            for house in (
                'KorkutLeft', 'KorkutRight', 'KorkutTemple',
                'KorkutAlly1', 'KorkutAlly2', 'KorkutAlly3',
                'KorkutAlly4', 'KorkutCenterFront', 'KorkutCenterBack',
            ):
                self.assertEqual(generated[house]['ActsLike'], original[house]['ActsLike'])
            for section in ('AITriggerTypes', 'AITriggerTypesEnable', 'TeamTypes', 'TaskForces'):
                self.assertEqual(generated[section], original[section])
            for trigger in ('01000078', '01000080', '01000082', '01000086'):
                for section in ('Triggers', 'Events', 'Actions'):
                    self.assertEqual(generated[section][trigger], original[section][trigger])

    def test_reload_stacks_always_improve_and_mcv_shows_both_rulesets(self):
        reload_reward = REWARD_BY_BUFF_KEY[('LTNKCRUS', 'reload')]
        limit = buff_stack_limit(reload_reward)
        self.assertGreater(limit, 19)
        for stack in range(1, limit + 1):
            self.assertLess(stacked_weapon_rof(70, stack), stacked_weapon_rof(70, stack - 1))
        text = buff_effect_lines(REWARD_BY_BUFF_KEY[('GMCV', 'cost')], 1)[0]
        self.assertIn('2,000 [2,500] credits (Enhanced)', text)
        self.assertIn('4,000 [5,000] credits (Classic)', text)
        mission = {
            'code': 'M_SE1', 'scenario': 'Maps/Missions/se01.map',
            'required_addon': True,
        }
        rules, report = unit_specific_buff_rules(
            mission, [REWARD_BY_BUFF_KEY[('NMCV', 'cost')]]
        )
        mcv = next(item for item in report['applied'] if item['unit'] == 'NMCV')
        self.assertEqual(rules[mcv['output_type']]['Cost'], '2000')


if __name__ == '__main__':
    unittest.main()
