"""Player-only DTA mobile-unit access isolation."""

from randomizer.core.paths import GAME_ROOT
from randomizer.dta.clones import _player_production_context
from randomizer.dta.maps import mission_source_path
from randomizer.dta.rules import (
    ALWAYS_AVAILABLE_MOBILE_IDS,
    catalogue_by_id,
    comma_items,
    effective_section,
    ini_sections,
)


def _forbidden_houses(values, player_house, locked):
    houses = list(comma_items(values.get('ForbiddenHouses')))
    existing = {house.casefold() for house in houses}
    marker = player_house.casefold()
    if locked and marker not in existing:
        houses.append(player_house)
    elif not locked:
        houses = [house for house in houses if house.casefold() != marker]
    return ','.join(houses)


def player_infantry_access_rules(mission, rewards, enabled):
    """Lock or unlock human mobile production without changing map objects.

    Vinifera evaluates RequiredHouses/ForbiddenHouses against ``ActsLike``.
    Therefore the resolved production HouseType is used, and the adapter safely
    opts out when a hostile scenario house shares that same production bit.
    """
    report = {
        'enabled': bool(enabled),
        'player_house': '',
        'production_house': '',
        'acts_like': None,
        'shared_hostile_houses': [],
        'skipped_reason': '',
        'locked': [],
        'original_unlocked': [],
        'clone_unlocked': [],
        'map_objects_rewritten': 0,
    }
    if not enabled:
        return {}, report

    source = mission_source_path(mission.get('scenario'))
    installed = ini_sections(GAME_ROOT / 'INI' / 'Rules.ini')
    authored = ini_sections(source)
    context = _player_production_context(authored)
    report.update(context)
    production_house = context['production_house']
    if not production_house:
        return {}, report
    if context['shared_hostile_houses']:
        report['skipped_reason'] = 'production_house_shared_with_hostile_house'
        return {}, report

    earned = {
        str(reward.get('unit') or '').upper()
        for reward in rewards or ()
        if reward.get('dta_production_access') and reward.get('unit')
    }
    report['clone_unlocked'] = sorted(earned)
    catalogue = catalogue_by_id()
    rules = {}
    for unit_id, target in sorted(catalogue.items()):
        if (
            target.get('category') not in {'infantry', 'vehicles', 'aircraft'}
            or not target.get('rewardable')
            or unit_id.startswith('AI')
            or unit_id in ALWAYS_AVAILABLE_MOBILE_IDS
            or target.get('duplicate_of')
        ):
            continue
        values = effective_section(installed, unit_id)
        # Earned production uses a player-only clone. Keep every randomized
        # original blocked for the player so enemy/map identities and native
        # build rules remain untouched.
        unlocked_original = False
        forbidden = _forbidden_houses(
            values,
            production_house,
            locked=not unlocked_original,
        )
        original = str(values.get('ForbiddenHouses') or '')
        if forbidden != original:
            rules[unit_id] = {'ForbiddenHouses': forbidden}
        report['locked'].append(unit_id)
    return rules, report
