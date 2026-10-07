# Native Vinifera co-op playtest

The next milestone is a real DTA multiplayer session. Local launcher, map,
spawn configuration and TCP checks cannot verify native UDP synchronization,
sidebars or scripted mission outcomes. Keep the source feature flag off in
release builds until these checks have passed.

## Setup

Follow [COOP_CONNECTION_GUIDE.md](COOP_CONNECTION_GUIDE.md) for the step-by-step
connection setup. Use a private ZeroTier network for every player session;
manual router forwarding is normally unnecessary. Keep IP and pairing code
masked if streaming, and share them privately.

1. Use matching DTA installations and launcher source/builds on every player PC.
   Enable `COOP_FEATURE_ENABLED = True` in `randomizer/coop/feature.py` on each.
   For source launches, run `python launcher_gui.py` from RandomizerLauncher.
2. Choose experimental co-op and the same player count on every launcher.
   Start with two players on separate PCs in the same private ZeroTier network.
   Authorize both devices and confirm each has a Managed IPv4 address.
3. Generate a Grid on the host, then open Co-op Connection. Give every player
   a distinct name. Host and guests must use the same pairing code. Guests enter
   the host's ZeroTier Managed IPv4 address. Ports are configured automatically.
4. Allow TCP 19420 on the host and UDP 1234 on every PC through the firewall
   over the ZeroTier network if needed.
5. Wait until every launcher shows the complete roster. Guests should display
   the host's seed, mode, mission and progression; only the host launches.

## Required sessions

Run the following checks with 2, 3 and 4 humans. Use only missions offered by
the launcher. Record the mission code, seed, difficulty and player count.
Difficulty variants count as separate native catalogue entries.
All screenshot missions are listed in [COOP_MAP_COVERAGE.md](COOP_MAP_COVERAGE.md).
Include Forged Payback and It Came For DTA II when checking rewards: allied AI
share the human faction there, so human-only clones must not replace or buff
the AI's native production. Check Tunnel Train-ing or Radial Range with 2, 3
and 4 humans to verify their native ranged player-count support.

| Check | Expected result |
| --- | --- |
| Grid launch | Every client launches the same mission and enters the match without connection failure or desync. |
| Human ownership | Each player controls the intended Spawn house/start position; no player becomes AI and all humans are allied. Native allied/enemy AI keep their positions and ownership. |
| Production rewards | Unlock a unit and a unit buff on the host; all humans receive the same production reward and upgraded new units. Authored starting forces and scripted AI stay unchanged. |
| Starting credits | Shared Grid rewards apply equally. In Shop, give players different permanent starting-credit upgrade levels: each receives their own bonus after about one second. AI retains native balances. |
| Grid victory | A normal scripted win unlocks host progress once, updates guests and survives host launcher restart. |
| Grid selection/ping | Click different missions on the host and every guest. Host selection updates immediately; each guest ping appears on every grid, retaining the host's launch authority. |
| Shop launch | Start personal Shop runs with matching seed, mission pool, run length and modifiers. Buy different units on each player; host rerolls and commits an offer. Mission decisions sync, while purchases and Ore remain different. The committed mission launches on all clients. |
| Personal permanent access | A selects permanent Artillery, B selects Behemoth. A can build Artillery only; B can build Behemoth only. Current Loadout and Shop Setup show each player's own selections. A run purchase grants access only to its buyer. |
| Personal buffs | Give players different permanent and purchased unit buff stacks and global upgrade levels. Newly built units use only their owner's levels. Check deployed/transformed forms and factory prerequisites too. |
| Shop victory | A win grants each player's own Ore/Gems and advances every personal run once. Repeated snapshots and reconnects must not duplicate rewards or overwrite personal purchases. |
| Defeat/revival | A real team defeat follows the existing Shop failure/revival lifecycle once; relaunch keeps the committed mission and shared loadout consistent. |
| Guest exit | A guest exiting early does not independently complete/fail the host's run. The host's final runtime result remains authoritative. |
| Host defeated first | With the host watching in CoachMode, a surviving human teammate's scripted win counts as team victory. An AI winner alone never grants progress. |
| Reconnect | Close the game, explicitly disconnect, reconnect every player and launch again. Guest local Grid selection/progression returns on disconnect; personal co-op Shop progress persists. Solo run files remain unchanged. |

Also check once:

- Wrong pairing code, mismatched runtime or player count fails visibly before
  launching. A runtime mismatch lists the differing files on both updated
  launchers; Show connection log includes both hashes. Host rejection and
  connection stages also appear in the persistent launcher log. Disconnect
  and retry with matching settings.
- Matching runtime text files using CRLF on one PC and LF on the other connect.
  Confirm `files` hashes match while `raw_files` hashes can differ. Changing an
  actual rules value or an executable/DLL byte still fails. Personal saves,
  completions, Gems, and randomizer configuration files need not match.
- An older launcher using raw-byte fingerprints reports that the compatibility
  check differs instead of incorrectly blaming matching DTA game files.
- Native map/option files with CRLF/LF or filename casing differences produce
  matching metadata. Legacy Grid/Shop hashes upgrade without changing saved
  progress, Gems, purchases, or mission selection. Real map changes still fail.
- Applying a host snapshot never sends the unchanged guest loadout back. A
  rejected snapshot leaves the last valid guest state intact and disconnects
  with one rejection instead of repeating errors.
- Join with a different existing seed, selected mission, and unlock history.
  The guest's Grid, mission details, unlock icons, progress, and header must
  reflect the host immediately. Both launch buttons say Suggest Mission.
  Disconnect restores the guest's previous selection, data, and button labels.
- Select Brutal on a map that supports it and launch from the host. Preparation
  must reach the ready/go barrier without a campaign difficulty indexing error.
  Easy, Normal (native Medium), Hard, and Brutal use the map's authored modes;
  a missing mode falls back to a supported difficulty.
- Launch validation and preparation errors appear in Show connection log and
  the persistent launcher log, including a traceback for validation failures.
- Host always shows its generated code as a noneditable text label. Switching
  to Join shows a separate input; switching back restores the same host label.
  Copying, connecting, disconnecting, and reopening Host keep the code visible.
- In Join, IP and pairing-code inputs start hidden. Verify hidden paste and
  code copying, and that deliberate reveal
  stays visible while changing roles, connecting, disconnecting, and switching
  away from the window. Confirm the entered guest code survives role changes.
  Unchecking reveal or closing/reopening the window masks details again. Confirm
  connection errors do not reveal addresses or codes. Keep chat, clipboard
  history and ZeroTier Central outside the captured scene.
- In a 3/4-player lobby, submit guest loadouts in a different arrival order.
  Player slot mappings must remain correct; no player gets another’s loadout.
- Try a wrong pairing code or unreachable host, then retry Connect without
  reopening the launcher. Failed initial connections must release controls.
- Try buying while the host prepares the map. Changes to prepared loadouts must
  be rejected; unchanged mission-control acknowledgements must not abort launch.
- Use different Art.ini, AI.ini or Vinifera.ini on one PC. Pairing must report
  the differing runtime file before any native game starts.
- In a 3/4-player lobby, disconnect one guest during preparation. No remaining
  player should launch alone. Other guests must receive the abort/disconnect
  without waiting for the preparation timeout.
- Rerolls never offer missions for another player count. Unsafe power, enemy,
  allied-helper and per-offer modifiers remain unavailable.
- Disable the source flag again and restart: normal solo Grid/Shop controls,
  saved progression and mission launch should work as before.

Do not use “Record Co-op Victory” while verifying automatic victory detection.
That button is a manual recovery option and would mask a watcher failure.

## Evidence for failures

Before launching another mission, copy these files from every participant:

- `spawn.ini` and `spawnmap.ini` from the game folder.
- The session's `Debug/DEBUG_*.LOG`; include matching `SYNC_*.LOG` or crash logs
  if a desync or crash occurred.
- `RandomizerLauncher/logs/launcher.log` for source launches, or
  `RandomizerLauncherData/logs/launcher.log` for packaged launches.
- Host co-op state: `randomizer_coop_state.json`, `shop_coop_run.json` and
  `shop_profile.json`, as relevant, from the launcher data folder.

Include host/guest roles, player count, mission code, seed, difficulty, connection
method, what happened and whether any player exited or was defeated early.
Spawn files contain player names and IP addresses; redact those before public
posting. Never include the pairing code.

Current status: structural preparation is validated; the live-session matrix
above has not yet been played. The unrelated existing launcher self-check
Paradrop pricing assertion still fails on unchanged baseline source.
