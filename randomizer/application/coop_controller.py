"""Experimental host-authoritative native co-op Grid/Shop integration."""

import copy
import hashlib
import json
import logging
import queue
import re
import secrets
import subprocess
import time
import traceback
import tkinter as tk
from tkinter import messagebox, ttk

from randomizer.config.player import save_config
from randomizer.coop import feature
from randomizer.coop.catalogue import discover_coop_missions, eligible, validate_pool
from randomizer.coop.privacy import redact_connection_details
from randomizer.coop.lobby import Lobby, pack, unpack
from randomizer.coop.loadouts import contribution, normalize_contribution, personal_shop_run, personal_upgrade_levels, PERSONAL_UPGRADES
from randomizer.coop.maps import prepare_map, safe_settings, supported_reward, verify_dependencies
from randomizer.coop.persistence import COOP_STATE_PATH, SharedShopRepository
from randomizer.coop.shop import gameplay_document, mission_view, sync_personal_run
from randomizer.coop.spawn import spawn_data
from randomizer.coop.victory import ScoreLog
from randomizer.core.paths import DEBUG_LOG, GAME_EXE, GAME_LAUNCHER_EXE, GAME_ROOT, SPAWN_INI, SPAWN_MAP_INI
from randomizer.core.paths import LAUNCHER_LOG
from randomizer.core.diagnostics import event as log_event
from randomizer.core.storage import atomic_write_json, read_json_object
from randomizer.shop.model import RunStatus, ShopRewardType
from randomizer.shop.persistence import ShopPersistenceError, ShopRepository
from randomizer.shop.service import ShopProgressionService
from randomizer.shop.state import normalize_shop_run
from randomizer.shop.transitions import ShopTransitionError


SAFE_SHOP_MODIFIERS = frozenset({
    'greedy', 'veteran_economy', 'poor_logistics', 'generous_command',
    'blind_choice', 'no_safety_net', 'war_economy', 'narrow_intelligence',
    'liquid_assets', 'low_tech_war', 'blockbuster_special',
})


class CoopController:
    def initialize_coop(self):
        self.coop_mode_var = tk.BooleanVar(value=feature.enabled(self.config))
        self.coop_player_count_var = tk.StringVar(value=str(self.config.get('coop_player_count', 2)))
        self._coop_lobby = None
        self._coop_pending_launch = None
        self._coop_restore_error = ''
        self._coop_controls = []
        self._coop_disabled_widgets = {}
        self._coop_loadouts = {}
        self._coop_player_selections = {}
        self._coop_building_map = False

    def coop_enabled(self):
        return feature.enabled(getattr(self, 'config', {}))

    def coop_guest_connected(self):
        lobby = getattr(self, '_coop_lobby', None)
        return bool(lobby and lobby.role == 'guest')

    def coop_count(self):
        return feature.player_count(self.config.get('coop_player_count', 2))

    def build_coop_controls(self, parent, row):
        if not feature.COOP_FEATURE_ENABLED:
            return
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        toggle = ttk.Checkbutton(frame, text='Co-op mode (experimental)', variable=self.coop_mode_var, command=self.on_coop_mode_changed)
        toggle.grid(row=0, column=0, sticky='w')
        ttk.Label(frame, text='Players').grid(row=0, column=1, padx=(12, 4))
        count = ttk.Combobox(frame, textvariable=self.coop_player_count_var, values=('2', '3', '4'), state='readonly', width=3)
        count.grid(row=0, column=2)
        count.bind('<<ComboboxSelected>>', self.on_coop_mode_changed)
        connect = ttk.Button(frame, text='Co-op Connection…', command=self.open_coop_dialog)
        connect.grid(row=1, column=0, sticky='w', pady=(5, 0))
        ttk.Label(frame, text='Grid rewards are shared. Shop players keep their own Ore, Gems, purchases and loadouts; host controls missions. Powers/enemy effects disabled.', wraplength=360, style='Muted.TLabel').grid(row=2, column=0, columnspan=3, sticky='w')
        self._coop_controls.append((toggle, count, connect))

    def refresh_coop_controls(self):
        if not feature.COOP_FEATURE_ENABLED:
            return
        from ._dependencies import CAMPAIGN_FILTERS, PROGRESSION_MODES
        cooperative = self.coop_enabled()
        campaigns = ('All Campaigns', 'GDI', 'Nod', 'Allies', 'Soviet') if cooperative else CAMPAIGN_FILTERS
        self.campaign_combo.configure(values=campaigns)
        if self.campaign_var.get() not in campaigns:
            self.campaign_var.set(campaigns[0])
        modes = ('Grid Mode', 'Shop Mode') if cooperative else PROGRESSION_MODES
        for name in ('progression_mode_combo', 'shop_progression_mode_combo'):
            widget = getattr(self, name, None)
            if widget:
                widget.configure(values=modes)
        if cooperative and self.progression_mode_var.get() not in modes:
            self.progression_mode_var.set('Grid Mode')
        process = getattr(self, 'active_game_process', None)
        run = getattr(self, 'shop_run', None)
        locked = bool(self._coop_lobby or (process and process.poll() is None)
                      or self.shop_launch_active() or self.gameplay_settings_locked()
                      or self.busy_depth)
        active_shop_run = bool(run and run.status is RunStatus.ACTIVE)
        for toggle, count, connect in self._coop_controls:
            toggle.configure(state='disabled' if locked else 'normal')
            count.configure(state='disabled' if locked or active_shop_run or (self.state and self.coop_enabled()) else 'readonly')
            connect.configure(state='normal' if self.coop_enabled() else 'disabled')
        if self.coop_enabled():
            for modifier_id, variable in getattr(self, 'shop_modifier_vars', {}).items():
                if modifier_id not in SAFE_SHOP_MODIFIERS:
                    variable.set(False)
        for name in ('primary_launch_button', 'compact_launch_button'):
            button = getattr(self, name, None)
            if button:
                button.configure(text='Suggest Mission' if self.coop_guest_connected() else 'Launch Selected Mission')
        for name in ('debug_complete_button', 'compact_complete_button'):
            button = getattr(self, name, None)
            if button:
                button.configure(text='Record Co-op Victory' if self.coop_enabled() else 'Mark Mission Complete')
        if self.coop_guest_connected():
            for card in getattr(self, 'shop_mission_cards', ()):
                for key in ('reroll_button', 'ease_button'):
                    card[key].configure(state='disabled')
                card['launch_button'].configure(text='Suggest Mission')
            for name in ('debug_complete_button', 'compact_complete_button', 'shop_debug_complete_button',
                         'shop_start_endless_button', 'shop_give_up_button',
                         'shop_reset_profile_button', 'shop_ap_purchase_button'):
                widget = getattr(self, name, None)
                if widget:
                    self._coop_disabled_widgets.setdefault(widget, widget.cget('state'))
                    widget.configure(state='disabled')
            start = getattr(self, 'shop_setup_start_button', None)
            host = getattr(self, '_coop_host_shop_run', None)
            local = self.shop_repository.load_run()
            if start:
                start.configure(state='normal' if (
                    self._coop_lobby.connected and host and host.status is RunStatus.ACTIVE
                    and host.stage == 1 and not host.completed_missions
                    and (local is None or local.status is not RunStatus.ACTIVE)
                    and not self._coop_pending_launch and not self.shop_launch_active()
                ) else 'disabled')
        elif self._coop_disabled_widgets:
            for widget, state in self._coop_disabled_widgets.items():
                if widget.winfo_exists():
                    widget.configure(state=state)
            self._coop_disabled_widgets.clear()

    def on_coop_mode_changed(self, *_args):
        previous = self.coop_enabled()
        requested = bool(self.coop_mode_var.get())
        process = getattr(self, 'active_game_process', None)
        run = getattr(self, 'shop_run', None)
        if (not feature.COOP_FEATURE_ENABLED or self._coop_lobby or self.busy_depth
                or self.gameplay_settings_locked() or (process and process.poll() is None)
                or self.shop_launch_active()):
            self.coop_mode_var.set(previous)
            self.coop_player_count_var.set(str(self.config.get('coop_player_count', 2)))
            messagebox.showwarning('Co-op settings', 'Finish the active run/game or disconnect before changing co-op settings.', parent=self)
            return
        count = feature.player_count(self.coop_player_count_var.get())
        if previous and self.state and count != self.coop_count():
            self.coop_player_count_var.set(str(self.coop_count()))
            messagebox.showwarning('Co-op settings', 'Start a new co-op Grid before changing player count, or switch to solo first.', parent=self)
            return
        if run and run.status is RunStatus.ACTIVE:
            if requested == previous:
                self.coop_player_count_var.set(str(self.coop_count()))
                messagebox.showwarning('Co-op settings', 'Finish the active Shop run before changing player count.', parent=self)
                return
            mode = 'co-op' if requested else 'solo'
            if not messagebox.askyesno(
                'End Shop Run?',
                f'Switching to {mode} will end your active Shop run.\n\n'
                'Run Ore and run purchases will be abandoned. '
                'Gems and permanent unlocks are kept.\n\nContinue?',
                default=messagebox.NO,
                parent=self,
            ):
                self.coop_mode_var.set(previous)
                self.coop_player_count_var.set(str(self.coop_count()))
                return
            try:
                self.shop_service.give_up_run()
            except (ShopTransitionError, ShopPersistenceError, OSError) as exc:
                self.coop_mode_var.set(previous)
                self.coop_player_count_var.set(str(self.coop_count()))
                messagebox.showerror('Co-op settings', f'Cannot end the active Shop run: {exc}', parent=self)
                return
        self.config.update({'coop_mode': requested, 'coop_player_count': count})
        self.state = self.load_state()
        if self.state:
            self.campaign_var.set(self.state.get('campaign_filter', 'All Campaigns'))
        self._select_coop_shop_repository()
        self.migrate_state()
        self.apply_missions(self.load_missions())
        self.grid_render_signature = None
        self.refresh_progress_view()
        self.refresh_shop_mode()
        self.refresh_coop_controls()
        save_config(self.config)

    def load_state(self):
        if not self.coop_enabled():
            self._coop_restore_error = ''
            return super().load_state()
        if not COOP_STATE_PATH.exists():
            self._coop_restore_error = ''
            return {}
        loaded = {}
        try:
            loaded = read_json_object(COOP_STATE_PATH)
            if loaded.get('coop_mode') is not True or loaded.get('coop_player_count') != self.coop_count():
                raise ValueError('Saved Grid uses a different co-op player count.')
            if not isinstance(loaded.get('coop_metadata'), dict) or not loaded.get('mission_order'):
                raise ValueError('Saved cooperative Grid lacks native eligibility metadata.')
            validate_pool(discover_coop_missions(GAME_ROOT), loaded['mission_order'], self.coop_count(), loaded['coop_metadata'])
            self._coop_restore_error = ''
        except (ValueError, OSError) as exc:
            self._coop_restore_error = 'Cannot restore experimental Grid: ' + str(exc)
        return loaded

    def migrate_state(self):
        if self.coop_enabled() and self._coop_restore_error:
            return
        return super().migrate_state()

    def sync_state_mission_objectives(self):
        if self.coop_enabled() and self._coop_restore_error:
            return
        return super().sync_state_mission_objectives()

    def save_state(self):
        if self.coop_guest_connected():
            return
        if not self.state.get('coop_mode'):
            return super().save_state()
        feature.require_enabled()
        if self._coop_restore_error:
            return
        for key in ('_active_reward_settings_cache', '_canonical_earned_rewards_cache', '_unlock_dashboard_sources_cache', '_configured_reward_pool_cache'):
            self.__dict__.pop(key, None)
        self._enemy_buffs_view_dirty = True
        atomic_write_json(COOP_STATE_PATH, self.state, indent=None)
        self.coop_publish_state()

    def load_missions(self):
        if self.coop_enabled():
            catalogue = discover_coop_missions(GAME_ROOT, include_excluded=True)
            self._coop_catalogue_exclusions = [(mission['code'], mission['coop_excluded_reason'])
                                              for mission in catalogue if mission['coop_excluded_reason']]
            return eligible(catalogue, self.coop_count())
        return super().load_missions()

    def refresh_missions(self):
        if self.coop_enabled():
            self.apply_missions(self.load_missions())
            return
        return super().refresh_missions()

    def apply_missions(self, missions):
        result = super().apply_missions(missions)
        if self.coop_enabled():
            for code, reason in getattr(self, '_coop_catalogue_exclusions', ()):
                self.append_log(f'Co-op excluded {code}: {reason}')
            try:
                if self._coop_restore_error:
                    raise ValueError(self._coop_restore_error)
                self.validate_coop_run()
                self._coop_restore_error = ''
            except ValueError as exc:
                self._coop_restore_error = str(exc)
                self.append_log(str(exc), error=True)
                messagebox.showerror('Invalid experimental co-op run', str(exc), parent=self)
            self.refresh_coop_controls()
        return result

    def validate_coop_run(self):
        feature.require_enabled()
        run = getattr(self, 'shop_run', None) if self.shop_mode_selected() else None
        document = run.reward_settings if run is not None else self.state
        if not document:
            return
        codes = run.eligible_mission_codes if run else document.get('mission_order', ())
        self._validate_coop_document(document, codes)

    def _validate_coop_document(self, document, codes):
        if document.get('coop_mode') is not True or document.get('coop_player_count') != self.coop_count():
            raise ValueError('Saved run is not compatible with the selected co-op player count.')
        hashes = document.get('coop_metadata')
        if not codes or not isinstance(hashes, dict):
            raise ValueError('Saved co-op run lacks native mission eligibility metadata.')
        validate_pool(self.missions, codes, self.coop_count(), hashes)

    def initialize_shop_controller(self):
        super().initialize_shop_controller()
        if self.coop_enabled():
            self._select_coop_shop_repository()

    def _select_coop_shop_repository(self):
        self.shop_repository = SharedShopRepository(self.coop_publish_state, self._guard_coop_shop_write) if self.coop_enabled() else ShopRepository()
        self.shop_service = ShopProgressionService(self.shop_repository, loadout=self.effective_shop_run)
        self.shop_profile, self.shop_run = self.shop_repository.load()

    def _guard_coop_shop_write(self):
        if self._coop_pending_launch or self._coop_building_map:
            raise ShopTransitionError('Wait for co-op preparation to finish before changing the Shop run.')
        if self.coop_guest_connected() and not self._coop_lobby.connected:
            raise ShopTransitionError('Reconnect or disconnect before changing your co-op Shop run.')

    def _own_coop_loadout(self):
        repository = getattr(self, '_coop_personal_repository', self.shop_repository)
        profile = repository.load_profile()
        run = repository.load_run()
        selected = (run.selected_permanent_units if run and run.status is RunStatus.ACTIVE
                    else self._selected_loadout_reward_ids())
        selected = [item for item in selected if item in profile.permanent_unit_unlocks]
        return contribution(profile, selected, run)

    def effective_shop_run(self, run):
        if not self.coop_enabled():
            return run
        slot = getattr(self, '_coop_launch_loadout_slot', None)
        loadout = self._coop_loadouts[slot] if slot is not None else self._own_coop_loadout()
        if slot is not None and run is not None:
            run = mission_view(normalize_shop_run(loadout['run']), run)
        return personal_shop_run(run, loadout)

    def _shop_context_run(self):
        return self.effective_shop_run(super()._shop_context_run())

    def active_launch_rewards(self):
        rewards = list(super().active_launch_rewards())
        if self.coop_enabled() and self.shop_launch_active():
            slot = getattr(self, '_coop_launch_loadout_slot', None)
            if slot is None:
                return rewards
            levels = personal_upgrade_levels(self._coop_loadouts[slot])
            # ShopController adds the local profile's credit upgrade. Replace
            # only that contribution, leaving shared credit rewards intact.
            remaining = self.shop_profile.upgrade_level('mission_starting_credits')
            for index in range(len(rewards) - 1, -1, -1):
                if remaining and rewards[index].get('name') == 'Starting Credits +1,000':
                    rewards.pop(index)
                    remaining -= 1
            from randomizer.shop.catalogue import canonical_reward_for_id
            rewards.extend(canonical_reward_for_id('Starting Credits +1,000')
                           for _ in range(levels['mission_starting_credits']))
        return rewards

    def active_reward_settings(self):
        settings = super().active_reward_settings()
        if self.coop_enabled() and self._shop_context_run() is not None:
            slot = getattr(self, '_coop_launch_loadout_slot', None)
            loadout = self._coop_loadouts[slot] if slot is not None else self._own_coop_loadout()
            levels = personal_upgrade_levels(loadout)
            settings = dict(settings)
            settings['shop_global_buff_levels'] = {
                buff_type: levels[upgrade_id]
                for upgrade_id, buff_type in PERSONAL_UPGRADES.items() if buff_type
            }
        return settings

    def refresh_shop_mode(self, *_args):
        result = super().refresh_shop_mode(*_args)
        if hasattr(self, '_coop_controls'):
            self.refresh_coop_controls()
        return result

    def refresh_setting_states(self):
        result = super().refresh_setting_states()
        if self.coop_enabled():
            for name in ('include_superweapon_rewards_check', 'include_aid_power_rewards_check',
                         'include_power_buff_rewards_check', 'buff_allied_helpers_check',
                         'shop_buff_allied_helpers_check'):
                widget = getattr(self, name, None)
                if widget:
                    widget.configure(state='disabled')
            for widget in getattr(self, 'arsenal_power_count_spinboxes', {}).values():
                widget.configure(state='disabled')
        return result

    def configured_manual_starting_rewards(self):
        rewards = super().configured_manual_starting_rewards()
        return [reward for reward in rewards if supported_reward(reward)] if self.coop_enabled() else rewards

    def apply_portable_settings(self, config):
        config = dict(config)
        config.pop('coop_feature_enabled', None)
        config['coop_mode'] = feature.enabled(config)
        config['coop_player_count'] = feature.player_count(config.get('coop_player_count', 2))
        changed = (config['coop_mode'], config['coop_player_count']) != (self.coop_enabled(), self.coop_count())
        run = getattr(self, 'shop_run', None)
        if changed and (self._coop_lobby or self.busy_depth or (run and run.status is RunStatus.ACTIVE)):
            messagebox.showwarning('Co-op settings', 'Disconnect and finish the active run before importing different co-op settings.', parent=self)
            return
        result = super().apply_portable_settings(config)
        self.coop_mode_var.set(self.coop_enabled())
        self.coop_player_count_var.set(str(self.coop_count()))
        if changed:
            self.state = self.load_state()
            self._select_coop_shop_repository()
            self.apply_missions(self.load_missions())
        return result

    def current_reward_settings(self):
        settings = super().current_reward_settings()
        return safe_settings(settings, self.coop_count()) if self.coop_enabled() else settings

    def reward_pool_for_code(self, code):
        rewards = super().reward_pool_for_code(code)
        return [reward for reward in rewards if supported_reward(reward)] if self.coop_enabled() else rewards

    def build_seed_generation(self, options):
        result = super().build_seed_generation(options)
        if self.coop_enabled():
            result['state'].update({'coop_mode': True, 'coop_player_count': self.coop_count(),
                                    'coop_metadata': {mission['code']: mission['coop_metadata_hash'] for mission in options['seed_missions']}})
        return result

    def seed_generation_options_from_settings(self):
        if self.coop_enabled() and self.progression_mode_var.get() != 'Grid Mode':
            messagebox.showwarning('Experimental co-op', 'Choose Grid Mode or Shop Mode for co-op.', parent=self)
            return None
        return super().seed_generation_options_from_settings()

    def finish_seed_generation(self, result):
        if self.coop_enabled():
            self._coop_restore_error = ''
        super().finish_seed_generation(result)
        if self.coop_enabled():
            self.refresh_coop_controls()
            self.coop_publish_state()

    def shop_reward_settings_for_new_run(self):
        settings = super().shop_reward_settings_for_new_run()
        if self.coop_enabled():
            settings = safe_settings(settings, self.coop_count())
            settings['coop_metadata'] = {mission['code']: mission['coop_metadata_hash'] for mission in self.missions}
        return settings

    def _shop_run_mission_pool(self, run=None):
        missions = super()._shop_run_mission_pool(run)
        if self.coop_enabled():
            active = run or getattr(self, 'shop_run', None)
            if active and active.status is RunStatus.ACTIVE:
                validate_pool(self.missions, active.eligible_mission_codes, self.coop_count(), active.reward_settings.get('coop_metadata', {}))
            return eligible(missions, self.coop_count())
        return missions

    def _repair_shop_mission_offers(self, run):
        if self.coop_guest_connected() or (self.coop_enabled() and getattr(self, '_coop_restore_error', '')):
            return run
        return super()._repair_shop_mission_offers(run)

    def _shop_entry_available(self, entry, run=None, *, stock=False):
        if self.coop_enabled() and entry.reward_type in {ShopRewardType.POWER_ACCESS, ShopRewardType.POWER_BUFF}:
            return False
        return super()._shop_entry_available(entry, run, stock=stock)

    def _shop_modifier_toggled(self, modifier_id):
        if self.coop_enabled() and modifier_id not in SAFE_SHOP_MODIFIERS:
            self.shop_modifier_vars[modifier_id].set(False)
            messagebox.showwarning('Experimental co-op', 'This gameplay modifier has no audited co-op implementation.', parent=self)
            return
        return super()._shop_modifier_toggled(modifier_id)

    def launch_shop_mission(self, index):
        if self.coop_guest_connected():
            run = self.shop_run
            if run and 0 <= index < len(run.mission_offers) and self._coop_lobby.connected:
                self._publish_coop_selection(run.mission_offers[index].mission_code)
            return
        return super().launch_shop_mission(index)

    def launch_selected_shop_mission(self):
        if self.coop_guest_connected():
            run = self.shop_repository.load_run()
            if run and run.selected_mission_code:
                self._publish_coop_selection(run.selected_mission_code)
            return
        if self.coop_enabled():
            try:
                lobby = self._coop_lobby
                if not lobby or not lobby.connected:
                    raise ValueError('Connect every configured player before committing the Shop mission.')
                host = self.shop_repository.load_run()
                for slot in range(self.coop_count()):
                    loadout = self._own_coop_loadout() if slot == 0 else self._coop_loadouts.get(slot)
                    if loadout is None:
                        raise ValueError('Wait for every player to share their personal Shop run.')
                    mission_view(normalize_shop_run(loadout['run']), host)
            except (ValueError, KeyError) as exc:
                self._set_shop_message(exc, error=True)
                messagebox.showwarning('Co-op Shop not ready', str(exc), parent=self)
                return
        return super().launch_selected_shop_mission()

    def reroll_shop_mission(self, index):
        if self.coop_guest_connected():
            return
        return super().reroll_shop_mission(index)

    def ease_shop_mission(self, index):
        if self.coop_guest_connected():
            return
        return super().ease_shop_mission(index)

    def unlock_shop_preconditions(self, index):
        if self.coop_guest_connected():
            return
        return super().unlock_shop_preconditions(index)

    def give_up_shop_run(self):
        if self.coop_guest_connected():
            return
        return super().give_up_shop_run()

    def start_shop_endless(self):
        if self.coop_guest_connected():
            return
        return super().start_shop_endless()

    def start_shop_run(self):
        if self.coop_guest_connected():
            host = getattr(self, '_coop_host_shop_run', None)
            if (host is None or host.status is not RunStatus.ACTIVE
                    or host.stage != 1 or host.completed_missions):
                self._set_shop_message('Join at stage 1, or reconnect with your matching personal Shop save.', error=True)
                return
            self.seed_var.set(host.seed)
            for key, variable in self.shop_modifier_vars.items():
                variable.set(key in host.modifiers)
        if self.coop_enabled():
            if self.archipelago_run_active():
                raise ShopTransitionError('Co-op and Archipelago cannot share a run.')
            for modifier_id, variable in self.shop_modifier_vars.items():
                if modifier_id not in SAFE_SHOP_MODIFIERS:
                    variable.set(False)
        result = super().start_shop_run()
        if self.coop_guest_connected():
            try:
                self._sync_coop_shop_run(self._coop_host_shop_run)
            except (ValueError, ShopTransitionError) as exc:
                self._set_shop_message(exc, error=True)
                messagebox.showwarning('Co-op Shop setup', str(exc), parent=self)
            self.refresh_shop_mode()
            self.coop_publish_state()
        return result

    def gameplay_settings_locked(self):
        return self.coop_guest_connected() or super().gameplay_settings_locked()

    def connect_archipelago(self):
        if self.coop_enabled():
            messagebox.showwarning('Experimental co-op', 'Switch to solo before connecting Archipelago.', parent=self)
            return
        return super().connect_archipelago()

    def save_archipelago_yaml(self):
        if self.coop_enabled():
            messagebox.showwarning('Experimental co-op', 'Switch to solo before exporting an Archipelago YAML.', parent=self)
            return
        return super().save_archipelago_yaml()

    def on_new_seed(self):
        if self.coop_guest_connected() or getattr(self, '_coop_pending_launch', None):
            return
        process = getattr(self, 'active_game_process', None)
        if self.coop_enabled() and process and process.poll() is None:
            messagebox.showwarning('Experimental co-op', 'Close the active game before generating a new run.', parent=self)
            return
        return super().on_new_seed()

    def on_launch_selected(self):
        if self.coop_guest_connected():
            mission = self.selected_mission()
            if mission and self._coop_lobby.connected:
                self._publish_coop_selection(mission['code'])
            return
        return super().on_launch_selected()

    def unlock_mission_check(self, code, check_id, source):
        if self.coop_guest_connected() or getattr(self, '_coop_pending_launch', None):
            return False
        result = super().unlock_mission_check(code, check_id, source)
        if self.coop_enabled():
            self.coop_publish_state()
        return result

    def record_failed_mission_attempt(self, code, source):
        if self.coop_guest_connected():
            return False
        result = super().record_failed_mission_attempt(code, source)
        if self.coop_enabled():
            self.coop_publish_state()
        return result

    def on_debug_mark_complete(self):
        if self.coop_guest_connected():
            return
        if self.coop_enabled() and not messagebox.askyesno('Record Co-op Victory', 'Record a confirmed team victory for this mission?', parent=self):
            return
        return super().on_debug_mark_complete()

    def coop_publish_state(self):
        lobby = getattr(self, '_coop_lobby', None)
        if (not lobby or not lobby.connected or self._coop_pending_launch
                or getattr(self, '_coop_applying_state', False)):
            return
        if lobby.role == 'guest':
            try:
                loadout = self._own_coop_loadout()
                if loadout == getattr(self, '_coop_last_shared_loadout', None):
                    return
                lobby.send({'type': 'loadout', 'loadout': loadout})
                self._coop_last_shared_loadout = copy.deepcopy(loadout)
            except (OSError, ValueError) as exc:
                self.append_log('Co-op loadout sharing failed: ' + self._coop_safe_message(exc), error=True)
            return
        _profile, run = self.shop_repository.load()
        if run and run.reward_settings.get('coop_mode'):
            self._validate_coop_document(run.reward_settings, run.eligible_mission_codes)
        self._coop_loadouts[0] = self._own_coop_loadout()
        selected = self.selected_mission_code()
        if selected in self._mission_by_code:
            self._coop_player_selections[0] = selected
        snapshot = {'state': self.state, 'loadout_protocol': 3,
                    'loadouts': {str(slot): loadout for slot, loadout in self._coop_loadouts.items()},
                    'shop_run': run.to_dict() if run else None,
                    'mode': self.progression_mode_var.get(), 'count': self.coop_count(),
                    'selections': {str(slot): code for slot, code in self._coop_player_selections.items()},
                    'selected': self.selected_mission_code(), 'difficulty': self.difficulty_var.get()}
        try:
            lobby.send({'type': 'state', 'snapshot': pack(json.dumps(snapshot).encode())})
        except (OSError, ValueError) as exc:
            self.append_log('Co-op state sharing failed: ' + self._coop_safe_message(exc), error=True)

    def _publish_coop_selection(self, code):
        lobby = getattr(self, '_coop_lobby', None)
        if (not lobby or not lobby.connected or code not in self._mission_by_code
                or getattr(self, '_coop_applying_state', False)
                or getattr(self, '_coop_applying_selection', False)):
            return
        self._coop_player_selections[lobby.slot] = code
        try:
            message = {'type': 'suggest' if lobby.role == 'guest' else 'select', 'code': code}
            if lobby.role == 'host':
                message['selections'] = {str(slot): selected for slot, selected in self._coop_player_selections.items()}
            lobby.send(message)
            self.refresh_grid_tiles()
        except (OSError, ValueError) as exc:
            self.append_log('Co-op mission sync failed: ' + self._coop_safe_message(exc), error=True)

    def _apply_coop_selections(self, selections):
        if (not isinstance(selections, dict)
                or not set(selections) <= {str(slot) for slot in range(self.coop_count())}
                or any(code not in self._mission_by_code for code in selections.values())):
            raise ValueError('Invalid cooperative mission selections.')
        self._coop_player_selections = {int(slot): code for slot, code in selections.items()}

    def _select_coop_host_mission(self, code):
        if code not in self._mission_by_code:
            raise ValueError('Host selected a mission outside the native catalogue.')
        self._coop_applying_selection = True
        try:
            index = next(index for index, mission in enumerate(self.missions) if mission['code'] == code)
            self.selected_index.set(index)
            self.refresh_progress_view()
        finally:
            self._coop_applying_selection = False

    def refresh_grid_tiles(self, mission_codes=None):
        result = super().refresh_grid_tiles(mission_codes)
        if not self.coop_enabled() or not getattr(self, '_coop_lobby', None):
            return result
        for code, widgets in self.grid_tile_widgets.items():
            if mission_codes is not None and code not in mission_codes:
                continue
            if widgets['body'].cget('text') == '?':
                continue
            markers = ['Host selected' if slot == 0 else f'Player {slot + 1} ping'
                       for slot, selected in sorted(self._coop_player_selections.items()) if selected == code]
            if markers:
                widgets['body'].configure(text=widgets['body'].cget('text') + '\n' + ' · '.join(markers))
        return result

    def open_coop_dialog(self):
        if not self.coop_enabled():
            return
        old = getattr(self, '_coop_dialog', None)
        if old and old.winfo_exists():
            old.lift()
            return
        dialog = tk.Toplevel(self)
        self._coop_dialog = dialog
        dialog.title('ZeroTier co-op connection')
        dialog.transient(self)
        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill='both', expand=True)
        if not hasattr(self, '_coop_role'):
            self._coop_role = tk.StringVar(value='Host')
            self._coop_name = tk.StringVar(value=self.config.get('player_name', 'Commander')[:15])
            self._coop_address = tk.StringVar(value='')
            self._coop_host_pairing = tk.StringVar(value=secrets.token_hex(12))
            self._coop_pairing = tk.StringVar(value='')
            self._coop_status = tk.StringVar(value='Disconnected')
        self._coop_show_details = tk.BooleanVar(value=False)
        self._coop_private_entries = []
        self._coop_connection_entries = []
        frame.columnconfigure(1, weight=1)
        for row, (label, variable) in enumerate((('Role', self._coop_role), ('Player name', self._coop_name), ('Host ZeroTier IPv4', self._coop_address), ('Pairing code', self._coop_pairing))):
            field_label = ttk.Label(frame, text=label)
            field_label.grid(row=row, column=0, sticky='w', padx=(0, 8))
            widget = ttk.Combobox(frame, textvariable=variable, values=('Host', 'Join'), state='readonly') if row == 0 else ttk.Entry(frame, textvariable=variable, width=30)
            widget.grid(row=row, column=1, pady=3, sticky='ew')
            self._coop_connection_entries.append(widget)
            if variable is self._coop_role:
                widget.bind('<<ComboboxSelected>>', self._on_coop_role_changed)
            elif variable is self._coop_address:
                self._coop_address_widgets = (field_label, widget)
            elif variable is self._coop_pairing:
                self._coop_guest_code_entry = widget
                self._coop_host_code_label = ttk.Label(frame, textvariable=self._coop_host_pairing)
                self._coop_host_code_label.grid(row=row, column=1, pady=3, sticky='w')
            if variable is self._coop_address or variable is self._coop_pairing:
                widget.configure(show='*')
                self._coop_private_entries.append(widget)
        self._coop_show_details_check = ttk.Checkbutton(
            frame, variable=self._coop_show_details, command=self._toggle_coop_details)
        self._coop_show_details_check.grid(row=4, column=0, columnspan=2, sticky='w', pady=(6, 0))
        ttk.Button(frame, text='Copy pairing code', command=self._copy_coop_pairing).grid(row=5, column=0, sticky='w', pady=5)
        self._coop_connect_button = ttk.Button(frame, text='Connect', command=self.connect_coop)
        self._coop_connect_button.grid(row=6, column=0, pady=8)
        ttk.Button(frame, text='Disconnect', command=self.disconnect_coop).grid(row=6, column=1)
        ttk.Label(frame, textvariable=self._coop_status, wraplength=430).grid(row=7, column=0, columnspan=2)
        ttk.Button(frame, text='Show connection log', command=self._show_coop_log).grid(
            row=8, column=0, columnspan=2, sticky='w', pady=(8, 0))
        dialog.protocol('WM_DELETE_WINDOW', self._close_coop_dialog)
        self._refresh_coop_connection_fields()

    def _hide_coop_details(self):
        if hasattr(self, '_coop_show_details'):
            self._coop_show_details.set(False)
        for entry in getattr(self, '_coop_private_entries', ()):
            if entry.winfo_exists():
                entry.configure(show='*')

    def _toggle_coop_details(self):
        if not self._coop_show_details.get():
            self._hide_coop_details()
            return
        for entry in self._coop_private_entries:
            entry.configure(show='')

    def _close_coop_dialog(self):
        self._hide_coop_details()
        self._coop_dialog.destroy()

    def _copy_coop_pairing(self):
        self._hide_coop_details()
        self.clipboard_clear()
        self.clipboard_append(self._coop_pairing_code())

    def _coop_pairing_code(self):
        return (self._coop_host_pairing if self._coop_role.get() == 'Host' else self._coop_pairing).get()

    def _on_coop_role_changed(self, *_args):
        self._refresh_coop_connection_fields()

    def _record_coop_log(self, message, error=False):
        message = self._coop_safe_message(message)
        self.append_log(message, error=error)
        lines = self.__dict__.setdefault('_coop_connection_log', [])
        lines.append(time.strftime('%H:%M:%S') + ' ' + message)
        del lines[:-200]
        self._refresh_coop_log()

    def _refresh_coop_log(self):
        widget = getattr(self, '_coop_log_text', None)
        if widget and widget.winfo_exists():
            widget.configure(state='normal')
            widget.delete('1.0', 'end')
            widget.insert('end', '\n'.join(getattr(self, '_coop_connection_log', ())))
            widget.configure(state='disabled')
            widget.see('end')

    def _show_coop_log(self):
        old = getattr(self, '_coop_log_dialog', None)
        if old and old.winfo_exists():
            old.lift()
            return
        dialog = tk.Toplevel(self)
        self._coop_log_dialog = dialog
        dialog.title('Co-op connection log')
        dialog.transient(self)
        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text=f'Persistent log: {LAUNCHER_LOG}', wraplength=700).pack(anchor='w')
        text_frame = ttk.Frame(frame)
        text_frame.pack(fill='both', expand=True, pady=8)
        self._coop_log_text = tk.Text(text_frame, width=100, height=22, wrap='word', state='disabled')
        scrollbar = ttk.Scrollbar(text_frame, command=self._coop_log_text.yview)
        self._coop_log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self._coop_log_text.pack(side='left', fill='both', expand=True)
        ttk.Button(frame, text='Copy connection log', command=self._copy_coop_log).pack(anchor='w')
        self._refresh_coop_log()

    def _copy_coop_log(self):
        self.clipboard_clear()
        self.clipboard_append('\n'.join(getattr(self, '_coop_connection_log', ())))

    def _refresh_coop_connection_fields(self):
        connected = bool(self._coop_lobby)
        joining = hasattr(self, '_coop_role') and self._coop_role.get() == 'Join'
        for name, visible in (('_coop_host_code_label', not joining), ('_coop_guest_code_entry', joining)):
            widget = getattr(self, name, None)
            if widget and widget.winfo_exists():
                widget.grid() if visible else widget.grid_remove()
        for widget in getattr(self, '_coop_address_widgets', ()):
            if widget.winfo_exists():
                if joining:
                    widget.grid()
                else:
                    widget.grid_remove()
        reveal = getattr(self, '_coop_show_details_check', None)
        if reveal and reveal.winfo_exists():
            reveal.configure(text='Show IP and code (visible on stream)')
            reveal.grid() if joining else reveal.grid_remove()
        for widget in getattr(self, '_coop_connection_entries', ()):
            if widget.winfo_exists():
                widget.configure(state='disabled' if connected else 'readonly' if isinstance(widget, ttk.Combobox) else 'normal')
        button = getattr(self, '_coop_connect_button', None)
        if button and button.winfo_exists():
            button.configure(state='disabled' if connected else 'normal')

    def _coop_safe_message(self, value):
        private = [getattr(self, name).get() for name in
                   ('_coop_address', '_coop_pairing', '_coop_host_pairing') if hasattr(self, name)]
        lobby = self._coop_lobby
        if lobby:
            private.extend((lobby.address, lobby.pairing_code))
            private.extend(player['ip'] for player in lobby.players)
        return redact_connection_details(value, *private)

    def connect_coop(self):
        if self._coop_lobby:
            return
        try:
            role = 'host' if self._coop_role.get() == 'Host' else 'guest'
            if role == 'host':
                self.validate_coop_run()
            if role == 'guest' and not self._coop_address.get().strip():
                raise ValueError('Paste the host\'s ZeroTier Managed IPv4.')
            lobby = Lobby(GAME_ROOT, role, self._coop_name.get(), self.coop_count(),
                          address=self._coop_address.get().strip() if role == 'guest' else '',
                          pairing_code=self._coop_pairing_code())
            if role == 'guest':
                selection = {name: getattr(self, name).get() for name in
                             ('campaign_var', 'reward_mode_var', 'seed_var', 'difficulty_var', 'selected_index')}
                self._coop_local_snapshot = (copy.deepcopy(self.state), self.shop_repository,
                                             self.progression_mode_var.get(), selection)
                self._coop_personal_repository = self.shop_repository
            self._coop_loadouts = {0: self._own_coop_loadout()}
            self._coop_player_selections = {}
            self.__dict__.pop('_coop_last_shared_loadout', None)
            self._coop_lobby = lobby
            self._coop_was_connected = False
            self._record_coop_log(f'Co-op starting: role={role}, players={lobby.count}, TCP {lobby.port}.')
            lobby.start()
            self._coop_status.set('Connecting...' if role == 'guest' else 'Waiting for guests...')
            self._refresh_coop_connection_fields()
            self.refresh_coop_controls()
            self.after(100, self._poll_coop_lobby)
        except (ValueError, OSError) as exc:
            self._record_coop_log('Co-op connection failed: ' + str(exc), error=True)
            messagebox.showerror('Co-op connection', self._coop_safe_message(exc), parent=self)

    def disconnect_coop(self):
        process = getattr(self, 'active_game_process', None)
        if process and process.poll() is None:
            messagebox.showwarning('Co-op connection', 'Close the active game before disconnecting.', parent=self)
            return
        lobby = self._coop_lobby
        if lobby:
            lobby.close()
            self._record_coop_log('Co-op disconnected.')
        self._coop_lobby = None
        self._coop_pending_launch = None
        self._coop_loadouts = {}
        self._coop_player_selections = {}
        self.__dict__.pop('_coop_last_shared_loadout', None)
        self.__dict__.pop('_coop_personal_repository', None)
        self.__dict__.pop('_coop_guest_loadout_selection', None)
        self.__dict__.pop('_coop_host_shop_run', None)
        self.finish_progression_launch_context()
        snapshot = self.__dict__.pop('_coop_local_snapshot', None)
        if snapshot:
            self.state, self.shop_repository, mode, selection = snapshot
            self.shop_service = ShopProgressionService(self.shop_repository, loadout=self.effective_shop_run)
            self.shop_profile, self.shop_run = self.shop_repository.load()
            self.progression_mode_var.set(mode)
            for name, value in selection.items():
                getattr(self, name).set(value)
            self._refresh_coop_state_views()
        if hasattr(self, '_coop_status'):
            self._coop_status.set('Disconnected')
        self.refresh_coop_controls()
        self.refresh_grid_tiles()
        self._refresh_coop_connection_fields()

    def _poll_coop_lobby(self):
        lobby = self._coop_lobby
        if not lobby:
            return
        try:
            while True:
                event, value = lobby.events.get_nowait()
                if event == 'status':
                    self._record_coop_log('Co-op: ' + value, error=value.startswith('Guest rejected:'))
                    if hasattr(self, '_coop_status'):
                        self._coop_status.set(self._coop_safe_message(value))
                elif event == 'diagnostic':
                    name, details = value
                    log_event(name, **details)
                    self._record_coop_log(name + ': ' + json.dumps(details, sort_keys=True, indent=2))
                elif event == 'connected':
                    self._coop_was_connected = True
                    self._record_coop_log(f'Co-op connected: {len(value)} players.')
                    if hasattr(self, '_coop_status'):
                        self._coop_status.set(self._coop_safe_message(f'Connected as player {lobby.slot + 1}: ' + ', '.join(player['name'] for player in value)))
                    self.coop_publish_state()
                elif event == 'error':
                    safe_value = self._coop_safe_message(value)
                    self._record_coop_log('Co-op connection failed: ' + safe_value, error=True)
                    if hasattr(self, '_coop_status'):
                        self._coop_status.set('Disconnected: ' + safe_value)
                    self._coop_pending_launch = None
                    if not (self.active_game_process and self.active_game_process.poll() is None):
                        self.finish_progression_launch_context()
                    if not self._coop_was_connected:
                        self.disconnect_coop()
                        if hasattr(self, '_coop_status'):
                            self._coop_status.set('Connection failed: ' + safe_value)
                        return
                    # Keep guest state read-only until explicit disconnect,
                    # even when the host socket drops during a running game.
                elif event == 'message':
                    self._handle_coop_message(*value)
        except queue.Empty:
            pass
        except (ValueError, OSError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError, ShopTransitionError) as exc:
            safe_value = self._coop_safe_message(exc)
            self._record_coop_log('Co-op message rejected: ' + safe_value, error=True)
            self._coop_pending_launch = None
            if not (self.active_game_process and self.active_game_process.poll() is None):
                self.finish_progression_launch_context()
            if lobby.connected:
                try:
                    lobby.send({'type': 'abort', 'reason': str(exc)})
                except OSError:
                    pass
            if event == 'message' and value[1].get('type') == 'state':
                # An incompatible snapshot cannot support further launches.
                # Stop processing it and keep the last valid personal state.
                lobby.close()
                if hasattr(self, '_coop_status'):
                    self._coop_status.set('Disconnected: ' + safe_value)
                return
        pending = self._coop_pending_launch
        if pending and time.monotonic() > pending['deadline']:
            self.append_log('Co-op preparation timed out; no game started.', error=True)
            self._coop_pending_launch = None
            if lobby.connected:
                lobby.send({'type': 'abort', 'reason': 'Preparation timed out'})
            self.finish_progression_launch_context()
        self.after(100, self._poll_coop_lobby)

    def _handle_coop_message(self, slot, message):
        lobby = self._coop_lobby
        kind = message.get('type')
        if kind == 'abort':
            preparing = bool(self._coop_pending_launch)
            self._coop_pending_launch = None
            if preparing:
                if lobby.role == 'host' and lobby.connected:
                    lobby.send({'type': 'abort', 'reason': str(message.get('reason', 'Peer rejected preparation'))})
                self.finish_progression_launch_context()
            self.append_log('Co-op launch aborted: ' + self._coop_safe_message(message.get('reason', 'Peer rejected preparation')), error=True)
            return
        if lobby.role == 'host':
            if kind == 'loadout':
                if not 0 < slot < self.coop_count():
                    raise ValueError('Invalid co-op loadout player slot.')
                loadout = normalize_contribution(message['loadout'])
                if self._coop_pending_launch or self.busy_depth or (self.active_game_process and self.active_game_process.poll() is None):
                    host_run = self.shop_repository.load_run()
                    finished_stage = (not self._coop_pending_launch and not self._coop_building_map
                                      and self.shop_launch_active() and host_run
                                      and (host_run.status is not RunStatus.ACTIVE or not host_run.mission_committed))
                    if not finished_stage and gameplay_document(loadout) != gameplay_document(self._coop_loadouts.get(slot, {})):
                        raise ValueError('Cannot change team loadouts during a co-op mission/preparation.')
                    self._coop_loadouts[slot] = loadout
                    return
                self._coop_loadouts[slot] = loadout
                self.coop_publish_state()
                self.refresh_shop_mode()
                self.append_log(f'{lobby.players[slot]["name"]} shared their permanent loadout.')
            elif kind == 'suggest' and message.get('code') in self._mission_by_code:
                if not 0 < slot < self.coop_count():
                    raise ValueError('Invalid co-op suggestion player slot.')
                self._coop_player_selections[slot] = message['code']
                lobby.send({'type': 'selections', 'selections': {str(player): code for player, code in self._coop_player_selections.items()}})
                self.refresh_grid_tiles()
                self.append_log(f'{lobby.players[slot]["name"]} suggests {self._mission_by_code[message["code"]]["title"]}.')
            elif kind == 'ready':
                pending = self._coop_pending_launch
                if not pending or message.get('token') != pending['token'] or message.get('sha256') != pending['sha256']:
                    raise ValueError('Stale or mismatched co-op preparation acknowledgement.')
                pending['ready'].add(slot)
                if len(pending['ready']) == self.coop_count():
                    self._validate_coop_runtime(pending)
                    lobby.send({'type': 'go', 'token': pending['token']})
                    self._launch_prepared_coop()
            else:
                raise ValueError('Guest sent a host-only or unsupported message.')
            return
        if kind == 'state':
            self._apply_coop_state(message)
        elif kind in ('select', 'selections'):
            self._apply_coop_selections(message['selections'])
            if kind == 'select':
                self._select_coop_host_mission(message['code'])
            self.refresh_grid_tiles()
        elif kind == 'prepare':
            if self._coop_pending_launch or (self.active_game_process and self.active_game_process.poll() is None):
                raise ValueError('A co-op game is already active/preparing.')
            mission = self._mission_by_code[message['code']]
            verify_dependencies(GAME_ROOT, mission)
            if message['metadata_hash'] != mission['coop_metadata_hash']:
                raise ValueError('Native co-op source map or metadata differs.')
            self.validate_coop_run()
            data = unpack(message['map'])
            if hashlib.sha256(data).hexdigest() != message['sha256']:
                raise ValueError('Co-op map checksum differs.')
            if self.shop_mode_selected():
                run = self.shop_run
                if not run or not run.mission_committed or run.selected_mission_code != mission['code']:
                    raise ValueError('Host Shop commitment differs from launch.')
            elif mission['code'] not in {*self.unlocked_mission_codes(), *self.state.get('completed_missions', ())}:
                raise ValueError('Host selected a locked Grid mission.')
            pending = dict(message, mission=mission, deadline=time.monotonic() + 45)
            self._write_coop_runtime(pending, data)
            self._coop_pending_launch = pending
            lobby.send({'type': 'ready', 'token': message['token'], 'sha256': message['sha256']})
        elif kind == 'go':
            if not self._coop_pending_launch or message['token'] != self._coop_pending_launch['token']:
                raise ValueError('Stale cooperative game start.')
            self._launch_prepared_coop()
        else:
            raise ValueError('Unsupported host co-op message.')

    def _apply_coop_state(self, message):
        if self._coop_pending_launch:
            raise ValueError('Host changed run during co-op preparation.')
        snapshot = json.loads(unpack(message['snapshot']))
        if snapshot.get('loadout_protocol') != 3:
            raise ValueError('Host launcher must support personal Shop purchases and mission pings. Update every launcher.')
        if snapshot['count'] != self.coop_count() or snapshot['mode'] not in ('Grid Mode', 'Shop Mode'):
            raise ValueError('Host mode or player count differs.')
        loadouts = snapshot['loadouts']
        if (not isinstance(loadouts, dict) or '0' not in loadouts
                or not set(loadouts) <= {str(slot) for slot in range(self.coop_count())}):
            raise ValueError('Invalid host player loadouts.')
        loadouts = {int(slot): normalize_contribution(item) for slot, item in loadouts.items()}
        state = snapshot['state']
        if not isinstance(state, dict):
            raise ValueError('Invalid host Grid state.')
        run = normalize_shop_run(snapshot['shop_run']) if snapshot['shop_run'] else None
        active_run = run if snapshot['mode'] == 'Shop Mode' else None
        document = active_run.reward_settings if active_run else state
        if document:
            codes = active_run.eligible_mission_codes if active_run else state.get('mission_order', ())
            self._validate_coop_document(document, codes)
        # Reject incompatible snapshots before replacing any guest progress.
        personal = self._coop_personal_repository
        profile, local = personal.load()
        personal_update = None
        if active_run and local is not None and (local.status is RunStatus.ACTIVE
                or (local.seed == active_run.seed and local.completed_missions == active_run.completed_missions)):
            self._validate_coop_document(local.reward_settings, local.eligible_mission_codes)
            personal_update = sync_personal_run(profile, local, active_run, self._mission_by_code)
        selections = snapshot.get('selections', {})
        if (not isinstance(selections, dict)
                or not set(selections) <= {str(slot) for slot in range(self.coop_count())}
                or any(code not in self._mission_by_code for code in selections.values())):
            raise ValueError('Invalid cooperative mission selections.')
        self._coop_applying_state = True
        try:
            if personal_update:
                self._commit_coop_shop_sync(local, *personal_update)
            self._coop_loadouts = loadouts
            self.state = state
            self._coop_host_shop_run = run
            if active_run and personal_update is None:
                self._set_shop_message(f'Start your own co-op Shop run with host seed {active_run.seed}. Purchases and Ore stay personal.', error=True)
            self.shop_profile, self.shop_run = personal.load()
            self.progression_mode_var.set(snapshot['mode'])
            if state:
                self.campaign_var.set(state.get('campaign_filter', 'All Campaigns'))
                self.reward_mode_var.set(state.get('reward_mode', self.reward_mode_var.get()))
            self.seed_var.set(run.seed if active_run else state.get('seed', ''))
            self.difficulty_var.set(snapshot['difficulty'])
            selected = next((index for index, mission in enumerate(self.missions)
                             if mission['code'] == snapshot.get('selected')), None)
            if selected is not None:
                self.selected_index.set(selected)
            self._apply_coop_selections(snapshot.get('selections', {}))
            self._refresh_coop_state_views()
            self._record_coop_log(f'Co-op host state synced: {snapshot["mode"]}, seed {self.seed_var.get()}.')
        finally:
            self._coop_applying_state = False
        self.coop_publish_state()

    def _sync_coop_shop_run(self, host):
        personal = self._coop_personal_repository
        profile, local = personal.load()
        if local is None or (local.status is not RunStatus.ACTIVE
                             and (local.seed != host.seed or local.completed_missions != host.completed_missions)):
            self._set_shop_message(f'Start your own co-op Shop run with host seed {host.seed}. Purchases and Ore stay personal.', error=True)
            return
        profile, updated = sync_personal_run(profile, local, host, self._mission_by_code)
        self._commit_coop_shop_sync(local, profile, updated)

    def _commit_coop_shop_sync(self, local, profile, updated):
        personal = self._coop_personal_repository
        if updated != local or profile != personal.load_profile():
            personal.commit(profile, updated, f'{local.run_id}:coop-sync:{secrets.token_hex(8)}')
        if self.shop_launch_active():
            self._shop_launch_run = updated
            if len(updated.completed_missions) > len(local.completed_missions):
                self._shop_launch_victory_key = updated.rewarded_victories[-1]

    def _refresh_coop_state_views(self):
        for key in ('_active_reward_settings_cache', '_canonical_earned_rewards_cache',
                    '_unlock_dashboard_sources_cache', '_configured_reward_pool_cache'):
            self.__dict__.pop(key, None)
        self.grid_render_signature = None
        self.unlock_dashboard_signature = None
        self._unlocks_view_dirty = True
        self._enemy_buffs_view_dirty = True
        self.update_header_summary()
        self.redraw_mission_tree()
        self.refresh_progress_view()
        self.refresh_shop_mode()
        self.refresh_coop_controls()

    def _record_coop_launch_error(self, exc, stage):
        detail = self._coop_safe_message(exc)
        self._record_coop_log(f'Co-op {stage} failed: {detail}', error=True)
        log_event('coop_launch_failed', level=logging.ERROR, stage=stage,
                  error=detail, traceback=self._coop_safe_message(traceback.format_exc()))

    def launch_mission_async(self, mission, extra_rules=None, launch_note=''):
        if not self.coop_enabled():
            if mission.get('coop_mode') or self.state.get('coop_mode'):
                messagebox.showerror('Experimental co-op', 'Co-op is disabled; switch to a normal run.', parent=self)
                return
            return super().launch_mission_async(mission, extra_rules, launch_note)
        try:
            self.validate_coop_run()
            lobby = self._coop_lobby
            if not lobby or not lobby.connected or lobby.role != 'host':
                raise ValueError('Connect the host and all configured co-op players before launching.')
            if len(self._coop_loadouts) != self.coop_count():
                raise ValueError('Wait for every player to share their permanent loadout. Update every launcher if a player is missing.')
            if self.busy_depth or self._coop_pending_launch or (self.active_game_process and self.active_game_process.poll() is None):
                raise ValueError('A co-op game is already running/preparing.')
            if not self.shop_launch_active() and not self.state.get('coop_mode'):
                raise ValueError('Generate a co-op Grid run before launching its missions.')
            if mission.get('coop_player_count') != self.coop_count():
                raise ValueError('Selected native mission does not support this player count.')
            if self.progression_mode_var.get() not in ('Grid Mode', 'Shop Mode'):
                raise ValueError('Experimental DTA co-op supports Grid Mode and Shop Mode.')
            run = self._shop_launch_run
            if run and set(run.modifiers) - SAFE_SHOP_MODIFIERS:
                raise ValueError('Saved co-op Shop run contains unsupported gameplay modifiers.')
            from randomizer.rewards.catalogue import REWARD_POOL
            from randomizer.rewards.display import starting_credit_bonus
            player_loadouts = []
            try:
                for slot in range(self.coop_count()):
                    self._coop_launch_loadout_slot = slot
                    rewards = list(self.launch_rewards_for_mission(mission['code']))
                    if any(not supported_reward(reward) and not reward.get('max_rewards_achieved') for reward in rewards):
                        raise ValueError('Saved co-op rewards contain unsupported effects. Generate a new experimental run.')
                    starter_ids = set(self.active_starting_tier_one_expanded_ids()) | set(self.active_starting_tier_one_defense_expanded_ids())
                    rewards.extend(reward for reward in REWARD_POOL if reward.get('dta_production_access') and reward.get('unit') in starter_ids)
                    settings = self.active_reward_settings()
                    credit_bonus = starting_credit_bonus(rewards)
                    if run:
                        from randomizer.shop.modifiers import modifier_effects
                        credit_bonus += modifier_effects(run.modifiers)['mission_starting_credits_flat']
                    player_loadouts.append({'rewards': rewards, 'settings': settings,
                                           'credit_bonus': credit_bonus,
                                           'randomize_access': self.randomize_unit_access_enabled()})
            finally:
                self.__dict__.pop('_coop_launch_loadout_slot', None)
            difficulty = self.resolve_selected_mission_difficulty(mission)
            speed = self.get_selected_game_speed_value()
            self._record_coop_log(f'Co-op preparing {mission["code"]}: {difficulty.label}.')
            self._coop_building_map = True
            self.run_in_background(
                'Preparing co-op mission…', 'Building the host team map and waiting for every player.',
                lambda: prepare_map(GAME_ROOT, mission, (), difficulty, player_loadouts=player_loadouts),
                lambda result: self._share_coop_launch(mission, difficulty, speed, result, launch_note),
                self.handle_mission_prepare_error,
            )
        except (ValueError, OSError, KeyError, IndexError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
            self._coop_building_map = False
            self._record_coop_launch_error(exc, 'launch validation')
            self.finish_progression_launch_context()
            messagebox.showerror('Co-op launch', self._coop_safe_message(exc), parent=self)

    def handle_mission_prepare_error(self, exc, detail):
        self._coop_building_map = False
        if self.coop_enabled():
            self._record_coop_log('Co-op map preparation failed: ' + self._coop_safe_message(exc), error=True)
        return super().handle_mission_prepare_error(exc, detail)

    def _share_coop_launch(self, mission, difficulty, speed, result, launch_note):
        self._coop_building_map = False
        data, settings, report, digest = result
        lobby = self._coop_lobby
        if not lobby or not lobby.connected:
            self.finish_progression_launch_context()
            return
        pending = {'type': 'prepare', 'code': mission['code'], 'metadata_hash': mission['coop_metadata_hash'],
                   'token': secrets.token_hex(16), 'game_id': secrets.randbelow(2**31 - 1) + 1,
                   'sha256': digest, 'map': pack(data), 'settings': settings, 'speed': speed}
        try:
            self.coop_publish_state()
            self._write_coop_runtime(pending, data)
            self._coop_pending_launch = dict(pending, mission=mission, difficulty=difficulty,
                                              ready={0}, deadline=time.monotonic() + 45)
            lobby.send(pending)
            self._record_coop_log(f'Co-op map prepared: {len(report["applied"])} player-specific production clones; {len(report["skipped"])} skipped. Waiting for all players.')
            for player in report.get('players', ()):
                self._record_coop_log(f'Player {player["slot"] + 1}: {player["production_house"]}; {len(player["applied"])} clones; starting credit bonus {player["credit_bonus"]}.')
        except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
            self._record_coop_launch_error(exc, 'preparation')
            self._coop_pending_launch = None
            self.finish_progression_launch_context()
            messagebox.showerror('Co-op preparation', self._coop_safe_message(exc), parent=self)

    def _write_coop_runtime(self, pending, data):
        mission = self._mission_by_code[pending['code']]
        lobby = self._coop_lobby
        spawn = spawn_data(mission, lobby.players, lobby.slot, pending['game_id'], data, pending['settings'], pending['speed'])
        SPAWN_MAP_INI.write_bytes(data)
        SPAWN_INI.write_bytes(spawn)
        pending['_spawn_sha256'] = hashlib.sha256(spawn).hexdigest()
        self._validate_coop_runtime(pending)
        if not GAME_EXE.is_file() or not GAME_LAUNCHER_EXE.is_file():
            raise FileNotFoundError('DTA game.exe or LaunchVinifera.dat is missing.')
        # Resolve the native launch path before acknowledging preparation.
        # Missing Wine/SyringeEx must not release the other players' barrier.
        self.build_command()

    def _validate_coop_runtime(self, pending):
        if hashlib.sha256(SPAWN_MAP_INI.read_bytes()).hexdigest() != pending['sha256']:
            raise ValueError('Prepared co-op map changed before game start.')
        if hashlib.sha256(SPAWN_INI.read_bytes()).hexdigest() != pending['_spawn_sha256']:
            raise ValueError('Prepared co-op spawn configuration changed before game start.')

    def _launch_prepared_coop(self):
        pending = self._coop_pending_launch
        self._validate_coop_runtime(pending)
        self._coop_pending_launch = None
        mission = pending['mission']
        if self.coop_guest_connected() and self.shop_mode_selected():
            self._shop_launch_run = self.shop_run
        hook = {'mission_code': mission['code'], 'scenario': 'spawnmap.ini', 'markers': {},
                'seen': set(), 'offset': 0, 'dta': True, 'coop': True,
                'coop_score_log': ScoreLog(DEBUG_LOG),
                'coop_human_names': [player['name'] for player in self._coop_lobby.players]}
        self.start_mission_process(mission, hook, self.resolve_selected_mission_difficulty(mission), pending['speed'], 'Experimental native co-op')
        self.refresh_coop_controls()

    def process_hook_log_text(self, text):
        hook = getattr(self, 'active_hook', None)
        if not hook or not hook.get('coop'):
            return super().process_hook_log_text(text)
        if self.coop_guest_connected() or 'co-op victory' in hook['seen']:
            return
        # The host log contains all final player scores. A surviving human
        # teammate can win after the host was defeated. AI winners alone and
        # a campaign score-screen message must never grant team progression.
        names = '|'.join(re.escape(name) for name in hook['coop_human_names'])
        text = hook.pop('coop_log_tail', '') + text
        parts = text.split('\n')
        hook['coop_log_tail'] = parts.pop()
        if any(re.fullmatch('(?:' + names + r'): Winner\s*', line.strip()) for line in parts):
            self.unlock_mission_check(hook['mission_code'], 'victory', 'DTA co-op team victory')
            hook['seen'].add('co-op victory')

    def on_mission_select(self, event):
        result = super().on_mission_select(event)
        if self.coop_enabled():
            self._publish_coop_selection(self.selected_mission_code())
        return result

    def select_grid_mission(self, index):
        result = super().select_grid_mission(index)
        if self.coop_enabled() and self.selected_index.get() == index:
            self._publish_coop_selection(self.selected_mission_code())
        return result

    def poll_hook_log(self):
        hook = getattr(self, 'active_hook', None)
        if not hook or not hook.get('coop'):
            return super().poll_hook_log()
        process = getattr(self, 'active_game_process', None)
        try:
            text = hook['coop_score_log'].read_text(final=process is None or process.poll() is not None)
            self.process_hook_log_text(text)
        except OSError as exc:
            self.append_log('Co-op score log read failed: ' + self._coop_safe_message(exc), error=True)
        # Reuse the existing process-exit/Shop failure lifecycle after reading
        # scores. The shared watcher skips its solo log discovery for co-op.
        result = super().poll_hook_log()
        if self.active_hook is None:
            self.refresh_coop_controls()
        return result

    def close_launcher(self):
        process = getattr(self, 'active_game_process', None)
        if self._coop_lobby and not (process and process.poll() is None):
            self._coop_lobby.close()
        return super().close_launcher()
