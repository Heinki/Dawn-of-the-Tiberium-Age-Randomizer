# Developer Guide

Start with [README.md](README.md) for current scope and runtime behavior. This guide contains the remaining implementation and validation notes.

## Source map

### DTA adapter

- `randomizer/dta/rules.py`: installed `Rules.ini` catalogue and collision diagnostics.
- `randomizer/dta/maps.py`: source-map resolution, difficulty overlay, and `spawnmap.ini` preparation.
- `randomizer/dta/difficulty.py`: DTA label, client-rank, and engine-value translation.
- `randomizer/dta/clones.py`: Vinifera player-production access, Player Army buffs, and unit-specific clone rules.
- `randomizer/dta/powers.py`: DTA power catalogue, direct player grants, buildable player-only power-provider clones, exclusive native Ion effects, and cloned auxiliary effect chains.
- `randomizer/dta/enemies.py`: hostile-family detection and enemy-only country bonuses.
- `randomizer/dta/cameos.py`: DTA MIX and TS SHP cameo extraction.

### Missions and progression

- `randomizer/missions/catalogue.py`: `INI/Battle.ini` parsing, DTA classifications, filters, and deterministic mission ordering.
- `randomizer/progression/grid.py`: Grid topology and unlock state.
- `randomizer/progression/state.py`: persisted completion and retry state normalization.
- `randomizer/rewards/planning.py`: deterministic reward-slot planning.
- `randomizer/rewards/dta_definitions.py`: active DTA access and buff catalogue.
- `randomizer/rewards/display.py`: reward canonicalization, stacking, and display.
- `randomizer/shop/`: pure Shop economy, mission offers, catalogue, purchases,
  modifiers, lifecycle transitions, normalization, and persistence.
- `randomizer/shop/catalogue.py`: DTA runtime-catalogue and target-price adapter.
- `randomizer/shop/mission_modifiers.py`: deterministic player boons and
  hostile-house challenges.

### Configuration

- `randomizer/config/static.py`: packaged/source paths, JSON loading, and caching.
- `randomizer/config/schema.py`: static configuration validation.
- `randomizer/config/player.py`: `dta_randomizer.yaml` loading, saving, and migration.
- `configs/missions.json`: 92 mission classifications and campaign policy.
- `configs/factions.json`: DTA production families and permanent essentials.
- `configs/ui.json`: DTA campaigns, difficulties, speeds, colors, and preserved progression modes.
- `configs/rewards/`: active DTA reward tuning and policy.

Read [configs/README.md](configs/README.md) before changing static data.

### Launcher and UI

- `launcher_gui.py`: source entry point and non-invasive self-check.
- `randomizer/application/app.py`: Tk composition and initialization.
- `randomizer/application/*_controller.py`: seed, state, launch, reward, progression, and Archipelago orchestration.
- `randomizer/ui/`: widget construction, layouts, themes, grids, cameos, and tooltips.
- `randomizer/application/shop_controller.py`: Shop workspace, launch context,
  victory/failure transitions, and DTA reward integration.
- `randomizer/ui/shop.py`: mission cards, run stock, loadout, permanent
  progression, and summaries.
- `randomizer/maps/shop_modifiers.py`: Shop run modifiers over isolated DTA
  player clones.
- `randomizer/launch/options.py`: DTA `spawn.ini` serialization.
- `randomizer/core/paths.py`: source and packaged paths.
- `randomizer/core/storage.py`: atomic persistence.

## Runtime flow

1. `launcher_gui.py` validates DTA paths and initializes the application.
2. `randomizer/missions/catalogue.py` reads the installed DTA mission catalogue.
3. Seed creation freezes mission order, settings, checks, and reward assignments.
4. A mission launch reads a fresh source map and resolves its DTA difficulty.
5. The map pipeline applies access, prerequisite-free player production infrastructure, guarded player-production clones, unit and army buffs, exact-player power grants or provider buildings, starting credits, enemy-only bonuses, and DTA colors.
6. The launcher writes `spawnmap.ini` and `spawn.ini`.
7. `LaunchVinifera.dat game.exe --args="-SPAWN -CD."` starts the mission through DTA 16.0.2's SyringeEx launcher.
8. The debug-log watcher records the score-screen Victory check exactly once. DTA has no uniform runtime event for map sub-objectives, so only mission victory awards progression rewards.

Shop Mode persists its selected offer before launch. Victory atomically awards
Ore/Gems and creates the next offer; mission process exit without victory ends
the run. Shop loadouts feed the same access, clone, power, starting-credit, and
hostile-house scaling stages as normal progression.

Shop unit prices are explicit per target in `configs/shop_mode.json`. Native
DTA build cost supplies the baseline Mental Omega price band; reviewed utility
and high-impact targets may override it. TechLevel remains catalogue metadata,
not an economy input. Keep run access, run buff, permanent access, and
permanent buff prices aligned when adding a rewardable DTA target.

Pure modules must not import `randomizer/application`. Tk variables stay on the UI thread; workers receive plain Python data.

## Change rules

- Preserve deterministic RNG call order. New deterministic behavior needs a named stream.
- Preserve serialized reward, mission, and check IDs unless an explicit migration exists.
- Treat `VehicleTypes` A_/B_/C_/D_ registrations as authoritative ground-unit factions; `Owner` can be broader for scenario placement.
- Never edit installed source mission maps.
- Never replace authored placed-unit, TaskForce, TeamType, trigger, script, or reinforcement identities.
- Resolve scenario houses through Vinifera `ActsLike` before writing production masks.
- Resolve shared `ActsLike` collisions through map-local HouseType-bit isolation before access or clone routing. Fail launch visibly if exact player-only isolation cannot be established; never silently discard earned access.
- Keep all 92 installed mission codes explicitly classified.
- Keep mission INI order, repeated entries, comments, and line-ending behavior intact.
- Put data-driven mission exceptions in `configs/missions.json` when possible.
- Keep filesystem and Tk wrappers thin; keep deterministic behavior in pure functions.
- Preserve public facade imports when splitting modules.
- Preserve Shop profile/run transaction recovery. Purchases, rerolls, mission
  commitments, and victory receipts must remain idempotent.

## Validation

Routine checks from `RandomizerLauncher`:

```powershell
python -m compileall -q .
python launcher_gui.py --self-check
git diff --check
```

Packaging:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_all.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_exe.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\Archipelago\build_apworld.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_archipelago_release.ps1
```

Equivalent Linux maintainer commands (the EXE remains a Windows executable):

```bash
./build_all_linux.sh
./build_exe_wine.sh
python3 Archipelago/build_apworld.py
```

Changes affecting mission parsing, map generation, difficulty, access, clones, buffs, launch, or completion require focused generated-map checks and relevant live DTA mission tests. Changes affecting the catalogue or APWorld require matching launcher and APWorld builds.
