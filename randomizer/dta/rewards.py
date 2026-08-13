"""Translate earned safe DTA rewards into human difficulty modifiers."""

from collections import Counter

from randomizer.config.tuning import stacking_multiplier
from randomizer.rewards.catalogue import canonical_rewards


_BASE = {
    'Firepower': 1.0,
    'Armor': 1.0,
    'Groundspeed': 0.9,
    'Airspeed': 1.0,
    'ROF': 0.91,
    'Cost': 1.0,
    'BuildTime': 1.0,
}


def _number(value):
    text = f'{value:.6f}'.rstrip('0').rstrip('.')
    return text if text else '0'


def human_modifier_rules(rewards, baseline=None, section_name='Normal'):
    """Compose broad rewards in DTA's selected human difficulty section."""
    base = dict(_BASE)
    for key, value in (baseline or {}).items():
        if key not in base:
            continue
        try:
            base[key] = float(value)
        except (TypeError, ValueError):
            continue
    counts = Counter(
        reward.get('buff_type')
        for reward in canonical_rewards(rewards)
        if reward.get('dta_house_modifier') and reward.get('buff_type')
    )
    values = {}
    if counts['damage']:
        values['Firepower'] = _number(
            base['Firepower'] * stacking_multiplier('damage', counts['damage'])
        )
    if counts['armor']:
        # DTA's difficulty Armor multiplier scales hit points. The preserved
        # reward tuning expresses damage taken, so invert it here.
        values['Armor'] = _number(
            base['Armor'] / stacking_multiplier('armor', counts['armor'])
        )
    if counts['speed']:
        factor = stacking_multiplier('speed', counts['speed'])
        values['Groundspeed'] = _number(base['Groundspeed'] * factor)
        values['Airspeed'] = _number(base['Airspeed'] * factor)
    if counts['reload']:
        values['ROF'] = _number(
            base['ROF'] * stacking_multiplier('reload', counts['reload'])
        )
    if counts['cost']:
        values['Cost'] = _number(
            base['Cost'] * stacking_multiplier('cost', counts['cost'])
        )
    if counts['production']:
        values['BuildTime'] = _number(
            base['BuildTime']
            * stacking_multiplier('production', counts['production'])
        )
    return {section_name: values} if values else {}
