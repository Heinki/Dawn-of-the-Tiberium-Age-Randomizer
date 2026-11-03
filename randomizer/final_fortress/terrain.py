"""Decode installed terrain for complete DTA placement validation."""

import base64
import struct
from .ground import _decode_lzo
from .placement import PlayableBounds


# Flat native ground/LAT sets from DTA's Temperat.ini and Desert.ini.
# Cliff, water, ramp and impassable variants are deliberately absent.
BUILDABLE_TILES = {
    'temperate': frozenset({
        65535, 0, 1, *range(152, 168), *range(231, 313),
        *range(970, 988), *range(1007, 1024), 1032,
        *range(1047, 1076), *range(1955, 1972),
        2945, 2946, *range(2949, 3064), 3163,
        *range(4253, 4270), *range(4365, 4382), *range(4804, 4935),
    }),
    'desert': frozenset({
        65535, 0, 1, *range(62, 69), *range(179, 196),
        *range(224, 325), *range(696, 747), *range(1366, 1383),
        2554, *range(2556, 2639), *range(3259, 3330),
        *range(3462, 3496),
    }),
}


def _lcw(data):
    output = bytearray()
    cursor = 0
    relative = data[:1] == b'\0'
    if relative:
        cursor = 1
    while cursor < len(data):
        command = data[cursor]
        cursor += 1
        if not command & 0x80:
            count = (command >> 4) + 3
            offset = ((command & 15) << 8) | data[cursor]
            cursor += 1
            position = len(output) - offset
        elif not command & 0x40:
            count = command & 63
            if not count:
                break
            output.extend(data[cursor : cursor + count])
            cursor += count
            continue
        elif command == 0xFE:
            count = struct.unpack_from('<H', data, cursor)[0]
            output.extend(bytes([data[cursor + 2]]) * count)
            cursor += 3
            continue
        else:
            count = (command & 63) + 3
            if command == 0xFF:
                count = struct.unpack_from('<H', data, cursor)[0]
                cursor += 2
            offset = struct.unpack_from('<H', data, cursor)[0]
            cursor += 2
            position = len(output) - offset if relative else offset
        for index in range(count):
            output.append(output[position + index])
    return output


def unpack(section, *, lzo=False):
    packed = base64.b64decode(''.join(section.values()), validate=True)
    result = bytearray()
    cursor = 0
    while cursor < len(packed):
        size, length = struct.unpack_from('<HH', packed, cursor)
        cursor += 4
        block = packed[cursor : cursor + size]
        if len(block) != size:
            raise ValueError('Truncated DTA terrain block.')
        cursor += size
        decoded = _decode_lzo(block, length) if lzo else _lcw(block)
        if len(decoded) != length:
            raise ValueError('DTA terrain block length mismatch.')
        result.extend(decoded)
    return result


class Terrain:
    def __init__(self, source):
        self.bounds = PlayableBounds(source['Map'])
        self.theater = source['Map']['Theater'].casefold()
        if self.theater not in ('temperate', 'desert'):
            raise ValueError('Unsupported Fortress terrain theater: ' + self.theater)
        raw = unpack(source['IsoMapPack5'], lzo=True)
        if len(raw) % 11 == 4 and raw[-4:] == b'\0' * 4:
            raw = raw[:-4]  # DTA editor's native trailing map-pack sentinel.
        self.cells = {
            (x, y): (tile, sub, height)
            for x, y, tile, sub, height, extra in struct.iter_unpack('<HHIBBB', raw)
        }
        self.overlays = unpack(source['OverlayPack'])
        self.objects = {(int(key) % 1000, int(key) // 1000) for key in source.get('Terrain', {})}
        self.heights = {cell: value[2] for cell, value in self.cells.items()}

    def clear(self, cells, *, flat_tiles=None, occupied=()):
        cells = set(cells)
        if flat_tiles is None:
            flat_tiles = BUILDABLE_TILES[self.theater]
        if not cells or cells.intersection(occupied) or cells.intersection(self.objects):
            return False
        if not self.bounds.contains(cells, heights=self.heights):
            return False
        heights = set()
        for x, y in cells:
            tile, sub, height = self.cells.get((x, y), (0, 0, 0))
            if tile not in flat_tiles or not 0 <= x < 512 or not 0 <= y < 512:
                return False
            if self.overlays[y * 512 + x] != 255:
                return False
            heights.add(height)
        return len(heights) == 1
