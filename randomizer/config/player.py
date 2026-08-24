"""Read and persist launcher/player options in a small YAML subset."""

from randomizer.core.paths import CONFIG_DIR, LEGACY_CONFIG_DIR
from randomizer.core.storage import atomic_write_text
from randomizer.config.static import static_config_section


CONFIG_PATH = CONFIG_DIR / 'dta_randomizer.yaml'
LEGACY_CONFIG_PATH = LEGACY_CONFIG_DIR / CONFIG_PATH.name

DEFAULT_CONFIG = static_config_section(
    'default_player_config.json', 'defaults', dict
)
UNIT_BUFF_CATALOGUE_VERSION = 4
UNIT_BUFF_TYPES_INTRODUCED = {
    1: ('passenger_capacity', 'open_topped'),
    2: ('health', 'range', 'sight', 'ammo', 'passenger_capacity', 'cloak', 'sensors'),
    3: ('self_healing',),
    4: ('build_limit',),
}
POWER_BUFF_CATALOGUE_VERSION = 4
POWER_BUFF_TYPES_INTRODUCED = {
    1: ('vision',),
    2: ('recharge',),
    3: ('damage', 'area'),
    4: ('payload',),
}
ENEMY_STACK_MODEL_VERSION = 2
INFANTRY_ACCESS_CATALOGUE_VERSION = 1
DTA_POWER_CATALOGUE_VERSION = 4


def deep_copy(value):
    if isinstance(value, dict):
        return {key: deep_copy(item) for key, item in value.items()}
    if isinstance(value, list):
        return [deep_copy(item) for item in value]
    return value


def deep_merge(defaults, loaded):
    merged = deep_copy(defaults)
    for key, value in (loaded or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def migrate_loaded_config(loaded):
    """Migrate persisted options without restoring old user toggles."""
    if not isinstance(loaded, dict):
        return False
    changed = False
    if 'eva_voice' in loaded:
        loaded.pop('eva_voice', None)
        changed = True
    archipelago = loaded.get('archipelago')
    if isinstance(archipelago, dict):
        server = str(archipelago.get('server') or '').strip()
        if server.casefold() in {
            '',
            'archipelaog.gg',
            'ws://archipelaog.gg',
            'wss://archipelaog.gg',
            'ws://archipelago.gg',
            'wss://archipelago.gg',
        }:
            archipelago['server'] = 'archipelago.gg'
            changed = True
    generation = loaded.get('generation')
    if loaded.get('rewards_on_victory_only') is not True:
        loaded['rewards_on_victory_only'] = True
        changed = True
    if not isinstance(generation, dict):
        return changed
    if generation.get('reward_mode') == 'Chaos (Experimental)':
        generation['reward_mode'] = 'Chaos'
        changed = True
    try:
        access_version = max(
            0, int(generation.get('infantry_access_catalogue_version', 0))
        )
    except (TypeError, ValueError):
        access_version = 0
    if access_version < INFANTRY_ACCESS_CATALOGUE_VERSION:
        generation['randomize_unit_access'] = True
        enabled_reward_types = generation.get('enabled_reward_types')
        if isinstance(enabled_reward_types, list):
            if 'access' not in enabled_reward_types:
                enabled_reward_types.insert(0, 'access')
        else:
            generation['enabled_reward_types'] = ['access', 'buff']
        generation['infantry_access_catalogue_version'] = (
            INFANTRY_ACCESS_CATALOGUE_VERSION
        )
        changed = True
    try:
        dta_power_version = max(
            0, int(generation.get('dta_power_catalogue_version', 0))
        )
    except (TypeError, ValueError):
        dta_power_version = 0
    if dta_power_version < DTA_POWER_CATALOGUE_VERSION:
        generation['include_superweapon_rewards'] = True
        generation['include_aid_power_rewards'] = True
        generation['include_secondary_superweapon_rewards'] = False
        generation['include_power_buff_rewards'] = True
        generation['include_defensive_buildings'] = True
        enabled_reward_types = generation.get('enabled_reward_types')
        if isinstance(enabled_reward_types, list):
            while 'secondary_superweapon' in enabled_reward_types:
                enabled_reward_types.remove('secondary_superweapon')
            for reward_type in ('superweapon', 'aid_power', 'power_buff'):
                if reward_type not in enabled_reward_types:
                    enabled_reward_types.append(reward_type)
        generation['dta_power_catalogue_version'] = DTA_POWER_CATALOGUE_VERSION
        changed = True
    try:
        version = max(0, int(generation.get('unit_buff_catalogue_version', 0)))
    except (TypeError, ValueError):
        version = 0
    enabled = generation.get('enabled_buff_types')
    if isinstance(enabled, list):
        for introduced_version in range(
            version + 1,
            UNIT_BUFF_CATALOGUE_VERSION + 1,
        ):
            for buff_type in UNIT_BUFF_TYPES_INTRODUCED.get(
                introduced_version, ()
            ):
                if buff_type not in enabled:
                    enabled.append(buff_type)
                    changed = True
    if version < UNIT_BUFF_CATALOGUE_VERSION:
        generation['unit_buff_catalogue_version'] = (
            UNIT_BUFF_CATALOGUE_VERSION
        )
        changed = True
    try:
        power_version = max(
            0, int(generation.get('power_buff_catalogue_version', 0))
        )
    except (TypeError, ValueError):
        power_version = 0
    enabled_power = generation.get('enabled_power_buff_types')
    if isinstance(enabled_power, list):
        for introduced_version in range(
            power_version + 1,
            POWER_BUFF_CATALOGUE_VERSION + 1,
        ):
            for buff_type in POWER_BUFF_TYPES_INTRODUCED.get(
                introduced_version, ()
            ):
                if buff_type not in enabled_power:
                    enabled_power.append(buff_type)
                    changed = True
    if power_version < POWER_BUFF_CATALOGUE_VERSION:
        generation['power_buff_catalogue_version'] = (
            POWER_BUFF_CATALOGUE_VERSION
        )
        changed = True
    enemy_scaling = generation.get('enemy_scaling')
    if isinstance(enemy_scaling, dict):
        try:
            enemy_version = max(
                0, int(enemy_scaling.get('stack_model_version', 1))
            )
        except (TypeError, ValueError):
            enemy_version = 1
        if enemy_version < ENEMY_STACK_MODEL_VERSION:
            caps = enemy_scaling.get('caps')
            if isinstance(caps, dict):
                for effect_id, cap in tuple(caps.items()):
                    if cap == 3:
                        caps[effect_id] = 5
                        changed = True
            enemy_scaling['stack_model_version'] = (
                ENEMY_STACK_MODEL_VERSION
            )
            changed = True
    return changed


def parse_scalar(value):
    value = value.strip()
    if not value:
        return ''
    if value in ("''", '""'):
        return ''
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1].replace('\\"', '"')
    if value.startswith('[') and value.endswith(']'):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_scalar(part.strip()) for part in inner.split(',')]
    if value == '{}':
        return {}
    lowered = value.lower()
    if lowered == 'true':
        return True
    if lowered == 'false':
        return False
    try:
        return int(value)
    except ValueError:
        return value


def quote_yaml_string(value):
    if value == '':
        return "''"
    needs_quote = (
        value.strip() != value
        or value.lower() in {'true', 'false', 'null'}
        or value.startswith(('-', '[', '{', '#', '!', '&', '*'))
        or any(char in value for char in [':', '#', "'", '"'])
    )
    if not needs_quote:
        try:
            int(value)
        except ValueError:
            return value
    return "'" + value.replace("'", "''") + "'"


def scalar_to_yaml(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return '[' + ', '.join(scalar_to_yaml(item) for item in value) + ']'
    return quote_yaml_string(str(value))


def parse_simple_yaml_text(text):
    """Parse the launcher's deliberately small mapping/scalar YAML subset."""
    root = {}
    stack = [(-1, root)]
    for raw_line in str(text).splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith('#'):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(' '))
        line = raw_line.strip()
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        key = key.strip()
        value = value.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value == '':
            child = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = parse_scalar(value)
    return root


def read_simple_yaml(path):
    if not path.exists():
        return {}
    return parse_simple_yaml_text(
        path.read_text(encoding='utf-8', errors='ignore')
    )


def simple_yaml_mapping_lines(data, indent=0):
    """Serialize a nested mapping using the same readable config format."""
    lines = []

    def append_mapping(mapping, current_indent):
        prefix = ' ' * current_indent
        for key, value in mapping.items():
            if isinstance(value, dict):
                if value:
                    lines.append(f'{prefix}{key}:')
                    append_mapping(value, current_indent + 2)
                else:
                    lines.append(f'{prefix}{key}: {{}}')
            else:
                lines.append(f'{prefix}{key}: {scalar_to_yaml(value)}')

    append_mapping(data, indent)
    return lines


def write_simple_yaml(path, data):
    lines = [
        '# Dawn of the Tiberium Age Randomizer player config.',
        '# Shared by standalone and Archipelago launcher workflows.',
        '# Archipelago player YAML is exported from the launcher AP tab.',
        '',
    ]

    lines.extend(simple_yaml_mapping_lines(data))
    atomic_write_text(path, '\n'.join(lines) + '\n')


def load_config():
    migrate_legacy_config()
    loaded = read_simple_yaml(CONFIG_PATH)
    migrated = migrate_loaded_config(loaded)
    config = deep_merge(DEFAULT_CONFIG, loaded)
    if migrated or not CONFIG_PATH.exists():
        save_config(config)
    return config


def save_config(config):
    write_simple_yaml(CONFIG_PATH, deep_merge(DEFAULT_CONFIG, config))


def migrate_legacy_config():
    """Move pre-package player YAML into its grouped configuration folder."""
    if CONFIG_PATH.exists() or not LEGACY_CONFIG_PATH.is_file():
        return
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LEGACY_CONFIG_PATH.replace(CONFIG_PATH)
