"""Regression checks for staged and independently tuned self-healing buffs."""

import copy
from collections import Counter
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from randomizer.config.player import DEFAULT_CONFIG, migrate_loaded_config
from randomizer.config.tuning import BUFF_EFFECTS, stacked_self_heal_rate
from randomizer.dta.clones import _unit_overrides
from randomizer.maps.buff_values import apply_unit_buff_value
from randomizer.rewards.catalogue import BUFF_TARGETS, REWARD_BY_BUFF_KEY
from randomizer.rewards.display import (
    buff_effect_comparison_lines,
    buff_stack_limit,
    canonical_reward,
)


class SelfHealingBuffChecks(unittest.TestCase):
    def test_catalogue_splits_access_cap_and_rate(self):
        machine_gunner = BUFF_TARGETS['MGI']
        self.assertEqual(
            {
                'self_healing',
                'self_healing_cap',
                'self_healing_rate',
            },
            {
                buff_type
                for buff_type in machine_gunner['allowed_buff_types']
                if buff_type.startswith('self_healing')
            },
        )
        self.assertEqual(
            buff_stack_limit(REWARD_BY_BUFF_KEY[('MGI', 'self_healing')]),
            2,
        )
        self.assertEqual(
            buff_stack_limit(REWARD_BY_BUFF_KEY[('MGI', 'self_healing_cap')]),
            1,
        )
        self.assertEqual(
            buff_stack_limit(REWARD_BY_BUFF_KEY[('MGI', 'self_healing_rate')]),
            BUFF_EFFECTS['self_heal_rate']['stack_limit'],
        )

    def test_access_unlocks_veteran_then_rookie_healing(self):
        target = BUFF_TARGETS['MGI']
        veteran = {
            'VeteranAbilities': 'RADAR_INVISIBLE,ROF',
            'EliteAbilities': 'SELF_HEAL,FASTER',
        }
        self.assertTrue(
            apply_unit_buff_value(veteran, target, 'self_healing', 1)
        )
        self.assertEqual(
            veteran['VeteranAbilities'],
            'RADAR_INVISIBLE,ROF,SELF_HEAL',
        )
        self.assertNotIn('SelfHealing', veteran)
        self.assertNotIn('SelfHealingCap', veteran)
        self.assertNotIn('SelfHealingRate', veteran)
        self.assertNotIn('SelfHealingStep', veteran)

        rookie = dict(veteran)
        self.assertTrue(
            apply_unit_buff_value(rookie, target, 'self_healing', 2)
        )
        self.assertEqual(rookie['SelfHealing'], 'yes')
        self.assertEqual(
            rookie['VeteranAbilities'].split(',').count('SELF_HEAL'),
            1,
        )

    def test_cap_and_rate_change_only_their_engine_keys(self):
        target = BUFF_TARGETS['MGI']
        cap = {}
        self.assertTrue(
            apply_unit_buff_value(cap, target, 'self_healing_cap', 1)
        )
        self.assertEqual(cap, {'SelfHealingCap': '100%'})

        rate = {}
        self.assertTrue(
            apply_unit_buff_value(rate, target, 'self_healing_rate', 1)
        )
        self.assertAlmostEqual(
            float(rate['SelfHealingRate']),
            stacked_self_heal_rate(1),
        )
        self.assertLess(
            float(rate['SelfHealingRate']),
            stacked_self_heal_rate(0),
        )
        self.assertNotIn('SelfHealingStep', rate)

        faster_native = {'SelfHealingRate': '0.008'}
        self.assertTrue(apply_unit_buff_value(
            faster_native, target, 'self_healing_rate', 1
        ))
        self.assertAlmostEqual(
            float(faster_native['SelfHealingRate']),
            stacked_self_heal_rate(1, 0.008),
        )

    def test_clone_pipeline_keeps_three_effects_independent(self):
        target = BUFF_TARGETS['MGI']
        values = {
            'VeteranAbilities': 'RADAR_INVISIBLE,ROF',
            'EliteAbilities': 'SELF_HEAL,FASTER',
        }
        veteran = _unit_overrides(
            values, Counter({'self_healing': 1}), target
        )
        self.assertEqual(
            veteran,
            {'VeteranAbilities': 'RADAR_INVISIBLE,ROF,SELF_HEAL'},
        )
        full = _unit_overrides(
            values,
            Counter({
                'self_healing': 2,
                'self_healing_cap': 1,
                'self_healing_rate': 1,
            }),
            target,
        )
        self.assertEqual(full['SelfHealing'], 'yes')
        self.assertEqual(full['SelfHealingCap'], '100%')
        self.assertAlmostEqual(
            float(full['SelfHealingRate']),
            stacked_self_heal_rate(1),
        )
        self.assertNotIn('SelfHealingStep', full)

    def test_native_healers_skip_only_the_access_upgrade(self):
        self.assertNotIn(
            'self_healing', BUFF_TARGETS['HTNK']['allowed_buff_types']
        )
        self.assertIn(
            'self_healing_cap', BUFF_TARGETS['HTNK']['allowed_buff_types']
        )
        self.assertIn(
            'self_healing_rate', BUFF_TARGETS['HTNK']['allowed_buff_types']
        )
        old_mammoth = canonical_reward({
            'name': 'GDI Mammoth Tank (HTNK) Regeneration I',
            'kind': 'buff',
            'unit': 'HTNK',
            'buff_type': 'self_healing',
        })
        self.assertEqual(old_mammoth.get('buff_type'), 'self_healing_cap')
        self.assertEqual(
            {
                'self_healing',
                'self_healing_cap',
                'self_healing_rate',
            },
            {
                buff_type
                for buff_type in BUFF_TARGETS['E1']['allowed_buff_types']
                if buff_type.startswith('self_healing')
            },
        )

    def test_display_names_each_stage_explicitly(self):
        reward = REWARD_BY_BUFF_KEY[('MGI', 'self_healing')]
        self.assertEqual(
            buff_effect_comparison_lines(reward, 0),
            ['Self-healing enabled from Veteran rank'],
        )
        self.assertEqual(
            buff_effect_comparison_lines(reward, 1),
            ['Self-healing enabled from Rookie rank'],
        )

    def test_config_migration_enables_new_split_effects(self):
        config = copy.deepcopy(DEFAULT_CONFIG)
        generation = config['generation']
        generation['unit_buff_catalogue_version'] = 7
        generation['enabled_buff_types'].remove('self_healing_cap')
        generation['enabled_buff_types'].remove('self_healing_rate')
        self.assertTrue(migrate_loaded_config(config))
        self.assertIn('self_healing_cap', generation['enabled_buff_types'])
        self.assertIn('self_healing_rate', generation['enabled_buff_types'])
        self.assertFalse(migrate_loaded_config(config))


if __name__ == '__main__':
    unittest.main()
