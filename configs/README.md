# DTA randomizer configuration

The active static configuration targets Dawn of the Tiberium Age.

- `missions.json` contains the 81-entry DTA campaign catalogue metadata and explicit build classifications.
- `factions.json` and `tier_one.json` contain DTA faction and production-family identities.
- `ui.json` defines DTA campaign filters, colors, difficulty choices, and preserved UI modes.
- `default_player_config.json` keeps the existing settings structure with conservative DTA defaults.
- `rewards/` exposes verified broad human-house modifiers, player-production clone buffs, and 105 mobile-unit access rewards. Eleven essential mobile units remain permanent; building, power, special-building, and AI access remain disabled.

Installed DTA techno identities and cameo mappings come from `INI/Rules.ini`, `INI/Art.ini`, and the native MIX archives at runtime. They are not copied from the source game's roster snapshots.

All JSON files use the wrapper:

```json
{
  "schema_version": 1,
  "description": "...",
  "sections": {}
}
```

Validate the full bundle with:

```powershell
python RandomizerLauncher\launcher_gui.py --self-check
```
