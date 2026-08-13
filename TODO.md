Tasks
--------
1. [x] Check and fix DTA-specific launcher errors.
2. [x] Replace Mental Omega presentation assets with DTA assets. Keep `DTA Puzzle.png` out of the launcher window; use it for the GitHub README and packaged executable resources.
3. [x] Remove active Mental Omega game data and engine assumptions. DTA uses Vinifera, not Ares or Phobos.
4. [x] Add guarded player-production clones for unit-specific buffs. Static generation and self-checks pass; installed Vinifera behavior still needs a live mission/save/load test.
5. [x] Remove the unfinished DTA Shop implementation. The idea is deferred until its design is completed in the Mental Omega Randomizer.
6. [x] Correct Vinifera production routing to use the scenario house's ActsLike HouseType mask. The earlier custom scenario-house restriction parsed but failed live. Unsafe shared-ActsLike missions preserve enemy production and skip isolation.
7. [x] Include 116 canonical non-AI mobile types: 20 infantry, 56 regular vehicles/naval types, 8 aircraft, and 32 campaign/skirmish special units. Keep 11 essential units permanently available, deduplicate obsolete aliases, and show locked, available, unlocked, and unavailable access states.
8. [x] Correct DTA game-speed translation. Display order remains `0 - Slowest` through `6 - Fastest`; TS engine values are written in reverse (`6` through `0`).
9. [x] Migrate pre-access player configs to enable `access + buff`. Existing buff-only seeds remain unchanged and show a new-seed warning.
10. [ ] Live-retest Tutorial #2 with the corrected GDI ActsLike route, then verify a produced clone through save/load. Automated preflight now proves `E2_PLAYER` receives its unit damage and production buffs plus the player-house production buff; sidebar behavior and clone persistence still require the live test.
