"""Native DTA endpoints, personal score identity and shared run agreement."""

from randomizer.coop.interfaces import unicast_ipv4
from .catalogue import validate_name


def validate_endpoints(plan, endpoints):
    players = plan.get('coop_players', [])
    if (
        not isinstance(endpoints, list)
        or not 2 <= len(players) <= 3
        or len(players) != len(endpoints)
    ):
        raise ValueError('Fortress network roster differs from the frozen run.')
    seen = set()
    for name, entry in zip(players, endpoints):
        if set(entry) != {'name', 'address', 'port'} or validate_name(entry['name']) != name:
            raise ValueError('Invalid Fortress endpoint.')
        address = unicast_ipv4(entry['address'])
        port = entry['port']
        if type(port) is not int or not 1 <= port <= 65535 or (address, port) in seen:
            raise ValueError('Invalid or repeated game endpoint.')
        seen.add((address, port))


def result_identity(run):
    slot = run.get('coop_player', 0)
    plan = run['plan']
    return (
        plan.get('coop_players', ['Commander'])[slot],
        plan['coalition_scores'][slot]['initial_transfers'],
        slot if plan.get('coop_players') else None,
    )
