# Chrono Hazard co-op crash investigation

The reported crash occurred in a build from before the Hardcore changes.
This investigation therefore covers the existing co-op aircraft/production
adapter independently of the new enemy challenge pipeline.

## Evidence and limits

The tester's exception report and crashing generated map were not available
locally. The available launcher logs and older engine debug logs do not contain
this reported crash. There is no matching fault address or call stack, and the
crash has not been reproduced in a live multiplayer game. The reported aircraft
connection remains a hypothesis.

The installed authored `Maps/Co-Op/chrono_hazard.map` is byte-for-byte identical
to the separate vanilla DTA installation. It has native GDI/Nod helipads with
free aircraft, plus scripted A-10, Orca, and Apache teams. The authored A-10
wave labels refer to five-/six-minute attacks; that does not exclude earlier
aircraft activity from the helipads.

A confirmed randomizer-side routing problem was found. The generic docking
compatibility pass widened **native** aircraft docking lists to every runway
and helicopter pad, even when no aircraft reward or enemy modifier was active.
For example, Chrono Hazard's A-10 changed from:

```ini
Dock=DEPCARR,ASTRP,RAASTRP
```

to include unrelated `GHPAD`, `NHPAD`, `AHPAD`, `SHPAD`, and AI pads. This changes
AI landing/refueling behavior. The same generic routine exists in the packaged
launcher backup taken immediately before the Hardcore implementation, so it
is not introduced by Hardcore.

The matching Vinifera
[aircraft implementation](https://github.com/Vinifera-Developers/Vinifera/blob/17b45db54bab4fd8753b7a98b8fa94dae124b546/src/extensions/aircraft/aircraftext_hooks.cpp)
uses each aircraft type's Dock list when selecting landing/refueling buildings.
This establishes the behavior change, not that it caused the tester's crash.

## Changes

- Human-only production preparation now preserves each native aircraft's
  authored docking families and their order. It may add equivalent player pad
  clones, allowing captured aircraft to use a cloned version of a compatible
  native facility. It does not add unrelated native pad families.
- Player aircraft clones retain the expanded cross-faction docking routes
  needed for purchased aircraft. Solo preparation keeps its existing behavior.
- Each successful co-op preparation now saves
  `RandomizerLauncherData/diagnostics/last-coop-preparation.zip` in packaged
  builds. It contains the exact generated `spawnmap.ini`, its SHA-256, mission
  identity, and launch settings with player names, IPs, and ports removed.
  One archive is retained and replaced on the next co-op preparation. Playing
  another mode no longer destroys the last co-op map evidence. Diagnostic
  write errors are logged and do not prevent launch.

The archive is local; nothing is uploaded or sent automatically. This change
does not replace the engine's own exception report or dump.

## Verification

No automated test suites were added or run, in accordance with `AGENTS.md`.
The focused audit prepared 11 actual installed maps/configurations without
enemy modifiers: Chrono Hazard at all four authored difficulties using both
the installed permanent profile and purchased aircraft loadouts, plus one
two-, three-, and four-player native mission with aircraft purchases.

All preparations passed. Every native aircraft's original docking families
and order were preserved; added destinations were equivalent pad clones.
Authored TeamTypes were unchanged, and purchased aircraft remained isolated
player clones with working docking lists. The saved diagnostic preserved exact
map bytes/checksum and omitted connection identity fields.

Detailed generated maps and audit results are in
`/tmp/dta-chrono-docking-audit/`. Compilation and `git diff --check` passed.
The updated executable and matching APWorld are packaged under
`release/2.6-coop-chrono-fix/`.

## Required playtest

Restart both launchers with the updated build and retry Chrono Hazard with
the same rewards and difficulty that previously crashed. The docking change
is active without enabling Hardcore and does not require resetting a run.
If the crash repeats, retain the engine exception report/dump, current debug
log, and `last-coop-preparation.zip` before preparing another co-op mission.
Those artifacts are necessary to establish the remaining failure precisely.

This is a fix for the confirmed routing issue and an investigatory build for
the reported crash; it is not a claim that the crash has been reproduced or
that its root cause has been proven.
