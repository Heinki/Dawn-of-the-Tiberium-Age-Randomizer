"""Installed DTA identities; no Mental Omega runtime dependencies."""

import re
from randomizer.dta.rules import PLAYABLE_FACTIONS, installed_effective_sections, techno_catalogue

SIDE_COUNTRIES = PLAYABLE_FACTIONS
SIDE_FAMILIES = ('gdi', 'nod', 'allies', 'soviet')
COUNTRY_LABELS = dict(zip(SIDE_COUNTRIES, SIDE_COUNTRIES))
TYPE_LISTS = ('InfantryTypes', 'VehicleTypes', 'AircraftTypes', 'BuildingTypes')


def validate_name(value):
    if (
        not isinstance(value, str)
        or not re.fullmatch(r'[A-Za-z0-9 _-]{1,15}', value)
        or not value.strip()
    ):
        raise ValueError(
            'Player names require 1–15 ASCII letters, digits, spaces, underscores or hyphens.'
        )
    return value


def installed_rules_registry(synchronous=False):
    return {}, installed_effective_sections()


def tier(record):
    # Match the installed DTA reward catalogue's reviewed tier classification.
    from randomizer.shop.catalogue import _unit_tiers

    return int(_unit_tiers().get(record['id'], 'tier_3' if record.get('special') else 'tier_1')[-1])


def roster(faction, level=None):
    return [
        r
        for r in techno_catalogue()
        if faction in r['playable_owners']
        and r['rewardable']
        and r['category'] in ('infantry', 'vehicles')
        and not r['naval']
        and r['primary_weapon']
        and not r['deploys_into']
        and not r['passengers']
        and (level is None or tier(r) == level)
    ]
