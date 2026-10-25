"""Decode installed terrain for complete DTA placement validation."""

import base64
import struct
from .ground import _decode_lzo
from .placement import PlayableBounds


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

    def clear(
        self,
        cells,
        *,
        flat_tiles=(
            65535,
            0,
            1,
            152,
            153,
            154,
            155,
            156,
            157,
            158,
            159,
            160,
            161,
            162,
            163,
            164,
            165,
            166,
            167,
            231,
            232,
            233,
            234,
            235,
            236,
            237,
            238,
            239,
            240,
            241,
            242,
            243,
            244,
            245,
            246,
            247,
            248,
            249,
            250,
            251,
            252,
            253,
            254,
            255,
            256,
            257,
            258,
            259,
            260,
            261,
            262,
            263,
            264,
            265,
            266,
            267,
            268,
            269,
            270,
            271,
            272,
            273,
            274,
            275,
            276,
            277,
            278,
            279,
            280,
            281,
            282,
            283,
            284,
            285,
            286,
            287,
            288,
            289,
            290,
            291,
            292,
            293,
            294,
            295,
            296,
            297,
            298,
            299,
            300,
            301,
            302,
            303,
            304,
            305,
            306,
            307,
            308,
            309,
            310,
            311,
            312,
            970,
            971,
            972,
            973,
            974,
            975,
            976,
            977,
            978,
            979,
            980,
            981,
            982,
            983,
            984,
            985,
            986,
            987,
            1007,
            1008,
            1009,
            1010,
            1011,
            1012,
            1013,
            1014,
            1015,
            1016,
            1017,
            1018,
            1019,
            1020,
            1021,
            1022,
            1023,
            1032,
            1047,
            1048,
            1049,
            1050,
            1051,
            1052,
            1053,
            1054,
            1055,
            1056,
            1057,
            1058,
            1059,
            1060,
            1061,
            1062,
            1063,
            1064,
            1065,
            1066,
            1067,
            1068,
            1069,
            1070,
            1071,
            1072,
            1073,
            1074,
            1075,
            1955,
            1956,
            1957,
            1958,
            1959,
            1960,
            1961,
            1962,
            1963,
            1964,
            1965,
            1966,
            1967,
            1968,
            1969,
            1970,
            1971,
        ),
        occupied=()
    ):
        cells = set(cells)
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
