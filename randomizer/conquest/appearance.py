"""Transparent strategic markers extracted from installed DTA tank sprites."""

import struct
import zlib

from randomizer.core.paths import GAME_ROOT
from randomizer.dta.cameos import _ini_sections, mix_asset, decode_shp_frame, _png_chunk
from .catalogue import ROSTERS


def army_sprites():
    """Decode eight facings off the UI thread; omit native shadow frames."""
    rules = _ini_sections(GAME_ROOT / 'INI/Rules.ini')
    art = _ini_sections(GAME_ROOT / 'INI/Art.ini')
    palette = mix_asset('UNITTEM.PAL')
    if not palette or len(palette) < 768:
        return {}
    result = {}
    for faction, roster in ROSTERS.items():
        image = rules[roster[2]].get('image', roster[2]).upper()
        row = art.get(image, {})
        data = mix_asset(row.get('image', image) + '.SHP')
        if not data:
            continue
        frames = []
        for facing in range(0, 32, 4):
            body = int(row.get('startstandframe', 0)) + facing * int(row.get('standingframes', 1))
            turret = int(row.get('startturretframe', 32)) + facing
            width, height, pixels = decode_shp_frame(data, body)
            tw, th, top = decode_shp_frame(data, turret)
            if (tw, th) == (width, height):
                pixels = bytearray(b or a for a, b in zip(pixels, top))
            # Keep the native sprite and add a pale one-pixel contour, with a
            # fully transparent exterior. Ownership is shown by the node ring.
            stride = width + 2
            rgba = bytearray(stride * (height + 2) * 4)
            for y in range(height):
                for x in range(width):
                    index = pixels[y * width + x]
                    if not index:
                        continue
                    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        offset = ((y + 1 + dy) * stride + x + 1 + dx) * 4
                        rgba[offset:offset + 4] = bytes((220, 232, 238, 220))
            for y in range(height):
                for x in range(width):
                    index = pixels[y * width + x]
                    if index:
                        offset = ((y + 1) * stride + x + 1) * 4
                        color = palette[index * 3:index * 3 + 3]
                        if 16 <= index <= 31:
                            # Native remap ramp is magenta until a house color
                            # is applied. Use neutral steel under the owner ring.
                            shade = round(48 + (31 - index) * 12)
                            rgba[offset:offset + 4] = bytes((shade, shade, shade, 255))
                        else:
                            rgba[offset:offset + 4] = bytes(min(255, c * 4) for c in color) + b'\xff'
            scanlines = b''.join(b'\0' + rgba[y * stride * 4:(y + 1) * stride * 4]
                                 for y in range(height + 2))
            frames.append(b'\x89PNG\r\n\x1a\n'
                + _png_chunk(b'IHDR', struct.pack('>IIBBBBB', stride, height + 2, 8, 6, 0, 0, 0))
                + _png_chunk(b'IDAT', zlib.compress(scanlines)) + _png_chunk(b'IEND', b''))
        result[faction] = frames
    return result
