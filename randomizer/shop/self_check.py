"""Focused non-invasive validation for DTA Shop Mode."""

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from randomizer.core.paths import BATTLE_CLIENT_INI
from randomizer.missions.catalogue import parse_missions
from randomizer.rewards.catalogue import canonical_reward
from randomizer.rewards.weights import UNIT_BUFF_WEIGHT_TYPES

from .active import (
    active_shop_power_ids,
    active_shop_rewards,
    active_shop_tech_ids,
    shop_starter_defense_ids,
    shop_starter_unit_ids,
)
from .catalogue import (
    canonical_reward_for_id,
    shop_catalogue,
    shop_entry_available,
)
from .config import SHOP_CONFIG
from .missions_self_check import validate_shop_mission_selection
from .economy import (
    discounted_shop_price,
    mission_reward,
    permanent_buff_price,
    permanent_power_buff_price,
    permanent_power_price,
    permanent_unit_price,
    run_buff_price,
    run_unit_price,
    starting_run_coins,
)
from .meta import (
    purchase_permanent_buff,
    purchase_permanent_power,
    validate_starting_loadout,
)
from .mission_modifiers import (
    CHALLENGE_MODIFIERS,
    PLAYER_BOON_MODIFIERS,
    mission_modifier_for_run_offer,
)
from .missions import (
    classify_mission,
    generate_mission_offers,
    mission_difficulty,
    mission_difficulty_weights_for_stage,
)
from .model import (
    MissionEconomyClass,
    PurchaseResult,
    RunStatus,
    ShopProfile,
    ShopRewardType,
)
from .modifiers import (
    modifier_allows_faction_pool,
    modifier_allows_loadout_entry,
    modifier_allows_shop_offer,
    modifier_effects,
    modifier_forces_hardest_difficulty,
    modifier_shop_faction,
)
from .persistence import ShopPersistencePaths, ShopRepository
from .service import ShopProgressionService
from .state import normalize_shop_run
from .transitions import (
    ShopTransitionError,
    apply_mission_victory,
    commit_selected_mission,
    start_new_run,
)


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def validate_shop_domain():
    """Validate DTA catalogue, missions, economy, state, and persistence."""
    selection_checks = validate_shop_mission_selection()
    for check, valid in selection_checks.items():
        _require(valid, f'Shop mission selection failed: {check}')
    missions = parse_missions(BATTLE_CLIENT_INI)
    classes = {classify_mission(mission) for mission in missions}
    _require(
        classes == set(MissionEconomyClass),
        f'Shop mission classes incomplete: {sorted(item.value for item in classes)}',
    )
    early_campaigns = {
        mission['campaign']
        for mission in missions
        if classify_mission(mission) is MissionEconomyClass.ACT_1
    }
    _require(
        {
            'Tutorial', 'Shadow Exodus', 'PTTP', 'CR',
            'Toxic Diversion', 'It Came From Red Alert!',
            'Creeping Destruction',
        }.issubset(early_campaigns),
        'Shop opening classes do not cover every numbered campaign',
    )
    first_offers = generate_mission_offers(
        missions, run_seed='DTA-SHOP-SELF-CHECK', stage=1
    )
    repeated_offers = generate_mission_offers(
        missions, run_seed='DTA-SHOP-SELF-CHECK', stage=1
    )
    _require(first_offers == repeated_offers, 'Shop mission offers are not deterministic')
    _require(
        len(first_offers) == SHOP_CONFIG.mission_offer_count,
        'Shop opening offer count is incorrect',
    )
    _require(
        len({offer.mission_code for offer in first_offers}) == len(first_offers),
        'Shop opening contains duplicate missions',
    )
    first_difficulties = tuple(
        mission_difficulty(
            'DTA-SHOP-SELF-CHECK', 1, offer.mission_code
        )
        for offer in first_offers
    )
    _require(
        first_difficulties == tuple(
            mission_difficulty(
                'DTA-SHOP-SELF-CHECK', 1, offer.mission_code
            )
            for offer in first_offers
        ),
        'Shop mission difficulties are not deterministic',
    )
    early_difficulties = {
        name for name, weight in mission_difficulty_weights_for_stage(1).items()
        if weight
    }
    final_difficulties = {
        name for name, weight in mission_difficulty_weights_for_stage(
            SHOP_CONFIG.run_length
        ).items()
        if weight
    }
    _require(
        early_difficulties == {'Easy', 'Normal'},
        'DTA Shop opening difficulties are incorrect',
    )
    _require(
        final_difficulties == {'Extreme', 'Ultimate', 'Impossible'},
        'DTA Shop finale difficulties are incorrect',
    )

    catalogue = shop_catalogue()
    unit_access = [
        entry for entry in catalogue
        if entry.reward_type is ShopRewardType.UNIT_ACCESS
    ]
    unit_buffs = [
        entry for entry in catalogue
        if entry.reward_type is ShopRewardType.UNIT_BUFF
    ]
    power_access = [
        entry for entry in catalogue
        if entry.reward_type is ShopRewardType.POWER_ACCESS
    ]
    power_buffs = [
        entry for entry in catalogue
        if entry.reward_type is ShopRewardType.POWER_BUFF
    ]
    _require(len(unit_access) >= 100, 'DTA Shop unit access catalogue is incomplete')
    _require(len(unit_buffs) >= 500, 'DTA Shop unit buff catalogue is incomplete')
    _require(len(power_access) == 6, 'DTA Shop power access catalogue is incomplete')
    _require(len(power_buffs) >= 10, 'DTA Shop power buff catalogue is incomplete')
    paradrop_payload_choices = {
        str(canonical_reward_for_id(entry.reward_id).get('payload_unit_id') or '')
        for entry in power_buffs
        if entry.target_id == 'DROPPODSPECIAL'
        and canonical_reward_for_id(entry.reward_id).get('power_buff_type')
        == 'payload'
    }
    _require(
        paradrop_payload_choices == {
            '', 'E4S', 'E5', 'E3S', 'SHOK', 'MEDIC',
        },
        'DTA Shop selectable Paratroopers payload catalogue is incomplete',
    )
    provider_capacity_targets = {
        entry.target_id
        for entry in power_buffs
        if canonical_reward_for_id(entry.reward_id).get('power_buff_type')
        == 'capacity'
    }
    _require(
        provider_capacity_targets == {
            'AIRSTRIKESPECIAL', 'CHEMICALSPECIAL', 'VORTEXSPECIAL',
            'MULTISPECIAL',
        },
        'DTA Shop provider-capacity buffs are incomplete',
    )
    _require(
        any(entry.target_id == 'E1' for entry in unit_access),
        'Minigunner access missing from DTA Shop',
    )
    unit_access_targets = {entry.target_id for entry in unit_access}
    unit_buff_targets = {entry.target_id for entry in unit_buffs}
    _require(
        {'GMCV', 'NMCV', 'AMCV', 'SMCV'}.issubset(unit_access_targets),
        'DTA Shop MCV access catalogue is incomplete',
    )
    _require(
        unit_access_targets.issubset(unit_buff_targets),
        'One or more DTA Shop units have no upgrades',
    )

    for challenge in CHALLENGE_MODIFIERS:
        reward = canonical_reward_for_id(challenge.enemy_reward_id)
        _require(
            reward.get('enemy_reward'),
            f'Shop challenge {challenge.id} is not an enemy-house reward',
        )
    _require(CHALLENGE_MODIFIERS, 'DTA Shop has no enemy-house challenges')
    _require(PLAYER_BOON_MODIFIERS, 'DTA Shop has no player boons')
    _require(
        'veteran' not in {item[0] for item in UNIT_BUFF_WEIGHT_TYPES},
        'Unsupported DTA veterancy modifier is still selectable',
    )
    _require(
        'elite_force' not in SHOP_CONFIG.modifiers,
        'Unsupported DTA Elite Force modifier is still selectable',
    )
    _require(
        not SHOP_CONFIG.permanent_upgrades['veteran_academy'].purchasable,
        'Unsupported DTA Veteran Academy is still purchasable',
    )

    greedy_reward = mission_reward(
        MissionEconomyClass.ACT_1, modifiers=('greedy',)
    )
    generous_reward = mission_reward(
        MissionEconomyClass.ACT_1, modifiers=('generous_command',)
    )
    treasure_reward = mission_reward(
        MissionEconomyClass.ACT_1, modifiers=('treasure_hunter',)
    )
    _require(
        starting_run_coins(modifiers=('greedy',)) == 3
        and greedy_reward.meta_coins == 2,
        'Greedy does not use flat Shop currency changes',
    )
    _require(
        starting_run_coins(modifiers=('generous_command',)) == 10
        and generous_reward.meta_coins == 0,
        'Generous Command does not use flat Shop currency changes',
    )
    _require(
        discounted_shop_price(4, modifiers=('black_market',)) == 6
        and discounted_shop_price(4, modifiers=('liquid_assets',)) == 2,
        'Shop price modifiers do not use flat Ore changes',
    )
    _require(
        treasure_reward.run_coins == 1,
        'Treasure Hunter does not subtract 2 Ore from normal victories',
    )
    veteran_effects = modifier_effects(('veteran_economy',))
    poor_logistics_effects = modifier_effects(('poor_logistics',))
    _require(
        veteran_effects['mission_starting_credits_flat'] == 2000
        and veteran_effects['run_reward_flat'] == -1
        and veteran_effects['shop_price_percent'] == 1
        and veteran_effects['shop_price_flat'] == 0
        and poor_logistics_effects['mission_starting_credits_flat'] == 0
        and poor_logistics_effects['run_reward_flat'] == 4
        and poor_logistics_effects['shop_price_flat'] == 2,
        'Veteran Economy and Poor Logistics are not distinct flat-value trades',
    )

    new_modifier_ids = {
        'low_tech_war', 'superweapon_arms_race',
        'hardcore', 'faction_roulette',
    }
    _require(
        new_modifier_ids.issubset(SHOP_CONFIG.modifiers),
        'One or more requested DTA Shop modifiers are missing',
    )
    low_tech_effects = modifier_effects(('low_tech_war',))
    _require(
        low_tech_effects['run_reward_flat'] == 2
        and low_tech_effects['exclude_tier_3_offers']
        and low_tech_effects['exclude_special_offers']
        and low_tech_effects['exclude_power_offers'],
        'Low-Tech War effects are incomplete',
    )
    low_tech_access = [
        entry for entry in (*unit_access, *power_access)
        if modifier_allows_shop_offer(
            entry,
            canonical_reward_for_id(entry.reward_id),
            ('low_tech_war',),
        )
    ]
    _require(
        low_tech_access
        and all(
            entry.reward_type is ShopRewardType.UNIT_ACCESS
            for entry in low_tech_access
        )
        and all(entry.tier != 'tier_3' for entry in low_tech_access)
        and all(
            not canonical_reward_for_id(entry.reward_id).get('special_reward')
            for entry in low_tech_access
        )
        and mission_reward(
            MissionEconomyClass.ACT_1, modifiers=('low_tech_war',)
        ).run_coins == 5,
        'Low-Tech War stock or victory Ore is incorrect',
    )
    low_tech_tier_3 = next(
        entry for entry in unit_access if entry.tier == 'tier_3'
    )
    low_tech_special = next(
        entry for entry in unit_access
        if canonical_reward_for_id(entry.reward_id).get('special_reward')
    )
    _require(
        not modifier_allows_loadout_entry(
            low_tech_tier_3,
            canonical_reward_for_id(low_tech_tier_3.reward_id),
            ('low_tech_war',),
        )
        and modifier_allows_loadout_entry(
            low_tech_special,
            canonical_reward_for_id(low_tech_special.reward_id),
            ('low_tech_war',),
        )
        and modifier_allows_loadout_entry(
            power_access[0],
            canonical_reward_for_id(power_access[0].reward_id),
            ('low_tech_war',),
        ),
        'Low-Tech War loadout restriction is not limited to Tier 3 units',
    )
    try:
        start_new_run(
            ShopProfile(),
            run_id='dta-shop-low-tech-loadout-self-check',
            seed='DTA-SHOP-LOW-TECH-LOADOUT',
            mission_offers=first_offers,
            selected_reward_ids=(low_tech_tier_3.reward_id,),
            permanent_entitlement_ids=(low_tech_tier_3.reward_id,),
            modifiers=('low_tech_war',),
        )
    except ShopTransitionError as exc:
        low_tech_loadout_rejected = 'Low-Tech War' in str(exc)
    else:
        low_tech_loadout_rejected = False
    _require(
        low_tech_loadout_rejected,
        'Low-Tech War accepted a Tier 3 permanent starting unit',
    )
    arms_effects = modifier_effects(('superweapon_arms_race',))
    _require(
        arms_effects['power_inventory_flat'] == 2
        and arms_effects['cross_faction_power_offers']
        and arms_effects['enemy_armor_stacks'] == 1,
        'Superweapon Arms Race effects are incomplete',
    )
    hardcore_effects = modifier_effects(('hardcore',))
    _require(
        modifier_forces_hardest_difficulty(('hardcore',))
        and hardcore_effects['force_enemy_challenge']
        and hardcore_effects['disable_assists'],
        'Hardcore effects are incomplete',
    )
    _require(
        tuple(
            modifier_shop_faction(('faction_roulette',), stage)
            for stage in range(1, 9)
        ) == (
            'GDI', 'Nod', 'Allies', 'Soviet',
            'GDI', 'Nod', 'Allies', 'Soviet',
        )
        and modifier_effects(('faction_roulette',))['disable_rerolls'],
        'Faction Roulette rotation or reroll lock is incorrect',
    )
    _require(
        modifier_allows_faction_pool(
            ('faction_roulette',), 'All Campaigns'
        )
        and not modifier_allows_faction_pool(
            ('faction_roulette',), 'GDI'
        ),
        'Faction Roulette accepts a single-faction Shop pool',
    )
    try:
        start_new_run(
            ShopProfile(),
            run_id='dta-shop-faction-roulette-pool-self-check',
            seed='DTA-SHOP-FACTION-ROULETTE-POOL',
            mission_offers=first_offers,
            reward_settings={'shop_faction_filter': 'GDI'},
            modifiers=('faction_roulette',),
        )
    except ShopTransitionError as exc:
        faction_roulette_pool_rejected = 'All Factions' in str(exc)
    else:
        faction_roulette_pool_rejected = False
    _require(
        faction_roulette_pool_rejected,
        'Faction Roulette started with a single-faction Shop pool',
    )

    nod_only_loadout_entry = next(
        entry for entry in unit_access
        if 'Nod' in entry.factions and 'GDI' not in entry.factions
    )
    _require(
        not shop_entry_available(
            nod_only_loadout_entry,
            campaign_filter='GDI',
            reward_mode='Chaos',
            strict_faction=True,
        ),
        'Single-faction Shop pool exposes another faction loadout unit',
    )
    try:
        start_new_run(
            ShopProfile(),
            run_id='dta-shop-faction-loadout-self-check',
            seed='DTA-SHOP-FACTION-LOADOUT',
            mission_offers=first_offers,
            selected_reward_ids=(nod_only_loadout_entry.reward_id,),
            permanent_entitlement_ids=(nod_only_loadout_entry.reward_id,),
            reward_mode='Chaos',
            reward_settings={'shop_faction_filter': 'GDI'},
        )
    except ShopTransitionError as exc:
        wrong_faction_loadout_rejected = 'current campaign' in str(exc)
    else:
        wrong_faction_loadout_rejected = False
    _require(
        wrong_faction_loadout_rejected,
        'Single-faction Shop pool accepted another faction loadout unit',
    )

    marker_units = (
        'T1_GROUND_INFANTRY',
        'T1_ANTI_AIR_INFANTRY',
        'T1_GROUND_VEHICLE',
        'T1_ANTI_AIR_VEHICLE',
        'T1_BASIC_AIRCRAFT',
    )
    gdi_starters = shop_starter_unit_ids(
        seed='DTA-SHOP-SELF-CHECK',
        starting_unit_ids=marker_units,
        faction_filter='GDI',
    )
    _require(len(gdi_starters) == 5, 'DTA Shop did not resolve five GDI starters')
    starter_defenses = shop_starter_defense_ids(
        seed='DTA-SHOP-SELF-CHECK',
        starting_defense_ids=('T1_DEFENSES',),
        faction_filter='GDI',
    )
    _require(starter_defenses, 'DTA Shop starter defenses are incomplete')

    act_one_reward = mission_reward(MissionEconomyClass.ACT_1)
    operation_reward = mission_reward(
        MissionEconomyClass.OPERATION, victory_coin_bonus_level=3
    )
    _require(act_one_reward.run_coins > 0, 'Act 1 Shop reward grants no Ore')
    _require(
        operation_reward.victory_bonus_run_coins == 3,
        'Victory Ore upgrade does not add one Ore per level',
    )
    _require(
        run_unit_price('E1') == 2
        and permanent_unit_price('E1') == 8,
        'Low-cost DTA infantry Shop prices are incorrect',
    )
    _require(
        run_unit_price('JEEP') == 4
        and permanent_unit_price('JEEP') == 14,
        'Mid-cost DTA vehicle Shop prices are incorrect',
    )
    _require(
        run_unit_price('BRIG') == 12
        and permanent_unit_price('BRIG') == 60,
        'Top-cost DTA vehicle Shop prices are incorrect',
    )
    _require(
        run_unit_price('GMCV') == 12
        and permanent_unit_price('GMCV') == 60,
        'MCV Shop prices are incorrect',
    )
    _require(
        run_unit_price('SPY') == 3
        and permanent_buff_price('SPY') == 5
        and run_buff_price('BRIG') == 6,
        'DTA target-specific Shop utility or buff prices are incorrect',
    )
    _require(
        SHOP_CONFIG.power_target_prices['DROPPODSPECIAL'].run_access == 5
        and SHOP_CONFIG.power_target_prices['IONCANNONSPECIAL'].run_access == 10
        and SHOP_CONFIG.power_target_prices['MULTISPECIAL'].run_access == 12,
        'DTA Shop power prices are not strength-specific',
    )
    _require(
        permanent_power_price('DROPPODSPECIAL') == 25
        and permanent_power_price('IONCANNONSPECIAL') == 50
        and permanent_power_price('MULTISPECIAL') == 60
        and permanent_power_buff_price('DROPPODSPECIAL') == 5
        and permanent_power_buff_price('IONCANNONSPECIAL') == 10,
        'DTA permanent Shop power prices are incorrect',
    )

    power_entry = next(
        entry for entry in power_access
        if entry.target_id == 'IONCANNONSPECIAL'
    )
    power_buff_entry = next(
        entry for entry in power_buffs
        if entry.target_id == power_entry.target_id
    )
    permanent_profile = ShopProfile(meta_coins=200)
    blocked_power_buff = purchase_permanent_buff(
        permanent_profile,
        canonical_reward_for_id(power_buff_entry.reward_id),
        price=permanent_power_buff_price(power_buff_entry.target_id),
    )
    power_purchase = purchase_permanent_power(
        permanent_profile,
        canonical_reward_for_id(power_entry.reward_id),
        price=permanent_power_price(power_entry.target_id),
    )
    power_buff_purchase = purchase_permanent_buff(
        power_purchase.profile,
        canonical_reward_for_id(power_buff_entry.reward_id),
        price=permanent_power_buff_price(power_buff_entry.target_id),
    )
    _require(
        blocked_power_buff.validation.result.value == 'requires_power_access'
        and power_purchase.validation.allowed
        and power_buff_purchase.validation.allowed,
        'DTA permanent Shop power purchase validation failed',
    )
    permanent_power_transition = start_new_run(
        power_buff_purchase.profile,
        run_id='dta-shop-permanent-power-self-check',
        seed='DTA-SHOP-PERMANENT-POWER',
        mission_offers=first_offers,
        eligible_mission_codes=(mission['code'] for mission in missions),
        reward_mode='Chaos',
        permanent_power_reward_ids=(power_entry.reward_id,),
        permanent_power_entitlement_ids=(power_entry.reward_id,),
        permanent_buffs=power_buff_purchase.profile.permanent_buffs,
    )
    _require(
        power_entry.target_id in active_shop_power_ids(
            permanent_power_transition.run
        )
        and sum(
            reward.get('name') == power_buff_entry.reward_id
            for reward in active_shop_rewards(permanent_power_transition.run)
        ) == 1,
        'DTA permanent Shop power or buff did not activate for a new run',
    )
    unit_loadout_entry = unit_access[0]
    mixed_loadout = validate_starting_loadout(
        starter_tech_ids=(),
        selected_reward_ids=(
            unit_loadout_entry.reward_id,
            power_entry.reward_id,
        ),
        entitled_reward_ids=(
            unit_loadout_entry.reward_id,
            power_entry.reward_id,
        ),
        maximum_extra_units=2,
    )
    full_loadout = validate_starting_loadout(
        starter_tech_ids=(),
        selected_reward_ids=(
            unit_loadout_entry.reward_id,
            power_entry.reward_id,
        ),
        entitled_reward_ids=(
            unit_loadout_entry.reward_id,
            power_entry.reward_id,
        ),
        maximum_extra_units=1,
    )
    _require(
        mixed_loadout.allowed
        and mixed_loadout.extra_slots_used == 2
        and full_loadout.result is PurchaseResult.MAX_LOADOUT_SIZE,
        'Permanent powers do not share starting loadout slots with units',
    )
    mixed_transition = start_new_run(
        ShopProfile(),
        run_id='dta-shop-mixed-loadout-self-check',
        seed='DTA-SHOP-MIXED-LOADOUT',
        mission_offers=first_offers,
        selected_reward_ids=(unit_loadout_entry.reward_id,),
        permanent_power_reward_ids=(power_entry.reward_id,),
        permanent_entitlement_ids=(unit_loadout_entry.reward_id,),
        permanent_power_entitlement_ids=(power_entry.reward_id,),
        maximum_extra_units=2,
    )
    _require(
        mixed_transition.run.selected_permanent_units
        == (unit_loadout_entry.reward_id,)
        and mixed_transition.run.permanent_power_unlocks_snapshot
        == (power_entry.reward_id,),
        'Mixed permanent loadout does not preserve selected units and powers',
    )
    _require(
        SHOP_CONFIG.permanent_upgrades[
            'expanded_loadout'
        ].effects['slots_per_level'] == 2,
        'Expanded Loadout does not add two slots per level',
    )

    transition = start_new_run(
        ShopProfile(),
        run_id='dta-shop-self-check-run',
        seed='DTA-SHOP-SELF-CHECK',
        mission_offers=first_offers,
        eligible_mission_codes=(mission['code'] for mission in missions),
        starter_tech_ids=(*gdi_starters, *starter_defenses),
        starting_unit_ids=gdi_starters,
        starting_defense_ids=starter_defenses,
        reward_mode='Chaos',
        reward_settings={'shop_faction_filter': 'GDI'},
    )
    hardcore_run = replace(transition.run, modifiers=('hardcore',))
    _require(
        all(
            (modifier := mission_modifier_for_run_offer(hardcore_run, offer))
            is not None and modifier.challenge
            for offer in hardcore_run.mission_offers
        ),
        'Hardcore does not assign an enemy challenge to every mission offer',
    )
    completion_modifiers = tuple(SHOP_CONFIG.modifiers)[:8]
    completion_run = commit_selected_mission(
        replace(
            transition.run,
            stage=transition.run.run_length,
            modifiers=completion_modifiers,
        ),
        first_offers[0].mission_code,
    )
    completion = apply_mission_victory(
        ShopProfile(),
        completion_run,
        first_offers[0].mission_code,
    )
    base_completion = apply_mission_victory(
        ShopProfile(),
        replace(
            completion_run,
            run_id='dta-shop-base-completion-self-check',
            modifiers=(),
        ),
        first_offers[0].mission_code,
    )
    _require(
        SHOP_CONFIG.run_completion_meta_coins == 20
        and SHOP_CONFIG.run_completion_modifier_meta_coins == 2
        and base_completion.reward.run_completion_meta_coins == 20
        and completion.reward.run_completion_meta_coins == 36
        and completion.run.status is RunStatus.COMPLETED
        and completion.profile.lifetime_runs_completed == 1,
        'Shop run completion Gems or modifier bonus is incorrect',
    )
    legacy_elite_run = transition.run.to_dict()
    legacy_elite_run['modifiers'] = ['elite_force']
    _require(
        normalize_shop_run(legacy_elite_run).modifiers == (),
        'Legacy Elite Force runs are not migrated safely',
    )
    committed = commit_selected_mission(
        transition.run, first_offers[0].mission_code
    )
    next_offers = generate_mission_offers(
        missions,
        run_seed=committed.seed,
        stage=2,
        completed_codes=(first_offers[0].mission_code,),
    )
    victory = apply_mission_victory(
        transition.profile,
        committed,
        first_offers[0].mission_code,
        next_offers=next_offers,
    )
    duplicate = apply_mission_victory(
        victory.profile,
        victory.run,
        first_offers[0].mission_code,
        next_offers=next_offers,
    )
    _require(victory.changed, 'Shop victory was not applied')
    _require(not duplicate.changed, 'Duplicate Shop victory paid twice')
    _require(victory.run.status is RunStatus.ACTIVE, 'Stage 1 ended Shop run')
    free_token_definition = SHOP_CONFIG.permanent_upgrades['free_buff_token']
    _require(
        free_token_definition.max_level == 5
        and len(free_token_definition.prices) == 5,
        'Free Buff Token upgrade does not support five levels',
    )

    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        repository = ShopRepository(ShopPersistencePaths(
            profile=root / 'shop_profile.json',
            run=root / 'shop_run.json',
            transaction=root / 'shop_transaction.json',
            backup_dir=root / 'backups',
        ))
        token_profile = replace(
            transition.profile,
            permanent_upgrades={'free_buff_token': 3},
        )
        repository.commit(
            token_profile, transition.run, 'self-check-purchase-setup'
        )
        service = ShopProgressionService(repository)
        e2_access = next(
            entry for entry in unit_access if entry.target_id == 'E2'
        )
        e2_damage = next(
            entry for entry in unit_buffs
            if entry.target_id == 'E2'
            and canonical_reward({'name': entry.reward_id}).get('buff_type')
            == 'damage'
        )
        access_purchase = service.purchase_run_reward(e2_access.reward_id)
        buff_purchases = tuple(
            service.purchase_run_reward(e2_damage.reward_id)
            for _index in range(4)
        )
        purchased_run = repository.load_run()
        _require(access_purchase.allowed, 'DTA Shop unit purchase was rejected')
        _require(
            all(item.allowed for item in buff_purchases),
            'DTA Shop buff purchase was rejected',
        )
        _require(
            tuple(item.cost for item in buff_purchases[:3]) == (0, 0, 0)
            and buff_purchases[3].cost == run_buff_price('E2')
            and purchased_run.free_buff_tokens_used == 3
            and purchased_run.free_buff_tokens_used_stage == 3,
            'Free Buff Tokens are not applied per mission stage',
        )
        _require('E2' in active_shop_tech_ids(purchased_run), 'Shop purchase granted no E2 access')
        token_committed = commit_selected_mission(
            purchased_run, first_offers[0].mission_code
        )
        token_victory = apply_mission_victory(
            token_profile,
            token_committed,
            first_offers[0].mission_code,
            next_offers=next_offers,
        )
        _require(
            token_victory.run.free_buff_tokens_used == 3
            and token_victory.run.free_buff_tokens_used_stage == 0,
            'Free Buff Tokens do not refresh after a mission victory',
        )
        repository.commit(victory.profile, victory.run, 'self-check-commit')
        loaded_profile, loaded_run = repository.load()
        _require(loaded_profile == victory.profile, 'Shop profile restart mismatch')
        _require(loaded_run == victory.run, 'Shop run restart mismatch')

    return {
        'valid': True,
        **selection_checks,
        'missions': len(missions),
        'catalogue_entries': len(catalogue),
        'unit_access_entries': len(unit_access),
        'unit_buff_entries': len(unit_buffs),
        'power_access_entries': len(power_access),
        'power_buff_entries': len(power_buffs),
        'enemy_house_challenges': len(CHALLENGE_MODIFIERS),
        'player_boons': len(PLAYER_BOON_MODIFIERS),
    }
