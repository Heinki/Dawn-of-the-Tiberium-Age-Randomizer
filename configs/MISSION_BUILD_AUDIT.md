# Mission build classification audit

Reviewed against the installed loose DTA maps, their house ownership, map-local
rules, registered reinforcement teams, ownership-transfer scripts/triggers, and
briefings. All 121 configured mission codes are covered below. This is a source
review, not a claim that every mission has been played through.

- `base_build`: the player can obtain a functional construction yard or deployable
  MCV during normal mission progression, including later phases or required captures.
- `no_build_production`: the player can train/build units through existing,
  transferred, captured, or deployed factories, without normal base construction.
- `true_no_build`: normal play uses supplied, discovered, stolen, or scripted
  forces/powers without a player production economy.

Enemy/allied MCVs alone do not establish player construction. A negative factory
`TechLevel` does not disable an existing factory; `Factory=none` does. Initial
ownership alone also misses mission phase changes. Fixed-unit missions are judged
by their playable progression, not incidental opportunities to capture an enemy
base outside their intended objectives.

Tutorial 1 teaches movement/combat and remains `true_no_build`. Tutorial 2 teaches
construction and is `base_build`. The classification map in `missions.json` is the
authoritative source for normal and bonus catalogue entries, labels, and filters.

The current `Battle.ini` plus the configured bonus entry registers 93 missions.
The other 28 reviewed codes belong to optional campaigns/maps; their classification
entries do not register missions by themselves. They enter through `BattleE.ini`
when that catalogue and the corresponding map are installed.

All map filenames below are relative to the game's `Maps/Missions` directory.

| Mission code | Classification | Map | Evidence |
| --- | --- | --- | --- |
| `M_TUTORIAL1` | `true_no_build` | `tutorial1.map` | Combat tutorial with supplied units; no player factory or MCV. |
| `M_TUTORIAL2` | `base_build` | `tutorial2.map` | Team 01000002 delivers GMCV; script 01000000 transfers it to TutorialGDI. The briefing explicitly asks the player to build a base. |
| `M_SE1` | `base_build` | `se01.map` | Player MCV reinforcement team 01000031. |
| `M_SE2` | `base_build` | `se02.map` | Trigger 01000033 transfers the Nod base, including NFACT, to Player. |
| `M_SE3` | `base_build` | `se03.map` | The required hijacking objective gives the player the GDI MCV. |
| `M_SE4` | `no_build_production` | `se04.map` | Outpost barracks/airstrips transfer to Nod; no player construction yard or MCV. |
| `M_SE5` | `base_build` | `se05.map` | Nod initially owns a functional NFACT and unit factories. |
| `M_SE6` | `base_build` | `se06.map` | The objective builds NMCV from the captured Soviet factory. NMCV deploys into NFACT; the launcher also supplies this MCV as a runtime mission fix. |
| `M_SE7` | `true_no_build` | `se07.map` | Interior infiltration with supplied units. |
| `M_SE8` | `true_no_build` | `se08.map` | Infiltration and stolen naval units; no player production base. |
| `M_SE9` | `base_build` | `se09.map` | Phase-two transport team 01000104 contains the player MCV. |
| `M_SE10` | `base_build` | `se10.map` | Nod initially owns a functional NFACT. |
| `M_SE11` | `base_build` | `se11.map` | The NodFortress base, including NFACT and NMCV, transfers to Nod. |
| `M_SEEXT` | `base_build` | `seext.map` | Intro team 01000027 transports NMCV for Nod. |
| `M_PTTP1` | `base_build` | `pttp1.map` | Team 01000098 delivers SMCV under Soviet1. Its tag 01000040 attaches the timed ownership transfer 01000039, giving it to Soviet. |
| `M_PTTP2` | `true_no_build` | `pttp2.map` | Prison rescue with supplied forces; no player factory or MCV. |
| `M_PTTP3` | `base_build` | `pttp3.map` | Soviet initially owns SFACT. |
| `M_PTTP4` | `base_build` | `pttp4.map` | Soviet initially owns SFACT. |
| `M_PTTP5` | `true_no_build` | `pttp5.map` | Infiltration/heist with scripted forces; no player production base. |
| `M_PTTP6` | `base_build` | `pttp6.map` | Soviet initially owns SFACT. |
| `M_PTTP7` | `no_build_production` | `pttp7.map` | Soviet owns aircraft production. Enemy construction yards and ground factories cannot be captured. |
| `M_PTTP8` | `no_build_production` | `pttp8.map` | The objective captures GDI Weapons Factories for Mammoth production. GFACT cannot be captured; the Nod factories are destruction targets. |
| `M_PTTP9` | `base_build` | `pttp9.map` | Both campaign routes spawn a player SMCV (teams 01000051 and 01000631). |
| `M_CR1` | `base_build` | `cr01.map` | Player MCV team 01000073 is reinforced by start trigger 01000080. |
| `M_CR2` | `no_build_production` | `cr02.map` | Trigger 01000035 transfers the Orca airbase to CRAllies; no player MCV. |
| `M_CR3` | `base_build` | `cr03.map` | Trigger 01000049 transfers Allies1, including AFACT; a later train also delivers an MCV. |
| `M_CR4` | `no_build_production` | `cr04.map` | The Commando opening is followed by player Enforcer team 01000161. BFRT deploys into the infantry factory DBFRT; a later outpost transfer also gives AWEAP. No player construction yard or MCV. |
| `M_CR5` | `base_build` | `cr05.map` | After retaking the bridgehead, team 01000056 delivers AMCV. |
| `M_CR6` | `base_build` | `cr06.map` | Trigger 01000233 transfers the shore base, including AFACT, to Allies. |
| `M_CR7` | `true_no_build` | `cr07.map` | Spy infiltration with supplied forces. |
| `M_CR8` | `base_build` | `cr08.map` | The Enforcer phase is followed by player MCV team 01000050. |
| `M_CRA9` | `true_no_build` | `cra09.map` | Sensor Array escort. The discovered service-depot outpost provides repair support, not production. |
| `M_CRA10` | `base_build` | `cra10.map` | Player MCV landing team 01000008. |
| `M_CRA11` | `base_build` | `cra11.map` | Player MCV teams 01000016 and 01000017. |
| `M_CRA12` | `no_build_production` | `cra12.map` | The train supplies engineers to capture city factories; no construction yard or MCV is supplied. |
| `M_CRA13` | `base_build` | `cra13.map` | Player MCV team 01000047. |
| `M_CRA14` | `base_build` | `cra14.map` | Player MCV team 01000060. |
| `M_CRB9` | `true_no_build` | `crb09.map` | Interior spy mission. |
| `M_CRB10` | `true_no_build` | `crb10.map` | Mobile HQ escape with discovered combat forces; no player factory or MCV. |
| `M_CRB11` | `base_build` | `crb11.map` | The objective captures a War Factory and builds an MCV to establish a base. |
| `M_CRB12` | `base_build` | `crb12.map` | Landing hovercraft team 01000123 delivers GMCV after the opening phase. |
| `M_CRB13` | `base_build` | `crb13.map` | Player GMCV team 01000004. |
| `M_CRB14` | `base_build` | `crb14.map` | GDI initially owns GMCV (Units entry 54). |
| `M_CRB15` | `base_build` | `crb15.map` | Trigger 01000091 transfers GDI1, including GFACT, after the SAM sites are destroyed. |
| `M_CRB16` | `base_build` | `crb16.map` | Player GMCV team 01000160. |
| `M_CRB17` | `base_build` | `crb17.map` | GDI initially owns GMCV. |
| `M_CRC9` | `base_build` | `crc09.map` | Engineers capture critical Soviet buildings, including capturable SFACT; the briefing calls for expansion. |
| `M_CRC10` | `base_build` | `crc10.map` | Player MCV team 01000110 arrives under Allies1 and transfers to Allies. |
| `M_CRC11` | `no_build_production` | `crc11.map` | Engineers take over the Soviet outpost with a functional RABARR. The launcher explicitly includes Soviet in player_production_houses; no MCV or construction yard. |
| `M_CRC12` | `base_build` | `crc12.map` | Player MCV team 01000163 follows the Battle Rig opening. |
| `M_CRC13` | `base_build` | `crc13.map` | PlayerAllies initially owns AMCV. |
| `M_CRC14` | `base_build` | `crc14.map` | Allies initially owns AMCV. |
| `M_CRC15` | `base_build` | `crc15.map` | Allies initially owns AMCV. |
| `M_CRC16` | `base_build` | `crc16.map` | Player initially owns AMCV. |
| `M_CREXT` | `base_build` | `crext.map` | Player MCV transport teams 01000005 and 01000016. |
| `M_TTD_LOST_POSITION` | `base_build` | `tte1a.map` | Trigger 01000012 transfers the discovered GDI2 base, including GFACT, to TTEGDI. |
| `M_TTD_THE_BREAKTHROUGH` | `true_no_build` | `tte2a.map` | Escape with surviving/discovered forces. The transferred shipyard is explicitly Factory=none. |
| `M_TTD_THE_FRONTAL_DUEL` | `base_build` | `tte3a.map` | TTEGDI initially owns GFACT. |
| `M_TTD_THE_TOXIC_TIME_TRIAL` | `base_build` | `tte4a.map` | TTEGDI initially owns GFACT. |
| `M_TTD_THE_RECTIFICATION` | `base_build` | `tte4b.map` | TTEGDI initially owns GFACT. |
| `M_TTD_THE_RAIN_OF_DEATH` | `base_build` | `tte4c.map` | Nod-aligned phase supplies player NMCV through the MCV reinforcement teams. |
| `M_TTD_THE_CONVERSION` | `base_build` | `tte4d.map` | Player MCV team 01000237 supplies NMCV in the Nod-aligned phase. |
| `M_ICFRA12` | `base_build` | `icfra1&2.map` | The discovered outpost permits production; later reinforcement team 01000059 supplies deployable AMCV to icfRA. |
| `M_ICFRA3` | `base_build` | `icfra3.map` | Starting MCV team 01000008 reinforces AMCV to icfRA. |
| `M_ICFRA4` | `true_no_build` | `icfra4.map` | Interior ant-nest assault with supplied forces. |
| `M_CD1` | `true_no_build` | `rsovm1.map` | Commando operation with supplied forces. |
| `M_CD2` | `base_build` | `rsovm2.map` | Soviet initially owns SMCV. |
| `M_CD3` | `base_build` | `rsovm3.map` | Soviet initially owns SFACT. |
| `M_CD4` | `true_no_build` | `rsovm4.map` | Convoy interception with supplied forces. |
| `M_CD5` | `base_build` | `rsovm5.map` | Soviet initially owns SFACT. |
| `M_CD6` | `base_build` | `rsovm6.map` | Soviet initially owns SFACT. |
| `M_CD7` | `true_no_build` | `rsovm7.map` | Mobile HQ escape; no player factory or MCV. |
| `M_CD8` | `base_build` | `rsovm8.map` | Soviet initially owns SMCV. |
| `M_UNDER_SIEGE_2` | `base_build` | `unsiege2.map` | GDI initially owns GFACT. |
| `M_MAYDAY` | `base_build` | `mayday.map` | Phase-two trigger 01000041 delivers GMCV team 01000088. |
| `M_BUNNY_HUNT` | `base_build` | `eastermission1.map` | Starting MCV team 01000029; objective 1 requires deploying it. |
| `M_CURFEW_BREAKER` | `base_build` | `curfew_breaker.map` | GDI initially owns GMCV. |
| `M_OP_GUIL` | `true_no_build` | `op_guil.map` | Beach assault with supplied forces. |
| `M_REUNIFICATION` | `true_no_build` | `reunific.map` | Naval/ground assault with scripted reinforcements. Nod1 retains its allied base; it never transfers to the player. |
| `M_SHADOW_REPRISAL` | `no_build_production` | `shadow_reprisal.map` | Nod owns a refinery and unit factories, with no construction yard or MCV. |
| `M_STEALTHY_INHIBITION` | `true_no_build` | `si.map` | Convoy attack with supplied stealth forces. |
| `M_SARIN1_RA_CS` | `base_build` | `sarin1_ra_cs.map` | Mission-start trigger 01000026 delivers Allied MCV team 01000028. |
| `M_SARIN2_RA_CS` | `true_no_build` | `sarin2_ra_cs.map` | Infiltration with supplied/stolen forces; no player factory or MCV. |
| `M_DESPERATE_GRIP` | `base_build` | `sandtrapsp.map` | Allies initially owns AFACT. |
| `M_FROSTBITE` | `base_build` | `frstbite.map` | Allies initially owns AFACT. |
| `M_RIVER_RAID` | `base_build` | `river_raid.map` | Reinforcement team 01000012 supplies AMCV after the opening objective. |
| `M_THE_EAST_ASIAN_FRONT` | `base_build` | `asia01.map` | Player MCV team 01000009. |
| `M_DAWN_OF_LIBERATION` | `base_build` | `dawn_of_liberation.map` | Starting AMCV team 01000007. |
| `M_RECLAMATION` | `true_no_build` | `reclamation.map` | Supplied elite force with discovered reinforcements; no player production base. |
| `M_RED_PARADISE` | `base_build` | `crparad.map` | Trigger 01000006 transfers the Soviet2 base, including SFACT, to Soviet. |
| `M_STOMP` | `true_no_build` | `stomp.map` | Tank assault with supplied forces; no player production base. |
| `M_A_BRIDGE_TOO_FEW` | `base_build` | `a_bridge_too_few.map` | Soviet initially owns SMCV. |
| `M_CHAINBREAKER` | `base_build` | `chainbreaker.map` | Player landing team 01000106 delivers SMCV after the harbor objective. |
| `M_HUE` | `true_no_build` | `hardpoints_ugv_edition.map` | The player replaces the MCV with a Tactical UGV; enemy MCVs are not player assets. |
| `M_FUE` | `true_no_build` | `frenzy_ugv_edition.map` | The player replaces the MCV with a Tactical UGV; enemy MCVs are not player assets. |
| `M_CREXT2` | `base_build` | `crextnod.map` | Player MCV transport teams 01000005 and 01000016. |
| `M_RAS01` | `no_build_production` | `ras1.map` | Soviet initially owns aircraft production, with no construction yard or MCV. |
| `M_RAS02` | `base_build` | `ras2.map` | Soviet initially owns SFACT. |
| `M_RAS03` | `true_no_build` | `ras3.map` | Dog/spy hunt; the map explicitly disables the barracks Factory. |
| `M_RAS04` | `base_build` | `ras4.map` | Player MCV team 01000008. |
| `M_RAS05` | `base_build` | `ras5.map` | Initial player MCV team 01000007. |
| `M_RAS06` | `base_build` | `ras6.map` | Initial player MCV team 01000017. |
| `M_RAS07` | `true_no_build` | `ras7.map` | Interior reactor mission with engineers and supplied units. |
| `M_RAS08` | `base_build` | `ras8.map` | Initial player MCV team 01000028. |
| `M_RAS09` | `base_build` | `ras9.map` | Introduction trigger 01000052 transfers Soviet1, including SFACT, to Soviet. |
| `M_RAS10` | `no_build_production` | `ras10.map` | Introduction trigger 01000048 transfers Soviet1 airfields/barracks to Soviet; no construction yard or MCV. |
| `M_RAS11` | `base_build` | `ras11.map` | Phase-three landing team 01000152 supplies SMCV. |
| `M_RAS12` | `base_build` | `ras12.map` | Player MCV team 01000059. |
| `M_SDA1` | `no_build_production` | `sda01.map` | Trigger 01000246 transfers the functional RATENT to Allies; no construction yard or MCV. |
| `M_SDA2` | `base_build` | `sda02.map` | Starting player MCV team 01000006. |
| `M_SDA3` | `base_build` | `sda03.map` | Starting player MCV team 01000026. |
| `M_SDA4` | `base_build` | `sda04.map` | Starting player MCV team 01000003. |
| `M_SDA5` | `no_build_production` | `sda05.map` | Start trigger 01000037 transfers the Allies1 airbase to Allies; no construction yard or MCV. |
| `M_SDA6` | `no_build_production` | `sda06.map` | Allies initially owns a functional RATENT supporting the prototype; no construction yard or MCV. |
| `M_SDA7` | `base_build` | `sda07.map` | Starting player MCV team 01000029. |
| `M_JC1` | `true_no_build` | `jc1.map` | Mercenary rescue/protection mission with supplied forces. |
| `M_American Gambit` | `base_build` | `ag01.map` | Nod Spawn MCV team 01000001. |
| `M_FRENZY` | `base_build` | `frenzy.map` | GDI initially owns GMCV. |
| `KITEMAP` | `base_build` | `kitemap.map` | Soviet initially owns SMCV. |
| `M_PEACE` | `base_build` | `peace.map` | Starting player MCV team 01000012. |
| `M_DARK_NIGHT` | `true_no_build` | `dark_night.map` | Tanya/spy interior missile-silo operation; no player factory or MCV. |
