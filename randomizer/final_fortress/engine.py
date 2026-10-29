"""Vinifera map/spawn adapter with the existing DTA player power helpers."""

from copy import deepcopy
from collections import Counter
import base64
import hashlib
from pathlib import Path
import re
from randomizer.core.storage import atomic_write_text
from randomizer.core.paths import GAME_ROOT
from randomizer.dta.rules import ini_sections, comma_items, installed_effective_sections
from randomizer.maps.ini import (
    IniLines, find_section_bounds, merge_ini_section_values, section_value_map,
)
from randomizer.maps.hooks import append_hook_team
from randomizer.coop.maps import validate_scripting
from .catalogue import SIDE_COUNTRIES, TYPE_LISTS
from .maps import inspect_map, source_lines, validate_layout
from .terrain import unpack

ACTORS = ('FFPLAYER', 'FFALLY1', 'FFALLY2')
ALIASES = ('GDI1', 'Nod1', 'GDI2', 'Nod2')
NATIVE_INDICES = (6, 7, 8, 9)
FRIENDLY_ALIASES = ('GDI1', 'Allies1', 'Allies2')
FRIENDLY_INDICES = (6, 10, 11)


def coalition(plan):
    return [
        (ACTORS[i], plan['player_country'], waypoint)
        for i, waypoint in enumerate([plan['map']['player_waypoint'], *plan['allied_waypoints']])
    ]


def marker_names(run_id, plan=None):
    if not isinstance(run_id, str) or not re.fullmatch('[0-9a-f]{32}', run_id):
        raise ValueError('Invalid DTA Fortress run ID.')
    prefix = 'DFF_' + hashlib.sha256(run_id.encode()).hexdigest()[:16]
    names = {
        event: prefix + suffix
        for event, suffix in [('started', '_START'), ('victory', '_WIN'), ('defeat', '_LOSS')]
    }
    for i in range(1, len((plan or {}).get('wave_schedule', range(11))) + 1):
        names[f'wave:{i}'] = prefix + f'_W{i:02}'
    for event in (plan or {}).get('gem_rewards', {}):
        if event not in names and not event.startswith(('kills:', 'challenge:')):
            names[event] = prefix + '_E' + hashlib.sha256(event.encode()).hexdigest()[:8]
    return names


def _waypoint(number):
    # Native waypoint encoding is Excel-like, zero based (A=0, Z=25, AA=26).
    result = ''
    number += 1
    while number:
        number, rest = divmod(number - 1, 26)
        result = chr(65 + rest) + result
    return result


def _action(code, value=0, *, team=None, trigger=None, waypoint=0, extra=0):
    return list(
        map(
            str,
            (
                code,
                1 if team else 2 if trigger else 0,
                team or trigger or value,
                extra,
                0,
                0,
                0,
                _waypoint(waypoint),
            ),
        )
    )


def _set_local(index, number):
    action = _action(124, index)
    action[4] = str(number)
    return action


def _countdowns(writer, plan, finished):
    """DTA's native templated overlay follows actual delivery timer resets."""
    clocks = {}
    for name, initial in [
        ('victory', 3600),
        ('enemy', 300),
        *[(actor, 300) for actor, _, _ in coalition(plan) if plan['effects']['reinforcements']],
    ]:
        index = writer.flag('DFF_' + name)
        clocks[name] = index
        writer.trigger(
            'Initialize ' + name + ' countdown', [(13, 0, 0)], [_set_local(index, initial)]
        )
        writer.trigger(
            name + ' countdown tick',
            [(13, 0, 1), (37, 0, finished), (68, 4, index, 0, 0)],
            [_action(128, index)],
            persistence=2,
        )
    text = 'Until Victory: {{l_DFF_victory}} s | Next enemy wave: {{l_DFF_enemy}} s'
    for seat, (actor, _, _) in enumerate(coalition(plan)):
        if actor in clocks:
            name = (
                plan.get('coop_players', ['Player'])[seat]
                if seat < (len(plan.get('coop_players', [])) or 1)
                else f'Helper {seat}'
            )
            text += f' | {name} allied: {{{{l_DFF_{actor}}}}} s'
    writer.put('Tutorial', 'DFF_CLOCKS', text)
    writer.trigger('Display Fortress countdowns', [(13, 0, 0)], [_action(133, 'DFF_CLOCKS')])
    writer.trigger('Stop Fortress countdowns', [(36, 0, finished)], [_action(134)])
    return clocks


class MapWriter:
    def __init__(self, lines, rules, root=GAME_ROOT):
        self.lines = lines
        self.rules = rules
        self.root = Path(root)
        self.sections = {}
        self.counter = 0
        self.variable_counter = 0

    def key(self):
        self.counter += 1
        return f'DFF{self.counter:05X}'

    def put(self, section, key, value):
        self.sections.setdefault(section, {})[str(key)] = str(value)

    def register(self, category, kind):
        values = self.sections.setdefault(category, {})
        if kind not in values.values() and kind not in self.rules.get(category, {}).values():
            keys = [int(k) for k in (*values, *self.rules.get(category, {})) if str(k).isdigit()]
            values[str(max([19999, *keys]) + 1)] = kind

    def flag(self, name):
        value = self.variable_counter
        self.variable_counter += 1
        if value >= 500:
            raise ValueError('DTA Fortress exhausted native local variables.')
        self.put('VariableNames', value, name + ',0')
        return value

    def actions(self, key, actions):
        self.put(
            'Actions',
            key,
            ','.join([str(len(actions)), *(token for action in actions for token in action)]),
        )

    def trigger(
        self,
        name,
        events,
        actions,
        *,
        disabled=False,
        persistence=0,
        owner='Neutral',
        linked='<none>',
    ):
        key, tag = self.key(), self.key()
        self.put('Triggers', key, f'{owner},{linked},{name},{int(disabled)},1,1,1,0')
        self.put('Tags', tag, f'{persistence},{name},{key}')
        self.put('Events', key, ','.join(map(str, [len(events), *(t for e in events for t in e)])))
        self.actions(key, actions)
        return key, tag

    def team(self, name, units, owner, waypoint, *, attack=True, tag=None, veterancy=0):
        if not 1 <= len(units) <= 6:
            raise ValueError('Native DTA teams require one to six types.')
        team, force, script = self.key(), self.key(), self.key()
        for category, kind in [('TeamTypes', team), ('TaskForces', force), ('ScriptTypes', script)]:
            self.register(category, kind)
        self.sections[force] = {
            'Name': name,
            'Group': '-1',
            **{str(i): f'{u["count"]},{u["type"]}' for i, u in enumerate(units)},
        }
        self.sections[script] = {
            'Name': name,
            **({'0': '0,1', '1': '6,1'} if attack else {'0': '11,5'}),
        }
        self.sections[team] = {
            'Name': name,
            'House': f'Spawn{owner+1}',
            'TaskForce': force,
            'Script': script,
            'Waypoint': _waypoint(waypoint),
            'Max': '1',
            'Priority': '50',
            'Group': '-1',
            'TechLevel': '0',
            'Autocreate': 'no',
            'Prebuild': 'no',
            'Recruiter': 'no',
            'Reinforce': 'no',
            'LooseRecruit': 'no',
            'Full': 'no',
            'Whiner': 'no',
            'Suicide': 'no',
            'Aggressive': 'yes' if attack else 'no',
            'AvoidThreats': 'no',
            'VeteranLevel': str(veterancy + 1),
            'Loadable': 'no',
            'OnTransOnly': 'no',
        }
        if tag:
            self.put(team, 'Tag', tag)
        return team

    def reinforce(self, team):
        action = _action(80, team=team)
        action[-1] = self.sections[team]['Waypoint']
        return action

    def place(
        self, section, kind, position, *, tag='None', veterancy=0, mission='Guard', owner='Neutral'
    ):
        p = position
        index = len(self.sections.get(section, {})) + 10000
        if section == 'Structures':
            value = f'{owner},{kind},256,{p["x"]},{p["y"]},0,{tag},1,0,1,0,0,None,None,None,0,0'
        elif section == 'Infantry':
            value = (
                f'{owner},{kind},256,{p["x"]},{p["y"]},0,{mission},0,{tag},{veterancy*100},-1,0,-1'
            )
        else:
            value = (
                f'{owner},{kind},256,{p["x"]},{p["y"]},0,{mission},{tag},{veterancy*100},-1,0,-1'
            )
        self.put(section, index, value)

    def transfer_tag(self, waypoint, name, *, linked='<none>'):
        trigger, tag = self.trigger(name, [(13, 0, 0)], [], persistence=2, linked=linked)
        self.actions(trigger, [_action(14, 50 + waypoint), _action(54, trigger=trigger)])
        return tag

    def message(self, text):
        key = self.key()
        self.put('Tutorial', key, text)
        return _action(11, key)

    def finish(self):
        # Packed streams must remain in numeric chunk order. The ordinary INI
        # merger sorts newly appended keys as text (1000 before 130), which
        # corrupts compressed data when a rewritten stream gains more rows.
        packed_sections = ('OverlayPack', 'OverlayDataPack', 'IsoMapPack5')
        for section in packed_sections:
            values = self.sections.get(section)
            if not values:
                continue
            rows = [f'{key}={values[key]}' for key in sorted(values, key=int)]
            start, end = find_section_bounds(self.lines, section)
            if start is None:
                self.lines.extend(['', f'[{section}]', *rows])
            else:
                self.lines[start + 1:end] = rows
        merge_ini_section_values(
            self.lines,
            {key: values for key, values in self.sections.items() if key not in packed_sections},
        )
        for section in ('OverlayPack', 'OverlayDataPack'):
            if len(unpack(section_value_map(self.lines, section))) != 512 * 512:
                raise ValueError('Invalid generated DTA packed overlay: ' + section)
        validate_scripting(self.root, self.lines)
        return ('\r\n'.join(self.lines) + '\r\n').encode('cp1252')


def _category(rules, kind):
    for category in TYPE_LISTS:
        if kind in rules[category].values():
            return category
    raise ValueError('Unregistered native DTA type: ' + kind)


def _defense_slots(available, center, count):
    """Choose a small, distributed screen from already reviewed clear slots."""
    directions = [(0, -7), (0, 7)] if count == 2 else [(-7, 0), (0, -7), (7, 0), (0, 7)]
    result = []
    for number in range(count):
        dx, dy = directions[number % len(directions)]
        target = (center['x'] + dx, center['y'] + dy)
        index = min(range(len(available)), key=lambda i: (
            (available[i]['x'] - target[0]) ** 2 + (available[i]['y'] - target[1]) ** 2, i
        ))
        result.append(available.pop(index))
    return result


def _private_type(writer, kind, *, suffix, owners, stats=None, cache=None):
    cache = {} if cache is None else cache
    if kind in cache:
        return cache[kind]
    original = writer.rules[kind]
    category = _category(writer.rules, kind)
    alias = writer.key()
    cache[kind] = alias
    writer.register(category, alias)
    row = deepcopy(original)
    row.pop('$Inherits', None)
    row.pop('BaseSection', None)
    row.update(
        Image=original.get('Image', kind),
        Owner=','.join(owners),
        RequiredHouses=','.join(owners),
        ForbiddenHouses='',
        AllowedToStartInMultiplayer='no',
    )
    if stats:
        row.update(stats)
    writer.sections[alias] = row
    for field in ('DeploysInto', 'UndeploysInto', 'TransformsInto'):
        target = row.get(field, '')
        if target in writer.rules and any(target in writer.rules[c].values() for c in TYPE_LISTS):
            row[field] = _private_type(writer, target, suffix=suffix, owners=owners, cache=cache)
    return alias


def _enemy_rules(writer, plan):
    """Route native enemy production and tier effects through private masks/types."""
    from randomizer.dta.rules import techno_catalogue

    records = {r['id']: r for r in techno_catalogue()}
    result = []
    for enemy, country in enumerate(plan['enemy_countries']):
        owner = ALIASES[enemy + 1]
        aliases = {}
        for category in TYPE_LISTS[:3]:
            for kind in writer.rules[category].values():
                row = writer.rules[kind]
                record = records.get(kind)
                if record is not None and country not in record['playable_owners']:
                    continue
                if record is None and country not in comma_items(row.get('Owner')):
                    continue
                stats, weapon_counts = _challenge_type_stats(writer, plan, kind)
                alias = _private_type(
                    writer, kind, suffix='EN', owners=[owner], stats=stats, cache=aliases
                )
                for field in ('Primary', 'Secondary', 'Elite', 'ElitePrimary', 'EliteSecondary'):
                    weapon = row.get(field)
                    if weapon not in writer.rules or not weapon_counts:
                        continue
                    new = writer.key()
                    values = deepcopy(writer.rules[weapon])
                    from randomizer.dta.clones import _weapon_overrides

                    values.update(_weapon_overrides(values, weapon_counts))
                    writer.sections[new] = values
                    writer.put(alias, field, new)
                forbidden = list(
                    comma_items(
                        writer.sections.get(kind, {}).get(
                            'ForbiddenHouses', row.get('ForbiddenHouses')
                        )
                    )
                )
                if owner not in forbidden:
                    forbidden.append(owner)
                writer.put(kind, 'ForbiddenHouses', ','.join(forbidden))
        # Native AI's first-ownable lookup ignores ForbiddenHouses. Originals
        # must also relinquish this mask when a private identity replaces them.
        for kind in aliases:
            values = {**writer.rules[kind], **writer.sections.get(kind, {})}
            writer.put(kind, 'Owner', ','.join(
                v for v in comma_items(values.get('Owner')) if v != owner
            ))
        for field in ('BaseUnit', 'HarvesterUnit', 'PadAircraft'):
            original = comma_items(writer.rules.get('General', {}).get(field))
            current = comma_items(writer.sections.get('General', {}).get(
                field, writer.rules.get('General', {}).get(field)
            ))
            additions = [aliases[k] for k in original if k in aliases]
            if additions:
                writer.put('General', field, ','.join(dict.fromkeys([*current, *additions])))
        for key, value in writer.rules.get('AI', {}).items():
            if key.startswith('Build'):
                items = list(comma_items(writer.sections.get('AI', {}).get(key, value)))
                additions = [aliases[v] for v in comma_items(value) if v in aliases]
                if additions:
                    writer.put('AI', key, ','.join(dict.fromkeys([*items, *additions])))
        result.append(aliases)
    return result


def _route_native_ai(writer, country, owner, mask, aliases, *, opponent_aliases=()):
    ai = ini_sections(writer.root / 'INI/AI.ini')
    # Native AI recipes are duplicated for the exact private HouseType.
    teams = {}
    forces = {}

    def force(key):
        if key not in forces:
            new = writer.key()
            forces[key] = new
            values = deepcopy(ai[key])
            for index, value in list(values.items()):
                if index.isdigit():
                    count, kind = value.split(',', 1)
                    values[index] = count + ',' + aliases.get(kind, kind)
            writer.sections[new] = values
            writer.register('TaskForces', new)
        return forces[key]

    def team(key):
        if key not in teams:
            new = writer.key()
            teams[key] = new
            values = deepcopy(ai[key])
            values['House'] = owner
            if values.get('TaskForce') in ai:
                values['TaskForce'] = force(values['TaskForce'])
            script = values.get('Script')
            if script in ai:
                writer.sections[script] = deepcopy(ai[script])
                writer.register('ScriptTypes', script)
            writer.sections[new] = values
            writer.register('TeamTypes', new)
        return teams[key]

    for key, value in ai.get('AITriggerTypes', {}).items():
        fields = value.split(',')
        if len(fields) < 18:
            continue
        native_index = SIDE_COUNTRIES.index(country)
        if fields[2] not in ('<all>', country):
            continue
        if int(fields[12]) not in (0, native_index + 1):
            continue
        fields[2] = owner
        fields[12] = str(mask + 1)
        for index in (1, 14):
            if fields[index] in ai:
                fields[index] = team(fields[index])
        if fields[4] == '1':  # This house owns the condition type.
            conditions = [aliases.get(fields[5], fields[5])]
        elif fields[4] == '0' and opponent_aliases:
            # Enemy-owned conditions must inspect opponents' private types,
            # rather than this AI's own private production identities.
            conditions = list(dict.fromkeys(
                opponent.get(fields[5], fields[5]) for opponent in opponent_aliases
            ))
        else:
            conditions = [fields[5]]
        for condition in conditions:
            routed = list(fields)
            routed[5] = condition
            new = writer.key()
            writer.put('AITriggerTypes', new, ','.join(routed))
            writer.put('AITriggerTypesEnable', new, 'yes')


def _challenge_type_stats(writer, plan, kind):
    from randomizer.dta.clones import _unit_overrides
    from randomizer.rewards.catalogue import BUFF_TARGETS
    from randomizer.shop.catalogue import _unit_tiers
    from .challenges import definition

    row = writer.rules[kind]
    native = kind if kind in BUFF_TARGETS else row.get('Image', kind)
    target = BUFF_TARGETS.get(native)
    counts = Counter()
    if target:
        unit_tier = int(_unit_tiers().get(native, 'tier_1')[-1])
        for entry in plan['challenges']:
            effect = definition(entry)
            if effect['effect'] == 'unit' and effect['tier'] == unit_tier:
                counts[effect['unit_buff_type']] += entry['stacks']
    return (_unit_overrides(row, counts, target) if target else {}), counts


def _player_rules(writer, plan):
    """Shared friendly private types include every human/helper country mask."""
    from randomizer.dta.rules import techno_catalogue
    from .catalogue import tier
    from .utilities import unit_updates, weapon_updates

    effects = plan['effects']
    faction = plan['player_country']
    country = ALIASES[0]
    aliases = {}
    original_types = {v: c for c in TYPE_LISTS for v in writer.rules[c].values()}
    records = {r['id']: r for r in techno_catalogue()}
    duplicates = {
        kind: record['duplicate_of'] for kind, record in records.items()
        if record.get('duplicate_of') and record['buildable']
    }
    sources = {}
    for kind, canonical in duplicates.items():
        # The catalogue shares E1A/E1S and E3A/E3S reward identities. Prefer
        # the faction's native variant so Soviet speech remains Soviet.
        required = comma_items(writer.rules[kind].get('RequiredHouses'))
        canonical_required = comma_items(writer.rules[canonical].get('RequiredHouses'))
        if faction in required and canonical_required and faction not in canonical_required:
            sources[canonical] = kind
    for kind, category in original_types.items():
        if kind in duplicates:
            continue
        source_kind = sources.get(kind, kind)
        row = writer.rules[source_kind]
        record = records.get(kind)
        if record is not None and faction not in record['playable_owners']:
            continue
        if record is None and faction not in comma_items(row.get('Owner')):
            continue
        if kind.startswith('AI') or row.get('Buildability', '').casefold() == 'aionly':
            continue
        stats = {}
        cost = float(row.get('Cost', '0'))
        discount = (
            effects['construction_discount_percent']
            if category == 'BuildingTypes'
            else effects['unit_discount_percent']
        )
        if cost > 0:
            stats['Cost'] = str(max(1, round(cost * (100 - discount) / 100)))
        stats['BuildTimeMultiplier'] = str(
            float(row.get('BuildTimeMultiplier', '1')) * (100 - effects['production_percent']) / 100
        )
        native_limit = max(
            int(row.get('BuildLimit') or '0'), records.get(kind, {}).get('build_limit', 0)
        )
        if effects.get('unique_limit_stacks') and category != 'BuildingTypes' and native_limit > 0:
            stats['BuildLimit'] = str(native_limit + effects['unique_limit_stacks'])
        if effects.get('special_building_limit_stacks') and category == 'BuildingTypes':
            from randomizer.dta.clones import _unit_overrides

            stats.update(_unit_overrides(
                row,
                Counter(build_limit=effects['special_building_limit_stacks']),
                {'build_limit': native_limit},
            ))
        if float(row.get('Power', '0')) > 0 and effects.get('generator_power_percent'):
            stats['Power'] = str(
                round(float(row['Power']) * (100 + effects['generator_power_percent']) / 100)
            )
        record = records.get(kind)
        percent = (
            effects['tier_buffs'].get(str(tier(record)), 0)
            if record and category != 'BuildingTypes'
            else 0
        )
        if percent:
            stats['Strength'] = str(round(float(row.get('Strength', 1)) * (100 + percent) / 100))
        defense = bool(record and record['category'] == 'defenses')
        stats.update(unit_updates(
            kind, {**row, **stats}, effects, building=category == 'BuildingTypes',
            defense=defense,
        ))
        if effects['healing_stacks'] and record and record.get('strength', 0) > 0:
            native_healing = row.get('SelfHealing', '').casefold() in ('yes', 'true', '1') or any(
                'SELF_HEAL' in row.get(field, '').upper()
                for field in ('VeteranAbilities', 'EliteAbilities')
            )
            step = max(
                int(row.get('SelfHealingStep', '0')),
                int(writer.rules['General'].get('SelfHealStep', '1')) if native_healing else 0,
                round(
                    float(stats.get('Strength', row.get('Strength', '1')))
                    * effects['healing_stacks']
                    / 100
                ),
                1,
            )
            stats.update(
                SelfHealing='yes',
                SelfHealingCap='100%',
                SelfHealingRate=row.get(
                    'SelfHealingRate', writer.rules['General'].get('SelfHealRate', '.016')
                ),
                SelfHealingStep=str(step),
            )
        if effects['recon_stacks'] and record:
            native_sight = int(row.get('Sight', '0'))
            stats['Sight'] = str(max(native_sight, min(10, native_sight + effects['recon_stacks'])))
            if category in ('VehicleTypes', 'BuildingTypes'):
                stats.update(
                    Sensors='yes',
                    SensorsSight=str(
                        max(int(row.get('SensorsSight', '0')), effects['recon_stacks'])
                    ),
                )
        # Native AI's first-ownable building lookup checks the actual country,
        # so helper country IDs must be explicit even with shared ActsLike.
        alias = _private_type(
            writer, source_kind, suffix='FR', owners=list(FRIENDLY_ALIASES), stats=stats,
            cache=aliases,
        )
        aliases[kind] = alias
        private = writer.sections[alias]
        # A mobile type may already have created its deployed building clone.
        # Apply this building's own limits and economy even when it was cached.
        private.update(stats)
        if kind in effects['special_access']:
            private.update(
                TechLevel='1',
                BuildLimit=str(
                    max(1, int(row.get('BuildLimit') or '1')) + effects['unique_limit_stacks']
                ),
            )
            from randomizer.dta.clones import PRODUCTION_BUILDINGS

            production = PRODUCTION_BUILDINGS[faction.casefold()]
            factory_group = (
                'infantry'
                if category == 'InfantryTypes'
                else 'air' if category == 'AircraftTypes' else 'vehicles'
            )
            factories = production[factory_group]
            private['BuiltAt'] = ','.join(factories)
            private['Prerequisite'] = ','.join(factories)
        if kind in effects.get('support_technology', ()):
            private['TechLevel'] = '1'
            if category == 'BuildingTypes':
                yard = {'GDI': 'GFACT', 'Nod': 'NFACT', 'Allies': 'AFACT', 'Soviet': 'SFACT'}[faction]
                private['Prerequisite'] = yard + ',RADAR'
            else:
                from randomizer.dta.clones import PRODUCTION_BUILDINGS

                factories = PRODUCTION_BUILDINGS[faction.casefold()]['vehicles']
                private['BuiltAt'] = ','.join(factories)
                private['Prerequisite'] = ','.join([*factories, 'RADAR'])
        for field in ('Primary', 'Secondary', 'Elite', 'ElitePrimary', 'EliteSecondary'):
            weapon = row.get(field)
            if not weapon or weapon not in writer.rules:
                continue
            bonus = effects['defense_percent'] if defense else percent
            values = deepcopy(writer.rules[weapon])
            utility = weapon_updates(kind, weapon, values, effects)
            if not bonus and not utility:
                continue
            new = writer.key()
            factor = 1 + bonus / 100
            if float(values.get('Damage', '0')) > 0:
                values['Damage'] = str(round(float(values['Damage']) * factor))
            if float(values.get('ROF', '0')) > 0:
                values['ROF'] = str(max(1, round(float(values['ROF']) / factor)))
            if defense and float(values.get('Range', '0')) > 0:
                values['Range'] = f'{min(30,float(values["Range"])*factor):g}'
            values.update(utility)
            writer.sections[new] = values
            private[field] = new
    for kind, canonical in duplicates.items():
        if canonical in aliases:
            # Starting troops, paradrops and native helper AI recipes may use
            # either identity, but they must all resolve to the same clone.
            aliases[kind] = aliases[canonical]
    # Native originals remain usable by enemies; humans see only private copies.
    # Block every alias too, rather than exposing an unmodified second entry.
    for kind in aliases:
        row = writer.rules[kind]
        forbidden = list(comma_items(row.get('ForbiddenHouses')))
        for friendly in FRIENDLY_ALIASES:
            if friendly not in forbidden:
                forbidden.append(friendly)
        writer.put(kind, 'ForbiddenHouses', ','.join(forbidden))
        source = {**row, **writer.sections.get(kind, {})}
        writer.put(kind, 'Owner', ','.join(
            v for v in comma_items(source.get('Owner')) if v not in FRIENDLY_ALIASES
        ))
    # PrerequisiteGroups implement OR without losing ordinary expansion yards.
    for kind, alias in aliases.items():
        row = writer.sections[alias]
        for field in ('Prerequisite', 'BuiltAt', 'Dock', 'FreeUnit', 'Owner'):
            if field == 'Owner':
                continue
            if field in row:
                row[field] = ','.join(aliases.get(v, v) for v in comma_items(row[field]))
    for key, value in writer.rules.get('General', {}).items():
        if key.startswith('Prerequisite') or key in (
            'BuildConst',
            'BaseUnit',
            'HarvesterUnit',
            'PadAircraft',
            'BuildRefinery',
        ):
            items = list(comma_items(value))
            additions = [aliases[v] for v in items if v in aliases]
            if additions:
                writer.put('General', key, ','.join([*items, *additions]))
    for key, value in writer.rules.get('PrerequisiteGroups', {}).items():
        items = list(comma_items(value))
        writer.put(
            'PrerequisiteGroups',
            key,
            ','.join([*items, *[aliases[v] for v in items if v in aliases]]),
        )
    for key, value in writer.rules.get('AI', {}).items():
        if key.startswith('Build'):
            items = list(comma_items(value))
            additions = [aliases[v] for v in items if v in aliases]
            if additions:
                writer.put('AI', key, ','.join([*items, *additions]))
    return aliases


def _tracked_units(writer, units, owner, aliases, cache):
    """Separate scripted survivors from ordinary AI recruitment and production."""
    result = []
    for unit in units:
        native = unit['type']
        source = aliases.get(native, native)
        key = (owner, source)
        if key not in cache:
            original = writer.sections.get(source, writer.rules.get(source))
            if original is None:
                raise ValueError('Unknown scripted type: ' + source)
            if original.get('Spawns', '').casefold() not in ('', 'none'):
                raise ValueError('Scripted aircraft spawners require a separate population budget.')
            kind = writer.key()
            cache[key] = kind
            category = next(
                (
                    c
                    for c in TYPE_LISTS
                    if source in writer.rules[c].values()
                    or source in writer.sections.get(c, {}).values()
                ),
                None,
            )
            if category is None:
                raise ValueError('Unregistered scripted type: ' + source)
            row = deepcopy(original)
            row.update(
                TechLevel='-1', BuildLimit='0', Crewed='no', AllowedToStartInMultiplayer='no'
            )
            if category == 'AircraftTypes':
                # Dedicated scripted VTOL attacks do not require captured or
                # newly built pads. Unlimited ammunition prevents untracked
                # rearm/return cycles; ordinary aircraft retain native ammo.
                row['Ammo'] = '-1'
            writer.sections[kind] = row
            writer.register(category, kind)
        result.append({'type': cache[key], 'count': unit['count']})
    return result


def _encode_lcw(data):
    """Encode native LCW literals and repeated overlay values."""
    import struct

    output = bytearray()
    literals = bytearray()

    def flush():
        for offset in range(0, len(literals), 63):
            chunk = literals[offset:offset + 63]
            output.append(0x80 + len(chunk))
            output.extend(chunk)
        literals.clear()

    cursor = 0
    while cursor < len(data):
        end = cursor + 1
        while end < len(data) and data[end] == data[cursor] and end - cursor < 65535:
            end += 1
        if end - cursor >= 4:
            flush()
            output.extend(b'\xfe' + struct.pack('<H', end - cursor) + data[cursor:cursor + 1])
        else:
            literals.extend(data[cursor:end])
        cursor = end
    flush()
    output.append(0x80)
    return bytes(output)


def _camp_crates(writer, plan, markers, finished, player_aliases, enemy_aliases):
    """Native visual crates, one shared claim flag, collector-specific frozen payload."""
    from .terrain import unpack

    overlay = bytearray(unpack(section_value_map(writer.lines, 'OverlayPack')))
    no_build_index = list(writer.rules['OverlayTypes'].values()).index('NOBUILD')
    for layout in plan['map']['perk_layouts'].values():
        p = layout['arrival']
        for dx in range(-2, 3):
            for dy in range(-1, 2):
                overlay[(p['y'] + dy) * 512 + p['x'] + dx] = no_build_index
    # OverlayPack values are ordinal OverlayTypes indices, not INI key numbers.
    crate_index = list(writer.rules['OverlayTypes'].values()).index('CRATE')
    friends = coalition(plan)
    humans = len(plan.get('coop_players', [])) or 1
    collectors = [(wp, seat if seat < humans else 0) for seat, (_, _, wp) in enumerate(friends)]
    collectors.extend((wp, 0) for wp in plan['map']['enemy_waypoints'])
    for i, camp in enumerate(plan['map']['camps']):
        p = camp['position']
        overlay[p['y'] * 512 + p['x']] = crate_index
        claimed = writer.flag('Camp ' + camp['id'] + ' claimed')
        previous = '<none>'
        first_tag = None
        waypoint = 30 + i
        writer.put('Waypoints', waypoint, p['y'] * 1000 + p['x'])
        for wp, seat in collectors:
            reward = camp['crate_reward']
            actions = [
                _action(56, claimed),
                _action(4, team=markers['camp:' + camp['id']]),
                _action(4, team=markers[f'camp_pick:{seat}:' + camp['id']]),
            ]
            recipient = friends[seat][2]
            if reward['credits']:
                actions.append(_action(106, 50 + recipient, extra=reward['credits']))
            for unit in reward['units']:
                team = writer.team(
                    'Fortress camp reward ' + camp['id'],
                    [
                        {
                            'type': player_aliases.get(unit['type'], unit['type']),
                            'count': unit['count'],
                        }
                    ],
                    recipient,
                    waypoint,
                    attack=False,
                )
                actions.append(writer.reinforce(team))
            actions.append(writer.message('Camp collected: ' + reward['display_name']))
            trigger, tag = writer.trigger(
                'Camp ' + camp['id'] + ' pickup',
                [(1, 0, 50 + wp), (37, 0, claimed), (37, 0, finished)],
                actions,
                persistence=2,
                linked=previous,
            )
            previous = trigger
            first_tag = tag
        writer.put('CellTags', p['y'] * 1000 + p['x'], first_tag)
        # Guards retain Area Guard and never enter normal AI recruitment pools.
        owner = plan['map']['enemy_waypoints'][camp['enemy_index']]
        tag = writer.transfer_tag(owner, 'Camp ' + camp['id'] + ' owner')
        positions = iter(camp['guard_positions'])
        for unit in camp['guards']:
            native = unit['type']
            stats, counts = _challenge_type_stats(writer, plan, native)
            kind = _private_type(
                writer,
                native,
                suffix='CAMP',
                owners=[ALIASES[camp['enemy_index'] + 1]],
                stats={
                    **stats,
                    'TechLevel': '-1',
                    'BuildLimit': '0',
                    'AllowedToStartInMultiplayer': 'no',
                },
            )
            if counts:
                from randomizer.dta.clones import _weapon_overrides

                for field in ('Primary', 'Secondary', 'Elite', 'ElitePrimary', 'EliteSecondary'):
                    weapon = writer.rules[native].get(field)
                    if weapon not in writer.rules:
                        continue
                    new = writer.key()
                    values = deepcopy(writer.rules[weapon])
                    values.update(_weapon_overrides(values, counts))
                    writer.sections[new] = values
                    writer.put(kind, field, new)
            for _ in range(unit['count']):
                writer.place(
                    (
                        'Infantry'
                        if _category(writer.rules, unit['type']) == 'InfantryTypes'
                        else 'Units'
                    ),
                    kind,
                    next(positions),
                    tag=tag,
                    mission='Area Guard',
                )
    packed = bytearray()
    # Even an incompressible literal block must fit LCWStraw's native buffer.
    for offset in range(0, len(overlay), 4096):
        chunk = overlay[offset : offset + 4096]
        encoded = _encode_lcw(chunk)
        packed.extend(__import__('struct').pack('<HH', len(encoded), len(chunk)))
        packed.extend(encoded)
    value = base64.b64encode(packed).decode()
    writer.sections['OverlayPack'] = {
        str(i // 70 + 1): value[i : i + 70] for i in range(0, len(value), 70)
    }
    # Only cash crates, with zero native payout; actual contents come from pickup actions.
    writer.put('General', 'SoloCrateMoney', 0)
    writer.put('General', 'WoodCrate', 'Money')
    writer.put('Powerups', 'Money', '100,MONEY,0')
    for key in writer.rules.get('Powerups', {}):
        if key != 'Money':
            parts = writer.rules['Powerups'][key].split(',')
            parts[0] = '0'
            writer.put('Powerups', key, ','.join(parts))


def _delivery_chain(
    writer,
    plan,
    deliveries,
    pools,
    finished,
    *,
    name,
    marker=None,
    clock=None,
    upgrader=None,
    late_flag=None,
):
    """Native semipersistent all-member death tags release small living reservations.

    Scripts loop rather than disbanding. Tracked units have no deploy, transform,
    passengers or aircraft spawns. A missing death callback holds capacity safely.
    """
    timers = [
        writer.trigger(
            name + f' interval {i}', [(13, 0, 300), (37, 0, finished)], [], disabled=i > 0
        )[0]
        for i in range(len(deliveries))
    ]
    for i, groups in enumerate(deliveries):
        sequence = writer.flag(name + f' delivery sequence {i}')
        chunks = []
        for owner, waypoint, units, attack, veterancy in groups:
            from .wave_pool import batches

            chunks.extend(
                (owner, waypoint, batch, attack, veterancy)
                for batch in batches(units, pools[0]['capacity'])
            )
        relays = [
            writer.trigger(
                name + f' delivery {i}:{n}', [(13, 0, 0), (37, 0, finished)], [], disabled=True
            )[0]
            for n in range(len(chunks) + 1)
        ]
        writer.actions(timers[i], [_action(53, trigger=relays[0])])
        for n, (owner, waypoint, units, attack, veterancy) in enumerate(chunks):
            gates = []
            variants = [(None, units)]
            if upgrader and i < 5:
                variants = [(False, units), (True, upgrader(i, owner, units))]
            for phase, roster in variants:
                for pool in pools:
                    if pool.get('owner') not in (None, owner):
                        continue
                    events = [(37, 0, pool['busy']), (37, 0, finished), (71, 3, sequence, n)]
                    if phase is not None:
                        events.append((36 if phase else 37, 0, late_flag))
                    gate, _ = writer.trigger(name + ' capacity', events, [], disabled=True)
                    release, tag = writer.trigger(
                        name + ' group destroyed',
                        [(7, 0, 0)],
                        [_action(57, pool['busy'])],
                        persistence=1,
                    )
                    team = writer.team(
                        name + f' {i}:{n}',
                        roster,
                        owner,
                        waypoint,
                        attack=attack,
                        tag=tag,
                        veterancy=veterancy,
                    )
                    gates.append((gate, pool, team))
            writer.actions(relays[n], [_action(53, trigger=gate) for gate, _, _ in gates])
            for gate, pool, team in gates:
                writer.actions(
                    gate,
                    [
                        _set_local(sequence, n + 1),
                        _action(56, pool['busy']),
                        writer.reinforce(team),
                        _action(53, trigger=relays[n + 1]),
                    ],
                )
        actions = []
        if marker:
            actions.append(_action(4, team=marker[i]))
        if i + 1 < len(timers):
            actions.append(_action(53, trigger=timers[i + 1]))
        if clock is not None:
            actions.append(_set_local(clock, 300 if i + 1 < len(timers) else -1))
        writer.actions(relays[-1], actions or [writer.message(name + ' deliveries complete')])


def build_map(game_root, run, rules=None, *, power_runtime=None):
    root = Path(game_root)
    plan = run['plan']
    # Private types must inherit Enhance.ini too, or flattened Classic fields
    # override the Enhanced rules selected by spawn.ini's Firestorm setting.
    rules = rules or installed_effective_sections(enhanced=True)
    info = inspect_map(root, plan['map'])
    if info['sha256'] != plan['map']['source_sha256']:
        raise ValueError('Fortress source map changed; reviewed layout needs updating.')
    validate_layout(root, plan['map'], rules)
    lines = source_lines(root, plan['map'])
    writer = MapWriter(lines, rules, root)
    finished = writer.flag('Run finished')
    for i in range(8):
        writer.put('Houses', 50 + i, f'Spawn{i+1}')
    markers = {}
    for event, name in marker_names(run['id'], plan).items():
        team, force, script = writer.key(), writer.key(), writer.key()
        append_hook_team(lines, team, force, script, name, 'Neutral')
        markers[event] = team
    friends = coalition(plan)
    faction = plan['player_country']
    from .challenges import house_modifiers

    # Existing registered HouseTypes avoid multiplayer preload files entirely.
    for i, (country, alias) in enumerate(zip([faction, *plan['enemy_countries']], ALIASES)):
        row = deepcopy(rules[country])
        row.update(ActsLike=str(NATIVE_INDICES[i]), Multiplay='yes', MultiplayPassive='no')
        if i:
            row.update(house_modifiers(plan['challenges']))
            bonus = plan['difficulty_profile']['enemy_firepower_percent']
            row['Firepower'] = str(float(row.get('Firepower', '1')) * (1 + bonus / 100))
        writer.sections[alias] = row
    for alias in FRIENDLY_ALIASES[1:]:
        writer.sections[alias] = dict(writer.sections[ALIASES[0]])
    for side, members in rules['Sides'].items():
        kept = [v for v in comma_items(members) if v not in (*ALIASES, *FRIENDLY_ALIASES)]
        kept.extend(
            alias
            for country, alias in zip([faction, *plan['enemy_countries']], ALIASES)
            if rules[country]['Side'] == side
        )
        if rules[faction]['Side'] == side:
            kept.extend(FRIENDLY_ALIASES[1:])
        writer.put('Sides', side, ','.join(kept))
    for kind, row in rules.items():
        for field in ('Owner', 'RequiredHouses', 'ForbiddenHouses'):
            if field not in row:
                continue
            members = [
                v for v in comma_items(row[field])
                if v not in (*ALIASES, *FRIENDLY_ALIASES)
            ]
            for country, alias in zip([faction, *plan['enemy_countries']], ALIASES):
                if country in comma_items(row[field]):
                    members.append(alias)
            if ','.join(members) != row[field]:
                writer.put(kind, field, ','.join(members))
    player_aliases = _player_rules(writer, plan)
    enemy_aliases = _enemy_rules(writer, plan)
    from .powers import apply_player_powers

    apply_player_powers(writer, plan, player_aliases, power_runtime if power_runtime is not None else {})
    tracked = {}
    clocks = _countdowns(writer, plan, finished)
    startup = [
        _action(4, team=markers['started']),
        writer.message('Defend the headquarters for 60 minutes.'),
    ]
    occupied_points = section_value_map(lines, 'Waypoints')

    def start(wp):
        cell = int(occupied_points[str(wp)])
        return {'x': cell % 1000, 'y': cell // 1000}

    objective_definition = plan['map']['protected_building']
    objective = deepcopy(rules[objective_definition['type']])
    objective.update(
        Image=objective.get('Image', objective_definition['type']),
        Name='Final Fortress headquarters',
        Unsellable='yes',
        Capturable='no',
        ImmuneToEMP='yes',
        LegalTarget='yes',
        Insignificant='no',
        RadarInvisible='no',
        Power='0',
        TechLevel='-1',
        BuildLimit='0',
        Armory='no',
        Ammo='0',
        Strength=str(
            round(float(objective_definition.get('base_strength', objective['Strength']))
                  * (1 + plan['effects']['lab_health_percent'] / 100))
        ),
    )
    writer.sections['DFFOBJECTIVE'] = objective
    writer.register('BuildingTypes', 'DFFOBJECTIVE')
    loss, loss_tag = writer.trigger('Fortress objective destroyed', [(48, 0, 0)], [], persistence=2)
    writer.actions(
        loss,
        [
            _action(56, finished),
            _action(54, trigger=loss),
            _action(4, team=markers['defeat']),
            *[_action(110, 50 + wp) for _, _, wp in friends],
        ],
    )
    objective_tag = writer.transfer_tag(
        plan['map']['player_waypoint'], 'Objective ownership', linked=loss
    )
    writer.place(
        'Structures',
        'DFFOBJECTIVE',
        plan['map']['protected_building']['position'],
        tag=objective_tag,
    )
    terminal = [
        _action(56, finished),
        _action(4, team=markers['victory']),
        *[_action(110, 50 + wp) for wp in plan['map']['enemy_waypoints']],
    ]
    writer.trigger('Survival victory', [(13, 0, 3600), (37, 0, finished)], terminal)
    for milestone in plan['milestones']:
        writer.trigger(
            'Survival ' + milestone['id'],
            [(13, 0, milestone['seconds']), (37, 0, finished)],
            [_action(4, team=markers['milestone:' + milestone['id']])],
        )
    generators = {'GDI': 'NUK2', 'Nod': 'NUK2', 'Allies': 'RAAPWR', 'Soviet': 'RAAPWR'}
    mcv = {'GDI': 'GMCV', 'Nod': 'NMCV', 'Allies': 'AMCV', 'Soviet': 'SMCV'}
    enemy_defenses = {
        'GDI': ['TWR', 'TWR', 'ATWR', 'ATWR'],
        'Nod': ['GUN', 'GUN', 'SAM', 'OBLI'],
        'Allies': ['RAPBOX', 'RAHBOX', 'RAAGUN', 'RAGUN'],
        'Soviet': ['RAFTUR', 'RAFTUR', 'RASAM', 'RATSLA'],
    }
    for seat, (_, _, wp) in enumerate(friends):
        layout = plan['map']['perk_layouts'][str(wp)]
        helper = seat >= (len(plan.get('coop_players', [])) or 1)
        tag = writer.transfer_tag(wp, 'Friendly grants ' + str(seat))
        writer.place(
            'Units', player_aliases.get(mcv[faction], mcv[faction]), start(wp),
            tag='None' if helper else tag,
            mission='Unload' if helper else 'Guard',
            owner=f'Spawn{wp+1}' if helper else 'Neutral',
        )
        effects = plan['effects']
        grants = [
            *effects['starting_buildings'],
            *effects['starting_power_buildings'],
            *effects['defense_types'],
        ]
        available = list(layout['slots'])
        production_count = len(effects['starting_buildings']) + len(effects['starting_power_buildings'])
        grant_positions = [available.pop(0) for _ in range(production_count)]
        grant_positions.extend(_defense_slots(available, start(wp), len(effects['defense_types'])))
        used = []
        for kind, position in zip(grants, grant_positions):
            alias = player_aliases.get(kind, kind)
            used.append(kind)
            # A preplaced refinery is supplied exactly one explicit native harvester.
            if kind in ('TDPROC', 'RAPROC'):
                placed = writer.key()
                writer.sections[placed] = dict(
                    writer.sections[alias],
                    FreeUnit='none',
                    TechLevel='-1',
                    BuildLimit='0',
                    AIBuildThis='no',
                )
                writer.register('BuildingTypes', placed)
                # Direct refinery prerequisites must accept either the ordinary
                # buildable copy or any friendly house's placement-only copy.
                group = 'DFFREFINERY_' + kind
                values = writer.sections.get('PrerequisiteGroups', {}).get(group, alias)
                writer.put('PrerequisiteGroups', group, values + ',' + placed)
                for target, row in list(writer.sections.items()):
                    prerequisites = comma_items(row.get('Prerequisite'))
                    if alias in prerequisites:
                        writer.put(
                            target, 'Prerequisite',
                            ','.join(group if v == alias else v for v in prerequisites),
                        )
                for target, row in list(writer.sections.items()):
                    docks = list(comma_items(row.get('Dock')))
                    if alias in docks:
                        writer.put(target, 'Dock', ','.join([*docks, placed]))
                items = list(
                    comma_items(
                        writer.sections.get('AI', {}).get(
                            'BuildRefinery', rules['AI'].get('BuildRefinery')
                        )
                    )
                )
                writer.put('AI', 'BuildRefinery', ','.join([*items, placed]))
                values = writer.sections.get('PrerequisiteGroups', {}).get(
                    'REFINERY', rules.get('PrerequisiteGroups', {}).get('REFINERY', '')
                )
                writer.put('PrerequisiteGroups', 'REFINERY', values + ',' + placed)
                alias = placed
            writer.place('Structures', alias, position, tag=tag)
        controller = _private_type(
            writer,
            'INGALITE',
            suffix='CTRL',
            owners=[ALIASES[0]],
            stats={
                'Name': 'Fortress survival controller',
                'Immune': 'yes',
                'LegalTarget': 'no',
                'AILegalTarget': 'no',
                'Insignificant': 'no',
                'Selectable': 'no',
                'Capturable': 'no',
                'Unsellable': 'yes',
                'TechLevel': '-1',
                'BuildLimit': '0',
                'LightVisibility': '0',
                'LightIntensity': '0',
                'Power': '0',
            },
        )
        writer.place('Structures', controller, layout['controller'], tag=tag)
        army = [*effects['starting_units'], *effects['starting_harvesters']]
        positions = iter(layout['army'])
        helper_units = (
            _tracked_units(writer, effects['starting_units'], wp, player_aliases, tracked)
            if helper
            else []
        )
        helper_types = {
            u['type']: v['type'] for u, v in zip(effects['starting_units'], helper_units)
        }
        for unit in army:
            for _ in range(unit['count']):
                kind = unit['type']
                position = next(positions)
                writer.place(
                    'Infantry' if _category(rules, kind) == 'InfantryTypes' else 'Units',
                    helper_types.get(kind, player_aliases.get(kind, kind)),
                    position,
                    tag=tag,
                    veterancy=0 if kind in ('TDHARV', 'RAHARV') else effects['veterancy'],
                    mission='Harvest' if kind in ('TDHARV', 'RAHARV') else 'Guard',
                )
        if helper and effects['starting_units']:
            # Native recruitment explicitly commands helper starting armies.
            from .wave_pool import batches

            for units in batches(helper_units, 15):
                team = writer.team('Fortress helper starting attack', units, wp, wp)
                startup.append(_action(4, team=team))
        if effects['starting_credits']:
            startup.append(_action(106, 50 + wp, extra=effects['starting_credits']))
        rank = (
            plan['fundraising_ranks'][seat]
            if seat < len(plan['fundraising_ranks'])
            else effects['fundraising_stacks']
        )
        if rank:
            writer.trigger(
                'Fundraising ' + str(seat),
                [(13, 0, 300), (37, 0, finished)],
                [_action(106, 50 + wp, extra=1000 * rank)],
                persistence=2,
            )
        # Objective + MCV + all placed grants and armies are one-time captures.
        plan_count = 2 + len(grants) + sum(u['count'] for u in army) + (seat == 0) - helper
        writer.put('DFFSetupTransfers', ACTORS[seat], plan_count)
        if effects['reveal_map']:
            startup.append(_action(16))
        arrival = layout['arrival']
        writer.put('Waypoints', 10 + seat, arrival['y'] * 1000 + arrival['x'])
    starting_yards = {}
    enemy_conditions = []
    for enemy, (country, wp) in enumerate(
        zip(plan['enemy_countries'], plan['map']['enemy_waypoints'])
    ):
        layout = plan['map']['perk_layouts'][str(wp)]
        tag = writer.transfer_tag(wp, 'Enemy fortress ' + str(enemy))
        yard = rules[mcv[country]]['DeploysInto']
        private = _private_type(
            writer,
            yard,
            suffix='YARD',
            owners=[ALIASES[enemy + 1]],
            stats={
                'Immune': 'yes',
                'LegalTarget': 'no',
                'AILegalTarget': 'no',
                'Capturable': 'no',
                'Unsellable': 'yes',
                'UndeploysInto': 'none',
                'TechLevel': '-1',
                'BuildLimit': '0',
            },
        )
        # Native MCV deployment calls Begin_Construction and seeds Base.Nodes;
        # transferring a preplaced yard does neither. Only this initial MCV
        # deploys into the protected type. Future ordinary MCVs stay vulnerable.
        starting_mcv = writer.key()
        source_mcv = enemy_aliases[enemy][mcv[country]]
        writer.sections[starting_mcv] = {
            **writer.sections[source_mcv],
            'DeploysInto': private,
            'Immune': 'yes',
            'LegalTarget': 'no',
            'AILegalTarget': 'no',
            'TechLevel': '-1',
            'BuildLimit': '0',
        }
        writer.register('VehicleTypes', starting_mcv)
        base_units = comma_items(writer.sections.get('General', {}).get(
            'BaseUnit', rules['General']['BaseUnit']
        ))
        writer.put('General', 'BaseUnit', ','.join([*base_units, starting_mcv]))
        writer.place('Units', starting_mcv, start(wp), owner=f'Spawn{wp+1}', mission='Unload')
        enemy_conditions.append({**enemy_aliases[enemy], yard: private})
        writer.put(
            'AI',
            'BuildConst',
            ','.join(
                [
                    *[
                        kind for kind in comma_items(writer.sections.get('AI', {}).get(
                            'BuildConst', rules.get('AI', {}).get('BuildConst')
                        )) if kind != enemy_aliases[enemy].get(yard)
                    ],
                    private,
                ]
            ),
        )
        starting_yards.setdefault(yard, []).append(private)
        if yard in enemy_aliases[enemy]:
            starting_yards[yard].append(enemy_aliases[enemy][yard])
        gen = generators[country]
        defenses = enemy_defenses[country]
        demand = sum(max(0, -int(rules[k].get('Power', '0'))) for k in defenses)
        generators_needed = (demand + 100 + int(rules[gen]['Power']) - 1) // int(
            rules[gen]['Power']
        )
        available = list(layout['slots'])
        positions = [available.pop(0) for _ in range(generators_needed)]
        positions.extend(_defense_slots(available, start(wp), len(defenses)))
        for kind, position in zip([*([gen] * generators_needed), *defenses], positions):
            alias = (
                _private_type(
                    writer,
                    kind,
                    suffix='FORT',
                    owners=[ALIASES[enemy + 1]],
                    stats={
                        'Immune': 'yes',
                        'LegalTarget': 'no',
                        'AILegalTarget': 'no',
                        'Capturable': 'no',
                        'Unsellable': 'yes',
                        'TechLevel': '-1',
                        'BuildLimit': '0',
                    },
                )
                if kind in defenses
                else kind
            )
            writer.place('Structures', alias, position, tag=tag)
        arrival = layout['arrival']
        writer.put('Waypoints', 16 + enemy, arrival['y'] * 1000 + arrival['x'])
    # Preplaced/transferred yards bypass normal multiplayer MCV initialization.
    # Enable each computer explicitly after ownership and helper deployments.
    computers = [
        (ALIASES[i + 1], wp) for i, wp in enumerate(plan['map']['enemy_waypoints'])
    ]
    computers.extend(
        (FRIENDLY_ALIASES[seat], wp)
        for seat, (_, _, wp) in enumerate(friends)
        if seat >= (len(plan.get('coop_players', [])) or 1)
    )
    for owner, wp in computers:
        writer.trigger(
            'Start native computer ' + owner, [(13, 0, 3)],
            [_action(3, 50 + wp), _action(13, 50 + wp), _action(30, 1), _action(74, 50 + wp)],
            owner=owner,
        )
    for yard, yards in starting_yards.items():
        group = 'DFFYARD_' + yard
        writer.put('PrerequisiteGroups', group, ','.join(dict.fromkeys([yard, *yards])))
        for kind, row in [*rules.items(), *list(writer.sections.items())]:
            prereq = comma_items(row.get('Prerequisite'))
            if yard in prereq:
                writer.put(
                    kind, 'Prerequisite', ','.join(group if v == yard else v for v in prereq)
                )
    for enemy, country in enumerate(plan['enemy_countries']):
        _route_native_ai(
            writer, country, ALIASES[enemy + 1], NATIVE_INDICES[enemy + 1],
            enemy_conditions[enemy], opponent_aliases=[player_aliases],
        )
    for seat in range(len(plan.get('coop_players', [])) or 1, len(friends)):
        _route_native_ai(
            writer, faction, FRIENDLY_ALIASES[seat], NATIVE_INDICES[0],
            player_aliases, opponent_aliases=enemy_conditions,
        )
    for offset in range(0, len(startup), 8):
        writer.trigger('Final Fortress start', [(13, 0, 1)], startup[offset : offset + 8])
    # Shared small enemy and friendly reservations. Ordinary AI units are excluded.
    enemy_pools = [
        {'owner': wp, 'capacity': 20, 'busy': writer.flag('Enemy reservation')}
        for wp in plan['map']['enemy_waypoints']
        for _ in range(8)
    ]
    late = writer.flag('Late enemy deliveries')
    writer.trigger('Late enemy deliveries', [(13, 0, 1800)], [_action(56, late)])
    deliveries = []
    for wave in plan['wave_schedule']:
        groups = []
        for g in wave['groups']:
            enemy = plan['map']['enemy_waypoints'].index(g['waypoint'])
            air = set(g.get('air_types', []))
            for flying in (False, True):
                native_units = [u for u in g['units'] if (u['type'] in air) == flying]
                if not native_units:
                    continue
                units = _tracked_units(
                    writer, native_units, g['waypoint'], enemy_aliases[enemy], tracked
                )
                groups.append(
                    (g['waypoint'], 16 + enemy, units, True, g.get('veteran_level', 1) - 1)
                )
        deliveries.append(groups)

    def upgrade(index, owner, units):
        from .wave_priority import late_delivery

        enemy = plan['map']['enemy_waypoints'].index(owner)
        reverse = {value: key for key, value in enemy_aliases[enemy].items()}
        native_by_type = {
            value: reverse.get(source, source)
            for (wp, source), value in tracked.items()
            if wp == owner
        }
        native = [{'type': native_by_type[u['type']], 'count': u['count']} for u in units]
        wave = plan['wave_schedule'][index]
        group = next(g for g in wave['groups'] if g['waypoint'] == owner)
        upgraded = late_delivery(plan, wave, group, native)
        if len(upgraded) > 6:
            from .wave_priority import resize

            upgraded = resize(
                upgraded[:6],
                sum(u['count'] for u in units),
                seed=plan['seed'],
                house=group['house'],
                seconds=1800,
                policy=plan['wave_priorities'],
            )
        return _tracked_units(writer, upgraded, owner, enemy_aliases[enemy], tracked)

    _delivery_chain(
        writer,
        plan,
        deliveries,
        enemy_pools,
        finished,
        name='Enemy wave',
        marker=[markers[f'wave:{i+1}'] for i in range(len(deliveries))],
        clock=clocks['enemy'],
        upgrader=upgrade,
        late_flag=late,
    )
    if plan['effects']['reinforcements']:
        pools = [
            {'owner': None, 'capacity': 15, 'busy': writer.flag('Allied reservation')}
            for _ in range(10)
        ]
        for seat, (_, _, wp) in enumerate(friends):
            effect = plan['effects']['reinforcements']
            units = _tracked_units(writer, effect['units'], wp, player_aliases, tracked)
            groups = [
                [
                    (
                        wp,
                        10 + seat,
                        units,
                        seat >= len(plan.get('coop_players', [])) and seat > 0,
                        effect.get('veterancy', 0),
                    )
                ]
                for _ in range(11)
            ]
            _delivery_chain(
                writer,
                plan,
                groups,
                pools,
                finished,
                name='Allied reinforcements ' + str(seat),
                clock=clocks[ACTORS[seat]],
            )
    if plan['effects']['lab_reserve_units']:
        actions = []
        for seat, (_, _, wp) in enumerate(friends):
            for unit in plan['effects']['lab_reserve_units']:
                units = [
                    {'type': player_aliases.get(unit['type'], unit['type']), 'count': unit['count']}
                ]
                team = writer.team(
                    'Objective reserves',
                    units,
                    wp,
                    10 + seat,
                    attack=seat >= len(plan.get('coop_players', [])) and seat > 0,
                    veterancy=plan['effects']['lab_reserve_veterancy'],
                )
                actions.append(writer.reinforce(team))
        used = writer.flag('Objective reserve used')
        relays = []
        for offset in range(0, len(actions), 8):
            relay, _ = writer.trigger(
                'Objective reserve delivery',
                [(36, 0, used), (37, 0, finished)],
                actions[offset : offset + 8],
            )
            relays.append(relay)
        previous = loss
        for event in (42, 43):
            actions = [_action(56, used)]
            if plan['effects'].get('lab_reserve_shield'):
                # Forced native Iron Curtain targets only this trigger's
                # attached objective and uses DTA's unchanged duration. The
                # neutral trigger owner keeps human power charges untouched.
                actions.insert(0, _action(136, 1))
            trigger, tag = writer.trigger(
                'Objective reserve health',
                [(event, 0, 0), (37, 0, used), (37, 0, finished)],
                actions,
                persistence=2,
                linked=previous,
            )
            previous = trigger
        ownership = next(
            k for k, v in writer.sections['Triggers'].items() if ',Objective ownership,' in v
        )
        fields = writer.sections['Triggers'][ownership].split(',')
        fields[1] = previous
        writer.put('Triggers', ownership, ','.join(fields))
    _camp_crates(writer, plan, markers, finished, player_aliases, enemy_aliases)
    from .ground import pave_spawn_areas

    cells = {
        (layout['arrival']['x'] + dx, layout['arrival']['y'] + dy)
        for layout in plan['map']['perk_layouts'].values()
        for dx in range(-2, 3)
        for dy in range(-1, 2)
    }
    pave_spawn_areas(lines, cells)
    writer.put('Basic', 'Name', 'Final Fortress - King of the Hills Extreme')
    writer.put('Basic', 'RequiredAddOn', '1')
    writer.put('Basic', 'MultiplayerOnly', 'yes')
    writer.put('Basic', 'IgnoreGlobalAITriggers', 'no')
    writer.put('Basic', 'SkipScore', 'no')
    writer.put('SpecialFlags', 'FixedAlliance', 'yes')
    writer.put('General', 'PersistTagsOnAIDeploy', 'yes')
    writer.put('General', 'CellTagsIgnoreStealth', 'no')
    # DTA native persistent overlay uses the same simulation variables as delivery timers.
    writer.put('Tutorial', 'DFFHELP', 'Until Victory: 60 minutes. Next enemy wave: 5 minutes.')
    from .maps import validate_generated_placements

    validate_generated_placements(writer, plan['map'], root)
    return writer.finish()


def spawn_data(plan, map_data, *, game_speed=2, slot=0, endpoints=None):
    friends = coalition(plan)
    humans = len(plan.get('coop_players', [])) or 1
    if type(game_speed) is not int or not 0 <= game_speed <= 6:
        raise ValueError('Invalid DTA game speed.')
    if endpoints is not None:
        from .coop import validate_endpoints

        validate_endpoints(plan, endpoints)
    elif humans != 1:
        raise ValueError('Co-op endpoints are required.')
    if not 0 <= slot < humans:
        raise ValueError('Invalid local Fortress seat.')
    players = plan.get('coop_players', ['Commander'])
    game_id = int(hashlib.sha256(plan['seed'].encode()).hexdigest()[:8], 16) % (2**31 - 1) + 1
    actors = [(wp, FRIENDLY_INDICES[i], i) for i, (_, _, wp) in enumerate(friends[:humans])]
    actors.extend(
        (wp, NATIVE_INDICES[i + 1], 3 + i) for i, wp in enumerate(plan['map']['enemy_waypoints'])
    )
    actors.extend(
        (wp, FRIENDLY_INDICES[i], i) for i, (_, _, wp) in enumerate(friends) if i >= humans
    )
    settings = {
        'Scenario': 'spawnmap.ini',
        'Name': players[slot],
        'Host': 'Yes' if slot == 0 else 'No',
        'IsSinglePlayer': 'No',
        'PlayerCount': str(humans),
        'AIPlayers': str(len(actors) - humans),
        'GameID': str(game_id),
        'Seed': str(game_id),
        'Side': str(NATIVE_INDICES[0]),
        'Color': str(slot),
        'GameSpeed': str(game_speed),
        'Protocol': '0',
        'FrameSendRate': '1',
        'FogOfWar': 'No',
        'TechLevel': '7',
        'ShortGame': 'No',
        'MCVRedeploy': 'Yes',
        'Crates': 'No',
        'MultiEngineer': 'Yes',
        'UnitCount': '0',
        'BuildOffAlly': 'Yes',
        'BridgeDestroy': 'No',
        'Credits': '10000',
        'Bases': 'No',
        'AIDifficulty': str(plan['engine_difficulty']),
        'Firestorm': 'Yes',
        'CoachMode': 'Yes',
        'WriteStatistics': 'Yes',
        'LoadSaveGame': 'No',
        'AutoSaveGame': '0',
        'MapHash': hashlib.sha1(map_data).hexdigest(),
        'UIMapName': plan['map']['display_name'],
    }
    sections = {
        'Settings': settings,
        'SpawnLocations': {},
        'HouseCountries': {},
        'HouseColors': {},
        'HouseHandicaps': {},
    }
    settings['Side'] = str(FRIENDLY_INDICES[slot])
    if endpoints:
        settings.update(Ip=endpoints[slot]['address'], Port=str(endpoints[slot]['port']))
        for j, peer in enumerate(i for i in range(humans) if i != slot):
            p = endpoints[peer]
            sections[f'Other{j+1}'] = {
                'Name': players[peer],
                'Side': str(FRIENDLY_INDICES[peer]),
                'Color': str(peer),
                'Ip': p['address'],
                'Port': str(p['port']),
            }
    for i, (wp, side, color) in enumerate(actors):
        multi = f'Multi{i+1}'
        sections['SpawnLocations'][multi] = str(wp)
        if i >= humans:
            sections['HouseCountries'][multi] = str(side)
            sections['HouseColors'][multi] = str(color)
            sections['HouseHandicaps'][multi] = str(
                plan['engine_difficulty'] if i < humans + 3 else 1
            )
    friend_indices = [*range(humans), *range(humans + 3, len(actors))]
    ordinals = ('One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven')
    for group in (friend_indices, list(range(humans, humans + 3))):
        for i in group:
            sections[f'Multi{i+1}_Alliances'] = {
                'HouseAlly' + word: str(j)
                for word, j in zip(ordinals, (j for j in group if j != i))
            }
    from .colors import remap_colors
    remap_colors(sections, plan)
    return (
        '\r\n'.join(
            line
            for section, values in sections.items()
            for line in [f'[{section}]', *[f'{k}={v}' for k, v in values.items()], '']
        )
        + '\r\n'
    ).encode('cp1252')


def prepare_game(game_root, run, rules=None, *, game_speed=2, coop_slot=None, endpoints=None):
    from randomizer.maps.assets import claim_runtime_asset_lease
    from randomizer.dta.powers import ensure_power_action_types, ensure_power_runtime_types

    claim_runtime_asset_lease()
    runtime = {}
    data = build_map(game_root, run, rules, power_runtime=runtime)
    spawn = spawn_data(
        run['plan'], data, game_speed=game_speed, slot=coop_slot or 0, endpoints=endpoints
    )
    ensure_power_action_types(Path(game_root) / 'INI/Action.ini')
    ensure_power_runtime_types(
        runtime.get('rules', {}), runtime.get('art', {}),
        rules_path=Path(game_root) / 'INI/Rules.ini',
        art_path=Path(game_root) / 'INI/Art.ini',
    )
    atomic_write_text(Path(game_root) / 'spawnmap.ini', data.decode('cp1252'), encoding='cp1252')
    atomic_write_text(Path(game_root) / 'spawn.ini', spawn.decode('cp1252'), encoding='cp1252')
    return hashlib.sha256(data).hexdigest()
