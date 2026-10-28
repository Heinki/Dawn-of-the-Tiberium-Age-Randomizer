# DTA Final Fortress expansion review

Reviewed the installed DTA, C&C Reloaded and Mental Omega launcher catalogues on
28 October 2026. The original comparison below records the catalogue at review
time. Specialist support technology, targeting and ammunition, fortified
infrastructure and transport capacity were subsequently implemented in DTA,
bringing its current catalogue to 31 perks. Their ranks, prices and runtime
behavior are documented in [Final Fortress in DTA](FINAL_FORTRESS_DTA.md).
The remaining entries are proposals rather than enabled gameplay features.

## Headquarters alternatives

The installed native base sprites were extracted to
`generated_maps/final_fortress_preview/hq-alternatives/comparison.png`. Team color
is illustrative gold and idle animations are omitted. These previews are not
in-game rendering verification.

| Building | Foundation | Installed art and placement review |
| --- | --- | --- |
| Forward Command Center (`RAFCOM`) | 2×2 | Recommended for a command-building appearance. Native SHP is present and the current objective position passes the installed map layout validator. |
| Tech Center (`MISS`) | 2×2 | Recommended futuristic alternative. Native SHP is present and the current position passes layout validation. |
| Bio Research Lab (`BIO`) | 2×2 | Native SHP is present and the current position passes layout validation. |
| Research Facility (`BIOE`) | 2×2 | Larger-looking lab variant with the same foundation; native SHP is present and the current position passes layout validation. |
| Arcology (`ARCO`) | 1×1 | Native SHP is present and the foundation passes layout validation, but its small silhouette makes it a weaker HQ choice. |
| Stock Exchange (`STEX`) | 3×3 | Native SHP is present, but it fails layout validation at the current position. It would require relocation and removal of its native cash payout. |
| Field Generator (`CA0007`) | 1×2 | Rules and art entries exist, but the expected native sprite was not found in the inspected top-level installed MIX archives. Do not select it based on the INI entry alone. |

Any replacement must preserve the objective's 7,000 base health, durability
upgrades, ownership, loss trigger and reserve shield. Native power consumption,
crew spawning, storage, economy, base expansion and technology benefits should
be reviewed and neutralized independently of the chosen appearance.

## Catalogue comparison

| Launcher | Fortress perks | Challenge entries |
| --- | ---: | ---: |
| DTA | 27 | 27 |
| C&C Reloaded | 29 | 37 |
| Mental Omega | 34 | 38 |

Reloaded has two perk IDs absent from DTA: emergency objective repair and veteran
defenses. Mental Omega also has transport capacity, fortified infrastructure,
open-topped transports, stolen-tech access and special-building income.
Shared perk IDs do not imply equivalent payloads: support powers, special units,
starting defenses and reinforcement rosters are adapted to each game.

## Recommended additions

These capabilities already have relevant DTA runtime code or installed native
identities. Each still needs Fortress configuration, pricing, descriptions and
private friendly routing before it becomes a purchasable perk.

| Proposal | Existing support | Intended scope |
| --- | --- | --- |
| Fortified infrastructure | Mental Omega's perk design and DTA's private building `Strength` overrides | Production and economy buildings, excluding the objective and defenses. The MO ranks of +15%, +30% and +45% are a starting design reference, not approved DTA balance. |
| Transport capacity | MO's perk and DTA's `passenger_capacity` buff | Extra passenger slots on eligible APCs, Chinooks and landing craft; no free units or passengers. |
| Amphibious conversion | DTA's existing Amphibious Drive reward, modeled on its native Hover MLRS movement | Eligible dry-land vehicles only; retain the reviewed locomotor, speed-type and movement-zone combination. |
| Resource logistics | DTA Shop's Room for Tiberium modifier and existing collector mobility/durability buffs | Larger refinery/silo storage and optionally better surviving collectors. Storage does not increase resource value or grant a starting harvester. |
| Mobility and targeting | Existing DTA speed and weapon-range buffs | Eligible mobile units with existing caps and projectile travel-range handling; exclude Demolition Truck range changes. |
| Extra ammunition | Existing DTA ammo buff | Finite-ammunition friendly aircraft only. Do not sell ammo ranks for unlimited-ammunition scripted waves. |
| Specialist support technology | Installed DTA unit/building identities | A separate unlock line for support roles omitted from the current three-rank hero/special-unit perk. |

Concrete specialist candidates include GDI's Mobile Sensor Array (`MSA`), Nod's
Mobile Repair Vehicle (`MRV`) and Stealth Generator (`SGEN`), Allied Gap Generator
(`RAGAP`) or Artillery Emplacement (`ART`), and Soviet Shore Artillery (`RAPARTY`).
Those candidates need faction-specific balance; they are not equivalent in power.
Building unlocks need their own construction and prerequisite handling rather
than being passed through the current mobile special-unit factory path.

## Challenge opportunities

Mental Omega and Reloaded expose enemy regeneration, cloaking and additional
reinforcement/offensive power challenges that DTA Fortress currently omits.
DTA already has self-healing and cloaking unit overrides, so those are practical
candidate additions with explicit tier eligibility and hostile-only routing.
Existing reconnaissance would provide counterplay to cloaked attackers.

DTA's campaign enemy scripting also implements Ion Thunderbolt. A Fortress
version is a distinctive strategic-pressure candidate, but needs its own
cooldown, targeting, warning, terminal-stop and reward review. Faction-native
airstrikes or other offensive powers require similar integration. The MO names
Bloodhounds and Moon reinforcements are not DTA feature requirements.

The current five-minute wave spacing and living-unit budgets should remain
explicit when adapting team-delay, reinforcement-size or airborne-pressure
modifiers. Campaign trigger modifiers are not automatically effective on
Fortress's separate delivery chains.

## Features requiring more engine work

- Emergency full objective repair and veteran defenses remain intentionally
  excluded from DTA Fortress; the current adapter does not implement them.
- Open-topped passenger fire has no reviewed DTA reward implementation. Passenger
  capacity support alone does not establish passenger firing support.
- MO stolen-tech rosters have no direct DTA equivalent. Use DTA-native support
  or prototype unlocks instead.
- Special-building income is currently excluded. Installed `ProduceCashAmount`
  fields warrant a separate runtime review before offering an income upgrade.

The first expansion should prioritize fortified infrastructure, transport
capacity and one DTA-specific utility line, followed by enemy regeneration or
cloaking. This adds different decisions without duplicating the existing tier
health/firepower/fire-rate perks.

## Source references

- Each launcher's `configs/final_fortress.json` supplies the compared perk and
  Challenge counts and descriptions.
- DTA `randomizer/rewards/dta_definitions.py` defines buff eligibility.
- DTA `randomizer/dta/clones.py` implements private unit and weapon overrides.
- DTA `randomizer/dta/movement.py` implements Amphibious Drive eligibility.
- DTA `randomizer/maps/shop_modifiers.py` implements storage and transport
  modifier handling.
- DTA `randomizer/maps/enemy_scripting.py` implements campaign Ion Thunderbolt
  and native script pressure modifiers.
- DTA `randomizer/final_fortress/challenges.py` restricts current Fortress
  Challenge support.
- Installed DTA `INI/Rules.ini`, `INI/Art.ini` and MIX assets supply the building
  and support-unit identities reviewed above.
