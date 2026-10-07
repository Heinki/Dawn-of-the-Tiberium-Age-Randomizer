"""Bounded, paired TCP control channel for one host and up to three guests."""

import base64
import binascii
import hashlib
import hmac
import ipaddress
import json
import queue
import re
import secrets
import socket
import threading
import zlib

from .feature import player_count, require_enabled
from .compatibility import FINGERPRINT_POLICY, normalize_text


LOBBY_PORT = 19420
MAX_WIRE = 16 * 1024 * 1024
MAX_DATA = 32 * 1024 * 1024
INSTALLATION_FILES = ('version', 'game.exe', 'Vinifera.dll', 'LaunchVinifera.dat',
                      'INI/Rules.ini', 'INI/Enhance.ini', 'INI/Art.ini', 'INI/AI.ini', 'INI/Vinifera.ini',
                      'Resources/GameOptions.ini', 'Resources/SkirmishLobby.ini', 'INI/MPMaps.ini')


def pack(data):
    if len(data) > MAX_DATA:
        raise ValueError('Co-op data exceeds size limit.')
    return base64.b64encode(zlib.compress(data)).decode('ascii')


def unpack(value):
    try:
        decoder = zlib.decompressobj()
        data = decoder.decompress(base64.b64decode(value, validate=True), MAX_DATA + 1)
    except (binascii.Error, zlib.error, TypeError) as exc:
        raise ValueError('Invalid co-op data.') from exc
    if len(data) > MAX_DATA or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError('Invalid or excessive co-op data.')
    return data


def installation(root):
    return installation_manifest(root)[0]


def installation_manifest(root):
    fingerprint, files, _raw_files = installation_details(root)
    return fingerprint, files


def installation_details(root):
    """Ignore CRLF/LF differences in text without changing installed game files."""
    digest = hashlib.sha256()
    files = {}
    raw_files = {}
    for name in INSTALLATION_FILES:
        data = (root / name).read_bytes()
        raw_files[name] = hashlib.sha256(data).hexdigest()
        if name == 'version' or name.endswith('.ini'):
            data = normalize_text(data)
        digest.update(name.encode())
        digest.update(data)
        files[name] = hashlib.sha256(data).hexdigest()
    return digest.hexdigest(), files, raw_files


class Lobby:
    def __init__(self, root, role, name, count, *, address='', port=LOBBY_PORT,
                 game_port=1234, pairing_code=''):
        require_enabled()
        if role not in ('host', 'guest'):
            raise ValueError('Select Host or Join.')
        if role == 'guest':
            try:
                address = str(ipaddress.IPv4Address(str(address).strip()))
            except ipaddress.AddressValueError:
                raise ValueError(
                    'Enter only the host\'s ZeroTier Managed IPv4: four numbers separated by dots. '
                    'Do not include /24, a port, a network ID, or the pairing code.'
                ) from None
        if isinstance(name, str):
            name = name.strip()
        if not isinstance(name, str) or not name.strip() or not re.fullmatch(r'[A-Za-z0-9 _-]{1,15}', name):
            raise ValueError('Player name must contain 1–15 letters, digits, spaces, underscores or hyphens.')
        if not 1 <= int(port) <= 65535 or not 1 <= int(game_port) <= 65535:
            raise ValueError('Ports must be between 1 and 65535.')
        if not pairing_code or len(pairing_code) > 128:
            raise ValueError('Enter the host pairing code.')
        self.root, self.role, self.name = root, role, name
        self.count = player_count(count)
        self.address, self.port, self.game_port = address, int(port), int(game_port)
        self.pairing_code = pairing_code
        self.events = queue.Queue()
        self.players = [{'name': name, 'ip': '127.0.0.1', 'port': self.game_port}]
        self.slot = 0
        self.peers = {}
        self.closed = threading.Event()
        self.lock = threading.RLock()
        self.listener = None
        self.connected = False

    def start(self):
        threading.Thread(target=self._run, daemon=True, name='DTACoopLobby').start()

    def close(self):
        self.closed.set()
        self.connected = False
        for connection in [self.listener, *self.peers.values()]:
            if connection:
                try:
                    connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                connection.close()

    @staticmethod
    def receive(stream):
        data = stream.readline(MAX_WIRE + 1)
        if not data:
            raise ConnectionError('Co-op peer disconnected before sending a message.')
        if len(data) > MAX_WIRE:
            raise ValueError('Co-op message exceeds size limit.')
        if not data.endswith(b'\n'):
            raise ConnectionError('Co-op peer disconnected before completing a message.')
        message = json.loads(data)
        if not isinstance(message, dict):
            raise ValueError('Invalid co-op message.')
        return message

    def send(self, message, slot=None):
        data = json.dumps(message, separators=(',', ':')).encode() + b'\n'
        if len(data) > MAX_WIRE:
            raise ValueError('Co-op message exceeds size limit.')
        with self.lock:
            targets = [self.peers[slot]] if slot is not None else list(self.peers.values())
            for connection in targets:
                connection.sendall(data)

    def _run(self):
        phase = 'reading the local DTA runtime'
        stream = None
        try:
            fingerprint, self.runtime_files, raw_files = installation_details(self.root)
            self.events.put(('diagnostic', ('coop_runtime_manifest', {
                'role': self.role, 'fingerprint': fingerprint, 'files': self.runtime_files,
                'fingerprint_policy': FINGERPRINT_POLICY, 'raw_files': raw_files,
            })))
            if self.role == 'host':
                phase = f'opening the host lobby (TCP {self.port})'
                self.listener = socket.create_server(('0.0.0.0', self.port), backlog=3)
                self.listener.settimeout(0.5)
                self.events.put(('status', f'Waiting for {self.count - 1} guests'))
                while len(self.players) < self.count and not self.closed.is_set():
                    try:
                        connection, remote = self.listener.accept()
                    except socket.timeout:
                        continue
                    try:
                        self._pair(connection, fingerprint, remote[0])
                    except (OSError, ValueError, KeyError, TypeError) as exc:
                        connection.close()
                        self.events.put(('status', f'Guest rejected: {exc}'))
                if self.closed.is_set():
                    return
                self.listener.close()
                self.listener = None
                self.connected = True
                for slot in self.peers:
                    self.send({'type': 'roster', 'players': self.players, 'slot': slot}, slot)
                self.events.put(('connected', self.players))
            else:
                phase = f'connecting to the host over ZeroTier (TCP {self.port})'
                self.events.put(('status', f'Connecting to host (TCP {self.port})...'))
                connection = socket.create_connection((self.address, self.port), timeout=15)
                self.peers[0] = connection
                stream = connection.makefile('rb')
                phase = 'waiting for the host greeting'
                self.events.put(('status', 'Host reached; checking DTA runtime...'))
                hello = self.receive(stream)
                if hello.get('fingerprint_policy') != FINGERPRINT_POLICY:
                    raise ValueError('DTA compatibility check differs. Update both launchers to the same build.')
                nonce = hello['nonce']
                proof = hmac.new(self.pairing_code.encode(), nonce.encode(), hashlib.sha256).hexdigest()
                phase = 'checking DTA runtime and pairing code with the host'
                self.send({'type': 'hello', 'protocol': 3, 'name': self.name,
                           'count': self.count, 'port': self.game_port,
                           'fingerprint': fingerprint, 'files': self.runtime_files, 'proof': proof,
                           'fingerprint_policy': FINGERPRINT_POLICY,
                           'folder': str(self.root.resolve()), 'node': socket.gethostname()})
                paired = self.receive(stream)
                expected = hmac.new(self.pairing_code.encode(), ('host:' + nonce).encode(), hashlib.sha256).hexdigest()
                if (paired.get('type') == 'rejected'
                        and hmac.compare_digest(str(paired.get('proof', '')), expected)):
                    if paired.get('reason') == 'runtime':
                        raise ValueError(self._runtime_mismatch(hello, 'Host'))
                    reasons = {'protocol': 'Co-op protocol differs. Update both launchers.',
                               'count': 'Player count differs. Choose the same count on both PCs.'}
                    raise ValueError(reasons.get(paired.get('reason'), 'Host rejected the connection.'))
                if paired.get('type') != 'paired' or not hmac.compare_digest(str(paired.get('proof', '')), expected):
                    raise ValueError('Host did not authenticate with the pairing code. Check that both codes match.')
                if hello.get('fingerprint') != fingerprint:
                    raise ValueError(self._runtime_mismatch(hello, 'Host'))
                connection.settimeout(None)
                self.events.put(('status', f'Paired; waiting for all {self.count} players...'))
                threading.Thread(target=self._reader, args=(0, stream), daemon=True).start()
                stream = None  # The reader owns the stream after pairing.
        except (OSError, ValueError, KeyError, TypeError) as exc:
            if not self.closed.is_set():
                if isinstance(exc, TimeoutError):
                    detail = f'Timed out while {phase}.'
                    if phase.startswith('connecting to the host'):
                        detail += f' Confirm Host is waiting and its firewall allows TCP {self.port} on ZeroTier.'
                else:
                    detail = f'Failed while {phase}: {exc}'
                self.events.put(('error', detail))
                self.close()
        finally:
            if stream is not None:
                stream.close()

    def _runtime_mismatch(self, remote, peer):
        files = remote.get('files')
        differences = {}
        if isinstance(files, dict):
            for name, local_hash in self.runtime_files.items():
                remote_hash = files.get(name)
                if remote_hash != local_hash:
                    # Only fixed relative paths and hashes enter diagnostic output.
                    valid = isinstance(remote_hash, str) and re.fullmatch(r'[0-9a-f]{64}', remote_hash)
                    differences[name] = {'local': local_hash, 'remote': remote_hash if valid else 'unavailable'}
        self.events.put(('diagnostic', ('coop_runtime_mismatch', {
            'role': self.role, 'files': differences,
        })))
        if differences:
            return (f'{peer} DTA runtime differs: ' + ', '.join(differences)
                    + '. Use matching DTA game files on both PCs; see connection log for hashes.')
        return (f'{peer} DTA runtime differs. Use matching DTA game files on both PCs. '
                'Update both launchers for per-file diagnostics.')

    def _pair(self, connection, fingerprint, ip):
        connection.settimeout(15)
        nonce = secrets.token_hex(24)
        connection.sendall((json.dumps({'nonce': nonce, 'fingerprint': fingerprint,
                                       'files': self.runtime_files,
                                       'fingerprint_policy': FINGERPRINT_POLICY}) + '\n').encode())
        stream = connection.makefile('rb')
        try:
            self._authenticate_guest(connection, stream, fingerprint, nonce, ip)
        except (OSError, ValueError, KeyError, TypeError):
            stream.close()
            raise

    def _authenticate_guest(self, connection, stream, fingerprint, nonce, ip):
        hello = self.receive(stream)
        expected = hmac.new(self.pairing_code.encode(), nonce.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(str(hello.get('proof', '')), expected):
            raise ValueError('Pairing code differs. Guest must paste the host pairing code.')
        reason = None
        detail = ''
        if hello.get('protocol') != 3 or hello.get('fingerprint_policy') != FINGERPRINT_POLICY:
            reason, detail = 'protocol', 'Co-op protocol differs. Update both launchers.'
        elif hello.get('count') != self.count:
            reason, detail = 'count', 'Player count differs. Choose the same count on both PCs.'
        elif hello.get('fingerprint') != fingerprint:
            reason, detail = 'runtime', self._runtime_mismatch(hello, 'Guest')
        if reason:
            proof = hmac.new(self.pairing_code.encode(), ('host:' + nonce).encode(), hashlib.sha256).hexdigest()
            connection.sendall((json.dumps({'type': 'rejected', 'reason': reason, 'proof': proof}) + '\n').encode())
            raise ValueError(detail)
        name = str(hello.get('name', '')).strip()
        if not name.strip() or not re.fullmatch(r'[A-Za-z0-9 _-]{1,15}', name):
            raise ValueError('Invalid guest name.')
        if name.casefold() in {player['name'].casefold() for player in self.players}:
            raise ValueError('Players need distinct names.')
        if hello.get('node') == socket.gethostname() and hello.get('folder') == str(self.root.resolve()):
            raise ValueError('Each player needs a separate DTA game folder.')
        port = int(hello['port'])
        if not 1 <= port <= 65535:
            raise ValueError('Invalid game UDP port.')
        if hello.get('node') == socket.gethostname() and port == self.game_port:
            raise ValueError('Players on one computer need distinct game UDP ports.')
        if any(player['ip'] == ip and player['port'] == port for player in self.players):
            raise ValueError('Players on one computer need distinct game UDP ports.')
        slot = len(self.players)
        proof = hmac.new(self.pairing_code.encode(), ('host:' + nonce).encode(), hashlib.sha256).hexdigest()
        connection.sendall((json.dumps({'type': 'paired', 'proof': proof}) + '\n').encode())
        self.players.append({'name': name, 'ip': ip, 'port': port})
        self.peers[slot] = connection
        self.events.put(('status', f'{len(self.players)}/{self.count} players ready'))
        connection.settimeout(None)
        threading.Thread(target=self._reader, args=(slot, stream), daemon=True).start()

    def _reader(self, slot, stream):
        try:
            while not self.closed.is_set():
                message = self.receive(stream)
                if message.get('type') == 'roster' and self.role == 'guest':
                    self.players = message['players']
                    self.slot = int(message['slot'])
                    self.players[0]['ip'] = socket.gethostbyname(self.address)
                    self.connected = True
                    self.events.put(('connected', self.players))
                else:
                    self.events.put(('message', (slot, message)))
        except (OSError, ValueError, KeyError) as exc:
            if not self.closed.is_set():
                self.events.put(('error', str(exc)))
                self.close()
        finally:
            stream.close()
