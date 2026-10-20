# Co-op bug investigation

## Findings and changes

- **Startup crashes:** Both supplied exception reports fail at `0x00649563`
  (`TriggerClass::Is_Triggered`), while dereferencing the trigger owner's
  HouseType. Inspection of the installed executable shows that trigger loading
  indexes the HouseTypes array with the owner's name lookup result, without
  checking for `-1`. The generated starting-credit trigger used `Spawn1` as its
  owner. Freezing Offensive and Chrono Hazard do not register that HouseType;
  virtual Spawn lookup is supported for credit action targets, not trigger
  owners. The trigger now belongs to `Neutral`; credit targets remain personal
  Spawn slots. Preparation also rejects unresolved owners, malformed action
  counts, and script values of 512 bytes or more. No 512-byte overflow was
  reproduced in the supplied missions. The reports do not include their
  crashing generated `spawnmap.ini`, so reproducing those exact crashes still
  requires an in-game retest.
- **Victory and defeat:** Personal production countries replace the human
  faction's HouseType identity. Vinifera's native winner/loser actions compare
  that identity directly, ignoring alliances. An Allied victory consequently
  defeats both personal countries; Chrono Hazard's failure action targeting
  country 6 can instead reward the first personal country. Preparation now
  preserves the original human faction's result by defeating the losing team
  through Spawn-aware action 110. Normal multiplayer alliance scoring then
  determines the result for every player. Nonterminal actions, placements,
  task forces, and AI countries are preserved.
- **Shop technology and MCVs:** Personal co-op production omitted the
  infrastructure access preparation used by solo generation. A02 locks its
  War Factory and radar; the native MCV requires both. Earned units therefore
  lacked usable production infrastructure. Each randomized loadout now gets
  isolated base essentials, factories for its earned categories, and its native
  MCV through the matching factory, including its personal factory clone.
  `MultiMCV` also permits production through authored reinforcement yards whose
  producer identity differs from the personal country. Native AI technology
  remains unchanged. Placed starting units remain authored actors, as intended.
  The catalogue sweep also exposed blank authored `Side=` fields in all three
  Operation Barachiel variants. Personal country preparation now falls back
  to the installed faction side when the map supplies no value.
- **Joining from Setup:** The Setup button calls `on_new_seed`, which returned
  immediately for guests. The Shop Run button called `start_shop_run` directly.
  Both paths now create the same personal run. Refreshing ordinary Setup
  controls also reapplies co-op join permissions.
- **Synchronization and modifiers:** A snapshot containing only changed player
  loadouts did not refresh dependent views. Such snapshots now invalidate and
  refresh those views. Guests see the host's active modifiers. The existing
  shared modifiers (`no_safety_net`, `narrow_intelligence`) follow the host and
  cannot be edited by guests; personal economy modifiers remain selectable
  before joining and lock during the run. Unsupported co-op modifiers remain
  disabled. Tests exercise different players' units, starting-credit upgrades,
  global upgrades, currencies, and buffs without merging their economies.
- **Permanent buffs and powers:** No persistence defect was reproduced.
  Effective personal loadouts already clear disabled permanent unit buffs and
  permanent power snapshots. Co-op power rewards remain disabled by existing
  policy. No reset behavior was changed.

The matching engine sources document the relevant behavior in
[winner/loser and house-destruction actions](https://github.com/Vinifera-Developers/Vinifera/blob/17b45db5/src/extensions/taction/tactionext.cpp),
[Spawn house lookup](https://github.com/Vinifera-Developers/Vinifera/blob/17b45db5/src/extensions/house/houseext.cpp),
and [MCV production checks](https://github.com/Vinifera-Developers/Vinifera/blob/17b45db5/src/extensions/house/houseext_hooks.cpp).

## Files

- `randomizer/coop/maps.py`: safe trigger ownership and script validation.
- `randomizer/coop/victory.py`: team outcome adaptation.
- `randomizer/coop/production.py`: personal infrastructure and MCV production.
- `randomizer/application/coop_controller.py`: join dispatch, snapshot refresh,
  and modifier presentation/permissions.

## Verification

Before packaging, all 16 focused regressions passed. Their temporary unittest
file was subsequently removed at the user's request. The checks covered the
two crash maps and A02, real success/failure paths, preservation
of nonterminal scripts across the native catalogue, personal production and
upgrades, peer spawn settings, joining, modifier permissions, loadout-only
snapshots, and permanent-buff reset behavior.

All 86 eligible native maps were generated with personal randomized loadouts
at the Normal difficulty selection: 53 two-player, 26 three-player, and seven
four-player maps. The three Barachiel variants were rerun after fixing their
blank side fields. All passed script validation, CRLF/cp1252 serialization,
map checksums, per-peer spawn configuration checks, and authored actor/team
preservation checks. Generated files and the detailed validation results were
kept in `/tmp`; saved runs and live `spawn.ini`/`spawnmap.ini` were not changed.

The existing `test_*.py` suites were also run. Their three failures reproduce
with the original HEAD implementations: two Shop UI fixtures lack
`_shop_search_after_ids`, and a reload test expects every integer ROF stack to
decrease. The additional `check_*.py` suites likewise reproduce their baseline
failures: stale tooltip fixtures/expectations and unavailable or incomplete
Archipelago test dependencies. These unrelated failures were left unchanged.
Python compilation and `git diff --check` pass.

## Manual co-op verification still required

No game process was launched. On two machines, retest Freezing Offensive and
Chrono Hazard with credit bonuses/debits; test both scripted victory and defeat
in A02 and Chrono Hazard; build earned units and replacement MCVs after getting
a construction yard. Test joining through both Setup and Shop Run, modifiers
before and after joining, reconnecting after purchases/upgrades, and restarting
with permanent unit buffs disabled. Repeat with three/four players to confirm
engine scoring, production timing, and network synchronization.
