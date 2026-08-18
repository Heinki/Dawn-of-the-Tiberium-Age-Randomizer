# DTA randomizer configuration

The active static configuration targets Dawn of the Tiberium Age.

- `missions.json` contains the 81-entry DTA campaign catalogue metadata and explicit build classifications.
- `factions.json` and `tier_one.json` contain DTA faction and production-family identities.
- `ui.json` defines DTA campaign filters, colors, difficulty choices, and preserved UI modes.
- `default_player_config.json` keeps the existing settings structure with conservative DTA defaults.
- `rewards/tuning.json` and `rewards/enemy_scaling.json` contain active DTA reward tuning.
- `rewards/powers.json` defines each supported DTA player power explicitly: sidebar action, engine type, native launch-provider source, payload capacity, and buffable effect chain. Missile effects use isolated managed helper types in installed `Rules.ini` and `Art.ini`; generated SuperWeaponTypes and hidden off-map launch providers remain mission-local.

DTA unit and defense catalogues are derived from installed game data at runtime. Power behavior is not inferred by cloning an installed SuperWeaponType. DTA's Vinifera missile routine requires a live `NukeSilo=yes` BuildingClass whose `SuperWeapon` exactly matches the selected power, so the randomizer derives invisible launchers from `TMPL`, `RAMSLO`, or `RAPDOX` and places them in the map's off-map buffer. DTA's paradrop routine ignores `DropPodInfantryMinimum`, `DropPodInfantryMaximum`, and `Paratrooper`; delivered quantity is the configured `BADGER` passenger capacity.

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
