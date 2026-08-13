"""DTA campaign difficulty labels and engine-level translation."""

from dataclasses import dataclass


DIFFICULTY_ORDER = (
    'Easy',
    'Normal',
    'Hard',
    'Brutal',
    'Extreme',
    'Ultimate',
    'Impossible',
)
DEFAULT_DIFFICULTY_LABELS = ('Easy', 'Normal', 'Hard')
DEFAULT_EXTENDED_DIFFICULTY_LABELS = ('Easy', 'Normal', 'Hard', 'Brutal')

_SEMANTIC_RANK = {
    label.casefold(): index for index, label in enumerate(DIFFICULTY_ORDER)
}


@dataclass(frozen=True)
class MissionDifficulty:
    requested_label: str
    label: str
    label_index: int
    labels: tuple[str, ...]
    has_extended_difficulty: bool
    client_rank: int
    engine_value: int
    apply_normal_modifiers: bool
    used_fallback: bool


def _display_label(value):
    text = str(value or '').strip()
    if not text:
        return ''
    known = next(
        (label for label in DIFFICULTY_ORDER if label.casefold() == text.casefold()),
        None,
    )
    return known or text[:1].upper() + text[1:].lower()


def mission_difficulty_labels(mission):
    """Return labels shown by DTA for one mission, in trackbar order."""
    extended = bool(mission.get('has_extended_difficulty'))
    labels = tuple(
        _display_label(label)
        for label in mission.get('difficulty_labels', ())
        if str(label or '').strip()
    )
    expected = 4 if extended else 3
    if len(labels) == expected:
        return labels
    return (
        DEFAULT_EXTENDED_DIFFICULTY_LABELS
        if extended else DEFAULT_DIFFICULTY_LABELS
    )


def installed_difficulty_labels(missions):
    """Return installed labels in semantic order, including DTA defaults."""
    found = set(DEFAULT_DIFFICULTY_LABELS)
    for mission in missions:
        found.update(mission_difficulty_labels(mission))
    ordered = [label for label in DIFFICULTY_ORDER if label in found]
    ordered.extend(sorted(found.difference(ordered), key=str.casefold))
    return tuple(ordered)


def resolve_mission_difficulty(mission, requested_label):
    """Resolve one global selection to DTA's closest supported lower label.

    DTA has three-position and four-position mission selectors. Display labels
    are mission-authored and do not directly equal Tiberian Sun's three engine
    difficulty values. This mirrors DTA client translation before writing
    ``spawn.ini`` and applying map-code overlays.
    """
    labels = mission_difficulty_labels(mission)
    requested = _display_label(requested_label) or 'Normal'
    requested_rank = _SEMANTIC_RANK.get(
        requested.casefold(), _SEMANTIC_RANK['normal']
    )

    known = [
        (index, label, _SEMANTIC_RANK.get(label.casefold()))
        for index, label in enumerate(labels)
    ]
    exact = next(
        (item for item in known if item[1].casefold() == requested.casefold()),
        None,
    )
    if exact is not None:
        selected = exact
    else:
        lower = [item for item in known if item[2] is not None and item[2] <= requested_rank]
        if lower:
            selected = max(lower, key=lambda item: (item[2], item[0]))
        else:
            recognized = [item for item in known if item[2] is not None]
            selected = min(recognized, key=lambda item: (item[2], item[0])) if recognized else known[0]

    index, label, _ = selected
    extended = bool(mission.get('has_extended_difficulty'))
    if extended:
        client_ranks = (10, 20, 30, 40)
    else:
        client_ranks = (10, 30, 40)
    client_rank = client_ranks[index]
    engine_value = 0 if client_rank == 10 else 2 if client_rank == 40 else 1
    return MissionDifficulty(
        requested_label=requested,
        label=label,
        label_index=index,
        labels=labels,
        has_extended_difficulty=extended,
        client_rank=client_rank,
        engine_value=engine_value,
        apply_normal_modifiers=client_rank == 20,
        used_fallback=label.casefold() != requested.casefold(),
    )
