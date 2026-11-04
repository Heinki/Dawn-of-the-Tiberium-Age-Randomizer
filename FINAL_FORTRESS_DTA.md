# Final Fortress in DTA

Select **Settings → Game Mode → Final Fortress**. The workspace follows Mental
Omega's Defense setup, Permanent perks, Challenge and Run results layout. Settings
remains available; choosing another Game Mode restores the previous workspace.
Defense setup, Permanent perks, Challenge and Run results have separate tabs.
While Final Fortress is selected, Settings shows only Game Mode, Fortress co-op
and launcher appearance; campaign seed, mission and reward settings are hidden.
Fortress uses its own purchases, preferences, run snapshots and Defensive Points.
Campaign, Grid, Shop and Archipelago saves are independent.

Permanent perks use the Shop-style arrow controls: **◀** refunds the highest
purchased rank at its full Defensive Points cost, and **▶** buys the next rank.
The same actions are available through Left/Right keys and the Refund rank and
Buy / upgrade buttons. Refunded points can be spent on another perk immediately.
Purchases and refunds are locked during an active run. Disabling a perk retains
its purchased ranks without refunding points. Refunds also work on ranks retained
above the current faction's usable limit. Finished run snapshots and reward
receipts remain unchanged when points are reallocated for a later run.

Defend the Civilian Armory headquarters (`ARMORY`) beside the initial MCV for
60 simulation minutes. Choose **King of the Hills Extreme**, **Cliffs of Lunacy**,
**Cliffs of Insanity**, **Hardpoints**, **Radial Range**, or **Castle Rock** from
the Map dropdown. The selection persists between launches and is frozen into
each solo or co-op run. [Map layouts](FINAL_FORTRESS_MAPS.md) describe the starts
and the installed-map review. Choose GDI, Nod, Allies or Soviet, one of
the seven DTA difficulty grades, and a wave multiplier from x1 through x10.
Normal skirmish AI continues alongside scripted waves. Only starting enemy
construction yards and their fixed defenses are protected; expansion yards,
factories, power plants and other ordinary buildings remain destructible.
Protected yards and fixed defenses also disable repairability, which DTA uses
to deny C4 placement even when a player forces the attack command.
Runs without a starting refinery receive no harvester. The Starting buildings
perk supplies one faction harvester per friendly house at refinery rank and
above. Soviet radar ranks grant the Soviet Radar Dome (`SDOME`); Allied ranks
grant the Allied Radar Dome (`RADOME`). Preplaced refineries do not grant a
duplicate collector. Their placement-only
types are hidden from human and AI construction and satisfy the same technology
prerequisites as ordinary friendly refineries. Newly built refineries still supply
their native collector. Starting defenses form a perimeter around the friendly production core. Each rank
unlocks another faction defense type, with these grants:

- GDI: Guard Tower and Advanced Guard Tower; maximum rank 2, six of each type (12 total).
- Nod: Gun Turret, Obelisk and SAM Site; maximum rank 3, four of each type (12 total).
- Soviet: Flame Tower, Tesla Coil and SAM Site; maximum rank 3, four of each type (12 total).
- Allies: Pill Box, Gun Turret, Camouflaged Pill Box and AA Gun; maximum rank 4,
  three of each type (12 total).

The UI shows the chosen faction's ranks and limit. Higher purchased ranks are
retained when switching to a faction with fewer types; purchases beyond that
faction's limit are disabled. Existing rank 3/4 purchases remain valid. Profiles
already refunded by the earlier two-rank version keep those refunds and can buy
the newly available ranks.
Each enemy starts with four fixed emplacements covering all its available types.
Extra friendly generators cover only the actual starting power shortfall,
accounting for More power ranks. The headquarters uses ARMORY's native 2×2 art,
with its training function disabled, while retaining the Fortress base health of 7,000 and existing objective
ownership, durability upgrades, reserve shield and defeat behavior.

Six guarded crates exist at startup. First collection pays 10 Defensive Points
to every human. Human collectors receive their own frozen cash or unit payload;
allied helper collection routes the payload to the host. Enemy units do not recover camps. Guard deaths grant no
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
- Buildable catalogue aliases share one friendly production clone. Soviet Rifle
  Infantry and Rocket Soldiers retain their native Soviet voices without adding
  duplicate sidebar entries. Starting troops, paradrops and helper AI recipes
  route both native identities to that same clone; native originals remain
  unavailable to friendly production.
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
  before launch. Camp formations use each map's reviewed friendly/hostile clearance and
  inter-camp spacing; the original map retains its 32/40/32-cell limits. Original maps
  remain untouched. At preparation, the existing DTA power installer registers
  stable Action.ini entries and managed Rules.ini/Art.ini effect helpers. Managed
  effect helpers are cleared before preparation and after Fortress releases its
  runtime, using the same cleanup as other randomizer modes.

The current catalogue exposes **38 perks and 27 Challenges**. Building-income
upgrades, emergency objective repair and veteran defenses are intentionally
excluded. DTA's available power catalogue replaces MO's support/superweapon rank
lists; the two power unlock perks each have one rank. Aircraft handling and the
shared co-op countdown overlay retain the DTA adaptations described above.

Four additional perk lines use the existing purchases, enable/disable controls
and full-cost rank refunds:

| Perk | Ranks and Defensive Points cost per rank | Effect |
| --- | --- | --- |
| Specialist support technology | 1 rank: 250 | GDI Mobile Sensor Array; Nod Mobile Repair Vehicle and Stealth Generator; Allied Gap Generator; Soviet Shore Artillery. Vehicles require the faction war factory and radar; buildings require the faction construction yard and radar. Native credit costs, power demand and limits remain. |
| Targeting and ammunition | 3 ranks: 100 / 220 / 400 | +0.5 / +1 / +1.5 cells of weapon range and +1 / +2 / +3 ammunition on catalogue-eligible friendly mobile types. Existing DTA buff caps and projectile travel margins apply. Demolition Truck range, defensive-building range and infinite ammunition are excluded. |
| Fortified infrastructure | 3 ranks: 100 / 220 / 400 | +15% / +30% / +45% maximum health on friendly construction yards, production buildings, refineries, generators and silos, including future construction. Objective, defenses and support structures retain their separate health rules. |
| Transport capacity | 3 ranks: 80 / 160 / 280 | +1 / +2 / +3 passenger slots on eligible APCs, Chinooks and landing craft. Gunner and sealed transports are excluded. |

These perks grant no starting units, buildings or passengers. Friendly human and
helper houses share their private production types; enemy copies retain native
values. The Mobile Sensor Array retains its linked deployed sensor structure
and can undeploy back into its private mobile type. Specialist access does not
assign a hero limit to ordinarily unlimited support vehicles.

Seven expedition and defense perks extend the same purchases and refunds:

| Perk | Ranks and Defensive Points cost per rank | Effect |
| --- | --- | --- |
| Fortified Emplacements | 3: 120 / 260 / 480 | +15% / +30% / +45% health to friendly defensive buildings, including outpost defenses. |
| Expedition Salvage | 3: 100 / 220 / 400 | Every collected camp pays an additional 1,000 / 2,000 / 3,000 credits alongside its normal reward. |
| Priority Reinforcements | 3: 160 / 320 / 560 | First and subsequent periodic deliveries use 4:45 / 4:30 / 4:15 intervals. Requires Periodic reinforcements; capacity waits and the shared 150-unit living cap remain. |
| Hazard Training | 1: 180 | All friendly infantry gain native Tiberium and Tiberium gas protection. Ordinary weapon damage remains. |
| Advanced Spoils | 3: 150 / 300 / 550 | Replace Tier 1 and Tier 2 camp unit rolls with mixed faction squads of 5 / 6 / 8 units. Cash and special-unit rolls remain. |
| Veteran Spoils | 2: 180 / 360 | All camp reward units arrive Veteran / Elite, including Advanced Spoils squads. |
| Forward Outposts | 6: 200 / 350 / 550 / 800 / 1,150 / 1,600 | Each collected camp deploys a powered faction outpost, with cumulative grants described below. |

Forward Outposts ranks grant faction-native buildings:

1. Barracks, two basic defenses and enough advanced generators.
2. Add refinery and one faction harvester when claimed.
3. Add faction radar and air defense.
4. Add vehicle production and the remaining faction defense types.
5. Add helipad and repair depot.
6. Add construction yard and a 12-emplacement perimeter, alternating every faction defense type.

Friendly starting bases use compact production cores with 12 defenses at maximum
Starting defenses rank. Production footprints stay inside the perimeter; initial
MCV deployment, objective, arrivals and starting armies retain clear tiles.
Cliffs and other impassable terrain shape the available perimeter sectors.

Camp outpost buildings appear only after a human or allied helper recovers the
crate position. They do not exist as passive or hidden structures before pickup.
The collecting human owns the deployment; allied helper collections route to the
host. Enemy units cannot trigger recovery. Buildings deploy at the same compact,
faction-correct positions used by version 6, with no relocation of blocked plots.
They cannot be sold, captured with engineers or undeployed. Destroyed grants do
not rebuild. Ordinary native refinery construction supplies its matching collector.

Generators deploy first. Each foundation uses non-forced native placement and
retries once per simulation second until clear. Human and enemy units are never
removed or crushed to force a building into its reserved position. A one-time
completion flag prevents automatic replacement after destruction, and every
attempt stops at the terminal run flag.

Native creation actions and building-existence events are bound after final INI
serialization. They use the reviewed runtime building heap prefix of 501 rather
than the catalogue's 498 entries, then the actual emitted map type order. Runtime
binary and registration fingerprints guard that reviewed mapping so unsupported
installations cannot silently deliver foreign buildings.

Production occupies the inner core, with defenses around it. Foundations use
connected ground at one elevation, avoiding isolated cliff ledges. Buildings have
clearance from other structures, scenery, existing units, arrival lanes and camp
guards. Compact groups use a perimeter radius of at most 11 cells. If all granted
production cannot fit inside a defended group, the planner removes late production
additions first; it never scatters those buildings beyond protection. An entirely
unusable site grants no outpost and displays that fact. Power covers the actual
compound, including More power ranks. Buildings remain absent until collection, then wait for clear foundations.

New deployments are created directly under the receiving house and do not
contribute capture score. Version 6 receipts retain their original transfer
correction and zero-point loss markers.

Run plan version 7 freezes recovery-gated deployments. Versions 1–6 retain their
original frozen layouts, delivery strategy and receipts. The installed-map review is
recorded in [the outpost audit](FINAL_FORTRESS_OUTPOSTS_AUDIT.md).

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
APP_DIR. Saves use DTA-owned schema version 1; new plans use version 7, while
version 1–6 receipts retain their frozen effects and starting economy. Other games' state is
rejected. Recovery scans DTA's rotating DEBUG logs, requires this run's START and
terminal markers, backs up changed saves and credits only missing receipts.
Generic Winner rows and elapsed launcher time never award completion.

Source gameplay testing uses the developer flag `TESTING_PROFILE_ENABLED` in
`randomizer/final_fortress/feature.py`. Set it to `True` and restart the source
launcher: all configured perks are already purchased at maximum rank. Set it
to `False` and restart to restore ordinary progression. There is no JSON,
environment-variable or player-facing override.

Compiled EXEs always disable the testing profile, even if the source flag was
left enabled during packaging or a testing save is present. Both profile
selection and the all-unlocks initializer enforce this source-only gate.
The ordinary EXE build therefore cannot accidentally distribute the developer
all-perks mode. Its installation report records the effective testing flag.

Enabled source runs automatically use `final_fortress_testing_state.json` and
its separate lock. The header and wallet show "Testing profile". Every configured
perk is purchased at maximum rank; newly added perks are enabled automatically.
The testing wallet starts with at least 1,000,000 Defensive Points. A fresh
profile uses GDI, Normal difficulty, x1 waves and no Challenges. Existing disabled
perk selections and preferences are preserved. Testing ranks refresh at startup,
including newly added perks; an active run retains its frozen gameplay loadout.
Ordinary saves and rewards remain isolated. Testing saves are not packaged.

Final scores are read from Vinifera's native Winner/Loser records without
requiring the older `Sending game results.` preamble. Human names and actual
remapped color schemes identify friendly houses, including helpers when the
commander selects their original color. The full friendly table must be read
before kill rewards are credited and automatic game closure is scheduled.

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
