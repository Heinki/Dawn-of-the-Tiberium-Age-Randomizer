"""Regression checks for Shop role entitlements and the retired DTA thief."""

import unittest

from randomizer.application.shop_controller import ShopController
from randomizer.dta.rules import techno_catalogue
from randomizer.generation.reward_controller import RewardGeneration
from randomizer.rewards.catalogue import REWARD_POOL
from randomizer.rewards.display import unit_buff_counts
from randomizer.rewards.rules import (
    expand_equivalent_role_access,
    expand_equivalent_role_buffs,
    tech_ids_for_rewards,
)
from randomizer.shop.active import active_shop_rewards, role_buff_stack_count
from randomizer.shop.catalogue import canonical_reward_for_id, shop_catalogue
from randomizer.shop.config import SHOP_CONFIG
from randomizer.shop.economy import permanent_buff_price, permanent_unit_price
from randomizer.shop.meta import purchase_permanent_buff, purchase_permanent_unit
from randomizer.shop.model import (
    MissionEconomyClass,
    MissionOffer,
    BuffPurchase,
    PurchaseResult,
    ShopProfile,
    ShopRun,
    ShopRewardType,
    RunStatus,
)
from randomizer.shop.purchases import validate_run_purchase
from randomizer.shop.transitions import start_new_run


class ShopEquivalentUnitsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = shop_catalogue()

    @classmethod
    def entry(cls, unit_id, reward_type, buff_type=None):
        return next(
            entry for entry in cls.entries
            if entry.target_id == unit_id
            and entry.reward_type is reward_type
            and (
                buff_type is None
                or canonical_reward_for_id(entry.reward_id).get('buff_type')
                == buff_type
            )
        )

    def test_thief_is_not_rewardable(self):
        thief = next(
            record for record in techno_catalogue()
            if record['id'] == 'THIEF'
        )
        self.assertFalse(thief['rewardable'])
        self.assertFalse(any(item.get('unit') == 'THIEF' for item in REWARD_POOL))
        self.assertFalse(any(entry.target_id == 'THIEF' for entry in self.entries))

    def test_one_purchase_entitles_peer_buff_and_shared_cap(self):
        minigunner = self.entry('E1', ShopRewardType.UNIT_ACCESS)
        rifleman = self.entry('E1A', ShopRewardType.UNIT_ACCESS)
        minigunner_damage = self.entry('E1', ShopRewardType.UNIT_BUFF, 'damage')
        rifleman_damage = self.entry('E1A', ShopRewardType.UNIT_BUFF, 'damage')
        profile = purchase_permanent_unit(
            ShopProfile(meta_coins=500),
            canonical_reward_for_id(minigunner.reward_id),
            price=permanent_unit_price('E1'),
        ).profile
        duplicate = purchase_permanent_unit(
            profile,
            canonical_reward_for_id(rifleman.reward_id),
            price=permanent_unit_price('E1A'),
        )
        self.assertEqual(duplicate.validation.result, PurchaseResult.ALREADY_OWNED)

        peer_reward = canonical_reward_for_id(rifleman_damage.reward_id)
        purchase = purchase_permanent_buff(
            profile, peer_reward, price=permanent_buff_price('E1A')
        )
        self.assertEqual(purchase.validation.result, PurchaseResult.OK)
        self.assertEqual(
            role_buff_stack_count(
                (peer_reward,), canonical_reward_for_id(minigunner_damage.reward_id)
            ),
            1,
        )
        profile = purchase.profile
        for _ in range(rifleman_damage.stack_limit - 1):
            profile = purchase_permanent_buff(
                profile,
                canonical_reward_for_id(minigunner_damage.reward_id),
                price=permanent_buff_price('E1'),
            ).profile
        capped = purchase_permanent_buff(
            profile, peer_reward, price=permanent_buff_price('E1A')
        )
        self.assertEqual(capped.validation.result, PurchaseResult.MAX_STACKS)
        active_buffs = [
            canonical_reward_for_id(item.reward_id)
            for item in profile.permanent_buffs
            for _ in range(item.stacks)
        ]
        self.assertEqual(
            unit_buff_counts(
                expand_equivalent_role_buffs(active_buffs, enabled=True),
                'E1A',
            )['damage'],
            rifleman_damage.stack_limit,
        )

    def test_cross_faction_loadout_and_buff(self):
        minigunner = self.entry('E1', ShopRewardType.UNIT_ACCESS)
        damage = self.entry('E1', ShopRewardType.UNIT_BUFF, 'damage')
        profile = ShopProfile(permanent_unit_unlocks=(minigunner.reward_id,))
        transition = start_new_run(
            profile,
            run_id='role-test',
            seed='role-test',
            mission_offers=(
                MissionOffer('M_SE1', MissionEconomyClass.ACT_1),
            ),
            campaign_filter='All Campaigns',
            reward_mode='Chaos',
            reward_settings={'shop_faction_filter': 'Allies'},
            selected_reward_ids=(minigunner.reward_id,),
            permanent_entitlement_ids=(minigunner.reward_id,),
        )
        run = transition.run
        self.assertIn(minigunner.reward_id, run.selected_permanent_units)
        active = active_shop_rewards(run)
        expanded = expand_equivalent_role_access(active, REWARD_POOL, enabled=True)
        collapsed = RewardGeneration.chaos_equivalent_access_pool(
            expanded, ('Allies',)
        )
        self.assertIn('E1A', tech_ids_for_rewards(collapsed))
        self.assertNotIn('E1', tech_ids_for_rewards(collapsed))

        rifleman_damage = self.entry('E1A', ShopRewardType.UNIT_BUFF, 'damage')
        validation = validate_run_purchase(
            canonical_reward_for_id(rifleman_damage.reward_id),
            price=1,
            run_coins=10,
            active_tech_ids=('E1',),
            active_equivalent_tech_ids=('E1', 'E1A'),
        )
        self.assertEqual(validation.result, PurchaseResult.OK)
        expanded_buffs = expand_equivalent_role_buffs(
            [canonical_reward_for_id(damage.reward_id)], enabled=True
        )
        self.assertEqual(
            {reward['unit'] for reward in expanded_buffs}, {'E1', 'E1A'}
        )

    def test_owned_loadout_shows_peer_and_selects_one_entitlement(self):
        class Value:
            def __init__(self, value=''):
                self.value = value

            def get(self):
                return self.value

            def set(self, value):
                self.value = value

        class Widget:
            def __init__(self):
                self.rows = {}

            def get_children(self):
                return tuple(self.rows)

            def delete(self, *items):
                for item in items:
                    self.rows.pop(item, None)

            def insert(self, _parent, _position, **options):
                self.rows[options['iid']] = options

            def configure(self, **_options):
                pass

        minigunner = self.entry('E1', ShopRewardType.UNIT_ACCESS)
        rifleman = self.entry('E1A', ShopRewardType.UNIT_ACCESS)
        controller = ShopController()
        controller.shop_config = SHOP_CONFIG
        controller.shop_profile = ShopProfile(
            permanent_unit_unlocks=(minigunner.reward_id,)
        )
        controller.shop_run = ShopRun(
            run_id='role-test', seed='role-test', status=RunStatus.COMPLETED,
            stage=1, run_length=10, run_coins=0,
            selected_permanent_units=(minigunner.reward_id,),
        )
        controller._shop_unit_entries = tuple(
            entry for entry in self.entries
            if entry.reward_type is ShopRewardType.UNIT_ACCESS
        )
        controller._shop_power_entries = ()
        controller._shop_entry_by_reward_id = {
            entry.reward_id: entry for entry in self.entries
        }
        controller.shop_loadout_select_tree = Widget()
        controller.shop_loadout_help_var = Value()
        controller.shop_setup_search_var = Value()
        controller.shop_permanent_units_without_buffs_check = Widget()
        controller.shop_modifier_status_var = Value()
        controller.shop_modifier_vars = {}
        controller.shop_modifier_button_by_id = {}
        controller._shop_pending_loadout_selection = set()
        controller._shop_loadout_selection_initialized = False
        controller.archipelago_shop_context = lambda: (None, ())
        controller.shop_campaign_filter = lambda: 'Allies'
        controller._prepare_shop_unit_cameos = lambda _items: {}
        controller._refresh_shop_modifier_difficulty = lambda: None

        controller._refresh_shop_setup()
        rows = controller.shop_loadout_select_tree.rows
        peer_row = next(
            row for row in rows.values()
            if row['values'][1] == rifleman.reward_id
        )
        self.assertEqual(peer_row['values'][0], '✓ Selected')
        self.assertEqual(peer_row['values'][3], 'Equivalent Unit')
        self.assertEqual(
            controller._shop_loadout_rows[peer_row['iid']],
            minigunner.reward_id,
        )
        self.assertEqual(
            controller._shop_pending_loadout_selection, {minigunner.reward_id}
        )

    def test_starter_uses_mission_faction_variant(self):
        controller = ShopController()
        controller._shop_launch_run = ShopRun(
            run_id='role-test', seed='role-test', status=RunStatus.ACTIVE,
            stage=1, run_length=10, run_coins=0,
            selected_mission_code='M_SE1',
            starting_unit_ids=('E1',),
            starting_defense_ids=('GUN',),
        )
        controller.reward_factions_for_code = lambda _code: {'Allies'}
        self.assertEqual(controller.active_starting_tier_one_unit_ids(), ['E1A'])
        self.assertEqual(
            controller._shop_mission_local_starters(
                ('GUN',), controller._shop_launch_run
            ),
            ['RAGUN'],
        )

    def test_active_loadout_shows_peer_buff(self):
        class Tree:
            def __init__(self):
                self.rows = {}

            def get_children(self):
                return tuple(self.rows)

            def delete(self, *items):
                for item in items:
                    self.rows.pop(item, None)

            def insert(self, _parent, _position, **options):
                self.rows[options['iid']] = options

            def configure(self, **_options):
                pass

        minigunner = self.entry('E1', ShopRewardType.UNIT_ACCESS)
        rifleman = self.entry('E1A', ShopRewardType.UNIT_ACCESS)
        damage = self.entry('E1', ShopRewardType.UNIT_BUFF, 'damage')
        controller = ShopController()
        controller.shop_profile = ShopProfile(
            permanent_unit_unlocks=(minigunner.reward_id,)
        )
        controller.shop_run = ShopRun(
            run_id='role-test', seed='role-test', status=RunStatus.ACTIVE,
            stage=1, run_length=10, run_coins=0,
            selected_permanent_units=(minigunner.reward_id,),
            permanent_buffs_snapshot=(BuffPurchase(damage.reward_id),),
        )
        controller.shop_loadout_tree = Tree()
        controller.shop_loadout_upgrade_button = Tree()
        controller.shop_loadout_search_var = type(
            'Search', (), {'get': lambda self: ''}
        )()
        controller._shop_entry_by_reward_id = {
            entry.reward_id: entry for entry in self.entries
        }
        controller._shop_unit_entries = tuple(
            entry for entry in self.entries
            if entry.reward_type is ShopRewardType.UNIT_ACCESS
        )
        controller._shop_buff_entries = tuple(
            entry for entry in self.entries
            if entry.reward_type is ShopRewardType.UNIT_BUFF
        )
        controller._shop_power_buff_entries = ()
        controller._clear_shop_tree_buttons = lambda _name: None
        controller._rebuild_shop_loadout_upgrade_buttons = lambda: None
        controller._prepare_shop_unit_cameos = lambda _items: {}
        controller._shop_unit_base_stats = lambda _unit_id: ''

        controller._refresh_shop_loadout()
        peer_row = next(
            row for row in controller.shop_loadout_tree.rows.values()
            if row['values'][1] == rifleman.reward_id
        )
        self.assertIn('effects', peer_row['values'][2])
        self.assertIn(
            'Permanent ×1: Rifle Infantry:',
            controller._shop_loadout_details[peer_row['iid']],
        )


if __name__ == '__main__':
    unittest.main()
