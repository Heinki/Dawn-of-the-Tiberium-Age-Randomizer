"""Settings-only Fortress lobby over DTA's authenticated, all-peer UDP transport."""

from randomizer.ui.viewport import ScrollableViewport, fit_dialog
import json
import queue
import secrets
import tkinter as tk
from tkinter import ttk, messagebox
from randomizer.core.paths import GAME_ROOT
from randomizer.coop.lobby import Lobby, pack, unpack
from randomizer.coop.interfaces import zerotier_ipv4_addresses
from randomizer.final_fortress.catalogue import validate_name
from .fortress_coop_launch import FortressCoopLaunchController


class FortressLobby(Lobby):
    mode = 'final_fortress'
    allow_auto_count = True


class FortressCoopController(FortressCoopLaunchController):
    def build_coop_controls(self, parent, row):
        super().build_coop_controls(parent, row)
        if parent is not getattr(self, 'mission_appearance_column', None):
            return
        if not hasattr(self, '_fortress_control_frames'):
            self._fortress_control_frames = []
        frame = ttk.LabelFrame(parent, text='Final Fortress co-op', padding=8)
        frame.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        frame.grid_remove()
        toggle = ttk.Checkbutton(
            frame,
            text='Co-op',
            variable=self.final_fortress_coop_var,
            command=self.on_fortress_coop_mode_changed,
        )
        toggle.grid(row=0, column=0, sticky='w')
        ttk.Label(frame, text='Co-op players').grid(row=0, column=1, padx=(12, 4))
        count = ttk.Combobox(
            frame,
            textvariable=self._fortress_coop_count_var,
            values=('2', '3'),
            state='readonly',
            width=3,
        )
        count.grid(row=0, column=2)
        connect = ttk.Button(
            frame, text='Co-op Connection…', command=self.open_fortress_coop_dialog
        )
        connect.grid(row=1, column=0, columnspan=3, sticky='w', pady=(6, 0))
        self._fortress_control_frames.append((frame, toggle, count, connect))

    def on_fortress_coop_mode_changed(self):
        if self._fortress_lobby or self.fortress_busy():
            self.final_fortress_coop_var.set(bool(self._fortress_lobby))
        self.refresh_final_fortress()

    def refresh_fortress_settings_controls(self):
        selected = self.final_fortress_mode_selected()
        locked = bool(self._fortress_lobby) or self.fortress_busy()
        mode = getattr(self, 'fortress_settings_mode_combo', None)
        if mode is not None:
            mode.configure(
                state='disabled' if locked or getattr(self, '_coop_lobby', None)
                or self.busy_depth else 'readonly'
            )
        for toggle, count, connect in getattr(self, '_coop_controls', []):
            toggle.master.grid_remove() if selected else toggle.master.grid()
        for frame, toggle, count, connect in getattr(self, '_fortress_control_frames', []):
            frame.grid() if selected else frame.grid_remove()
            toggle.configure(state='disabled' if locked else 'normal')
            count.configure(
                state='readonly' if self.final_fortress_coop_var.get() and not locked
                else 'disabled'
            )
            connect.configure(
                state=(
                    'normal'
                    if self.final_fortress_coop_var.get() or self._fortress_lobby
                    else 'disabled'
                )
            )
            if self.final_fortress_coop_var.get() or self._fortress_lobby:
                connect.grid()
            else:
                connect.grid_remove()
        # Preserve the campaign selection in its original variable.
        for name in ('include_challenge_missions_check', 'shop_include_challenge_missions_check'):
            widget = getattr(self, name, None)
            if widget is None:
                continue
            if selected:
                if not hasattr(widget, '_fortress_original_variable'):
                    widget._fortress_original_variable = widget.cget('variable')
                if not hasattr(self, '_fortress_no_challenge_maps'):
                    self._fortress_no_challenge_maps = tk.BooleanVar(value=False)
                widget.configure(variable=self._fortress_no_challenge_maps, state='disabled')
            elif hasattr(widget, '_fortress_original_variable'):
                widget.configure(variable=widget._fortress_original_variable, state='normal')

    def fortress_coop_guest(self):
        lobby = getattr(self, '_fortress_lobby', None)
        return bool(lobby and lobby.role == 'guest')

    def open_fortress_coop_dialog(self):
        current = getattr(self, '_fortress_connection_window', None)
        if current is not None and current.winfo_exists():
            current.lift()
            return
        window = tk.Toplevel(self)
        self._fortress_connection_window = window
        window.title('Final Fortress co-op')
        window.transient(self)
        window.resizable(True, True)
        viewport = ScrollableViewport(window, padding=16)
        viewport.pack(fill='both', expand=True)
        frame = viewport.content
        frame.columnconfigure(1, weight=1)
        role = tk.StringVar(value='Host')
        name = tk.StringVar(value='Commander')
        address = tk.StringVar()
        code = tk.StringVar(value=secrets.token_hex(4))
        for row, (text, variable) in enumerate(
            (
                ('Role', role),
                ('Player name', name),
                ('Host ZeroTier IPv4', address),
                ('Pairing code', code),
            )
        ):
            ttk.Label(frame, text=text).grid(row=row, column=0, sticky='w', padx=(0, 12), pady=5)
            widget = (
                ttk.Combobox(
                    frame, textvariable=variable, values=('Host', 'Join'), state='readonly'
                )
                if row == 0
                else ttk.Entry(frame, textvariable=variable, width=30)
            )
            widget.grid(row=row, column=1, sticky='ew', pady=5)

        def connect():
            if self._fortress_lobby or self.fortress_busy():
                return
            try:
                validate_name(name.get())
                count = int(self._fortress_coop_count_var.get())
                if count not in (2, 3):
                    raise ValueError('Choose two or three players in Settings.')
                host = role.get() == 'Host'
                bind = zerotier_ipv4_addresses()[0] if host else ''
                lobby = FortressLobby(
                    GAME_ROOT,
                    'host' if host else 'guest',
                    name.get(),
                    count,
                    address=address.get(),
                    pairing_code=code.get(),
                    bind_address=bind,
                )
                self._fortress_lobby = lobby
                self._fortress_ranks = {}
                lobby.start()
                if host:
                    address.set(bind)
                self.fortress_coop_status_var.set('Connecting…')
                self.refresh_fortress_settings_controls()
                self.after(100, self._poll_fortress_lobby)
            except (ValueError, OSError) as exc:
                messagebox.showerror('Final Fortress co-op', str(exc), parent=window)

        ttk.Label(frame, textvariable=self.fortress_coop_status_var, wraplength=400).grid(
            row=4, column=0, columnspan=2, sticky='w', pady=8
        )
        ttk.Button(frame, text='Connect', command=connect).grid(row=5, column=0, sticky='w')
        ttk.Button(frame, text='Disconnect', command=self.disconnect_fortress_coop).grid(
            row=5, column=1, sticky='e'
        )
        viewport.bind_controls()
        fit_dialog(window, frame)

    def publish_fortress_income(self):
        lobby = getattr(self, '_fortress_lobby', None)
        if not lobby or not lobby.connected:
            return
        state = self.final_fortress_repository.load()
        rank = (
            state['perk_ranks'].get('fundraising', 0)
            if 'fundraising' in state['selected_perks']
            else 0
        )
        self._fortress_ranks[lobby.slot] = rank
        if lobby.role == 'guest':
            lobby.send({'type': 'fortress_income', 'rank': rank})

    def _poll_fortress_lobby(self):
        lobby = self._fortress_lobby
        if not lobby:
            return
        try:
            for _ in range(40):
                try:
                    kind, value = lobby.events.get_nowait()
                except queue.Empty:
                    break
                if kind == 'connected':
                    self._fortress_coop_count_var.set(str(lobby.count))
                    self.fortress_coop_status_var.set(
                        'Connected: ' + ', '.join(p['name'] for p in value)
                    )
                    self.publish_fortress_income()
                elif kind == 'status':
                    self.fortress_coop_status_var.set(value)
                elif kind == 'error':
                    self.append_log('Fortress connection: ' + str(value), error=True)
                    self.cancel_fortress_preparation(str(value))
                    self.disconnect_fortress_coop()
                    return
                elif kind == 'message':
                    slot, message = value
                    self.handle_fortress_message(lobby, slot, message)
            pending = self._fortress_pending
            if pending and __import__('time').monotonic() > pending['deadline']:
                self.cancel_fortress_preparation('Fortress preparation timed out.')
        except (ValueError, OSError, KeyError, TypeError) as exc:
            self.cancel_fortress_preparation(str(exc))
            self.disconnect_fortress_coop()
            self.append_log(str(exc), error=True)
            return
        self.refresh_fortress_settings_controls()
        if self._fortress_lobby:
            self.after(200, self._poll_fortress_lobby)

    def handle_fortress_message(self, lobby, slot, message):
        kind = message.get('type')
        if kind == 'fortress_income' and lobby.role == 'host':
            rank = message.get('rank')
            if type(rank) is not int or not 0 <= rank <= 4:
                raise ValueError('Invalid personal Fundraising rank.')
            if self._fortress_pending:
                raise ValueError('Fundraising changed after run preparation.')
            self._fortress_ranks[slot] = rank
        elif kind == 'fortress_prepare' and lobby.role == 'guest':
            self.prepare_fortress_guest(lobby, message)
        elif kind == 'fortress_ready' and lobby.role == 'host':
            self.fortress_guest_ready(lobby, slot, message)
        elif kind == 'fortress_start' and lobby.role == 'guest':
            self.start_fortress_guest(lobby, message)
        elif kind == 'fortress_cancel':
            self.cancel_fortress_preparation('Peer cancelled preparation.', broadcast=False)

    def disconnect_fortress_coop(self):
        lobby = getattr(self, '_fortress_lobby', None)
        if lobby:
            if self._final_fortress_watch is None:
                self.cancel_fortress_preparation('Lobby disconnected.')
            lobby.close()
        self._fortress_lobby = None
        self._fortress_ranks = {}
        if hasattr(self, 'final_fortress_coop_var'):
            self.final_fortress_coop_var.set(False)
            self.fortress_coop_status_var.set('Disconnected')
            self.refresh_fortress_settings_controls()
