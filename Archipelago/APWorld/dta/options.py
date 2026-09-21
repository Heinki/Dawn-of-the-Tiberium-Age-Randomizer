"""Dawn of the Tiberium Age APWorld options."""

from dataclasses import dataclass

from Options import (
    Choice,
    DefaultOnToggle,
    FreeText,
    OptionCounter,
    OptionDict,
    OptionGroup,
    OptionSet,
    PerGameCommonOptions,
    Range,
    Toggle,
    Visibility,
)

from .data import MISSION_DATA


CAMPAIGNS = (
    "All Campaigns", "Tutorial", "Shadow Exodus", "PTTP", "CR",
    "Toxic Diversion", "It Came From Red Alert!", "Creeping Destruction",
    "Stand-Alone Missions",
)
PROGRESSION_MODES = ("Classic", "Mission List", "Grid Mode", "Shop Mode")
REWARD_MODES = ("Standard", "Chaos", "Randomizer Arsenal")
DIFFICULTIES = (
    "Easy", "Normal", "Hard", "Brutal", "Extreme", "Ultimate", "Impossible",
)
GAME_SPEEDS = (
    "0 - Slowest", "1 - Slower", "2 - Slow", "3 - Medium",
    "4 - Fast", "5 - Faster", "6 - Fastest",
)
PLAYER_COLORS = (
    "Default", "Gold", "Red", "Teal", "Green", "Orange", "Blue",
    "Purple", "Metallic", "White", "Brown", "Pink", "Cyan",
)


class LauncherSettings(OptionDict):
    """Legacy launcher-exported settings. New YAMLs use the options below."""

    visibility = Visibility.none
    display_name = "Launcher Settings"
    default = {}


class RunManifest(FreeText):
    """Legacy launcher-exported deterministic run manifest as JSON."""

    visibility = Visibility.none
    display_name = "Run Manifest"
    default = ""


class GeneratedWorld(OptionDict):
    """Legacy world template retained for old player files."""

    visibility = Visibility.none
    display_name = "Generated World"
    default = {}


class Campaign(Choice):
    """Mission campaign pool. All Campaigns includes every installed campaign."""

    display_name = "Campaign"
    option_all_campaigns = 0
    option_tutorial = 1
    option_shadow_exodus = 2
    option_pttp = 3
    option_cr = 4
    option_toxic_diversion = 5
    option_it_came_from_red_alert = 6
    option_creeping_destruction = 7
    option_stand_alone_missions = 8
    default = 0


class MissionGoal(Range):
    """Number of missions in the generated run."""

    display_name = "Missions to Finish"
    range_start = 1
    range_end = len(MISSION_DATA)
    default = 15


class ProgressionMode(Choice):
    """Classic order, shuffled list, mission grid, or ten-stage Shop Mode."""

    display_name = "Progression Mode"
    option_classic = 0
    option_mission_list = 1
    option_grid_mode = 2
    option_shop_mode = 3
    default = 1


class GridTwoStartPositions(Toggle):
    """Start Grid Mode with two available neighboring missions."""

    display_name = "Grid: Two Starting Missions"


class UnlockAllGridRewards(Toggle):
    """Release unfinished Grid rewards after completing the final Grid mission."""

    display_name = "Grid: Release Rewards After Goal"


class RewardsPerObjective(Range):
    """Number of item draws assigned to each objective or mission victory."""

    display_name = "Rewards Per Objective"
    range_start = 1
    range_end = 30
    default = 1


class UseActRewardMultipliers(DefaultOnToggle):
    """Give later-act and finale missions additional victory rewards."""

    display_name = "Use Act-Based Reward Multipliers"


class Difficulty(Choice):
    """Difficulty written to every launched mission."""

    display_name = "Difficulty"
    option_easy = 0
    option_normal = 1
    option_hard = 2
    option_brutal = 3
    option_extreme = 4
    option_ultimate = 5
    option_impossible = 6
    default = 1


class GameSpeed(Choice):
    """Game speed written to every launched mission."""

    display_name = "Game Speed"
    option_0_slowest = 0
    option_1_slower = 1
    option_2_slow = 2
    option_3_medium = 3
    option_4_fast = 4
    option_5_faster = 5
    option_6_fastest = 6
    default = 3


class PlayerColor(Choice):
    """Player color used by launched missions."""

    display_name = "Player Color"
    option_default = 0
    option_gold = 1
    option_red = 2
    option_teal = 3
    option_green = 4
    option_orange = 5
    option_blue = 6
    option_purple = 7
    option_metallic = 8
    option_white = 9
    option_brown = 10
    option_pink = 11
    option_cyan = 12
    default = 0


class Rainbowizer(Toggle):
    """Randomize the player color deterministically for each mission."""

    display_name = "Rainbowizer"


class RewardMode(Choice):
    """Standard, all-faction Chaos, or per-mission Randomizer Arsenal rewards."""

    display_name = "Reward Mode"
    option_standard = 0
    option_chaos = 1
    option_randomizer_arsenal = 2
    default = 0


class IncludeNoBuildMissions(DefaultOnToggle):
    """Include true no-build missions played with fixed or scripted forces."""

    display_name = "Include True No-Build Missions"


class IncludeNoBuildProductionMissions(DefaultOnToggle):
    """Include no-build missions that still provide limited production."""

    display_name = "Include No-Build Production Missions"


class IncludeOperationMissions(DefaultOnToggle):
    """Include optional operation missions in the mission pool."""

    display_name = "Include Operation Missions"


class PrioritizeNoBuildMissions(Toggle):
    """Prefer enabled no-build missions in protected opening positions."""

    display_name = "Prioritize No-Build Openings"


class ExcludedMissions(OptionSet):
    """Mission codes removed from the generated mission pool."""

    display_name = "Excluded Missions"
    valid_keys = frozenset(MISSION_DATA)
    default = frozenset()


class RandomizeUnitAccess(DefaultOnToggle):
    """Lock unearned combat technology and add unit access rewards."""

    display_name = "Randomize Unit Access"


class StartWithTierOneUnits(Toggle):
    """Start with a safe basic Tier 1 combat roster."""

    display_name = "Start With Tier 1 Units"


class StartWithTierOneDefenses(Toggle):
    """Start with basic anti-ground and anti-air defenses."""

    display_name = "Start With Tier 1 Defenses"


class StartingRewardCount(Range):
    """Number of ordinary rewards granted before the first mission."""

    display_name = "Starting Reward Count"
    range_start = 0
    range_end = 9999
    default = 0


class StartingRewardTypes(OptionSet):
    """Unlock families allowed for randomly rolled starting rewards."""

    display_name = "Starting Reward Types"
    valid_keys = frozenset({
        "access", "superweapon", "secondary_superweapon", "aid_power",
    })
    default = frozenset()


class IncludeDefensiveBuildings(DefaultOnToggle):
    """Include defensive structures in access and buff rewards."""

    display_name = "Include Defensive Buildings"


class IncludeSpecialBuildings(Toggle):
    """Include special economy building access rewards."""

    display_name = "Include Special Buildings"


class IncludeSpecialRewards(DefaultOnToggle):
    """Include campaign and map-only units, buildings, and powers."""

    display_name = "Include Special Rewards"


class UnlimitedHeroUnits(Toggle):
    """Remove positive simultaneous-unit limits from player hero clones."""

    display_name = "Unlimited Hero Units"


class ShareChaosRoleBuffs(DefaultOnToggle):
    """Share buffs with curated same-tier equivalents in Chaos or all-campaign play."""

    display_name = "Share Equivalent Unit Buffs"


class BuffAlliedHelpers(Toggle):
    """Apply compatible player buffs to reviewed allied AI helpers."""

    display_name = "Buff Allied Helpers"


class FailureAssistance(Toggle):
    """Strengthen the player on each retry of a failed mission."""

    display_name = "Failure Assistance"


class IncludeBuffRewards(DefaultOnToggle):
    """Include repeatable unit and building buff rewards."""

    display_name = "Include Buff Rewards"


class IncludeSuperweaponRewards(DefaultOnToggle):
    """Include offensive superweapon unlock rewards."""

    display_name = "Include Offensive Superweapons"


class IncludeSecondarySuperweaponRewards(Toggle):
    """Include secondary superweapon unlock rewards."""

    display_name = "Include Secondary Superweapons"


class IncludeAidPowerRewards(DefaultOnToggle):
    """Include support and aid power unlock rewards."""

    display_name = "Include Aid Powers"


class IncludePowerBuffRewards(DefaultOnToggle):
    """Include repeatable buffs for unlocked superweapons and aid powers."""

    display_name = "Include Power Buffs"


class EnabledBuffTypes(OptionSet):
    """Unit and building buff families allowed in the reward pool."""

    display_name = "Enabled Unit Buff Types"
    valid_keys = frozenset({
        "production", "cost", "speed", "armor", "health", "damage", "reload",
        "range", "sight", "ammo", "passenger_capacity", "open_topped",
        "build_limit", "cloak", "sensors", "self_healing",
        "self_healing_cap", "self_healing_rate", "area", "veteran",
    })
    default = frozenset({
        "production", "cost", "speed", "armor", "health", "damage", "reload",
        "range", "sight", "ammo", "passenger_capacity", "build_limit", "cloak",
        "sensors", "self_healing", "self_healing_cap", "self_healing_rate",
        "area",
    })


class EnabledPowerBuffTypes(OptionSet):
    """Superweapon and aid-power buff families allowed in the reward pool."""

    display_name = "Enabled Power Buff Types"
    valid_keys = frozenset({
        "recharge", "damage", "area", "payload", "cost", "production",
        "capacity", "vision", "duration", "other",
    })
    default = frozenset({
        "recharge", "damage", "area", "payload", "cost", "production", "capacity",
    })


class MainRewardWeights(OptionCounter):
    """Relative reward-category weights. Zero disables a category."""

    display_name = "Main Reward Weights"
    valid_keys = frozenset({
        "unit_unlocks", "power_unlocks", "special_unlocks", "production",
        "unit_buffs", "power_buffs", "enemy_buffs",
    })
    min = 0
    max = 100
    default = {key: 100 for key in valid_keys}


class UnitBuffWeights(OptionCounter):
    """Relative weights for unit and building buff families."""

    display_name = "Unit Buff Weights"
    valid_keys = frozenset({
        "speed", "health", "damage", "range", "reload", "armor", "cost",
        "production", "self_healing", "self_healing_cap",
        "self_healing_rate", "area", "sight", "ammo",
        "passenger_capacity", "open_topped", "cloak", "sensors", "veteran",
        "build_limit", "building_limit", "other",
    })
    min = 0
    max = 100
    default = {key: 100 for key in valid_keys}


class PowerBuffWeights(OptionCounter):
    """Relative weights for superweapon and aid-power buff families."""

    display_name = "Power Buff Weights"
    valid_keys = frozenset({
        "recharge", "cost", "production", "capacity", "area", "damage",
        "duration", "vision", "payload", "other",
    })
    min = 0
    max = 100
    default = {key: 100 for key in valid_keys}


class ArsenalFactions(OptionSet):
    """Faction families available to Randomizer Arsenal rosters."""

    display_name = "Arsenal Factions"
    valid_keys = frozenset({"GDI", "Nod", "Allies", "Soviet"})
    default = valid_keys


class ArsenalRosterSizes(OptionCounter):
    """Roster size per tier and production category."""

    display_name = "Arsenal Roster Sizes"
    valid_keys = frozenset(
        f"tier_{tier}_{category}"
        for tier in (1, 2, 3)
        for category in ("infantry", "vehicles", "aircraft", "naval")
    )
    min = 0
    max = 20
    default = {key: 0 for key in valid_keys}


class ArsenalPowerCounts(OptionCounter):
    """Offensive, secondary, and aid powers in each Arsenal roster."""

    display_name = "Arsenal Power Counts"
    valid_keys = frozenset({"offensive", "secondary", "aid"})
    min = 0
    max = 20
    default = {key: 0 for key in valid_keys}


class EnemyRewardPool(Toggle):
    """Add hostile-AI bonus items beside normal player rewards."""

    display_name = "Enable Enemy Rewards"


class EnemyRewardsPerObjective(Range):
    """Enemy bonus items generated for each completed objective."""

    display_name = "Enemy Rewards Per Objective"
    range_start = 0
    range_end = 30
    default = 0


class EnemyRewardsPerMission(Range):
    """Enemy bonus items generated for each completed mission."""

    display_name = "Enemy Rewards Per Mission"
    range_start = 0
    range_end = 30
    default = 0


@dataclass
class DTAOptions(PerGameCommonOptions):
    launcher_settings: LauncherSettings
    generated_world: GeneratedWorld
    run_manifest: RunManifest
    campaign: Campaign
    mission_goal: MissionGoal
    progression_mode: ProgressionMode
    grid_two_start_positions: GridTwoStartPositions
    unlock_all_grid_rewards: UnlockAllGridRewards
    rewards_per_objective: RewardsPerObjective
    use_act_reward_multipliers: UseActRewardMultipliers
    difficulty: Difficulty
    game_speed: GameSpeed
    player_color: PlayerColor
    rainbowizer: Rainbowizer
    reward_mode: RewardMode
    include_no_build_missions: IncludeNoBuildMissions
    include_no_build_production_missions: IncludeNoBuildProductionMissions
    include_operation_missions: IncludeOperationMissions
    prioritize_no_build_missions: PrioritizeNoBuildMissions
    excluded_missions: ExcludedMissions
    randomize_unit_access: RandomizeUnitAccess
    start_with_tier_one_units: StartWithTierOneUnits
    start_with_tier_one_defenses: StartWithTierOneDefenses
    starting_reward_count: StartingRewardCount
    starting_reward_types: StartingRewardTypes
    include_defensive_buildings: IncludeDefensiveBuildings
    include_special_buildings: IncludeSpecialBuildings
    include_special_rewards: IncludeSpecialRewards
    unlimited_hero_units: UnlimitedHeroUnits
    share_chaos_role_buffs: ShareChaosRoleBuffs
    buff_allied_helpers: BuffAlliedHelpers
    failure_assistance: FailureAssistance
    include_buff_rewards: IncludeBuffRewards
    include_superweapon_rewards: IncludeSuperweaponRewards
    include_secondary_superweapon_rewards: IncludeSecondarySuperweaponRewards
    include_aid_power_rewards: IncludeAidPowerRewards
    include_power_buff_rewards: IncludePowerBuffRewards
    enabled_buff_types: EnabledBuffTypes
    enabled_power_buff_types: EnabledPowerBuffTypes
    main_reward_weights: MainRewardWeights
    unit_buff_weights: UnitBuffWeights
    power_buff_weights: PowerBuffWeights
    arsenal_factions: ArsenalFactions
    arsenal_roster_sizes: ArsenalRosterSizes
    arsenal_power_counts: ArsenalPowerCounts
    enemy_reward_pool: EnemyRewardPool
    enemy_rewards_per_objective: EnemyRewardsPerObjective
    enemy_rewards_per_mission: EnemyRewardsPerMission


DTA_OPTION_GROUPS = [
    OptionGroup("Randomizer Run", [
        Campaign, MissionGoal, ProgressionMode, GridTwoStartPositions,
        UnlockAllGridRewards, Difficulty, GameSpeed, PlayerColor, Rainbowizer,
    ]),
    OptionGroup("Mission Pool", [
        IncludeNoBuildMissions, IncludeNoBuildProductionMissions,
        IncludeOperationMissions, PrioritizeNoBuildMissions, ExcludedMissions,
    ]),
    OptionGroup("Reward Pool", [
        RewardsPerObjective, UseActRewardMultipliers, RewardMode,
        RandomizeUnitAccess, StartWithTierOneUnits, StartWithTierOneDefenses,
        StartingRewardCount, StartingRewardTypes, IncludeDefensiveBuildings,
        IncludeSpecialBuildings, IncludeSpecialRewards, UnlimitedHeroUnits,
        ShareChaosRoleBuffs, BuffAlliedHelpers, FailureAssistance,
        IncludeBuffRewards, IncludeSuperweaponRewards,
        IncludeSecondarySuperweaponRewards, IncludeAidPowerRewards,
        IncludePowerBuffRewards,
    ]),
    OptionGroup("Buffs and Weights", [
        EnabledBuffTypes, EnabledPowerBuffTypes, MainRewardWeights,
        UnitBuffWeights, PowerBuffWeights,
    ], start_collapsed=True),
    OptionGroup("Randomizer Arsenal", [
        ArsenalFactions, ArsenalRosterSizes, ArsenalPowerCounts,
    ], start_collapsed=True),
    OptionGroup("Enemy Rewards", [
        EnemyRewardPool, EnemyRewardsPerObjective, EnemyRewardsPerMission,
    ], start_collapsed=True),
]


def _arsenal_rosters(flat):
    return {
        f"tier_{tier}": {
            category: int(flat.get(f"tier_{tier}_{category}", 0))
            for category in ("infantry", "vehicles", "aircraft", "naval")
        }
        for tier in (1, 2, 3)
    }


def launcher_settings_from_options(options):
    """Translate option-creator fields into the launcher's nested settings."""
    generation = {
        "reward_mode": REWARD_MODES[options.reward_mode.value],
        "arsenal": {
            "factions": sorted(options.arsenal_factions.value),
            "roster_sizes": _arsenal_rosters(options.arsenal_roster_sizes.value),
            "power_counts": dict(options.arsenal_power_counts.value),
        },
        "include_no_build_missions": bool(options.include_no_build_missions.value),
        "include_no_build_production_missions": bool(
            options.include_no_build_production_missions.value
        ),
        "include_operation_missions": bool(options.include_operation_missions.value),
        "prioritize_no_build_missions": bool(options.prioritize_no_build_missions.value),
        "excluded_mission_codes": sorted(options.excluded_missions.value),
        "randomize_unit_access": bool(options.randomize_unit_access.value),
        "start_with_tier_one_units": bool(options.start_with_tier_one_units.value),
        "start_with_tier_one_defenses": bool(options.start_with_tier_one_defenses.value),
        "starting_reward_count": options.starting_reward_count.value,
        "starting_reward_types": sorted(options.starting_reward_types.value),
        "include_defensive_buildings": bool(options.include_defensive_buildings.value),
        "include_special_buildings": bool(options.include_special_buildings.value),
        "include_special_rewards": bool(options.include_special_rewards.value),
        "unlimited_hero_units": bool(options.unlimited_hero_units.value),
        "share_chaos_role_buffs": bool(options.share_chaos_role_buffs.value),
        "buff_allied_helpers": bool(options.buff_allied_helpers.value),
        "failure_assistance": bool(options.failure_assistance.value),
        "include_buff_rewards": bool(options.include_buff_rewards.value),
        "include_superweapon_rewards": bool(options.include_superweapon_rewards.value),
        "include_secondary_superweapon_rewards": bool(
            options.include_secondary_superweapon_rewards.value
        ),
        "include_aid_power_rewards": bool(options.include_aid_power_rewards.value),
        "include_power_buff_rewards": bool(options.include_power_buff_rewards.value),
        "enabled_buff_types": sorted(options.enabled_buff_types.value),
        "enabled_power_buff_types": sorted(options.enabled_power_buff_types.value),
        "reward_weights": {
            "main": dict(options.main_reward_weights.value),
            "unit_buffs": dict(options.unit_buff_weights.value),
            "power_buffs": dict(options.power_buff_weights.value),
        },
        "enemy_scaling": {
            "reward_enabled": bool(options.enemy_reward_pool.value),
            "rewards_per_completed_objective": options.enemy_rewards_per_objective.value,
            "rewards_per_completed_mission": options.enemy_rewards_per_mission.value,
        },
    }
    return {
        "campaign_filter": CAMPAIGNS[options.campaign.value],
        "mission_goal": options.mission_goal.value,
        "progression_mode": PROGRESSION_MODES[options.progression_mode.value],
        "grid_two_start_positions": bool(options.grid_two_start_positions.value),
        "unlock_all_rewards_after_final_grid_mission": bool(
            options.unlock_all_grid_rewards.value
        ),
        "rewards_per_objective": options.rewards_per_objective.value,
        "rewards_on_victory_only": True,
        "use_act_based_reward_multipliers": bool(
            options.use_act_reward_multipliers.value
        ),
        "difficulty": DIFFICULTIES[options.difficulty.value],
        "game_speed": GAME_SPEEDS[options.game_speed.value],
        "player_color": PLAYER_COLORS[options.player_color.value],
        "rainbowizer": bool(options.rainbowizer.value),
        "generation": generation,
    }
