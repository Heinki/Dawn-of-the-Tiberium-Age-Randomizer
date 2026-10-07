# Mental Omega co-op review for DTA

Reviewed MO commits `fe3e84e` and `822799d` against DTA baseline `a985808`.
This review changes launcher source; participating players must rebuild or
update to the same launcher version.

## Requested behavior

- **Mission selection and pings:** DTA previously sent a complete state on
  host selection and logged guest suggestions only. Host selections now use
  a small immediate message. Guest pings are relayed to every player and
  displayed on the grid alongside the host's selection. Receiving a selection
  does not send a suggestion back. The host still chooses what launches.
- **Grid rewards:** The existing launch path already supplies the same earned
  unit unlocks and buffs to all human players. This behavior is retained.
  Shop profiles and permanent upgrades do not contribute to Grid gameplay.
- **Shop rewards:** The previous DTA implementation made permanent selections
  personal but shared the host's run purchases and starters. Each player now
  retains a personal `shop_coop_run.json`, including purchases, unit buffs,
  starters, drafts, Ore and selected permanent units. The host combines each
  player's own rewards into one common native map, with separate human
  production masks. Guest purchases are enabled.
- **Shop progression:** Mission offers, selection, commitment, rerolls,
  difficulty assists and team results follow the host. Each personal economy
  processes victory and failure using its own profile. The host decides
  whether the team revives. Completion history and revival counters prevent
  duplicate rewards on repeated snapshots and reconnects. Host endless
  continuation preserves each player's purchases and balances.

All Shop players need matching seed, mission pool, run length and modifiers.
Guests may start their personal run after connecting at stage 1. Joining a
later stage requires the matching personal save. A host cannot commit a
mission until every player has shared a compatible personal run. Existing
solo run files are unaffected; the normal personal profile is still shared
between solo and co-op on each player's computer.

## Other fixes and engine differences

- Initial connection failures release the lobby and controls so Connect can
  be retried. Loss of an established session still requires explicit disconnect.
- Shop writes are blocked while the map is built and during preparation.
  Unchanged loadouts acknowledging host mission controls do not abort launch.
- Runtime comparison now includes `INI/Art.ini`, `INI/AI.ini`,
  `INI/Vinifera.ini` and `LaunchVinifera.dat`. Older launcher protocols are
  rejected before entering a session.
- DTA already transfers one common map, validates native dependencies, checks
  preparation checksums and waits for every player's ready acknowledgement.
  Rewards remain human-only production clones; authored starting units,
  scripted actors and AI production retain their original identities.
- MO's YR-specific Grid power providers, Ares/Phobos rules, multiplayer
  protocol values and `Behind=none` desync workaround are not transferable
  assumptions about Vinifera. DTA co-op powers, enemy scaling and allied-helper
  buffs remain unsupported. Buffs apply to newly produced reward units;
  authored starting forces are not upgraded.
- The source feature flag was already `True`; this review leaves it unchanged.
  The release TODO still requires a disabled flag until live verification.

## Focused manual verification

No automated tests were added, modified or run.

- Syntax parsing and `git diff --check` passed.
- Three simulated launcher peers confirmed immediate host selection, guest
  ping relay to the third player, no selection echo and no duplicate badges.
- Native map preparation for representative 2-, 3- and 4-player missions
  produced matching Grid rewards for every human and rewrote zero authored actors.
- A personal Shop map gave player 1 a buffed Mammoth Tank and 1,000 bonus
  credits; player 2 received Artillery and 2,000 bonus credits, through different
  human production masks.
- Controller snapshot inspection preserved guest Ore/Gems on commitment,
  awarded personal currency once on victory, preserved purchases on defeat
  and revival, and left personal saves untouched after invalid selections.
  Endless continuation and duplicate result snapshots were also checked.
- The expanded runtime manifest successfully read every newly checked file.

Live Windows/Linux DTA gameplay has not been verified. Use
[COOP_PLAYTEST.md](COOP_PLAYTEST.md) for native sidebars, deployed units,
network synchronization, scripted victories, defeat and revival. MO's
successful sessions do not establish DTA engine compatibility.
