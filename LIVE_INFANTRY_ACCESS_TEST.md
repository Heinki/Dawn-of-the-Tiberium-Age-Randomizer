# DTA player-clone live test

Test prepared: 2026-08-13  
Mission: Tutorial Mission 2 (`M_TUTORIAL2`)  
Scenario player house: `TutorialGDI` (`ActsLike=GDI`)

## Current test payload

The reversible test generates a fresh `spawnmap.ini` from the original Tutorial #2 map with these rewards:

- Production access for GDI Grenadier (`E2`).
- One unit-specific damage stack for `E2`.
- One unit-specific production stack for `E2`.
- One player-army production stack.
- GDI Rocket Soldier (`E3`) remains locked as the control.

Expected production behavior:

- Earned production uses `E2_PLAYER`; the authored `E2` identity is not replaced.
- `E2_PLAYER` is routed through `Owner=GDI` and `RequiredHouses=GDI`, matching `TutorialGDI`'s Vinifera `ActsLike` mask.
- `E2_PLAYER` has `TechLevel=1` and no inherited prerequisite, `BuiltAt`, or `BuildLimit` restriction.
- `E2_PLAYER` uses `E2_GRENADE_PLAYER`, whose damage is higher than the installed original weapon.
- Its unit production multiplier and the player-house production multiplier are both emitted.
- `E3` is forbidden for the effective GDI production house.
- No placed object, TaskForce, TeamType, trigger, script, or reinforcement identity is rewritten.

## Automated preflight result

Preparation currently passes every static check:

- Original mission file unchanged.
- Authored map objects untouched.
- Earned access routed to a player clone.
- `TutorialGDI` resolved to the GDI `ActsLike` production mask.
- Clone received both unit-specific buffs.
- Clone inherited no build restriction.
- Player-house production buff emitted.
- Required Vinifera INI sections emitted in the generated map.

Machine-readable report: `logs/live_infantry_access_test.json`  
Generated test map: `generated_maps/live_infantry_access_spawnmap.ini`

## Live observations still required

The next task remains incomplete until these are checked in gameplay:

- `E2_PLAYER` is visible and buildable immediately from the GDI Barracks.
- Unearned `E3` is absent from production.
- The unit-specific damage and production improvements work.
- The player-house production improvement also applies to the clone.
- A produced `E2_PLAYER` survives save/load and still works.
- Starting, enemy, scripted, and reinforced map units remain original and unbuffed.

## Reproduction

From the `RandomizerLauncher` directory:

```powershell
python tools\live_infantry_access_test.py
python tools\live_infantry_access_test.py --launch
```

Preparation is non-destructive. Launch mode creates durable backups, restores runtime files after exit, and leaves the generated test map plus JSON report for inspection. If a run is interrupted before cleanup, restore with:

```powershell
python tools\live_infantry_access_test.py --restore
```

## Earlier evidence and correction

An earlier PTTP #6 test proved that Vinifera loaded an added player InfantryType, entered interactive gameplay, exited cleanly, preserved the source map, and allowed normal mission save/load. That run did not verify clone persistence because its seed had unit access disabled.

A later Tutorial #2 test showed why scenario-house names could not be used directly: Vinifera evaluates `RequiredHouses` and `ForbiddenHouses` through the house's `ActsLike` bit. The adapter now emits the effective GDI mask for `TutorialGDI` and refuses isolation when an active hostile house shares that mask.
