"""Source-only developer gate; packaged launchers always retain normal progression."""

from randomizer.core.paths import FROZEN


# Local developer switch, matching the co-op source flag. Frozen builds ignore
# it even when enabled here, preventing all-unlocks builds from reaching players.
TESTING_PROFILE_ENABLED = True


def testing_profile_enabled():
    return not FROZEN and TESTING_PROFILE_ENABLED is True


def require_testing_profile():
    if not testing_profile_enabled():
        raise ValueError('The source-only Final Fortress testing profile is disabled in this build.')
