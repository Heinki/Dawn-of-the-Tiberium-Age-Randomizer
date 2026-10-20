"""Adapt native team outcomes and read only the current game's score log."""

from pathlib import Path

from randomizer.maps.ini import parse_action_groups


def adapt_team_outcomes(mission, sections):
    """Preserve authored results after separating human production countries.

    Vinifera's actions 1/2 compare Class->House directly, ignoring alliances
    and Spawn lookup. Personal countries therefore all lose a native faction
    win (and can accidentally win a scripted loss targeting an unused alias).
    Action 110 resolves Spawn waypoints and calls MPlayer_Defeated. Defeating
    the losing team lets the normal multiplayer alliance logic score everyone.
    """
    for key, value in sections.get('Actions', {}).items():
        count, groups = parse_action_groups(value)
        if count != len(groups):
            raise ValueError(f'Co-op action {key} has an invalid action count.')
        if not any(group[0] in {'1', '2'} for group in groups):
            continue
        rewritten = []
        for group in groups:
            if group[0] not in {'1', '2'}:
                rewritten.append(group)
                continue
            human_target = int(group[2]) == mission['coop_side']
            won = human_target if group[0] == '1' else not human_target
            positions = ([position for _side, _color, position in mission['coop_enemies']]
                         if won else [*range(mission['coop_player_count']),
                                      *(position for _side, _color, position in mission['coop_allies'])])
            for position in positions:
                rewritten.append(['110', '0', str(50 + position), '0', '0', '0', '0', 'A'])
        sections['Actions'][key] = ','.join([str(len(rewritten)),
                                            *(token for group in rewritten for token in group)])


def debug_logs(directory):
    directory = Path(directory)
    if not directory.is_dir():
        return []
    return [path for path in directory.iterdir() if path.is_file()
            and path.name.upper().startswith('DEBUG_') and path.suffix.lower() == '.log']


def anchor(handle, offset):
    handle.seek(max(0, offset - 128))
    return handle.read(min(offset, 128))


class ScoreLog:
    """Ignore old games, SYNC dumps and overwritten/partial log fragments."""

    def __init__(self, directory):
        self.directory = Path(directory)
        self.baseline = {}
        self.path = None
        self.offset = 0
        self.anchor = b''
        self.tail = b''
        for path in debug_logs(self.directory):
            stat = path.stat()
            with path.open('rb') as handle:
                self.baseline[path] = (stat.st_size, stat.st_mtime_ns, anchor(handle, stat.st_size))

    def read_text(self, *, final=False):
        if self.path is None:
            changed = []
            for path in debug_logs(self.directory):
                stat = path.stat()
                previous = self.baseline.get(path)
                if previous is None or (stat.st_size, stat.st_mtime_ns) != previous[:2]:
                    changed.append((stat.st_mtime_ns, path))
            if not changed:
                return ''
            self.path = max(changed, key=lambda item: item[0])[1]
            previous = self.baseline.get(self.path)
            if previous:
                self.offset, _, self.anchor = previous
        with self.path.open('rb') as handle:
            size = self.path.stat().st_size
            if size < self.offset or anchor(handle, self.offset) != self.anchor:
                self.offset = 0
                self.tail = b''
            handle.seek(self.offset)
            data = self.tail + handle.read()
            self.offset = handle.tell()
            self.anchor = anchor(handle, self.offset)
        if final:
            self.tail = b''
            return data.decode('utf-8', errors='replace') + ('\n' if data and not data.endswith(b'\n') else '')
        complete, separator, self.tail = data.rpartition(b'\n')
        if not separator:
            self.tail = data
            return ''
        return (complete + separator).decode('utf-8', errors='replace')
