"""Player-only Demolition Truck Shop blast reward regressions."""

import tempfile
import unittest
from pathlib import Path

from randomizer.dta.clones import unit_specific_buff_rules
from randomizer.dta.demolition import (
    PLAYER_BLAST_ANIMATION,
    PLAYER_BLAST_AREA_ANIMATION,
    demolition_blast_values,
)
from randomizer.dta.maps import prepare_spawn_map
from randomizer.dta.powers import ensure_power_runtime_types
from randomizer.dta.rules import ini_sections
from randomizer.rewards.catalogue import REWARD_BY_BUFF_KEY, REWARD_POOL
from randomizer.rewards.display import buff_effect_lines
from randomizer.shop.catalogue import canonical_reward_for_id, shop_catalogue
from randomizer.shop.meta import purchase_permanent_buff
from randomizer.shop.model import PurchaseResult, ShopProfile, ShopRewardType


MISSION = {
    'code': 'M_CR7',
    'scenario': 'Maps/Missions/cr07.map',
    'required_addon': True,
}


class DemolitionTruckBuffTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.access = next(
            reward for reward in REWARD_POOL
            if reward.get('unit') == 'DTRK'
            and reward.get('dta_production_access')
        )
        cls.damage = REWARD_BY_BUFF_KEY['DTRK', 'damage']
        cls.area = REWARD_BY_BUFF_KEY['DTRK', 'area']

    def test_both_blast_upgrades_are_purchasable_and_display_real_effects(self):
        entries = [
            entry for entry in shop_catalogue()
            if entry.target_id == 'DTRK'
            and entry.reward_type is ShopRewardType.UNIT_BUFF
        ]
        types = {
            canonical_reward_for_id(entry.reward_id).get('buff_type')
            for entry in entries
        }
        self.assertTrue({'damage', 'area'}.issubset(types))
        self.assertNotIn('range', types)
        self.assertIn('Blast damage 10 [9]', buff_effect_lines(self.damage)[0])
        self.assertIn('Blast radius 0.89 [0.39] cells', buff_effect_lines(self.area)[0])

        profile = ShopProfile(
            meta_coins=100,
            permanent_unit_unlocks=(self.access['name'],),
        )
        for reward in (self.damage, self.area):
            purchase = purchase_permanent_buff(profile, reward, price=10)
            self.assertEqual(purchase.validation.result, PurchaseResult.OK)
            profile = purchase.profile
        self.assertEqual(len(profile.permanent_buffs), 2)

    def test_only_player_clone_uses_buffed_blast(self):
        rules, report = unit_specific_buff_rules(
            MISSION,
            [
                self.access, self.damage, self.area,
                {'kind': 'buff', 'unit': 'DTRK', 'buff_type': 'range'},
            ],
            access_randomized=True,
            allow_foreign_factory_access=True,
            buff_allied_helpers=True,
        )
        applied = next(
            entry for entry in report['applied'] if entry['unit'] == 'DTRK'
        )
        clone = rules[applied['output_type']]
        self.assertNotEqual(applied['output_type'], 'DTRK')
        self.assertEqual(applied['buffs'], {'damage': 1, 'area': 1})
        self.assertEqual(clone['Primary'], 'Suicide')
        self.assertEqual(clone['Explosion'], PLAYER_BLAST_ANIMATION)
        self.assertEqual(clone['ScrapExplosion'], PLAYER_BLAST_ANIMATION)
        self.assertEqual(clone['Buildability'], 'HumanOnly')
        self.assertEqual(applied['allied_helper_routes'], [])
        self.assertNotIn('Explosion', rules.get('DTRK', {}))
        self.assertIn(applied['output_type'], rules['VehicleTypes'].values())

        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'spawnmap.ini'
            prepare_spawn_map(MISSION, 1, extra_rules=rules, output_path=output)
            generated = ini_sections(output)
            self.assertEqual(
                generated[applied['output_type']]['Explosion'],
                PLAYER_BLAST_ANIMATION,
            )

        art = report['_runtime_art']
        self.assertEqual(art[PLAYER_BLAST_ANIMATION]['Spawns'], PLAYER_BLAST_AREA_ANIMATION)
        self.assertEqual(art[PLAYER_BLAST_AREA_ANIMATION]['Damage'], '10')
        self.assertEqual(art[PLAYER_BLAST_AREA_ANIMATION]['DamageRadius'], '228')
        self.assertEqual(demolition_blast_values(), (9, 100))

    def test_runtime_art_registration_and_cleanup(self):
        _rules, report = unit_specific_buff_rules(
            MISSION,
            [self.access, self.area],
            access_randomized=True,
            allow_foreign_factory_access=True,
        )
        art = report['_runtime_art']
        self.assertEqual(art[PLAYER_BLAST_AREA_ANIMATION]['Damage'], '9')
        self.assertEqual(art[PLAYER_BLAST_AREA_ANIMATION]['DamageRadius'], '228')
        with tempfile.TemporaryDirectory() as folder:
            rules_path = Path(folder) / 'Rules.ini'
            art_path = Path(folder) / 'Art.ini'
            rules_path.write_text('[Weapons]\n1=Suicide\n', encoding='cp1252')
            art_path.write_text('[Animations]\n1=DEMONUKE\n', encoding='cp1252')
            ensure_power_runtime_types(
                {}, art, rules_path=rules_path, art_path=art_path
            )
            installed = ini_sections(art_path)
            self.assertIn(PLAYER_BLAST_ANIMATION, installed['Animations'].values())
            self.assertIn(PLAYER_BLAST_AREA_ANIMATION, installed['Animations'].values())
            self.assertEqual(installed[PLAYER_BLAST_AREA_ANIMATION]['DamageRadius'], '228')
            ensure_power_runtime_types(
                {}, {}, rules_path=rules_path, art_path=art_path
            )
            cleaned = ini_sections(art_path)
            self.assertEqual(cleaned['Animations'], {'1': 'DEMONUKE'})
            self.assertNotIn(PLAYER_BLAST_AREA_ANIMATION, cleaned)


if __name__ == '__main__':
    unittest.main()
