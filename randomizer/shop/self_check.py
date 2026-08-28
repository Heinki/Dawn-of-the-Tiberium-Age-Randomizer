"""Focused non-invasive validation for DTA Shop Mode."""

from pathlib import Path
from tempfile import TemporaryDirectory

from randomizer.core.paths import BATTLE_CLIENT_INI
from randomizer.missions.catalogue import parse_missions
from randomizer.rewards.catalogue import canonical_reward

from .active import active_shop_tech_ids, shop_starter_defense_ids, shop_starter_unit_ids
from .catalogue import canonical_reward_for_id, shop_catalogue
from .config import SHOP_CONFIG
from .economy import (
    mission_reward,
    permanent_buff_price,
    permanent_unit_price,
    run_buff_price,
    run_unit_price,
)
from .mission_modifiers import CHALLENGE_MODIFIERS, PLAYER_BOON_MODIFIERS
from .missions import classify_mission, generate_mission_offers
from .model import (
    MissionEconomyClass,
    RunStatus,
    ShopProfile,
    ShopRewardType,
)
from .persistence import ShopPersistencePaths, ShopRepository
from .service import ShopProgressionService
from .transitions import (
    apply_mission_victory,
    commit_selected_mission,
    start_new_run,
)


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def validate_shop_domain():
    """Validate DTA catalogue, missions, economy, state, and persistence."""
    missions = parse_missions(BATTLE_CLIENT_INI)
    classes = {classify_mission(mission) for mission in missions}
    _require(
        classes == set(MissionEconomyClass),
        f'Shop mission classes incomplete: {sorted(item.value for item in classes)}',
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
    _require(
        any(entry.target_id == 'E1' for entry in unit_access),
        'Minigunner access missing from DTA Shop',
    )

    for challenge in CHALLENGE_MODIFIERS:
        reward = canonical_reward_for_id(challenge.enemy_reward_id)
        _require(
            reward.get('enemy_reward'),
            f'Shop challenge {challenge.id} is not an enemy-house reward',
        )
    _require(CHALLENGE_MODIFIERS, 'DTA Shop has no enemy-house challenges')
    _require(PLAYER_BOON_MODIFIERS, 'DTA Shop has no player boons')

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

    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        repository = ShopRepository(ShopPersistencePaths(
            profile=root / 'shop_profile.json',
            run=root / 'shop_run.json',
            transaction=root / 'shop_transaction.json',
            backup_dir=root / 'backups',
        ))
        repository.commit(
            transition.profile, transition.run, 'self-check-purchase-setup'
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
        buff_purchase = service.purchase_run_reward(e2_damage.reward_id)
        purchased_run = repository.load_run()
        _require(access_purchase.allowed, 'DTA Shop unit purchase was rejected')
        _require(buff_purchase.allowed, 'DTA Shop buff purchase was rejected')
        _require('E2' in active_shop_tech_ids(purchased_run), 'Shop purchase granted no E2 access')
        repository.commit(victory.profile, victory.run, 'self-check-commit')
        loaded_profile, loaded_run = repository.load()
        _require(loaded_profile == victory.profile, 'Shop profile restart mismatch')
        _require(loaded_run == victory.run, 'Shop run restart mismatch')

    return {
        'valid': True,
        'missions': len(missions),
        'catalogue_entries': len(catalogue),
        'unit_access_entries': len(unit_access),
        'unit_buff_entries': len(unit_buffs),
        'power_access_entries': len(power_access),
        'power_buff_entries': len(power_buffs),
        'enemy_house_challenges': len(CHALLENGE_MODIFIERS),
        'player_boons': len(PLAYER_BOON_MODIFIERS),
    }
