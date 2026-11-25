"""Installed Advanced AI options and private-house tactic routing."""

from copy import deepcopy
from pathlib import Path

from randomizer.coop.catalogue import inherited_sections


OPTION_PATH = 'INI/Game Options/Advanced AI.ini'
TACTIC_LISTS = ('AdvancedAIGroundTactics', 'AdvancedAIAirTactics', 'AdvancedAINavalTactics')


def advanced_ai_sections(root):
    """Use the complete native option, including tactics and production values."""
    root = Path(root).resolve()
    path = root / OPTION_PATH
    if not path.is_file():
        raise ValueError('Installed DTA Advanced AI option is missing: ' + str(path))
    sections = inherited_sections(root, path)
    if sections.get('AI', {}).get('UseAdvancedAI', '').casefold() not in ('yes', 'true', '1'):
        raise ValueError('Installed DTA Advanced AI option does not enable Advanced AI.')
    if any(not sections.get(category) for category in TACTIC_LISTS):
        raise ValueError('Installed DTA Advanced AI tactics are incomplete. Repair the game installation.')
    return sections


def apply_advanced_ai(writer, sections):
    """Apply before private types are built so their AI values inherit the option."""
    rules = deepcopy(writer.rules)
    for section, values in sections.items():
        rules.setdefault(section, {}).update(values)
        for key, value in values.items():
            writer.put(section, key, value)
    # Enhance.ini reparents these AI variants, dropping the Image inherited
    # from their Classic AI parents. Their own IDs have no sprite files.
    # Write the art for native AI teams and for any private copies built later.
    vehicles = rules.get('VehicleTypes', {}).values()
    for variant, source in (('AIBIKE2', 'BIKE'), ('AISHILKA2', 'SHILKA')):
        if variant in vehicles and not rules[variant].get('Image'):
            image = rules[source].get('Image') or source
            rules[variant]['Image'] = image
            writer.put(variant, 'Image', image)
    writer.rules = rules
    return rules


def route_advanced_ai_tactics(writer, houses, computers):
    """Route exact HouseType filters to the registered combat participants.

    Vinifera checks HouseType HeapID for tactics and enemy-faction conditions;
    ActsLike alone does not select a native faction's Advanced AI tactics.
    Engine reference: Rampastring/Vinifera, dta-advaiv2-spawner,
    src/new/advai/advaitactictype.cpp, AdvancedAITacticTypeClass::Process.
    """
    native_indices = {country: int(index) for index, country
                      in writer.rules['Houses'].items() if str(index).isdigit()}
    factions = {index: native_indices[country] for index, country in houses.items()}
    routed = {}
    for house in sorted(computers):
        if house not in factions:
            raise ValueError('Advanced AI computer has no registered faction.')
        counts = {}
        for category in TACTIC_LISTS:
            count = 0
            for tactic_id in dict.fromkeys(writer.rules[category].values()):
                tactic = writer.rules.get(tactic_id, {})
                if str(tactic.get('House', '')) != str(factions[house]):
                    continue
                variants = [[]]
                for key in sorted((key for key in tactic if key.startswith('Conditions.')),
                                  key=lambda key: int(key.split('.')[-1])):
                    value = tactic[key]
                    fields = [field.strip() for field in value.split(',')]
                    condition = fields[0]
                    if condition in ('TACTICCOND_ENEMY_IS_HOUSETYPE', 'TACTICCOND_ENEMY_IS_NOT_HOUSETYPE'):
                        native = int(fields[1])
                        matches = sorted(index for index, faction in factions.items() if faction == native)
                        if condition == 'TACTICCOND_ENEMY_IS_NOT_HOUSETYPE':
                            alternatives = [[','.join([condition, str(index), *fields[2:]])
                                             for index in dict.fromkeys([native, *matches])]]
                        else:
                            alternatives = [[','.join([condition, str(index), *fields[2:]])]
                                            for index in dict.fromkeys([native, *matches])]
                    else:
                        alternatives = [[value]]
                    variants = [previous + alternative for previous in variants for alternative in alternatives]
                    if len(variants) > 128:
                        raise ValueError('Installed Advanced AI tactic has too many faction alternatives.')
                for conditions in variants:
                    alias = writer.key()
                    row = {key: value for key, value in tactic.items() if not key.startswith('Conditions.')}
                    row['House'] = str(house)
                    row.update({f'Conditions.{index}': value for index, value in enumerate(conditions)})
                    writer.sections[alias] = row
                    writer.register(category, alias)
                    count += 1
            counts[category] = count
        if not counts[TACTIC_LISTS[0]]:
            raise ValueError('Installed Advanced AI has no ground tactics for ' + houses[house])
        routed[str(house)] = counts
    return routed
