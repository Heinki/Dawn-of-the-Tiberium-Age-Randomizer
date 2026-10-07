# Experimental native DTA co-op

## Reference and engine investigation

Mental Omega reference: upstream commit `9c12927abdfa089212809d8f489fd5d021deffe5`
(verified against the installed checkout before implementation).

| Mental Omega component | DTA equivalent | Decision |
| --- | --- | --- |
| `coop/feature.py`, configuration migration | Source-only developer constant | Reuse off-by-default gating |
| `application/coop_controller.py`, Settings and Shop Setup | Cooperative controller and existing Settings/Shop Setup | Adapt host/join workflow to 2–4 humans |
| `coop/catalogue.py`, `prototype._map_config` | Mission catalogue extension using MPMaps.ini and inherited map Basic/CoopInfo | Adapt, never infer count from titles |
| `generation/seed_controller.py`, Grid state | Existing DTA generator/Grid | Reuse with separate state and validated player count |
| Shop offers, stage messages and run persistence | Existing DTA Shop service/repository | Reuse host-owned run/profile; guests view the host snapshot |
| `coop/lobby.py`, `coop/direct.py` | Persistent multi-peer lobby, native Vinifera spawn writer | Adapt wire protocol and readiness barrier |
| `coop/reward_map.py`, `enemy_rewards.py` | DTA production clone builder | Personal human HouseType masks and HumanOnly clones; native AI unchanged |
| `coop/victory.py`, YR empty-TeamType marker | Vinifera multiplayer score log | Adapt; solo score-screen signal is not a multiplayer victory |
| Private Shop countries/loadouts | Registered DTA HouseTypes with native faction side/owner permissions | Personal production masks; no YR keys |
| YR power grants | No audited DTA power path | Do not port |

Native DTA missions are registered in `INI/MPMaps.ini`, not Battle.ini.
Metadata can live in the map's `[Basic]`, `[CoopInfo]`, an inherited map, or
a catalogue `BaseSection`. `ClientMinPlayer`/`ClientMaxPlayer` take precedence
over engine `MinPlayer`/`MaxPlayer` (the latter include scripted AI slots).
Campaign missions and most standalone missions require exact authored client
counts. Tunnel Train-ing and Radial Range explicitly permit 2–4 humans and
have no scripts requiring absent optional humans; they are eligible throughout
that range. The active count is included in their normalized metadata/hash.
`Spawn1`–`Spawn8`
refer to starting locations; runtime `Multi1`–`Multi8` slots are sorted by
human color, followed by allied and enemy AI.

Engine sources inspected: Vinifera `src/spawner/spawnerconfig.cpp`,
`spawner.cpp`, `extensions/scenario/scenarioext_hooks.cpp`,
`extensions/house/houseext_hooks.cpp`, and
`extensions/multiscore/multiscoreext_hooks.cpp`; DTA client
`Domain/Multiplayer/Map.cs`, `GameModeMapBase.cs`, and `CoopMapInfo.cs`.
Vinifera accepts native `Other1`–`Other7`, HouseCountries, HouseColors,
HouseHandicaps, SpawnLocations, and Multi*_Alliances. It launches through
SyringeEx (`LaunchVinifera.dat game.exe --args=-SPAWN -CD.`), not MO's Syringe/Ares.
Multiplayer logs report `<player name>: Winner` or `Loser`; campaign
`ScoreScreen: Loaded` alone must never award a cooperative victory.
The host observes the final roster scores and records a team victory when any
configured human won, even if the host's house was defeated earlier. An AI
winner alone does not count. Guests never record their own result.
The multiplayer protocol/frame settings come from DTA's GameOptions.ini
(`Protocol=0`, `FrameSendRate=1` on this installation); MO's protocol 2 is not
hard-coded. Native map validation uses `MapHash`, not YR's `MapSHA1`.

## Enabling and playing

Set `COOP_FEATURE_ENABLED = True` in `randomizer/coop/feature.py` and rebuild
every participating launcher. Keep it `False` in release builds. YAML cannot
override this gate. Co-op controls appear in Settings and Shop Setup only in
developer builds. Select **Co-op mode (experimental)** and **Players** (2–4).
Configure the mission pool before generating Grid progress or starting Shop.

Use the [player connection guide](COOP_CONNECTION_GUIDE.md) for setup. A private
ZeroTier network is the supported player connection method. The connection
window masks IP/code by default, copies the code without revealing it, and
redacts connection details in co-op messages. Ports use the existing defaults
without editable controls; pairing still authenticates the launcher session.
Masking is display protection; native spawn files and game logs still contain
addresses.

Use a separate DTA installation per player (separate Wine prefixes on one PC).
All players need matching game/rules/runtime versions. Open **Co-op Connection…**,
choose Host or Join, use distinct names, and enter the host's ZeroTier Managed
IPv4 and pairing code on each guest. All players join the same private ZeroTier
network and must be authorized by its owner. Allow TCP 19420 on the host and
UDP 1234 on every computer over that network.
The launcher lobby uses TCP and native gameplay uses peer UDP through ZeroTier;
ZeroTier manages the virtual network rather than the launcher installing or
configuring it. The underlying IPv4 sockets remain necessary for this transport.

The host owns Grid generation, mission selection, rerolls and team results.
Grid unit unlocks and buffs are shared by every human. In Shop, each player
owns their purchases, Ore, Gems and existing personal profile.
Players select their own permanent units before joining. Selected units,
permanent unit buffs, global combat upgrades and starting-credit upgrades
remain personal. Run purchases, starters and draft buffs are taken from each
player's own run. All players start Shop with matching seed, mission pool,
run length and modifiers; guests can start at stage 1 after connecting.
Host snapshots apply only mission decisions and durable results to personal
Shop saves. Each player's economy handles victory and failure independently;
the host controls the team's revival decision. Duplicate snapshots are
idempotent. Guest clicks ping missions on every grid; host selection syncs
immediately without transferring the full progression document.
Loadout views never copy another player's purchases or profile.
Maps transfer from the host,
with installation/source hashes and an all-player preparation acknowledgement
before launch. Reconnecting restores the latest host state. Cooperative Grid
and Shop run files are separate from solo files; `shop_profile.json` is shared
between solo and co-op on each player's computer. Changing player count is blocked
while a run/lobby is active; incompatible saved pools fail visibly.

## Deliberate limitations

Only active `MultiMaps` registrations with supported native settings and
player counts are eligible. Unpublished Soviet campaign maps are explicitly
blocked by filename and campaign title, even if locally registered. Standalone
missions played as Soviet remain eligible. The launcher picks an allowed native
side for the entire team, preferring one unused by AI (for example, GDI for
Nuclear Winter, which also permits Allies). Missing,
cyclic, escaping, or unsupported map inheritance/options are excluded with a
catalogue reason. Difficulty-specific map variants retain their native mode.
Native map units, teams, triggers, scripted allies and ownership stay authored.
Unused faction teams and neutral objects do not exclude a mission. Earned
production clones use a distinct registered HouseType mask per human, with
native `Buildability=HumanOnly`. The map copies the selected native faction’s
side and owner/factory permissions to those otherwise unused HouseTypes.
Spawn identities and AI countries stay native. Replaced originals are forbidden
only for that human mask, retaining other human and AI production. Deployed/transformed
reward clones are also human-only. Original forces and weapons are not buffed.
Reward clones cannot enter native starting-force or crate selection, which
bypass production eligibility; those routes retain native types.
When access randomization is enabled, rewardable native mobile units and
defenses are forbidden for human masks; earned personal clones provide access.
Always-available infrastructure remains available.
Retired `chkQueuing`/`chkSilosNeeded` map controls follow the current client's
defaults. Scripted AI houses need no start waypoint when Bases and UnitCount
disable generated starting forces; human starting waypoints remain required.
Maps without a Bases override retain Vinifera's native Bases=Yes default so
ordinary co-op starting MCVs are generated.
Shop uses the same provisional Act 1 economy class as the MO prototype;
all stages can repeat eligible maps so small four-player pools remain usable.

Power purchases/grants/buffs, enemy scaling, allied-helper buffs, per-offer
Shop boons/challenges and gameplay-changing Shop modifiers are disabled in
this prototype. Economy-only modifiers retain their existing behavior.
Unit production buffs and global Shop unit upgrades apply through personal
production clones. Each human receives their own starting-credit bonus via
native Give Credits action 106 targeted to Spawn1–Spawn4 after one second.
AI starting balances remain native. Authored starting forces are not converted
to reward clones. The shared map includes every player’s distinct production
rules; sending different map bytes to players would break synchronization.
Lobby protocol 3 and loadout protocol 3 reject older builds with shared Shop
purchases. Runtime comparison includes Art.ini, AI.ini, Vinifera.ini and the
native launcher in addition to the existing game/rules/options checks.
MO's YR-specific Grid power providers and Behind animation workaround are
not ported: this prototype uses Vinifera human-only production clones and
does not support co-op powers. Both engines still need their own live tests.

Structural validation is not a completed multiplayer playtest. Real 2/3/4
player networking, sidebars, scripted victory, defeat and revival still need
live-game verification. A host can record a confirmed victory manually when
the runtime omits its multiplayer score log. Closing without a winner follows
the existing Shop failure/revival lifecycle; guest exit alone changes no run.
The next verification milestone is the [native co-op playtest checklist](COOP_PLAYTEST.md).
The cooperative watcher binds only to a DEBUG log changed or created after
launch preparation, ignores old-game scores and SYNC/crash dumps, and handles
partial lines and overwritten logs. A guest's preparation abort is relayed by
the host to every guest before releasing the launch barrier.

On the inspected installation, the catalogue admits 55 two-human,
28 three-human, and 7 four-human entries (difficulty variants count as entries,
and the two ranged maps appear in all supported counts). All 70 distinct titles
in the supplied native-client screenshots are covered; see
[the complete mission list](COOP_MAP_COVERAGE.md). The catalogue retains explicit
exclusion reasons; the launcher
logs them when it loads the pool. Counts depend on the installed DTA maps.

## Implementation and validation

New modules: `randomizer/coop/{feature,catalogue,maps,spawn,lobby,persistence,victory}.py`
and `randomizer/application/coop_controller.py`. Existing integration changes
are limited to application initialization/launch/Shop controllers, configuration,
Settings and Shop Setup controls, DTA clone/difficulty helpers, and Shop state
normalization/mission modifiers. README and DEVELOPER_GUIDE link this document.

Validation performed against the installed DTA copy:

- `python -m compileall -q .` and `git diff --check` passed.
- `python launcher_gui.py --self-check` ran but failed with the existing
  assertion `DTA Shop Paradrop payload prices are not strength-specific`.
  A clean archive of unchanged HEAD `d158302` failed at the same assertion;
  no self-check was weakened or changed.
- Manual Tk launcher inspection generated eligible Grid and Shop runs for
  2, 3 and 4 humans, recorded offline progression, restored persisted state,
  and advanced Shop to stage 2. Deterministic rerolls remained in each pool;
  stale count validation and guest repository write rejection were inspected.
- Actual loopback TCP sessions paired 2, 3 and 4 launchers, transferred matching
  generated maps, and collected every guest's preparation acknowledgement.
  Native UDP gameplay was not launched.
- Native launch-path preflight passed for 2/3/4-player preparation; editing the
  prepared spawn.ini was rejected before game start.
- Follow-up manual log inspection ignored historical installed DEBUG logs and
  SYNC dumps, retained partial score lines, detected truncation/overwrite even
  when the replacement file was larger, and read a final unterminated score.
  Actual Tk launcher abort handling relayed a guest's cancellation to all
  1/2/3 guests in real 2/3/4-player loopback TCP lobbies.
- Before catalogue expansion, all 37 eligible generated maps preserved authored actor/team/script sections;
  repeated preparation produced identical hashes. Credit trigger output targeted
  only Spawn1 through the selected human count. Native 2/3/4-player spawn output
  was inspected, including AI slots and alliances.
- After expansion, all 90 count-specific preparations (55/28/7) preserved native
  actor/team/script sections. 747 generated reward clones and their deployed
  forms were checked for HumanOnly gating; native AI faction masks remained
  available. The two ranged maps prepared deterministically at every count.
  All 70 screenshot titles matched, unpublished filename/title guards were
  inspected, and the existing user Grid's pool/hash validation still passed.
- Expanded real Tk Grid/Shop inspection loaded 55/28/7 entries, recorded
  offline victories, and advanced every Shop run to stage 2. Shared-faction
  Shop global upgrades produced human-only clones without rewriting actors.
- With the source flag disabled, a config requesting co-op loaded 93 normal
  missions, exposed no cooperative controls, and normalized to solo mode.

No unit tests or new test suite were added. Temporary manual-inspection output
used separate `/tmp` state folders and did not replace player progression.
