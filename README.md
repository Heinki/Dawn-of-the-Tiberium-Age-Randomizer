<img src="DTA%20Puzzle.png" alt="Dawn of the Tiberium Age Randomizer Launcher puzzle logo" width="500">

# Dawn of the Tiberium Age Randomizer Launcher

This project is the randomizer launcher for DTA 15.1.0 and Vinifera. It reuses the proven progression, reward-planning, launcher UI, save/load, and Archipelago structure from the Mental Omega Randomizer, while using DTA missions, factions, units, powers, rules, maps, cameos, difficulty handling, and launch behavior.

## Current DTA integration

- Reads all 81 installed campaign entries from `INI/Battle.ini`.
- Groups missions by the installed DTA campaigns: Tutorial, PTTP, CR, Toxic Diversion, It Came From Red Alert!, Creeping Destruction, and Special Ops.
- Reads each mission's DTA difficulty labels from `INI/Battle.ini`, including Brutal, Extreme, Ultimate, and Impossible. An unavailable selection falls back to the closest lower label supported by that mission.
- Generates `spawnmap.ini` from the selected loose DTA mission map without changing the source map.
- Applies DTA's Easy, Medium, or Hard map-code overlay.
- Writes DTA-compatible `spawn.ini` and launches `LaunchVinifera.dat -SPAWN -CD.`.
- Translates displayed game speeds to Tiberian Sun's reversed engine scale: `0 - Slowest` writes `6`, while `6 - Fastest` writes `0`.
- Detects the Vinifera score screen through the newest `Debug/*.LOG` file.
- Reads the installed `INI/Rules.ini` catalogue at runtime.
- Extracts native TS SHP cameos from DTA MIX archives.
- Applies five broad Player Army buffs through player-production clones: production, cost, movement speed, firepower, and reload. Direct player-owned starting units use the same clones; enemy and scripted units retain the installed rules. Armor remains unit-specific.
- Adds unit-specific production-clone buffs where the installed DTA rules support them: production, cost, speed, armor, health, damage, reload, range, sight, ammo, passenger capacity, cloaking, sensors, and self-healing. Native capabilities are not offered redundantly.
- Exposes 128 canonical mobile types: 27 infantry, 93 vehicles/naval units, and 8 aircraft. The 117 non-essential types can become access rewards. Engineer, all four MCVs, both resource harvesters, and all four faction hovercraft transports remain permanently available.
- Removes obsolete mission aliases such as `E1N`, `E3N`, and `APCN` from the dashboard. Shared units appear in each faction tab that can use them; global house rewards alone use Neutral. Duplicate display names use faction/editor-qualified labels.
- Excludes the base Tiberian Sun Devil's Tongue, Wolverine, and Disruptor types that are not part of DTA's active roster. Campaign-only units use curated faction ownership instead of appearing under every faction solely because their map-editor definitions list every house.
- Uses native DTA cameos for active rewards. Railgun Tank and Battle Rig use text-only entries because DTA has no correct native cameo for them.
- Includes five offensive powers and two support powers. Each is cloned into the generated map and granted only to the exact scenario player house.
- Includes 12 defensive-building unlocks and their supported production, cost, durability, weapon, range, sight, cloaking, sensor, and self-healing buffs.
- Offers stackable recharge-speed rewards for all seven powers. Airstrike, both nuclear strikes, and Chrono Vortex also offer player-only damage and effect-radius buffs through cloned weapon, warhead, and animation chains.
- Offers optional enemy armor and production-speed rewards. These target only active hostile production families; any family used by the player or a direct ally is excluded.
- Uses the 12 colors exposed by DTA's multiplayer options. The Pink UI choice writes DTA's `DarkMagenta` engine color.
- Awards mission rewards at the observable score-screen victory event. DTA maps do not expose one uniform runtime signal for their varied sub-objectives, so the launcher does not create or display objective-reward checks.

## Unit safety rule

Direct mobile-unit placements owned by the exact player house use a non-buildable player clone when that unit has an active buff. Enemy placements, structures, TaskForce entries, trigger references, script references, and reinforcements retain their original type.

Every unit-specific and Player Army buff uses a map-local Vinifera clone. Normal production routes the human production house from the original to the clone. Earned access uses the same isolation. Only exact player-owned starting mobile units are rewritten; TaskForces, teams, triggers, scripts, reinforcements, and non-player objects remain unchanged.

If a hostile scenario house shares the player's Vinifera `ActsLike` production mask, production clones are skipped for that mission. Exact player-owned starting mobile units may still use non-buildable placement-only clones, which the hostile factory cannot produce.

Unit and defensive-building access uses the same identity-preservation boundary. Earned production is routed through exact-production-house `_PLAYER` clones. Existing enemy and scripted objects are never replaced.

`DTA Puzzle.png` is shown on this GitHub README and bundled as a compiled-executable resource. The Python window and packaged executable use `launcher_icon.ico`, cut from the center JM section of that existing image; no replacement artwork is used.

## Run from source

From the DTA installation root:

```powershell
python RandomizerLauncher\launcher_gui.py
```

Run the non-invasive adapter check:

```powershell
python RandomizerLauncher\launcher_gui.py --self-check
```

The self-check does not launch DTA and writes its report to `RandomizerLauncher/self_check.json`.

## Status

The mission catalogue, cameos, map generation, launch contract, broad buffs, unit and defense buffs, production access, player-production clones, seven power unlocks, supported power buffs, optional enemy buffs, Randomizer Arsenal, and Archipelago catalogue are implemented and covered by the non-invasive self-check. Access clones use `TechLevel=1` and remove inherited prerequisites, `BuiltAt`, and `BuildLimit`. Standard mode activates only rewards matching the selected mission's faction; Chaos retains cross-faction access. Old buffs for still-locked units are ignored at launch instead of granting access.

All 81 active mission maps were checked for map-local power types. The obsolete duplicate `EMPulseSpecial` alias is not a reward.

Live verification is still required for sidebar production, buff effects, unlocks, clone save/load, score-screen completion, and Archipelago item receipt.

Player configurations created before mobile-unit access was introduced are migrated once to enable access and buffs. Existing buff-only seeds are not rewritten because changing their assigned rewards would invalidate completed progression; the launcher asks the player to generate a new seed instead.
