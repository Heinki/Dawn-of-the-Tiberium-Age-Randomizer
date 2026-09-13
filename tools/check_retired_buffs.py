"""Check retired upgrades and the restored amphibious vehicle upgrade."""
import copy
from collections import Counter
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from randomizer.config.player import DEFAULT_CONFIG, migrate_loaded_config
from randomizer.core.paths import BATTLE_CLIENT_INI
from randomizer.dta.clones import _unit_overrides, unit_specific_buff_rules
from randomizer.dta.movement import (
    AMPHIBIOUS_DRIVE_OVERRIDES,
    has_water_movement,
)
from randomizer.dta.rules import installed_effective_sections
from randomizer.maps.buff_values import apply_unit_buff_value
from randomizer.missions.catalogue import parse_missions
from randomizer.rewards.catalogue import BUFF_TARGETS, BUFF_TYPES, REWARD_POOL
from randomizer.rewards.display import buff_effect_lines, canonical_reward
from randomizer.shop.catalogue import shop_catalogue


class RetiredBuffChecks(unittest.TestCase):
    def test_not_offered_in_catalogues(self):
        retired = {'opportunity_fire'}
        self.assertTrue(retired.isdisjoint(item['id'] for item in BUFF_TYPES))
        self.assertTrue(retired.isdisjoint(r.get('buff_type') for r in REWARD_POOL))
        self.assertFalse(any('Run-and-Gun' in entry.reward_id for entry in shop_catalogue()))
        self.assertTrue(all(retired.isdisjoint(target.get('allowed_buff_types', ())) for target in BUFF_TARGETS.values()))

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

    def test_saved_amphibious_rewards_are_active_again(self):
        name = 'GDI Mammoth Tank (HTNK) Amphibious Drive I'
        restored = canonical_reward({'name': name})
        self.assertEqual(restored.get('buff_type'), 'amphibious')
        self.assertFalse(restored.get('retired_reward'))
        self.assertEqual(
            buff_effect_lines(restored),
            ['GDI Mammoth Tank: Amphibious movement enabled'],
        )

    def test_amphibious_is_vehicle_only_and_skips_water_capable_units(self):
        self.assertIn('amphibious', BUFF_TARGETS['HTNK']['allowed_buff_types'])
        amphibious_targets = {
            unit_id: target
            for unit_id, target in BUFF_TARGETS.items()
            if 'amphibious' in target.get('allowed_buff_types', ())
        }
        self.assertTrue(amphibious_targets)
        self.assertTrue(all(
            target.get('category') == 'vehicles'
            and not target.get('naval')
            and not has_water_movement(target)
            for target in amphibious_targets.values()
        ))
        for unit_id in ('E1', 'ORCA', 'HVR', 'HVCSAM', 'BOAT', 'ALST'):
            self.assertNotIn(
                'amphibious',
                BUFF_TARGETS[unit_id]['allowed_buff_types'],
                unit_id,
            )

    def test_amphibious_uses_complete_hover_mlrs_movement_structure(self):
        hover_mlrs = installed_effective_sections()['HVCSAM']
        self.assertEqual(
            {
                key: hover_mlrs.get(key)
                for key in AMPHIBIOUS_DRIVE_OVERRIDES
            },
            AMPHIBIOUS_DRIVE_OVERRIDES,
        )
        target = BUFF_TARGETS['HTNK']
        native = {
            'MovementZone': 'Destroyer',
            'SpeedType': 'Track',
            'Locomotor': '{4A582741-9839-11d1-B709-00A024DDAFD1}',
        }
        self.assertEqual(
            {
                key: value
                for key, value in _unit_overrides(
                    native, Counter({'amphibious': 1}), target
                ).items()
                if key in AMPHIBIOUS_DRIVE_OVERRIDES
            },
            AMPHIBIOUS_DRIVE_OVERRIDES,
        )
        generic = dict(native)
        self.assertTrue(
            apply_unit_buff_value(generic, target, 'amphibious', 1)
        )
        self.assertTrue(all(
            generic[key] == value
            for key, value in AMPHIBIOUS_DRIVE_OVERRIDES.items()
        ))

    def test_amphibious_does_not_rewrite_existing_water_movement(self):
        target = BUFF_TARGETS['HTNK']
        native = {
            'MovementZone': 'Fly',
            'SpeedType': 'Hover',
            'Locomotor': '{4A582742-9839-11d1-B709-00A024DDAFD1}',
        }
        self.assertEqual(
            _unit_overrides(
                native, Counter({'amphibious': 1}), target
            ),
            {},
        )
        generic = dict(native)
        self.assertFalse(
            apply_unit_buff_value(generic, target, 'amphibious', 1)
        )
        self.assertEqual(generic, native)

    def test_generated_mammoth_clone_gets_all_three_movement_fields(self):
        mission = next(
            item for item in parse_missions(BATTLE_CLIENT_INI)
            if not item.get('no_build')
        )
        access = next(
            reward for reward in REWARD_POOL
            if reward.get('unit') == 'HTNK'
            and reward.get('dta_production_access')
        )
        amphibious = next(
            reward for reward in REWARD_POOL
            if reward.get('unit') == 'HTNK'
            and reward.get('buff_type') == 'amphibious'
        )
        rules, report = unit_specific_buff_rules(
            mission,
            [access, amphibious],
            access_randomized=True,
        )
        applied = next(
            item for item in report['applied'] if item['unit'] == 'HTNK'
        )
        self.assertEqual(applied['buffs'], {'amphibious': 1})
        self.assertTrue(all(
            rules[applied['output_type']][key] == value
            for key, value in AMPHIBIOUS_DRIVE_OVERRIDES.items()
        ))

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
