"""Mission catalogue parsing and deterministic seed-order construction.

This module deliberately contains no Tk state.  Keeping mission discovery and
ordering pure makes seed compatibility testable without starting the launcher.
"""

import re

from randomizer.config.static import load_static_config


_MISSION_CONFIG = load_static_config('missions.json')
_MISSION_CATALOGUE = _MISSION_CONFIG['catalogue']
_MISSION_REWARD_CONFIG = _MISSION_CONFIG['mission_reward_multipliers']


FACTION_ORDER = tuple(_MISSION_CATALOGUE['faction_order'])
CAMPAIGN_ORDER = tuple(_MISSION_CATALOGUE['campaign_order'])
CAMPAIGN_BY_HEADER = dict(_MISSION_CATALOGUE['campaign_by_header'])
FALLBACK_OBJECTIVE_COUNT = int(_MISSION_CATALOGUE['fallback_objective_count'])
STARTING_UNLOCKED_MISSIONS = int(_MISSION_CATALOGUE['starting_unlocked_missions'])
LOW_LEVEL_MISSION_COUNT = int(_MISSION_CATALOGUE['low_level_mission_count'])
LOW_LEVEL_STAGE_MAX = int(_MISSION_CATALOGUE['low_level_stage_max'])
OPERATION_STAGE_SCORE = int(_MISSION_CATALOGUE['operation_stage_score'])
FALLBACK_STAGE_SCORE = int(_MISSION_CATALOGUE['fallback_stage_score'])
FINALE_STAGE_SCORE = int(_MISSION_CATALOGUE['finale_stage_score'])
FINALE_MISSION_CODES = frozenset(_MISSION_CATALOGUE['finale_mission_codes'])
OPERATION_MISSION_CODES = frozenset(_MISSION_CATALOGUE['operation_mission_codes'])

MISSION_REWARD_CLASS_MULTIPLIERS = {
    str(class_name): int(multiplier)
    for class_name, multiplier in _MISSION_REWARD_CONFIG[
        'class_multipliers'
    ].items()
}
MISSION_REWARD_CLASS_BY_CODE = {
    str(code).upper(): str(class_name)
    for class_name, codes in _MISSION_REWARD_CONFIG['mission_classes'].items()
    for code in codes
}
MISSION_REWARD_MULTIPLIER_OVERRIDES = {
    str(code).upper(): int(multiplier)
    for code, multiplier in _MISSION_REWARD_CONFIG.get(
        'mission_overrides', {}
    ).items()
}
DEFAULT_MISSION_REWARD_MULTIPLIER = int(
    _MISSION_REWARD_CONFIG['default_multiplier']
)

BASE_BUILD = 'base_build'
TRUE_NO_BUILD = 'true_no_build'
NO_BUILD_PRODUCTION = 'no_build_production'

# Static DTA classification. Keep every catalogue code explicit: this is
# player-facing seed data, not a title/stage-name guess.
MISSION_BUILD_CLASSIFICATIONS = dict(_MISSION_CONFIG['build_classifications'])

TRUE_NO_BUILD_MISSION_CODES = frozenset(
    code for code, classification in MISSION_BUILD_CLASSIFICATIONS.items()
    if classification == TRUE_NO_BUILD
)
NO_BUILD_PRODUCTION_MISSION_CODES = frozenset(
    code for code, classification in MISSION_BUILD_CLASSIFICATIONS.items()
    if classification == NO_BUILD_PRODUCTION
)
NO_BUILD_MISSION_CODES = frozenset(
    TRUE_NO_BUILD_MISSION_CODES | NO_BUILD_PRODUCTION_MISSION_CODES
)

# Backward-compatible boolean view for older integrations. ``True`` means the
# mission belongs to either non-base-building category.
NO_BUILD_MISSION_FLAGS = {
    code: classification != BASE_BUILD
    for code, classification in MISSION_BUILD_CLASSIFICATIONS.items()
}

# Optional late-mission exclusions retained as a generic catalogue hook.
LATE_FOEHN_MISSION_CODES = frozenset(_MISSION_CATALOGUE['late_foehn_mission_codes'])


def mission_reward_class(code):
    return MISSION_REWARD_CLASS_BY_CODE.get(str(code or '').upper(), '')


def mission_reward_multiplier(code):
    code = str(code or '').upper()
    if code in MISSION_REWARD_MULTIPLIER_OVERRIDES:
        return MISSION_REWARD_MULTIPLIER_OVERRIDES[code]
    class_name = MISSION_REWARD_CLASS_BY_CODE.get(code)
    return MISSION_REWARD_CLASS_MULTIPLIERS.get(
        class_name,
        DEFAULT_MISSION_REWARD_MULTIPLIER,
    )


def normalize_faction(side):
    side = (side or '').strip().lower()
    if side in {'0', 'gdi', 'gdiside'}:
        return 'GDI'
    if side in {'1', 'nod', 'nodside'}:
        return 'Nod'
    if side in {'2', 'allies', 'allied', 'alliedside'}:
        return 'Allies'
    if side in {'3', 'soviet', 'soviets', 'sovietside'}:
        return 'Soviet'
    if 'allies' in side or 'allied' in side:
        return 'Allies'
    if 'soviet' in side:
        return 'Soviet'
    return ''


def filter_missions_by_build_settings(
    missions,
    include_true_no_build=True,
    include_no_build_production=True,
    include_operation_missions=True,
):
    """Apply independent no-build and optional-operation pool settings."""
    excluded = set()
    if not include_true_no_build:
        excluded.add(TRUE_NO_BUILD)
    if not include_no_build_production:
        excluded.add(NO_BUILD_PRODUCTION)
    return [
        mission for mission in missions
        if mission.get('build_classification', BASE_BUILD) not in excluded
        and (
            include_operation_missions
            or mission.get('code', '').upper() not in OPERATION_MISSION_CODES
        )
    ]


def parse_long_description_objectives(text):
    if not text:
        return []
    objectives = []
    for part in text.split('@'):
        match = re.match(r'\s*Objective\s+(\d+)\s*:\s*(.+?)\s*$', part, flags=re.IGNORECASE)
        if match:
            objectives.append(match.group(2).strip())
            continue
        numbered = re.match(r'\s*\d+[.)]\s*(.+?)\s*$', part)
        if numbered:
            objectives.append(numbered.group(1).strip())
    return objectives


def parse_missions(path, fallback_objective_count=FALLBACK_OBJECTIVE_COUNT):
    """Read the ordered DTA campaign catalogue from ``Battle.ini``."""
    if not path.exists():
        return []

    lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
    mission_entries = []
    seen_codes = set()
    sections = {}
    current_section = None
    in_battles = False
    current_campaign = ''

    for line in lines:
        no_comment = line.split(';', 1)[0].strip()
        if not no_comment:
            continue
        if no_comment.startswith('[') and no_comment.endswith(']'):
            current_section = no_comment[1:-1].strip()
            in_battles = current_section == 'Battles'
            sections.setdefault(current_section, {})
            continue
        if in_battles and '=' in no_comment:
            _, value = no_comment.split('=', 1)
            code = value.strip()
            if code in CAMPAIGN_BY_HEADER:
                current_campaign = CAMPAIGN_BY_HEADER[code]
            elif code and code not in {'.', ',', '-'} and code not in seen_codes:
                mission_entries.append((code, current_campaign))
                seen_codes.add(code)
            continue
        if current_section and '=' in no_comment:
            key, value = no_comment.split('=', 1)
            sections.setdefault(current_section, {})[key.strip()] = value.strip()

    missions = []
    for code, campaign in mission_entries:
        section = sections.get(code, {})
        scenario = section.get('Scenario') or section.get('SCENARIO')
        if not scenario:
            continue
        # DTA has no uniform runtime signal for completed sub-objectives.
        # Victory is the only reliably observable completion event, so do not
        # generate objective checks that the launcher cannot report.
        objectives = []
        missions.append({
            'index': len(missions) + 1,
            'code': code,
            'scenario': scenario,
            'title': section.get('UIName') or section.get('Description') or section.get('description') or code,
            'side': section.get('SideName') or section.get('Side') or '',
            'campaign': campaign or 'Special Ops',
            'objectives': objectives,
            'objective_count': len(objectives) or fallback_objective_count,
            'build_classification': MISSION_BUILD_CLASSIFICATIONS.get(code, BASE_BUILD),
            'no_build': bool(NO_BUILD_MISSION_FLAGS.get(code, False)),
            'true_no_build': code in TRUE_NO_BUILD_MISSION_CODES,
            'no_build_production': code in NO_BUILD_PRODUCTION_MISSION_CODES,
            'operation': code in OPERATION_MISSION_CODES,
            'reward_class': mission_reward_class(code),
            'reward_multiplier': mission_reward_multiplier(code),
            'required_addon': section.get('RequiredAddon', '0').strip().lower() in {'1', 'yes', 'true'},
            'player_always_normal': section.get('PlayerAlwaysOnNormalDifficulty', '').strip().lower() in {'1', 'yes', 'true'},
            'has_extended_difficulty': section.get('HasExtendedDifficulty', '').strip().lower() in {'1', 'yes', 'true'},
            'difficulty_labels': [
                label.strip()
                for label in section.get('DifficultyLabels', '').split(',')
                if label.strip()
            ],
        })
    return missions


def mission_stage_score(mission):
    title = mission.get('title', '') or ''
    code = mission.get('code', '') or ''
    match = re.search(r'\b(?:GDI|Nod|Allied|Soviet)\s+(\d{1,2})\b', title, flags=re.IGNORECASE)
    if match:
        score = int(match.group(1))
    elif re.search(r'\bOp\b', title, flags=re.IGNORECASE):
        score = OPERATION_STAGE_SCORE
    else:
        score = int(mission.get('index') or FALLBACK_STAGE_SCORE)
    if (
        re.search(r'\b(finale|final)\b', title, flags=re.IGNORECASE)
        or code.upper() in FINALE_MISSION_CODES
    ):
        score = max(score, FINALE_STAGE_SCORE)
    return score


def campaign_mission_counts(missions):
    counts = {campaign: 0 for campaign in CAMPAIGN_ORDER}
    for mission in missions:
        campaign = mission.get('campaign', '')
        if campaign in counts:
            counts[campaign] += 1
    return {campaign: count for campaign, count in counts.items() if count}


def mission_matches_campaign(mission, selected):
    return selected == 'All Campaigns' or mission.get('campaign') == selected


def campaign_factions(missions, selected):
    return {
        normalize_faction(mission.get('side', ''))
        for mission in missions
        if mission_matches_campaign(mission, selected)
        and normalize_faction(mission.get('side', ''))
    }


def seed_campaign_limits(missions, mission_goal):
    """Return installed per-faction limits for a mixed DTA seed."""
    counts = campaign_mission_counts(missions)
    return dict(counts)


def classic_mission_order(missions, mission_goal):
    """Return the requested missions in installed campaign-catalogue order."""
    missions = list(missions)
    if not missions:
        return []
    mission_goal = max(1, min(mission_goal, len(missions)))
    return [mission['code'] for mission in missions[:mission_goal]]


def seed_mission_order(
    missions,
    rng,
    mission_goal,
    low_level_count=LOW_LEVEL_MISSION_COUNT,
    preferred_opening_codes=None,
    excluded_opening_codes=None,
):
    """Return the requested low-level opening, then an unrestricted shuffle."""
    missions = list(missions)
    if not missions:
        return []
    mission_goal = max(1, min(mission_goal, len(missions)))
    campaign_limits = seed_campaign_limits(missions, mission_goal)
    picked_by_campaign = {campaign: 0 for campaign in campaign_limits}

    def bucket(mission):
        score = mission_stage_score(mission)
        return 0 if score <= LOW_LEVEL_STAGE_MAX else 1 if score <= 16 else 2 if score < 24 else 3

    def shuffled(items):
        items = list(items)
        rng.shuffle(items)
        return items

    opening_count = min(max(0, int(low_level_count)), mission_goal)
    preferred_opening_codes = set(preferred_opening_codes or ())
    excluded_opening_codes = set(excluded_opening_codes or ())

    picked_codes = set()
    ordered = []

    def add_mission(mission):
        campaign = mission.get('campaign', '')
        if (
            mission['code'] in picked_codes
            or picked_by_campaign.get(campaign, 0)
            >= campaign_limits.get(campaign, len(missions))
        ):
            return False
        ordered.append(mission)
        picked_codes.add(mission['code'])
        picked_by_campaign[campaign] = picked_by_campaign.get(campaign, 0) + 1
        return True

    # Optional no-build preference still respects stage buckets: easier fixed-
    # unit missions win before late/finale no-build missions. Late maps
    # remain excluded from the protected opening.
    if preferred_opening_codes and opening_count:
        for bucket_index in range(4):
            bucket_missions = (
                mission for mission in missions
                if mission['code'] in preferred_opening_codes
                and mission['code'] not in excluded_opening_codes
                and bucket(mission) == bucket_index
            )
            for mission in shuffled(bucket_missions):
                if add_mission(mission) and len(ordered) >= opening_count:
                    break
            if len(ordered) >= opening_count:
                break

    # Keep only the opening approachable. The installed catalogue has enough
    # missions 1-6 for all campaign filters; later buckets are a defensive
    # fallback for custom or incomplete catalogues.
    for bucket_index in range(4) if len(ordered) < opening_count else ():
        bucket_missions = (
            mission for mission in missions
            if mission['code'] not in excluded_opening_codes
            and bucket(mission) == bucket_index
        )
        for mission in shuffled(bucket_missions):
            if add_mission(mission) and len(ordered) >= opening_count:
                break
        if len(ordered) >= opening_count:
            break

    # A narrow custom/campaign-only pool may contain too few safe opening maps.
    # Fill from excluded maps only when otherwise impossible to reach requested
    # opening size; mixed installed campaigns never need this fallback.
    if len(ordered) < opening_count:
        for bucket_index in range(4):
            bucket_missions = (
                mission for mission in missions
                if mission['code'] in excluded_opening_codes
                and bucket(mission) == bucket_index
            )
            for mission in shuffled(bucket_missions):
                if add_mission(mission) and len(ordered) >= opening_count:
                    break
            if len(ordered) >= opening_count:
                break
    if len(ordered) >= mission_goal:
        return [item['code'] for item in ordered]

    # Everything after the protected opening is equally eligible. Act 2 and
    # finale missions can therefore appear in the first unprotected slot.
    for mission in shuffled(missions):
        if add_mission(mission) and len(ordered) >= mission_goal:
            break
    return [item['code'] for item in ordered]
