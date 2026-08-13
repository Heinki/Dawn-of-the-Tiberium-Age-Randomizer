"""Read/write helpers for DTA/Vinifera launch option files."""


def choice_label_from_ini(path, key, choices, default=''):
    """Read numeric INI option and return matching configured UI label."""
    if not path.exists():
        return default
    try:
        lines = path.read_text(
            encoding='utf-8',
            errors='ignore',
        ).splitlines()
    except OSError:
        return default

    wanted_prefix = key.lower()
    for line in lines:
        stripped = line.strip()
        if not stripped.lower().startswith(wanted_prefix) or '=' not in stripped:
            continue
        _, value = stripped.split('=', 1)
        selected = value.strip()
        for label, code in choices:
            if str(code) == selected:
                return label
    return default


def spawn_ini_text(
    scenario,
    difficulty_value,
    game_speed_value,
    extra_options=None,
):
    """Serialize DTA's direct single-player ``spawn.ini`` contract."""
    options = dict(extra_options or {})
    side = options.pop('Side', 0)
    firestorm = options.pop('Firestorm', 'True')
    mission_name = options.pop('MissionInternalName', '')
    difficulty_name = options.pop('DifficultyName', '')
    client_difficulty = options.pop('ClientDifficulty', '')
    computer_difficulty = options.pop(
        'DifficultyModeComputer',
        abs(int(difficulty_value) - 2),
    )
    content = [
        '[Settings]',
        f'Scenario={scenario}',
        'CampaignID=-1',
        f'GameSpeed={game_speed_value}',
        f'Firestorm={firestorm}',
        'IsSinglePlayer=Yes',
        'SidebarHack=Yes',
        f'Side={side}',
        'BuildOffAlly=True',
        f'DifficultyModeHuman={difficulty_value}',
        f'DifficultyModeComputer={computer_difficulty}',
    ]
    if mission_name:
        content.append(f'MissionInternalName={mission_name}')
    if difficulty_name:
        content.append(f'DifficultyName={difficulty_name}')
    if client_difficulty != '':
        content.append(f'ClientDifficulty={client_difficulty}')
    for key, value in sorted(options.items()):
        content.append(f'{key}={value}')
    return '\r\n'.join(content) + '\r\n'


def patch_large_ini_key(handle, key, value):
    """Patch existing INI value in-place without rewriting huge file."""
    pattern = f'{key}='.encode('ascii')
    pattern_lower = pattern.lower()
    replacement = str(value).encode('ascii')
    chunk_size = 1024 * 1024
    overlap_size = len(pattern) + 32
    carry = b''
    offset = 0
    handle.seek(0)

    while True:
        chunk = handle.read(chunk_size)
        if not chunk:
            return False
        data = carry + chunk
        search = data.lower()
        base_offset = offset - len(carry)
        position = 0

        while True:
            index = search.find(pattern_lower, position)
            if index < 0:
                break
            if index > 0 and data[index - 1] not in (10, 13):
                position = index + len(pattern)
                continue
            absolute_index = base_offset + index
            value_start = absolute_index + len(pattern)
            handle.seek(value_start)
            existing = handle.read(32)
            old_length = 0
            for byte in existing:
                if byte in (10, 13):
                    break
                old_length += 1
            if old_length >= len(replacement):
                handle.seek(value_start)
                handle.write(
                    replacement + (b' ' * (old_length - len(replacement)))
                )
                return True
            position = index + len(pattern)

        carry = data[-overlap_size:] if len(data) > overlap_size else data
        offset += len(chunk)
