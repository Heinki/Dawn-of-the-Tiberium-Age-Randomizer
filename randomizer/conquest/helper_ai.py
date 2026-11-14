"""Register native Conquest AI production and command its committed armies."""

from randomizer.dta.rules import comma_items, ini_sections
from randomizer.final_fortress.engine import _action, _route_native_ai
from randomizer.final_fortress.wave_pool import batches

from .teams import HOUSE_ALIASES


def _recipe_aliases(writer, member, private):
    """Resolve campaign-only factory conditions to live skirmish factories.

    DTA's AI.ini also contains campaign recipes referring to older *_AI
    buildings. Those conditions must use the same types as native Build*
    choices, including any house-specific upgrade copies.
    """
    buildings = set(writer.rules['BuildingTypes'].values())
    country = member['loadout']['country']
    aliases = {}
    for kind in buildings:
        if kind.endswith('_AI') and kind[:-3] in buildings:
            aliases[kind] = kind[:-3]
    # Some retired condition types no longer have a registered definition.
    ai = ini_sections(writer.root / 'INI/AI.ini')
    for value in ai.get('AITriggerTypes', {}).values():
        fields = value.split(',')
        if len(fields) >= 18 and fields[5].endswith('_AI') and fields[5][:-3] in buildings:
            aliases[fields[5]] = fields[5][:-3]
    for field, legacy in (('BuildRadar', ('HQ', 'RADOME_AI')),
                          ('BuildHelipad', ('HPAD_AI', 'AHPAD_AI'))):
        choices = comma_items(writer.rules.get('AI', {}).get(field))
        native = next((kind for kind in choices
                       if country in comma_items(writer.rules.get(kind, {}).get('Owner'))), None)
        if native:
            aliases.update(dict.fromkeys(legacy, native))
    return {**private, **{kind: private.get(native, native) for kind, native in aliases.items()}}


def start_computers(writer, members, private_types):
    """Keep ordinary native construction active, with or without any grants."""
    recipes = {m['slot']: _recipe_aliases(writer, m, private_types[m['slot']]) for m in members}
    for member in members:
        if member['controller'] != 'ai':
            continue
        slot, waypoint = member['slot'], member['waypoint']
        owner = HOUSE_ALIASES[slot]
        private = private_types[slot]
        # Custom registered HouseTypes need recipes even when no perk created
        # a private TechnoType. Otherwise their ActLike mask matches no AI.
        _route_native_ai(writer, member['loadout']['country'], owner, 6 + slot, recipes[slot],
                         opponent_aliases=[recipes[m['slot']] for m in members
                                           if m['team'] != member['team']])
        # Native MCV deployment seeds the base plan. Enable production after
        # deployment; do not replace that plan with a scripted build queue.
        actions = [_action(3, 50 + waypoint), _action(13, 50 + waypoint),
                   _action(30, 1), _action(74, 50 + waypoint)]
        writer.trigger('Start Conquest computer ' + owner, [(13, 0, 3)], actions, owner=owner)
        force = member['loadout']['force']
        units = [{'type': private.get(kind, kind), 'count': count}
                 for kind, count in force['units'].items() if kind != force['collector'] and count]
        # Create Team recruits existing owned units. Reinforce would duplicate
        # the committed army. Harvesters remain outside combat teams.
        for number, batch in enumerate(batches(units, 15)):
            team = writer.team('Conquest starting army', batch, waypoint, waypoint)
            writer.put(team, 'AreTeamMembersRecruitable', 'yes')
            # Separate triggers also keep the largest committed armies below
            # the native 512-byte Actions record limit.
            writer.trigger(f'Conquest starting army {owner} {number}', [(13, 0, 3)],
                           [_action(4, team=team)], owner=owner)
