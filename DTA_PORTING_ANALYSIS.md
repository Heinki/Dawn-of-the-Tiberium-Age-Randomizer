# DTA Randomizer Porting Analysis

Audit date: 2026-08-13  
Scope: source audit plus the current DTA adapter implementation and verification status.

## Evidence labels

Every material conclusion uses one of the requested labels:

- **CONFIRMED FROM DTA SOURCE** — observed in the installed DTA files or the DTA client source.
- **CONFIRMED FROM VINIFERA SOURCE** — observed in the public Vinifera source or its official documentation.
- **CONFIRMED FROM MENTAL OMEGA SOURCE** — observed in the tracked Mental Omega Randomizer source.
- **CONFIRMED FROM LOCAL RANDOMIZER** — observed in the local working Mental Omega Randomizer, including ignored runtime data.
- **CONFIRMED BY LIVE TEST** — observed in an actual local game/client run.
- **NEEDS LIVE TEST** — source evidence exists, but installed runtime behavior has not been proven.
- **INFERRED** — a reasoned conclusion from confirmed evidence.
- **UNKNOWN** — insufficient evidence.

## Executive conclusion

- **CONFIRMED FROM LOCAL RANDOMIZER** — The Mental Omega Randomizer should remain the source implementation for the UI, seed/run model, mission-list and grid progression, reward planning/presentation, state storage, logging, and most orchestration.
- **CONFIRMED FROM DTA SOURCE** — DTA already contains working solutions for the hardest early porting problems: campaign discovery from `INI/Battle.ini`, creation of `spawn.ini` and `spawnmap.ini`, difficulty-map consolidation, campaign-global persistence, optional campaign bonuses, direct Vinifera launch, and post-game completion detection.
- **INFERRED** — The safest design is a shared randomizer core with a DTA adapter that reuses those DTA mechanisms. A separate rewrite would discard working code on both sides.
- **CONFIRMED FROM DTA SOURCE** — DTA's existing house-wide difficulty modifiers can implement broad player-only firepower, armor, speed, rate-of-fire, cost, and build-time rewards without cloning TechnoTypes.
- **CONFIRMED FROM VINIFERA SOURCE** — Current public Vinifera additionally has trigger action 135, `Adjust House Modifier`, for those seven modifiers at runtime.
- **CONFIRMED FROM DTA SOURCE** — Installed `Vinifera.dll` contains action 135's name, description, and adjacent extended-action metadata even though installed FinalSun data is outdated and lists patch actions only through 109.
- **NEEDS LIVE TEST** — Execute action 135 once in a disposable generated map before relying on it; binary presence is strong evidence, not a completed runtime test.
- **CONFIRMED FROM VINIFERA SOURCE** — No public INI key or trigger action applies an arbitrary modifier to one TechnoType only for one house while retaining the original TechnoType ID.
- **INFERRED** — Type-specific player-only rewards therefore use the mandatory collision-scan and production-only clone policy documented below. Map objects and mission-authored references are never replaced.
- **CONFIRMED FROM DTA SOURCE** — All 81 catalogued DTA missions contain a `Winner is...` action, but DTA's own score-screen log signal is a cleaner first victory detector than modifying every win trigger.
- **CONFIRMED BY USER LIVE TEST** — The launcher generated and started PTTP #6 directly from Mission List without opening the DTA client. Result detection, objective hooks, and cumulative modifier behavior still need live verification.

## Sources and version boundary

- **CONFIRMED FROM LOCAL RANDOMIZER** — Primary source inspected: `C:\Spiele\Mental Omega - Randomizer (try)\RandomizerLauncher`.
- **CONFIRMED FROM MENTAL OMEGA SOURCE** — The tracked local source is clean at commit `099aa086c7cbc5366649ae07bebe23018aecaa08`, and local `HEAD`, cached `origin/main`, and the remote repository head matched during the audit.
- **CONFIRMED FROM LOCAL RANDOMIZER** — Ignored local runtime/development data exists, including `PROJECT_CONTEXT.md`, `AGENTS.md`, player YAML, `randomizer_state.json`, map caches, generated/extracted maps, logs, builds, releases, and self-check output. These explain runtime behavior but do not represent tracked-source divergence.
- **CONFIRMED FROM DTA SOURCE** — Installed DTA version is `15.1.0`; `game.exe` identifies as Tiberian Sun 2.03; `Resources/clientdx.exe` is DTA client 2.13.4.6; `Vinifera.dll` identifies as `0.1.0.0 (f4d33ac5)`.
- **CONFIRMED FROM DTA SOURCE** — The closest public DTA client source revision with the same 2.13-era APIs is commit `8ad59ff0847698288a0428c2accae10257d80638` (assembly 2.13.4.4). Installed 2.13.4.6 is not an exact public-source match.
- **CONFIRMED FROM VINIFERA SOURCE** — Public Vinifera `develop` was inspected at commit `90a1139e7c74b453e57a3dd6af17f30005e73d1c`.
- **UNKNOWN** — Public Vinifera history does not contain installed hash `f4d33ac5`; installed DTA likely uses a private/custom or separately maintained build.
- **NEEDS LIVE TEST** — Capabilities found only in current public Vinifera must be tested against installed DTA before use.

Primary online references:

- Mental Omega Randomizer: <https://github.com/Heinki/Mental-Omega-Randomizer>
- DTA client: <https://github.com/Rampastring/dta-xna-cncnet-client>
- DTA client 2.13-era campaign handler: <https://github.com/Rampastring/dta-xna-cncnet-client/blob/8ad59ff0847698288a0428c2accae10257d80638/DXMainClient/Domain/Singleplayer/CampaignHandler.cs>
- DTA mission difficulty metadata: <https://github.com/Rampastring/dta-xna-cncnet-client/blob/master/DXMainClient/Domain/Singleplayer/Mission.cs>
- DTA campaign difficulty selector: <https://github.com/Rampastring/dta-xna-cncnet-client/blob/master/DXMainClient/DXGUI/Generic/CampaignSelector.cs>
- Vinifera: <https://github.com/Vinifera-Developers/Vinifera>
- Vinifera TechnoType house restrictions: <https://github.com/Vinifera-Developers/Vinifera/blob/develop/src/extensions/technotype/technotypeext.h>
- Vinifera mapping documentation: <https://github.com/Vinifera-Developers/Vinifera/blob/develop/docs/Mapping.md>
- Vinifera features: <https://github.com/Vinifera-Developers/Vinifera/blob/develop/docs/New-Features-and-Enhancements.md>

## Local Mental Omega Randomizer architecture

### Entry point and layer layout

- **CONFIRMED FROM MENTAL OMEGA SOURCE** — `launcher_gui.py` is the application entry point.
- **CONFIRMED FROM MENTAL OMEGA SOURCE** — The source is split into `randomizer/application`, `config`, `core`, `launch`, `maps`, `missions`, `progression`, `rewards`, and `ui`. This is already close to the desired shared-core/game-adapter boundary.
- **CONFIRMED FROM MENTAL OMEGA SOURCE** — The UI uses Python Tk/Tkinter and controller-oriented modules rather than web UI technology.
- **CONFIRMED FROM MENTAL OMEGA SOURCE** — Background work communicates through a UI queue; worker threads do not directly mutate Tk widgets.
- **CONFIRMED FROM MENTAL OMEGA SOURCE** — Configuration uses YAML and JSON; run state uses compact JSON; persistent writes use atomic replacement patterns.

### File-level subsystem map

| Responsibility | Current MO implementation |
|---|---|
| Composition and window lifecycle | **CONFIRMED FROM MENTAL OMEGA SOURCE** — `launcher_gui.py`, `randomizer/application/app.py`, `_dependencies.py`, and `window.py` |
| Seed/run creation | **CONFIRMED FROM MENTAL OMEGA SOURCE** — `application/seed_controller.py`, `progression/state.py`, and `progression/grid.py` |
| Mission discovery/safety | **CONFIRMED FROM MENTAL OMEGA SOURCE** — `missions/catalogue.py`, `access.py`, `houses.py`, `overrides.py`, `safety.py`, and `tier_one.py` |
| Reward planning/state | **CONFIRMED FROM MENTAL OMEGA SOURCE** — `rewards/planning.py`, `catalogue.py`, `definitions.py`, `rules.py`, `roster.py`, `starting.py`, `weights.py`, and application reward/progression controllers |
| UI construction | **CONFIRMED FROM MENTAL OMEGA SOURCE** — `ui/builder.py`, `layout.py`, `settings.py`, `general_settings.py`, `grid.py`, `cameos.py`, `theme.py`, `tooltips.py`, and feature panels |
| INI/map pipeline | **CONFIRMED FROM MENTAL OMEGA SOURCE** — `maps/ini.py`, `pipeline.py`, `base.py`, `_shared.py`, `rules.py`, `settings.py`, and `houses.py` |
| Access/ownership/production | **CONFIRMED FROM MENTAL OMEGA SOURCE** — `maps/ownership.py`, `production.py`, `powers.py`, `special_buildings.py`, and access diagnostics |
| Buffs and cloning | **CONFIRMED FROM MENTAL OMEGA SOURCE** — `maps/clone_builder.py`, `clone_references.py`, `player_clones.py`, `country_buffs.py`, `weapon_buffs.py`, `power_buffs.py`, and validation/value modules |
| Completion instrumentation | **CONFIRMED FROM MENTAL OMEGA SOURCE** — `maps/hooks.py`, `progress_hooks.py`, and `application/launch_controller.py` |
| Paths/storage/diagnostics | **CONFIRMED FROM MENTAL OMEGA SOURCE** — `core/paths.py`, `storage.py`, `diagnostics.py`, and `version.py` |
| Static data | **CONFIRMED FROM MENTAL OMEGA SOURCE** — `configs/factions.json`, `missions.json`, `map_rules.json`, `tier_one.json`, `ui.json`, `configs/rewards/*.json`, and `Randomizer*.ini` files |

### Runtime flow

1. **CONFIRMED FROM MENTAL OMEGA SOURCE** — Resolve project/game paths and load static configuration, player configuration, and prior state.
2. **CONFIRMED FROM MENTAL OMEGA SOURCE** — Discover missions from the Mental Omega client's ordered battle catalogue.
3. **CONFIRMED FROM MENTAL OMEGA SOURCE** — Create deterministic run state from the seed and settings; named random streams keep subsystems reproducible.
4. **CONFIRMED FROM MENTAL OMEGA SOURCE** — Present missions through Classic, Mission List, or Grid progression.
5. **CONFIRMED FROM MENTAL OMEGA SOURCE** — Plan access rewards, buffs, powers, and mission assistance without immediately mutating the source map.
6. **CONFIRMED FROM MENTAL OMEGA SOURCE** — Extract a fresh map, apply ownership/access/buffs/hooks in an ordered pipeline, then write a loose generated map.
7. **CONFIRMED FROM MENTAL OMEGA SOURCE** — Write runtime launcher configuration and start `Syringe.exe gamemd.exe -SPAWN -CD -SPEEDCONTROL -LOG`.
8. **CONFIRMED FROM LOCAL RANDOMIZER** — Completion and reward state are persisted in `randomizer_state.json`; player settings are persisted in YAML.

### UI architecture and behavior

- **CONFIRMED FROM MENTAL OMEGA SOURCE** — Main window baseline is 1100×700, with scaling/capping behavior up to 1600×1000.
- **CONFIRMED FROM MENTAL OMEGA SOURCE** — Workspace navigation contains dynamic Classic/Mission List/Grid run views plus Settings, Advanced, and Archipelago areas.
- **CONFIRMED FROM MENTAL OMEGA SOURCE** — The mission information area has Details, Unlocks, and Enemy Rewards views.
- **CONFIRMED FROM MENTAL OMEGA SOURCE** — Unlocks are divided into Allies, Soviets, Epsilon, Foehn, Neutral, and Summary tabs.
- **CONFIRMED FROM MENTAL OMEGA SOURCE** — Advanced controls are divided into Missions, Units/Buildings, Superpowers, Unit Buffs, Superpower Buffs, and Starting Unlocks.
- **CONFIRMED FROM MENTAL OMEGA SOURCE** — Settings cover seed/run creation, mission appearance and pool, reward pool, randomizer arsenal, unit/building buffs, superweapon buffs, weights, mission assistance, and appearance/hidden options.
- **CONFIRMED FROM MENTAL OMEGA SOURCE** — The Archipelago area contains connection/status, player YAML, activity, and chat controls.
- **CONFIRMED FROM MENTAL OMEGA SOURCE** — The same UI components drive seed entry, run creation, mission selection, mission start, progression display, reward/unlock inspection, status reporting, and error dialogs.
- **NEEDS LIVE TEST** — Exact rendering, theme colors, spacing at all DPI settings, tooltip timing, and every dialog path were source-audited but not visually smoke-tested in this assignment.

### Where the UI gets data

| UI data | Current source | DTA replacement |
|---|---|---|
| Mission order, IDs, paths, sides | **CONFIRMED FROM MENTAL OMEGA SOURCE** — `INI/BattleClient.ini` `[Battles]` and mission sections | **CONFIRMED FROM DTA SOURCE** — `INI/Battle.ini` `[Battles]` and mission sections |
| Mission objective text | **CONFIRMED FROM MENTAL OMEGA SOURCE** — parsed from `LongDescription` `Objective N:` text | **INFERRED** — DTA needs mission-specific briefing/trigger extraction or curated metadata; no equivalent uniform objective text was found |
| Factions, units, buildings, powers, weights, exceptions | **CONFIRMED FROM MENTAL OMEGA SOURCE** — static JSON/config files plus Rules data | **CONFIRMED FROM DTA SOURCE** — generate catalogues from `INI/Rules.ini`, DTA house/side lists, and small DTA exception config |
| Run/progression state | **CONFIRMED FROM LOCAL RANDOMIZER** — `randomizer_state.json` | **INFERRED** — reuse unchanged schema with game/adaptor identity and DTA IDs |
| Player settings | **CONFIRMED FROM LOCAL RANDOMIZER** — player YAML | **INFERRED** — reuse schema; replace MO-only fields/catalogues |
| Mission completion | **CONFIRMED FROM MENTAL OMEGA SOURCE** — injected map hooks plus debug watcher | **CONFIRMED FROM DTA SOURCE** — first use DTA score-screen log signal; add objectives later |
| Cameos and art | **CONFIRMED FROM MENTAL OMEGA SOURCE** — MIX extraction, renderer DLLs, PCX conversion, cache, generated art aliases | **INFERRED** — keep loader/cache/UI interfaces, replace DTA asset lookup and inheritance resolution |
| Launch status | **CONFIRMED FROM MENTAL OMEGA SOURCE** — process watcher and log parsing | **INFERRED** — reuse watcher structure with `LaunchVinifera.dat` and DTA debug log adapter |

## Local Mental Omega versus GitHub

- **CONFIRMED FROM MENTAL OMEGA SOURCE** — Tracked local source and GitHub are identical at commit `099aa086c7cbc5366649ae07bebe23018aecaa08`; there are no tracked modified, local-only, or GitHub-only source files at this audit point.
- **CONFIRMED FROM LOCAL RANDOMIZER — RUNTIME GENERATED** — `randomizer_state.json`, player YAML, extracted/generated maps, logs, cameo cache, self-check output, bytecode caches, build output, distribution output, and releases are intentionally ignored.
- **CONFIRMED FROM LOCAL RANDOMIZER — CONFIGURATION ONLY** — Local ignored player YAML and state describe this installation/run, not a more recent application implementation.
- **CONFIRMED FROM LOCAL RANDOMIZER — LOCAL IS NEWER** — Ignored `PROJECT_CONTEXT.md` and `AGENTS.md` contain local working/development guidance not present in the repository, but they do not change executable tracked behavior.
- **UNKNOWN** — None for tracked-source parity at the audited commit.
- **CONFIRMED FROM LOCAL RANDOMIZER** — The important local/GitHub distinction is runtime evidence and ignored documentation, not an uncommitted code fork.

## Reuse and replacement matrix

| Component | Classification | Reuse for DTA | Required change |
|---|---|---:|---|
| Tk UI shell, navigation, layouts | **GAME-INDEPENDENT — CONFIRMED FROM MENTAL OMEGA SOURCE** | Yes | Supply DTA labels, catalogues, images, and adapter state |
| Seed and named RNG streams | **GAME-INDEPENDENT — CONFIRMED FROM MENTAL OMEGA SOURCE** | Yes | Add game identity/version to compatibility metadata |
| Classic/List/Grid progression | **GAME-INDEPENDENT — CONFIRMED FROM MENTAL OMEGA SOURCE** | Yes | DTA mission IDs and DTA pool validation |
| Reward planner and presentation | **MOSTLY GAME-INDEPENDENT — CONFIRMED FROM MENTAL OMEGA SOURCE** | Yes | Replace catalogue, constraints, and application back end |
| Atomic YAML/JSON persistence | **GAME-INDEPENDENT — CONFIRMED FROM MENTAL OMEGA SOURCE** | Yes | Namespace/migrate per game |
| Async UI queue/process watcher | **GAME-INDEPENDENT — CONFIRMED FROM MENTAL OMEGA SOURCE** | Yes | DTA process and log signatures |
| Order-preserving `IniLines` map editing | **ENGINE-ADJACENT — CONFIRMED FROM MENTAL OMEGA SOURCE** | Likely | Validate packed/long DTA maps and DTA semantics |
| Mission exception registry | **GAME-INDEPENDENT PATTERN — CONFIRMED FROM MENTAL OMEGA SOURCE** | Yes | New DTA entries only after evidence |
| Mission discovery | **MO/CLIENT-SPECIFIC — CONFIRMED FROM MENTAL OMEGA SOURCE** | Replace | Parse `INI/Battle.ini` and DTA metadata |
| MIX map extraction | **MO-SPECIFIC — CONFIRMED FROM LOCAL RANDOMIZER** | No for missions | DTA campaign maps are already loose; copy originals |
| Syringe/gamemd launch | **YR/MO-LAUNCHER-SPECIFIC — CONFIRMED FROM MENTAL OMEGA SOURCE** | No | DTA spawn writer plus `LaunchVinifera.dat` |
| Objective/victory hooks | **YR/ARES/MO-SPECIFIC — CONFIRMED FROM MENTAL OMEGA SOURCE** | Replace | DTA completion log first; separate DTA objective strategy |
| Access rules | **ARES/PHOBOS/MO-SPECIFIC — CONFIRMED FROM MENTAL OMEGA SOURCE** | Planner only | TS/Vinifera `Owner`, `RequiredHouses`, `ForbiddenHouses`, `Prerequisite`, `TechLevel` adapter |
| Clone/buff writer | **YR/ARES/PHOBOS-SPECIFIC — CONFIRMED FROM MENTAL OMEGA SOURCE** | Do not port initially | House modifiers first; selective DTA strategy later |
| Superpower rewards | **ENGINE-SPECIFIC — CONFIRMED FROM MENTAL OMEGA SOURCE** | UI/planner only | DTA's nine SuperWeaponTypes and provider buildings |
| Cameo extraction | **GAME-ASSET-SPECIFIC — CONFIRMED FROM MENTAL OMEGA SOURCE** | Interface/cache yes | DTA MIX/INI/image lookup implementation |
| Archipelago integration | **MOSTLY GAME-INDEPENDENT — CONFIRMED FROM MENTAL OMEGA SOURCE** | Later | DTA item/location model; not prototype scope |

### MO/YR/Ares/Phobos assumptions that must not leak into DTA

- **CONFIRMED FROM MENTAL OMEGA SOURCE** — MO access and clones rely on features such as Ares/Phobos ownership/prerequisite behavior, `FactoryOwners.Forbidden`, `Prerequisite.Negative`, generic warheads, attach effects, and MO-specific art aliases.
- **CONFIRMED FROM MENTAL OMEGA SOURCE** — MO uses `rulesmo.ini`, `RA2MO.ini`, `RA2MD.INI`, `BattleClient.ini`, `gamemd.exe`, `Syringe.exe`, and MO MIX/cameo layout.
- **CONFIRMED FROM MENTAL OMEGA SOURCE** — MO objective recognition depends on MO-authored action/signature conventions (`ObjectiveComplete`, `EVA_ObjectiveComplete`, and `Mission:ObjC`) and a debug-visible marker TeamType.
- **CONFIRMED FROM DTA SOURCE** — None of those filenames or objective conventions are the DTA campaign contract.

## DTA engine and client baseline

| Item | Finding |
|---|---|
| Game | **CONFIRMED FROM DTA SOURCE** — Dawn of the Tiberium Age 15.1.0 |
| Engine executable | **CONFIRMED FROM DTA SOURCE** — `game.exe`, Tiberian Sun 2.03 |
| Engine extension | **CONFIRMED FROM DTA SOURCE** — `Vinifera.dll` 0.1.0.0, product `0.1.0.0 (f4d33ac5)` |
| Injector/launcher | **CONFIRMED FROM DTA SOURCE** — `LaunchVinifera.dat` |
| Main launcher | **CONFIRMED FROM DTA SOURCE** — `DTA.exe` 2.0.0.2 |
| CnCNet client | **CONFIRMED FROM DTA SOURCE** — `Resources/clientdx.exe` 2.13.4.6 |
| Client definition | **CONFIRMED FROM DTA SOURCE** — executable `LaunchVinifera.dat`, extra argument `-CD.`, sidebar hack enabled, campaign file `BattleE.ini` |
| Rules | **CONFIRMED FROM DTA SOURCE** — INI data, principally `INI/Rules.ini`, with Vinifera extensions and map-local overrides |
| Campaign catalogue | **CONFIRMED FROM DTA SOURCE** — `INI/Battle.ini`; `BattleE.ini` is the localized/augmenting client path |
| Mission format | **CONFIRMED FROM DTA SOURCE** — loose TS INI-format `.map` files under `Maps/Missions` |
| Runtime scenario | **CONFIRMED FROM DTA SOURCE** — client-generated root `spawnmap.ini` selected by root `spawn.ini` |

## DTA mission discovery

- **CONFIRMED FROM DTA SOURCE** — `INI/Battle.ini` `[Battles]` contains 98 ordered entries including headers and spacers.
- **CONFIRMED FROM DTA SOURCE** — 81 entries resolve to 81 unique `Scenario` paths, and all 81 installed files exist.
- **CONFIRMED FROM DTA SOURCE** — Side distribution is GDI/side 0: 18; Nod/side 1: 5; Allies/side 2: 37; Soviet/side 3: 21.
- **CONFIRMED FROM DTA SOURCE** — Mission metadata includes `Scenario`, `Description`/`UIName`, `Side`, `IconPath`, `PreviewImagePath`, `LongDescription`, `RequiredAddon`, `RequiresUnlocking`, direct and conditional unlocks, campaign globals, difficulty behavior, cutscenes, and bonus-campaign ID where applicable.
- **CONFIRMED FROM DTA SOURCE** — 57 missions are marked locked (`yes` or `true`); 24 omit `RequiresUnlocking`.
- **CONFIRMED FROM DTA SOURCE** — 74 missions require the addon flag and 7 omit it.
- **CONFIRMED FROM DTA SOURCE** — `M_ERADICATING_THE_RED` exists but is commented out of the ordered battle list; discovery must follow `[Battles]`, not every section containing `Scenario`.
- **CONFIRMED FROM DTA SOURCE** — `INI/Campaigns.ini` defines campaign-global/UI data, but its `[Campaigns]` registration is commented/empty. It is not the canonical mission list.
- **CONFIRMED FROM DTA SOURCE** — `MapSel.ini`/`MapSel01.ini` are legacy in-game selection data and are not the current client catalogue.
- **INFERRED** — Implement DTA discovery as an ordered `Battle.ini` adapter and retain headers/groups separately from playable records.

### Preliminary mission-mode signals

- **INFERRED** — Static starting-object analysis finds 22 missions with a starting Construction Yard/MCV signal, 3 with a production-building-only signal, and 56 without a static production signal.
- **NEEDS LIVE TEST** — These are not final base-build/no-build classifications. Missions can create, transfer, capture, or unlock production through triggers, so the result needs trigger-aware analysis and representative play tests.

## DTA map format and map generation

- **CONFIRMED FROM DTA SOURCE** — All catalogued missions are loose files; no MIX extraction is needed for the first DTA mission pipeline.
- **CONFIRMED FROM DTA SOURCE** — Maps contain standard TS sections including `Basic`, `Briefing`, `Events`, `Actions`, `Triggers`, `Tags`, house definitions, `TaskForces`, `ScriptTypes`, `TeamTypes`, placed objects, and packed map data.
- **CONFIRMED FROM DTA SOURCE** — Every catalogued mission has `[Briefing]`; no uniform `[Objectives]` or `[MissionObjectives]` section was found.
- **CONFIRMED FROM DTA SOURCE** — No duplicate section headers were found across the 81 catalogued maps.
- **CONFIRMED FROM DTA SOURCE** — Every parsed `[Actions]` record contains a count followed by exactly eight fields per action. Counts from 1 through 16 were observed, with zero malformed records.
- **CONFIRMED FROM MENTAL OMEGA SOURCE** — The MO action-line parser also uses eight fields per action, so the record splitter is structurally reusable.
- **INFERRED** — Reuse the splitter but replace action-ID and parameter semantics; DTA NeedCodes and action meanings are not MO meanings.
- **CONFIRMED FROM VINIFERA SOURCE** — Vinifera documents the eight fields as action type, NeedCode, parameters 1–5, and optional parameter 6.
- **CONFIRMED FROM DTA SOURCE** — Longest observed entire map line is 502 bytes; longest observed `[Actions]` line is 361 bytes.
- **INFERRED** — Preserve the MO conservative line-length guard, but validate the actual installed TS/Vinifera parser limit before accepting generated lines near it.
- **CONFIRMED FROM MENTAL OMEGA SOURCE** — `IniLines` preserves section/key order, comments, and repeated registrations better than Python `configparser`; this remains the correct base abstraction.
- **NEEDS LIVE TEST** — Run the existing parser over all 81 DTA maps in a round-trip byte/semantic test, especially packed sections, comments, empty values, and case-insensitive filenames.

### Minimal DTA generation design

1. **INFERRED** — Copy the selected source map to a temporary working map; never edit `Maps/Missions` in place.
2. **CONFIRMED FROM DTA SOURCE** — Consolidate the matching `INI/Map Code/Difficulty Easy|Medium|Hard.ini` file as the DTA client does.
3. **INFERRED** — Apply randomizer-generated map-local rules and hooks through a DTA-specific ordered pipeline.
4. **CONFIRMED FROM DTA SOURCE** — Force `[Basic] EndOfGame=true` and `SkipScore=false` when relying on the DTA completion detector.
5. **CONFIRMED FROM DTA SOURCE** — Write the result to root `spawnmap.ini` and set `Scenario=spawnmap.ini` in root `spawn.ini`.
6. **NEEDS LIVE TEST** — First experiment should make only a harmless, visible change such as starting credits +100, then launch one simple campaign mission.

## DTA data, factions, access, and superweapons

- **CONFIRMED FROM DTA SOURCE** — DTA registers four primary playable houses (`GDI`, `Nod`, `Allies`, `Soviet`), Neutral/Special houses, and multiple mission/AI derivatives such as `GDI1`, `Nod1`, `Allies1`, and `Soviet1`.
- **CONFIRMED FROM DTA SOURCE** — Sides are `GDISide`, `NodSide`, `AlliesSide`, `SovietSide`, `CivilianSide`, and `SpecialSide`; this is not the MO faction model.
- **CONFIRMED FROM DTA SOURCE** — `INI/Rules.ini` registers `InfantryTypes`, `VehicleTypes`, `AircraftTypes`, `BuildingTypes`, and `SuperWeaponTypes`.
- **CONFIRMED FROM DTA SOURCE** — Access-relevant fields in active DTA data include `Owner`, `RequiredHouses`, `ForbiddenHouses`, `Prerequisite`, `TechLevel`, and `BuildLimit`.
- **CONFIRMED FROM DTA SOURCE** — DTA defines custom prerequisite groups such as `TDTECH`, `RATECH`, `SERVICE`, `REFINERY`, `PYLE/RABARR`, and `GDIHELIPAD`.
- **CONFIRMED FROM VINIFERA SOURCE** — Public Vinifera implements custom prerequisite groups and ports `RequiredHouses`/`ForbiddenHouses` behavior.
- **INFERRED** — A DTA technology catalogue should be generated from registrations plus resolved section inheritance (`BaseSection`/DTA INI system), not hand-written.
- **INFERRED** — Unlocks should modify the human house's eligibility while leaving global type identity and scripted teams intact. The exact combination of `Owner`, house filters, prerequisites, and TechLevel needs a per-category policy.
- **NEEDS LIVE TEST** — Test access changes against human sidebar production, AI production, preplaced units, captured factories, scripted reinforcement teams, and mission-specific houses before enabling rewards generally.
- **CONFIRMED FROM DTA SOURCE** — DTA registers nine superweapon types: Multi, EMPulse, Firestorm, Ion Cannon, Hunter Seeker, Chemical, Drop Pod, Airstrike, and Vortex variants.
- **CONFIRMED FROM DTA SOURCE** — Provider buildings use `SuperWeapon=` and the SuperWeaponType sections define recharge, type, sidebar image, action, and weapon settings.
- **INFERRED** — Superweapon rewards require a DTA-specific provider/buildability strategy; the MO power catalogue and Ares/Phobos grant logic cannot be reused directly.

## Existing DTA launch solution

### Client preparation

- **CONFIRMED FROM DTA SOURCE** — The 2.13-era `CampaignHandler.WriteFilesForMission` already writes root `spawn.ini` with scenario, game speed, addon flag, loading screen, single-player mode, sidebar hack, side, build-off-ally, human/computer difficulty, mission identity, and optional bonus.
- **CONFIRMED FROM DTA SOURCE** — With `CopyMissionsToSpawnmapINI` enabled (the default, and not overridden by installed client definitions), the client selects `spawnmap.ini` rather than the original scenario path.
- **CONFIRMED FROM DTA SOURCE** — It loads the source mission, consolidates difficulty INI, applies optional normal-difficulty modifiers/bonus values, forces score-screen-compatible Basic flags, applies forced-side/global-specific values, and writes root `spawnmap.ini`.
- **CONFIRMED FROM DTA SOURCE** — DTA progression is stored in base64-encoded INI data at `Client/spscore.dat`, with backup `Client/spscore_backup.dat`; sections cover missions, globals, and bonuses.
- **INFERRED** — The randomizer should not reuse DTA's `spscore.dat` as its own run state. It should reuse the launch/result mechanics while keeping randomizer state isolated.

### Executable sequence

- **CONFIRMED FROM DTA SOURCE** — Client configuration selects `LaunchVinifera.dat` and appends `-CD.`.
- **CONFIRMED BY LIVE TEST** — A local skirmish client log records the client writing `spawn.ini` and a map, then starting `LaunchVinifera.dat -SPAWN -CD.`, waiting for exit, and parsing the Debug log.
- **CONFIRMED BY LIVE TEST** — The resulting engine Debug log records startup of `spawnmap.ini` and Vinifera initialization.
- **CONFIRMED BY USER LIVE TEST** — `LaunchVinifera.dat -SPAWN -CD.` with the DTA root as working directory started generated PTTP #6 directly from Mission List.
- **NEEDS LIVE TEST** — The exact direct campaign command has source and skirmish evidence but has not been executed for a generated campaign map in this assignment.
- **INFERRED** — Do not launch `game.exe` directly; doing so would bypass Vinifera injection and the installed DTA engine contract.

## Triggers, victory, and objectives

### Installed DTA action evidence

- **CONFIRMED FROM DTA SOURCE** — Installed FinalSun definitions identify action 1 as `Winner is...`, action 2 as `Loser is...`, action 11 as text, action 21 as speech, actions 28/29 as global set/clear, actions 53/54 as trigger enable/disable, and action 56 as local set.
- **CONFIRMED FROM DTA SOURCE** — Across all 81 missions, every map has action 1; 79 have action 2; one uses action 67 `Announce Win`; two use action 68 `Announce Lose`; none use action 15 `Allow Win` or action 69 `Force end`.
- **CONFIRMED FROM DTA SOURCE** — There are 83 action-1 occurrences because `CR07` and `Reunification` contain two victory branches.
- **CONFIRMED FROM DTA SOURCE** — Action 80 (team creation) is extremely common, appearing 5,349 times; team/task-force identity is therefore a high-risk area for clone rewriting.

### Recommended victory detector

- **CONFIRMED FROM DTA SOURCE** — DTA's campaign handler forces `EndOfGame=true` and `SkipScore=false`, then treats a Debug-log line starting with `ScoreScreen: Loaded ` as successful completion.
- **CONFIRMED FROM DTA SOURCE** — The same post-game pass reads `Global variables: ` and updates conditional campaign progression.
- **INFERRED** — Reuse this completion signal for the first DTA prototype rather than inject a marker into 83 separate victory branches.
- **NEEDS LIVE TEST** — Verify on installed 2.13.4.6 with one victory, one defeat, one restart, one abort, and one load/save continuation. Confirm log selection/rotation and stale-line rejection.
- **INFERRED** — Store launch start time/session ID and parse only the current run's log region so an old score-screen line cannot grant a false win.

### Objective detection

- **CONFIRMED FROM DTA SOURCE** — DTA has no uniform objective section across the campaign maps; objective presentation uses per-map briefing, tutorial text, speech, globals/locals, named triggers, and mission-specific logic.
- **CONFIRMED FROM MENTAL OMEGA SOURCE** — MO's objective signature matcher is authored around MO/YR conventions and cannot be considered a DTA detector.
- **NEEDS LIVE TEST** — The MO debug marker TeamType method depends on the engine emitting a searchable team name. The available DTA skirmish log did not prove that behavior.
- **CONFIRMED FROM VINIFERA SOURCE** — Current public Vinifera developer mode can log executed trigger actions and exposes variable-oriented trigger actions, but availability and production-log behavior in installed DTA are unproven.
- **INFERRED** — Ship mission-completion rewards first. Add optional objectives only through a DTA objective registry backed by map-specific evidence, then research a generic instrumentation hook.

## Player-only buffs and the clone question

### Existing DTA solution: difficulty/house modifiers

- **CONFIRMED FROM DTA SOURCE** — `INI/Rules.ini` difficulty sections expose `Groundspeed`, `Airspeed`, `BuildTime`, `Armor`, `ROF`, `Cost`, `Firepower`, repair/build delays, and related flags.
- **CONFIRMED FROM DTA SOURCE** — `INI/CampaignBonuses.ini` registers 31 bonus names, of which 23 currently have definitions. Defined bonuses combine the same difficulty multipliers.
- **CONFIRMED FROM DTA SOURCE** — The 2.13-era client writes a selected bonus into the generated map's `[Normal]` difficulty section.
- **INFERRED** — Cumulative randomizer buffs can calculate one combined `[Normal]` section, giving the human player broad modifiers while leaving computer difficulty separate.
- **NEEDS LIVE TEST** — Verify which human house receives `[Normal]` in every mission/difficulty combination, especially missions with `PlayerAlwaysOnNormalDifficulty`, forced sides, allies, captured units, and multiple human-controlled house definitions.
- **NEEDS LIVE TEST** — Verify multiplier composition and displayed semantics. DTA's base values are not all 1.0 (`Groundspeed=0.9`, `ROF=0.91`), so rewards must modify from DTA baseline rather than replace it with MO assumptions.

### Vinifera runtime alternative

- **CONFIRMED FROM VINIFERA SOURCE** — Current public Vinifera action 135 adjusts the triggering house's Firepower, Armor, Groundspeed, Airspeed, ROF, Cost, or Build Time bias by percentage points.
- **CONFIRMED FROM VINIFERA SOURCE** — The implementation mutates the supplied `HouseClass` bias, so it avoids changing TechnoType IDs.
- **CONFIRMED FROM DTA SOURCE** — Installed `Vinifera.dll` contains `Adjust House Modifier` and its description in the extended action table. Installed FinalSun data is stale and does not expose it in the editor UI.
- **NEEDS LIVE TEST** — Do not generate action 135 until a minimal installed-build map proves parsing, execution, save/load, and intended house selection.
- **INFERRED** — Action 135 is useful for broad rewards obtained during a mission; generated difficulty sections remain simpler for pre-mission cumulative broad rewards.

### What broad modifiers cannot do

- **CONFIRMED FROM VINIFERA SOURCE** — House biases are broad; they do not target a single TechnoType.
- **INFERRED** — A reward such as “all player units +10% armor” fits the house approach. “Only the player's Medium Tank +25% strength” does not.
- **CONFIRMED FROM VINIFERA SOURCE** — Techno instances have internal firepower/armor/speed bias fields, and damage calculation combines instance and house firepower bias. Public mapping/INI APIs expose house adjustment and veterancy, but no arbitrary per-type/per-owner setter.
- **CONFIRMED FROM DTA SOURCE** — Installed binary metadata likewise exposes `Adjust House Modifier` and `Make Elite`; no Techno-specific modifier action or INI key was found.
- **INFERRED** — A clean `RIFLEMAN owned by human = +25% damage` rule would require new Vinifera engine code. It is not available to a map-only randomizer.

### Mandatory unit-specific buff policy

- **INFERRED** — Never replace TechnoType IDs in placed map objects. Player, allied, neutral, and enemy `[Infantry]`, `[Units]`, `[Aircraft]`, and `[Structures]` entries remain unchanged.
- **INFERRED** — Never rewrite mission-authored TaskForces, TeamTypes, triggers, actions, tags, scripts, AI teams, or reinforcement definitions to use a player clone.
- **INFERRED** — Before modifying the original type, scan the complete mission for any non-player use. “Present on the map” includes placed objects, TaskForces, scripted reinforcements, AI triggers/production, trigger-created types, and any non-player house able to produce it.
- **INFERRED** — Scan shared dependencies too. A damage change must not modify a weapon/warhead/projectile also used by a non-player type; duplicate only the required dependency where possible.
- **INFERRED** — Uncertain analysis counts as a collision.
- **INFERRED** — With no non-player collision, the original TechnoType may receive a map-local reward. Its ID and every placed-object record remain unchanged.
- **INFERRED** — With any non-player collision, leave the original type unchanged. Create a clone restricted to the exact human house, remove the original only from human production eligibility, and give only newly produced human units the clone.
- **INFERRED** — Player starting/scripted units stay original and unbuffed in the collision case. Enemy/map units stay original and unbuffed.
- **INFERRED** — If exact human-house production routing cannot be proven, or the mission has no usable production path, suppress that reward for the mission.

### Implemented Vinifera production-clone route

- **CONFIRMED FROM VINIFERA SOURCE** — `RequiredHouses` limits production to listed houses and `ForbiddenHouses` blocks listed houses from producing the original type.
- **CONFIRMED FROM LOCAL RANDOMIZER** — `randomizer/dta/clones.py` performs the conservative collision scan, leaves authored map and mission identities untouched, and emits map-local production clones restricted to the exact human house.
- **CONFIRMED FROM LOCAL RANDOMIZER** — Damage and reload rewards duplicate the target weapon before changing `Damage` or `ROF`, preventing a shared weapon from buffing unrelated units.
- **CONFIRMED FROM LOCAL RANDOMIZER** — Clone generation refuses collision cases without a usable human production path and currently refuses deploy/undeploy-linked identities.
- **CONFIRMED FROM LOCAL RANDOMIZER** — The self-check generates a `3TNK_PLAYER` clone for PTTP #6, keeps authored map objects unchanged, forbids Soviet production of the original, and requires Soviet ownership for the clone.
- **CONFIRMED BY LIVE TEST** — Installed Vinifera accepted a map-local `E1A_PLAYER` InfantryType plus private weapon, applied scenario overrides, and entered interactive PTTP #6 gameplay.
- **NEEDS LIVE TEST** — Confirm the clone appears once on the sidebar, only the human can build it, map and scripted units remain original, and save/load preserves the map-local type.

### Implemented first access category

- **CONFIRMED FROM LOCAL RANDOMIZER** — The reward catalogue exposes 105 canonical mobile-unit access rewards generated from installed `Rules.ini` data. Eleven essential mobile types remain permanently available, and obsolete mission aliases are excluded.
- **CONFIRMED FROM LOCAL RANDOMIZER** — `randomizer/dta/access.py` adds only the exact human house to unearned originals' `ForbiddenHouses`; it does not change enemy houses or authored identities.
- **CONFIRMED FROM LOCAL RANDOMIZER** — Earned foreign infantry uses an exact-house `_PLAYER` production clone when the original cannot be produced by the human house. Native originals remain available without cloning when possible.
- **CONFIRMED FROM LOCAL RANDOMIZER** — Standard and Chaos seed-planning checks assign mobile-unit access before any dependent unit-specific buff. Generated-map checks preserve the source map byte-for-byte.
- **CONFIRMED BY LIVE TEST** — PTTP #6 loaded with 57 InfantryTypes after the map-local access clone was added to the 56 installed types. The debug log reached interactive gameplay and the source map remained byte-identical.
- **NEEDS LIVE TEST** — Confirm sidebar, factory, capture, and save/load behavior before extending the adapter to vehicles or aircraft.

### Implemented mission difficulty translation

- **CONFIRMED FROM DTA SOURCE** — Installed missions expose three- and four-position selectors with mission-specific `DifficultyLabels`, including Brutal, Extreme, Ultimate, and Impossible.
- **CONFIRMED FROM DTA SOURCE** — DTA maps non-extended selector positions to client ranks 10, 30, and 40, and extended positions to 10, 20, 30, and 40. Those ranks map to Tiberian Sun engine values 0, 1, 1, and 2.
- **CONFIRMED FROM LOCAL RANDOMIZER** — The launcher offers every installed semantic difficulty label. Exact mission labels are used when available; otherwise the closest lower supported label is selected, or the mission's lowest label when no lower label exists.
- **CONFIRMED FROM LOCAL RANDOMIZER** — All 81 missions resolve successfully for all seven global choices. The launch contract writes the selected display label, client rank, and engine value.
- **NEEDS LIVE TEST** — Confirm gameplay scaling for representatives of every installed label set and for `PlayerAlwaysOnNormalDifficulty` missions.

Expected collision-case result:

```text
Enemy/map RIFLEMAN: original, normal damage
Player starting/map RIFLEMAN: original, normal damage
Player newly produced RIFLEMAN_PLAYER: +25% damage
```

### Clone/replacement risks

| Risk | Assessment |
|---|---|
| Preplaced tagged objects | **INFERRED** — Replacement is prohibited; exact-type event and tag behavior cannot be risked |
| TaskForce and team creation | **CONFIRMED FROM DTA SOURCE** — TaskForces contain exact type IDs and action 80 is pervasive; replacing only placed units misses reinforcements, while replacing task forces can alter AI/enemy teams |
| Scripted reinforcement/production | **INFERRED** — Original IDs referenced by teams or AI production remain unbuffed unless rewritten; broad rewriting risks enemy spillover |
| Type-count/destruction conditions | **INFERRED** — Conditions that count or destroy a specific type can fail when originals are replaced with clones |
| Owner/house restrictions | **CONFIRMED FROM DTA SOURCE** — Clones need correct `Owner`, `RequiredHouses`, `ForbiddenHouses`, prerequisites, TechLevel, and side behavior |
| Factory/sidebar behavior | **INFERRED** — A clone can create duplicate cameos, wrong sorting, build-limit changes, or captured-factory access differences |
| Weapon-only duplication | **INFERRED** — Safer than unit cloning for damage/ROF only when a player-only way exists to bind the duplicate weapon; otherwise the unit type still must differ |
| Art/image/inheritance | **CONFIRMED FROM DTA SOURCE** — DTA uses `BaseSection`, `Image`, and sidebar-image data; a clone must resolve these correctly |
| Save/load and engine heaps | **NEEDS LIVE TEST** — Dynamically added map-local types and their references must survive save/load and Vinifera serialization |

### Ranked buff strategy

1. **CONFIRMED FROM DTA SOURCE** — Use generated human difficulty/house modifiers for broad buffs.
2. **NEEDS LIVE TEST** — Use Vinifera action 135 for broad mid-mission rewards only after installed-build execution is proven.
3. **INFERRED** — For unit-specific rewards, modify the original only when the complete mission/dependency scan proves no non-player collision.
4. **INFERRED** — Duplicate only shared weapons/warheads/projectiles when that prevents unrelated-type bleed without a TechnoType clone.
5. **INFERRED** — When collision exists, create a human-production-only TechnoType clone. Never replace map objects or mission-authored references.
6. **INFERRED** — Suppress unsafe/inapplicable rewards. Do not port the full MO clone system.

## Map-local rules and safe override boundary

- **CONFIRMED FROM DTA SOURCE** — DTA itself proves scenario-local difficulty overrides: the client consolidates difficulty/bonus sections into `spawnmap.ini` before launch.
- **CONFIRMED FROM DTA SOURCE** — Mission maps already contain rule-like type/house/trigger sections alongside map data.
- **INFERRED** — Map-local overrides are the correct first mechanism for temporary randomizer changes because they do not mutate installed global `INI/Rules.ini`.
- **NEEDS LIVE TEST** — For each reward category, prove that the installed engine loads the target section from a scenario and that save/load retains it.
- **INFERRED** — Always generate from a fresh original plus deterministic patches. Never reuse a previously generated map as input.
- **INFERRED** — Keep a manifest of changed sections/keys and validate all generated references before launch.

## Assets and cameos

- **CONFIRMED FROM DTA SOURCE** — Mission metadata already exposes campaign icons and preview paths; Rules/SuperWeapon data exposes sidebar image IDs.
- **CONFIRMED FROM MENTAL OMEGA SOURCE** — The current UI already has image lookup, extraction/conversion, caching, fallback, and display abstractions.
- **INFERRED** — Reuse those abstractions and cache behavior. Add a DTA resolver for MIX search order, `Image`/`BaseSection` inheritance, sidebar IDs, and PCX/SHP conversion.
- **NEEDS LIVE TEST** — Asset precedence and every DTA archive/search path have not yet been exhaustively mapped; do not rebuild the image system before a focused asset audit.

## Uncertainties and required experiments

| Priority | Experiment | Why it blocks progress |
|---:|---|---|
| 1 | **NEEDS LIVE TEST** — Copy one simple campaign map, add +100 starting credits, generate `spawn.ini`/`spawnmap.ini`, launch `LaunchVinifera.dat -SPAWN -CD.` from DTA root | Proves generated map and direct campaign launch |
| 2 | **NEEDS LIVE TEST** — Win, lose, abort, restart, and save/load that test mission while recording the exact Debug log | Proves reliable completion and stale-log handling |
| 3 | **NEEDS LIVE TEST** — Round-trip all 81 maps through `IniLines`; compare all untouched lines/sections and run parser validation | Proves parser reuse |
| 4 | **NEEDS LIVE TEST** — Apply one changed `[Normal]` modifier to a mission where human and AI share a native type | Proves broad player-only separation without clones |
| 5 | **NEEDS LIVE TEST** — Repeat modifier test on Easy/Normal/Hard/Brutal and a `PlayerAlwaysOnNormalDifficulty` mission | Proves difficulty mapping and baseline composition |
| 6 | **NEEDS LIVE TEST** — Test action 135 in a disposable generated map | Determines whether installed custom Vinifera supports the public feature |
| 7 | **NEEDS LIVE TEST** — Unlock one infantry, vehicle, building, and superweapon through map-local rules; inspect human/AI/script/capture behavior | Establishes safe technology adapter rules |
| 8 | **NEEDS LIVE TEST** — Add a uniquely named harmless TeamType/action and inspect production Debug logs | Determines whether MO-style marker observation is possible |
| 9 | **NEEDS LIVE TEST** — Select representative static base-build, production-only, and no-production missions and trace trigger-granted assets | Produces trustworthy mission classifications |
| 10 | **UNKNOWN** — Find or build an exact source map for installed Vinifera hash `f4d33ac5` | Removes public/installed capability ambiguity |
| 11 | **NEEDS LIVE TEST** — Test one human-production-only clone while verifying placed objects, TaskForces, scripted reinforcements, exact-type events, and captures remain original | Proves mandatory clone isolation without touching mission objects |
| 12 | **NEEDS LIVE TEST** — Audit DTA MIX/assets and render representative infantry, vehicle, building, superweapon, campaign, and fallback icons | Completes UI data substitution |

## Recommended implementation order

1. **INFERRED** — Introduce a narrow game-adapter interface around mission discovery, map preparation, launch, completion, catalogues, assets, access, and buffs; do not perform a broad refactor.
2. **INFERRED** — Implement a read-only DTA mission diagnostic using `INI/Battle.ini` and verify all 81 records.
3. **INFERRED** — Reuse and extend `IniLines`; add DTA action semantics and full-campaign round-trip tests.
4. **INFERRED** — Implement the minimal fresh-copy `spawnmap.ini` generator and exact DTA `spawn.ini` writer.
5. **INFERRED** — Prove direct campaign launch through `LaunchVinifera.dat -SPAWN -CD.`.
6. **INFERRED** — Implement session-scoped score-screen victory detection and preserve the original map's win/lose triggers.
7. **INFERRED** — Connect DTA missions to the existing Mission List/Classic/Grid UI without reward mutation.
8. **INFERRED** — Generate DTA faction, TechnoType, building, superweapon, and cameo catalogues from installed data.
9. **INFERRED** — Add access rewards one category at a time with human/AI/script regression tests.
10. **INFERRED** — Add broad house/difficulty buffs; establish cumulative multiplier math from DTA baselines.
11. **INFERRED** — Research type-specific player buffs and allow selective clones only behind validated per-map/per-type safety rules.
12. **INFERRED** — Add optional objective hooks after the mission-completion loop is reliable.
13. **INFERRED** — Add Archipelago and advanced reward categories last.

## Blocking milestone status

| Milestone | Status |
|---|---|
| Existing UI understood | **CONFIRMED FROM LOCAL RANDOMIZER** — architecture and data flow understood; headless visual smoke test passes |
| DTA mission discovery | **CONFIRMED FROM DTA SOURCE** — 81 ordered installed missions enumerated |
| Generated DTA map loads | **NEEDS LIVE TEST** |
| Direct DTA campaign launch | **CONFIRMED BY USER LIVE TEST** — PTTP #6 started directly without opening the DTA client |
| Victory detection | **NEEDS LIVE TEST** — DTA's existing detector is identified |
| Player-only buff strategy | **NEEDS LIVE TEST** — broad house modifiers, mandatory unit-specific production clones, and mobile-unit access isolation are implemented; full production routing needs proof |
| Infantry access | **NEEDS LIVE TEST** — generated clone parsing and gameplay entry are live-confirmed; sidebar, capture, production, and save/load behavior need proof |

## Final porting decision

- **INFERRED** — Proceed with a DTA adapter and minimal shared-core seams, not a new application.
- **INFERRED** — Reuse the existing UI and progression immediately after direct launch and victory tests pass.
- **INFERRED** — Reuse DTA's campaign-handler design for spawn generation, difficulty consolidation, and result parsing rather than copying the MO launcher/hook path.
- **CONFIRMED FROM LOCAL RANDOMIZER** — Broad DTA house modifiers, mandatory unit-specific production clones, and mobile-unit access are integrated into the existing reward flow.
- **NEEDS LIVE TEST** — Verify clone routing, infantry production/save-load, score-screen completion, and cumulative modifiers before enabling the remaining unsafe reward families.
