"""Exact mixed batches within DTA's six-type TaskForce boundary."""

from copy import deepcopy


def batches(units, capacity):
    remaining = deepcopy(units)
    while any(u['count'] for u in remaining):
        counts = [0] * len(remaining)
        for _ in range(capacity):
            available = [
                i
                for i, u in enumerate(remaining)
                if u['count'] and (counts[i] or sum(n > 0 for n in counts) < 6)
            ]
            if not available:
                break
            i = min(available, key=lambda i: (counts[i], i))
            remaining[i]['count'] -= 1
            counts[i] += 1
        yield [{'type': u['type'], 'count': count} for u, count in zip(units, counts) if count]
