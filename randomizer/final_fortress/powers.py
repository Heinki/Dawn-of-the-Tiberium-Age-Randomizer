"""Adapt existing DTA player rewards to the human Fortress coalition."""

from copy import deepcopy

from randomizer.dta.powers import (
    POWER_SPEC_BY_ID,
    player_power_rules,
    power_unlock_rewards,
)
from randomizer.maps.ini import all_section_value_maps, section_value_map_preserve
from randomizer.rewards.dta_power_buffs import power_buff_stack_limit


def power_rewards(effects):
    """Use the same unlocks, supported buffs and caps as campaign/Grid/Shop."""
    unlocks = {r['superweapon'].upper(): r for r in power_unlock_rewards()}
    rewards = []
    for power in effects['support_powers']:
        rewards.append(deepcopy(unlocks[power.upper()]))
        spec = POWER_SPEC_BY_ID[power.upper()]
        for buff in spec['buffs']:
            # Building capacity belongs to Special Building Limit. DTA uses
            # separate power/provider identities so each launch site charges.
            count = (
                effects['special_building_limit_stacks']
                if buff == 'capacity'
                else effects['power_upgrade_stacks']
            )
            reward = {
                'dta_player_power_buff': True,
                'superweapon': spec['id'],
                'power_buff_type': buff,
            }
            rewards.extend(
                deepcopy(reward) for _ in range(min(count, power_buff_stack_limit(reward)))
            )
    return rewards


def apply_player_powers(writer, plan, aliases, runtime):
    """Share player power types; grant clicks and paradrop teams per human."""
    from .engine import FRIENDLY_ALIASES

    effects = plan['effects']
    rewards = power_rewards(effects)
    if not rewards:
        return
    authored = {
        section: section_value_map_preserve(writer.lines, section)
        for section in all_section_value_maps(writer.lines)
    }
    for section, values in writer.sections.items():
        authored.setdefault(section, {}).update(values)
    infantry = 'E1' if plan['player_country'] in ('GDI', 'Nod') else 'E1A'
    rules, actions, report = player_power_rules(
        {'code': 'DFF-' + plan['seed']},
        rewards,
        launch_building_ids=[
            alias for native, alias in aliases.items()
            if native in writer.rules['BuildingTypes'].values()
        ],
        paradrop_unit_routes={**aliases, 'E1S': aliases.get(infantry, infantry)},
        reserved_rules=writer.sections,
        production_context={
            'player_house': 'Spawn1',
            'production_house': FRIENDLY_ALIASES[0],
        },
        scenario_sections=authored,
        installed_sections=writer.rules,
        # Multiplayer allocates human HouseClass instances first. Spawn1 is
        # waypoint reference 50, not the host's native runtime heap ID (0).
        player_house_heap_id=0,
    )
    if report['skipped']:
        raise ValueError('Could not prepare DTA Fortress powers: ' + str(report['skipped']))
    runtime['rules'] = report.pop('_runtime_rules')
    runtime['art'] = report.pop('_runtime_art')
    for section, values in rules.items():
        writer.sections.setdefault(section, {}).update(values)

    humans = len(plan.get('coop_players', [])) or 1
    for provider in report['provider_buildings']:
        if not provider['buildable']:
            continue
        row = writer.sections[provider['provider']]
        row['Owner'] = row['RequiredHouses'] = ','.join(FRIENDLY_ALIASES[:humans])
        # Preserve ordinary economy perks on the new player-only providers.
        row['Cost'] = str(max(1, round(
            float(row.get('Cost', '0'))
            * (100 - effects['construction_discount_percent']) / 100
        )))
        row['BuildTimeMultiplier'] = str(
            float(row.get('BuildTimeMultiplier', '1'))
            * (100 - effects['production_percent']) / 100
        )
        source = aliases.get(provider['source'])
        if source:
            # Helpers can still construct their ordinary native power site;
            # humans use DTA's separate HumanOnly upgraded provider instead.
            writer.put(source, 'Buildability', 'AIOnly')

    waypoints = [plan['map']['player_waypoint'], *plan['allied_waypoints']][:humans]
    for seat, waypoint in enumerate(waypoints):
        if actions:
            writer.trigger(
                'Human player powers ' + str(seat), [(13, 0, 0)], actions,
                # Native action 34 dereferences the trigger's owner directly.
                # Spawn references work for placement/team actions, but do not
                # resolve here. Use this human's registered country instead.
                owner=FRIENDLY_ALIASES[seat],
            )
        # Vinifera chooses PARADROPINF_<HouseHeapID> for the clicking house.
        # Sharing a power must not send guests' infantry to the host.
        if seat and report['paradrop_team']:
            team = 'PARADROPINF_' + str(seat)
            writer.sections[team] = deepcopy(writer.sections[report['paradrop_team']])
            writer.put(team, 'House', 'Spawn' + str(waypoint + 1))
            writer.register('TeamTypes', team)
