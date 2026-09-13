"""Shared DTA movement capability and amphibious-drive rules."""


DRIVE_LOCOMOTOR = '{4A582741-9839-11d1-B709-00A024DDAFD1}'
AMPHIBIOUS_DRIVE_OVERRIDES = {
    # DTA's working HVCSAM Hover MLRS uses Drive locomotion with Hover terrain
    # speeds and Fly pathfinding. All three fields are required together.
    'SpeedType': 'Hover',
    'Locomotor': DRIVE_LOCOMOTOR,
    'MovementZone': 'Fly',
}

_WATER_SPEED_TYPES = frozenset({'amphibious', 'float', 'hover', 'winged'})
_WATER_MOVEMENT_ZONES = frozenset({
    'amphibious', 'amphibiouscrusher', 'amphibiousdestroyer', 'fly', 'water',
})
_LAND_VEHICLE_MOVEMENT_ZONES = frozenset({'normal', 'crusher', 'destroyer'})


def _value(values, key):
    normalized_key = key.replace('_', '').casefold()
    for candidate, value in (values or {}).items():
        if str(candidate).replace('_', '').casefold() == normalized_key:
            return str(value or '').strip()
    return ''


def has_water_movement(values):
    """Return whether a TechnoType already has water-capable movement."""
    return (
        _value(values, 'SpeedType').casefold() in _WATER_SPEED_TYPES
        or _value(values, 'MovementZone').casefold() in _WATER_MOVEMENT_ZONES
    )


def supports_amphibious_drive(target):
    """Limit the upgrade to dry-land VehicleTypes."""
    return bool(
        target
        and target.get('category') == 'vehicles'
        and not target.get('naval')
        and str(target.get('movement_zone') or '').casefold()
        in _LAND_VEHICLE_MOVEMENT_ZONES
        and not has_water_movement(target)
    )


def amphibious_drive_overrides(values, target):
    """Return HVCSAM-style movement fields for an eligible dry vehicle."""
    if not supports_amphibious_drive(target) or has_water_movement(values):
        return {}
    return dict(AMPHIBIOUS_DRIVE_OVERRIDES)
