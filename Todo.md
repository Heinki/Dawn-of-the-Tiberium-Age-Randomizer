- When the mission has paradrops (e.g. by checking if the PARADROP task force exists in the map), consider skipping setting the paradrop in the map. In CRB#16, you get mission-based paradrops of a bunch of Grenade Launcher - but the Randomizer reset them to be rifles instead, making the mission harder than it is supposed to be. -> We do not overwrite the paradrop on the mission if there is a paradrop skill given
- Use the labels used by the mission to determine difficulty. For instance, CRC#14's doesn't have "Easy", so don't suggest it as Game Difficulty: Easy. If the lowest difficulty that the mission has in "Hard", then consider the mission as Hard. You can use the DifficultyLabels labels to see which difficulty levels are supposed by the game, which are typically: Easy, Normal, Hard, Brutal, Extreme, Ultimate. -> we already do but just to ensure it is not saying easy when it is not
- In the Current Loadout screen, the cameo of the Paradrop is not being loaded for some reason
- Also, I think it would be interesting if the randomizer would decide the preconditions for you rather than let you set them, at least in Shop Mode. There's no reason otherwise why I wouldn't always set the preconditions in my favor. But you could then make it possible for players to "unlock" the choice for gems/ore. -> Adjust with unlocks in ore for shopmode
- This isn't very clear if it unlocks Self Healing immediately for units that don't typically self-heal; I was wondering if it would only take effect once a MG would reach Elite. Might be nice to improve how clear it is. I went and checked the code and it seems to add SelfHealing=yes, so it unlocks self-healing in addition to making them heal faster.
I wonder if those should be separate buffs though
Gives self healing regardless of veterancy
Increases self healing cap from 50% to 100%
Increases regeneration tick rate A buff that unlocks Self Healing on Veteran (can be done through the SELF_HEALING veteran ability, same as how they self-heal when elite), then on Rookie veterancy levels (with SelfHealing=yes)
A buff that increases Self Healing cap by a step, from 50% to 100% (by tweaking SelfHealingCap)
A buff that increases Self Healing rate by a step (by tweaking SelfHealingRate)
- When you lose and the Shop Run ends, the mission selections should be hidden. I tried clicking on "Relaunch this mission" or "Launch this mission" a few times, scratching my head on why the button doesn't work. 
Instead, just show clearly that the run ended with bold letters and a big, obvious button. 
It shouldn't say "Give up Run" because that sounds like you have a choice. Should be something like "Start New Run" instead.
- T3 Shocktrooper unit is too expensive in comparrison to other T3 unit (Machine Gunner, Grenade Launcher)
Operation Guillotine's enemy AI doesn't do anything. No building or attacking except for the scripted attacks. I know the Mental Omega randomizer had caused the AI to be asleep in the earlier releases so not sure if its the same for this mission here
- T1 AA defenses are not given sometimes, people complained they either get one defense and that is it.
- Chinook as a standard unit given from the start so that people can use an air transport unit on missions and maps
- Goverment forces are affected by unit upgardes on CRB9 (the mission with the spy)
- Change rotation of factions not always the same like gdi -> nod -> allied -> soviets, but determine the order randomly ONCE per run and then go for that until the run ends.

Additional notes:
Check if any of the Naval Yard are something the player can build naturally on the map or not. If they cannot, then don't give them a Naval Yard -> see if that even works
So what that means, probably, is that your randomizer only writes the Rules.ini into the map, but not Enhanced.ini - There seems o be more information regarding the maps TD and normal DTA maps are different and change incosts and how units work e.g.


Archipelago Issues and Shopmode UI for ALL Randomizers:
- Issue with Archipelago: every mission where alstar had the final reward is now completed
it wasnt even found i got them just now
- Reset Profile is not well set in the layout
- Remove the Right side with details/unlocks/neutral in Shopmode, people are confused what it is doing and all the essential information is in the shopmode tab
- In Shop Mode, keep the currencies always visible at the top. I find myself going up and down constantly to check how much Ore I have, compared to how much I need for buying buffs -> Ensure currency is always on top in the Tab!
- Multiworld Traps not working for enemy buffs.