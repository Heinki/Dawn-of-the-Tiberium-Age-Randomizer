# Final Fortress in DTA

Select **Settings → Game Mode → Final Fortress**. The workspace follows Mental
Omega's Defense setup, Permanent perks, Challenge and Run results layout. Settings
remains available; choosing another Game Mode restores the previous workspace.
Defense setup, Permanent perks, Challenge and Run results have separate tabs.
While Final Fortress is selected, Settings shows only Game Mode, Fortress co-op
and launcher appearance; campaign seed, mission and reward settings are hidden.
Fortress uses its own purchases, preferences, run snapshots and Defensive Points.
Campaign, Grid, Shop and Archipelago saves are independent.

Defend the Executive Building headquarters (`V37`) beside the initial MCV on **King of the Hills
Extreme** for 60 simulation minutes. Choose GDI, Nod, Allies or Soviet, one of
the seven DTA difficulty grades, and a wave multiplier from x1 through x10.
Normal skirmish AI continues alongside scripted waves. Only starting enemy
construction yards and their fixed defenses are protected; expansion yards,
factories, power plants and other ordinary buildings remain destructible.
Every friendly house starts with one faction harvester, including runs without
perks. Preplaced refineries do not grant a duplicate collector. Starting defenses
add two emplacements of one new type per rank, with faction-specific limits:

- GDI: Guard Tower and Advanced Guard Tower; maximum rank 2, four emplacements.
- Nod: Gun Turret, Obelisk and SAM Site; maximum rank 3, six emplacements.
- Soviet: Flame Tower, Tesla Coil and SAM Site; maximum rank 3, six emplacements.
- Allies: Pill Box, Gun Turret, Camouflaged Pill Box and AA Gun; maximum rank 4,
  eight emplacements.

The UI shows the chosen faction's ranks and limit. Higher purchased ranks are
retained when switching to a faction with fewer types; purchases beyond that
faction's limit are disabled. Existing rank 3/4 purchases remain valid. Profiles
already refunded by the earlier two-rank version keep those refunds and can buy
the newly available ranks. The debug profile owns every rank.
Each enemy starts with four fixed emplacements covering all its available types.
Extra friendly generators cover only the actual starting power shortfall,
accounting for More power ranks. The headquarters uses V37's native 2×2 art and
bib, while retaining the Fortress base health of 7,000 and existing objective
ownership, durability upgrades, reserve shield and defeat behavior.

Six guarded crates exist at startup. First collection pays 10 Defensive Points
to every human. Human collectors receive their own frozen cash or unit payload;
enemy/helper collection routes the payload to the host. Guard deaths grant no
points. Native visual crate cash is disabled to avoid duplicate payouts.

Survival awards are 25 points at minute 25, 25 at minute 45 and 50 on victory.
Earned milestones and camps survive defeat or quit. A verified victory or defeat
also awards five points per 50 corrected friendly native kill-score points, up
to 500 points at 5,000. Native scores may include captures. Setup transfers are
deducted separately for each friendly house. Direct credit payments need no cash
escrow correction. Unfinished quits grant no kill bonus.

## DTA engine choices

- The implementation uses Vinifera Houses/ActsLike masks and registered native
  house aliases, not MO countries or Ares rules. Friendly production, costs,
  unit buffs and generators use private types. Enemy recipes and tier buffs use
  separate private identities, including when both sides share a faction.
- Enemy MCVs deploy into their protected starting yards through DTA's normal
  deployment path, initializing native base plans. Allied AI MCVs also deploy
  automatically. Computer houses receive explicit production, autocreate,
  automated base-building and AI-trigger startup actions. Native first-ownable
  lookups select the actual starting yard; replacement identities also populate
  BaseUnit/HarvesterUnit/PadAircraft lists. AI conditions distinguish their own
  production types from opponents' private types.
- Native skirmish handicaps are Easy 2, Normal 1, Hard 0, Brutal 4, Extreme 5
  and Ultimate 6. Impossible uses Ultimate's native handicap with a separate
  25% enemy firepower bonus. Opening wave baselines are 3/6/9/10/12/14/16;
  each subsequent wave grows by that baseline before the selected multiplier.
- Waves begin at minutes 5/10/15 with one/two/three fronts. Deliveries reserve
  groups of at most 20 enemy units, up to 480 shared. Friendly reinforcements
  share ten 15-unit reservations, up to 150. Native semipersistent death tags
  release individual groups. Private identities prevent ordinary AI recipes
  from recruiting those groups; deployment tags are retained. Missing native
  death evidence conservatively holds a reservation rather than overflowing it.
- Each delivery chain starts its next five-minute interval only after its
  complete delivery. Capacity-delayed opening batches switch to stronger
  rosters after minute 30 without growing. Advanced/special ground shares rise
  at minutes 15, 30 and 45. Aircraft use separate teams within the same cap.
- Scripted air support uses native Orca, Apache, Longbow and Hind VTOL types.
  Private attack copies have unlimited ammunition so they do not depend on
  surviving pads or enter an untracked rearm cycle. Ordinary aircraft retain
  native ammunition and docks. Air replaces 15% of a wave from minute 15 and
  25% from minute 30. Additional heavy fixed-wing aircraft remain excluded.
- The native templated overlay displays **Until Victory** and **Next enemy
  wave** in simulation seconds. Purchased allied reinforcement timers use the
  same variables reset by their real delivery chains. DTA displays all friendly
  clocks together in co-op; zero means waiting for capacity and -1 means that
  chain completed its scheduled deliveries.
- Fundraising uses native action 106 for a direct 1,000–4,000 credit deposit
  every 300 simulation seconds per enabled recipient. Higher ranks change the
  amount, not the number of timers. Run outcomes stop further deposits.
- Support powers unlock DTA's Infantry Paradrop for each human. Faction offensive
  powers unlock GDI's Ion Cannon and Airstrike, Nod's Nuclear Strike, Allied
  Chrono Vortex or Soviet Nuclear Strike. These use the existing DTA player
  reward integration, not MO power definitions. Airstrike, nuclear and vortex
  powers require construction of their separate human-only provider buildings;
  Ion Cannon and Paradrop are directly granted repeating powers. AI helpers and
  enemies receive no perk power grants or upgraded providers. The existing DTA
  Ion Cannon exclusivity rules also apply, preventing native Ion Cannon grants
  from sharing the player's upgraded global effect.
- Power upgrades have six ranks and use each power's supported DTA buffs and
  existing stack caps: recharge, damage, radius, provider cost/construction and
  paradrop payload. They affect only enabled Fortress powers and do not unlock
  powers. Each human has their own native power charge; co-op paradrop teams
  belong to the clicking human and use the faction's private rifle infantry.
- Special Building Limit has three ranks. It uses DTA's positive-limit buff
  handling on friendly private buildings without granting access. Enabled
  player power providers gain up to three extra launch sites using DTA's
  separate provider/power identities, each charging independently. AI receives
  no additional player launch sites.
- The once-per-run reserve activation also applies native Iron Curtain to the
  objective alone. It uses DTA's unchanged configured duration, currently 900
  frames / 60 simulation seconds, rather than MO's ten-second shield.
- Arrival aprons use DTA pavement and its installed passable NOBUILD overlay,
  without MO terrain IDs or invisible Ares buildings. Full native foundations,
  source structures, scenery, height, resources and playable bounds are checked
  before launch. All six formations maintain 32-cell friendly and 40-cell
  hostile clearance; camp centers are at least 32 cells apart. Original maps
  remain untouched. At preparation, the existing DTA power installer registers
  stable Action.ini entries and managed Rules.ini/Art.ini effect helpers. Managed
  effect helpers are cleared before preparation and after Fortress releases its
  runtime, using the same cleanup as other randomizer modes.

The current catalogue exposes **27 perks and 27 Challenges**. Building-income
upgrades, emergency objective repair and veteran defenses are intentionally
excluded. DTA's available power catalogue replaces MO's support/superweapon rank
lists; the two power unlock perks each have one rank. Aircraft handling and the
shared co-op countdown overlay retain the DTA adaptations described above.

Possible replacements for the objective's visual are listed in
[Neutral objective candidates](FINAL_FORTRESS_OBJECTIVES.md). The current building
is retained until a replacement is chosen and its placement is reviewed.

## Co-op

In Settings, enable **Final Fortress co-op**, choose **2** or **3** players and
open **Co-op Connection…**. Host chooses the count and shares its
ZeroTier Managed IPv4 and pairing code. Guests choose Join and distinct names;
native lobby arrival order assigns seats. Guests receive the host's count
automatically. The dialog has no player-count or
seat selector. DTA's existing transport verifies all-peer UDP reachability and
matching installation files; it uses TCP 19420 and the existing native game
endpoints, UDP 1234 by default on separate PCs.

The host freezes faction, difficulty, multiplier, perks, Challenge stacks and
the human roster. Guests advertise personal Fundraising ranks before preparation.
Other perks come from the host without transferring ownership. Helpers fill only
unused friendly seats, share host perks and use host Fundraising. Co-op does not
multiply waves automatically.

Every peer prepares its native map locally, compares the exact SHA-256 and
acknowledges readiness. Map and local spawn bytes are checked again before
launch. Failed preparation, mismatched bytes or a lobby disconnect cancel a
pending launch. Each machine watches matching native run markers and credits
its own save. Joined-run IDs and atomic receipts prevent duplicate rewards.
Reconnect the whole lobby between games; there is no mid-game joining.

## Persistence and review status

Ordinary progression uses `final_fortress_state.json` and its OS lock in DTA's
APP_DIR. Plans and saves have DTA-owned version 1 and reject another game's
state. Recovery scans DTA's rotating DEBUG logs, requires this run's START and
terminal markers, backs up changed saves and credits only missing receipts.
Generic Winner rows and elapsed launcher time never award completion.

Both source and compiled launchers expose **Standard** and **Debug (all unlocks)**
in the Profile selector at the top of Final Fortress. Selecting Debug creates a
separate `final_fortress_testing_state.json`, purchasing and enabling every perk
at its maximum rank. Challenges remain individually selectable. Later catalogue
additions receive their maximum ranks when the profile is selected again;
existing selections and run receipts are retained. Standard progression uses its
own file and is never overwritten by debug unlocks.

Source compilation, production configuration validation and inspection of
prepared native map/spawn artifacts cover this implementation. Packed overlay
streams retain numeric chunk order and use compressed blocks within native LCW
buffer limits. Prepared examples and UI screenshots are under the ignored
`generated_maps/final_fortress_preview/` directory. No automated test suites were
added or run.

The launcher was visually inspected at normal and minimum window sizes. Its
Defense setup, Permanent perks, Challenge and Run results layout follows MO;
Setup fields use two columns when space allows. Narrow windows stack the perk
and Challenge panes vertically; overflowing content scrolls while the launch
button remains available. Live DTA 16.2.2 GDI, Nod and Allied startups with every debug
perk enabled and two AI helpers reached their native START markers and continued running.
The objective/base and active countdowns were visible. This verifies startup,
not a complete 60-minute run. Native power grants use registered human country
owners, and private production includes each friendly country's ownership mask.
The subsequent defense, collector and native-AI initialization changes were
checked through prepared-map inspection; AI construction and attacks still need
live confirmation in a new run. No desktop input was simulated for those changes.

The V37 objective and faction-specific defense ranks were also checked through
baseline and maximum-perk map/spawn generation for all four factions. Placement
and scripting validation passed, with 7,000/14,000 objective HP and the expected
four/six/eight/six maximum friendly emplacements. Temporary save checks confirmed
faction purchase caps, retained rank 4 ownership after switching to GDI, and
maximum debug unlocks. The Windows launcher was rebuilt with these changes.
Their in-game appearance and behavior still need manual confirmation in a new run.

Normal gameplay still needs to confirm player power grants and provider charging,
human-specific co-op paradrops, power upgrades, building limits, objective-only
shielding, full mixed-team arrivals, tag retention
after capture/deployment, continued capped deliveries, helper base production
and attacks, VTOL attacks, crate collector routing, exact per-house income,
objective health thresholds, countdown rendering, native victory/defeat scoring,
recovery and real two/three-PC agreement. Generated artifacts establish emitted
wiring and placement, not live engine behavior.

Native implementation references:
[Vinifera mapping](https://vinifera.readthedocs.io/en/latest/Mapping.html),
[spawner options](https://vinifera.readthedocs.io/en/latest/Miscellaneous.html),
[Vinifera source](https://github.com/Vinifera-Developers/Vinifera).
