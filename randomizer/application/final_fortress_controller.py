"""Isolated Fortress workspace, purchases, native preparation and result polling."""

import secrets
import tkinter as tk
from tkinter import ttk, messagebox
from randomizer.core.paths import DEBUG_LOG, GAME_ROOT
from randomizer.final_fortress import DISPLAY_NAME
from randomizer.final_fortress.catalogue import COUNTRY_LABELS
from randomizer.final_fortress.config import DIFFICULTY_IDS, WAVE_MULTIPLIERS, load_config
from randomizer.final_fortress.maps import select_map, inspect_map
from randomizer.final_fortress.persistence import (
    FinalFortressRepository,
    FinalFortressPersistenceError,
)
from randomizer.final_fortress.challenges import label, description, maximum
from randomizer.final_fortress.ui import refresh_results, show_final_fortress_help
from randomizer.final_fortress.results import FinalFortressResultWatch
from randomizer.ui.config import PROGRESSION_MODES
from .fortress_coop_controller import FortressCoopController


class FinalFortressController(FortressCoopController):
    def initialize_final_fortress_controller(self):
        self._final_fortress_preparing = False
        self._final_fortress_watch = None
        self._final_fortress_saved_tabs = None
        self._fortress_lobby = None
        self._fortress_pending = None
        self._fortress_ranks = {}
        self._final_fortress_launch_blockers = []
        self._final_fortress_recovery_checked = set()
        self.final_fortress_coop_var = tk.BooleanVar(value=False)
        self._fortress_coop_count_var = tk.StringVar(value='2')
        self.fortress_coop_status_var = tk.StringVar(value='Disconnected')
        self.game_mode_choices = (*PROGRESSION_MODES, DISPLAY_NAME)
        self.game_mode_var = tk.StringVar(value=self.progression_mode_var.get())
        self.final_fortress_country_choices = {v: k for k, v in COUNTRY_LABELS.items()}
        self.final_fortress_difficulty_choices = {k.title(): k for k in DIFFICULTY_IDS}
        self.final_fortress_wave_multiplier_choices = {f'x{n}': n for n in WAVE_MULTIPLIERS}
        for field, value in [
            ('map', ''),
            ('country', ''),
            ('difficulty', 'Normal'),
            ('wave_multiplier', 'x1'),
            ('status', 'Choose your faction.'),
            ('help', ''),
            ('result', 'Finish a run to see its rewards.'),
            ('header', 'Final Fortress · Survival defense'),
            ('gems', 'Defensive Points: 0'),
        ]:
            setattr(self, 'final_fortress_' + field + '_var', tk.StringVar(value=value))
        self.final_fortress_repository = FinalFortressRepository()
        self.final_fortress_config = None
        self.final_fortress_state = None
        try:
            self.final_fortress_config = load_config()
            self.final_fortress_map_catalogue = self.final_fortress_config
            self.final_fortress_map_choices = (self.final_fortress_config['map']['display_name'],)
            self.final_fortress_state = self.final_fortress_repository.reconcile_perk_ranks(
                self.final_fortress_config
            )
            if self.final_fortress_state['preferences']['workspace_selected']:
                self.game_mode_var.set(DISPLAY_NAME)
        except (RuntimeError, ValueError, OSError) as exc:
            self.final_fortress_map_choices = ()
            self.final_fortress_status_var.set(str(exc))
        self.progression_mode_var.trace_add('write', self._sync_game_mode_choice)

    def _sync_game_mode_choice(self, *_args):
        if not self.final_fortress_mode_selected():
            self.game_mode_var.set(self.progression_mode_var.get())

    def final_fortress_mode_selected(self):
        variable = getattr(self, 'game_mode_var', None)
        return variable is not None and variable.get() == DISPLAY_NAME

    def final_fortress_selected(self):
        return (
            self.final_fortress_mode_selected()
            and hasattr(self, 'final_fortress_tab')
            and self.workspace_tabs.select() == str(self.final_fortress_tab)
        )

    def fortress_busy(self):
        process = getattr(self, 'active_game_process', None)
        return (
            self._final_fortress_preparing
            or self._final_fortress_watch is not None
            or bool(process and process.poll() is None)
        )

    def on_game_mode_changed(self, event=None):
        choice = self.game_mode_var.get()
        if choice not in self.game_mode_choices:
            return
        if (
            self.fortress_busy()
            or self._fortress_lobby
            or getattr(self, '_coop_lobby', None)
            or self.busy_depth
        ):
            self.game_mode_var.set(
                DISPLAY_NAME
                if self._final_fortress_saved_tabs is not None
                else self.progression_mode_var.get()
            )
            return
        try:
            self.final_fortress_repository.set_workspace_selected(choice == DISPLAY_NAME)
        except FinalFortressPersistenceError as exc:
            messagebox.showerror(DISPLAY_NAME, str(exc), parent=self)
            return
        if choice != DISPLAY_NAME:
            self.progression_mode_var.set(choice)
            self.on_progression_mode_changed(event)
        self.sync_shop_workspace()
        self.refresh_coop_controls()
        self.settings_canvas.yview_moveto(0)

    def sync_shop_workspace(self):
        if not hasattr(self, 'final_fortress_tab'):
            return super().sync_shop_workspace()
        book = self.workspace_tabs
        if self.final_fortress_mode_selected():
            if self._final_fortress_saved_tabs is None:
                super().sync_shop_workspace()
                self._final_fortress_saved_tabs = [
                    (self.nametowidget(tab), book.tab(tab, 'text'))
                    for tab in book.tabs() if tab != str(self.final_fortress_tab)
                ]
            for tab in tuple(book.tabs()):
                if tab not in (str(self.final_fortress_tab), str(self.settings_tab)):
                    book.forget(tab)
            if str(self.final_fortress_tab) not in book.tabs():
                book.insert(0, self.final_fortress_tab, text=DISPLAY_NAME)
            book.tab(self.settings_tab, text='Settings')
            book.select(self.final_fortress_tab)
            self.on_workspace_tab_changed()
            return
        if self._final_fortress_saved_tabs is not None:
            for index, (widget, title) in enumerate(self._final_fortress_saved_tabs):
                book.insert(index, widget, text=title)
            self._final_fortress_saved_tabs = None
        if str(self.final_fortress_tab) in book.tabs():
            book.forget(self.final_fortress_tab)
        return super().sync_shop_workspace()

    def on_workspace_tab_changed(self, _event=None):
        self.refresh_fortress_settings_controls()
        if self.final_fortress_mode_selected() and hasattr(self, 'final_fortress_tab'):
            self.subtitle_label.configure(textvariable=self.final_fortress_header_var)
            self.sync_workspace_layout()
            self.copy_seed_button.grid_remove()
            self.sync_debug_completion_controls()
            if self.workspace_tabs.select() == str(self.settings_tab):
                self.after_idle(
                    lambda: self.layout_settings_sections(self.settings_canvas.winfo_width())
                )
            self.after_idle(self.refresh_final_fortress)
            return
        if hasattr(self, 'subtitle_label'):
            self.subtitle_label.configure(textvariable=self.header_summary_var)
            self.copy_seed_button.grid()
        result = super().on_workspace_tab_changed(_event)
        self.sync_debug_completion_controls()
        return result

    def sync_debug_completion_controls(self):
        if self.final_fortress_mode_selected():
            for name in (
                'debug_complete_button', 'compact_complete_button',
                'shop_debug_mission_combo', 'shop_debug_complete_button',
            ):
                widget = getattr(self, name, None)
                if widget is not None:
                    widget.grid_remove()
            return
        return super().sync_debug_completion_controls()

    def refresh_coop_controls(self):
        result = super().refresh_coop_controls()
        if not hasattr(self, 'game_mode_var'):
            return result
        for name in ('progression_mode_combo', 'shop_progression_mode_combo'):
            widget = getattr(self, name, None)
            if widget:
                widget.configure(textvariable=self.game_mode_var, values=self.game_mode_choices)
        self.refresh_fortress_settings_controls()
        return result

    def apply_color_mode(self):
        super().apply_color_mode()
        palette = self.ui_palette()
        canvas = getattr(self, 'final_fortress_canvas', None)
        if canvas is not None:
            canvas.configure(background=palette['background'])
        for pane in getattr(self, 'final_fortress_panes', ()):
            pane.configure(background=palette['background'])
        for name in ('final_fortress_perk_details', 'final_fortress_challenge_details'):
            widget = getattr(self, name, None)
            if widget:
                palette = self.ui_palette()
                widget.configure(
                    background=palette['background'],
                    foreground=palette['foreground'],
                    selectbackground=palette['select'],
                    selectforeground=palette['select_foreground'],
                )

    def on_new_seed(self):
        if self.final_fortress_mode_selected():
            return self.show_final_fortress_help()
        return super().on_new_seed()

    def refresh_final_fortress(self):
        if self.final_fortress_config is None:
            return
        try:
            state = self.final_fortress_repository.load()
        except (ValueError, FinalFortressPersistenceError) as exc:
            self.final_fortress_status_var.set(str(exc))
            return
        self.final_fortress_state = state
        preferences = state['preferences']
        config = self.final_fortress_config
        self.final_fortress_map_var.set(config['map']['display_name'])
        self.final_fortress_country_var.set(COUNTRY_LABELS.get(preferences['player_country'], ''))
        self.final_fortress_difficulty_var.set(preferences['difficulty'].title())
        self.final_fortress_wave_multiplier_var.set(f'x{preferences["wave_multiplier"]}')
        self.final_fortress_gems_var.set(f'Defensive Points: {state["gems"]}')
        if not hasattr(self, 'final_fortress_perks_tree'):
            return
        from randomizer.final_fortress.perks import ranks, owned_rank, next_price

        tree = self.final_fortress_perks_tree
        perks_locked = self.final_fortress_perks_locked()
        self.final_fortress_perk_hint.configure(
            text=(
                'Perk changes are locked during an active run or while joining a host.'
                if perks_locked else
                '◀ Refund rank at full cost · ▶ Buy next rank · Left/Right keys'
            )
        )
        for perk in config['perks']:
            country = preferences['player_country']
            max_rank = len(ranks(perk, country))
            purchased_rank = owned_rank(state, perk['id'])
            rank = min(purchased_rank, max_rank)
            price = next_price(perk, purchased_rank, country)
            status = (
                'Enabled'
                if perk['id'] in state['selected_perks']
                else 'Disabled' if rank else 'Not purchased'
            )
            if purchased_rank > max_rank:
                status += f' · {purchased_rank} owned'
            values = (
                perk['display_name'],
                '◀' if purchased_rank and not perks_locked else '',
                f'{rank}/{max_rank}',
                '▶' if not perks_locked and price is not None and state['gems'] >= price else '',
                status,
                f'{price} Defensive Points' if price is not None else 'MAX',
                perk['description'],
            )
            if tree.exists(perk['id']):
                tree.item(perk['id'], values=values)
            else:
                tree.insert('', 'end', iid=perk['id'], values=values)
        if not tree.selection() and tree.get_children():
            tree.selection_set(tree.get_children()[0])
        self.select_final_fortress_perk()
        tree = self.final_fortress_challenge_tree
        for entry in config['challenges']:
            key = entry['id']
            stacks = min(maximum(entry), preferences['challenge_stacks'].get(key, 1))
            values = (
                'Yes' if key in preferences['selected_challenges'] else 'No',
                label(entry),
                '◀' if stacks > 1 else '',
                stacks,
                '▶' if stacks < maximum(entry) else '',
                stacks * entry['victory_gems_per_stack'],
                description(entry, stacks),
            )
            if tree.exists(key):
                tree.item(key, values=values)
            else:
                tree.insert('', 'end', iid=key, values=values)
        self.select_final_fortress_challenge()
        self.final_fortress_help_var.set(self.fortress_help_text())
        blockers = []
        try:
            inspect_map(GAME_ROOT, config['map'])
        except (ValueError, OSError) as exc:
            blockers.append(str(exc))
        if preferences['player_country'] is None:
            blockers.append('Choose your player faction.')
        self._final_fortress_launch_blockers = blockers
        busy = self.fortress_busy()
        guest = self.fortress_coop_guest()
        for combo in self.final_fortress_setup_combos:
            combo.configure(state='disabled' if busy or guest else 'readonly')
        self.final_fortress_launch_button.configure(
            state='disabled' if busy or blockers or guest else 'normal'
        )
        self.final_fortress_status_var.set(
            'Preparing game…'
            if self._final_fortress_preparing
            else (
                'Game running.'
                if busy
                else '; '.join(blockers) if blockers else 'Ready — defend for 60 in-game minutes.'
            )
        )
        refresh_results(self, state['run'])
        self.refresh_fortress_settings_controls()
        if (
            state['run']
            and not busy
            and state['run']['id'] not in self._final_fortress_recovery_checked
        ):
            self._final_fortress_recovery_checked.add(state['run']['id'])
            self.after_idle(self._recover_final_fortress_result)

    def fortress_help_text(self):
        return (
            'Defend the Civilian Armory (ARMORY) headquarters beside your initial MCV for 60 simulation minutes. A starting refinery includes one faction harvester; runs without a starting refinery receive none. Starting defenses add two emplacements of each unlocked type: GDI has two types, Nod and Soviet three, Allies four. Higher purchased ranks remain available when switching factions. Extra generators cover only the actual starting demand. Objective destruction means defeat. Ordinary skirmish AI remains active. Enemy MCVs deploy into protected starting yards; fixed turrets are immune and expansions remain destructible.\n\n'
            'Waves begin at minute 5 on one front, minute 10 on two, minute 15 on three. Difficulty and x1–x10 scale scripted troops. Five minutes separate complete deliveries. Enemy reservations: 480 units in groups of 20; allied reinforcements: 150 in shared groups of 15. Living survivors retain their reservations. Helpers receive attack orders.\n\n'
            'Six guarded crates exist from the start. First pickup grants 10 Defensive Points to every human. Human collectors receive their frozen payload; enemy/helper pickup sends it to the host. Contents: 40% 2,500 credits; 30% ten Tier 1 units; 20% five Tier 2 units; 10% one faction special. Guard deaths award nothing.\n\n'
            'Survival awards: 25 points at minute 25, 25 at minute 45, 50 on victory. Earned points survive defeat or quit. Verified victory/defeat also awards five points per 50 corrected friendly native kill-score points, capped at 500 at 5,000. Native scores may include captures. Unfinished quits have no kill bonus.\n\n'
            'Settings contains Final Fortress co-op for two or three humans. Host chooses shared settings/perks; Fundraising remains personal. Every peer verifies identical map bytes before launch. Each machine keeps its own wallet and purchases. Helpers fill only unused friendly seats. No mid-game joining or reconnect.\n\n'
            'Specialist support technology unlocks faction support units/buildings through the normal war factory or construction yard plus radar. Targeting and ammunition improves only eligible mobile types. Fortified infrastructure adds up to 45% health to production/economy buildings, separately from objective durability. Transport capacity adds up to three passenger slots without granting units or passengers. These perks share friendly private types with helpers and do not buff enemy copies.\n\n'
            'Permanent perks: the left arrow refunds the highest purchased rank at its full Defensive Points cost; the right arrow buys the next rank. Refunded points can be spent on another perk. Left/Right keys and the Refund rank / Buy buttons also work. Purchases and refunds are locked during an active run. Higher ranks retained from another faction can also be refunded. Disabling a perk keeps its purchased ranks and does not refund points.\n\n'
            'Perks show cumulative faction-specific ranks. Challenge affects enemies only. Double-click or Space toggles selected Challenge rows; inline arrows adjust stacks. Drag, Shift/Ctrl/Alt selection, Ctrl+A, bulk enable/disable and Max stacks are supported. Max stacks never enables modifiers.\n\n'
            + self.final_fortress_config['capabilities']['unsupported']
        )

    def show_final_fortress_help(self, page='How to play'):
        show_final_fortress_help(self, page)

    def _final_fortress_action(self, action):
        if self.fortress_busy() or self.fortress_coop_guest():
            return
        try:
            action()
            self.refresh_final_fortress()
        except (ValueError, FinalFortressPersistenceError) as exc:
            messagebox.showerror(DISPLAY_NAME, str(exc), parent=self)
        self.publish_fortress_income()

    def on_final_fortress_map_changed(self, _event=None):
        self._final_fortress_action(
            lambda: self.final_fortress_repository.set_map(
                self.final_fortress_config, self.final_fortress_config['map']['id']
            )
        )

    def on_final_fortress_country_changed(self, _event=None):
        self._final_fortress_action(
            lambda: self.final_fortress_repository.set_player_country(
                self.final_fortress_country_choices[self.final_fortress_country_var.get()]
            )
        )

    def final_fortress_perks_locked(self):
        state = self.final_fortress_state
        return bool(
            state is None
            or self.fortress_busy()
            or self.fortress_coop_guest()
            or (state['run'] is not None and state['run']['status'] == 'active')
        )

    def on_final_fortress_perk_click(self, event):
        tree = self.final_fortress_perks_tree
        if tree.identify_region(event.x, event.y) != 'cell':
            return
        key = tree.identify_row(event.y)
        column = tree.column(tree.identify_column(event.x), 'id')
        if not key or column not in ('decrease', 'increase'):
            return
        tree.selection_set(key)
        tree.focus(key)
        tree.focus_set()
        if tree.set(key, column):
            if column == 'decrease':
                self.refund_final_fortress_perk()
            else:
                self.buy_final_fortress_perk()
        return 'break'

    def buy_final_fortress_perk(self):
        from randomizer.final_fortress.perks import next_price, owned_rank

        if self.final_fortress_perks_locked():
            return 'break'
        selection = self.final_fortress_perks_tree.selection()
        if selection:
            perk = next(
                entry for entry in self.final_fortress_config['perks'] if entry['id'] == selection[0]
            )
            state = self.final_fortress_state
            price = next_price(perk, owned_rank(state, selection[0]),
                               state['preferences']['player_country'])
            if price is None or state['gems'] < price:
                return 'break'
            self._final_fortress_action(
                lambda: self.final_fortress_repository.purchase_perk(
                    self.final_fortress_config, selection[0]
                )
            )
        return 'break'

    def refund_final_fortress_perk(self):
        if self.final_fortress_perks_locked():
            return 'break'
        selection = self.final_fortress_perks_tree.selection()
        if selection and selection[0] in self.final_fortress_state['owned_perks']:
            self._final_fortress_action(
                lambda: self.final_fortress_repository.refund_perk(
                    self.final_fortress_config, selection[0]
                )
            )
        return 'break'

    def _recover_final_fortress_result(self):
        if self.fortress_busy():
            return
        self.run_in_background(
            'Recovering Fortress results…',
            'Reading matching native receipts.',
            lambda: self.final_fortress_repository.recover_finished_run(DEBUG_LOG),
            lambda _: self.refresh_final_fortress(),
            lambda exc, detail: self.append_log(str(exc), error=True),
        )

    def launch_final_fortress(self):
        if self._fortress_lobby:
            return self.launch_fortress_coop()
        if self.final_fortress_coop_var.get():
            return self.open_fortress_coop_dialog()
        if self.fortress_busy() or self._final_fortress_launch_blockers:
            return
        from randomizer.final_fortress.engine import prepare_game

        preferences = dict(self.final_fortress_state['preferences'])
        preferences['player_color'] = self.selected_fortress_color()
        speed = self.get_selected_game_speed_value()
        self._final_fortress_preparing = True
        self.refresh_final_fortress()
        pending = {}

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
                player_color=preferences['player_color'],
                wave_multiplier=preferences['wave_multiplier'],
            )
            pending['run_id'] = run_id
            prepare_game(GAME_ROOT, state['run'], game_speed=speed)
            return state['run']

        def finish(run):
            self.start_fortress_process(run)

        self.run_in_background(
            'Starting Final Fortress…',
            'Preparing the DTA survival map.',
            prepare,
            finish,
            lambda exc, detail: self.fortress_prepare_failed(exc, detail, pending),
        )

    def begin_fortress_preparation(self):
        from randomizer.maps.assets import claim_runtime_asset_lease

        claim_runtime_asset_lease()
        self.cleanup_generated_root_maps()
        self.clear_power_runtime_types()

    def fortress_prepare_failed(self, exc, detail, pending=None):
        self._final_fortress_preparing = False
        if pending and pending.get('run_id'):
            self.final_fortress_repository.record_event(pending['run_id'], 'abandoned')
        self.release_fortress_runtime()
        self.append_log(detail, error=True)
        self.refresh_final_fortress()
        if getattr(self, '_close_after_game', False):
            self.close_launcher()
            return
        messagebox.showerror(DISPLAY_NAME, str(exc), parent=self)

    def start_fortress_process(self, run):
        import os, subprocess, sys
        from randomizer.final_fortress.coop import result_identity

        if getattr(self, '_close_after_game', False):
            self.final_fortress_repository.record_event(run['id'], 'abandoned')
            self._final_fortress_preparing = False
            self.release_fortress_runtime()
            self.close_launcher()
            return
        name, transfers, slot = result_identity(run)
        watch = FinalFortressResultWatch(
            DEBUG_LOG,
            run['id'],
            run['plan'],
            player_name=name,
            initial_transfers=transfers,
            coop_slot=slot,
        )
        command = self.build_command()
        options = {}
        if sys.platform == 'win32':
            options['executable'] = str(GAME_ROOT / 'LaunchVinifera.dat')
            command = subprocess.list2cmdline(command)
        else:
            environment = os.environ.copy()
            environment['WINEDLLOVERRIDES'] = ';'.join(
                v for v in (environment.get('WINEDLLOVERRIDES', ''), 'ddraw=n,b') if v
            )
            options.update(env=environment, start_new_session=True)
        process = subprocess.Popen(command, cwd=GAME_ROOT, **options)
        self.active_game_process = process
        self._final_fortress_watch = watch
        self._final_fortress_preparing = False
        self._fortress_saved_events = set()
        self._fortress_saved_counts = None
        self.refresh_final_fortress()
        self.after(200, self._poll_final_fortress_game)

    def _poll_final_fortress_game(self):
        watch = self._final_fortress_watch
        process = self.active_game_process
        running = process.poll() is None
        outcome = watch.poll()
        if not running:
            outcome = watch.finish()
        events = [e for e in watch.events if not e.startswith('kills:')]
        if outcome:
            events.append(outcome)
        events.extend(e for e in watch.events if e.startswith('kills:'))
        events = [e for e in events if e not in self._fortress_saved_events]
        try:
            counts = watch.kill_counts if outcome in ('victory', 'defeat') else None
            if events or counts != self._fortress_saved_counts:
                state, changed = self.final_fortress_repository.record_events(
                    watch.run_id, events, kill_counts=counts
                )
                self._fortress_saved_events.update(events)
                self._fortress_saved_counts = counts
                if changed:
                    self.final_fortress_gems_var.set(f'Defensive Points: {state["gems"]}')
                    refresh_results(self, state['run'])
        except (ValueError, FinalFortressPersistenceError) as exc:
            self.append_log(str(exc), error=True)
        if (
            running
            and watch.ready_to_close
            and not getattr(watch, '_close_scheduled', False)
            and outcome in self._fortress_saved_events
            and watch.kill_counts == self._fortress_saved_counts
            and all(event in self._fortress_saved_events for event in watch.events)
        ):
            watch._close_scheduled = True
            self.after(2500, lambda: self._close_fortress_result(process, watch))
        if running or not watch.caught_up:
            self.after(10 if not watch.caught_up else 500, self._poll_final_fortress_game)
            return
        if not outcome:
            self.final_fortress_repository.record_event(watch.run_id, 'abandoned')
        self.active_game_process = None
        self._final_fortress_watch = None
        self.release_fortress_runtime()
        self.disconnect_fortress_coop()
        self.refresh_final_fortress()
        if getattr(self, '_close_after_game', False):
            self.close_launcher()

    def _close_fortress_result(self, process, watch):
        """Close only this captured process tree after its complete result is saved."""
        if (
            self.active_game_process is not process
            or self._final_fortress_watch is not watch
            or process.poll() is not None
        ):
            return
        import os
        import signal
        import subprocess
        import sys

        try:
            if sys.platform != 'win32':
                os.killpg(process.pid, signal.SIGTERM)
            else:
                subprocess.run(
                    ['taskkill', '/PID', str(process.pid), '/T', '/F'],
                    cwd=GAME_ROOT,
                    capture_output=True,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                )
        except OSError as exc:
            self.append_log('Could not close the completed Fortress game: ' + str(exc), error=True)

    def release_fortress_runtime(self):
        from randomizer.maps.assets import remove_generated_runtime_assets

        self.clear_power_runtime_types()
        remove_generated_runtime_assets()

    def close_launcher(self):
        if hasattr(self, '_final_fortress_preparing') and self._final_fortress_preparing:
            self._close_after_game = True
            self.cancel_fortress_preparation('Launcher closing.')
            if not self._final_fortress_preparing:
                return
            self.withdraw()
            return
        process = getattr(self, 'active_game_process', None)
        if not process or process.poll() is not None:
            self.disconnect_fortress_coop()
        return super().close_launcher()

    def select_final_fortress_perk(self, _event=None):
        from randomizer.final_fortress.perks import ranks, owned_rank, next_price
        from randomizer.final_fortress.perk_descriptions import rank_descriptions
        from randomizer.final_fortress.ui import show_perk_details

        selection = self.final_fortress_perks_tree.selection()
        state = self.final_fortress_state
        if not selection or state is None:
            show_perk_details(self, 'Select a perk to see its ranks.')
            self.final_fortress_refund_perk_button.configure(state='disabled')
            self.final_fortress_buy_perk_button.configure(state='disabled')
            self.final_fortress_toggle_perk_button.configure(state='disabled')
            return
        perk = next(
            entry for entry in self.final_fortress_config['perks'] if entry['id'] == selection[0]
        )
        country = state['preferences']['player_country']
        rank = owned_rank(state, perk['id'])
        price = next_price(perk, rank, country)
        busy = self.final_fortress_perks_locked()
        enabled = perk['id'] in state['selected_perks']
        details = rank_descriptions(perk, country, self.final_fortress_config)
        if 0 < rank <= len(ranks(perk)):
            refund = ranks(perk)[rank - 1]['gem_cost']
            details = f'Refund purchased rank {rank}: {refund} Defensive Points.\n\n' + details
        if rank > len(ranks(perk, country)):
            details = (
                f'{rank} ranks owned; this faction uses at most {len(ranks(perk, country))}. '
                'Refunding removes the highest purchased rank first.\n\n' + details
            )
        show_perk_details(self, details)
        self.final_fortress_refund_perk_button.configure(
            state='normal' if rank and not busy else 'disabled',
        )
        self.final_fortress_buy_perk_button.configure(
            text='Maximum rank' if price is None else 'Upgrade' if rank else 'Buy',
            state='disabled' if busy or price is None or state['gems'] < price else 'normal',
        )
        self.final_fortress_toggle_perk_button.configure(
            text='Disable perk' if enabled else 'Enable perk',
            state='normal' if rank and not busy else 'disabled',
        )

    def toggle_final_fortress_perk(self):
        if self.final_fortress_perks_locked():
            return
        selection = self.final_fortress_perks_tree.selection()
        if selection:
            key = selection[0]
            self._final_fortress_action(
                lambda: self.final_fortress_repository.select_perk(
                    key, key not in self.final_fortress_state['selected_perks']
                )
            )

    def select_final_fortress_challenge(self, _event=None):
        from randomizer.final_fortress.ui import show_challenge_details

        selection = self.final_fortress_challenge_tree.selection()
        if not selection or self.final_fortress_state is None:
            show_challenge_details(self, 'Select a modifier to see its full effect.')
            for button in (
                self.final_fortress_stack_max_button,
                self.final_fortress_challenge_enable_button,
                self.final_fortress_challenge_disable_button,
            ):
                button.configure(state='disabled')
            return
        preferences = self.final_fortress_state['preferences']
        entries = [
            entry for entry in self.final_fortress_config['challenges'] if entry['id'] in selection
        ]
        effects = [
            description(
                entry, min(maximum(entry), preferences['challenge_stacks'].get(entry['id'], 1))
            )
            for entry in entries
        ]
        show_challenge_details(
            self,
            (
                effects[0]
                if len(entries) == 1
                else f'{len(entries)} modifiers selected\n\n'
                + '\n\n'.join(
                    f'{label(entry)}: {effect}' for entry, effect in zip(entries, effects)
                )
            ),
        )
        process = getattr(self, 'active_game_process', None)
        busy = (
            self._final_fortress_preparing
            or self.fortress_coop_guest()
            or (process is not None and process.poll() is None)
        )
        self.final_fortress_stack_max_button.configure(
            state=(
                'normal'
                if not busy
                and any(
                    preferences['challenge_stacks'].get(entry['id'], 1) < maximum(entry)
                    for entry in entries
                )
                else 'disabled'
            )
        )
        self.final_fortress_challenge_enable_button.configure(
            state=(
                'normal'
                if not busy
                and any(entry['id'] not in preferences['selected_challenges'] for entry in entries)
                else 'disabled'
            )
        )
        self.final_fortress_challenge_disable_button.configure(
            state=(
                'normal'
                if not busy
                and any(entry['id'] in preferences['selected_challenges'] for entry in entries)
                else 'disabled'
            )
        )

    def on_final_fortress_challenge_click(self, event, *, additive=False):
        tree = self.final_fortress_challenge_tree
        self._final_fortress_challenge_drag = None
        if tree.identify_region(event.x, event.y) != 'cell':
            return
        key = tree.identify_row(event.y)
        column = tree.column(tree.identify_column(event.x), 'id')
        if not key:
            return
        selected = tree.selection()
        if column not in ('decrease', 'increase'):
            anchor = tree.focus() if event.state & 1 else key
            extending = additive or bool(event.state & 4)
            self._final_fortress_challenge_drag = (
                anchor or key,
                selected if extending else (),
                extending and key in selected,
                False,
            )
            if additive:
                self._final_fortress_challenge_click_selection = None
                tree.selection_toggle(key)
            else:
                # Let a normal click reduce even an all-row selection. Save
                # the group so a subsequent double-click can still toggle it.
                self._final_fortress_challenge_click_selection = (
                    (key, selected) if key in selected and not event.state & 5 else None
                )
                return
            tree.focus(key)
            tree.focus_set()
            return 'break'
        if key not in selected:
            tree.selection_set(key)
        self._final_fortress_challenge_click_selection = None
        tree.focus(key)
        tree.focus_set()
        self._set_final_fortress_challenge_stacks(
            delta=-1 if column == 'decrease' else 1, keys=(key,)
        )
        return 'break'

    def drag_final_fortress_challenges(self, event):
        drag = getattr(self, '_final_fortress_challenge_drag', None)
        if drag is None:
            return
        tree = self.final_fortress_challenge_tree
        if event.y < 0:
            tree.yview_scroll(-1, 'units')
        elif event.y >= tree.winfo_height():
            tree.yview_scroll(1, 'units')
        key = tree.identify_row(max(0, min(event.y, tree.winfo_height() - 1)))
        anchor, previous, removing, moved = drag
        children = tree.get_children()
        if key and anchor in children:
            if key == anchor and not moved:
                return 'break'
            self._final_fortress_challenge_drag = (anchor, previous, removing, True)
            self._final_fortress_challenge_click_selection = None
            first, last = sorted((children.index(anchor), children.index(key)))
            span = children[first : last + 1]
            chosen = set(previous) - set(span) if removing else set(previous) | set(span)
            tree.selection_set([child for child in children if child in chosen])
            tree.focus(key)
        return 'break'

    def end_final_fortress_challenge_drag(self, _event=None):
        self._final_fortress_challenge_drag = None

    def select_all_final_fortress_challenges(self, _event=None):
        tree = self.final_fortress_challenge_tree
        self._final_fortress_challenge_click_selection = None
        children = tree.get_children()
        tree.selection_set(children)
        if children and not tree.focus():
            tree.focus(children[0])
        tree.focus_set()
        self.select_final_fortress_challenge()
        return 'break'

    def set_final_fortress_challenges_enabled(self, enabled):
        self._update_final_fortress_challenges(enabled=enabled)

    def clear_final_fortress_challenge_selection(self, _event=None):
        tree = self.final_fortress_challenge_tree
        tree.selection_remove(tree.selection())
        self._final_fortress_challenge_drag = None
        self._final_fortress_challenge_click_selection = None
        self.select_final_fortress_challenge()
        return 'break'

    def change_final_fortress_challenge_stacks(self, delta):
        self._set_final_fortress_challenge_stacks(delta=delta)

    def max_final_fortress_challenge_stacks(self):
        self._set_final_fortress_challenge_stacks()

    def _set_final_fortress_challenge_stacks(self, *, delta=None, keys=None):
        self._update_final_fortress_challenges(delta=delta, max_stacks=delta is None, keys=keys)

    def _update_final_fortress_challenges(
        self, *, enabled=None, delta=None, max_stacks=False, keys=None
    ):
        selection = self.final_fortress_challenge_tree.selection() if keys is None else keys
        if not selection or self.final_fortress_state is None:
            return
        preferences = self.final_fortress_state['preferences']
        choices = {}
        for entry in self.final_fortress_config['challenges']:
            key = entry['id']
            if key not in selection:
                continue
            limit = maximum(entry)
            current = min(limit, preferences['challenge_stacks'].get(key, 1))
            selected = key in preferences['selected_challenges']
            stacks = limit if max_stacks else min(limit, max(1, current + (delta or 0)))
            chosen = selected if enabled is None else enabled
            if stacks != current or chosen != selected:
                choices[key] = (chosen, stacks)
        if choices:
            self._final_fortress_action(
                lambda: self.final_fortress_repository.select_challenges(
                    self.final_fortress_config, choices
                )
            )

    def toggle_final_fortress_challenge(self, event=None):
        tree = self.final_fortress_challenge_tree
        if event is not None and getattr(event, 'num', None) == 1:
            if tree.identify_region(event.x, event.y) != 'cell':
                return 'break'
            column = tree.column(tree.identify_column(event.x), 'id')
            if column in ('decrease', 'increase'):
                # Tk dispatches the second rapid click as Double-1. Keep it
                # an adjustment, never a modifier enable/disable gesture.
                return self.on_final_fortress_challenge_click(event)
            key = tree.identify_row(event.y)
            if not key:
                return 'break'
            previous = getattr(self, '_final_fortress_challenge_click_selection', None)
            if previous and previous[0] == key:
                tree.selection_set(previous[1])
            self._final_fortress_challenge_click_selection = None
            if key not in tree.selection():
                tree.selection_set(key)
        if not tree.selection() or self.final_fortress_state is None:
            return 'break'
        preferences = self.final_fortress_state['preferences']
        # A mixed group enables together; an entirely enabled group disables.
        self.set_final_fortress_challenges_enabled(
            any(key not in preferences['selected_challenges'] for key in tree.selection())
        )
        return 'break'

    def on_final_fortress_difficulty_changed(self, _event=None):
        difficulty = self.final_fortress_difficulty_choices[
            self.final_fortress_difficulty_var.get()
        ]
        self._final_fortress_action(
            lambda: self.final_fortress_repository.set_difficulty(difficulty)
        )

    def on_final_fortress_wave_multiplier_changed(self, _event=None):
        multiplier = self.final_fortress_wave_multiplier_choices[
            self.final_fortress_wave_multiplier_var.get()
        ]
        self._final_fortress_action(
            lambda: self.final_fortress_repository.set_wave_multiplier(multiplier)
        )
