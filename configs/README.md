# DTA randomizer configuration

The active static configuration targets Dawn of the Tiberium Age.

- `missions.json` contains the 81-entry DTA campaign catalogue metadata, explicit build classifications, and mission reward multipliers. Stand-alone and non-finale CR Route A/B missions use x2; finales, the CR bonus mission, and every CR Route C mission use x3; all others use x1.
- `factions.json` and `tier_one.json` contain DTA faction and production-family identities.
- `factions.json` also defines curated equivalent-unit groups. Chaos keeps one access reward per group, preferring the current mission faction, while the shared-buff option applies one earned buff stack to every unlocked equivalent.
- `ui.json` defines DTA campaign filters, colors, difficulty choices, and preserved UI modes.
- `default_player_config.json` keeps the existing settings structure with conservative DTA defaults.
- `rewards/tuning.json` and `rewards/enemy_scaling.json` contain active DTA reward tuning.
- `rewards/powers.json` defines six supported player powers. Ion Cannon and Paratroopers use mission-local startup grants. Airstrike, both Nuclear Strikes, and Chrono Vortex use buildable provider clones whose inherited prerequisites are removed; the physical Construction Yard remains required.

DTA unit and defense catalogues are derived from installed game data at runtime. Firestorm and obsolete power aliases remain disabled.

Generated unit and building clones receive fixed `CameoPriority` bands in GDI, Nod, Allies, Soviet order. Defensive buildings use a separate lower set of faction bands, keeping every defense below normal buildings on the construction sidebar.

The Ion Cannon clone starts from the native `IonCannonSpecial` definition, then applies player-only identity and buff adjustments. Because Ion damage and radius are engine-global, native providers and scripted grants are removed and the native power is recharge-locked while the reward clone is active. Only the player-granted clone can fire the buffed effect. Paratroopers support recharge and payload-size buffs.

Airstrike, Nuclear Strike, and Chrono Vortex damage/radius upgrades use unique player-only SuperWeaponType, weapon, warhead, and animation clones. Their provider buildings use `Buildability=HumanOnly`; native buildings stay `AIOnly` for production and native AI effect chains remain unchanged.

In a power `provider`, `source` names the installed BuildingType template. Optional `buildable` is a boolean and defaults to `false`; `true` produces a human-only `TechLevel=1` clone with inherited prerequisite fields removed instead of placing a hidden startup provider. Optional `values` supplies explicit provider overrides.

The global `Starting Credits +1,000` reward adds 10 House-credit units at launch because DTA stores campaign House balances in hundreds. Stacks cap at 20, for a maximum 20,000-credit bonus.

DTA's paradrop hook first searches for a team named `PARADROPINF_<player house heap ID>`. The generated map supplies that player-only team with a cloned `BADGER` and the player's buffed Soviet rifle-infantry clone. This bypasses the hook's global hardcoded `E1` and native `BADGER` fallback without changing enemy paradrops.

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
