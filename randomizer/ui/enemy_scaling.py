"""Enemy-buff controls inside the normal reward settings."""

from ._builder_dependencies import (
    ENEMY_BUFF_GROUP_DEFINITIONS,
    MAX_AI_REWARDS_PER_COMPLETION,
    WidgetTooltip,
    ttk,
)


def build_enemy_scaling_settings(self, reward_frame):
    ttk.Separator(reward_frame, orient='horizontal').grid(
        row=15, column=0, sticky='ew', pady=(8, 6)
    )
    self.enemy_reward_pool_check = ttk.Checkbutton(
        reward_frame,
        text='Include enemy buff rewards',
        variable=self.enemy_reward_pool_var,
        command=self.refresh_setting_states,
    )
    self.enemy_reward_pool_check.grid(row=16, column=0, sticky='w')
    WidgetTooltip(
        self.enemy_reward_pool_check,
        'Adds hostile-AI-only buffs to the reward pool. Archipelago exports '
        'them as Trap items. No-build missions never apply enemy buffs.',
    )

    rate_row = ttk.Frame(reward_frame)
    rate_row.grid(row=17, column=0, sticky='ew', pady=(4, 0))
    ttk.Label(rate_row, text='Extra enemy buffs per mission victory').grid(
        row=0, column=0, sticky='w', padx=(0, 8)
    )
    self.enemy_mission_rewards_spinbox = ttk.Spinbox(
        rate_row,
        from_=0,
        to=MAX_AI_REWARDS_PER_COMPLETION,
        width=5,
        textvariable=self.enemy_mission_rewards_var,
        command=self.refresh_setting_states,
    )
    self.enemy_mission_rewards_spinbox.grid(row=0, column=1, sticky='w')
    self.enemy_mission_rewards_spinbox.bind(
        '<MouseWheel>', self.on_settings_control_mousewheel, add='+'
    )

    self.enemy_reward_capacity_label = ttk.Label(
        reward_frame,
        text='',
        style='Muted.TLabel',
        justify='left',
        wraplength=590,
    )
    self.enemy_reward_capacity_label.grid(
        row=18, column=0, sticky='w', pady=(3, 5)
    )

    groups_frame = ttk.Frame(reward_frame)
    groups_frame.grid(row=19, column=0, sticky='ew')
    groups_frame.columnconfigure(0, weight=1)
    groups_frame.columnconfigure(1, weight=1)
    self.enemy_buff_group_controls = []
    self.enemy_buff_group_tooltips = {}
    for index, group in enumerate(ENEMY_BUFF_GROUP_DEFINITIONS):
        check = ttk.Checkbutton(
            groups_frame,
            text=group['label'],
            variable=self.enemy_buff_group_vars[group['id']],
            command=lambda group_id=group['id']: (
                self.on_enemy_buff_group_changed(group_id)
            ),
        )
        check.grid(
            row=index // 2,
            column=index % 2,
            sticky='w',
            padx=(0, 10),
            pady=(0, 2),
        )
        self.enemy_buff_group_controls.append((group, check))
        self.enemy_buff_group_tooltips[group['id']] = WidgetTooltip(
            check, self.enemy_buff_group_help_text(group)
        )
    self.refresh_enemy_reward_setting_help()
