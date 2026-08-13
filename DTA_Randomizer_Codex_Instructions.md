# DTA Randomizer Porting & Research Instructions for Codex

## Project Goal

We want to create a randomizer for **Dawn of the Tiberium Age (DTA)** by reusing as much as possible from our existing **Mental Omega Randomizer**.

The existing Mental Omega Randomizer is the primary source implementation for:

- UI
- randomizer flow
- progression
- seed handling
- mission selection
- reward handling
- map modification architecture
- launching
- state persistence
- general UX

The goal is **not** to redesign the existing application.

The main job is to replace or adapt the **game-specific and engine-specific parts** so that the same randomizer concept works with DTA.

---

# Important Source Locations

## Primary Local Source

The most important reference is the local, working Mental Omega Randomizer installation:

```text
C:\Spiele\Mental Omega - Randomizer (try)\RandomizerLauncher
```

Codex must inspect this local version first where possible.

This local version represents the currently working behavior and UI.

It should be treated as the primary source for:

- actual UI structure
- current layout
- current navigation
- current settings
- current randomizer flow
- actual mission selection behavior
- actual reward flow
- current state/progression behavior
- current launcher behavior
- current runtime configuration
- any differences from the GitHub repository
- files or functionality that may not yet be committed
- current configuration files
- current assets
- current generated files
- current map-processing behavior

Do **not** assume that GitHub is fully identical to the local working version.

If there is a difference between the local implementation and GitHub, document it and prefer the local working implementation unless there is a clear reason not to.

---

## GitHub Source

Repository:

```text
https://github.com/Heinki/Mental-Omega-Randomizer
```

Use GitHub as an additional source for:

- code history
- documentation
- architecture
- comments
- developer notes
- technical findings
- commits
- repository structure

Important files and directories include:

```text
README.md
DEVELOPER_GUIDE.md
TECHNICAL_FINDINGS.md
randomizer/
randomizer/maps/
randomizer/missions/
randomizer/rewards/
randomizer/launch/
randomizer/ui/
configs/
```

The GitHub repository and local version must be compared rather than treated as automatically identical.

---

# Target Game

## Dawn of the Tiberium Age

Reference:

```text
https://www.moddb.com/mods/the-dawn-of-the-tiberium-age
```

DTA uses the **Tiberian Sun engine** with **Vinifera**.

This is a different engine stack from Mental Omega.

---

# Engine Context

## Mental Omega

Mental Omega uses:

```text
Red Alert 2: Yuri's Revenge
        ↓
       Ares
        ↓
      Phobos
        ↓
  Mental Omega
```

---

## Dawn of the Tiberium Age

DTA is based on:

```text
Tiberian Sun
      ↓
   Vinifera
      ↓
      DTA
```

Vinifera source should be inspected where necessary because engine behavior may differ substantially from Yuri's Revenge, Ares, and Phobos.

Do not assume that an Ares/Phobos feature has a direct Vinifera equivalent.

Do not assume that Tiberian Sun behaves exactly like Yuri's Revenge.

---

# Core Rule

## Do Not Rewrite the Randomizer

The purpose of this project is to **port the existing Mental Omega Randomizer architecture to DTA**.

Do not unnecessarily rebuild:

- the UI
- progression systems
- seed handling
- reward selection UX
- settings UX
- navigation
- state management
- randomizer screens
- general application structure

Where possible:

```text
KEEP EXISTING RANDOMIZER SYSTEM
          +
REPLACE GAME-SPECIFIC ADAPTERS
```

The desired result is closer to:

```text
C&C Campaign Randomizer
        |
        +-- Mental Omega
        |
        +-- Dawn of the Tiberium Age
```

rather than:

```text
Mental Omega Randomizer

and

Completely Separate DTA Randomizer
```

---

# Phase 1 — Audit the Existing Mental Omega Randomizer

## Task 1 — Inspect the Local Working Version

Start with:

```text
C:\Spiele\Mental Omega - Randomizer (try)\RandomizerLauncher
```

Inspect the project structure and identify:

- application entry point
- UI framework
- UI files
- settings system
- seed generation
- run creation
- mission selection
- grid progression
- mission list
- unlock/reward screens
- state persistence
- save files
- configuration files
- map generation
- mission discovery
- launch logic
- logging
- debugging
- assets
- icons
- cameos
- faction configuration
- reward configuration

Document the actual runtime architecture.

---

## Task 2 — Audit the Existing UI

The UI of the Mental Omega Randomizer is the visual and UX reference for the DTA version.

Inspect the actual local running application.

Document:

- window structure
- navigation
- tabs
- screens
- buttons
- settings
- grid
- mission list
- unlock view
- reward view
- tooltips
- mission information
- faction filters
- seed entry
- run-start flow
- mission-start flow
- post-mission flow
- victory/reward flow
- progress indicators
- error dialogs
- launch status
- colors/themes
- dark mode
- image/cameo handling
- icons
- spacing/layout behavior

### Important

Do **not** redesign these unless DTA technically requires a change.

The DTA implementation should reuse the Mental Omega UI as much as possible.

The UI should receive **DTA data instead of Mental Omega data**.

Examples:

```text
MO missions       → DTA missions
MO factions       → DTA factions
MO units          → DTA units
MO cameos         → DTA cameos
MO rewards        → DTA-compatible rewards
MO launcher data  → DTA launcher data
```

The UI architecture itself should remain.

---

## Task 3 — Compare Local Version Against GitHub

Compare:

```text
C:\Spiele\Mental Omega - Randomizer (try)\RandomizerLauncher
```

against:

```text
https://github.com/Heinki/Mental-Omega-Randomizer
```

Document:

- local-only files
- GitHub-only files
- modified files
- configuration differences
- runtime differences
- UI differences
- uncommitted functionality
- experimental systems
- generated files that reveal runtime behavior

Produce:

```text
MENTAL_OMEGA_SOURCE_AUDIT.md
```

Classify differences as:

```text
LOCAL IS NEWER
GITHUB IS NEWER
RUNTIME GENERATED
CONFIGURATION ONLY
UNKNOWN
```

---

# Phase 2 — Separate Generic Systems From MO-Specific Systems

## Task 4 — Classify the Existing Architecture

For every major subsystem classify it as:

```text
GAME-INDEPENDENT
MENTAL-OMEGA-SPECIFIC
YR-SPECIFIC
ARES-SPECIFIC
PHOBOS-SPECIFIC
LAUNCHER-SPECIFIC
UNKNOWN
```

Create a table like:

| Component | Purpose | Classification | Reusable for DTA? | Required changes |
|---|---|---:|---:|---|
| UI | Application UX | Game-independent | Yes | Replace game data |
| Seed generation | Deterministic runs | Game-independent | Yes | None/minor |
| Grid progression | Run progression | Game-independent | Yes | None/minor |
| Reward planning | Reward selection | Mostly generic | Yes | DTA reward catalogue |
| Mission discovery | Find MO missions | MO-specific | No | DTA implementation |
| Map modification | Modify maps | Partly engine-specific | Maybe | Verify TS format |
| Launching | Start YR/MO | Engine-specific | No | DTA implementation |
| Clone system | Player-only buffs | Ares/Phobos/YR dependent | Unknown | Research |
| Trigger hooks | Victory/objectives | Engine-specific | Unknown | Research |

---

# Phase 3 — Establish the DTA Technical Baseline

## Task 5 — Determine the Exact DTA Engine Stack

Identify:

- DTA version
- Tiberian Sun executable/version
- Vinifera version
- Vinifera branch/build if detectable
- DTA client version
- CnCNet client usage
- launch executables
- DLLs
- injectors
- additional patches
- rendering components
- mission format
- rules format
- campaign metadata format

Do not assume stock Tiberian Sun behavior if Vinifera changes it.

Produce:

```text
DTA_ENGINE_BASELINE.md
```

---

# Phase 4 — Compare YR/Ares/Phobos Against TS/Vinifera

## Task 6 — Build an Engine Capability Matrix

Compare:

```text
YR + Ares + Phobos
```

with:

```text
TS + Vinifera
```

Focus specifically on features used by the Mental Omega Randomizer.

Investigate:

- TechnoTypes
- InfantryTypes
- Vehicle/UnitTypes
- AircraftTypes
- BuildingTypes
- Weapons
- Warheads
- Projectiles
- Owners
- Houses
- Countries
- Sides
- Prerequisites
- TechLevel
- BuildLimit
- Cost
- BuildTime
- Strength
- Armor
- Speed
- Sight
- Range
- ROF
- Veterancy
- Cloak
- Sensors
- Self-healing
- Superweapons
- map-local rules overrides
- triggers
- tags
- teams
- task forces
- scripts
- AI triggers
- mission globals
- campaign definitions
- loose map overrides
- command-line launching
- debug/logging
- mission result detection

Classify every relevant feature:

```text
A — IDENTICAL / REUSABLE

B — SIMILAR BUT SYNTAX OR BEHAVIOR DIFFERS

C — NOT SUPPORTED

D — VINIFERA HAS AN ALTERNATIVE

E — REQUIRES A DIFFERENT RANDOMIZER DESIGN

F — NEEDS LIVE TEST
```

---

# Phase 5 — DTA Mission Discovery

## Task 7 — Find How DTA Defines Campaigns

Determine where DTA stores:

- campaign definitions
- mission IDs
- mission filenames
- mission titles
- mission order
- faction/house
- briefings
- difficulty
- campaign progression
- optional/bonus missions
- mission grouping

Do not assume DTA uses the Mental Omega approach.

Create a standalone diagnostic tool that can output:

```text
Campaign: GDI
Mission ID: ...
Map: ...
Title: ...
Faction/House: ...
Difficulty: ...
Briefing: ...
```

No UI integration yet.

---

# Phase 6 — DTA Rules and Data Extraction

## Task 8 — Locate Gameplay Definitions

Determine where DTA defines:

- infantry
- vehicles
- aircraft
- structures
- weapons
- warheads
- projectiles
- factions
- houses
- sides
- prerequisites
- superweapons
- upgrades
- cameos/icons

Determine file precedence.

Investigate:

```text
global INI
DTA INI
MIX-contained INI
Vinifera INI
map-local INI
client-generated INI
generated runtime INI
```

Document which definitions can safely be overridden inside a generated mission.

---

# Phase 7 — Verify the Existing Map Parser

## Task 9 — Test the Mental Omega Map/INI Parser Against DTA

Do not replace the parser before testing it.

Feed actual DTA mission maps into the existing Mental Omega randomizer parsing code.

Check:

- duplicate keys
- numbered keys
- section ordering
- whitespace
- comments
- triggers
- tags
- team definitions
- scripts
- task forces
- AI definitions
- map-local rules
- binary/packed sections
- unusual Tiberian Sun map data

Determine:

```text
REUSE UNCHANGED
REUSE WITH EXTENSIONS
NEEDS DTA-SPECIFIC PARSER
```

---

# Phase 8 — First Generated DTA Mission

## Task 10 — Create a Minimal Modified Mission

Take one simple DTA campaign mission.

Build a standalone experiment that:

1. finds the original mission
2. copies it
3. makes one harmless visible modification
4. writes a generated loose mission
5. launches it
6. verifies that DTA/Vinifera loads the generated version

Possible test modifications:

```text
Starting credits +100
```

or:

```text
One player unit has +10% Strength
```

Do not implement the full randomizer yet.

The key milestone is:

```text
Original DTA Mission
        ↓
Randomizer-generated copy
        ↓
DTA/Vinifera successfully loads it
```

---

# Phase 9 — Direct Mission Launching

## Task 11 — Trace How the DTA Client Launches a Mission

This is a blocking task.

Determine the complete launch sequence:

```text
DTA Client
    ↓
generated configuration
    ↓
launcher executable
    ↓
Vinifera
    ↓
Tiberian Sun executable
    ↓
scenario/map
```

Record:

- executable names
- command-line arguments
- working directory
- generated INIs
- temporary files
- scenario selection
- house/player selection
- difficulty
- renderer
- game mode
- client-specific values

---

## Task 12 — Test Launcherless Mission Starting

Determine whether a DTA campaign mission can be started directly without requiring the user to manually use the DTA client.

Test relevant options such as:

```text
Game.exe
LaunchVinifera.exe
LaunchVinifera.dat
spawn.ini
command-line scenario selection
client-generated config reuse
DTA-specific arguments
Vinifera-specific arguments
```

Desired final flow:

```text
Randomizer
    ↓
prepare generated mission
    ↓
prepare required runtime config
    ↓
start Vinifera/DTA directly
    ↓
selected mission loads
```

Produce:

```text
DTA_DIRECT_LAUNCH.md
```

Include the exact verified command and required files.

---

# Phase 10 — Player-Only Buff Research

## Task 13 — Investigate Better Alternatives to the MO Clone System

The Mental Omega Randomizer currently uses a copy/clone system for certain buffs.

This helps prevent enemy units using the same TechnoType from receiving player buffs.

However, replacing the original type with cloned types can break mission triggers or scripts that reference the original type.

Before porting this system to DTA, investigate whether Tiberian Sun/Vinifera provides a better solution.

Research:

- house-specific modifiers
- country-specific modifiers
- owner-specific modifiers
- player-only effects
- house-wide bonuses
- per-house firepower modifiers
- per-house armor modifiers
- per-house speed modifiers
- cost modifiers
- ROF modifiers
- veterancy modifiers
- TechnoType extensions
- runtime status effects
- trigger-applied effects
- mission-local upgrades
- creation hooks
- player-only rules
- Vinifera extension systems

Main question:

```text
Can we buff only the human player's instances of a TechnoType
without creating a replacement TechnoType?
```

Example:

```text
Player Tank:
    +25% HP

Enemy Tank:
    unchanged

TechnoType:
    remains the original Tank type
```

If Vinifera supports this, prefer it over cloning.

---

# Phase 11 — Determine Why Clones Break Triggers

## Task 14 — Analyze DTA/TS Trigger Semantics

Identify where mission logic references:

- exact TechnoType
- object instance
- owner
- house
- category
- tag
- team
- script
- trigger
- mission global

Investigate cases such as:

```text
Destroy all X
Capture X
Object X destroyed
Object enters area
Create Team
Reinforcement
AI Team
Production
Objective condition
Mission win
Mission lose
```

Determine when changing:

```text
TANK
```

into:

```text
RND_TANK
```

causes mission behavior to fail.

Document whether references compare:

```text
object identity
TechnoType ID
owner
category
team
tag
```

---

# Phase 12 — Rank Buff Strategies

## Task 15 — Evaluate Buff Methods in This Order

### Strategy A — House/Country Modifier

Preferred.

Example:

```text
Player owns TANK
Enemy owns TANK

Player:
TANK Strength ×1.25
```

No type replacement.

---

### Strategy B — Runtime Player-Owned Unit Effect

Example:

```text
on unit creation:
    if owner == human:
        apply buff
```

Native TechnoType remains unchanged.

---

### Strategy C — Partial Duplication

For example, duplicate only:

```text
weapon
warhead
projectile
```

if that avoids duplicating the unit type.

---

### Strategy D — Selective Clone System

Use clones only where no safer mechanism exists.

---

### Strategy E — Full Mental Omega Clone System

Use only as fallback.

Do not automatically port the existing clone system just because it already works in Mental Omega.

---

## Mandatory Rule — Unit-Specific Player Buffs

Before creating any TechnoType clone, check whether the installed DTA/Vinifera build can apply the requested buff to the original TechnoType only when it is owned by the human player.

Example:

```text
Human player's RIFLEMAN: +25% damage
Every non-player RIFLEMAN: normal damage
TechnoType ID remains RIFLEMAN
```

If a clean player-only mechanism exists, use it. Do not clone the unit.

House-wide modifiers are clean only for rewards intended to affect every eligible object owned by the player. A house-wide firepower modifier does not satisfy a RIFLEMAN-only reward.

### Immutable Map Objects

Never replace a TechnoType ID in any placed map object.

This prohibition applies to player, allied, neutral, and enemy objects in sections such as:

```text
[Infantry]
[Units]
[Aircraft]
[Structures]
```

It also applies to mission-authored TaskForces, TeamTypes, triggers, actions, tags, scripts, AI teams, reinforcements, and other mission references. These definitions must continue to use the original TechnoType unless a separate, explicitly verified implementation requires otherwise.

### Collision Scan

Before changing the original TechnoType, scan the complete mission for non-player use. Do not limit the scan to units placed at mission start.

The scan must include:

- placed objects owned by any non-player house
- TaskForces and TeamTypes
- AITriggerTypes and AI production
- scripted teams and reinforcements
- trigger actions that create or reference the type
- transports or other mission definitions that can introduce the type
- non-player houses that can produce the type
- shared weapons, warheads, projectiles, and other dependencies that could transfer the buff to unrelated enemy types

If any non-player use is found, or the result is uncertain, treat the TechnoType as shared.

### No Non-Player Collision

If the complete scan proves that no non-player instance can use the TechnoType during the mission, the original TechnoType may receive the reward through map-local rules.

Placed objects keep their original TechnoType ID. For a damage reward, duplicate only a shared weapon/warhead/projectile dependency when necessary to prevent the change from affecting unrelated types.

### Non-Player Collision Found

If any non-player use exists:

1. Leave the original TechnoType and all mission-authored references unchanged.
2. Create a player-production clone, for example `RIFLEMAN_PLAYER`.
3. Apply the reward only to the clone or its cloned weapon dependency.
4. Restrict the clone to the exact human player house.
5. Remove the original type only from the human player's production eligibility while preserving all other houses and existing restrictions.
6. Do not replace the player's starting or scripted map objects. They remain the original, unbuffed type.
7. Make only newly produced human units use the clone.

Expected result:

```text
Enemy/map RIFLEMAN: original, normal damage
Player starting/map RIFLEMAN: original, normal damage
Player newly produced RIFLEMAN_PLAYER: +25% damage
```

If the clone cannot be restricted safely to the exact human house, or the mission has no usable production path, do not apply that reward for the mission.

This production-clone method is a fallback only. It must not become permission to port the full Mental Omega clone system.

---

# Phase 13 — Technology Unlocking

## Task 16 — Determine DTA Technology Locking Behavior

Test how DTA handles:

```text
TechLevel
BuildLimit
Prerequisite
Owner
RequiredHouses
ForbiddenHouses
```

and Vinifera equivalents/extensions.

Determine effects on:

- human production
- AI production
- scripted reinforcements
- preplaced units
- captured factories
- campaign scripts
- mission triggers
- reinforcement teams

The goal is to lock/unlock player technology without breaking scripted mission behavior.

---

# Phase 14 — DTA Factions

## Task 17 — Build a DTA Faction/House Model

Do not reuse Mental Omega faction assumptions.

Discover DTA's actual:

- sides
- houses
- playable factions
- campaign factions
- subfactions
- AI houses
- neutral houses
- special mission houses

Build the model directly from DTA data.

---

# Phase 15 — DTA Unit and Reward Catalogue

## Task 18 — Generate a DTA Techno Catalogue

Automatically extract:

```text
ID
display name
category
faction
owner
prerequisite
TechLevel
cost
Strength
Armor
Speed
Sight
weapon
BuildLimit
image/cameo
```

Then identify which Mental Omega reward categories are compatible with DTA.

Potential categories include:

```text
Unit Access
Building Access
Health
Damage
Range
ROF
Cost
Speed
Armor
Sight
Veterancy
Build Limit
Special abilities
Superweapons
```

Do not manually recreate the DTA catalogue if the game data can be parsed.

---

# Phase 16 — Trigger and Objective Detection

## Task 19 — Compare YR and TS Mission Triggers

Do not assume the same trigger action numbers or semantics.

Create a comparison table:

| Purpose | Yuri's Revenge | Ares/Phobos | Tiberian Sun | Vinifera |
|---|---|---|---|---|
| Win mission | | | | |
| Lose mission | | | | |
| Create team | | | | |
| Set global | | | | |
| Objective completed | | | | |
| EVA/message | | | | |
| Reinforcement | | | | |

---

## Task 20 — Find the Safest DTA Victory Detection Mechanism

Investigate in this order:

```text
1. Vinifera logging/debug events
2. Existing DTA mission globals
3. Scenario trigger observation
4. Harmless injected marker
5. Team/script marker
6. Save/state inspection
7. Process memory only if absolutely necessary
```

Desired behavior:

```text
DTA Mission
    ↓
Victory event
    ↓
Observable signal
    ↓
Randomizer detects completion
    ↓
Reward/progression
```

The original mission trigger should remain intact.

---

# Phase 17 — UI Integration

## Task 21 — Reuse the Existing Mental Omega UI

After the DTA data layer works, connect it to the existing UI.

The existing UI should be treated as the source implementation.

Reuse:

- main window
- navigation
- settings
- run creation
- seed entry
- grid
- mission list
- unlock screen
- reward display
- tooltips
- state/progress visualization
- launch controls

Only replace game-specific information.

For example:

```text
Mental Omega mission metadata
            ↓
        DTA mission metadata
```

```text
Mental Omega faction list
            ↓
        DTA faction list
```

```text
Mental Omega unit catalogue
            ↓
        DTA unit catalogue
```

```text
Mental Omega cameo lookup
            ↓
        DTA cameo lookup
```

---

# Phase 18 — Asset Handling

## Task 22 — Identify DTA Cameos and UI Assets

Determine where DTA stores:

- unit cameos
- building cameos
- superweapon icons
- faction icons
- campaign icons
- mission artwork
- logos

Reuse the Mental Omega UI's asset-loading architecture if possible.

Only replace the source of assets.

Do not build a completely new image system unless necessary.

---

# Phase 19 — Introduce Game Adapters

## Task 23 — Refactor Toward a Shared Randomizer Core

Where practical, separate shared randomizer logic from game-specific implementations.

Target concept:

```text
randomizer/
    core/
    progression/
    rewards/
    ui/

games/
    mental_omega/
        missions/
        maps/
        launch/
        engine/
        assets/
        config/

    dta/
        missions/
        maps/
        launch/
        engine/
        assets/
        config/
```

An adapter interface might conceptually expose:

```python
discover_missions()
load_map()
generate_map()
launch_mission()
get_units()
get_buildings()
get_factions()
get_cameo()
apply_access()
apply_buff()
install_progress_hooks()
detect_victory()
```

Possible implementations:

```text
MentalOmegaAdapter
DTAAdapter
```

Do not perform a large refactor before understanding the current local architecture.

Prefer small, safe refactors driven by actual shared behavior.

---

# Phase 20 — First Playable DTA Prototype

## Task 24 — Build the Smallest End-to-End Prototype

The first playable version should only prove the core loop.

Success criteria:

```text
1. Detect DTA installation
2. Discover DTA campaign missions
3. Generate a seed
4. Select/randomize a small mission set
5. Show the missions in the EXISTING Mental Omega UI
6. Select a mission
7. Generate a modified/temporary DTA mission
8. Launch it directly
9. Detect mission victory
10. Mark mission completed
11. Unlock next mission
12. Persist the run
```

Do not begin with every reward feature.

---

# Phase 21 — Add Rewards Incrementally

After the base loop works:

```text
Stage 1 — Mission randomization

Stage 2 — Victory detection

Stage 3 — Unit/building access

Stage 4 — Simple buffs

Stage 5 — Player-only unit-specific buffs

Stage 6 — Advanced/special rewards

Stage 7 — Objective hooks

Stage 8 — Full grid validation

Stage 9 — Additional integrations
```

---

# Required Documentation

Codex should create and maintain:

```text
MENTAL_OMEGA_SOURCE_AUDIT.md
DTA_PORTING_ANALYSIS.md
DTA_ENGINE_BASELINE.md
DTA_ENGINE_CAPABILITY_MATRIX.md
DTA_MISSION_FORMAT.md
DTA_DIRECT_LAUNCH.md
DTA_BUFF_RESEARCH.md
DTA_TRIGGER_RESEARCH.md
DTA_IMPLEMENTATION_PLAN.md
```

---

# Evidence Classification

Every important technical conclusion must be classified as one of:

```text
CONFIRMED FROM DTA SOURCE
CONFIRMED FROM VINIFERA SOURCE
CONFIRMED FROM MENTAL OMEGA SOURCE
CONFIRMED FROM LOCAL RANDOMIZER
CONFIRMED BY LIVE TEST
NEEDS LIVE TEST
INFERRED
UNKNOWN
```

Do not present assumptions as facts.

---

# Important Restrictions

## Do Not

- redesign the UI without a technical requirement
- discard the existing Mental Omega architecture
- rewrite working generic systems unnecessarily
- assume GitHub exactly matches the local working version
- assume Yuri's Revenge behavior applies to Tiberian Sun
- assume Ares features exist in Vinifera
- assume Phobos features exist in Vinifera
- automatically port the existing clone system
- change triggers before understanding their semantics
- implement the entire DTA randomizer before validating direct launching
- implement the entire reward system before validating map generation
- hardcode DTA data that can be discovered from game files
- make speculative engine changes without evidence

---

# Blocking Milestones

Before implementing the full DTA port, these milestones must be proven.

## Milestone 1 — Existing UI Understood

Codex can explain how the current local Mental Omega Randomizer UI works and where it obtains all displayed data.

Source:

```text
C:\Spiele\Mental Omega - Randomizer (try)\RandomizerLauncher
```

---

## Milestone 2 — DTA Mission Discovery Works

Codex can enumerate actual DTA campaign missions from installed DTA data.

---

## Milestone 3 — Generated DTA Map Loads

A modified copy of a real DTA campaign mission successfully loads.

---

## Milestone 4 — Direct DTA Launch Works

A chosen generated DTA campaign mission can be started programmatically without requiring the user to manually select it in the client.

---

## Milestone 5 — Victory Can Be Detected

The randomizer can reliably determine that the launched DTA mission was completed successfully.

---

## Milestone 6 — Player-Only Buff Strategy Is Proven

Codex has determined the safest mechanism for buffing only the human player's units.

The preferred solution must avoid cloning TechnoTypes if Vinifera provides a safer mechanism.

---

# First Assignment for Codex

Use the following as the first actual assignment.

---

## Assignment

Do **not** implement the DTA randomizer yet.

First perform a technical source audit and porting analysis.

### Primary source

Inspect the local working Mental Omega Randomizer:

```text
C:\Spiele\Mental Omega - Randomizer (try)\RandomizerLauncher
```

This local version is the primary reference for both functionality and UI.

### Secondary source

Inspect:

```text
https://github.com/Heinki/Mental-Omega-Randomizer
```

Compare the GitHub repository against the local working implementation.

### Target

We want to add support for:

```text
Dawn of the Tiberium Age
```

which uses:

```text
Tiberian Sun + Vinifera
```

instead of:

```text
Yuri's Revenge + Ares + Phobos
```

### Your tasks

1. Inspect the complete local Mental Omega Randomizer architecture.

2. Inspect the actual UI and document:
   - screens
   - navigation
   - settings
   - grid
   - mission list
   - rewards
   - unlocks
   - seed handling
   - progression
   - launch flow
   - state persistence
   - assets/cameos

3. Determine exactly where the UI gets its data.

4. Determine which UI and application systems can be reused unchanged for DTA.

5. Compare the local project with GitHub and identify differences.

6. Identify every subsystem that depends specifically on:
   - Mental Omega
   - Yuri's Revenge
   - Ares
   - Phobos
   - the Mental Omega client/launcher

7. Identify systems that are game-independent and should be reused.

8. Research the Tiberian Sun + Vinifera equivalents for the engine functionality actually required by the randomizer.

9. Investigate DTA campaign mission discovery.

10. Investigate DTA map loading and map-local rules.

11. Investigate how to generate a modified copy of a DTA campaign mission.

12. Investigate exactly how DTA launches missions.

13. Determine whether a selected DTA campaign mission can be launched without manually using the DTA client.

14. Investigate victory/objective detection.

15. Investigate technology locking/unlocking.

16. Investigate player-only buffs.

17. Specifically determine whether Vinifera offers a cleaner alternative to our Mental Omega copy/clone buff system.

18. Determine which kinds of TechnoType cloning or replacement could break DTA/Tiberian Sun mission triggers.

19. Do not redesign the UI.

20. Do not begin the full port until the blocking technical questions are answered.

### Required output

Create:

```text
DTA_PORTING_ANALYSIS.md
```

The document must include:

- local Mental Omega architecture
- UI architecture
- local vs GitHub differences
- reusable systems
- MO-specific systems
- engine-specific systems
- DTA mission discovery findings
- DTA data/rules findings
- map format findings
- launcher findings
- direct-launch findings
- trigger findings
- victory-detection findings
- buff-system findings
- clone-system risks
- Vinifera alternatives
- uncertainties
- experiments required
- recommended implementation order

Every important statement must be labelled as:

```text
CONFIRMED FROM DTA SOURCE
CONFIRMED FROM VINIFERA SOURCE
CONFIRMED FROM MENTAL OMEGA SOURCE
CONFIRMED FROM LOCAL RANDOMIZER
CONFIRMED BY LIVE TEST
NEEDS LIVE TEST
INFERRED
UNKNOWN
```

The analysis should clearly distinguish verified facts from assumptions.

---

# Final Goal

The final implementation should ideally behave like this:

```text
Existing Mental Omega Randomizer UI
                |
                |
        Shared Randomizer Core
                |
        +-------+-------+
        |               |
 Mental Omega          DTA
 YR/Ares/Phobos     TS/Vinifera
        |               |
 MO missions        DTA missions
 MO units           DTA units
 MO launcher        DTA launcher
 MO map logic       DTA map logic
```

The Mental Omega Randomizer is not just an example.

It is the **source implementation** that should be reused wherever technically possible.

The DTA work should primarily replace:

```text
game data
engine-specific behavior
mission discovery
map handling where different
launching
trigger integration
buff implementation
asset lookup
```

while preserving:

```text
UI
UX
progression
seed behavior
run structure
reward presentation
mission selection experience
state handling
general application workflow
```
