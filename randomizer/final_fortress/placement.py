"""DTA isometric bounds and native foundations."""

import re


class PlayableBounds:
    def __init__(self, section):
        row = {key.lower(): value for key, value in section.items()}
        size = list(map(int, row['size'].split(',')))
        local = list(map(int, row['localsize'].split(',')))
        if len(size) != 4 or len(local) != 4 or min(local[2:]) <= 0:
            raise ValueError('Invalid playable map rectangle.')
        self.width = size[2]
        self.left, self.top, self.width_local, self.height_local = local

    def project(self, x, y, height=0):
        # Native isometric cell top-left, in whole rendered-cell dimensions.
        # See World-Altering Editor GameMath/CellMath.cs; LocalSize is a
        # rendered rectangle, not the bounding box of packed diamond cells.
        return (x - y + self.width - 1) / 2, (x + y - self.width - 1 - height) / 2

    def contains(self, cells, *, margin=0, heights=None, maximum_height=None):
        for x, y in cells:
            levels = [heights.get((x, y), 0)] if heights is not None else [0]
            if maximum_height is not None:
                levels.append(maximum_height)
            for height in levels:
                u, v = self.project(x, y, height)
                if not (
                    self.left + margin <= u
                    and u + 1 <= self.left + self.width_local - margin
                    and self.top + margin <= v
                    and v + 1 <= self.top + self.height_local - margin
                ):
                    return False
        return True


def foundation(row, art):
    image = row.get('Image', '')
    entry = art.get(image.casefold(), {})
    value = row.get('Foundation', entry.get('Foundation', '1x1'))
    match = re.fullmatch(r'(\d+)[xX](\d+)', value)
    if match:
        return {(x, y) for x in range(int(match[1])) for y in range(int(match[2]))}
    if value.lower() != 'custom':
        raise ValueError(f'Unknown building foundation: {image}: {value}.')
    cells = {
        tuple(map(int, value.split(',')))
        for key, value in entry.items()
        if re.fullmatch(r'Foundation\.\d+', key)
    }
    if not cells:
        raise ValueError(f'Empty custom building foundation: {image}.')
    return cells
