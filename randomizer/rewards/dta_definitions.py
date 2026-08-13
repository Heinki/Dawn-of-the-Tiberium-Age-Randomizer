"""Safe DTA reward catalogue exposed through the preserved generic UI."""

from collections import Counter

from randomizer.config.tuning import BUFF_EFFECTS, REWARD_PLANNING
from randomizer.dta.rules import ALWAYS_AVAILABLE_MOBILE_IDS, techno_catalogue


DEFAULT_REWARDS_PER_CHECK = int(REWARD_PLANNING['default_rewards_per_check'])
MAX_REWARDS_PER_CHECK = int(REWARD_PLANNING['maximum_rewards_per_check'])
FACTIONS = ('GDI', 'Nod', 'Allies', 'Soviet')
PLAYER_ARMY_ID = 'DTA_PLAYER_ARMY'

BUFF_TYPES = [
    {
        'id': 'production',
        'name': 'Drill',
        'setting_label': 'Production speed',
        'description': '{plural} are produced faster.',
    },
    {
        'id': 'cost',
        'name': 'Logistics',
        'setting_label': 'Cost',
        'description': '{plural} cost less.',
    },
    {
        'id': 'speed',
        'name': 'Mobility',
        'setting_label': 'Movement speed',
        'description': '{plural} move faster.',
    },
    {
        'id': 'armor',
        'name': 'Armor Plating',
        'setting_label': 'Armor',
        'description': '{plural} take less damage.',
    },
    {
        'id': 'damage',
        'name': 'Firepower',
        'setting_label': 'Damage',
        'description': '{plural} deal more damage.',
    },
    {
        'id': 'reload',
        'name': 'Weapon Tuning',
        'setting_label': 'Fire rate',
        'description': '{plural} fire faster.',
    },
]

_GLOBAL_BUFF_TARGET = {
    PLAYER_ARMY_ID: {
        'label': 'Player Army',
        'plural': 'Player units',
        'category': 'global',
        'factions': list(FACTIONS),
        'cost': 100,
        'speed': 10,
        'strength': 100,
        'sight': 5,
        'weapons': {'DTAHouseModifier': {'damage': 100, 'rof': 100}},
        'global_buff': True,
        'global_production': True,
        'allowed_buff_types': [item['id'] for item in BUFF_TYPES],
    },
}

_MOBILE_SOURCE_RECORDS = tuple(
    record for record in techno_catalogue()
    if record.get('rewardable')
    and record.get('category') in {'infantry', 'vehicles', 'aircraft'}
    and not record['id'].startswith('AI')
    and not record.get('duplicate_of')
)

_MOBILE_LABEL_COUNTS = Counter(
    record['label'].casefold() for record in _MOBILE_SOURCE_RECORDS
)


def _display_label(record):
    label = record['label']
    if _MOBILE_LABEL_COUNTS[label.casefold()] <= 1:
        return label
    editor_name = str(record.get('editor_name') or '').strip()
    if editor_name and not editor_name.casefold().startswith('obsolete'):
        return editor_name
    owners = ' / '.join(record.get('playable_owners', ()))
    same_label_owners = [
        other for other in _MOBILE_SOURCE_RECORDS
        if other['label'].casefold() == label.casefold()
        and other.get('playable_owners') == record.get('playable_owners')
    ]
    suffix = record['id'] if len(same_label_owners) > 1 else owners
    return f'{label} ({suffix})' if suffix else f'{label} ({record["id"]})'


_MOBILE_RECORDS = tuple(
    {**record, 'label': _display_label(record)}
    for record in _MOBILE_SOURCE_RECORDS
)

_MOBILE_ACCESS_RECORDS = tuple(
    record for record in _MOBILE_RECORDS
    if record['id'] not in ALWAYS_AVAILABLE_MOBILE_IDS
)

def _allowed_buff_types(record):
    allowed = ['production']
    if record.get('cost', 0) > 0:
        allowed.append('cost')
    if record.get('speed', 0) > 0:
        allowed.append('speed')
    if record.get('strength', 0) > 0:
        allowed.append('armor')
    if record.get('primary_weapon') or record.get('secondary_weapon'):
        allowed.extend(('damage', 'reload'))
    return allowed


BUFF_TARGETS = dict(_GLOBAL_BUFF_TARGET)
for _record in _MOBILE_RECORDS:
    BUFF_TARGETS[_record['id']] = {
        'label': _record['label'],
        'plural': _record['label'],
        'category': _record['category'],
        'factions': list(_record['playable_owners']),
        'cost': _record['cost'],
        'speed': _record['speed'],
        'strength': _record['strength'],
        'sight': 0,
        'weapons': {
            key: {}
            for key in (
                _record.get('primary_weapon'),
                _record.get('secondary_weapon'),
            )
            if key
        },
        'allowed_buff_types': _allowed_buff_types(_record),
        'dta_production_clone': True,
        'naval': bool(_record.get('naval')),
        'special_reward': bool(_record.get('special')),
    }

_GLOBAL_BUFF_REWARDS = [
    {
        'name': f'Player Army {buff_type["name"]} I',
        'description': (
            'Applies a DTA/Vinifera human-house modifier to units and '
            'buildings where the engine supports that modifier. Enemy units '
            'and map object identities stay unchanged.'
        ),
        'rules': {},
        'factions': list(FACTIONS),
        'kind': 'buff',
        'unit': PLAYER_ARMY_ID,
        'buff_type': buff_type['id'],
        'global_buff': True,
        'dta_house_modifier': True,
        'special_reward': False,
    }
    for buff_type in BUFF_TYPES
]

_BUFF_TYPE_BY_ID = {item['id']: item for item in BUFF_TYPES}
_UNIT_SPECIFIC_BUFF_REWARDS = [
    {
        'name': (
            f'{target["label"]} ({unit_id}) '
            f'{_BUFF_TYPE_BY_ID[buff_type]["name"]} I'
        ),
        'description': (
            'Buffs this unit for the human player. Authored map units keep '
            'their original identity; collisions use a Vinifera production clone.'
        ),
        'rules': {},
        'factions': list(target.get('factions', ())),
        'kind': 'buff',
        'unit': unit_id,
        'buff_type': buff_type,
        'global_buff': False,
        'dta_production_clone': True,
        'special_reward': False,
    }
    for unit_id, target in BUFF_TARGETS.items()
    if unit_id != PLAYER_ARMY_ID
    for buff_type in target.get('allowed_buff_types', ())
]
UNIT_BUFF_REWARDS = _GLOBAL_BUFF_REWARDS + _UNIT_SPECIFIC_BUFF_REWARDS

UNIT_UNLOCK_REWARDS = [
    {
        'name': f'Unlock {record["label"]} ({record["id"]})',
        'description': (
            'Unlocks this unit for human production through Vinifera ActsLike '
            'house restrictions. Authored mission identities remain unchanged.'
        ),
        'rules': {
            record['id']: {'TechLevel': str(max(1, record['tech_level']))}
        },
        'factions': list(record['playable_owners']),
        'kind': 'unit_access',
        'unit': record['id'],
        'dta_production_access': True,
        'access_category': 'unit',
        'special_reward': False,
    }
    for record in _MOBILE_ACCESS_RECORDS
]
EXTRA_UNIT_UNLOCK_REWARDS = []
ROSTER_UNIT_UNLOCK_REWARDS = []
DEFENSE_UNLOCK_REWARDS = []
SPECIAL_BUILDING_UNLOCK_REWARDS = []
SUPERWEAPON_UNLOCK_REWARDS = []
SECONDARY_SUPERWEAPON_UNLOCK_REWARDS = []
AID_POWER_UNLOCK_REWARDS = []
POWER_BUFF_REWARDS = []
ENEMY_REWARD_POOL = []
REWARD_POOL = list(UNIT_UNLOCK_REWARDS + UNIT_BUFF_REWARDS)
REWARD_BY_NAME = {reward['name']: reward for reward in REWARD_POOL}
REWARD_BY_BUFF_KEY = {
    (reward['unit'], reward['buff_type']): reward
    for reward in UNIT_BUFF_REWARDS
}

RETIRED_REWARD_BY_NAME = {}
REWARD_ALIASES = {}
ACCESS_REWARD_ALIASES = {}
AID_POWER_MAP_CONFIGS = []
AID_POWER_MAP_CONFIG_BY_SUPERWEAPON = {}
SPECIAL_BUILDING_DEFINITIONS = ()
UNIT_SIDEBAR_IMAGES = {}
STANDALONE_WEAPON_TEMPLATES = {}
UNIT_LABELS = {
    PLAYER_ARMY_ID: 'Player Army',
    **{record['id']: record['label'] for record in _MOBILE_RECORDS},
}
FACTION_UNIT_ROSTERS = {
    faction: {
        'infantry': {
            record['id']: record['label'] for record in _MOBILE_RECORDS
            if record['category'] == 'infantry'
            and faction in record['playable_owners']
        },
        'units': {
            record['id']: record['label'] for record in _MOBILE_RECORDS
            if record['category'] == 'vehicles'
            and faction in record['playable_owners']
        },
        'aircraft': {
            record['id']: record['label'] for record in _MOBILE_RECORDS
            if record['category'] == 'aircraft'
            and faction in record['playable_owners']
        },
    }
    for faction in FACTIONS
}
FACTION_DEFENSE_ROSTERS = {faction: {} for faction in FACTIONS}
NAVAL_UNIT_IDS = {
    record['id'] for record in _MOBILE_RECORDS if record.get('naval')
}
ALWAYS_AVAILABLE_UNIT_IDS = set()
ALWAYS_AVAILABLE_BUILDING_IDS = set()
ALWAYS_AVAILABLE_TECH_IDS = set(ALWAYS_AVAILABLE_MOBILE_IDS)
ENGINEER_UNIT_IDS = frozenset()
AMPHIBIOUS_TRANSPORT_UNIT_IDS = frozenset()
LIMITED_HERO_UNIT_IDS = frozenset()
NONTRAINABLE_UNIT_IDS = frozenset()
MANDATORY_EXCLUDED_BUFF_TYPE_IDS = {}
SPECIAL_REWARD_UNIT_IDS = frozenset()
CLONE_REQUIRED_BUFF_TYPES = frozenset(
    {'production', 'cost', 'speed', 'armor', 'damage', 'reload'}
)
HOUSE_SCOPED_BUFF_TYPES = frozenset()
WEAPON_STAT_BUFF_TYPES = frozenset({'damage', 'reload'})
_UNIT_POLICY_CONFIG = {'ammo_display_labels': {}}


def unit_display_label(unit_id):
    return UNIT_LABELS.get(str(unit_id or '').upper(), str(unit_id or ''))


def unit_role_equivalents(unit_id):
    unit_id = str(unit_id or '').upper()
    return frozenset((unit_id,)) if unit_id else frozenset()


def linked_buff_variant_ids(unit_id):
    return unit_role_equivalents(unit_id)


def movement_speed_ceiling(_target):
    return None


def capped_movement_speed(target, count):
    base = max(1, int(round(float(target.get('speed', 1)))))
    return max(base, int(round(
        base * float(BUFF_EFFECTS['speed']['factor_per_stack']) ** max(0, int(count))
    )))
