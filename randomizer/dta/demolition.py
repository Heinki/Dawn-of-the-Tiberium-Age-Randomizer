"""Isolated Demolition Truck blast animations for player reward stacks."""

from functools import lru_cache

from randomizer.config.tuning import stacked_weapon_damage, stacking_amount
from randomizer.core.paths import GAME_ROOT
from randomizer.dta.rules import ini_sections


PLAYER_BLAST_ANIMATION = 'DTARDEMONUKE'
PLAYER_BLAST_AREA_ANIMATION = 'DTARDEMOAREA'
LEPTONS_PER_CELL = 256


@lru_cache(maxsize=1)
def _native_blast_art():
    art = ini_sections(GAME_ROOT / 'INI' / 'Art.ini')
    return art['DEMONUKE'], art['DEMOAREA']


def demolition_blast_values(damage_stacks=0, area_stacks=0):
    """Return animation damage and radius after capped unit buff stacks."""
    _blast, area = _native_blast_art()
    base_damage = int(float(area['Damage']))
    base_radius = int(float(area['DamageRadius']))
    damage_stacks = max(0, int(damage_stacks))
    area_stacks = max(0, int(area_stacks))
    return (
        stacked_weapon_damage(base_damage, damage_stacks),
        base_radius + int(round(
            LEPTONS_PER_CELL * stacking_amount('area', area_stacks)
        )),
    )


def player_demolition_blast_art(damage_stacks=0, area_stacks=0):
    """Clone both native animations; leave enemy and scripted types untouched."""
    if not damage_stacks and not area_stacks:
        return {}
    native_blast, native_area = _native_blast_art()
    blast = dict(native_blast)
    area = dict(native_area)
    blast.setdefault('Image', 'DEMONUKE')
    area.setdefault('Image', 'DEMOAREA')
    blast['Spawns'] = PLAYER_BLAST_AREA_ANIMATION
    damage, radius = demolition_blast_values(damage_stacks, area_stacks)
    area['Damage'] = str(damage)
    area['DamageRadius'] = str(radius)
    return {
        'Animations': {
            '1': PLAYER_BLAST_ANIMATION,
            '2': PLAYER_BLAST_AREA_ANIMATION,
        },
        PLAYER_BLAST_ANIMATION: blast,
        PLAYER_BLAST_AREA_ANIMATION: area,
    }
