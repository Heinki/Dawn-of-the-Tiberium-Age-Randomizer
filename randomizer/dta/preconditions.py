"""DTA campaign preconditions, independent of campaign completion unlocks."""

from functools import lru_cache

from randomizer.core.paths import GAME_ROOT
from randomizer.dta.rules import comma_items, ini_sections


@lru_cache(maxsize=1)
def campaign_preconditions():
    campaign = ini_sections(GAME_ROOT / 'INI' / 'Campaigns.ini')
    battle = ini_sections(GAME_ROOT / 'INI' / 'Battle.ini')
    definitions = {}
    # Index by list order, including unnamed/internal variables, like DTA.
    for index, variable in enumerate(campaign.get('GlobalVariables', {}).values()):
        values = campaign.get(variable, {})
        definitions[variable] = {
            'id': variable,
            'index': index,
            'label': values.get('UIName', variable),
            'description': values.get('ToolTip', ''),
            'enabled': values.get('UIEnabledOption', 'Yes'),
            'disabled': values.get('UIDisabledOption', 'No'),
        }
    return definitions, battle


def mission_preconditions(mission):
    definitions, battle = campaign_preconditions()
    values = battle.get(mission.get('code', ''), {})
    return [
        dict(definitions[variable])
        for variable in dict.fromkeys(comma_items(values.get('UsedGlobalVariables')))
        if variable in definitions
    ]


def selected_precondition_flags(mission, selections):
    """Accept only globals declared for this mission, never difficulty flags."""
    selected = selections.get(mission.get('code', ''), {}) if isinstance(selections, dict) else {}
    if not isinstance(selected, dict):
        selected = {}
    return {
        item['index']: int(selected.get(item['id']) in (True, 1, '1'))
        for item in mission_preconditions(mission)
    }


def precondition_map_rules(mission, flags):
    definitions, battle = campaign_preconditions()
    rules = {}
    for key, value in battle.get(mission.get('code', ''), {}).items():
        if not key.startswith('GlobalSpecificINIValue'):
            continue
        fields = value.split(',', 3)
        if len(fields) != 4:
            continue
        variable, section, option, setting = fields
        definition = definitions.get(variable)
        if definition and flags.get(definition['index'], 0):
            rules.setdefault(section, {})[option] = setting
    return rules
