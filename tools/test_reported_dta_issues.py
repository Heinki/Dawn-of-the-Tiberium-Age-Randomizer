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
    def test_powerhouse_adds_normal_units_without_special_swarm(self):
        sections = {
            'Houses': {'0': 'Nod1', '1': 'Nod2'},
            'Nod1': {'ActsLike': '1'},
            'Nod2': {'ActsLike': '1'},
            'TeamTypes': {'0': 'T1', '1': 'T2', '2': 'T3', '3': 'T4'},
            'T1': {'House': 'Nod1', 'TaskForce': 'F1'},
            'T2': {'House': 'Nod1', 'TaskForce': 'F2'},
            'T3': {'House': 'Nod1', 'TaskForce': 'F3'},
            'T4': {'House': 'Nod2', 'TaskForce': 'F4'},
            'TaskForces': {'0': 'F1', '1': 'F2', '2': 'F3', '3': 'F4'},
            'F1': {'0': '2,E1N'},
            'F2': {'0': '3,E3N'},
            'F3': {'0': '2,LTNK'},
            'F4': {'0': '1,E1N'},
        }
        rules, applications = _team_taskforce_rules(
            sections, installed_effective_sections(True), {'Nod1', 'Nod2'}, 0, 1
        )
        cloned = [rules[rules[team]['TaskForce']] for team in ('T1', 'T2', 'T3', 'T4')]
        all_members = [value for force in cloned for value in force.values()]
        self.assertEqual(sum(value.endswith(',AIPLSM') for value in all_members), 1)
        self.assertEqual(
            [int(next(value for value in force.values() if value.endswith(unit)).split(',')[0])
             for force, unit in zip(cloned, (',E1N', ',E3N', ',LTNK', ',E1N'))],
            [3, 4, 3, 2],
        )
        self.assertEqual(sum(item[4] == 'TaskForce normal unit count' for item in applications), 4)

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
