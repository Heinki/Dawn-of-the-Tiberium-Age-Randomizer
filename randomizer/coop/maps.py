"""Native cooperative map preparation with personal, production-only rewards."""

import hashlib

from randomizer.dta.clones import unit_specific_buff_rules
from randomizer.dta.maps import preserve_collateral_damage_coefficients
from randomizer.dta.rules import PLAYABLE_FACTIONS, ini_sections
from randomizer.maps.ini import IniLines, append_section_entry, section_value_map
from randomizer.maps.hooks import unique_section_key

from .catalogue import inherited_sections, matches_player_count, merge, native_options, resolve_path
from .compatibility import text_hash
from .feature import require_enabled
from .settings import safe_settings, supported_reward
from .victory import adapt_team_outcomes


def prepare_map(root, mission, rewards, difficulty, *, settings=None, credit_bonus=0, player_loadouts=None):
    require_enabled()
    if not matches_player_count(mission, mission['coop_player_count']):
        raise ValueError('Native co-op mission requires its authored player count; reduced-player preparation is disabled.')
    verify_dependencies(root, mission)
    source = resolve_path(root, mission['scenario'])
    sections = inherited_sections(root, source)
    spawn_settings, overlays = native_options(root, sections)
    requested = str(getattr(difficulty, 'label', difficulty))
    choices = [('Easy', 2), ('Medium', 1), ('Hard', 0), ('Brutal', 4)]
    rank = {'Easy': 0, 'Normal': 1, 'Hard': 2, 'Brutal': 3}.get(requested, 3)
    modes = {mode.strip() for mode in mission['coop_modes']}
    available = [(name, level) for name, level in choices if f'Co-Op {name}' in modes]
    if not available:
        raise ValueError('Native co-op mission has no supported difficulty mode.')
    name, handicap = next(((name, level) for name, level in reversed(choices[:rank + 1]) if (name, level) in available), available[0])
    overlays.append(resolve_path(root, f'INI/Map Code/Difficulty {name}.ini'))
    for overlay in overlays:
        merge(sections, inherited_sections(root, overlay))
    if player_loadouts is not None:
        from .production import player_production_rules
        sides, report = player_production_rules(root, mission, sections, player_loadouts)
        spawn_settings['_coop_player_sides'] = sides
        adapt_team_outcomes(mission, sections)
    else:
        report = _shared_production_rules(mission, rewards, settings, sections)
    sections.setdefault('Basic', {}).update({'SkipScore': 'no', 'EndOfGame': 'no'})
    # Flatten inheritance: spawnmap.ini lives outside Maps/Co-Op and must
    # never resolve inherited map filenames relative to the game root.
    sections.pop('INISystem', None)
    lines = IniLines([line for section, values in sections.items()
                      for line in [f'[{section}]', *(f'{key}={value}' for key, value in values.items()), '']])
    # Settings/Credits initializes AI as well as humans. Native action 106
    # targets Spawn houses (50–57), so personal bonuses/debits never touch AI.
    bonuses = ([item['credit_bonus'] for item in player_loadouts] if player_loadouts is not None
               else [credit_bonus] * mission['coop_player_count'])
    actions = []
    for slot, bonus in enumerate(bonuses):
        bonus = max(-int(spawn_settings['Credits']), int(bonus))
        if bonus:
            actions.append(f'106,0,{50 + slot},{bonus},0,0,0,A')
    if actions:
        trigger = unique_section_key(lines, ('Events', 'Actions', 'Triggers'), 'DTACC')
        tag = unique_section_key(lines, ('Tags',), 'DTACR')
        append_section_entry(lines, 'Events', trigger, '1,13,0,1')
        append_section_entry(lines, 'Actions', trigger, f'{len(actions)},' + ','.join(actions))
        # Trigger owners require real HouseTypes. Unlike action 106's target,
        # this field does not resolve virtual Spawn houses on maps that omit
        # them from [Houses]. The engine indexes HouseTypes[-1] in that case.
        append_section_entry(lines, 'Triggers', trigger, 'Neutral,<none>,Co-op Starting Credits,0,1,1,1,0')
        append_section_entry(lines, 'Tags', tag, f'0,Co-op Starting Credits,{trigger}')
    preserve_collateral_damage_coefficients(lines)
    validate_scripting(root, lines)
    data = ('\r\n'.join(lines) + '\r\n').encode('cp1252')
    spawn_settings.update({'AIDifficulty': str(handicap), 'DifficultyName': name,
                           'CoachMode': 'Yes', 'WriteStatistics': 'Yes'})
    return data, spawn_settings, report, hashlib.sha256(data).hexdigest()


def validate_scripting(root, lines):
    """Reject unresolved trigger owners and truncated engine script records."""
    installed = ini_sections(root / 'INI' / 'Rules.ini')
    houses = {name.casefold() for name in (
        *installed.get('Houses', {}).values(),
        *section_value_map(lines, 'Houses').values(),
    )}
    houses.add('<none>')  # The engine explicitly defaults this owner to HouseTypes[0].
    for section in ('Triggers', 'Events', 'Actions'):
        for key, value in section_value_map(lines, section).items():
            if len(value.encode('cp1252')) >= 512:
                raise ValueError(f'Co-op [{section}] {key} exceeds the engine script buffer.')
            if section == 'Triggers' and value.split(',')[0].strip().casefold() not in houses:
                raise ValueError(f'Co-op trigger {key} has an unregistered owner.')
            if section == 'Actions':
                tokens = value.split(',')
                if not tokens[0].isdigit() or len(tokens) != 1 + 8 * int(tokens[0]):
                    raise ValueError(f'Co-op action {key} has an invalid action count.')


def _shared_production_rules(mission, rewards, settings, sections):
    """Preserve the preparation API for callers without personal Shop data."""
    faction = PLAYABLE_FACTIONS[mission['coop_side']]
    production_context = {
        # Synthetic actor ensures no placed unit, scripted house or team is
        # routed to a clone. Every real human uses the native faction mask.
        'player_house': '__COOP_PRODUCTION_ONLY__',
        'production_house': faction, 'acts_like': mission['coop_side'],
        'shared_hostile_houses': [],
    }
    rules, report = unit_specific_buff_rules(
        mission, [reward for reward in rewards if supported_reward(reward)],
        access_randomized=False, production_context=production_context,
        source_sections=sections, human_only_production=True,
        shop_global_buff_levels=(settings or {}).get('shop_global_buff_levels'),
    )
    if report['map_objects_rewritten'] or report['player_taskforce_routes']:
        raise ValueError('Co-op rewards attempted to rewrite authored actors.')
    merge(sections, rules)
    return report


def verify_dependencies(root, mission):
    for name, digest in mission['coop_dependencies'].items():
        if text_hash(resolve_path(root, name).read_bytes()) != digest:
            raise ValueError('Native co-op map/options changed; refresh catalogue and generate a new run.')
