<img src="DTA%20Puzzle.png" alt="Dawn of the Tiberium Age Randomizer Launcher puzzle logo" width="500">

# Dawn of the Tiberium Age Randomizer Launcher

This project is the randomizer launcher for DTA 15.1.0 and Vinifera. It reuses the proven progression, reward-planning, launcher UI, save/load, and Archipelago structure from the Mental Omega Randomizer, while using DTA missions, factions, units, powers, rules, maps, cameos, difficulty handling, and launch behavior.

For APWorld installation, room generation, connection, and troubleshooting,
see the [Archipelago player guide](Archipelago/README.md).

## Current DTA integration

- Reads all 81 installed campaign entries from `INI/Battle.ini`.
- Groups missions by the installed DTA campaigns and its STAND-ALONE MISSIONS category.
- Uses DTA-specific mission reward multipliers: stand-alone and non-finale CR Route A/B missions grant x2 rewards; finales, the CR bonus mission, and every CR Route C mission grant x3; all other missions grant x1.
- Reads each mission's DTA difficulty labels from `INI/Battle.ini`, including Brutal, Extreme, Ultimate, and Impossible. An unavailable selection falls back to the closest lower label supported by that mission.
- Generates `spawnmap.ini` from the selected loose DTA mission map without changing the source map.
- Applies DTA's Easy, Medium, or Hard map-code overlay.
- Writes DTA-compatible `spawn.ini` and launches `LaunchVinifera.dat -SPAWN -CD.`.
- Translates displayed game speeds to Tiberian Sun's reversed engine scale: `0 - Slowest` writes `6`, while `6 - Fastest` writes `0`.
- Detects the Vinifera score screen through the newest `Debug/*.LOG` file.
- Reads the installed `INI/Rules.ini` catalogue at runtime.
- Uses DTA's explicit `VehicleTypes` faction blocks for ground-unit rosters instead of broad scenario-placement `Owner` masks. The Rocket Launcher remains GDI-only and the Demolition Truck Soviet-only; hidden faction aliases such as Nod's APC remain merged under one shared reward identity.
- Extracts native TS SHP cameos from DTA MIX archives.
- Applies six broad Player Army buffs through player-production clones: production, cost, movement speed, firepower, reload, and vision. Each vision stack adds one `Sight` cell. Direct player-owned starting units use the same clones; enemy and scripted units retain the installed rules. Armor remains unit-specific.
- Adds unit-specific production-clone buffs where the installed DTA rules support them: production, cost, speed, armor, health, damage, reload, range, sight, ammo, passenger capacity, cloaking, sensors, and self-healing. Native capabilities are not offered redundantly.
- Restricts Commando, Tanya, and Volkov player-production clones to one live unit. Their Command Capacity rewards increase that simultaneous limit by one per stack, matching other capped hero and prototype units.
- Exposes 128 canonical mobile types: 27 infantry, 93 vehicles/naval units, and 8 aircraft. The 117 non-essential types can become access rewards. Engineer, all four MCVs, both resource harvesters, and all four faction hovercraft transports remain permanently available.
- Removes obsolete mission aliases such as `E1N`, `E3N`, and `APCN` from the dashboard. Shared units appear in each faction tab that can use them; global house rewards alone use Neutral. Duplicate display names use faction/editor-qualified labels.
- Treats curated cross-faction equivalents as one Chaos access choice, preferring the current mission faction. The same collapse is applied when launching legacy saves, preventing duplicate Nod/Soviet SAM sidebar entries. Shared equivalent buffs cover rifle infantry, grenadiers, rocket infantry, flamethrowers, APCs, mobile artillery, faction hovercraft transports, repair ships, the Nod torpedo-boat variant, Nod/Allied gun turrets, and Nod/Soviet SAM sites.
- Excludes the base Tiberian Sun Devil's Tongue, Wolverine, and Disruptor types that are not part of DTA's active roster. Campaign-only units use curated faction ownership instead of appearing under every faction solely because their map-editor definitions list every house.
- Uses native DTA cameos for active rewards. Cyborg Prototype, Ilhemoth, Battle Rig, Railgun Tank, Beluminator, Flak Corvette, and Soviet Shore Artillery use text-only entries because DTA has no correct native cameo for them.
- Includes Ion Cannon and Paratroopers as direct player grants. Airstrike, both Nuclear Strikes, and Chrono Vortex use prerequisite-free, buildable player-only clones of their required special structures. Missile and vortex damage/radius buffs clone their animation and weapon chains so campaign AI retains native effects.
- Makes exactly one matching Barracks, War Factory, air production building, or naval yard from the current player faction available without authored tech prerequisites after earning access to a unit that needs that factory. Foreign-faction factories remain unavailable. A deployed MCV/Construction Yard is still required to construct it, and the Unlocks UI explains this factory support on each unit card.
- Includes a stackable `Starting Credits +1,000` reward. Each stack raises the authored player balance for every future launched mission, capped at a 20,000-credit bonus.
- Includes 16 defensive-building unlocks and their supported production, cost, durability, weapon, range, sight, cloaking, sensor, and self-healing buffs. Hidden DTA defenses include Allied Artillery Emplacement, Land Mine, Gap Generator, and Soviet Shore Artillery.
- Offers recharge-speed, damage, and blast-radius rewards for the Ion Cannon. The player receives a map-local clone of the native `IonCannon` engine type. While active, native providers and scripted grants are removed and the native power is recharge-locked, so only the player clone can fire the buffed global Ion effect. Paratroopers gain recharge speed and additional deployed infantry; delivered infantry use the player's buff clone when available.
- Offers optional enemy armor and production-speed rewards. These target only active hostile production families; any family used by the player or a direct ally is excluded.
- Uses the 12 colors exposed by DTA's multiplayer options. The Pink UI choice writes DTA's `DarkMagenta` engine color.
- Awards mission rewards at the observable score-screen victory event. DTA maps do not expose one uniform runtime signal for their varied sub-objectives, so the launcher does not create or display objective-reward checks.

## Unit safety rule

Direct mobile-unit placements owned by the exact player house use a non-buildable player clone when that unit has an active buff. Enemy placements, structures, TaskForce entries, trigger references, script references, and reinforcements retain their original type.

Every unit-specific and Player Army buff uses a map-local Vinifera clone. Normal production routes the human production house from the original to the clone. Earned access uses the same isolation. Only exact player-owned starting mobile units are rewritten; TaskForces, teams, triggers, scripts, reinforcements, and non-player objects remain unchanged.

Generated maps also repeat installed `CollateralDamageCoefficient` values for every map-local exploding TechnoType. This avoids the engine's map-override reset to `1.0`, which otherwise makes low-collateral infantry such as E2/E4 cause catastrophic death explosions.

If a hostile scenario house shares the player's Vinifera `ActsLike` production mask, the generated map gives one side a distinct, already-registered HouseType bit and copies its original production permissions to that bit. Reward clones remain on the player's bit; hostile factories retain only their native production. Scenario-house names, alliances, placed objects, teams, triggers, scripts, and reinforcements keep their authored identities. Launch fails visibly if no safe distinct bit exists instead of silently dropping randomizer access.

Unit and defensive-building access uses the same identity-preservation boundary. Earned production is routed through exact-production-house `_PLAYER` clones. Existing enemy and scripted objects are never replaced.

`DTA Puzzle.png` is shown on this GitHub README and bundled as a compiled-executable resource. The Python window and packaged executable use `launcher_icon.ico`, cut from the center JM section of that existing image; no replacement artwork is used.

## Run from source

From the DTA installation root:

```powershell
python RandomizerLauncher\launcher_gui.py
```

Run the non-invasive adapter check:

```powershell
python RandomizerLauncher\launcher_gui.py --self-check
```

The self-check does not launch DTA and writes its report to `RandomizerLauncher/self_check.json`.

## AI-assisted development

This project was developed with assistance from OpenAI's ChatGPT, including
Codex coding assistance. AI tools have been used to analyze DTA's INI and
mission-map formats, catalogue units, weapons, powers, and image tags for the
UI, and support implementation, refactoring, debugging, testing, and
documentation. Generated suggestions are reviewed, adapted, and validated
against project requirements before inclusion. Final design decisions,
releases, and project behavior remain the responsibility of the project
maintainer.

## Status

The mission catalogue, cameos, map generation, launch contract, broad buffs, unit and defense buffs, production access, automatic production infrastructure, six power unlocks, supported power buffs, starting-credit rewards, optional enemy buffs, Randomizer Arsenal, and Archipelago catalogue are implemented and covered by the non-invasive self-check. Access clones use `TechLevel=1`, remove inherited prerequisites, `BuiltAt`, and nonpositive build locks, and retain positive simultaneous-unit caps. Standard mode activates only rewards matching the selected mission's faction; Chaos retains cross-faction access. Old buffs for still-locked units are ignored at launch instead of granting access.

All 81 active mission maps were checked for map-local power types. The obsolete duplicate `EMPulseSpecial` alias is not a reward.

Live verification is still required for sidebar production, buff effects, unlocks, clone save/load, score-screen completion, and Archipelago item receipt.

Player configurations created before mobile-unit access was introduced are migrated once to enable access and buffs. Existing buff-only seeds are not rewritten because changing their assigned rewards would invalidate completed progression; the launcher asks the player to generate a new seed instead.
