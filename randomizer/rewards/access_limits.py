"""Normalization for optional seed-wide content-access limits."""


DEFAULT_ACCESS_LIMIT = 1


def normalize_access_limits(value):
    """Return unit/building and power caps with legacy-safe defaults.

    A zero power cap keeps randomly assigned power unlocks out of the seed.
    """
    source = value if isinstance(value, dict) else {}

    def bounded_int(key, minimum):
        try:
            result = int(source.get(key, DEFAULT_ACCESS_LIMIT))
        except (TypeError, ValueError):
            result = DEFAULT_ACCESS_LIMIT
        return max(minimum, result)

    return {
        'enabled': bool(source.get('enabled', False)),
        'units': bounded_int('units', 1),
        'powers': bounded_int('powers', 0),
    }
