# DTA player-buff policy

## Confirmed direct path

DTA already applies player campaign bonuses by writing difficulty/house multipliers into the generated map's `[Normal]` section. `INI/CampaignBonuses.ini` and the installed `[Normal]` defaults expose broad modifiers for `Armor`, `Groundspeed`, `Airspeed`, `Cost`, `BuildTime`, `ROF`, and `Firepower`.

Vinifera's official `TechnoClassExtension::Time_To_Build` implementation multiplies every TechnoType's build time by the owning house's `BuildSpeedBias`, then by the individual type's `BuildTimeMultiplier`. Buildings derive from TechnoType, so the generated human difficulty `BuildTime` value is the correct direct route for both units and buildings. The launcher log records the exact emitted value for live timing comparisons.

The randomizer uses this path for broad player-army rewards. These modifiers do not change a TechnoType, weapon, map placement, TaskForce, trigger, or script identity.

## Unit-specific conclusion

No installed DTA/Vinifera metadata exposes a verified modifier scoped to both one TechnoType and only the human player. Vinifera's house-modifier support is house-wide, not unit-type-specific. Therefore a reward such as `RIFLEMAN +25% damage` cannot currently use the direct broad modifier without also affecting every player unit.

Unit-specific rewards use a guarded map-local player-production clone. The original type is never modified by a unit-specific buff, even when a static scan finds no current collision, because the original definition remains map-global.

## Mandatory clone routing

When unit-specific rewards are added:

1. Never replace an object already placed in the mission map.
2. Never rewrite authored TaskForces, Teams, triggers, scripts, or reinforcement identities to the player clone.
3. Scan player and non-player placements plus authored references for diagnostics and unsafe production-house sharing.
4. Keep the original type unchanged and create a player production clone.
5. Route only newly produced human units to the clone. Starting and map-placed player units stay original.
6. If reliable human-only production routing is unavailable, omit the reward rather than risk enemy buffs or mission breakage.

The collision audit is implemented in `randomizer/dta/rules.py`. The Vinifera production-clone writer is implemented in `randomizer/dta/clones.py`. Clone behavior still needs a live engine test before it is treated as fully verified.

## Mobile-unit access isolation

The canonical dashboard catalogue contains 116 reviewed non-AI mobile types from the installed DTA rules: 20 infantry, 56 regular vehicles/naval types, 8 aircraft, and 32 skirmish/campaign special units. Obsolete mission aliases are deduplicated. Of these, 105 can become access rewards; Engineer, the four MCVs, both resource harvesters, and the four faction hovercraft transports are permanent essentials.

Every unit-specific buff uses a separate player-production clone. This applies even when a static map scan finds no enemy copy, because changing the original TechnoType would still be map-global. If access randomization is enabled, a buff is applied only after the matching unit access has been earned. Old save rewards that violate this ordering are skipped safely.

Vinifera parses `RequiredHouses` and `ForbiddenHouses` into HouseType masks but checks those masks against the producing scenario house's `ActsLike` index. The adapter therefore resolves custom campaign houses such as `TutorialGDI` to their production HouseType (`GDI`) before writing restrictions or clone ownership. The previous exact scenario-house values parsed successfully but had no production effect.

Every earned mobile type receives a map-local `_PLAYER` clone owned by the resolved production HouseType. The clone uses `TechLevel=1`; inherited prerequisites, `BuiltAt`, and `BuildLimit` are removed so its production category can use the player's appropriate factory without tech or quantity restrictions. The original type is blocked only for player production. No placed object, TaskForce, TeamType, trigger, script, or reinforcement entry is rewritten.

Standard mode activates earned access and unit buffs only when their reward faction matches the selected mission. Chaos mode deliberately permits cross-faction access. This prevents Soviet rewards, for example, from appearing in a GDI Standard mission.

When an active hostile campaign house shares the player's `ActsLike` production bit, Vinifera offers no exact scenario-house restriction that can isolate the player. Access routing and collision-driven clones are skipped for that mission and the reason is logged. This preserves enemy production and follows the rule that an unsafe player-only reward must not leak to enemies or break authored behavior.
