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
| Starting credits | Select a starting-credit reward; each human receives the same bonus after about one second. AI should retain native balances; inspect replay/debug data if available. |
| Grid victory | A normal scripted win unlocks host progress once, updates guests and survives host launcher restart. |
| Shop launch | Start Shop on the host, buy an upgrade, reroll and commit an offer. Guests see the same run; the committed mission launches on all clients. |
| Shop victory | A win grants Ore/Gems and advances the stage once on the host; guests receive the result without changing their own profile files. |
| Defeat/revival | A real team defeat follows the existing Shop failure/revival lifecycle once; relaunch keeps the committed mission and shared loadout consistent. |
| Guest exit | A guest exiting early does not independently complete/fail the host's run. The host's final runtime result remains authoritative. |
| Host defeated first | With the host watching in CoachMode, a surviving human teammate's scripted win counts as team victory. An AI winner alone never grants progress. |
| Reconnect | Close the game, explicitly disconnect, reconnect every player and launch again. Guest local selection/progression returns on disconnect; solo files remain unchanged. |

Also check once:

- Wrong pairing code, mismatched runtime or player count fails visibly before
  launching. Disconnect and retry with matching settings.
- On a streamed/captured connection window, IP and pairing code start hidden.
  Verify hidden paste and private code copying, and that deliberate reveal
  masks again after 30 seconds or when switching away from the window. Confirm
  connection errors do not reveal addresses or codes. Keep chat, clipboard
  history and ZeroTier Central outside the captured scene.
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
  `shop_coop_profile.json`, as relevant, from the launcher data folder.

Include host/guest roles, player count, mission code, seed, difficulty, connection
method, what happened and whether any player exited or was defeated early.
Spawn files contain player names and IP addresses; redact those before public
posting. Never include the pairing code.

Current status: structural preparation is validated; the live-session matrix
above has not yet been played. The unrelated existing launcher self-check
Paradrop pricing assertion still fails on unchanged baseline source.
