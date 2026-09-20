"""A bounded two-dropdown editor shared by Details and Shop mission cards."""

from tkinter import ttk

from randomizer.dta.preconditions import mission_preconditions
from randomizer.ui.tooltips import WidgetTooltip


class PreconditionPicker(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.mission = {}
        self.options = []
        self.locked = False
        self.editable = True
        self.columnconfigure(0, weight=3, minsize=0)
        self.columnconfigure(1, weight=2, minsize=0)
        ttk.Label(self, text='Mission preconditions').grid(
            row=0, column=0, columnspan=2, sticky='w'
        )
        self.condition = ttk.Combobox(self, state='readonly', width=1, height=12)
        self.condition.grid(row=1, column=0, sticky='ew', padx=(0, 4))
        self.state = ttk.Combobox(self, state='readonly', width=1, height=8)
        self.state.grid(row=1, column=1, sticky='ew')
        self.tooltip = WidgetTooltip(self.condition, '')
        self.state_tooltip = WidgetTooltip(self.state, '')
        self.access_message = ttk.Label(self, text='', style='Muted.TLabel')
        self.unlock_button = ttk.Button(self, text='Unlock choices')
        self.condition.bind('<<ComboboxSelected>>', self._select)
        self.state.bind('<<ComboboxSelected>>', self._save)

    def configure_access(
        self, *, locked=False, editable=True, unlock_cost=0,
        can_unlock=False, unlock_command=None,
    ):
        """Lock Shop choices to ON until their per-mission fee is paid."""
        self.locked = bool(locked)
        self.editable = bool(editable)
        if self.locked:
            self.condition.grid_remove()
            self.state.grid_remove()
            self.access_message.configure(text='Default: all conditions ON')
            self.access_message.grid(
                row=1, column=0, columnspan=2, sticky='w', pady=(4, 0)
            )
            self.unlock_button.configure(
                text=f'Unlock choices ({int(unlock_cost)} Ore)',
                command=unlock_command,
                state='normal' if can_unlock else 'disabled',
            )
            self.unlock_button.grid(
                row=2, column=0, columnspan=2, sticky='ew', pady=(4, 0)
            )
        else:
            self.condition.grid()
            self.state.grid()
            self.access_message.grid_remove()
            self.unlock_button.grid_remove()
        self.state.configure(
            state='readonly' if self.editable and not self.locked else 'disabled'
        )
        self._select()

    def set_mission(self, mission):
        if mission == self.mission:
            self._select()
            return
        self.mission = mission
        self.options = mission_preconditions(mission) if mission else []
        if not self.options:
            self.grid_remove()
            return
        self.grid()
        self.condition.configure(values=[item['label'] for item in self.options])
        self.condition.current(0)
        self._select()

    def _select(self, _event=None):
        index = self.condition.current()
        if not self.options or not 0 <= index < len(self.options):
            return
        item = self.options[index]
        self.state.configure(values=(item['disabled'], item['enabled']))
        selections = self.app.config.get('mission_preconditions', {})
        selected = selections.get(self.mission['code'], {}) if isinstance(selections, dict) else {}
        value = (
            True
            if self.locked
            else selected.get(item['id'], False)
            if isinstance(selected, dict)
            else False
        )
        self.state.current(int(value in (True, 1, '1')))
        self.tooltip.text = item['label'] + '\n' + item['description']
        self.state_tooltip.text = f"{item['disabled']} / {item['enabled']}"

    def _save(self, _event=None):
        if not self.options or self.locked or not self.editable:
            return
        item = self.options[self.condition.current()]
        if not isinstance(self.app.config.get('mission_preconditions'), dict):
            self.app.config['mission_preconditions'] = {}
        if not isinstance(self.app.config['mission_preconditions'].get(self.mission['code']), dict):
            self.app.config['mission_preconditions'][self.mission['code']] = {}
        self.app.config['mission_preconditions'].setdefault(
            self.mission['code'], {}
        )[item['id']] = bool(self.state.current())
        self.app.save_current_launcher_config()
