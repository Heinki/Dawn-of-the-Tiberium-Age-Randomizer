<img src="DTA%20Puzzle.png" alt="Dawn of the Tiberium Age Randomizer Launcher puzzle logo" width="500">

# Dawn of the Tiberium Age Randomizer Launcher

This project is a direct DTA port of the existing Mental Omega Randomizer. It preserves the original launcher UI, modes, settings model, mission/grid progression, rewards view, seed system, save/load behavior, navigation, tooltips, and run flow. Game-specific data and engine integration are adapted for DTA 15.1.0 and Vinifera.

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
- Enables six broad player-only army modifiers through the mission's selected human difficulty section: production, cost, movement speed, armor, firepower, and reload.
- Exposes 116 canonical mobile types: 20 infantry, 56 regular vehicles/naval units, 8 aircraft, and 32 campaign/skirmish special units. The 105 non-essential types can become access rewards. Engineer, all four MCVs, both resource harvesters, and all four faction hovercraft transports remain permanently available.
- Removes obsolete mission aliases such as `E1N`, `E3N`, and `APCN` from the dashboard. Shared units appear in each faction tab that can use them; global house rewards alone use Neutral. Duplicate display names use faction/editor-qualified labels.
- Includes campaign/map-only Special rewards by default. Three special types whose referenced native cameo files are absent from DTA's active MIX archives use text cards instead of unrelated substitute artwork.

## Unit safety rule

Map-placed units always retain their original type. The DTA adapter never replaces authored map objects, TaskForce entries, trigger references, or script references.

Every unit-specific reward uses a map-local Vinifera production clone, forbids the human house from producing the original, and allows only that house to produce the clone. Earned access uses the same isolation. Placed objects, TaskForces, teams, triggers, scripts, and reinforcement identities remain unchanged.

Infantry access uses the same identity-preservation boundary. Native earned infantry can use the original type. A foreign infantry type that the human house cannot normally produce receives an exact-house `_PLAYER` production clone. Existing map and scripted infantry are never replaced.

`DTA Puzzle.png` is shown on this GitHub README and bundled as a compiled-executable resource. It is not rendered inside the launcher window.

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

The static adapter, mission catalogue, native cameos, map generation, launch contract, broad buffs, mobile-unit access, and player-production clones are implemented and self-checked. PTTP #6 was successfully started directly from Mission List without opening the DTA client. Unit-specific buffs and earned access always create a player-production clone; authored map units and enemy identities remain original. Access clones use `TechLevel=1` and remove inherited prerequisites, `BuiltAt`, and `BuildLimit`. Standard mode activates only rewards matching the selected mission's faction; Chaos retains cross-faction access. Old rewards for still-locked units are ignored at launch instead of granting access. Score-screen completion, sidebar production across every special unit, capture behavior, and clone save/load still need live verification.

Player configurations created before mobile-unit access was introduced are migrated once to enable access and buffs. Existing buff-only seeds are not rewritten because changing their assigned rewards would invalidate completed progression; the launcher asks the player to generate a new seed instead.
