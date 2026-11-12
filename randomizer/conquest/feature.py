"""Build-time switch for the unreleased Conquest mode."""

CONQUEST_FEATURE_ENABLED = False


def enabled():
    """Use the same release gate in source and packaged launchers."""
    return CONQUEST_FEATURE_ENABLED is True
