"""Shared eligibility for aircraft that replenish ammunition at a dock."""

AIRCRAFT_BUILDINGS = {'GDI': 'GHPAD', 'Nod': 'NHPAD', 'Allies': 'AHPAD', 'Soviet': 'RAASTRP'}
AIRCRAFT_BUILDING_LABELS = {'GDI': 'GDI Helipad', 'Nod': 'Nod Helipad',
                            'Allies': 'Allied Helipad', 'Soviet': 'Soviet Runway'}


def docked_reload_time(rules, category, values):
    if category not in ('AircraftTypes', 'aircraft'):
        return 0
    try:
        if float(values.get('Ammo', 0)) <= 0:
            return 0
        buildings = set(rules.get('BuildingTypes', {}).values())
        docks = (value.strip() for value in values.get('Dock', '').split(','))
        if not any(kind in buildings for kind in docks):
            return 0
        return max(0, float(values.get('ReloadRate', rules.get('General', {}).get('ReloadRate', 0))))
    except (TypeError, ValueError):
        return 0
