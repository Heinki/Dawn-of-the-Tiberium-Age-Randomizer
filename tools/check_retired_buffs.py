"""Check removal of unsupported moving-fire upgrades without changing saves."""
import copy
from collections import Counter
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from randomizer.config.player import DEFAULT_CONFIG, migrate_loaded_config
from randomizer.dta.clones import _unit_overrides
from randomizer.maps.buff_values import apply_unit_buff_value
from randomizer.rewards.catalogue import BUFF_TARGETS, BUFF_TYPES, REWARD_POOL
from randomizer.rewards.display import buff_effect_lines, canonical_reward
from randomizer.shop.catalogue import shop_catalogue


class RetiredBuffChecks(unittest.TestCase):
    def test_not_offered_in_catalogues(self):
        self.assertFalse(any(item['id'] == 'opportunity_fire' for item in BUFF_TYPES))
        self.assertFalse(any(r.get('buff_type') == 'opportunity_fire' for r in REWARD_POOL))
        self.assertFalse(any('Run-and-Gun' in entry.reward_id for entry in shop_catalogue()))
        self.assertTrue(all('opportunity_fire' not in target.get('allowed_buff_types', ()) for target in BUFF_TARGETS.values()))

    def test_saved_and_runtime_rewards_are_inert(self):
        name = 'GDI Mammoth Tank (HTNK) Run-and-Gun I'
        for reward in (
            {'name': name},
            {'name': name, 'kind': 'buff', 'unit': 'HTNK', 'buff_type': 'opportunity_fire'},
            {'kind': 'buff', 'unit': 'HTNK', 'buff_type': 'opportunity_fire', '_runtime_canonical': True},
        ):
            original = copy.deepcopy(reward)
            retired = canonical_reward(reward)
            self.assertTrue(retired.get('retired_reward'))
            self.assertEqual(retired.get('rules'), {})
            self.assertEqual(buff_effect_lines(reward), [])
            self.assertEqual(reward, original)

    def test_config_migration_does_not_restore_removed_buff(self):
        config = copy.deepcopy(DEFAULT_CONFIG)
        generation = config['generation']
        generation['unit_buff_catalogue_version'] = 4
        generation['enabled_buff_types'] += ['opportunity_fire']
        generation['reward_weights']['unit_buffs']['opportunity_fire'] = 100
        self.assertTrue(migrate_loaded_config(config))
        self.assertNotIn('opportunity_fire', generation['enabled_buff_types'])
        self.assertNotIn('opportunity_fire', generation['reward_weights']['unit_buffs'])
        self.assertIn('area', generation['enabled_buff_types'])
        self.assertIn('amphibious', generation['enabled_buff_types'])
        self.assertFalse(migrate_loaded_config(config))

    def test_native_ability_is_not_modified(self):
        target = BUFF_TARGETS['HTNK']
        counts = Counter({'opportunity_fire': 1})
        for native in ({'OpportunityFire': 'yes', 'NoMovingFire': 'no'}, {'OpportunityFire': 'no', 'NoMovingFire': 'yes'}):
            values = dict(native)
            self.assertFalse(apply_unit_buff_value(values, target, 'opportunity_fire', 1))
            self.assertEqual(values, native)
            overrides = _unit_overrides(values, counts, target)
            self.assertNotIn('OpportunityFire', overrides)
            self.assertNotIn('NoMovingFire', overrides)


if __name__ == '__main__':
    unittest.main()
