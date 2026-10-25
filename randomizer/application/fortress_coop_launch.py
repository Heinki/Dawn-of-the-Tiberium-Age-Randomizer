"""Host/guest preparation barrier and exact native map digest agreement."""

from copy import deepcopy
import hashlib
import json
import secrets
import time
from randomizer.core.paths import GAME_ROOT, DEBUG_LOG
from randomizer.coop.lobby import pack, unpack
from randomizer.final_fortress.engine import prepare_game
from randomizer.final_fortress.coop import validate_endpoints


class FortressCoopLaunchController:
    def launch_fortress_coop(self):
        lobby = self._fortress_lobby
        if not lobby or lobby.role != 'host' or not lobby.connected or self.fortress_busy():
            return
        if len(lobby.players) != int(self._fortress_coop_count_var.get()) or set(
            self._fortress_ranks
        ) != set(range(lobby.count)):
            self.fortress_coop_status_var.set(
                'Wait for every player and personal Fundraising rank.'
            )
            return
        state = self.final_fortress_repository.load()
        preferences = dict(state['preferences'])
        pending = {
            'token': secrets.token_hex(24),
            'deadline': time.monotonic() + 180,
            'ready': set(),
            'lobby': lobby,
            'cancelled': False,
        }
        self._fortress_pending = pending
        self._final_fortress_preparing = True
        self.refresh_final_fortress()
        endpoints = [
            {'name': p['name'], 'address': p['ip'], 'port': p['port']} for p in lobby.players
        ]
        speed = self.get_selected_game_speed_value()

        def prepare():
            self.build_command()
            self.begin_fortress_preparation()
            self.final_fortress_repository.recover_finished_run(DEBUG_LOG)
            old = self.final_fortress_repository.load()['run']
            if old and old['status'] == 'active':
                self.final_fortress_repository.record_event(old['id'], 'abandoned')
            state, run_id = self.final_fortress_repository.begin_run(
                self.final_fortress_config,
                difficulty=preferences['difficulty'],
                seed='DFF-' + secrets.token_hex(8),
                player_country=preferences['player_country'],
                wave_multiplier=preferences['wave_multiplier'],
                coop_players=[p['name'] for p in endpoints],
                fundraising_ranks=[self._fortress_ranks[i] for i in range(lobby.count)],
            )
            pending['run_id'] = run_id
            pending['run'] = state['run']
            digest = prepare_game(
                GAME_ROOT, state['run'], game_speed=speed, coop_slot=0, endpoints=endpoints
            )
            pending['spawn_digest'] = hashlib.sha256(
                (GAME_ROOT / 'spawn.ini').read_bytes()
            ).hexdigest()
            return digest

        def prepared(digest):
            pending['worker'] = False
            if pending['cancelled']:
                return self.cancel_fortress_preparation('Preparation cancelled.')
            if not lobby.connected:
                raise ValueError('A Fortress player disconnected.')
            pending['digest'] = digest
            payload = pack(
                json.dumps(
                    {
                        'run': pending['run'],
                        'endpoints': endpoints,
                        'speed': speed,
                        'digest': digest,
                    }
                ).encode()
            )
            lobby.send({'type': 'fortress_prepare', 'token': pending['token'], 'payload': payload})
            self.fortress_coop_status_var.set('Map ready. Waiting for every guest digest…')

        pending['worker'] = True
        self.run_in_background(
            'Preparing Fortress co-op…',
            'Freezing the run and native map.',
            prepare,
            prepared,
            lambda exc, detail: self.fortress_coop_failed(exc, detail),
        )

    def prepare_fortress_guest(self, lobby, message):
        if self.fortress_busy() or self._fortress_pending:
            raise ValueError('Fortress preparation is already active.')
        token = message.get('token')
        if not isinstance(token, str) or not __import__('re').fullmatch('[0-9a-f]{48}', token):
            raise ValueError('Invalid preparation token.')
        payload = json.loads(unpack(message['payload']))
        run = payload['run']
        endpoints = payload['endpoints']
        validate_endpoints(run['plan'], endpoints)
        if [p['name'] for p in lobby.players] != run['plan']['coop_players']:
            raise ValueError('Frozen human roster differs from the connected lobby.')
        state = self.final_fortress_repository.load()
        rank = (
            state['perk_ranks'].get('fundraising', 0)
            if 'fundraising' in state['selected_perks']
            else 0
        )
        if run['plan']['fundraising_ranks'][lobby.slot] != rank:
            raise ValueError('Host changed this player’s personal Fundraising rank.')
        pending = {
            'token': token,
            'deadline': time.monotonic() + 180,
            'run': run,
            'run_id': run['id'],
            'digest': payload['digest'],
            'lobby': lobby,
            'cancelled': False,
            'worker': True,
        }
        self._fortress_pending = pending
        self._final_fortress_preparing = True
        self.refresh_final_fortress()

        def prepare():
            self.build_command()
            self.begin_fortress_preparation()
            self.final_fortress_repository.recover_finished_run(DEBUG_LOG)
            old = self.final_fortress_repository.load()['run']
            if old and old['status'] == 'active':
                self.final_fortress_repository.record_event(old['id'], 'abandoned')
            state = self.final_fortress_repository.join_coop_run(run, lobby.name)
            pending['run'] = state['run']
            digest = prepare_game(
                GAME_ROOT,
                state['run'],
                game_speed=payload['speed'],
                coop_slot=lobby.slot,
                endpoints=endpoints,
            )
            pending['spawn_digest'] = hashlib.sha256(
                (GAME_ROOT / 'spawn.ini').read_bytes()
            ).hexdigest()
            return digest

        def prepared(digest):
            pending['worker'] = False
            if pending['cancelled']:
                return self.cancel_fortress_preparation('Preparation cancelled.')
            if not lobby.connected or digest != pending['digest']:
                raise ValueError('Fortress map digest differs or connection closed.')
            pending['ready'] = True
            lobby.send({'type': 'fortress_ready', 'token': token, 'digest': digest})
            self.fortress_coop_status_var.set('Map verified. Waiting for host…')

        self.run_in_background(
            'Preparing Fortress co-op…',
            'Validating shared balance and native map.',
            prepare,
            prepared,
            lambda exc, detail: self.fortress_coop_failed(exc, detail),
        )

    def fortress_guest_ready(self, lobby, slot, message):
        pending = self._fortress_pending
        if not pending or message.get('token') != pending['token']:
            raise ValueError('Stale Fortress readiness.')
        if message.get('digest') != pending.get('digest'):
            raise ValueError('Fortress map digest differs.')
        pending['ready'].add(slot)
        if pending['ready'] == set(range(1, lobby.count)):
            if not lobby.connected:
                raise ValueError('Fortress connection closed before launch.')
            self.validate_prepared_fortress(pending)
            lobby.send(
                {'type': 'fortress_start', 'token': pending['token'], 'digest': pending['digest']}
            )
            self._fortress_pending = None
            self.start_fortress_process(pending['run'])

    def start_fortress_guest(self, lobby, message):
        pending = self._fortress_pending
        if (
            not pending
            or not pending.get('ready')
            or message.get('token') != pending['token']
            or message.get('digest') != pending['digest']
            or not lobby.connected
        ):
            raise ValueError('Invalid Fortress start agreement.')
        self.validate_prepared_fortress(pending)
        self._fortress_pending = None
        self.start_fortress_process(pending['run'])

    def validate_prepared_fortress(self, pending):
        if (
            hashlib.sha256((GAME_ROOT / 'spawnmap.ini').read_bytes()).hexdigest()
            != pending['digest']
        ):
            raise ValueError('Prepared Fortress map changed before launch.')
        if (
            hashlib.sha256((GAME_ROOT / 'spawn.ini').read_bytes()).hexdigest()
            != pending['spawn_digest']
        ):
            raise ValueError('Prepared Fortress spawn settings changed before launch.')
        self.build_command()

    def fortress_coop_failed(self, exc, detail):
        if self._fortress_pending:
            self._fortress_pending['worker'] = False
        self.append_log(detail, error=True)
        self.cancel_fortress_preparation(str(exc))

    def cancel_fortress_preparation(self, reason, *, broadcast=True):
        pending = getattr(self, '_fortress_pending', None)
        if not pending:
            return
        pending['cancelled'] = True
        lobby = pending['lobby']
        if broadcast and lobby.connected:
            try:
                lobby.send({'type': 'fortress_cancel', 'token': pending['token']})
            except (OSError, ValueError):
                pass
        self.fortress_coop_status_var.set(reason)
        if pending.get('worker'):
            return
        if pending.get('run_id'):
            run = self.final_fortress_repository.load()['run']
            if run and run['id'] == pending['run_id'] and run['status'] == 'active':
                self.final_fortress_repository.record_event(run['id'], 'abandoned')
        self._fortress_pending = None
        self._final_fortress_preparing = False
        self.release_fortress_runtime()
        self.refresh_final_fortress()
        if getattr(self, '_close_after_game', False):
            self.close_launcher()
