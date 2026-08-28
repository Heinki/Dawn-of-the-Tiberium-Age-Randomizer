"""DTA Art.ini, TS MIX, and SHP cameo adapter."""

import struct
import zlib
from functools import lru_cache
from pathlib import Path

from randomizer.core.paths import CAMEO_CACHE_DIR, GAME_ROOT


TEXT_ONLY_CAMEO_IDS = frozenset({
    # No dedicated native cameo exists for these registered types. Art.ini
    # either omits Cameo or points at a different unit's labelled artwork.
    'BRIG', 'RAPARTY',
    'CYP', 'ILHEMOTH', 'TNKN', 'BEHEPLSM', 'FLAKCORV',
})


def _ini_sections(path):
    sections = {}
    current = None
    for raw in Path(path).read_text(encoding='cp1252', errors='ignore').splitlines():
        line = raw.split(';', 1)[0].strip()
        if line.startswith('[') and line.endswith(']'):
            current = line[1:-1].strip().upper()
            sections.setdefault(current, {})
        elif current and '=' in line:
            key, value = line.split('=', 1)
            sections[current][key.strip().casefold()] = value.strip()
    return sections


def mix_crc(filename):
    """Return the TS/RA2 padded CRC32 MIX identifier."""
    name = bytearray(Path(filename).name.upper().encode('ascii'))
    length = len(name)
    groups = length >> 2
    if length & 3:
        name.append(length - (groups << 2))
        for _ in range(3 - (length & 3)):
            name.append(name[groups << 2])
    return zlib.crc32(name) & 0xFFFFFFFF


def _read_mix_entry(mix_path, filename):
    wanted = mix_crc(filename)
    with Path(mix_path).open('rb') as stream:
        marker = stream.read(4)
        if len(marker) != 4:
            return None
        first_word, flags = struct.unpack('<HH', marker)
        if first_word == 0:
            if flags & 0x0002:
                return None
            header_start = 4
        else:
            header_start = 0
            stream.seek(0)
        header = stream.read(6)
        if len(header) != 6:
            return None
        count, _data_size = struct.unpack('<HI', header)
        index = stream.read(count * 12)
        if len(index) != count * 12:
            return None
        data_start = header_start + 6 + count * 12
        for offset in range(0, len(index), 12):
            file_id, relative, size = struct.unpack_from('<III', index, offset)
            if file_id != wanted:
                continue
            stream.seek(data_start + relative)
            payload = stream.read(size)
            return payload if len(payload) == size else None
    return None


def _mix_search_order():
    mix_dir = GAME_ROOT / 'MIX'
    return [
        *sorted(mix_dir.glob('ECache*.mix'), reverse=True),
        *sorted(mix_dir.glob('SideC*.mix')),
        *sorted(mix_dir.glob('sidenc*.mix')),
        mix_dir / 'Conquer.mix',
        mix_dir / 'Cache.mix',
        *sorted(mix_dir.glob('Expand*.mix'), reverse=True),
        mix_dir / 'Local.mix',
    ]


@lru_cache(maxsize=512)
def mix_asset(filename):
    for mix_path in _mix_search_order():
        if not mix_path.is_file():
            continue
        payload = _read_mix_entry(mix_path, filename)
        if payload is not None:
            return payload
    return None


def _decode_rle_line(payload, width):
    output = bytearray()
    cursor = 0
    while cursor < len(payload) and len(output) < width:
        value = payload[cursor]
        cursor += 1
        if value:
            output.append(value)
            continue
        if cursor >= len(payload):
            break
        run = payload[cursor]
        cursor += 1
        output.extend(b'\0' * run)
    if len(output) < width:
        output.extend(b'\0' * (width - len(output)))
    return output[:width]


def decode_shp_frame(data, frame_index=0):
    if len(data) < 8:
        raise ValueError('Truncated TS SHP header')
    empty, full_width, full_height, frame_count = struct.unpack_from('<4H', data, 0)
    if empty != 0 or not full_width or not full_height or frame_index >= frame_count:
        raise ValueError('Invalid TS SHP header')
    frame_offset = 8 + frame_index * 24
    if frame_offset + 24 > len(data):
        raise ValueError('Truncated TS SHP frame table')
    x, y, width, height, flags = struct.unpack_from('<4HI', data, frame_offset)
    data_offset = struct.unpack_from('<I', data, frame_offset + 20)[0]
    if not width or not height or data_offset >= len(data):
        raise ValueError('Invalid TS SHP frame')

    cropped = bytearray(width * height)
    cursor = data_offset
    if flags & 0x2:
        for row in range(height):
            if cursor + 2 > len(data):
                raise ValueError('Truncated TS SHP RLE row')
            row_size = struct.unpack_from('<H', data, cursor)[0]
            if row_size < 2 or cursor + row_size > len(data):
                raise ValueError('Invalid TS SHP RLE row')
            decoded = _decode_rle_line(data[cursor + 2:cursor + row_size], width)
            cropped[row * width:(row + 1) * width] = decoded
            cursor += row_size
    else:
        size = width * height
        if cursor + size > len(data):
            raise ValueError('Truncated TS SHP pixels')
        cropped[:] = data[cursor:cursor + size]

    pixels = bytearray(full_width * full_height)
    for row in range(height):
        target_y = y + row
        if target_y >= full_height or x >= full_width:
            continue
        count = min(width, full_width - x)
        start = target_y * full_width + x
        pixels[start:start + count] = cropped[row * width:row * width + count]
    return full_width, full_height, pixels


def _png_chunk(kind, payload):
    return (
        struct.pack('>I', len(payload)) + kind + payload
        + struct.pack('>I', zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _write_indexed_png(width, height, pixels, palette_data, output_path):
    if len(palette_data) < 768:
        raise ValueError('Invalid DTA cameo palette')
    scale = 4 if max(palette_data[:768]) <= 63 else 1
    rgba = bytearray(width * height * 4)
    cursor = 0
    for color_index in pixels:
        palette_offset = color_index * 3
        rgba[cursor:cursor + 3] = bytes(
            min(255, component * scale)
            for component in palette_data[palette_offset:palette_offset + 3]
        )
        rgba[cursor + 3] = 0 if color_index == 0 else 255
        cursor += 4
    scanlines = b''.join(
        b'\0' + bytes(rgba[row * width * 4:(row + 1) * width * 4])
        for row in range(height)
    )
    png = (
        b'\x89PNG\r\n\x1a\n'
        + _png_chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0))
        + _png_chunk(b'IDAT', zlib.compress(scanlines, level=9))
        + _png_chunk(b'IEND', b'')
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(png)
    return output_path


def shp_to_png(shp_data, palette_data, output_path):
    width, height, pixels = decode_shp_frame(shp_data)
    return _write_indexed_png(
        width, height, pixels, palette_data, output_path
    )


def _effective_art_value(sections, section_id, key, seen=None):
    section_id = str(section_id or '').upper()
    seen = set(seen or ())
    if not section_id or section_id in seen:
        return ''
    seen.add(section_id)
    values = sections.get(section_id, {})
    if values.get(key):
        return values[key]
    return _effective_art_value(
        sections,
        values.get('basesection') or values.get('$inherits'),
        key,
        seen,
    )


def ensure_unit_cameos(unit_ids):
    rules = _ini_sections(GAME_ROOT / 'INI' / 'Rules.ini')
    art = _ini_sections(GAME_ROOT / 'INI' / 'Art.ini')
    palette = mix_asset('CAMEO.PAL')
    if palette is None:
        return {}
    result = {}
    for raw_unit_id in unit_ids:
        unit_id = str(raw_unit_id or '').upper()
        output = CAMEO_CACHE_DIR / f'{unit_id.lower()}-dta.png'
        if unit_id in TEXT_ONLY_CAMEO_IDS:
            # Older builds may have cached the incorrect inherited cameo.
            # Remove it so every UI surface is forced back to its text card.
            try:
                output.unlink(missing_ok=True)
            except OSError:
                pass
            continue
        art_id = (
            _effective_art_value(rules, unit_id, 'image') or unit_id
        ).upper()
        cameo = _effective_art_value(art, art_id, 'cameo')
        filenames = []
        if cameo:
            filenames.append(cameo if Path(cameo).suffix else cameo + '.SHP')
        shp = next(
            (payload for filename in filenames if (payload := mix_asset(filename)) is not None),
            None,
        )
        try:
            if shp is None:
                continue
            shp_to_png(shp, palette, output)
        except (OSError, ValueError, struct.error):
            continue
        result[unit_id] = output
    return result


def ensure_superweapon_cameos(superweapon_ids, sidebar_overrides=None):
    """Extract DTA SuperWeaponType SidebarImage SHPs."""
    rules = _ini_sections(GAME_ROOT / 'INI' / 'Rules.ini')
    palette = mix_asset('CAMEO.PAL')
    if palette is None:
        return {}
    overrides = {
        str(power_id).upper(): str(image)
        for power_id, image in (sidebar_overrides or {}).items()
        if image
    }
    result = {}
    for raw_power_id in superweapon_ids:
        power_id = str(raw_power_id or '').upper()
        cameo = overrides.get(
            power_id,
            _effective_art_value(rules, power_id, 'sidebarimage'),
        )
        if not cameo:
            continue
        filename = cameo if Path(cameo).suffix else cameo + '.SHP'
        shp = mix_asset(filename)
        if shp is None:
            continue
        output = CAMEO_CACHE_DIR / f'sw-{power_id.lower()}-dta.png'
        try:
            shp_to_png(shp, palette, output)
        except (OSError, ValueError, struct.error):
            continue
        result[power_id] = output
    return result
